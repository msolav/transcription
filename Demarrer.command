#!/bin/bash
# Double-clique sur ce fichier pour lancer le Transcripteur.
cd "$(dirname "$0")" || exit 1

echo "Transcripteur"
echo "-------------"

PY=""
for candidate in python3 python3.12 python3.11 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
      PY="$candidate"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo
  echo "Python 3 n'est pas installé sur cette machine."
  echo "Télécharge-le sur https://www.python.org/downloads/ (bouton jaune),"
  echo "installe-le, puis double-clique de nouveau sur ce fichier."
  echo
  read -r -p "Appuie sur Entrée pour fermer."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Installation (une seule fois, compte deux ou trois minutes)…"
  "$PY" -m venv .venv || { echo "Création de l'environnement impossible."; read -r; exit 1; }
fi

VENV_PY=".venv/bin/python"
STAMP=".venv/.installed"

if [ ! -f "$STAMP" ] || [ transcripteur/requirements.txt -nt "$STAMP" ]; then
  echo "Installation des composants…"
  "$VENV_PY" -m pip install --quiet --upgrade pip
  "$VENV_PY" -m pip install --quiet -r transcripteur/requirements.txt || {
    echo "Installation échouée. Vérifie ta connexion et relance."; read -r; exit 1; }
  touch "$STAMP"
fi

"$VENV_PY" -m transcripteur
echo
read -r -p "Programme arrêté. Appuie sur Entrée pour fermer."
