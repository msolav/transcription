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
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               Response)

from . import (assets, config, fournisseurs, guide, memoire, relecture,
               pipeline, sous_titres)
from .pipeline import Cancelled, Options, PipelineError

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 Go

app = FastAPI(title="Transcripteur", docs_url=None, redoc_url=None)

_jobs: dict[str, dict] = {}
_lock = threading.Lock()

# Préparée à l'import et non dans main() : lancé par uvicorn, le serveur
# ne passe jamais par main(), et la mémoire resterait vide sans erreur.
try:
    memoire.preparer()
except Exception as exc:  # noqa: BLE001
    # Un disque plein ou un dossier en lecture seule ne doit pas
    # empêcher de transcrire : on perd la mémoire, pas l'outil.
    print(f"Mémoire des séances indisponible : {exc}")


def _retenir(job_id: str) -> None:
    """Range la séance, sans jamais faire échouer ce qui l'a appelée."""
    job = _jobs.get(job_id)
    if not job:
        return
    try:
        memoire.enregistrer(job)
    except Exception as exc:  # noqa: BLE001
        print(f"Séance non enregistrée : {exc}")
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
        # De quoi décider s'il y a lieu de proposer la séparation des
        # voix après coup, et s'il faudra redemander l'enregistrement.
        # `separable` tient aux horodatages des mots : sans eux, aucune
        # attribution n'est possible, et les exports anciens en manquent.
        "separable": bool(pipeline.mots_des_blocs(job["blocks"])),
        "separe": len({b.get("speaker") for b in job["blocks"]}) > 1,
        "audio_present": bool(job.get("source")
                              and Path(job["source"]).exists()),
        # L'aperçu dans l'image suppose les deux : une vidéo, et le
        # fichier encore là. Un transcript rouvert depuis un export n'a
        # plus de vidéo à montrer, même s'il en venait une.
        "video": bool(job.get("video")
                      and job.get("source") and Path(job["source"]).exists()),
        # Les sous-titres se taillent dans les horodatages des mots, les
        # mêmes que la séparation des voix : ce qui n'est pas séparable
        # n'est pas sous-titrable non plus.
        "sous_titrable": bool(pipeline.mots_des_blocs(job["blocks"])),
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
        # Rangée tout de suite : c'est le moment où trois quarts d'heure
        # de calcul viennent d'aboutir, et le seul où les perdre coûte
        # vraiment quelque chose.
        if not memoire.reglages().get("garder_enregistrement", True):
            # Le texte est écrit ; qui ne veut pas garder les
            # enregistrements le dit une fois et n'y pense plus. La
            # séparation des voix après coup et l'aperçu vidéo
            # deviennent impossibles, et la liste des séances le montre.
            src = Path(job["source"]) if job.get("source") else None
            if src and src.exists():
                src.unlink(missing_ok=True)
                _set(job_id, source="", video=False)
        _retenir(job_id)


# L'écran de branchement des clés vit dans son propre fichier, et c'est
# le serveur qui ajoute la balise qui le charge. Deux raisons. L'interface
# est réécrite en parallèle, et une première version de cet écran, placée
# dans le HTML, a été effacée par une réécriture du fichier : ici, rien à
# effacer. Et les deux interfaces — l'actuelle et la refonte — reçoivent
# le même écran sans qu'on ait à le poser deux fois.
_GREFFES = ("branchement.js", "apercu.js", "seances.js")


def _page(nom: str) -> HTMLResponse:
    html = (STATIC_DIR / nom).read_text(encoding="utf-8")
    # On cherche la balise, et non le nom du fichier : un commentaire de
    # l'interface qui mentionne « apercu.js » suffisait à faire croire
    # que le script était déjà posé, et il ne l'était plus nulle part —
    # sans erreur, sans trace, l'aperçu simplement absent.
    manquants = "".join(f'<script src="/static/{g}"></script>\n'
                        for g in _GREFFES if f'src="/static/{g}"' not in html)
    if manquants:
        # Après le script de la page, pour en voir les déclarations.
        html = (html.replace("</body>", manquants + "</body>")
                if "</body>" in html else html + manquants)
    return HTMLResponse(html)


@app.get("/static/{nom}")
def greffe_js(nom: str) -> FileResponse:
    if nom not in _GREFFES:
        raise HTTPException(404, "Fichier inconnu.")
    return FileResponse(STATIC_DIR / nom, media_type="application/javascript")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """La refonte, terminée, est maintenant l'interface.

    Elle vivait à /vm le temps qu'on puisse comparer, et l'ancienne
    tenait la racine. L'application empaquetée ouvrait déjà /vm : on
    livrait donc une interface aux gens et on en voyait une autre en
    développant, ce qui est la meilleure façon de ne pas remarquer ce
    qui s'y casse. L'ancienne reste à /classique, le temps qu'on soit
    sûr de ne rien regretter."""
    if (STATIC_DIR / "index-vm.html").exists():
        return _page("index-vm.html")
    return _page("index.html")


@app.get("/vm", response_class=HTMLResponse)
def index_vm() -> HTMLResponse:
    """Gardée : des essais et des signets pointent ici."""
    return index()


@app.get("/classique", response_class=HTMLResponse)
def index_classique() -> HTMLResponse:
    return _page("index.html")


def _expliquer_cle(exc: Exception, fournisseur: str) -> str:
    """Rend un refus de clé lisible, en nommant d'où venait la clé.

    Une variable d'environnement l'emporte sur le trousseau : une clé
    révoquée oubliée dans un shell est envoyée à la place de la bonne, et
    le message du fournisseur ne dit jamais laquelle il a reçue."""
    message = str(exc)
    if not message.startswith("CLE_REFUSEE::"):
        return message
    fiche = config.FOURNISSEURS.get(fournisseur, {})
    source = config.source_cle(fournisseur)
    ou = {"environnement": f"de la variable {fiche.get('env', '')}",
          "trousseau": "du trousseau du système",
          "simulation": "de la simulation de premier démarrage",
          "fichier": "de l'ancien fichier de configuration"}.get(source, "de nulle part")
    suite = ""
    if source == "environnement":
        suite = (f" Elle vient {ou}, qui l'emporte sur le trousseau : si une"
                 f" clé valide y est enregistrée, relancer le programme après"
                 f" « unset {fiche.get('env', '')} ».")
    elif source:
        suite = f" Elle vient {ou}."
    return (f"Clé {fiche.get('nom', fournisseur)} refusée." + suite)


def _empreinte_code() -> float:
    """Date du fichier source le plus récent de l'application.

    Python importe ses modules une fois pour toutes : modifier le code
    pendant que le serveur tourne ne change rien tant qu'on ne le relance
    pas. L'interface, elle, est relue du disque à chaque chargement de
    page — d'où une situation trompeuse où les réglages ont l'air à jour
    alors que le traitement obéit encore à l'ancien code. Cela s'est
    produit trois fois en une soirée, avec à chaque fois une demi-heure
    perdue à chercher la panne ailleurs."""
    dernier = 0.0
    for fichier in Path(__file__).parent.glob("*.py"):
        try:
            dernier = max(dernier, fichier.stat().st_mtime)
        except OSError:
            continue
    return dernier


# Relevée à l'import, donc figée pour la durée de vie du processus.
_CODE_CHARGE = _empreinte_code()


@app.get("/api/health")
def health() -> dict:
    cles = config.cles_presentes()
    return {
        # Groq reste la clé indispensable : c'est elle qui transcrit.
        "has_key": bool(cles.get("groq")),
        "key_from_env": config.source_cle("groq") == "environnement",
        # Vrai quand le programme tourne en simulation de premier
        # démarrage : l'interface le dit, sinon on finit par croire que
        # les vraies clés ont disparu.
        "vierge": config.en_simulation(),
        "cles": cles,
        "relecture": fournisseurs.modele_par_defaut(cles),
        "models_ready": assets.models_ready(),
        # Vrai quand des fichiers ont changé depuis le démarrage.
        "code_perime": _empreinte_code() > _CODE_CHARGE + 1.0,
    }


# Relevée une fois par lancement : savoir si une version plus récente
# existe n'a pas besoin d'être redemandé toutes les minutes, et une
# requête par démarrage est le minimum défendable pour un programme qui
# ne communique rien d'autre.
_VERSION_VUE: dict = {}
SITE = "https://transcripteur.solav.workers.dev"


def _numero(v: str) -> tuple:
    """« v1.10 » → (1, 10), pour comparer autrement qu'alphabétiquement."""
    chiffres = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in chiffres) if chiffres else ()


@app.get("/api/version")
def version() -> dict:
    """La version installée, et celle qui est publiée.

    Aucun identifiant n'est envoyé : la requête ne dit rien de plus que
    « quelqu'un a lancé le programme ». En cas d'échec — pas de réseau,
    site injoignable — on rend simplement « à jour » et l'interface se
    tait, plutôt que d'inquiéter avec une panne qui n'en est pas une."""
    from . import __version__ as installee
    if "resultat" in _VERSION_VUE:
        return _VERSION_VUE["resultat"]

    publiee = None
    try:
        import urllib.request
        # Un en-tête d'agent explicite : sans lui urllib s'annonce
        # « Python-urllib », que la protection de Cloudflare refuse par
        # 403. Le relevé de version ne marchait donc chez personne, et
        # en silence, puisque l'échec est volontairement muet.
        requete = urllib.request.Request(
            SITE + "/version.json",
            headers={"User-Agent": f"Transcripteur/{installee}",
                     "Accept": "application/json"})
        with urllib.request.urlopen(requete, timeout=6) as r:
            publiee = (json.loads(r.read()) or {}).get("version")
    except Exception:  # noqa: BLE001
        publiee = None

    retard = bool(publiee and _numero(publiee) > _numero(installee))
    _VERSION_VUE["resultat"] = {
        "installee": installee, "publiee": publiee,
        "retard": retard, "url": SITE,
    }
    return _VERSION_VUE["resultat"]


@app.post("/api/ouvrir")
def ouvrir_lien(payload: dict) -> dict:
    """Ouvre une adresse de fournisseur dans le navigateur du système.

    Dans l'application empaquetée, la page vit dans une fenêtre
    pywebview : window.open n'y ouvre rien du tout. Le bouton « Ouvrir
    console.groq.com » ne faisait donc rien, ce qui bloque la
    configuration au premier pas, et c'est le seul pas qu'on ne peut
    pas contourner.

    La liste des adresses permises vient de config.FOURNISSEURS. Un
    point d'entrée qui ouvrirait n'importe quelle adresse sur demande
    de la page serait un moyen commode, pour une page compromise, de
    faire ouvrir n'importe quoi au système."""
    demande = str(payload.get("url") or "").strip()
    permises = {f"https://{f['ou']}" for f in config.FOURNISSEURS.values()}
    if demande not in permises:
        raise HTTPException(400, "Adresse non autorisée.")
    try:
        webbrowser.open(demande)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Ouverture impossible : {exc}") from exc
    return {"ouvert": demande}


@app.get("/api/guide")
def api_guide(langue: str = "fr") -> dict:
    """Le mode d'emploi des clés, dans la langue de l'interface."""
    return guide.pour_interface("en" if langue == "en" else "fr")


@app.get("/aide", response_class=HTMLResponse)
def aide(langue: str = "fr") -> HTMLResponse:
    """La même marche à suivre, en page autonome.

    Elle existe parce que celui qui en a besoin ne peut pas encore lire
    une page servie par le programme : il n'a pas de clé, parfois même
    pas encore installé l'application. Cette page s'enregistre et
    s'envoie par courriel, s'ouvre sans serveur, et s'imprime."""
    return HTMLResponse(guide.page_html(langue))


@app.post("/api/key")
def save_key(payload: dict) -> dict:
    """Enregistre une clé. `fournisseur` vaut groq par défaut."""
    key = str(payload.get("key", ""))
    f = str(payload.get("fournisseur") or "groq")
    langue = "en" if str(payload.get("langue") or "fr") == "en" else "fr"
    if f not in config.FOURNISSEURS:
        raise HTTPException(400, "Fournisseur inconnu.")
    problem = config.check_key(key, f, langue)
    if problem:
        raise HTTPException(400, problem)
    config.set_key(key, f)
    return {"cles": config.cles_presentes()}


@app.delete("/api/key")
def forget_key(fournisseur: str = "groq") -> dict:
    config.clear_key(fournisseur)
    return {"cles": config.cles_presentes()}


@app.get("/api/relecture/modeles")
def modeles_relecture() -> dict:
    """Les modèles de relecture, avec ce qu'ils exigent et ce qu'ils coûtent."""
    cles = config.cles_presentes()
    liste = []
    for cle, m in fournisseurs.MODELES.items():
        liste.append({
            "cle": cle, "nom": m["nom"], "note": m["note"],
            "fournisseur": m["fournisseur"],
            "gratuit": not fournisseurs.payant(cle),
            "dispo": bool(cles.get(m["fournisseur"])),
            "un_appel": m["contexte"] > 100_000,
        })
    # Les utilisables d'abord, puis les gratuits.
    liste.sort(key=lambda x: (not x["dispo"], not x["gratuit"]))
    return {"modeles": liste, "defaut": fournisseurs.modele_par_defaut(cles),
            "fournisseurs": config.FOURNISSEURS}


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

    if not config.get_key("groq"):
        raise HTTPException(400, "Aucune clé Groq enregistrée.")

    job_id = uuid.uuid4().hex[:12]
    # Dans le dossier de données et non dans un dossier temporaire. Le
    # système efface le second quand il veut — l'aperçu vidéo et la
    # séparation des voix après coup ne survivaient donc pas à un
    # redémarrage — et ne l'efface jamais complètement, de sorte que les
    # fichiers s'accumulaient hors de vue. Ici on sait ce qu'ils pèsent
    # et on peut les jeter.
    work_dir = memoire.seances_dir() / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
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
        "video": pipeline.est_video(source),
    }
    with _lock:
        _jobs[job_id] = job

    options = Options(
        language=(language or "").strip() or None,
        num_speakers=as_int(speakers),
        diarize=diarize.lower() != "false",
        embedding="auto" if embedding == "auto" else assets.resoudre(embedding),
        denoise=denoise if denoise in assets.DEB_PAR_CLE else "",
        api_key=config.get_key("groq"),
    )

    # Les réglages sont retenus par l'interface, qui les lit sur les
    # vraies commandes, et non ici où ils arrivent déjà décomposés. Le
    # serveur se contente de les ranger et de les rendre.
    threading.Thread(target=_run_job, args=(job_id, options), daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


def _run_relecture(job_id: str, attribution: bool, texte: bool, modele: str,
                   contexte: str = "") -> None:
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
                blocs, noms, config.get_key(fournisseurs.fournisseur_de(modele)),
                modele, note=note, contexte=contexte)
        if texte:
            corrections += relecture.corriger_texte(
                blocs, config.get_key(fournisseurs.fournisseur_de(modele)),
                modele, note=note, contexte=contexte)
        apercu = relecture.appliquer(blocs, corrections, noms) if corrections else blocs
        with _lock:
            job["relecture"].update(status="done", corrections=corrections, blocks=apercu)
    except Exception as exc:  # noqa: BLE001
        with _lock:
            job["relecture"].update(status="error", error=str(exc))


@app.get("/api/relecture")
def relecture_options() -> dict:
    cles = config.cles_presentes()
    return {
        "modeles": [{"cle": k, "nom": v["nom"], "note": v["note"],
                     "dispo": bool(cles.get(v["fournisseur"]))}
                    for k, v in fournisseurs.MODELES.items()],
        "defaut": fournisseurs.modele_par_defaut(cles),
        "resumes": [{"cle": k, "nom": v["nom"], "apercu": v["apercu"]}
                    for k, v in relecture.RESUMES.items()],
        "resume_defaut": relecture.RESUME_DEFAUT,
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
              str(payload.get("modele") or fournisseurs.modele_par_defaut(config.cles_presentes())),
              str(payload.get("contexte") or "")),
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
    modele = str(payload.get("modele")
                 or fournisseurs.modele_par_defaut(config.cles_presentes()))
    try:
        texte = relecture.resumer(blocs, job["names"],
                                  config.get_key(fournisseurs.fournisseur_de(modele)),
                                  str(payload.get("forme") or relecture.RESUME_DEFAUT),
                                  modele,
                                  str(payload.get("contexte") or ""))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            502, "Résumé impossible : "
            + _expliquer_cle(exc, fournisseurs.fournisseur_de(modele))) from exc
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
    _retenir(job_id)
    return {"blocks": apercu}


def _run_voix(job_id: str, options: Options, mots: list, duree: float) -> None:
    """Sépare les voix d'un transcript déjà écrit, dans un fil à part.

    Le travail se fait sur la tâche elle-même plutôt que sur une
    nouvelle : l'interface suit déjà l'avancement de la tâche ouverte, et
    le résultat remplace son texte au même endroit. En cas d'échec, les
    blocs d'origine sont intacts — on n'écrit qu'une fois le calcul
    abouti."""
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

        # Les blocs d'origine servent de filet : un arrêt ou une panne
        # doit rendre le transcript tel qu'il était, pas une page vide.
        anciens = job["blocks"]
        _set(job_id, status="running", stage="Séparation des voix",
             progress=0.0, error=None, cancel=False)
        try:
            resultat = pipeline.separer_voix(src, work_dir, options, mots,
                                             duree, progress, notify, stop)
        except Cancelled:
            _set(job_id, status="done", stage="Séparation annulée",
                 progress=1.0, blocks=anciens)
            return
        except PipelineError as exc:
            _set(job_id, status="done", stage="Séparation abandonnée",
                 progress=1.0, blocks=anciens, error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            _set(job_id, status="done", stage="Séparation abandonnée",
                 progress=1.0, blocks=anciens,
                 error=f"Erreur inattendue : {exc}")
            return

        _set(job_id, status="done", stage="Terminé", progress=1.0,
             duration=resultat.duration, speakers=resultat.speakers,
             blocks=resultat.blocks,
             names={s["id"]: "" for s in resultat.speakers},
             # L'audio est de nouveau là : les extraits d'écoute et le
             # lecteur redeviennent utilisables.
             sans_audio=False,
             # Une relecture portait sur l'ancien découpage, dont les
             # numéros de blocs ne veulent plus rien dire.
             relecture=None)
        _retenir(job_id)


@app.post("/api/jobs/{job_id}/voix")
async def separer_voix(
    job_id: str,
    file: UploadFile | None = File(None),
    speakers: str = Form(""),
    embedding: str = Form(""),
    denoise: str = Form(""),
    language: str = Form(""),
) -> JSONResponse:
    """Sépare les voix d'un transcript existant, à partir de son audio.

    Rien n'est renvoyé à Groq : le texte existe, chaque mot porte déjà
    son horodatage, et la séparation ne lit que le son. L'opération ne
    consomme donc aucun quota — elle ne coûte que du temps de calcul,
    celui-là même qu'on avait voulu éviter en transcrivant sans séparer
    les voix."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    if job["status"] not in ("done", "error"):
        raise HTTPException(400, "Un traitement est déjà en cours.")

    mots = pipeline.mots_des_blocs(job["blocks"])
    if not mots:
        raise HTTPException(
            400, "Ce transcript ne porte pas les horodatages des mots, qui "
                 "sont ce dont la séparation des voix a besoin. Les exports "
                 "produits par une version ancienne peuvent en manquer.")

    work_dir = Path(job["work_dir"])
    work_dir.mkdir(parents=True, exist_ok=True)

    # L'audio est déjà là quand la transcription vient d'avoir lieu dans
    # cette séance : redemander le fichier à qui vient de le déposer
    # serait une formalité sans raison. Il manque, en revanche, quand le
    # transcript a été rouvert depuis un export.
    ancien = Path(job["source"]) if job.get("source") else None
    if file is None or not (file.filename or "").strip():
        if not (ancien and ancien.exists()):
            raise HTTPException(
                400, "L'enregistrement n'est plus sur cette machine. "
                     "Il faut le fournir de nouveau pour séparer les voix.")
        source = ancien
    else:
        suffix = Path(file.filename or "audio").suffix or ".bin"
        source = work_dir / f"source{suffix}"
        written = 0
        with open(source, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    source.unlink(missing_ok=True)
                    raise HTTPException(413, "Fichier trop volumineux (limite : 2 Go).")
                out.write(chunk)
        if written == 0:
            source.unlink(missing_ok=True)
            raise HTTPException(400, "Fichier vide.")

    nombre = (speakers or "").strip()
    options = Options(
        language=(language or "").strip() or None,
        num_speakers=int(nombre) if nombre.isdigit() and int(nombre) > 0 else None,
        diarize=True,
        embedding="auto" if embedding == "auto" else assets.resoudre(embedding),
        denoise=denoise if denoise in assets.DEB_PAR_CLE else "",
        # Facultative : elle ne sert qu'à reconnaître la langue quand le
        # modèle de voix est laissé en automatique.
        api_key=config.get_key("groq"),
    )
    # Redonner l'enregistrement d'un transcript rouvert, c'est aussi
    # rendre l'aperçu possible : si c'est une vidéo, elle est de nouveau
    # là, et il n'y a pas de raison de ne pas la montrer.
    _set(job_id, source=str(source), video=pipeline.est_video(source))
    threading.Thread(target=_run_voix,
                     args=(job_id, options, mots, float(job["duration"] or 0.0)),
                     daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


@app.post("/api/jobs/import")
async def import_job(file: UploadFile = File(...)) -> dict:
    """Rouvre un transcript déjà produit, exporté en .json.

    Transcrire quatre-vingts minutes demande une dizaine de minutes de
    calcul. Rien ne justifie de les repayer pour rédiger un compte rendu
    dans une autre forme, ou pour reprendre un travail le lendemain : le
    transcript contient déjà tout ce dont la rédaction a besoin."""
    try:
        donnees = json.loads((await file.read()).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "Fichier illisible : attendu un export .json.") from exc

    blocs = donnees.get("blocks")
    if not isinstance(blocs, list) or not blocs:
        raise HTTPException(400, "Ce fichier ne contient pas de transcript.")
    manquant = [c for c in ("speaker", "text", "start") if c not in (blocs[0] or {})]
    if manquant:
        raise HTTPException(400, "Transcript incomplet : il manque "
                                 + ", ".join(manquant) + ".")

    job_id = uuid.uuid4().hex[:12]
    work_dir = Path(tempfile.mkdtemp(prefix="transcripteur-"))
    job = {
        "id": job_id,
        "filename": donnees.get("filename") or file.filename or "transcript.json",
        "source": "", "work_dir": str(work_dir),
        # Rouvert, donc terminé : il n'y a rien à calculer.
        "status": "done", "stage": "Transcript rouvert", "progress": 1.0,
        "error": None,
        "duration": float(donnees.get("duration") or (blocs[-1].get("end") or 0.0)),
        "speakers": donnees.get("speakers") or [],
        "blocks": blocs,
        "names": donnees.get("names") or {},
        "notes": ["transcript rouvert depuis un export"],
        "relecture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Sans l'audio d'origine, pas d'extrait d'écoute : on le signale
        # plutôt que de laisser des boutons de lecture inertes.
        "sans_audio": True,
    }
    for voix in job["speakers"]:
        voix["has_sample"] = False
    with _lock:
        _jobs[job_id] = job
    return _public(job)


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
    _retenir(job_id)
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


_TYPES_MEDIA = {".mp4": "video/mp4", ".m4v": "video/mp4",
                ".mov": "video/quicktime", ".webm": "video/webm",
                ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
                ".ogv": "video/ogg", ".mpg": "video/mpeg",
                ".mpeg": "video/mpeg", ".wmv": "video/x-ms-wmv",
                ".flv": "video/x-flv", ".ts": "video/mp2t",
                ".3gp": "video/3gpp", ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4", ".wav": "audio/wav",
                ".aac": "audio/aac", ".ogg": "audio/ogg",
                ".opus": "audio/opus", ".flac": "audio/flac",
                ".aiff": "audio/aiff", ".aif": "audio/aiff"}


@app.get("/api/jobs/{job_id}/media")
def get_media(job_id: str) -> FileResponse:
    """Renvoie l'enregistrement d'origine, pour l'aperçu.

    FileResponse honore l'en-tête Range, donc le lecteur peut se
    déplacer dans une vidéo de deux heures sans la télécharger d'abord —
    c'est toute la différence entre un aperçu utilisable et un aperçu
    qu'on regarde se charger."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    # La chaîne vide est testée avant d'en faire un Path : `Path("")`
    # vaut `PosixPath('.')`, qui existe toujours. Le contrôle passait
    # donc, et le serveur rendait 500 en essayant d'envoyer un dossier,
    # au lieu de dire que l'enregistrement n'est plus là.
    chemin = str(job.get("source") or "").strip()
    source = Path(chemin) if chemin else None
    if source is None or not source.is_file():
        raise HTTPException(404, "L'enregistrement n'est plus sur le disque.")
    suffixe = Path(job.get("filename") or "").suffix.lower() or source.suffix.lower()
    return FileResponse(source,
                        media_type=_TYPES_MEDIA.get(suffixe,
                                                    "application/octet-stream"),
                        filename=job.get("filename") or source.name)


def _repliques(job_id: str, noms: int):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    try:
        return job, sous_titres.decouper(job["blocks"], job.get("names") or {},
                                         avec_noms=bool(noms))
    except sous_titres.SansHorodatage as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/jobs/{job_id}/soustitres.vtt")
def soustitres_vtt(job_id: str, noms: int = 0) -> Response:
    """Le format que lit une balise <track> : celui de l'aperçu."""
    _, repliques = _repliques(job_id, noms)
    # Pas de cache : les noms changent, et un sous-titre gardé en cache
    # continuerait d'afficher l'ancien nom sans qu'on comprenne pourquoi.
    return Response(sous_titres.vers_vtt(repliques), media_type="text/vtt",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/jobs/{job_id}/soustitres.srt")
def soustitres_srt(job_id: str, noms: int = 0) -> Response:
    """Le format qu'attendent les logiciels de montage et les lecteurs."""
    job, repliques = _repliques(job_id, noms)
    # Un en-tête HTTP ne porte que de l'ASCII : « Réunion du 3.mp4 »
    # ferait échouer la réponse entière. On réduit, et on garde un nom de
    # repli plutôt que de renvoyer un fichier appelé « .srt ».
    stem = Path(job.get("filename") or "").stem
    nom = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "soustitres"
    return Response(
        sous_titres.vers_srt(repliques), media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{nom}.srt"'})


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
    """Retire une tâche de la mémoire vive.

    Les fichiers restent : ils appartiennent maintenant à une séance
    rangée, et c'est `DELETE /api/seances/{id}` qui efface pour de bon.
    Avant, cette route effaçait le dossier de travail — ce qui, depuis
    que les séances survivent, reviendrait à perdre un enregistrement
    en fermant un onglet."""
    with _lock:
        job = _jobs.pop(job_id, None)
    return {"deleted": bool(job)}


# --------------------------------------------------------------- mémoire

@app.get("/api/reglages")
def lire_reglages() -> dict:
    """Les choix de la dernière fois, pour que l'interface s'y remette."""
    return memoire.reglages()


@app.post("/api/reglages")
def ecrire_reglages(payload: dict) -> dict:
    return memoire.retenir(payload or {})


@app.get("/api/seances")
def lister_seances() -> dict:
    return {"seances": memoire.liste(), "place": memoire.place_occupee()}


@app.post("/api/seances/{seance_id}")
def rouvrir_seance(seance_id: str) -> dict:
    """Reprend une séance là où elle avait été laissée.

    Rouvrir ne refait rien : le texte, les noms, la relecture et
    l'enregistrement sont déjà là. C'est ce qui permet de reprendre un
    compte rendu le lendemain sans repayer la transcription."""
    deja = _jobs.get(seance_id)
    if deja:
        return _public(deja)
    job = memoire.charger(seance_id)
    if not job:
        raise HTTPException(404, "Séance introuvable.")
    for voix in job["speakers"]:
        # Les extraits d'écoute vivent dans le dossier de la séance ;
        # proposer un bouton de lecture qui ne joue rien est pire que
        # ne pas le proposer.
        index = voix.get("index")
        voix["has_sample"] = bool(
            index is not None
            and (Path(job["work_dir"]) / f"sample_{index}.mp3").exists())
    with _lock:
        _jobs[seance_id] = job
    return _public(job)


@app.delete("/api/seances/{seance_id}")
def effacer_seance(seance_id: str) -> dict:
    with _lock:
        _jobs.pop(seance_id, None)
    return {"efface": memoire.oublier(seance_id),
            "place": memoire.place_occupee()}


@app.delete("/api/seances/{seance_id}/audio")
def effacer_audio(seance_id: str) -> dict:
    """Jette l'enregistrement et garde le texte.

    Les transcripts ne pèsent rien, les enregistrements pèsent tout :
    on peut faire de la place sans rien perdre de ce qui a été écrit."""
    fait = memoire.liberer_audio(seance_id)
    with _lock:
        job = _jobs.get(seance_id)
        if job:
            job.update(source="", video=False, sans_audio=True)
    return {"libere": fait, "place": memoire.place_occupee()}


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Interface locale de transcription.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7878)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--simulation", action="store_true",
        help="Démarrer comme chez quelqu'un qui n'a rien configuré : "
             "aucune clé connue, le trousseau du système ni lu ni écrit.")
    parser.add_argument(
        "--oublier-simulation", action="store_true",
        help="Effacer les clés saisies pendant une simulation.")
    args = parser.parse_args()

    if args.oublier_simulation:
        config.oublier_simulation()
        print("Simulation remise à zéro.")
    if args.simulation:
        # Posé dans l'environnement du processus, et non dans un drapeau
        # passé de fonction en fonction : config est lu depuis une
        # douzaine d'endroits, dont des fils d'exécution, et un seul
        # oubli rendrait la vraie clé à un écran censé n'en avoir aucune.
        os.environ["TRANSCRIPTEUR_VIERGE"] = "1"

    assets.ensure_models()

    url = f"http://{args.host}:{args.port}"
    print(f"\nTranscripteur prêt : {url}")
    if config.en_simulation():
        print("\n  SIMULATION DE PREMIER DÉMARRAGE")
        print("  Le programme ne connaît aucune clé : c'est ce que voit")
        print("  quelqu'un qui vient de l'installer. Les clés saisies ici")
        print(f"  vont dans un fichier jetable ({config.bac_vierge()}),")
        print("  et le trousseau du système n'est ni lu ni modifié.")
        print("  Pour effacer : --oublier-simulation\n")
    print("Laisse cette fenêtre ouverte. Ferme-la pour arrêter le programme.\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
