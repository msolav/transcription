#!/usr/bin/env python3
"""
Point d'entrée de l'application installée.

Un fichier d'une ligne, à la racine, parce que PyInstaller empaquette un
script et non un module : `python -m transcripteur` n'a pas d'équivalent
une fois l'application gelée.

Depuis les sources, les deux chemins restent ouverts :

    python lancer.py            la fenêtre, comme l'application installée
    python -m transcripteur     le serveur et le navigateur, avec les
                                options de la ligne de commande
"""

import multiprocessing

from transcripteur.fenetre import main

if __name__ == "__main__":
    # Sans cela, chaque processus fils relancé par un paquet gelé
    # rouvrirait l'application : une fenêtre, puis deux, puis seize.
    multiprocessing.freeze_support()
    main()
