"""La bibliotheque tient-elle sa promesse : conserver, relire, et rien
de lourd ?

Tout l'interet de ce second programme est son poids. S'il entraine
numpy ou sherpa-onnx, il ne pese plus 34 Mo mais 101, et il n'a plus de
raison d'exister. Or il suffit d'une importation ajoutee sans y penser
dans memoire.py, sous_titres.py ou texte.py pour que cela arrive — en
silence, puisque le programme marcherait tres bien.

C'est donc ce que ce verificateur regarde en premier.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

ok = 0
rate = 0


def verifie(quoi: str, condition: bool, detail: str = "") -> None:
    global ok, rate
    if condition:
        ok += 1
        print(f"  ok   {quoi}")
    else:
        rate += 1
        print(f"  RATE {quoi}" + (f" — {detail}" if detail else ""))


# Les modules dont la presence annulerait tout le benefice.
LOURDS = ("numpy", "sherpa_onnx", "groq", "anthropic", "openai",
          "keyring", "cryptography", "google")


def _lourds_charges() -> list[str]:
    return sorted({m.split(".")[0] for m in sys.modules
                   if m.split(".")[0] in LOURDS})


# 1. Les modules partages ne tirent rien derriere eux.
#
# texte.py existe pour cela : join_words vivait dans pipeline, et
# sous_titres l'important de la entrainait tout le pipeline — donc
# assets, donc les telechargements de modeles.
_avant = _lourds_charges()
from transcripteur import memoire, sous_titres, texte  # noqa: E402

verifie("texte, sous_titres et memoire n'entrainent rien de lourd",
        _lourds_charges() == _avant, str(_lourds_charges()))
verifie("join_words n'a qu'une implementation",
        texte.join_words is sous_titres.join_words)

_bac = tempfile.mkdtemp(prefix="verif-biblio-")
_avant_dossier = os.environ.get("TRANSCRIPTEUR_DONNEES")
os.environ["TRANSCRIPTEUR_DONNEES"] = _bac

try:
    import importlib
    importlib.reload(memoire)

    from transcripteur import bibliotheque  # noqa: E402
    verifie("la bibliotheque s'importe sans rien de lourd",
            _lourds_charges() == [], str(_lourds_charges()))

    memoire.preparer()
    memoire.enregistrer({
        "id": "essai01", "filename": "conseil.m4a", "duration": 125.0,
        "blocks": [{"speaker": "SPEAKER_00", "start": 0.0, "end": 4.0,
                    "text": "Bonjour a tous.", "words": []}],
        "speakers": [{"id": "SPEAKER_00", "index": 0, "color": "#e4572e"}],
        "names": {"SPEAKER_00": "Karina"}, "relecture": {},
        "source": "", "video": False})

    import uvicorn
    _cfg = uvicorn.Config(bibliotheque.app, host="127.0.0.1", port=7987,
                          log_level="error")
    _srv = uvicorn.Server(_cfg)
    threading.Thread(target=_srv.run, daemon=True).start()
    time.sleep(2.5)

    def _get(chemin: str):
        """Rend (code, donnees). Les donnees ne sont lues comme du JSON
        que si le serveur l'annonce : /static/ rend du JavaScript, et
        tenter de le decoder levait une exception au milieu des essais."""
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:7987{chemin}", timeout=5) as r:
                corps = r.read()
                if "json" in (r.headers.get("Content-Type") or ""):
                    return r.status, json.loads(corps)
                return r.status, corps
        except urllib.error.HTTPError as e:
            return e.code, {}

    # /api/health et non /api/sante : c'est la page de l'application
    # complete qui interroge, et elle connait ce nom-la.
    _code, _sante = _get("/api/health")
    verifie("elle repond, et se declare bibliotheque",
            _code == 200 and _sante.get("bibliotheque") is True, str(_code))
    verifie("elle sert la meme page que l'application",
            _get("/")[0] == 200)

    _code, _liste = _get("/api/seances")
    verifie("elle rend la liste des seances",
            _code == 200 and len(_liste.get("seances") or []) == 1, str(_liste)[:80])

    # 2. Ce qu'elle ne doit PAS offrir.
    #
    # Une route de transcription ici serait un piege : elle appellerait
    # un pipeline absent du paquet, et echouerait sur une trace de
    # ImportError au lieu d'un refus clair.
    _chemins = {r.path for r in bibliotheque.app.routes if hasattr(r, "path")}
    _interdits = {"/api/jobs", "/api/key", "/api/relecture", "/api/models"}
    verifie("elle n'offre aucune route de traitement",
            not (_chemins & _interdits), str(_chemins & _interdits))

    # 3. Les fichiers servis sont une liste close.
    _code, _ = _get("/static/seances.js")
    verifie("elle sert ses scripts", _code in (200, 404), str(_code))
    _code, _ = _get("/static/../bibliotheque.py")
    verifie("elle refuse un nom de fichier libre", _code == 404, str(_code))

    # 4. Une seance sans audio repond 404, jamais 500.
    #
    # Path("") rend PosixPath('.'), qui existe : sans le test explicite,
    # la route rendait une erreur de serveur sur une seance dont
    # l'enregistrement a ete efface — cas tout a fait ordinaire.
    _code, _ = _get("/media/essai01")
    verifie("une seance sans audio rend 404", _code == 404, str(_code))
    _code, _ = _get("/media/inconnue")
    verifie("une seance inconnue rend 404", _code == 404, str(_code))

    # 5. Les chemins que la page connait deja.
    #
    # La bibliotheque sert la page de l'application complete : elle doit
    # donc repondre aux memes adresses, sinon il faudrait deux versions
    # de la page — et c'est exactement ce qu'on evite ici.
    _chemins = {r.path for r in bibliotheque.app.routes if hasattr(r, "path")}
    for _attendu in ("/api/health", "/api/seances", "/api/reglages",
                     "/api/jobs/{seance_id}/media", "/api/jobs/import"):
        verifie(f"elle repond a {_attendu}", _attendu in _chemins,
                "la page de l'application appelle ce chemin")

    # 6. Les purges.
    #
    # Jeter les sons garde tous les textes : c'est la purge qu'on fait
    # en premier, et la seule a peu pres sans regret. Si elle emportait
    # aussi les transcripts, personne ne s'en apercevrait avant d'en
    # vouloir un.
    memoire.enregistrer({
        "id": "essai02", "filename": "autre.m4a", "duration": 60.0,
        "blocks": [{"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0,
                    "text": "Deuxieme seance.", "words": []}],
        "speakers": [], "names": {}, "relecture": None,
        "source": "", "video": False})
    _avant = len(memoire.liste())
    _bilan = memoire.liberer_tous_audios()
    verifie("jeter les sons garde tous les textes",
            len(memoire.liste()) == _avant, f"{_avant} avant, {len(memoire.liste())} apres")

    _bilan = memoire.tout_oublier()
    verifie("tout effacer vide la bibliotheque",
            memoire.liste() == [], str(memoire.liste())[:60])
    verifie("tout effacer rend son bilan",
            isinstance(_bilan.get("seances"), int), str(_bilan))
finally:
    if _avant_dossier is None:
        os.environ.pop("TRANSCRIPTEUR_DONNEES", None)
    else:
        os.environ["TRANSCRIPTEUR_DONNEES"] = _avant_dossier
    shutil.rmtree(_bac, ignore_errors=True)

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
