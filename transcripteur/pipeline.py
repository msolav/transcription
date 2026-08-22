#!/usr/bin/env python3
"""
Cœur du traitement : conversion, séparation des voix, transcription, fusion.

La séparation des voix tourne en local via sherpa-onnx (onnxruntime), sans
PyTorch et sans modèle sous licence à accepter. Seul l'audio compressé part
chez Groq pour la reconnaissance de la parole.
"""

from __future__ import annotations

import subprocess
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import assets

GROQ_MODEL = "whisper-large-v3-turbo"

DEFAULT_MAX_MB = 24
SAMPLE_SECONDS = 6.0
BLOCK_GAP_SECONDS = 2.0
MIN_TURN_AUDIO = 0.30     # tour de parole trop bref pour être autre chose qu'un « hum »
MIN_TURN_SECONDS = 0.45   # durée en dessous de laquelle une bascule est un artefact
MIN_TURN_WORDS = 2        # ou nombre de mots
BOUNDARY_WINDOW = 4       # mots de part et d'autre où chercher une respiration
BOUNDARY_SENTENCE_BONUS = 1.20
BOUNDARY_CLAUSE_BONUS = 0.35
BOUNDARY_DRIFT_COST = 0.06
SHIFT_RESOLUTION = 0.05
SHIFT_STEPS = 12          # ±0,6 s explorées
CLUSTER_THRESHOLD = 0.65
MAX_AUTO_SPEAKERS = 10    # au-delà, la détection automatique a déraillé
AUTO_RETRIES = 3
AUTO_THRESHOLD_STEP = 0.08
TRANSCRIBE_WORKERS = 3
MP3_BYTES_PER_SECOND = 8000  # mono, 64 kbit/s constants

CHANNEL_COLORS = [
    "#3F8EFC", "#E4572E", "#17BEBB", "#F4B942",
    "#A06CD5", "#7DAF3A", "#EC5F8E", "#5B6BF5",
]


class PipelineError(RuntimeError):
    pass


class Cancelled(RuntimeError):
    """Levée quand l'utilisateur arrête le traitement en cours."""


Progress = Callable[[str, float], None]


def _noop(stage: str, ratio: float) -> None:
    pass


_started = time.time()
_notify = None       # transmet les traces à l'interface
_stop = None         # interrogé régulièrement pour savoir s'il faut s'arrêter


def log(message: str) -> None:
    """Trace dans la fenêtre du programme et dans l'interface."""
    print(f"  [{time.time() - _started:6.1f}s] {message}", flush=True)
    if _notify:
        _notify(message)


def checkpoint() -> None:
    """Point d'arrêt : lève Cancelled si l'utilisateur a demandé l'arrêt."""
    if _stop and _stop():
        raise Cancelled()


# --------------------------------------------------------------------------
# ffmpeg
# --------------------------------------------------------------------------

def _run(args: list[str]) -> None:
    """Lance ffmpeg en surveillant les demandes d'arrêt.

    Une conversion de deux heures est un appel bloquant : sans cette
    surveillance, un arrêt demandé ne prendrait effet qu'à la fin."""
    proc = subprocess.Popen(
        [assets.ffmpeg_exe(), "-y", "-loglevel", "error", *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    while proc.poll() is None:
        if _stop and _stop():
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            raise Cancelled()
        time.sleep(0.15)

    _, stderr = proc.communicate()
    if proc.returncode != 0:
        tail = (stderr or "").strip().splitlines()
        raise PipelineError(f"ffmpeg : {tail[-1] if tail else 'conversion impossible'}")


def to_wav16k(src: Path, dst: Path) -> None:
    _run(["-i", str(src), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)])


def to_mp3(src: Path, dst: Path, start: float | None = None,
           duration: float | None = None) -> None:
    """MP3 mono 16 kHz à 64 kbit/s.

    Le -ss passe avant le -i pour que ffmpeg saute à la position demandée
    au lieu de décoder tout ce qui précède."""
    args = []
    if start is not None:
        args += ["-ss", f"{start:.3f}"]
    args += ["-i", str(src)]
    if duration is not None:
        args += ["-t", f"{duration:.3f}"]
    args += ["-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", str(dst)]
    _run(args)


def slice_mp3(src: Path, start: float, duration: float, dst: Path) -> None:
    """Tranche un MP3 sans le réencoder.

    Le -ss est placé AVANT le -i : ffmpeg saute directement à la position
    voulue au lieu de décoder tout ce qui précède. Avec -c copy, découper
    deux heures d'audio prend moins d'une seconde au lieu de plusieurs
    minutes."""
    _run(["-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
          "-c", "copy", str(dst)])


def to_excerpt(src: Path, start: float, duration: float, dst: Path) -> None:
    _run(["-ss", f"{start:.3f}", "-i", str(src), "-t", f"{duration:.3f}",
          "-ac", "1", "-ar", "22050", "-c:a", "libmp3lame", "-b:a", "96k", str(dst)])


def read_wav16k(path: Path):
    """Lit un WAV 16 kHz mono 16 bits en float32. Ni ffprobe, ni librosa."""
    import numpy as np

    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getframerate() != 16000:
            raise PipelineError("Conversion audio inattendue.")
        raw = w.readframes(w.getnframes())
        channels = w.getnchannels()

    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels)[:, 0]
    return samples.astype(np.float32) / 32768.0


# --------------------------------------------------------------------------
# Découpage pour l'envoi
# --------------------------------------------------------------------------

def _halve(src: Path, start: float, duration: float, max_mb: int,
           work_dir: Path, label: str) -> list[tuple[Path, float]]:
    """Filet de sécurité, si une tranche dépasse malgré le calcul."""
    out = work_dir / f"chunk_{label}.mp3"
    to_mp3(src, out, start, duration)
    if out.stat().st_size / 1048576 <= max_mb or duration < 30:
        return [(out, start)]
    out.unlink(missing_ok=True)
    half = duration / 2
    return (_halve(src, start, half, max_mb, work_dir, label + "a")
            + _halve(src, start + half, half, max_mb, work_dir, label + "b"))


def split_audio(src: Path, duration: float, max_mb: int, work_dir: Path,
                progress: Progress = _noop, span: tuple[float, float] = (0.0, 0.0)
                ) -> list[tuple[Path, float]]:
    """Encode directement les tranches finales, en parallèle.

    À 64 kbit/s constants un MP3 pèse 8 000 octets par seconde, donc la
    durée maximale d'une tranche se calcule sans avoir à encoder le fichier
    entier au préalable. Chaque tranche est encodée depuis la source, avec
    un saut à la position voulue, et les encodages tournent en parallèle."""
    import math
    import os
    from concurrent.futures import ThreadPoolExecutor

    budget = max_mb * 1048576 * 0.92 / MP3_BYTES_PER_SECOND
    parts = max(1, math.ceil(duration / budget))
    low, high = span
    log(f"découpage : {parts} tranche(s) de {duration / parts / 60:.0f} min")

    if parts == 1:
        progress("Préparation de l'envoi", high or low)
        full = work_dir / "full.mp3"
        to_mp3(src, full)
        return [(full, 0.0)]

    step = duration / parts
    plan = [(index, index * step,
             step if index < parts - 1 else max(duration - index * step, 0.5))
            for index in range(parts)]

    done = 0

    def encode(item):
        index, start, take = item
        out = work_dir / f"chunk_{index:03d}.mp3"
        to_mp3(src, out, start, take)
        return index, start, out

    workers = max(1, min(parts, (os.cpu_count() or 2), 4))
    log(f"encodage des tranches sur {workers} cœur(s)")
    chunks: list[tuple[Path, float]] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, start, out in pool.map(encode, plan):
            if out.stat().st_size / 1048576 > max_mb:
                out.unlink(missing_ok=True)
                chunks.extend(_halve(src, start, plan[index][2], max_mb,
                                     work_dir, f"{index:03d}x"))
            else:
                chunks.append((out, start))
            done += 1
            if high > low:
                progress("Préparation de l'envoi", low + (high - low) * (done / parts))

    chunks.sort(key=lambda c: c[1])
    return chunks


# --------------------------------------------------------------------------
# Séparation des voix
# --------------------------------------------------------------------------

def diarize(audio, num_speakers: int | None, progress: Progress,
            span: tuple[float, float],
            threshold: float = CLUSTER_THRESHOLD,
            embedding: str = "standard") -> list[tuple[float, float, str]]:
    try:
        import sherpa_onnx
    except ImportError as exc:
        raise PipelineError("sherpa-onnx n'est pas installé.") from exc

    seg_model, emb_model = assets.ensure_models(embedding)

    config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                model=str(seg_model))),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb_model)),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=num_speakers or -1, threshold=threshold),
        min_duration_on=0.3,
        min_duration_off=0.5,
    )
    if not config.validate():
        raise PipelineError(
            "Modèles de séparation illisibles. Supprime le dossier models/ et relance."
        )

    engine = sherpa_onnx.OfflineSpeakerDiarization(config)
    low, high = span
    log("modèles chargés, analyse du signal")

    def report(done: int, total: int) -> int:
        checkpoint()
        progress(f"Séparation des voix {int(100 * done / max(total, 1))} %",
                 low + (high - low) * (done / max(total, 1)))
        return 0

    result = engine.process(audio, callback=report).sort_by_start_time()
    turns = [(float(r.start), float(r.end), f"SPEAKER_{r.speaker:02d}") for r in result]
    if not turns:
        raise PipelineError("Aucune parole détectée dans ce fichier.")
    log(f"{len({t[2] for t in turns})} voix trouvées, {len(turns)} tours")
    return turns


def diarize_auto(audio, progress: Progress, span: tuple[float, float],
                 threshold: float, embedding: str = "standard"):
    """Détection automatique, avec garde-fou sur le nombre de voix.

    Sur un enregistrement bruité ou à plusieurs micros, le regroupement
    part parfois en morceaux et sort des dizaines de « voix » qui sont la
    même personne. Plutôt que de rendre ce résultat inutilisable, on
    resserre le seuil et on recommence."""
    attempt = 0
    while True:
        turns = diarize(audio, None, progress, span, threshold, embedding)
        found = len({t[2] for t in turns})
        if found <= MAX_AUTO_SPEAKERS or attempt >= AUTO_RETRIES:
            if found > MAX_AUTO_SPEAKERS:
                log(f"toujours {found} voix : indique le nombre à la main pour un meilleur résultat")
            return turns
        attempt += 1
        threshold = min(threshold + AUTO_THRESHOLD_STEP, 0.95)
        log(f"{found} voix, c'est trop : nouvel essai avec un regroupement plus large "
            f"(seuil {threshold:.2f}, essai {attempt}/{AUTO_RETRIES})")


# --------------------------------------------------------------------------
# Transcription
# --------------------------------------------------------------------------

def transcribe_chunk(chunk: Path, offset: float, language: str | None, api_key: str) -> list[dict]:
    try:
        from groq import Groq
    except ImportError as exc:
        raise PipelineError("Le paquet groq n'est pas installé.") from exc

    client = Groq(api_key=api_key)
    with open(chunk, "rb") as f:
        payload = f.read()

    params = dict(
        file=(chunk.name, payload),
        model=GROQ_MODEL,
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"],
    )
    if language:
        params["language"] = language

    try:
        result = client.audio.transcriptions.create(**params)
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "401" in message or "invalid_api_key" in message:
            raise PipelineError("Clé Groq refusée. Corrige-la dans les réglages.") from exc
        if "429" in message or "rate_limit" in message:
            raise PipelineError("Quota Groq atteint. Réessaie dans quelques minutes.") from exc
        raise PipelineError(f"Transcription refusée par Groq : {message}") from exc

    data = result if isinstance(result, dict) else result.model_dump()

    # Groq renvoie les mots nus, sans espace de tête : on stocke le mot
    # détouré et on recolle avec des espaces au moment de l'assemblage.
    words = data.get("words") or []
    if words:
        return [{"start": w["start"] + offset, "end": w["end"] + offset,
                 "text": w["word"].strip()}
                for w in words if w.get("word", "").strip()]

    return [{"start": s["start"] + offset, "end": s["end"] + offset,
             "text": s["text"].strip()}
            for s in data.get("segments", []) if s.get("text", "").strip()]


def transcribe_all(chunks, options: "Options", progress: Progress,
                   span: tuple[float, float]) -> list[dict]:
    """Envoie les tranches en parallèle, puis remet les mots dans l'ordre.

    Les tranches sont indépendantes et l'attente est surtout du réseau :
    trois envois simultanés divisent le temps par trois sans surcharger
    le quota."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    low, high = span
    total = len(chunks)
    if total == 1:
        progress("Transcription", low)
        words = transcribe_chunk(chunks[0][0], chunks[0][1],
                                 options.language, options.api_key)
        chunks[0][0].unlink(missing_ok=True)
        return words

    collected: dict[int, list[dict]] = {}
    done = 0

    with ThreadPoolExecutor(max_workers=TRANSCRIBE_WORKERS) as pool:
        futures = {
            pool.submit(transcribe_chunk, path, offset,
                        options.language, options.api_key): (index, path)
            for index, (path, offset) in enumerate(chunks)
        }
        for future in as_completed(futures):
            checkpoint()
            index, path = futures[future]
            collected[index] = future.result()
            path.unlink(missing_ok=True)
            done += 1
            progress(f"Transcription {done}/{total}",
                     low + (high - low) * (done / total))

    words: list[dict] = []
    for index in range(total):
        words.extend(collected[index])
    return words


# --------------------------------------------------------------------------
# Fusion
# --------------------------------------------------------------------------

def _turn_index(turns):
    """Bornes de début, pour retrouver les tours d'un intervalle sans tout parcourir."""
    return [t[0] for t in turns]


def _overlap(start: float, end: float, turns, starts) -> dict[str, float]:
    """Temps de recouvrement entre [start, end] et chaque locuteur."""
    import bisect

    scores: dict[str, float] = {}
    position = max(0, bisect.bisect_right(starts, start) - 2)
    for t_start, t_end, speaker in turns[position:]:
        if t_start >= end:
            break
        gain = min(end, t_end) - max(start, t_start)
        if gain > 0:
            scores[speaker] = scores.get(speaker, 0.0) + gain
    return scores


def speaker_at(start: float, end: float, turns, starts=None) -> str:
    starts = starts if starts is not None else _turn_index(turns)
    scores = _overlap(start, end, turns, starts)
    if scores:
        return max(scores, key=scores.get)
    center = (start + end) / 2
    return min(turns, key=lambda t: min(abs(t[0] - center), abs(t[1] - center)))[2]


def estimate_shift(words: list[dict], turns, starts) -> float:
    """Décalage global entre les horodatages de Whisper et les tours de parole.

    Whisper aligne les mots par déformation temporelle et se trompe
    régulièrement d'un ou deux dixièmes de seconde, toujours dans le même
    sens sur un enregistrement donné. On essaie plusieurs décalages et on
    garde celui qui fait tomber le plus de temps de parole à l'intérieur
    d'un seul tour."""
    sample = words[::3] if len(words) > 3000 else words
    if not sample:
        return 0.0

    best_shift, best_score = 0.0, -1.0
    step = 0
    while step <= SHIFT_STEPS:
        for sign in ((1, -1) if step else (1,)):
            shift = sign * step * SHIFT_RESOLUTION
            score = 0.0
            for word in sample:
                scores = _overlap(word["start"] + shift, word["end"] + shift, turns, starts)
                if scores:
                    score += max(scores.values())
            if score > best_score:
                best_shift, best_score = shift, score
        step += 1
    return best_shift


def _runs(labels: list[str]) -> list[list[int]]:
    runs: list[list[int]] = []
    for index, label in enumerate(labels):
        if runs and labels[runs[-1][0]] == label:
            runs[-1].append(index)
        else:
            runs.append([index])
    return runs


def _ends_sentence(word: dict) -> bool:
    text = word["text"]
    return bool(text) and text[-1] in ".!?…"


def clean_turns(turns):
    """Écarte les tours trop brefs pour être des prises de parole.

    Un « hum » d'un quart de seconde pendant que l'autre parle est un
    signe d'écoute, pas un tour. Filtrer ici plutôt qu'après coup évite de
    juger des bouts de phrase : à ce stade on ne regarde que l'audio, sans
    dépendre de l'endroit où Whisper a placé ses mots."""
    kept: list[list] = []
    for position, (start, end, speaker) in enumerate(turns):
        if end - start >= MIN_TURN_AUDIO:
            kept.append([start, end, speaker])
            continue

        previous = kept[-1][2] if kept else None
        following = None
        for other in turns[position + 1:]:
            if other[1] - other[0] >= MIN_TURN_AUDIO:
                following = other[2]
                break

        # Encadré par la même personne : c'est un débordement, on l'efface.
        if previous is not None and previous == following:
            continue
        if end - start < MIN_TURN_AUDIO * 0.6:
            continue
        kept.append([start, end, speaker])

    merged: list[list] = []
    for turn in kept:
        if merged and merged[-1][2] == turn[2] and turn[0] - merged[-1][1] < 0.4:
            merged[-1][1] = max(merged[-1][1], turn[1])
        else:
            merged.append(turn)

    dropped = len(turns) - len(merged)
    if dropped > 0:
        log(f"tours écartés (trop brefs) : {dropped} sur {len(turns)}")
    return [tuple(t) for t in merged]


def _substantial(run: list[int], words: list[dict],
                 before: str | None, after: str | None) -> bool:
    """Une prise de parole réelle, par opposition à un mot qui déborde.

    Un seul mot ne fait une réplique que s'il forme une phrase entière :
    « Exactement. » précédé d'un point et suivi d'autre chose en est une,
    alors qu'un « 100%. » qui termine le « À 100%. » du voisin n'est que
    la queue d'une phrase mal découpée. La durée ne suffit pas : Whisper
    étire volontiers un mot isolé sur une seconde."""
    opens = run[0] == 0 or _ends_sentence(words[run[0] - 1])
    closes = _ends_sentence(words[run[-1]])

    if len(run) >= MIN_TURN_WORDS + 1:
        return True
    if opens and closes:
        return True
    # Passage de relais entre deux personnes différentes : une accroche
    # ou une chute de phrase suffit. Encadré par la même personne, non.
    if before is not None and before == after:
        return False
    return opens or closes


def _break_score(index: int, words: list[dict]) -> float:
    """À quel point la position `index` est une coupure naturelle."""
    gap = words[index]["start"] - words[index - 1]["end"]
    score = min(gap, 1.5)
    if _ends_sentence(words[index - 1]):
        score += BOUNDARY_SENTENCE_BONUS
    elif words[index - 1]["text"][-1:] in ",;:":
        score += BOUNDARY_CLAUSE_BONUS
    return score


def _snap(cut: int, words: list[dict], floor: int, ceiling: int) -> int:
    """Ramène une frontière sur la respiration la plus proche.

    Les horodatages de Whisper se trompent de quelques dixièmes, donc la
    frontière brute tombe souvent après le premier mot de la réplique
    suivante — le « À » de « À 100% » resté chez la personne d'avant. On
    la déplace de quelques mots, vers une fin de phrase si possible."""
    low = max(floor, cut - BOUNDARY_WINDOW)
    high = min(ceiling, cut + BOUNDARY_WINDOW)
    best, best_score = cut, -99.0
    for candidate in range(low, high + 1):
        if candidate < 1 or candidate >= len(words):
            continue
        score = _break_score(candidate, words) - abs(candidate - cut) * BOUNDARY_DRIFT_COST
        if score > best_score:
            best, best_score = candidate, score
    return best


def snap_boundaries(labels: list[str], words: list[dict]) -> list[str]:
    """Aligne chaque changement de locuteur sur une coupure naturelle."""
    result = list(labels)
    guard = 0
    while guard < 6:
        guard += 1
        runs = _runs(result)
        moved = False
        for position in range(1, len(runs)):
            runs = _runs(result)
            if position >= len(runs):
                break
            cut = runs[position][0]
            floor = runs[position - 1][0] + 1
            ceiling = runs[position][-1] + 1
            target = _snap(cut, words, floor, ceiling)
            if target == cut:
                continue
            speaker, previous = result[cut], result[cut - 1]
            if target < cut:
                for index in range(target, cut):
                    result[index] = speaker
            else:
                for index in range(cut, target):
                    result[index] = previous
            moved = True
        if not moved:
            break
    return result


def assign_speakers(words: list[dict], turns) -> list[str]:
    """Attribue chaque mot, en respectant les changements courts.

    L'ordre compte : on recale d'abord les frontières sur les coupures
    naturelles, et seulement ensuite on décide si une réplique est réelle.
    L'inverse jugeait des bouts de phrase arbitraires et gardait des
    fragments comme « qu'on » ou « 100%. »."""
    turns = clean_turns(turns)
    starts = _turn_index(turns)
    shift = estimate_shift(words, turns, starts)
    if abs(shift) >= SHIFT_RESOLUTION:
        log(f"recalage des horodatages : {shift * 1000:+.0f} ms")

    labels = [speaker_at(w["start"] + shift, w["end"] + shift, turns, starts)
              for w in words]

    labels = snap_boundaries(labels, words)

    changed = True
    while changed:
        changed = False
        runs = _runs(labels)
        for position, run in enumerate(runs):
            before = runs[position - 1] if position else None
            after = runs[position + 1] if position + 1 < len(runs) else None
            if _substantial(run, words,
                            labels[before[0]] if before else None,
                            labels[after[0]] if after else None):
                continue
            if before and after:
                giver = before if len(before) >= len(after) else after
            else:
                giver = before or after
            if giver is None:
                continue
            for index in run:
                labels[index] = labels[giver[0]]
            changed = True
            break

    return snap_boundaries(labels, words)


def build_blocks(words: list[dict], turns) -> list[dict]:
    labels = assign_speakers(words, turns)

    blocks: list[dict] = []
    for word, speaker in zip(words, labels):
        current = blocks[-1] if blocks else None
        gap = word["start"] - current["end"] if current else 0.0
        if current and current["speaker"] == speaker and gap < BLOCK_GAP_SECONDS:
            current["end"] = word["end"]
            current["words"].append(word)
        else:
            blocks.append({"speaker": speaker, "start": word["start"],
                           "end": word["end"], "words": [word]})

    for block in blocks:
        block["text"] = join_words(block["words"])
    return [b for b in blocks if b["text"]]


def join_words(words: list[dict]) -> str:
    """Recolle les mots avec des espaces, sans en mettre avant la ponctuation."""
    out = ""
    for word in words:
        text = word["text"]
        if out and not (text[:1] in ",.;:!?…%)]}" or out[-1:] in "\u2019'([{"):
            out += " "
        out += text
    return out.strip()


def speaker_profiles(turns, blocks, src: Path, out_dir: Path) -> list[dict]:
    order: list[str] = []
    totals: dict[str, float] = {}
    longest: dict[str, tuple[float, float]] = {}

    for t_start, t_end, speaker in turns:
        length = t_end - t_start
        totals[speaker] = totals.get(speaker, 0.0) + length
        if speaker not in longest or length > (longest[speaker][1] - longest[speaker][0]):
            longest[speaker] = (t_start, t_end)

    for block in blocks:
        if block["speaker"] not in order:
            order.append(block["speaker"])
    for speaker in totals:
        if speaker not in order:
            order.append(speaker)

    grand_total = sum(totals.values()) or 1.0
    profiles = []

    for index, speaker in enumerate(order):
        t_start, t_end = longest.get(speaker, (0.0, SAMPLE_SECONDS))
        length = t_end - t_start
        take = min(SAMPLE_SECONDS, max(length, 1.0))
        offset = t_start + max(0.0, (length - take) / 2)

        sample = out_dir / f"sample_{index}.mp3"
        try:
            to_excerpt(src, offset, take, sample)
            has_sample = sample.exists() and sample.stat().st_size > 0
        except PipelineError:
            has_sample = False

        profiles.append({
            "id": speaker,
            "index": index,
            "color": CHANNEL_COLORS[index % len(CHANNEL_COLORS)],
            "speaking_seconds": round(totals.get(speaker, 0.0), 1),
            "share": round(totals.get(speaker, 0.0) / grand_total, 4),
            "turns": sum(1 for t in turns if t[2] == speaker),
            "sample_start": round(offset, 2),
            "sample_seconds": round(take, 2),
            "has_sample": has_sample,
        })
    return profiles


# --------------------------------------------------------------------------
# Enchaînement
# --------------------------------------------------------------------------

@dataclass
class Options:
    language: str | None = "fr"
    num_speakers: int | None = None
    max_mb: int = DEFAULT_MAX_MB
    diarize: bool = True
    embedding: str = "standard"
    api_key: str = ""


@dataclass
class Result:
    duration: float = 0.0
    blocks: list = field(default_factory=list)
    speakers: list = field(default_factory=list)


def process(src: Path, work_dir: Path, options: Options,
            progress: Progress = _noop, notify=None, stop=None) -> Result:
    global _started, _notify, _stop
    _started = time.time()
    _notify, _stop = notify, stop

    if not options.api_key:
        raise PipelineError("Clé Groq absente.")

    log(f"fichier : {src.stat().st_size / 1048576:.0f} Mo")
    progress("Conversion", 0.02)
    wav = work_dir / "audio16k.wav"
    to_wav16k(src, wav)
    audio = read_wav16k(wav)
    duration = len(audio) / 16000.0
    if duration < 0.5:
        raise PipelineError("Fichier trop court, ou sans piste audio exploitable.")
    log(f"durée : {duration / 60:.1f} min — conversion faite")

    checkpoint()
    turns = []
    if options.diarize:
        progress("Séparation des voix", 0.06)
        if options.num_speakers:
            log(f"séparation des voix, {options.num_speakers} demandées "
                f"(modèle « {options.embedding} »)")
            turns = diarize(audio, options.num_speakers, progress, (0.06, 0.52),
                            CLUSTER_THRESHOLD, options.embedding)
        else:
            log("séparation des voix, nombre à déterminer")
            turns = diarize_auto(audio, progress, (0.06, 0.52),
                                 CLUSTER_THRESHOLD, options.embedding)
    del audio
    wav.unlink(missing_ok=True)

    progress("Préparation de l'envoi", 0.55)
    chunks = split_audio(src, duration, options.max_mb, work_dir, progress, (0.55, 0.62))

    checkpoint()
    log(f"{len(chunks)} tranche(s) prête(s), envoi à Groq")
    words = transcribe_all(chunks, options, progress, (0.62, 0.94))
    log(f"transcription terminée : {len(words)} mots")
    checkpoint()

    if not words:
        raise PipelineError("Transcription vide : aucune parole reconnue.")

    progress("Assemblage", 0.94)

    if not turns:
        blocks = [{"speaker": "SPEAKER_00", "start": words[0]["start"],
                   "end": words[-1]["end"], "words": words,
                   "text": join_words(words)}]
        profiles = [{"id": "SPEAKER_00", "index": 0, "color": CHANNEL_COLORS[0],
                     "speaking_seconds": round(duration, 1), "share": 1.0,
                     "turns": 1, "sample_start": 0.0, "sample_seconds": 0.0,
                     "has_sample": False}]
    else:
        blocks = build_blocks(words, turns)
        log(f"{len(blocks)} passages attribués")
        progress("Extraits d'écoute", 0.97)
        profiles = speaker_profiles(turns, blocks, src, work_dir)
        log(f"extraits d'écoute prêts pour {len(profiles)} voix")

    log("terminé")
    progress("Terminé", 1.0)
    return Result(duration=duration, blocks=blocks, speakers=profiles)
