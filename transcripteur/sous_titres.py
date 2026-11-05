"""
Sous-titres (SRT, VTT) construits sur les horodatages des mots.

Pourquoi ne pas exporter les blocs tels quels : un bloc est un tour de
parole. En réunion, un tour dure couramment deux minutes. Affiché comme
sous-titre, cela donne un pavé immobile à l'écran pendant deux minutes,
pendant que la personne parle d'autre chose. Un sous-titre est une unité
de lecture, pas une unité de parole, et les deux n'ont aucun rapport de
taille.

On redécoupe donc depuis les mots, qui portent chacun son début et sa
fin. Les règles suivies sont celles du sous-titrage courant : deux lignes
au plus, une quarantaine de caractères par ligne, une seconde au moins à
l'écran et six au plus. Les coupes cherchent d'abord une fin de phrase,
puis un silence, puis une fin de membre de phrase — couper au milieu d'un
groupe de mots se lit mal, même quand le compte de caractères tombe juste.

Une réplique ne franchit jamais un changement de voix : deux personnes
dans le même sous-titre, c'est l'information la plus trompeuse qu'on
puisse afficher.

Sans horodatage des mots — les exports d'une version ancienne — on ne
produit rien. Répartir un bloc au prorata des caractères donnerait des
sous-titres d'aspect normal et faux de plusieurs secondes, ce qui est
pire qu'une absence : un sous-titre décalé se remarque, mais on ne sait
pas de combien, donc on ne sait plus à quoi se fier.
"""

from __future__ import annotations

import re

from .pipeline import join_words

# Deux lignes de ~42 caractères : la limite du sous-titrage télévisé, et
# ce que l'œil lit sans quitter l'image des yeux.
CHARS_PAR_LIGNE = 42
LIGNES_MAX = 2
LIMITE = CHARS_PAR_LIGNE * LIGNES_MAX

MIN_DUREE = 1.0     # en deçà, on ne lit pas : on aperçoit
MAX_DUREE = 6.0     # au-delà, le sous-titre paraît figé
PAUSE = 0.7         # un silence de cette longueur est une coupe naturelle
ECART = 0.08        # blanc entre deux répliques, pour qu'on voie le changement

# Dans un tour de parole long, le nom réapparaît de temps en temps : qui
# arrive en cours de tour n'a jamais vu le nom affiché au début.
RAPPEL_NOM = 30.0

# Une coupe de membre de phrase n'est préférable que si elle laisse une
# réplique de taille honnête ; sinon on remplit la ligne.
PART_MINIMALE = 0.6

_FIN_PHRASE = re.compile(r"[.!?…]+[\"'»)\]]*$")
_FIN_MEMBRE = re.compile(r"[,;:]+[\"'»)\]]*$")


class SansHorodatage(Exception):
    """Le transcript ne porte pas les horodatages des mots."""


def _coller(mots: list[dict]) -> str:
    return join_words(mots)


def _prochaine_coupe(mots: list[dict], depart: int, limite: int) -> int:
    """Index de fin (exclu) de la réplique qui commence à `mots[depart]`."""
    membre = 0
    j = depart
    while j < len(mots):
        trop = (len(_coller(mots[depart:j + 1])) > limite
                or mots[j]["end"] - mots[depart]["start"] > MAX_DUREE)
        if trop and j > depart:
            # On a dépassé la limite. Reculer sur la dernière virgule
            # connue, mais seulement si elle laisse une réplique pleine :
            # une coupe deux mots après le début fabrique un clignotement.
            if membre and len(_coller(mots[depart:membre])) >= limite * PART_MINIMALE:
                return membre
            return j
        if _FIN_PHRASE.search(mots[j]["text"]):
            return j + 1
        silence = (j + 1 < len(mots)
                   and mots[j + 1]["start"] - mots[j]["end"] >= PAUSE)
        if silence:
            return j + 1
        if _FIN_MEMBRE.search(mots[j]["text"]):
            membre = j + 1
        j += 1
    return len(mots)


def replier(texte: str) -> str:
    """Au plus deux lignes, coupées à l'espace le plus proche du milieu.

    Équilibrer les deux lignes plutôt que remplir la première : un
    sous-titre dont la seconde ligne porte un mot seul attire l'œil sur
    ce mot sans raison."""
    if len(texte) <= CHARS_PAR_LIGNE:
        return texte
    milieu = len(texte) // 2
    espaces = [i for i, c in enumerate(texte) if c == " "]
    if not espaces:
        return texte
    coupe = min(espaces, key=lambda i: abs(i - milieu))
    return texte[:coupe] + "\n" + texte[coupe + 1:]


def decouper(blocs: list[dict], noms: dict | None = None,
             avec_noms: bool = False) -> list[dict]:
    """Les répliques d'un transcript, prêtes à être affichées.

    `noms` est la table des noms donnés aux voix ; une voix sans nom garde
    son étiquette d'origine, faute de mieux. `avec_noms` à faux produit
    des sous-titres de film : le texte seul."""
    noms = noms or {}
    mots_totaux = sum(len(b.get("words") or []) for b in blocs)
    if blocs and not mots_totaux:
        raise SansHorodatage(
            "Ce transcript ne porte pas les horodatages des mots : on ne "
            "peut pas en tirer de sous-titres. Il faut le retranscrire "
            "depuis l'enregistrement.")

    repliques: list[dict] = []
    for bloc in blocs:
        mots = [m for m in (bloc.get("words") or [])
                if m.get("text", "").strip()]
        if not mots:
            continue
        voix = bloc.get("speaker") or ""
        nom = (noms.get(voix) or "").strip() or _etiquette(voix)
        dernier_nom = -1e9
        i = 0
        while i < len(mots):
            # Le nom occupe de la place : la limite de caractères doit en
            # tenir compte, sinon la réplique nommée déborde sur une
            # troisième ligne.
            # `dernier_nom` repart à chaque bloc : la première réplique
            # d'un tour porte toujours le nom, puisqu'un bloc est un tour.
            prefixe = ""
            if avec_noms and nom and mots[i]["start"] - dernier_nom >= RAPPEL_NOM:
                prefixe = f"{nom} : "
            fin = _prochaine_coupe(mots, i, LIMITE - len(prefixe))
            texte = prefixe + _coller(mots[i:fin])
            if prefixe:
                dernier_nom = mots[i]["start"]
            repliques.append({
                "start": mots[i]["start"],
                "end": mots[fin - 1]["end"],
                "text": texte,
                "speaker": voix,
            })
            i = fin

    # Les blocs arrivent dans l'ordre, mais on ne s'y fie pas : une seule
    # réplique hors séquence suffirait à faire caler toutes les suivantes
    # sur un mauvais voisin.
    repliques.sort(key=lambda r: (r["start"], r["end"]))
    return _caler(repliques)


def _etiquette(voix: str) -> str:
    """« SPEAKER_00 » devient « Voix 1 » : un nom par défaut lisible."""
    chiffres = re.search(r"(\d+)", voix or "")
    return f"Voix {int(chiffres.group(1)) + 1}" if chiffres else (voix or "")


def _caler(repliques: list[dict]) -> list[dict]:
    """Règle les durées : rien de trop court, rien qui chevauche.

    Une réplique d'un demi-mot dure parfois 0,3 s. On l'étire dans le
    silence qui suit, jamais sur la réplique suivante : un sous-titre qui
    en recouvre un autre fait disparaître l'un des deux selon le lecteur,
    et on ne sait pas lequel."""
    for n, r in enumerate(repliques):
        if r["end"] < r["start"]:
            r["end"] = r["start"]
        suivante = repliques[n + 1]["start"] if n + 1 < len(repliques) else None
        if r["end"] - r["start"] < MIN_DUREE:
            voulu = r["start"] + MIN_DUREE
            plafond = suivante - ECART if suivante is not None else voulu
            r["end"] = max(r["end"], min(voulu, plafond))
        if suivante is not None and r["end"] > suivante - ECART:
            r["end"] = max(r["start"], suivante - ECART)
    return repliques


# --------------------------------------------------------------------------
# Sorties
# --------------------------------------------------------------------------

def horodatage(secondes: float, separateur: str) -> str:
    secondes = max(0.0, secondes)
    heures, reste = divmod(int(secondes), 3600)
    minutes, sec = divmod(reste, 60)
    milli = int(round((secondes - int(secondes)) * 1000))
    if milli >= 1000:   # un arrondi qui déborde ne doit pas écrire « :60 »
        milli = 999
    return f"{heures:02d}:{minutes:02d}:{sec:02d}{separateur}{milli:03d}"


def vers_srt(repliques: list[dict]) -> str:
    lignes = []
    for n, r in enumerate(repliques, start=1):
        lignes += [str(n),
                   f"{horodatage(r['start'], ',')} --> {horodatage(r['end'], ',')}",
                   replier(r["text"]), ""]
    return "\n".join(lignes)


def vers_vtt(repliques: list[dict]) -> str:
    """WebVTT, le seul format que lise une balise <track>.

    Les chevrons sont échappés : un « <rire> » noté dans le transcript
    serait pris pour une balise et effacerait la fin de la réplique."""
    lignes = ["WEBVTT", ""]
    for n, r in enumerate(repliques, start=1):
        texte = (replier(r["text"]).replace("&", "&amp;")
                 .replace("<", "&lt;").replace(">", "&gt;"))
        # Posé à la hauteur voulue plutôt qu'au défaut du navigateur.
        # Dans un cadre d'aperçu, qui est bien plus court qu'un lecteur
        # plein écran, le défaut colle le texte au bord inférieur et les
        # jambages des p et des g passent sous l'image. On vise une fin
        # de bloc aux alentours de 95 % de la hauteur, que la réplique
        # tienne sur une ligne ou sur deux.
        place = "line:80%" if "\n" in texte else "line:88%"
        lignes += [str(n),
                   f"{horodatage(r['start'], '.')} --> "
                   f"{horodatage(r['end'], '.')} {place} align:center",
                   texte, ""]
    return "\n".join(lignes)
