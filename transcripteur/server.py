#!/usr/bin/env python3
"""
Serveur local du transcripteur.

Lancement :
    python -m transcripteur

Les fichiers ne quittent la machine que pour l'appel de transcription Groq.
La diarisation et le découpage restent locaux.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import assets, config, relecture, pipeline
from .pipeline import Cancelled, Options, PipelineError

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 Go

app = FastAPI(title="Transcripteur", docs_url=None, redoc_url=None)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
# Un seul traitement à la fois : pyannote monopolise le CPU (ou le GPU),
# deux jobs en parallèle sont plus lents que deux jobs à la suite.
_gate = threading.Semaphore(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set(job_id: str, **fields) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job:
            job.update(fields)


def _public(job: dict) -> dict:
    return {
        "id": job["id"],
        "filename": job["filename"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": round(job["progress"], 3),
        "error": job["error"],
        "duration": job["duration"],
        "speakers": job["speakers"],
        "blocks": job["blocks"],
        "names": job["names"],
        "notes": job["notes"][-12:],
        "relecture": job.get("relecture"),
        "created_at": job["created_at"],
    }


def _run_job(job_id: str, options: Options) -> None:
    with _gate:
        job = _jobs.get(job_id)
        if job is None or job["status"] == "cancelled":
            return

        src = Path(job["source"])
        work_dir = Path(job["work_dir"])

        def progress(stage: str, ratio: float) -> None:
            _set(job_id, stage=stage, progress=ratio)

        def notify(message: str) -> None:
            with _lock:
                current = _jobs.get(job_id)
                if current is not None:
                    current["notes"].append(message)
                    del current["notes"][:-60]

        def stop() -> bool:
            current = _jobs.get(job_id)
            return current is None or current.get("cancel", False)

        _set(job_id, status="running")
        try:
            result = pipeline.process(src, work_dir, options, progress, notify, stop)
        except Cancelled:
            _set(job_id, status="cancelled", stage="Arrêté", progress=0.0)
            return
        except PipelineError as exc:
            _set(job_id, status="error", error=str(exc), stage="Arrêt")
            return
        except Exception as exc:  # noqa: BLE001
            _set(job_id, status="error", error=f"Erreur inattendue : {exc}", stage="Arrêt")
            return

        names = {s["id"]: "" for s in result.speakers}
        _set(
            job_id,
            status="done",
            stage="Terminé",
            progress=1.0,
            duration=result.duration,
            speakers=result.speakers,
            blocks=result.blocks,
            names=names,
        )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {
        "has_key": bool(config.get_key()),
        "key_from_env": bool(os.environ.get("GROQ_API_KEY")),
        "models_ready": assets.models_ready(),
    }


@app.post("/api/key")
def save_key(payload: dict) -> dict:
    key = str(payload.get("key", ""))
    problem = config.check_key(key)
    if problem:
        raise HTTPException(400, problem)
    config.set_key(key)
    return {"has_key": True}


@app.delete("/api/key")
def forget_key() -> dict:
    config.clear_key()
    return {"has_key": bool(config.get_key())}


@app.get("/api/models")
def list_models(langue: str = "") -> dict:
    """Le catalogue des modèles de voix, le plus adapté à la langue en tête.

    L'ordre suit la langue d'entraînement de chaque modèle. Ce n'est pas un
    classement de précision : départager deux modèles d'une même famille
    demanderait un enregistrement annoté que nous n'avons pas."""
    return {"modeles": assets.inventaire(langue or None),
            "defaut": assets.DEFAULT_EMBEDDING,
            "nettoyeurs": assets.inventaire_debruiteurs(),
            "nettoyeur_defaut": assets.DEBRUITEUR_DEFAUT}


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    language: str = Form("fr"),
    speakers: str = Form(""),
    diarize: str = Form("true"),
    embedding: str = Form(""),
    denoise: str = Form(""),
) -> JSONResponse:
    def as_int(value: str) -> int | None:
        value = (value or "").strip()
        return int(value) if value.isdigit() and int(value) > 0 else None

    if not config.get_key():
        raise HTTPException(400, "Aucune clé Groq enregistrée.")

    job_id = uuid.uuid4().hex[:12]
    work_dir = Path(tempfile.mkdtemp(prefix=f"transcripteur_{job_id}_"))
    suffix = Path(file.filename or "audio").suffix or ".bin"
    source = work_dir / f"source{suffix}"

    written = 0
    with open(source, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                out.close()
                shutil.rmtree(work_dir, ignore_errors=True)
                raise HTTPException(413, "Fichier trop volumineux (limite : 2 Go).")
            out.write(chunk)

    if written == 0:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(400, "Fichier vide.")

    job = {
        "id": job_id,
        "filename": file.filename or "audio",
        "source": str(source),
        "work_dir": str(work_dir),
        "status": "queued",
        "stage": "En file d'attente",
        "progress": 0.0,
        "error": None,
        "duration": 0.0,
        "speakers": [],
        "blocks": [],
        "names": {},
        "notes": [],
        "relecture": None,
        "cancel": False,
        "created_at": _now(),
    }
    with _lock:
        _jobs[job_id] = job

    options = Options(
        language=(language or "").strip() or None,
        num_speakers=as_int(speakers),
        diarize=diarize.lower() != "false",
        embedding="auto" if embedding == "auto" else assets.resoudre(embedding),
        denoise=denoise if denoise in assets.DEB_PAR_CLE else "",
        api_key=config.get_key(),
    )

    threading.Thread(target=_run_job, args=(job_id, options), daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


def _run_relecture(job_id: str, attribution: bool, texte: bool, modele: str) -> None:
    """Relit un transcript déjà produit, dans un fil à part.

    Rien n'est appliqué ici : on range des propositions que l'interface
    affiche côte à côte avec l'original. C'est l'utilisateur qui tranche."""
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        return

    def note(message: str) -> None:
        with _lock:
            job["relecture"]["notes"] = (job["relecture"]["notes"] + [message])[-8:]

    try:
        blocs, noms = job["blocks"], job["names"]
        corrections = []
        if attribution:
            corrections += relecture.corriger_attribution(
                blocs, noms, config.get_key(), modele, note=note)
        if texte:
            corrections += relecture.corriger_texte(
                blocs, config.get_key(), modele, note=note)
        apercu = relecture.appliquer(blocs, corrections, noms) if corrections else blocs
        with _lock:
            job["relecture"].update(status="done", corrections=corrections, blocks=apercu)
    except Exception as exc:  # noqa: BLE001
        with _lock:
            job["relecture"].update(status="error", error=str(exc))


@app.get("/api/relecture")
def relecture_options() -> dict:
    return {
        "modeles": [{"cle": k, "nom": v["nom"], "note": v["note"]}
                    for k, v in relecture.MODELES.items()],
        "defaut": relecture.MODELE_DEFAUT,
        "resumes": [{"cle": k, "nom": v[0]} for k, v in relecture.RESUMES.items()],
    }


@app.get("/api/jobs/{job_id}/cout")
def cout_relecture(job_id: str, attribution: int = 1, texte: int = 1) -> dict:
    """Estimation avant de lancer, pour ne pas épuiser un quota sans le voir."""
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Tâche inconnue.")
    return {"jetons": relecture.estimer_jetons(
        job["blocks"], bool(attribution), bool(texte)),
        "blocs": len(job["blocks"])}


@app.post("/api/jobs/{job_id}/relire")
def relire(job_id: str, payload: dict) -> dict:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Tâche inconnue.")
        if job["status"] != "done":
            raise HTTPException(400, "La transcription n'est pas terminée.")
        if job.get("relecture", {}) and job["relecture"].get("status") == "running":
            raise HTTPException(409, "Une relecture est déjà en cours.")
        job["relecture"] = {"status": "running", "notes": [], "corrections": [],
                            "blocks": [], "error": None}
    threading.Thread(
        target=_run_relecture,
        args=(job_id, bool(payload.get("attribution", True)),
              bool(payload.get("texte", True)),
              str(payload.get("modele") or relecture.MODELE_DEFAUT)),
        daemon=True).start()
    return {"ok": True}


@app.post("/api/jobs/{job_id}/resume")
def resume(job_id: str, payload: dict) -> dict:
    with _lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Tâche inconnue.")
    if job["status"] != "done":
        raise HTTPException(400, "La transcription n'est pas terminée.")
    blocs = job["relecture"]["blocks"] if (job.get("relecture") or {}).get("blocks") \
        else job["blocks"]
    try:
        texte = relecture.resumer(blocs, job["names"], config.get_key(),
                                  str(payload.get("forme") or "compte_rendu"),
                                  str(payload.get("modele") or relecture.MODELE_DEFAUT))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Résumé impossible : {exc}") from exc
    return {"texte": texte}


@app.post("/api/jobs/{job_id}/appliquer")
def appliquer(job_id: str, payload: dict) -> dict:
    """Ré-applique un sous-ensemble de corrections.

    L'utilisateur décoche ce qu'il refuse ; on recalcule à partir de
    l'original, jamais à partir de la version déjà corrigée, sinon les
    refus successifs s'empileraient sur un texte déjà modifié."""
    with _lock:
        job = _jobs.get(job_id)
    if not job or not job.get("relecture"):
        raise HTTPException(404, "Aucune relecture pour cette tâche.")
    gardees = payload.get("corrections") or []
    try:
        apercu = relecture.appliquer(job["blocks"], gardees, job["names"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Corrections inapplicables : {exc}") from exc
    with _lock:
        job["relecture"]["blocks"] = apercu
    return {"blocks": apercu}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, light: int = 0) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    data = _public(job)
    if light and job["status"] != "done":
        data["blocks"] = []
    return data


@app.post("/api/jobs/{job_id}/names")
def set_names(job_id: str, names: dict) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    cleaned = {k: str(v)[:60] for k, v in names.items() if isinstance(k, str)}
    _set(job_id, names={**job["names"], **cleaned})
    return {"names": _jobs[job_id]["names"]}


@app.get("/api/jobs/{job_id}/sample/{index}")
def get_sample(job_id: str, index: int) -> FileResponse:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    sample = Path(job["work_dir"]) / f"sample_{index}.mp3"
    if not sample.exists():
        raise HTTPException(404, "Extrait indisponible.")
    return FileResponse(sample, media_type="audio/mpeg")


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    if job["status"] in ("queued", "running"):
        _set(job_id, cancel=True, stage="Arrêt en cours…")
    return {"status": _jobs[job_id]["status"]}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    with _lock:
        job = _jobs.pop(job_id, None)
    if job:
        shutil.rmtree(job["work_dir"], ignore_errors=True)
    return {"deleted": bool(job)}


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Interface locale de transcription.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7878)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    assets.ensure_models()

    url = f"http://{args.host}:{args.port}"
    print(f"\nTranscripteur prêt : {url}")
    print("Laisse cette fenêtre ouverte. Ferme-la pour arrêter le programme.\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
