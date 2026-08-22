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

from . import assets, config, pipeline
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


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    language: str = Form("fr"),
    speakers: str = Form(""),
    diarize: str = Form("true"),
    embedding: str = Form("standard"),
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
        "cancel": False,
        "created_at": _now(),
    }
    with _lock:
        _jobs[job_id] = job

    options = Options(
        language=(language or "").strip() or None,
        num_speakers=as_int(speakers),
        diarize=diarize.lower() != "false",
        embedding=embedding if embedding in assets.EMBEDDINGS else "standard",
        api_key=config.get_key(),
    )

    threading.Thread(target=_run_job, args=(job_id, options), daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


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
