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

from starlette.concurrency import run_in_threadpool
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               Response)

from . import (assets, config, fournisseurs, guide, journal, memoire,
               routes_relecture,
               pipeline, sous_titres)
from .pipeline import Cancelled, Options, PipelineError

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 Go

app = FastAPI(title="Transcripteur", docs_url=None, redoc_url=None)


def _espace_libre(dossier: Path) -> int | None:
    """Octets libres sur le volume qui porte `dossier`, ou None si inconnu."""
    try:
        p = dossier
        while not p.exists() and p != p.parent:
            p = p.parent
        return shutil.disk_usage(p).free
    except Exception:  # noqa: BLE001
        return None


def _message_disque(exc: BaseException) -> str:
    import errno
    if getattr(exc, "errno", None) == errno.ENOSPC:
        return ("Le disque est plein. Libérer de la place (par exemple avec "
                "« Jeter les sons » sur d'anciennes séances), puis réessayer.")
    return f"Écriture impossible sur le disque : {exc}"


@app.exception_handler(Exception)
async def _erreur_inattendue(request, exc: Exception) -> JSONResponse:
    """Toute erreur non prévue : écrite dans le journal, dite en clair.

    Sans cela l'interface n'affichait que « Erreur 500 », sans la raison —
    et sans aucune trace ailleurs, puisque l'application installée n'a
    pas de terminal."""
    journal.erreur(f"{request.method} {request.url.path}", exc)
    message = _message_disque(exc) if isinstance(exc, OSError) else f"Erreur inattendue : {exc}"
    return JSONResponse({"detail": message}, status_code=500)

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
        "raffinage": job.get("raffinage"),
        "enrolement_pret": bool(job.get("work_dir") and (Path(job["work_dir"]) / "enrolement.npz").exists()),
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
        # Le coût de chaque étape, en multiple de la durée de
        # l'enregistrement. L'interface s'en sert pour annoncer le temps
        # AVANT de lancer, et ce que coûte chaque option : « séparer les
        # voix, +46 min » se décide bien mieux avant deux heures
        # d'attente qu'après. Une seule source, celle qui découpe aussi
        # la barre de progression.
        "couts": pipeline.COUT,
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
def version(force: bool = False) -> dict:
    """La version installée, et celle qui est publiée.

    Aucun identifiant n'est envoyé : la requête ne dit rien de plus que
    « quelqu'un a lancé le programme ». En cas d'échec — pas de réseau,
    site injoignable — on rend simplement « à jour » et l'interface se
    tait, plutôt que d'inquiéter avec une panne qui n'en est pas une."""
    from . import __version__ as installee
    if force:                   # menu « Rechercher une mise à jour », revérification périodique
        _VERSION_VUE.clear()
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


# ------------------------------------------------ mise à jour assistée
#
# Pas de remplacement automatique : les paquets ne sont pas signés, et un
# programme qui s'écrase lui-même déclencherait les alertes du système.
# On télécharge la bonne version, on la range dans Téléchargements, on la
# montre : il reste à l'ouvrir.

_MAJ: dict = {"etat": "repos", "octets": 0, "total": 0, "nom": "", "erreur": ""}


def _plateforme() -> str:
    import platform
    import sys
    if sys.platform == "darwin":
        return "mac-silicon" if platform.machine() == "arm64" else "mac-intel"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _telecharger_maj() -> None:
    import urllib.request
    try:
        url = f"{SITE}/telecharger/{_plateforme()}"
        requete = urllib.request.Request(
            url, headers={"User-Agent": "Transcripteur"})
        with urllib.request.urlopen(requete, timeout=30) as r:
            nom = Path(url).name
            cd = r.headers.get("content-disposition", "")
            m = re.search(r'filename="?([^";]+)"?', cd)
            if m:
                nom = Path(m.group(1)).name
            _MAJ.update(total=int(r.headers.get("content-length") or 0), nom=nom)
            dossier = Path.home() / "Downloads"
            if not dossier.is_dir():
                dossier = Path.home()
            cible = dossier / nom
            n = 1
            while cible.exists():
                cible = dossier / f"{Path(nom).stem} ({n}){''.join(Path(nom).suffixes)}"
                n += 1
            partiel = cible.with_name(cible.name + ".part")
            with open(partiel, "wb") as out:
                while True:
                    bloc = r.read(1024 * 256)
                    if not bloc:
                        break
                    out.write(bloc)
                    _MAJ["octets"] += len(bloc)
            partiel.rename(cible)
        _MAJ.update(etat="fini", nom=cible.name)
        try:
            import subprocess
            import sys
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(cible)])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", str(cible)])
            else:
                subprocess.Popen(["xdg-open", str(dossier)])
        except Exception:  # noqa: BLE001
            pass
    except Exception as exc:  # noqa: BLE001
        _MAJ.update(etat="erreur", erreur=str(exc))


@app.post("/api/mise-a-jour")
def lancer_maj() -> dict:
    if _MAJ["etat"] != "cours":
        _MAJ.update(etat="cours", octets=0, total=0, nom="", erreur="")
        threading.Thread(target=_telecharger_maj, daemon=True).start()
    return dict(_MAJ)


@app.get("/api/mise-a-jour")
def etat_maj() -> dict:
    return dict(_MAJ)


@app.post("/api/enregistrer")
def enregistrer_fichier(payload: dict) -> dict:
    """Écrit un export dans le dossier Téléchargements, puis le montre.

    La fenêtre de l'application (WebKit intégré) ignore l'attribut
    `download` d'un lien interne : au lieu d'enregistrer, elle navigue
    vers le texte et remplace toute l'interface. Le programme écrit donc
    le fichier lui-même, sans passer par la fenêtre."""
    nom = Path(str(payload.get("nom") or "transcription.txt")).name
    nom = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", nom).strip(". ") or "transcription.txt"
    texte = payload.get("texte")
    if not isinstance(texte, str):
        raise HTTPException(400, "Rien à enregistrer.")
    dossier = Path.home() / "Downloads"
    if not dossier.is_dir():
        dossier = Path.home()
    cible = dossier / nom
    n = 1
    while cible.exists():
        cible = dossier / f"{Path(nom).stem} ({n}){Path(nom).suffix}"
        n += 1
    cible.write_text(texte, encoding="utf-8")
    try:
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(cible)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", str(cible)])
        else:
            subprocess.Popen(["xdg-open", str(dossier)])
    except Exception:  # noqa: BLE001
        pass
    return {"nom": cible.name, "dossier": dossier.name}


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


# ---------------------------------------- corriger et résumer

class _DepotServeur:
    """Ce que les routes partagées ont besoin de savoir d'ici.

    Elles vivent dans routes_relecture parce que la bibliothèque les
    sert aussi : on corrige et on résume aussi bien juste après une
    transcription que des mois plus tard en rouvrant une séance. Deux
    copies auraient fini par ne plus se ressembler."""

    verrou = _lock

    def lire(self, job_id: str):
        return _jobs.get(job_id)

    def retenir(self, job_id: str) -> None:
        _retenir(job_id)


routes_relecture.brancher(app, _DepotServeur())


@app.get("/api/models")
def list_models(langue: str = "") -> dict:
    """Le catalogue des modèles de voix, le plus adapté à la langue en tête.

    L'ordre suit d'abord la langue d'entraînement, puis la justesse
    mesurée — c'est un classement de précision depuis qu'il en existe
    une mesure, et le coût de calcul ne sert plus qu'à départager.
    Voir outils/mesure_attribution.py."""
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
    raffiner: str = Form(""),
) -> JSONResponse:
    def as_int(value: str) -> int | None:
        value = (value or "").strip()
        return int(value) if value.isdigit() and int(value) > 0 else None

    if not config.get_key("groq"):
        raise HTTPException(400, "Aucune clé Groq enregistrée.")
    # La clé est éprouvée avant tout travail : sinon un refus de Groq ne se
    # découvre qu'à l'étape de transcription, après des heures de calcul.
    try:
        _verdict = await run_in_threadpool(
            config.check_key, config.get_key("groq"), "groq")
    except Exception:  # noqa: BLE001
        _verdict = None
    if _verdict:
        raise HTTPException(400, _verdict if isinstance(_verdict, str) else str(_verdict))

    job_id = uuid.uuid4().hex[:12]
    # Dans le dossier de données et non dans un dossier temporaire. Le
    # système efface le second quand il veut — l'aperçu vidéo et la
    # séparation des voix après coup ne survivaient donc pas à un
    # redémarrage — et ne l'efface jamais complètement, de sorte que les
    # fichiers s'accumulaient hors de vue. Ici on sait ce qu'ils pèsent
    # et on peut les jeter.
    work_dir = memoire.seances_dir() / job_id
    # L'espace est vérifié avant d'écrire quoi que ce soit : un disque plein
    # se manifestait par un envoi qui s'arrête à moitié, puis « Erreur 500 ».
    # Le besoin est estimé : la copie, l'audio converti (≈ 4 fois le fichier
    # compressé) et les tranches envoyées à Groq.
    taille = getattr(file, "size", None)
    if taille:
        besoin = int(taille * 6) + 300 * 1024 * 1024
        libre = _espace_libre(work_dir.parent)
        if libre is not None and libre < besoin:
            raise HTTPException(
                507, f"Espace disque insuffisant : {libre / 1e9:.1f} Go libres, "
                     f"environ {besoin / 1e9:.1f} Go nécessaires. Libérer de la "
                     f"place, ou utiliser « Jeter les sons » sur d'anciennes séances.")
    work_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "audio").suffix or ".bin"
    source = work_dir / f"source{suffix}"

    written = 0
    try:
        with open(source, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    out.close()
                    shutil.rmtree(work_dir, ignore_errors=True)
                    raise HTTPException(413, "Fichier trop volumineux (limite : 2 Go).")
                out.write(chunk)
    except OSError as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        journal.erreur("envoi du fichier", exc)
        raise HTTPException(507, _message_disque(exc)) from exc

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
        raffiner=raffiner == "1",
        api_key=config.get_key("groq"),
    )

    # Les réglages sont retenus par l'interface, qui les lit sur les
    # vraies commandes, et non ici où ils arrivent déjà décomposés. Le
    # serveur se contente de les ranger et de les rendre.
    threading.Thread(target=_run_job, args=(job_id, options), daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


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
        # Le journal de la transcription n'a rien à faire ici : on repart d'une page blanche.
        with _lock:
            current = _jobs.get(job_id)
            if current is not None:
                current["notes"] = []
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
    raffiner: str = Form(""),
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
        raffiner=raffiner == "1",
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


def _run_guide(job_id: str, options: Options, noms: dict, exemples: list,
               duree: float) -> None:
    """Raffine d'après les noms et les exemples, dans un fil à part.

    Même principe que `_run_voix` : le travail se fait sur la tâche elle-même,
    les blocs d'origine servent de filet, et rien n'est écrit tant que le
    calcul n'a pas abouti. Les empreintes sont gardées dans la séance :
    relancer après avoir ajouté un exemple prend quelques secondes."""
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

        anciens = job["blocks"]
        avant = (job.get("raffinage") or {}).get("part_incertaine")
        _set(job_id, status="running", stage="Raffinage des voix",
             progress=0.0, error=None, cancel=False)
        with _lock:
            current = _jobs.get(job_id)
            if current is not None:
                current["notes"] = []
        try:
            resultat, noms_finaux, rapport = pipeline.raffiner_selon_noms(
                src, work_dir, options, anciens, noms, exemples, duree,
                progress, notify, stop)
        except Cancelled:
            _set(job_id, status="done", stage="Raffinage annulé",
                 progress=1.0, blocks=anciens)
            return
        except (PipelineError, ValueError) as exc:
            _set(job_id, status="done", stage="Raffinage abandonné",
                 progress=1.0, blocks=anciens, error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            journal.erreur("raffinage guidé", exc)
            _set(job_id, status="done", stage="Raffinage abandonné",
                 progress=1.0, blocks=anciens,
                 error=f"Erreur inattendue : {exc}")
            return

        rapport["part_avant"] = avant
        _set(job_id, status="done", stage="Terminé", progress=1.0,
             duration=resultat.duration, speakers=resultat.speakers,
             blocks=resultat.blocks, names=noms_finaux, raffinage=rapport,
             sans_audio=False, relecture=None)
        _retenir(job_id)


@app.post("/api/jobs/{job_id}/raffiner-noms")
async def raffiner_noms(job_id: str, payload: dict) -> JSONResponse:
    """Raffine la séparation des voix d'après les noms et des exemples désignés.

    `payload` : {"noms": {id_de_voix: nom}, "exemples": [{"start", "end",
    "nom"}], "langue": ""}. Rien n'est renvoyé à Groq : seul le son est lu."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    if job["status"] not in ("done", "error"):
        raise HTTPException(400, "Un traitement est déjà en cours.")
    ancien = Path(job["source"]) if job.get("source") else None
    if not (ancien and ancien.exists()):
        raise HTTPException(
            400, "L'enregistrement n'est plus sur cette machine. Il faut le "
                 "fournir de nouveau (« Raffiner les voix », puis choisir le fichier).")
    if not pipeline.mots_des_blocs(job["blocks"]):
        raise HTTPException(400, "Ce transcript ne porte pas les horodatages des mots.")
    noms = {str(k): str(v) for k, v in (payload.get("noms") or {}).items()}
    exemples = []
    for e in payload.get("exemples") or []:
        try:
            exemples.append({"start": float(e["start"]), "end": float(e["end"]),
                             "nom": str(e.get("nom") or "")})
        except (KeyError, TypeError, ValueError):
            continue
    if len({n.strip() for n in noms.values() if n.strip()}
           | {e["nom"].strip() for e in exemples if e["nom"].strip()}) < 2:
        raise HTTPException(400, "Il faut nommer au moins deux personnes pour raffiner.")
    options = Options(language=(payload.get("langue") or "").strip() or None,
                      diarize=True, embedding="auto", denoise="",
                      api_key=config.get_key("groq"), raffiner=True)
    threading.Thread(target=_run_guide,
                     args=(job_id, options, noms, exemples, float(job["duration"] or 0.0)),
                     daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


def _contexte_enrolement(job_id: str, exiger_pret: bool = False):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Traitement introuvable.")
    if job["status"] not in ("done", "error"):
        raise HTTPException(400, "Un traitement est déjà en cours.")
    src = Path(job["source"]) if job.get("source") else None
    if not (src and src.exists()):
        raise HTTPException(
            400, "L'enregistrement n'est plus sur cette machine. Il faut le fournir "
                 "de nouveau pour identifier les voix.")
    if not pipeline.mots_des_blocs(job["blocks"]):
        raise HTTPException(400, "Ce transcript ne porte pas les horodatages des mots.")
    work_dir = Path(job["work_dir"])
    if exiger_pret and not (work_dir / "enrolement.npz").exists():
        raise HTTPException(400, "Les empreintes ne sont pas encore calculées.")
    return job, src, work_dir


def _exemples(payload: dict) -> list:
    sortie = []
    for e in payload.get("exemples") or []:
        try:
            sortie.append({"start": float(e["start"]), "end": float(e["end"]),
                           "nom": str(e.get("nom") or "").strip()})
        except (KeyError, TypeError, ValueError):
            continue
    return sortie


def _notifier(job_id: str):
    def notify(message: str) -> None:
        with _lock:
            current = _jobs.get(job_id)
            if current is not None:
                current["notes"].append(message)
                del current["notes"][:-60]
    return notify


def _run_enrol_prep(job_id: str, options: Options, duree: float) -> None:
    with _gate:
        job = _jobs.get(job_id)
        if job is None:
            return
        src, work_dir = Path(job["source"]), Path(job["work_dir"])
        anciens = job["blocks"]
        _set(job_id, status="running", stage="Empreintes des voix", progress=0.0,
             error=None, cancel=False)
        with _lock:
            job["notes"] = []

        def stop() -> bool:
            current = _jobs.get(job_id)
            return current is None or current.get("cancel", False)
        try:
            pipeline.preparer_enrolement(
                src, work_dir, options, anciens, duree,
                lambda stage, ratio: _set(job_id, stage=stage, progress=ratio),
                _notifier(job_id), stop)
        except Cancelled:
            _set(job_id, status="done", stage="Préparation annulée", progress=1.0)
            return
        except (PipelineError, ValueError) as exc:
            _set(job_id, status="done", stage="Préparation abandonnée", progress=1.0, error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            journal.erreur("préparation de l'identification des voix", exc)
            _set(job_id, status="done", stage="Préparation abandonnée", progress=1.0,
                 error=f"Erreur inattendue : {exc}")
            return
        _set(job_id, status="done", stage="Empreintes prêtes", progress=1.0, enrolement_pret=True)


def _run_enrol_fin(job_id: str, options: Options, exemples: list) -> None:
    with _gate:
        job = _jobs.get(job_id)
        if job is None:
            return
        src, work_dir = Path(job["source"]), Path(job["work_dir"])
        anciens = job["blocks"]
        _set(job_id, status="running", stage="Attribution des voix", progress=0.0,
             error=None, cancel=False)
        with _lock:
            job["notes"] = []

        def stop() -> bool:
            current = _jobs.get(job_id)
            return current is None or current.get("cancel", False)
        try:
            resultat, noms = pipeline.terminer_enrolement(
                src, work_dir, options, anciens, exemples,
                lambda stage, ratio: _set(job_id, stage=stage, progress=ratio),
                _notifier(job_id), stop)
        except Cancelled:
            _set(job_id, status="done", stage="Attribution annulée", progress=1.0, blocks=anciens)
            return
        except (PipelineError, ValueError) as exc:
            _set(job_id, status="done", stage="Attribution abandonnée", progress=1.0,
                 blocks=anciens, error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            journal.erreur("attribution des voix", exc)
            _set(job_id, status="done", stage="Attribution abandonnée", progress=1.0,
                 blocks=anciens, error=f"Erreur inattendue : {exc}")
            return
        _set(job_id, status="done", stage="Terminé", progress=1.0,
             duration=resultat.duration, speakers=resultat.speakers,
             blocks=resultat.blocks, names=noms, sans_audio=False, relecture=None)
        _retenir(job_id)


def _options_enrol(payload: dict) -> Options:
    return Options(language=(payload.get("langue") or "").strip() or None, diarize=True,
                   embedding="auto", denoise="", api_key=config.get_key("groq"), raffiner=True)


@app.post("/api/jobs/{job_id}/enrolement/preparer")
async def enrolement_preparer(job_id: str, payload: dict | None = None) -> JSONResponse:
    """Calcule l'empreinte de chaque passage de parole (quelques minutes)."""
    job, src, work_dir = _contexte_enrolement(job_id)
    threading.Thread(target=_run_enrol_prep,
                     args=(job_id, _options_enrol(payload or {}), float(job["duration"] or 0.0)),
                     daemon=True).start()
    return JSONResponse({"id": job_id}, status_code=202)


@app.post("/api/jobs/{job_id}/enrolement/classer")
async def enrolement_classer(job_id: str, payload: dict) -> dict:
    """Où en est-on d'après les exemples, et quels passages montrer ensuite."""
    from . import enrolement
    job, src, work_dir = _contexte_enrolement(job_id, exiger_pret=True)
    wav = work_dir / "audio16k.wav"
    try:
        return await run_in_threadpool(enrolement.classer, work_dir, _exemples(payload),
                                       wav if wav.exists() else None,
                                       payload.get("vus") or [], payload.get("cible") or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/jobs/{job_id}/enrolement/terminer")
async def enrolement_terminer(job_id: str, payload: dict) -> JSONResponse:
    """Attribue chaque mot d'après les exemples, et remplace le texte à une voix."""
    job, src, work_dir = _contexte_enrolement(job_id, exiger_pret=True)
    exemples = _exemples(payload)
    if len({e["nom"] for e in exemples if e["nom"]}) < 2:
        raise HTTPException(400, "Il faut au moins deux personnes avec des exemples.")
    threading.Thread(target=_run_enrol_fin, args=(job_id, _options_enrol(payload), exemples),
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


@app.delete("/api/seances")
def tout_effacer(audio_seulement: int = 0) -> dict:
    """Vide la bibliotheque, ou seulement ses enregistrements.

    `audio_seulement=1` garde tous les textes et ne jette que le son :
    c'est la purge presque sans regret, puisque les transcripts ne
    pesent rien et que l'audio est tout le poids. Sans ce parametre,
    tout part — et rien ne revient."""
    with _lock:
        _jobs.clear()
    bilan = (memoire.liberer_tous_audios() if audio_seulement
             else memoire.tout_oublier())
    return {**bilan, "place": memoire.place_occupee()}


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
