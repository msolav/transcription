"""
La séparation des voix, dans un processus à part.

Pourquoi : sherpa-onnx ignore ce que rend la fonction de rappel de
progression. Mesuré — 669 appels, valeur de retour non nulle dès le
troisième, et le calcul va quand même jusqu'au bout. Lever une
exception depuis ce rappel ne marche pas davantage : elle est avalée
par la couche C++.

Conséquence : sur une réunion de deux heures, « Arrêter » ne pouvait
rien pendant les trois quarts d'heure de séparation. Le bouton
répondait, l'état disait « Arrêt en cours… », et la machine continuait.

Un processus séparé se tue. C'est la seule façon d'arrêter vraiment un
calcul qu'on ne peut pas interrompre de l'intérieur.

Appelé par pipeline.diarize, jamais à la main :

    python -m transcripteur.diariseur AUDIO.wav SEG.onnx EMB.onnx \\
        NOMBRE SEUIL FILS

Écrit sur la sortie standard, une ligne à la fois :
    P <faits> <total>     progression
    R <json>              le résultat, en dernier
    E <message>           une erreur
"""

from __future__ import annotations

import json
import sys
import wave


def lire_wav(chemin: str):
    import numpy as np
    with wave.open(chemin, "rb") as w:
        brut = w.readframes(w.getnframes())
    return np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0


def main(argv: list[str]) -> int:
    try:
        audio_path, seg, emb, nombre, seuil, fils = argv[:6]
        import sherpa_onnx

        audio = lire_wav(audio_path)
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=seg),
                num_threads=int(fils)),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=emb, num_threads=int(fils)),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=int(nombre), threshold=float(seuil)),
            min_duration_on=0.3,
            min_duration_off=0.5,
        )
        if not config.validate():
            print("E Modèles de séparation illisibles.", flush=True)
            return 2

        moteur = sherpa_onnx.OfflineSpeakerDiarization(config)

        dernier = [-1]

        def rappel(faits: int, total: int) -> int:
            # Une ligne par pour cent : le parent n'a pas besoin de
            # davantage, et des milliers de lignes coûteraient plus
            # cher à transmettre qu'à calculer.
            cent = int(100 * faits / max(total, 1))
            if cent != dernier[0]:
                dernier[0] = cent
                print(f"P {faits} {total}", flush=True)
            return 0

        res = moteur.process(audio, callback=rappel).sort_by_start_time()
        tours = [[float(r.start), float(r.end), f"SPEAKER_{r.speaker:02d}"]
                 for r in res]
        print("R " + json.dumps(tours), flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"E {exc}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
