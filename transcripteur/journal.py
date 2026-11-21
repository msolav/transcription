"""
Le journal du programme, dans un fichier.

L'application installée n'a pas de terminal : ce que `print` écrit part au
néant, et une panne ne laisse aucune trace à lire. Ici, chaque ligne de
`pipeline.log` et chaque erreur non prévue du serveur sont aussi écrites
dans `journal.log`, dans le dossier de données :

    macOS     ~/Library/Application Support/Transcripteur/journal.log
    Windows   %APPDATA%\\Transcripteur\\journal.log
    Linux     ~/.local/share/Transcripteur/journal.log

Au-delà de 2 Mo, le fichier devient `journal.log.1` et un neuf commence :
il ne grossit pas sans fin.

Écrire dans le journal ne doit jamais lui-même faire échouer quoi que ce
soit — un disque plein est justement le cas où l'on en a le plus besoin —
donc toute erreur d'écriture est ignorée.
"""

from __future__ import annotations

import time
import traceback
from pathlib import Path

MAX_OCTETS = 2 * 1024 * 1024


def chemin() -> Path:
    from . import memoire
    return memoire.dossier() / "journal.log"


def ecrire(ligne: str) -> None:
    try:
        f = chemin()
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists() and f.stat().st_size > MAX_OCTETS:
            f.replace(f.with_name(f.name + ".1"))
        with open(f, "a", encoding="utf-8") as out:
            out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {ligne}\n")
    except Exception:  # noqa: BLE001
        pass


def erreur(contexte: str, exc: BaseException) -> None:
    """Une erreur, avec sa trace complète."""
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    ecrire(f"ERREUR {contexte} : {exc!r}\n{trace.rstrip()}")
