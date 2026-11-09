#!/usr/bin/env python3
"""Le paquet de la bibliothèque démarre-t-il, et pèse-t-il ce qu'il doit ?

Une construction qui réussit ne prouve rien : les pannes d'empaquetage
— un fichier oublié, un module exclu à tort — n'apparaissent qu'au
démarrage, chez celui qui vient d'installer.

Deux choses à vérifier, et la seconde est la raison d'être de ce
programme. Qu'il démarre et serve. Et qu'il soit resté **petit** : si
une importation ajoutée sans y penser ramène sherpa-onnx, il passe de
34 Mo à 101 et n'a plus de raison d'exister. Cela arriverait en
silence, puisque le programme marcherait très bien.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PORT = 7993
BASE = f"http://127.0.0.1:{PORT}"

# Au-delà, c'est qu'un module lourd est revenu.
#
# Un plafond par système, et non un seul : les trois ne pèsent pas la
# même chose pour le même code. Mesuré — 33 Mo sur macOS, 68 sur Linux,
# qui embarque davantage de bibliothèques système. Un plafond unique
# calibré sur macOS faisait échouer Linux sur un paquet parfaitement
# sain, et c'est exactement l'erreur déjà commise sur le contrôle de
# taille de l'application complète.
#
# Ce plafond n'est qu'un second filet : le vrai contrôle est la liste
# des modules interdits ci-dessous, qui ne dépend d'aucun système.
PLAFONDS_MO = {"darwin": 50, "linux": 90, "win32": 75}
PLAFOND_MO = PLAFONDS_MO.get(sys.platform, 90)

INTERDITS = ("sherpa_onnx", "numpy", "keyring", "cryptography", "groq")

echecs: list[str] = []


def ok(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        echecs.append(nom)


def binaire() -> Path:
    if sys.platform == "darwin":
        return RACINE / "dist/Bibliotheque.app/Contents/MacOS/Bibliotheque"
    if os.name == "nt":
        return RACINE / "dist/Bibliotheque/Bibliotheque.exe"
    return RACINE / "dist/Bibliotheque/Bibliotheque"


def racine_app() -> Path:
    # Et non `exe.parent.parent` : Contents/ sur macOS, mais dist/ sur
    # Linux et Windows — où il contient aussi l'archive qu'on vient de
    # fabriquer, et le contrôle de taille compterait le paquet lui-même.
    if sys.platform == "darwin":
        return RACINE / "dist" / "Bibliotheque.app"
    return RACINE / "dist" / "Bibliotheque"


def get(chemin: str, delai: int = 10):
    try:
        with urllib.request.urlopen(BASE + chemin, timeout=delai) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


exe = binaire()
ok("le binaire existe", exe.is_file(), str(exe))
if not exe.is_file():
    sys.exit(1)

# ---- le poids, et ce qu'il contient
app = racine_app()
# Les liens symboliques sont écartés : un paquet .app de macOS en
# contient vingt-cinq, qui pointent vers des fichiers déjà comptés.
# Les suivre donnait 59 Mo pour un paquet que `du` mesure à 34, et le
# contrôle échouait sur un paquet parfaitement sain.
poids = sum(f.stat().st_size for f in app.rglob("*")
            if f.is_file() and not f.is_symlink())
ok(f"le paquet reste petit ({poids / 1048576:.0f} Mo)",
   poids / 1048576 <= PLAFOND_MO,
   f"plafond {PLAFOND_MO} Mo — un module lourd est probablement revenu")

for module in INTERDITS:
    present = any(module.lower() in p.name.lower() for p in app.rglob("*"))
    ok(f"{module} est absent du paquet", not present)

# ---- il démarre et il sert
donnees = Path(tempfile.mkdtemp(prefix="eprouve-biblio-"))
env = dict(os.environ)
env.update(TRANSCRIPTEUR_PORT=str(PORT),
           TRANSCRIPTEUR_SANS_FENETRE="1",
           TRANSCRIPTEUR_DONNEES=str(donnees))

proc = subprocess.Popen([str(exe)], env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
try:
    vivant = False
    for _ in range(60):
        if proc.poll() is not None:
            break
        try:
            if get("/api/health", 2)[0] == 200:
                vivant = True
                break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    ok("le programme démarre et répond", vivant,
       "mort au démarrage" if proc.poll() is not None else "pas de réponse")

    if vivant:
        code, corps = get("/api/health")
        sante = json.loads(corps or b"{}")
        ok("il se déclare bibliothèque", sante.get("bibliotheque") is True)

        code, corps = get("/")
        ok("il sert l'interface", code == 200 and b"<html" in corps.lower())

        code, corps = get("/api/seances")
        ok("il rend la liste des séances",
           code == 200 and "seances" in json.loads(corps or b"{}"))

        # Le dossier de données doit être inscriptible : dans un paquet,
        # écrire à côté de l'exécutable est refusé par le système.
        ok("il écrit dans le dossier de données",
           any(donnees.rglob("*.sqlite3")), str(donnees))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

print(f"\n{'BIBLIOTHÈQUE CONFORME' if not echecs else str(len(echecs)) + ' PROBLÈME(S)'}")
sys.exit(1 if echecs else 0)
