@echo off
rem Double-clique sur ce fichier pour lancer le Transcripteur.
cd /d "%~dp0"
title Transcripteur

echo Transcripteur
echo -------------

where py >nul 2>&1 && set PY=py -3
if not defined PY (where python >nul 2>&1 && set PY=python)

if not defined PY (
  echo.
  echo Python 3 n'est pas installe sur cette machine.
  echo Telecharge-le sur https://www.python.org/downloads/
  echo Coche "Add Python to PATH" pendant l'installation,
  echo puis double-clique de nouveau sur ce fichier.
  echo.
  pause
  exit /b 1
)

if not exist .venv (
  echo Installation ^(une seule fois, compte deux ou trois minutes^)...
  %PY% -m venv .venv || (echo Creation de l'environnement impossible. & pause & exit /b 1)
)

if not exist .venv\.installed (
  echo Installation des composants...
  .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
  .venv\Scripts\python.exe -m pip install --quiet -r transcripteur\requirements.txt || (
    echo Installation echouee. Verifie ta connexion et relance. & pause & exit /b 1)
  echo ok> .venv\.installed
)

.venv\Scripts\python.exe -m transcripteur
echo.
pause
