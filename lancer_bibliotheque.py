#!/usr/bin/env python3
"""Démarre la bibliothèque.

Le pendant de `lancer.py` pour le programme allégé : conserver et
relire, sans rien qui transcrive.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from transcripteur.bibliotheque import main  # noqa: E402

if __name__ == "__main__":
    main()
