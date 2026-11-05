#!/usr/bin/env python3
"""
L'application empaquetée démarre-t-elle, et sert-elle son interface ?

Lancé par la chaîne de construction, sur Mac et sur Windows, juste après
PyInstaller. Une construction qui réussit ne prouve rien : les pannes
d'empaquetage — un fichier oublié, une bibliothèque native absente, un
dossier où l'on ne peut pas écrire — ne se produisent qu'au démarrage,
chez quelqu'un qui vient d'installer, et ressemblent à un programme qui
ne fait rien.

    python outils/eprouver_paquet.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PORT = 7873
BASE = f"http://127.0.0.1:{PORT}"

echecs: list[str] = []


def ok(nom: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        echecs.append(nom)


def binaire() -> Path:
    if sys.platform == "darwin":
        return RACINE / "dist/Transcripteur.app/Contents/MacOS/Transcripteur"
    if os.name == "nt":
        return RACINE / "dist/Transcripteur/Transcripteur.exe"
    return RACINE / "dist/Transcripteur/Transcripteur"


def ressources() -> Path:
    """Où PyInstaller a posé les fichiers qui ne sont pas du code."""
    if sys.platform == "darwin":
        return RACINE / "dist/Transcripteur.app/Contents/Resources"
    return RACINE / "dist/Transcripteur/_internal"


def get(chemin: str, delai: int = 10):
    with urllib.request.urlopen(BASE + chemin, timeout=delai) as r:
        return r.status, r.read()


exe = binaire()
donnees = Path(tempfile.mkdtemp(prefix="eprouve-"))

print(f"\n1. Le paquet est complet ({exe.name})")
ok("le binaire existe", exe.exists(), str(exe))
if not exe.exists():
    print("\nRIEN À ÉPROUVER")
    sys.exit(1)
ok("il est exécutable", os.access(exe, os.X_OK))

statiques = ressources() / "transcripteur" / "static"
ok("les pages sont emportées", (statiques / "index-vm.html").exists(),
   str(statiques))
for greffe in ("branchement.js", "apercu.js", "seances.js"):
    ok(f"{greffe} est emporté", (statiques / greffe).exists())

print("\n2. Elle démarre")
# Sans fenêtre : la machine de construction n'a pas d'écran, et c'est le
# serveur qu'on éprouve. Sur un port connu, sinon on ne saurait où
# frapper. Sur un dossier de données jetable, et sans les clés de
# l'environnement, pour voir ce que voit une installation neuve.
env = dict(os.environ,
           TRANSCRIPTEUR_SANS_FENETRE="1",
           TRANSCRIPTEUR_PORT=str(PORT),
           TRANSCRIPTEUR_DONNEES=str(donnees))
for cle in ("GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    env.pop(cle, None)

proc = subprocess.Popen([str(exe)], env=env, cwd=str(RACINE),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True)
sante = None
for _ in range(80):
    if proc.poll() is not None:
        break
    try:
        _, corps = get("/api/health", 2)
        sante = json.loads(corps)
        break
    except Exception:  # noqa: BLE001
        time.sleep(0.5)

ok("le programme tourne encore", proc.poll() is None,
   f"terminé avec le code {proc.returncode}")
ok("le serveur répond", sante is not None)

if sante:
    ok("une installation neuve ne connaît aucune clé",
       not sante["has_key"] and not sante["key_from_env"], str(sante))

    print("\n3. Elle sert son interface depuis le paquet")
    code, html = get("/vm")
    page = html.decode("utf-8")
    ok("l'interface est servie", code == 200 and len(page) > 100_000,
       f"{code}, {len(page)} octets")
    ok("les trois greffes sont posées",
       all(f'src="/static/{g}"' in page
           for g in ("branchement.js", "apercu.js", "seances.js")))
    for greffe in ("branchement.js", "apercu.js", "seances.js"):
        code, corps = get(f"/static/{greffe}")
        ok(f"{greffe} est servi", code == 200 and len(corps) > 500, str(code))

    # Le mode d'emploi est fabriqué par du code, pas lu sur le disque :
    # c'est la page que verra quelqu'un qui n'a pas encore de clé.
    code, aide = get("/aide")
    ok("la page d'aide se fabrique",
       code == 200 and b"console.groq.com" in aide, str(code))

    print("\n4. Elle écrit là où elle a le droit")
    code, corps = get("/api/seances")
    place = json.loads(corps)["place"]
    ok("la mémoire s'ouvre dans le dossier de données",
       str(donnees) in place["dossier"], place["dossier"])
    ok("la base est créée", (donnees / "transcripteur.sqlite3").exists())
    # Le point qui casse une application installée : les modèles ne
    # doivent plus viser l'intérieur du paquet, en lecture seule.
    code, corps = get("/api/reglages")
    ok("les réglages se lisent et s'écrivent", code == 200)

proc.terminate()
try:
    sortie = proc.communicate(timeout=20)[0]
except subprocess.TimeoutExpired:
    proc.kill()
    sortie = proc.communicate()[0]

if sortie and sortie.strip():
    print("\n   sortie du programme :")
    for ligne in sortie.strip().splitlines()[:15]:
        print("     " + ligne[:160])

shutil.rmtree(donnees, ignore_errors=True)

print(f"\n{'PAQUET CONFORME' if not echecs else str(len(echecs)) + ' PROBLÈME(S)'}")
sys.exit(1 if echecs else 0)
