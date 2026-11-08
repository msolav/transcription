#!/usr/bin/env python3
"""Dessine l'icône de l'application, et la décline pour chaque système.

Le motif est ce que l'application produit : un transcript. Des lignes de
texte, précédées chacune du filet de couleur qui marque sa voix — le même
filet que dans l'interface, avec les mêmes couleurs. Les lignes sont de
longueurs inégales, comme de vraies répliques, et la dernière est courte
parce qu'elle est en cours.

Pas de microphone, pas d'onde sonore : ce sont les icônes de tous les
enregistreurs. Ce programme ne sert pas à enregistrer, il sert à relire.

    python3 outils/icone.py            écrit dans outils/icone/
    python3 outils/icone.py --montrer  et ouvre l'aperçu 512 px

Produit icone.icns (macOS), icone.ico (Windows) et icone.png (Linux et
l'aperçu). PyInstaller lit les deux premiers depuis Transcripteur.spec.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    sys.exit("Pillow est requis : pip install pillow")

RACINE = Path(__file__).resolve().parent.parent
SORTIE = Path(__file__).resolve().parent / "icone"

# Les couleurs de l'application. L'encre et le papier d'abord, puis les
# couleurs de voix, dans l'ordre où l'interface les distribue.
ENCRE = (12, 12, 11, 255)
PAPIER = (241, 239, 233, 255)
VOIX = [(228, 87, 46, 255),      # orangé
        (74, 108, 247, 255),     # cobalt
        (23, 190, 187, 255),     # turquoise
        (232, 168, 56, 255)]     # ambre

# Chaque réplique : la voix qui parle, et la longueur de ses lignes en
# part de la largeur utile. Composé à la main plutôt que tiré au hasard :
# à seize pixels, l'équilibre des pleins et des vides fait tout.
REPLIQUES = [
    (0, [0.95, 0.62]),
    (1, [0.80]),
    (2, [0.95, 0.88, 0.40]),
    (3, [0.55]),
]

# En dessous de 32 px, sept lignes de texte se touchent et l'icône
# devient une bouillie grise — vérifié sur une planche au pixel près. On
# n'y met que trois répliques d'une ligne, plus épaisses et plus
# espacées : le motif reste le même, il est seulement dit moins vite.
REPLIQUES_PETITES = [
    (0, [0.95]),
    (1, [0.70]),
    (2, [0.88]),
]
SEUIL_PETIT = 32


def dessiner(taille: int) -> Image.Image:
    """L'icône à une taille donnée, dessinée en proportions pures."""
    # Dessiné quatre fois trop grand puis réduit : les filets font moins
    # d'un pixel aux petites tailles, et un rendu direct les ferait
    # disparaître ou sauter d'une rangée à l'autre.
    echelle = 4
    n = taille * echelle
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Le fond : un carré à coins arrondis, à la façon des icônes du
    # système, mais sans dégradé ni ombre — le grain et l'aplat suffisent.
    marge = n * 0.055
    rayon = n * 0.22
    d.rounded_rectangle([marge, marge, n - marge, n - marge],
                        radius=rayon, fill=ENCRE)

    petite = taille < SEUIL_PETIT
    repliques = REPLIQUES_PETITES if petite else REPLIQUES

    gauche = n * 0.235
    droite = n - n * 0.20
    largeur = droite - gauche

    # La hauteur totale des répliques, pour les centrer verticalement.
    hauteur_ligne = n * (0.090 if petite else 0.052)
    espace_ligne = n * 0.035
    espace_replique = n * (0.085 if petite else 0.062)
    total = 0.0
    for _, lignes in repliques:
        total += len(lignes) * hauteur_ligne + (len(lignes) - 1) * espace_ligne
    total += (len(repliques) - 1) * espace_replique
    y = (n - total) / 2

    for voix, lignes in repliques:
        bloc = len(lignes) * hauteur_ligne + (len(lignes) - 1) * espace_ligne
        # Le filet de la voix, à gauche, sur toute la hauteur du bloc.
        filet = n * (0.052 if petite else 0.030)
        d.rounded_rectangle(
            [gauche - n * 0.085, y, gauche - n * 0.085 + filet, y + bloc],
            radius=filet / 2, fill=VOIX[voix % len(VOIX)])
        # Les lignes de texte.
        yy = y
        for part in lignes:
            d.rounded_rectangle(
                [gauche, yy, gauche + largeur * part, yy + hauteur_ligne],
                radius=hauteur_ligne / 2, fill=PAPIER)
            yy += hauteur_ligne + espace_ligne
        y += bloc + espace_replique

    return img.resize((taille, taille), Image.LANCZOS)


def icns(dossier: Path) -> Path | None:
    """Le .icns de macOS, par iconutil — le seul qui fasse foi."""
    if not shutil.which("iconutil"):
        print("  iconutil absent : .icns non produit (hors macOS)")
        return None
    jeu = dossier / "icone.iconset"
    if jeu.exists():
        shutil.rmtree(jeu)
    jeu.mkdir(parents=True)
    # Les tailles qu'exige iconutil, et leurs doubles.
    for t in (16, 32, 128, 256, 512):
        dessiner(t).save(jeu / f"icon_{t}x{t}.png")
        dessiner(t * 2).save(jeu / f"icon_{t}x{t}@2x.png")
    cible = dossier / "icone.icns"
    subprocess.run(["iconutil", "-c", "icns", str(jeu), "-o", str(cible)],
                   check=True)
    shutil.rmtree(jeu)
    return cible


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--montrer", action="store_true")
    args = p.parse_args()

    SORTIE.mkdir(parents=True, exist_ok=True)

    png = SORTIE / "icone.png"
    dessiner(1024).save(png)
    print(f"  {png.relative_to(RACINE)}")

    # Windows veut toutes ses tailles dans un seul fichier.
    ico = SORTIE / "icone.ico"
    dessiner(256).save(ico, sizes=[(16, 16), (24, 24), (32, 32),
                                   (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"  {ico.relative_to(RACINE)}")

    mac = icns(SORTIE)
    if mac:
        print(f"  {mac.relative_to(RACINE)}")

    # L'aperçu ne s'écrit que si on le demande : c'est un brouillon de
    # contrôle, pas un produit, et il n'a rien à faire dans le dépôt.
    if args.montrer:
        apercu = SORTIE / "apercu.png"
        dessiner(512).save(apercu)
        subprocess.run(["open", str(apercu)])


if __name__ == "__main__":
    main()
