#!/usr/bin/env python3
"""Quel modèle d'empreintes confond le moins deux voix du même genre ?

Le défaut signalé à l'usage : la séparation distingue bien une voix
masculine d'une voix féminine, et mélange complètement deux voix du même
genre. Il fallait donc une mesure qui distingue ces deux erreurs, et un
enregistrement où les deux cas existent.

Faute de corpus annoté sous la main, la conversation est synthétisée avec
les voix de macOS : quatre personnes, deux féminines et deux masculines,
dont on connaît exactement qui parle quand. C'est une approximation —
des voix de synthèse ne se confondent pas comme des vraies — et elle vaut
pour **classer les modèles entre eux**, pas pour annoncer un taux absolu.

    python3 outils/mesure_attribution.py              6,9 min, tous les modèles
    python3 outils/mesure_attribution.py --minutes 2  plus court, pour essayer
    python3 outils/mesure_attribution.py --nettoyage  avec et sans nettoyage

Deux colonnes, parce que deux erreurs différentes :

    même genre   part du temps donnée à l'autre personne du même genre
    autre        part du temps donnée à quelqu'un de l'autre genre

C'est la première qui compte ici. La seconde devrait être proche de zéro
sur un modèle sain ; quand elle ne l'est pas, le modèle n'entend pas
grand-chose.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from transcripteur import assets, pipeline  # noqa: E402

# Deux voix par genre : c'est le minimum pour que la confusion de même
# genre puisse seulement exister.
VOIX = [("Amélie", "F1"), ("Marie", "F2"), ("Thomas", "H1"), ("Jacques", "H2")]

PHRASES = [
    "Je pense qu'il faut revoir le budget du printemps avant la rencontre.",
    "On a reçu trois soumissions, et la dernière me paraît la plus sérieuse.",
    "Est-ce qu'on a confirmé la salle pour le quinze du mois prochain ?",
    "Il reste à décider qui va rédiger le compte rendu de cette séance.",
    "Les inscriptions ont augmenté depuis septembre, c'est une bonne nouvelle.",
    "Je ne serai pas disponible vendredi, j'ai une formation toute la journée.",
    "Le comité a demandé qu'on précise les modalités d'accès en soirée.",
    "On pourrait commencer par le point sur la sécurité alimentaire.",
]

PAS = 0.10      # on compte le temps par tranches de 100 ms


def _outil(nom: str) -> str:
    chemin = subprocess.run(["which", nom], capture_output=True,
                            text=True).stdout.strip()
    if not chemin:
        sys.exit(f"{nom} est introuvable.")
    return chemin


def fabriquer(dossier: Path, minutes: float, graine: int = 29):
    """Une conversation à quatre voix, et la vérité sur qui parle quand."""
    if not sys.platform.startswith("darwin"):
        sys.exit("La synthèse passe par `say`, qui n'existe que sur macOS.")
    ff = _outil("ffmpeg")
    sonde = ff.replace("ffmpeg", "ffprobe")
    random.seed(graine)

    morceaux, etiquettes = [], []
    # Un tour fait trois à quatre secondes : de quoi viser la durée.
    for tour in range(int(minutes * 60 / 3.8)):
        # Le tour de parole alterne, sauf une fois sur sept : une
        # conversation où chacun parle à son tour est plus facile à
        # séparer qu'une vraie réunion.
        nom, etiq = VOIX[tour % 4] if tour % 7 else random.choice(VOIX)
        f = dossier / f"{tour:03d}.aiff"
        subprocess.run(["say", "-v", nom, "-o", str(f),
                        random.choice(PHRASES)], check=True)
        morceaux.append(f)
        etiquettes.append(etiq)

    liste = dossier / "liste.txt"
    liste.write_text("".join(f"file '{f}'\n" for f in morceaux))
    wav = dossier / "conversation.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(liste), "-ar", "16000", "-ac", "1", str(wav)],
                   check=True)

    # Les durées se relisent sur les fichiers : `say` ne rend pas
    # exactement la longueur qu'on croit, et une vérité terrain fausse de
    # deux dixièmes fausserait tout le reste.
    verite, t = [], 0.0
    for f, etiq in zip(morceaux, etiquettes):
        dur = float(subprocess.run(
            [sonde, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(f)], capture_output=True,
            text=True).stdout.strip())
        verite.append({"debut": round(t, 3), "fin": round(t + dur, 3), "qui": etiq})
        t += dur
    return wav, verite, t


def _qui_a(verite, t):
    for v in verite:
        if v["debut"] <= t < v["fin"]:
            return v["qui"]
    return None


def noter(verite, tours):
    """Rend (exactitude, même genre, autre genre, groupes trouvés).

    Chaque groupe trouvé est associé à la personne qu'il contient
    majoritairement — sans cela, une permutation des étiquettes compterait
    comme une erreur alors que la séparation serait parfaite."""
    trouve = {}
    for debut, fin, lab in tours:
        t = debut
        while t < fin:
            trouve[round(t, 1)] = lab
            t += PAS

    par_groupe = defaultdict(Counter)
    for t, lab in trouve.items():
        qui = _qui_a(verite, t)
        if qui:
            par_groupe[lab][qui] += 1
    carte = {g: c.most_common(1)[0][0] for g, c in par_groupe.items()}

    bons = meme = autre = total = 0
    for t, lab in trouve.items():
        qui = _qui_a(verite, t)
        if not qui:
            continue
        total += 1
        vu = carte.get(lab)
        if vu == qui:
            bons += 1
        elif vu and vu[0] == qui[0]:     # F1 pris pour F2, H1 pour H2
            meme += 1
        else:
            autre += 1
    n = max(total, 1)
    return bons / n, meme / n, autre / n, len(par_groupe)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minutes", type=float, default=6.9)
    p.add_argument("--nettoyage", action="store_true",
                   help="mesurer aussi avec le son nettoyé")
    p.add_argument("--modeles", nargs="*", default=None)
    args = p.parse_args()

    bac = Path(tempfile.mkdtemp(prefix="mesure-attribution-"))
    print(f"synthèse de la conversation dans {bac}…")
    wav, verite, duree = fabriquer(bac, args.minutes)
    audio = pipeline.read_wav16k(wav)
    print(f"{duree / 60:.1f} min, 4 voix (2 féminines, 2 masculines), "
          f"{len(verite)} tours\n")

    cles = args.modeles or [e.cle for e in assets.CATALOGUE
                            if e.famille == "multi"] + ["campplus_zh_en"]
    versions = [("non", audio)]
    if args.nettoyage:
        print("nettoyage du son…")
        versions.append(("oui", pipeline.denoise(audio, "gtcrn",
                                                 lambda *a: None, (0, 1))))

    print(f"{'modèle':24s} {'nett.':6s} {'exact':>7s} {'même genre':>11s} "
          f"{'autre':>7s} {'groupes':>8s} {'durée':>7s}")
    for cle in cles:
        for nom_n, son in versions:
            t0 = time.time()
            try:
                tours = pipeline.diarize(son, len(VOIX), lambda *a: None, (0, 1),
                                         pipeline.CLUSTER_THRESHOLD, cle)
            except Exception as exc:  # noqa: BLE001
                print(f"{cle:24s} {nom_n:6s} échec : {exc}")
                continue
            ex, mg, au, ng = noter(verite, tours)
            print(f"{cle:24s} {nom_n:6s} {ex * 100:6.1f}% {mg * 100:10.1f}% "
                  f"{au * 100:6.1f}% {ng:8d} {time.time() - t0:6.1f}s")

    print(f"\nLes fichiers restent dans {bac}")
    print("La justesse relevée ici alimente le champ `justesse` du catalogue,\n"
          "qui décide de ce que « choisir pour moi » retient.")


if __name__ == "__main__":
    main()
