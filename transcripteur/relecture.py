"""
Relecture du transcript par un modèle de langue.

Deux passes, indépendantes et facultatives :

- **l'attribution** : un modèle de langue voit ce qu'aucun modèle de voix
  ne peut voir. Que « avant d'être » et « accordés » forment une seule
  proposition, qu'une question appelle une réponse, qu'un « exactement »
  répond à quelqu'un d'autre. Là où les empreintes vocales hésitent, la
  syntaxe tranche.

- **le texte** : mots tronqués, coquilles, accords manquants. Whisper
  transcrit vite et laisse des scories.

Rien n'est écrasé. Chaque passe rend une liste de corrections que
l'interface applique par-dessus l'original, qui reste intact : on peut
comparer, revenir en arrière, n'accepter que l'attribution.

Garde-fou : un modèle de langue à qui l'on demande de corriger réécrit
volontiers ce qu'il aurait dit à la place. Une correction de texte qui
s'éloigne trop de l'original est refusée ici même, sans être montrée.
C'est le compte rendu d'une vraie réunion : ce qui a été dit prime sur ce
qui aurait été mieux dit.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher

# Modèles à poids ouverts servis par Groq. La clé est déjà là, il n'y a
# donc ni compte à créer ni gigaoctet à télécharger.
MODELES = {
    "gpt-oss-120b": {"id": "openai/gpt-oss-120b", "nom": "GPT-OSS 120B",
                     "note": "Le plus fiable des trois. À préférer pour l'attribution."},
    "gpt-oss-20b": {"id": "openai/gpt-oss-20b", "nom": "GPT-OSS 20B",
                    "note": "Plus rapide et moins cher, un peu moins sûr."},
    "qwen3.6-27b": {"id": "qwen/qwen3.6-27b", "nom": "Qwen 3.6 27B",
                    "note": "Autre famille : utile en deuxième avis."},
}
MODELE_DEFAUT = "gpt-oss-120b"

# Fenêtres larges à dessein : la consigne système est renvoyée à chaque
# appel, donc doubler la fenêtre divise par deux ce qu'on repaie. Sur un
# transcript de 600 blocs, passer de 14 à 30 fait tomber le nombre
# d'appels de 44 à 21. Le quota gratuit de Groq est de 200 000 jetons par
# jour et par modèle : une relecture complète en consommait presque tout.
FENETRE = 30          # blocs envoyés d'un coup
RECOUVREMENT = 2      # blocs de contexte repris de la fenêtre précédente
CARACTERES_PAR_JETON = 3.4   # approximation pour du français
FIDELITE_MIN = 0.72   # en dessous, la « correction » est une réécriture

RESUMES = {
    "compte_rendu": ("Compte rendu", "un compte rendu structuré : contexte, "
                     "points abordés, décisions prises, points en suspens"),
    "actions": ("Décisions et suites à donner", "la liste des décisions arrêtées et "
                "des actions à mener, avec qui s'en charge quand c'est dit"),
    "bref": ("Résumé bref", "un résumé de dix lignes au plus, en prose"),
    "themes": ("Par thème", "une synthèse organisée par thème plutôt que "
               "chronologiquement"),
}


class RelectureError(RuntimeError):
    pass


class QuotaError(RelectureError):
    """Quota du fournisseur épuisé.

    Distincte des autres pannes parce qu'elle ne se rattrape pas : réessayer
    la fenêtre suivante ne fera que rejouer le même refus. Une relecture à
    moitié faite qui se présente comme terminée est pire qu'un arrêt net,
    donc celle-ci interrompt la passe entière."""


def _est_quota(exc: Exception) -> bool:
    texte = str(exc)
    return "rate_limit" in texte or "429" in texte or "tokens per day" in texte


def _delai(exc: Exception) -> str:
    import re as _re
    trouve = _re.search(r"try again in ([\dhms.]+)", str(exc))
    # Le point final de la phrase colle au délai : « dans 1h21m9.936s. »
    return trouve.group(1).rstrip(".") if trouve else ""


def estimer_jetons(blocs: list[dict], attribution: bool, texte: bool) -> int:
    """Ce que la relecture va coûter, avant de la lancer.

    Approximation volontairement haute : mieux vaut annoncer plus que de
    laisser quelqu'un épuiser son quota du jour sans prévenir."""
    corps = sum(len(b["text"]) for b in blocs)
    fenetres = max(1, -(-len(blocs) // FENETRE))
    consigne = 1400 * fenetres          # la consigne système, à chaque appel
    contexte = corps * (1 + RECOUVREMENT / FENETRE) / CARACTERES_PAR_JETON
    total = 0
    if attribution:
        total += consigne + contexte + corps / CARACTERES_PAR_JETON * 0.15
    if texte:
        total += consigne + contexte + corps / CARACTERES_PAR_JETON * 0.5
    return int(total)


def _client(api_key: str):
    try:
        from groq import Groq
    except ImportError as exc:
        raise RelectureError("Le paquet groq n'est pas installé.") from exc
    return Groq(api_key=api_key)


def _appeler(api_key: str, modele: str, systeme: str, requete: str,
             json_attendu: bool = True) -> str:
    reference = MODELES.get(modele, MODELES[MODELE_DEFAUT])["id"]
    params = dict(
        model=reference,
        messages=[{"role": "system", "content": systeme},
                  {"role": "user", "content": requete}],
        temperature=0.0,
    )
    if json_attendu:
        params["response_format"] = {"type": "json_object"}
    reponse = _client(api_key).chat.completions.create(**params)
    return reponse.choices[0].message.content or ""


def _nom(bloc: dict, noms: dict) -> str:
    return noms.get(bloc["speaker"]) or bloc["speaker"].replace("SPEAKER_", "Voix ")


def _fenetres(total: int):
    """Découpe en fenêtres qui se chevauchent.

    Le recouvrement n'est pas du luxe : une frontière mal placée se juge
    sur ce qui la précède, et une fenêtre qui commencerait pile dessus ne
    verrait que la moitié du problème."""
    debut = 0
    while debut < total:
        fin = min(debut + FENETRE, total)
        yield max(0, debut - RECOUVREMENT), debut, fin
        debut = fin


SYSTEME_ATTRIBUTION = """Tu relis la transcription d'une conversation réelle.

Un logiciel a réparti les phrases entre les personnes en comparant les
voix. Il se trompe régulièrement de deux façons :
- il coupe au milieu d'une proposition et donne la fin à quelqu'un d'autre
- il rate un changement de personne et colle une réponse au locuteur précédent

Tu ne juges QUE sur le sens et la syntaxe. Une proposition grammaticale
appartient à une seule personne. Une question et sa réponse appartiennent
à deux personnes différentes. Une approbation (« exactement », « tout à
fait », « oui ») vient de quelqu'un d'autre que celui qui vient de parler.

Réponds en JSON : {"corrections": [...]}, chaque correction étant
- {"bloc": <numéro>, "locuteur": "<nom exact>"} pour réattribuer un bloc entier
- {"bloc": <numéro>, "deplacer": <n>} pour déplacer des mots à la frontière :
  n positif = les n premiers mots du bloc reviennent au bloc précédent,
  n négatif = les |n| derniers mots du bloc passent au bloc suivant

N'inclus que les blocs à corriger. Dans le doute, ne corrige pas : une
attribution douteuse laissée telle quelle est préférable à une correction
inventée. Si tout est correct, réponds {"corrections": []}."""

SYSTEME_TEXTE = """Tu corriges la transcription automatique d'une conversation.

Corrige uniquement : coquilles, mots tronqués, accords, ponctuation
manquante, majuscules. Découpe en phrases lisibles si la ponctuation
manque.

N'AJOUTE RIEN. Ne supprime rien. Ne reformule pas. Ne rends pas le
propos plus élégant, plus court ou plus professionnel. Les hésitations
et les répétitions font partie de ce qui a été dit : garde-les. C'est le
compte rendu d'une réunion réelle, pas un texte à publier.

Réponds en JSON : {"blocs": [{"bloc": <numéro>, "texte": "<texte corrigé>"}]}
N'inclus que les blocs réellement modifiés."""


def corriger_attribution(blocs: list[dict], noms: dict, api_key: str,
                         modele: str = MODELE_DEFAUT, note=None) -> list[dict]:
    """Corrections d'attribution proposées, sans rien appliquer."""
    connus = sorted({_nom(b, noms) for b in blocs})
    vers_id = {_nom(b, noms): b["speaker"] for b in blocs}
    corrections: list[dict] = []

    for contexte, debut, fin in _fenetres(len(blocs)):
        lignes = []
        for i in range(contexte, fin):
            marque = "  " if i < debut else "→ "
            lignes.append(f"{marque}[{i}] {_nom(blocs[i], noms)} : {blocs[i]['text']}")
        requete = (f"Personnes présentes : {', '.join(connus)}\n\n"
                   "Les lignes marquées → sont à examiner ; les autres sont là "
                   "pour le contexte et ne doivent pas être corrigées.\n\n"
                   + "\n".join(lignes))
        try:
            brut = _appeler(api_key, modele, SYSTEME_ATTRIBUTION, requete)
            proposees = json.loads(brut).get("corrections", [])
        except Exception as exc:  # noqa: BLE001
            if _est_quota(exc):
                raise QuotaError(
                    "Quota de jetons épuisé chez Groq pour ce modèle"
                    + (f" (réessayer dans {_delai(exc)})" if _delai(exc) else "")
                    + ". Choisir un autre modèle : chaque modèle a son propre "
                    "quota quotidien.") from exc
            if note:
                note(f"relecture : fenêtre {debut}-{fin} ignorée ({exc})")
            continue

        for c in proposees:
            index = c.get("bloc")
            if not isinstance(index, int) or not debut <= index < fin:
                continue
            if "locuteur" in c:
                cible = str(c["locuteur"]).strip()
                # Un nom inventé ne vaut rien : on n'accepte que les personnes
                # déjà identifiées dans l'enregistrement.
                if cible in connus and cible != _nom(blocs[index], noms):
                    # On range aussi l'identifiant technique. Se contenter du
                    # nom affiché obligeait à le retraduire au moment
                    # d'appliquer, et cette traduction échouait quand les voix
                    # n'étaient pas nommées : le bloc héritait alors du libellé
                    # « Voix 01 » en guise d'identifiant, que l'interface ne
                    # reconnaissait plus et affichait « Voix ? ».
                    corrections.append({"type": "locuteur", "bloc": index,
                                        "avant": _nom(blocs[index], noms),
                                        "apres": cible,
                                        "apres_id": vers_id.get(cible, "")})
            elif "deplacer" in c:
                try:
                    n = int(c["deplacer"])
                except (TypeError, ValueError):
                    continue
                voisin = index - 1 if n > 0 else index + 1
                disponibles = len(blocs[index]["words"])
                if n == 0 or abs(n) >= disponibles or not 0 <= voisin < len(blocs):
                    continue
                if blocs[voisin]["speaker"] == blocs[index]["speaker"]:
                    continue
                corrections.append({"type": "frontiere", "bloc": index, "mots": n})
        if note:
            note(f"relecture de l'attribution : {fin}/{len(blocs)} blocs")
    return corrections


def corriger_texte(blocs: list[dict], api_key: str, modele: str = MODELE_DEFAUT,
                   note=None) -> list[dict]:
    """Corrections de texte proposées, filtrées sur leur fidélité."""
    corrections: list[dict] = []
    refusees = 0

    for _, debut, fin in _fenetres(len(blocs)):
        lignes = [f"[{i}] {blocs[i]['text']}" for i in range(debut, fin)]
        try:
            brut = _appeler(api_key, modele, SYSTEME_TEXTE, "\n".join(lignes))
            proposees = json.loads(brut).get("blocs", [])
        except Exception as exc:  # noqa: BLE001
            if _est_quota(exc):
                raise QuotaError(
                    "Quota de jetons épuisé chez Groq pour ce modèle"
                    + (f" (réessayer dans {_delai(exc)})" if _delai(exc) else "")
                    + ". Choisir un autre modèle : chaque modèle a son propre "
                    "quota quotidien.") from exc
            if note:
                note(f"relecture du texte : fenêtre {debut}-{fin} ignorée ({exc})")
            continue

        for c in proposees:
            index, texte = c.get("bloc"), c.get("texte")
            if not isinstance(index, int) or not debut <= index < fin:
                continue
            if not isinstance(texte, str) or not texte.strip():
                continue
            origine = blocs[index]["text"]
            if texte.strip() == origine.strip():
                continue
            # Le garde-fou : au-delà d'un certain écart, ce n'est plus une
            # correction mais une réécriture. On la jette sans la montrer.
            if SequenceMatcher(None, origine, texte).ratio() < FIDELITE_MIN:
                refusees += 1
                continue
            corrections.append({"type": "texte", "bloc": index,
                                "avant": origine, "apres": texte.strip()})
        if note:
            note(f"relecture du texte : {fin}/{len(blocs)} blocs")

    if refusees and note:
        note(f"{refusees} réécriture(s) trop libre(s) écartée(s)")
    return corrections


def resumer(blocs: list[dict], noms: dict, api_key: str,
            forme: str = "compte_rendu", modele: str = MODELE_DEFAUT) -> str:
    """Un résumé de la conversation, dans la forme demandée."""
    if forme not in RESUMES:
        forme = "compte_rendu"
    _, consigne = RESUMES[forme]
    corps = "\n".join(f"{_nom(b, noms)} : {b['text']}" for b in blocs)
    # Whisper produit beaucoup de texte ; on borne l'envoi plutôt que de
    # laisser l'appel échouer sur la limite du modèle.
    if len(corps) > 180_000:
        corps = corps[:180_000] + "\n[…suite tronquée…]"
    systeme = (
        "Tu rédiges à partir de la transcription d'une réunion réelle. "
        "Tu produis " + consigne + ". "
        "N'invente aucune décision, aucun chiffre, aucun engagement qui ne "
        "figure pas dans la transcription. Si un point reste ambigu dans "
        "l'échange, dis qu'il est resté ambigu plutôt que de le trancher. "
        "Écris en français, dans la langue de la réunion."
    )
    try:
        return _appeler(api_key, modele, systeme, corps, json_attendu=False).strip()
    except Exception as exc:  # noqa: BLE001
        if _est_quota(exc):
            raise QuotaError(
                "Quota de jetons épuisé chez Groq pour ce modèle"
                + (f" (réessayer dans {_delai(exc)})" if _delai(exc) else "")
                + ". Choisir un autre modèle : chaque modèle a son propre "
                "quota quotidien.") from exc
        raise


def appliquer(blocs: list[dict], corrections: list[dict], noms: dict) -> list[dict]:
    """Applique les corrections sur une copie, l'original restant intact.

    L'ordre compte : les déplacements de frontière changent le contenu des
    blocs, les réattributions non. On déplace d'abord, en partant de la fin
    pour que les indices restent valables."""
    sortie = [dict(b, words=list(b["words"])) for b in blocs]

    for c in sorted((c for c in corrections if c["type"] == "frontiere"),
                    key=lambda c: -c["bloc"]):
        i, n = c["bloc"], c["mots"]
        if n > 0:
            deplaces = sortie[i]["words"][:n]
            sortie[i]["words"] = sortie[i]["words"][n:]
            sortie[i - 1]["words"].extend(deplaces)
        else:
            deplaces = sortie[i]["words"][n:]
            sortie[i]["words"] = sortie[i]["words"][:n]
            sortie[i + 1]["words"] = deplaces + sortie[i + 1]["words"]

    # Tout ce qui permet de retrouver un identifiant de voix à partir d'un
    # nom affiché : le nom donné par l'utilisateur, et le libellé par défaut.
    vers_id = {v: k for k, v in noms.items() if v}
    vers_id.update({_nom(b, noms): b["speaker"] for b in blocs})

    for c in corrections:
        if c["type"] == "locuteur":
            cible = c.get("apres_id") or vers_id.get(c["apres"])
            if not cible:
                continue      # nom intraduisible : on préfère ne rien changer
            sortie[c["bloc"]]["speaker"] = cible
        elif c["type"] == "texte":
            sortie[c["bloc"]]["texte_corrige"] = c["apres"]

    from .pipeline import join_words
    for bloc in sortie:
        if bloc["words"]:
            bloc["start"] = bloc["words"][0]["start"]
            bloc["end"] = bloc["words"][-1]["end"]
            bloc["text"] = bloc.pop("texte_corrige", None) or join_words(bloc["words"])
    return [b for b in sortie if b["words"] and b["text"]]
