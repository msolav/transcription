"""La bibliothèque : conserver et relire, rien d'autre.

Un second programme, bien plus petit que l'application complète, pour
qui transcrit ailleurs — dans un navigateur, sur une autre machine — et
veut garder ses comptes rendus quelque part de durable, avec l'audio
pour les réécouter.

Ce qu'elle fait : la liste des séances, le texte, l'écoute synchronisée,
les exports, l'import d'un `.json` et de son audio. Ce qu'elle ne fait
pas : transcrire, séparer les voix, nettoyer le son, corriger. Elle ne
demande donc aucune clé d'API et ne parle à personne.

Pourquoi un module à part plutôt que des routes de plus dans `server` :
celui-ci importe `pipeline` au premier niveau, qui importe `assets`, et
PyInstaller suit ces chemins même quand le code ne les emprunte jamais.
Le paquet y gagne les quarante mégaoctets de sherpa-onnx et les dix de
numpy, dont la bibliothèque n'a aucun usage. Mesuré : 34 Mo contre 101,
et 17,4 Mo compressés contre 46.

L'audio gardé ici est compressé — un mp3 mono, qui suffit largement à
réécouter. Il ne suffit pas à séparer les voix : mesuré sur la même
conversation, la séparation tombe de 69,3 % à 38,9 % de justesse sur un
mp3 à 64 kbit/s, et les confusions entre genres différents passent de
1,3 % à 45,2 %. Écouter et départager ne demandent pas le même fichier.
"""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from . import memoire

app = FastAPI(title="Transcripteur — bibliothèque")

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Les séances ouvertes, en mémoire vive. Même rôle que dans `server`,
# mais sans travail en cours : ici rien ne se calcule, on ne fait que
# tenir sous la main ce qui vient d'être lu.
_ouvertes: dict[str, dict] = {}
_verrou = threading.Lock()


@app.on_event("startup")
def _preparer() -> None:
    memoire.preparer()


# ------------------------------------------------------------- la page

_GREFFES = ("seances.js", "apercu.js")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """La même page que l'application complète.

    Pas une page à part, et c'est voulu. Une seconde interface qui
    montre les mêmes séances finirait par ne plus leur ressembler : deux
    listes, deux lecteurs, deux façons d'exporter, qui divergent à la
    première correction faite d'un seul côté.

    La page sait se passer de ce qui manque : chacun de ses appels est
    enveloppé d'un `catch`, et `/api/health` lui dit qu'elle est ici
    dans la bibliothèque. Ce qui ne s'y fait pas — déposer un fichier,
    régler la séparation des voix — se replie tout seul."""
    page = STATIC_DIR / "index-vm.html"
    if not page.exists():
        raise HTTPException(500, "Interface absente du paquet.")
    html = page.read_text(encoding="utf-8")
    manquants = "".join(f'<script src="/static/{g}"></script>\n'
                        for g in _GREFFES if f'src="/static/{g}"' not in html)
    if manquants:
        html = (html.replace("</body>", manquants + "</body>")
                if "</body>" in html else html + manquants)
    return HTMLResponse(html)


@app.get("/static/{nom}")
def fichier_statique(nom: str) -> FileResponse:
    # Liste close : un nom libre ici laisserait lire n'importe quel
    # fichier du paquet à qui sait demander.
    if nom not in _GREFFES:
        raise HTTPException(404, "Fichier inconnu.")
    return FileResponse(STATIC_DIR / nom, media_type="application/javascript")


# -------------------------------------------------------- les séances

@app.get("/api/health")
def sante() -> dict:
    """Le même nom que dans l'application complète, parce que c'est la
    même page qui demande.

    `bibliotheque` vaut vrai, et c'est à cela qu'elle reconnaît où elle
    se trouve. Les clés sont annoncées absentes : il n'y en a pas ici,
    et rien n'en demande."""
    from . import __version__
    return {"bibliotheque": True, "version": __version__,
            "has_key": False, "key_from_env": False, "vierge": False,
            "cles": {}, "relecture": "", "models_ready": True,
            "code_perime": False,
            "place": memoire.place_occupee()}


@app.get("/api/models")
def modeles_de_voix(langue: str = "") -> dict:
    """Le catalogue des modèles de voix.

    La bibliothèque ne sépare aucune voix. Mais c'est la page de
    l'application qu'elle sert, et cette page remplit ses listes au
    démarrage : sans cette réponse, l'appel échouait en 404 et le rendu
    d'une séance s'arrêtait là — on cliquait « Rouvrir » et rien ne
    s'ouvrait. `assets` n'entraîne rien de lourd, vérifié."""
    from . import assets
    return {"modeles": assets.inventaire(langue or None),
            "defaut": assets.DEFAULT_EMBEDDING,
            "nettoyeurs": assets.inventaire_debruiteurs(),
            "nettoyeur_defaut": assets.DEBRUITEUR_DEFAUT}


@app.get("/api/reglages")
def lire_reglages() -> dict:
    """Les réglages d'affichage. La page les lit au démarrage.

    Ceux du traitement n'ont pas de sens ici — rien ne se traite — mais
    les rendre tels quels coûte moins qu'un second chemin, et la base
    est partagée avec l'application complète quand les deux sont
    installées côte à côte."""
    return memoire.reglages()


@app.post("/api/reglages")
def ecrire_reglages(payload: dict) -> dict:
    return memoire.retenir(payload or {})


@app.get("/api/seances")
def lister() -> dict:
    return {"seances": memoire.liste(), "place": memoire.place_occupee()}


@app.post("/api/seances/{seance_id}")
def ouvrir(seance_id: str) -> dict:
    with _verrou:
        deja = _ouvertes.get(seance_id)
    if deja:
        return deja
    job = memoire.charger(seance_id)
    if not job:
        raise HTTPException(404, "Séance introuvable.")
    for voix in job.get("speakers") or []:
        index = voix.get("index")
        voix["has_sample"] = bool(
            index is not None
            and (Path(job["work_dir"]) / f"sample_{index}.mp3").exists())
    with _verrou:
        _ouvertes[seance_id] = job
    return job


@app.delete("/api/seances/{seance_id}")
def effacer(seance_id: str) -> dict:
    with _verrou:
        _ouvertes.pop(seance_id, None)
    return {"efface": memoire.oublier(seance_id),
            "place": memoire.place_occupee()}


@app.delete("/api/seances")
def tout_effacer(audio_seulement: int = 0) -> dict:
    """Vide la bibliotheque, ou seulement ses enregistrements.

    `audio_seulement=1` garde tous les textes et ne jette que le son :
    c'est la purge presque sans regret, puisque les transcripts ne
    pesent rien et que l'audio est tout le poids. Sans ce parametre,
    tout part — et rien ne revient."""
    with _verrou:
        _ouvertes.clear()
    bilan = (memoire.liberer_tous_audios() if audio_seulement
             else memoire.tout_oublier())
    return {**bilan, "place": memoire.place_occupee()}


@app.delete("/api/seances/{seance_id}/audio")
def effacer_audio(seance_id: str) -> dict:
    """Jette l'enregistrement, garde le texte."""
    fait = memoire.liberer_audio(seance_id)
    with _verrou:
        job = _ouvertes.get(seance_id)
        if job:
            job.update(source="", video=False, sans_audio=True)
    return {"libere": fait, "place": memoire.place_occupee()}


# ----------------------------------------------------------- l'écoute

@app.get("/api/jobs/{seance_id}/media")
def media_comme_lapplication(seance_id: str) -> FileResponse:
    """Le même chemin que dans l'application complète.

    C'est la même page qui demande, et elle ne doit pas avoir à savoir
    lequel des deux programmes la sert. Un second chemin pour le même
    fichier, c'est un endroit de plus où les deux peuvent diverger."""
    return media(seance_id)


@app.get("/media/{seance_id}")
def media(seance_id: str) -> FileResponse:
    """L'enregistrement d'une séance, pour le lecteur de la page."""
    job = memoire.charger(seance_id)
    if not job:
        raise HTTPException(404, "Séance introuvable.")
    chemin = str(job.get("source") or "")
    # Path("") rend PosixPath('.'), qui existe : sans ce test, une
    # séance sans audio répondait 500 au lieu de 404.
    if not chemin:
        raise HTTPException(404, "Pas d'enregistrement pour cette séance.")
    f = Path(chemin)
    if not f.is_file():
        raise HTTPException(404, "Enregistrement introuvable.")
    return FileResponse(f)


@app.get("/sample/{seance_id}/{index}")
def extrait(seance_id: str, index: int) -> FileResponse:
    """Un extrait d'écoute d'une voix, s'il a été gardé."""
    job = memoire.charger(seance_id)
    if not job:
        raise HTTPException(404, "Séance introuvable.")
    f = Path(job["work_dir"]) / f"sample_{index}.mp3"
    if not f.is_file():
        raise HTTPException(404, "Extrait introuvable.")
    return FileResponse(f, media_type="audio/mpeg")


# ----------------------------------------------------------- l'import

@app.post("/api/jobs/import")
async def importer_comme_lapplication(file: UploadFile = File(...),
                                      audio: UploadFile | None = File(None)) -> dict:
    """Le même chemin et le même nom de champ que l'application.

    La page poste déjà là pour rouvrir un .json ; lui demander un autre
    chemin selon le programme qui la sert serait une divergence de plus.
    `audio` en supplément, que l'application complète ignore et dont la
    bibliothèque a besoin — sans l'enregistrement, la séance importée ne
    se réécoute pas."""
    return await importer(file, audio)


@app.post("/api/import")
async def importer(transcript: UploadFile = File(...),
                   audio: UploadFile | None = File(None)) -> dict:
    """Range un `.json` exporté, et son audio s'il vient avec.

    C'est la porte d'entrée de ce programme : tout ce qu'il contient est
    venu d'ailleurs. Le format est celui que l'application exporte, et
    les mêmes contrôles s'appliquent — un fichier sans blocs n'est pas
    un transcript."""
    try:
        donnees = json.loads((await transcript.read()).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, "Fichier illisible : attendu un export .json.") from exc

    blocs = donnees.get("blocks")
    if not isinstance(blocs, list) or not blocs:
        raise HTTPException(400, "Ce fichier ne contient pas de transcript.")
    manquant = [c for c in ("speaker", "text", "start") if c not in (blocs[0] or {})]
    if manquant:
        raise HTTPException(400, "Transcript incomplet : il manque "
                                 + ", ".join(manquant) + ".")

    import uuid
    seance_id = donnees.get("id") or uuid.uuid4().hex[:12]
    dossier = memoire.seances_dir() / seance_id
    dossier.mkdir(parents=True, exist_ok=True)

    source = ""
    if audio is not None and audio.filename:
        # On garde l'extension d'origine : le navigateur choisit son
        # décodeur d'après elle, et un mp3 nommé .bin ne se lit pas.
        suffixe = Path(audio.filename).suffix or ".mp3"
        cible = dossier / f"source{suffixe}"
        with cible.open("wb") as sortie:
            shutil.copyfileobj(audio.file, sortie)
        source = str(cible)

    job = {
        "id": seance_id,
        "filename": donnees.get("filename") or transcript.filename or "transcript.json",
        "source": source,
        "work_dir": str(dossier),
        "status": "done",
        "duration": float(donnees.get("duration")
                          or (blocs[-1].get("end") or 0.0)),
        "speakers": donnees.get("speakers") or [],
        "blocks": blocs,
        "names": donnees.get("names") or {},
        # None et non {} : un objet vide est « vrai » en JavaScript, et
        # la page proposait alors « Version relue » pour une relecture
        # qui n'existe pas.
        "relecture": donnees.get("relecture") or None,
        "video": bool(donnees.get("video")),
        "sans_audio": not source,
    }
    memoire.enregistrer(job)
    return {"id": seance_id, "place": memoire.place_occupee()}


# ------------------------------------------------------- le démarrage

def main() -> None:
    """Sert la bibliothèque, et l'ouvre dans une fenêtre ou un onglet.

    Le même mécanisme que l'application complète, et pour les mêmes
    raisons : l'interface graphique doit vivre sur le fil principal."""
    # `ouvrir` et non `lancer_fenetre` : c'est le nom qu'elle porte dans
    # fenetre.py. Et `servir` n'est pas repris — il monte l'application
    # complète, donc tout ce que l'on vient d'exclure.
    from .fenetre import attendre, ouvrir as ouvrir_fenetre, port_libre
    import os
    import sys
    import webbrowser

    impose = os.environ.get("TRANSCRIPTEUR_PORT", "").strip()
    port = int(impose) if impose.isdigit() else port_libre()
    url = f"http://127.0.0.1:{port}/"

    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port,
                            log_level="warning")
    serveur = uvicorn.Server(config)
    threading.Thread(target=serveur.run, daemon=True).start()

    if not attendre(port):
        print("Le serveur n'a pas démarré.")
        sys.exit(1)
    if os.environ.get("TRANSCRIPTEUR_SANS_FENETRE", "").strip() not in ("", "0"):
        print(f"Bibliothèque sur {url} (sans fenêtre).")
        while True:
            threading.Event().wait(3600)
    if not ouvrir_fenetre(url):
        webbrowser.open(url)


if __name__ == "__main__":
    main()
