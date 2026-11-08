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
import time
from difflib import SequenceMatcher

from . import fournisseurs
from .fournisseurs import (MODELES, MODELE_DEFAUT, MODELE_GRATUIT,  # noqa: F401
                           QuotaError, LimiteMinute, Indisponible,
                           FournisseurError)

# Modèles à poids ouverts servis par Groq. La clé est déjà là, il n'y a
# donc ni compte à créer ni gigaoctet à télécharger.

# Fenêtres larges à dessein : la consigne système est renvoyée à chaque
# appel, donc doubler la fenêtre divise par deux ce qu'on repaie. Sur un
# transcript de 600 blocs, passer de 14 à 30 fait tomber le nombre
# d'appels de 44 à 21. Le quota gratuit de Groq est de 200 000 jetons par
# jour et par modèle : une relecture complète en consommait presque tout.
# Deux tailles, parce que les deux passes n'ont pas le même coût de
# réponse. L'attribution ne renvoie que des numéros : une large fenêtre
# est gratuite en sortie et économise la consigne système. La correction
# de texte, elle, renvoie chaque bloc réécrit en entier — sur trente
# blocs la réponse dépasse ce que le modèle peut produire d'un coup,
# le JSON revient tronqué et l'appel entier est perdu.
# Dix blocs : mesuré comme le point où le modèle juge encore chaque bloc
# de façon stable. Au-delà, il commence à rendre des listes incomplètes.
FENETRE_ATTRIBUTION = 10
FENETRE_TEXTE = 10
FENETRE = FENETRE_ATTRIBUTION   # compatibilité
RECOUVREMENT = 2      # blocs de contexte repris de la fenêtre précédente
# Groq applique deux limites de nature différente : un seau par minute
# (8000 jetons) et un plafond par jour (200 000 sur le forfait gratuit).
# Demander 8000 jetons de réponse, c'était réclamer le seau entier d'un
# coup. La moitié suffit largement pour dix blocs réécrits.
# Deux plafonds, parce que les deux passes ne rendent pas la même chose :
# l'attribution quelques numéros, la correction dix blocs réécrits. Le
# plafond demandé est réservé sur le seau de la minute, qu'on le consomme
# ou non : demander large, c'est se limiter à deux appels par minute.
JETONS_ATTRIBUTION = 1500
JETONS_TEXTE = 3000
JETONS_REPONSE = JETONS_TEXTE   # compatibilité
# Un quota par minute se rétablit sur une frontière de minute, pas au
# bout du délai poliment suggéré par le serveur : patienter six secondes
# ne faisait que consommer les tentatives sans rien changer. On attend
# donc au moins le quart d'une minute, et on insiste davantage.
ATTENTE_MIN = 20.0
ATTENTE_MAX = 75.0
REESSAIS = 5
CARACTERES_PAR_JETON = 3.4   # approximation pour du français
FIDELITE_MIN = 0.72   # en dessous, la « correction » est une réécriture

# Les formes de restitution.
#
# Un parti pris, né d'une mesure : la séparation des voix sur un micro
# unique dans une salle se trompe souvent, et aucun modèle de langue ne
# la répare de façon fiable — essayé, mesuré, les corrections proposées
# dégradaient le découpage au lieu de l'améliorer. Plutôt que d'affirmer
# qui a dit quoi en se trompant, ces formes restituent ce qui a été dit,
# décidé et confié, et n'attribuent une parole que lorsque la
# conversation elle-même la désigne sans ambiguïté.
#
# Un compte rendu qui écrit « Annie s'occupe des locaux » alors que
# c'était quelqu'un d'autre est plus nuisible qu'un compte rendu qui ne
# nomme personne : l'erreur y est invisible et se propage.
PRUDENCE_ATTRIBUTION = """
La répartition des voix dans ce transcript est approximative : elle vient
d'un logiciel qui compare des empreintes vocales et se trompe
régulièrement, surtout aux changements de tour.

N'attribue donc une parole, une décision ou une tâche à une personne que
lorsque la conversation la désigne sans ambiguïté — quelqu'un se nomme,
on l'interpelle, ou le propos ne peut venir que d'elle. Dans tous les
autres cas, écris ce qui a été dit sans dire qui. « Il a été convenu
que… », « un membre propose… » valent mieux qu'un nom inventé.

Les étiquettes « Voix 1 », « Voix 2 » et autres ne sont pas des noms :
ce sont des numéros posés par la machine. Elles ne doivent jamais
apparaître dans ce que tu écris. Si une tâche revient à quelqu'un que la
conversation ne nomme pas, écris que la personne n'a pas été désignée.

En revanche, un nom prononcé pendant la réunion — « c'est Dominique qui
s'en charge », « Annie, tu peux… » — est une information fiable, bien
plus que la répartition des voix : sers-t'en sans hésiter.

Une réunion se corrige en parlant. « C'était le 24 ? — Non, le 17 » : la
date retenue est la seconde. Chaque fois qu'un chiffre, une date, un
montant ou un nom est repris, contredit ou rectifié dans l'échange,
retiens la dernière version, jamais la première. C'est l'erreur la plus
coûteuse dans un compte rendu, parce qu'elle est invisible à la
relecture : la date fausse y a l'air aussi sûre que les autres.

N'ajoute aucune précision qui ne soit pas dans l'échange. Si une adresse,
un montant ou un intitulé n'est pas prononcé, n'en invente pas un
plausible : décris ce qui a été décidé sans le détail manquant.

Ne signale pas cette incertitude dans le texte : contente-toi de ne pas
affirmer ce que tu ne sais pas."""

RESUMES = {
    "compte_rendu": {
        "nom": "Compte rendu",
        "consigne": "un compte rendu structuré : contexte, points abordés, "
                    "décisions prises, points laissés en suspens",
        "apercu": """## Contexte
Réunion du conseil, 83 minutes, trois personnes présentes.

## Points abordés
**Gestion des locaux.** La question d'un comité chargé d'accepter ou de
refuser les activités selon leur nature. Les propositions reçues
seraient réévaluées avant d'être accordées.

**Transition.** Développer des lieux de rencontre où les gens peuvent
élaborer et se mobiliser ensemble.

## Décisions
- Un comité sera constitué, réunissant des citoyens, des membres du CA
  et de l'équipe.

## En suspens
- Les modalités d'accès aux locaux en soirée.""",
    },
    "actions": {
        "nom": "Décisions et suites à donner",
        "consigne": "la liste des décisions arrêtées et des actions à mener, "
                    "avec l'échéance et la personne chargée quand la "
                    "conversation les désigne clairement",
        "apercu": """## Décisions
1. Constitution d'un comité d'évaluation des activités.
2. Les propositions seront réévaluées avant d'être accordées.

## À faire
| Quoi | Qui | Quand |
|---|---|---|
| Réunir le comité | — | non précisé |
| Définir les règles d'accès aux locaux | Dominique | avant l'été |

Les tirets marquent ce que la réunion n'a pas attribué.""",
    },
    "bref": {
        "nom": "Résumé bref",
        "consigne": "un résumé de dix lignes au plus, en prose continue, "
                    "sans titres ni listes",
        "apercu": """La réunion a porté sur l'usage des locaux et sur la mise en place
d'un comité chargé d'évaluer les activités proposées. L'idée retenue
est de permettre à chaque personne de gérer son propre secteur, dans
le cadre plus large de la transition : créer des lieux où les gens
peuvent se rencontrer, élaborer et se mobiliser ensemble. Les
propositions reçues seront réévaluées avant d'être accordées. Les
modalités d'accès en soirée restent à préciser.""",
    },
    "themes": {
        "nom": "Par thème",
        "consigne": "une synthèse organisée par thème plutôt que "
                    "chronologiquement, chaque thème regroupant tout ce qui "
                    "s'est dit à son sujet même à des moments éloignés",
        "apercu": """## Locaux
Accès en soirée, remise des clés, usage autonome par les groupes.
Comparaison avec le fonctionnement de Milton Park, où les groupes
viennent chercher la clé eux-mêmes.

## Comité et gouvernance
Composition : citoyens, membres du CA, équipe. Rôle : accepter ou
refuser les activités selon leur nature.

## Transition
Développer des lieux de rencontre et de mobilisation.""",
    },
    "verbatim": {
        "nom": "Transcript lisible",
        "consigne": "le transcript complet rendu lisible : ponctuation, "
                    "paragraphes, hésitations et répétitions retirées quand "
                    "elles n'apportent rien. Ne résume pas, ne raccourcis "
                    "pas, ne reformule pas le propos — garde tout ce qui a "
                    "été dit, dans l'ordre",
        "apercu": """**[06:06]** Il y a deux possibilités. Il va y avoir, c'est sûr,
d'abord un comité. Ça entre dans le cadre de la transition :
développer des lieux où les gens peuvent se rencontrer, élaborer,
se mobiliser ensemble.

**[06:14]** Un comité réunissant des citoyens, des membres du CA et
de l'équipe, qui va accepter ou non les activités selon leur nature.
Vous allez recevoir des propositions ; elles seront réévaluées avant
d'être accordées.

**[06:30]** Exactement. Et il y aura des façons pour eux d'utiliser
les locaux eux-mêmes.""",
    },
    "questions": {
        "nom": "Questions soulevées",
        "consigne": "les questions posées pendant la réunion et restées sans "
                    "réponse, ou dont la réponse a été remise à plus tard, "
                    "avec ce qui a été dit autour de chacune",
        "apercu": """## Restées sans réponse
**Qui décide en dernier ressort de refuser une activité ?** Le comité
est évoqué, sa composition aussi, mais pas la règle de décision.

**Les locaux sont-ils accessibles en soirée ?** Évoqué deux fois, sans
conclusion.

## Réponse remise à plus tard
**Comment se fait la remise des clés ?** Renvoyé au modèle de Milton
Park, à préciser.""",
    },
    "reperes": {
        "nom": "Dates et chiffres à vérifier",
        "consigne": "",   # aucun modèle n'intervient
        "mecanique": True,
        "apercu": """Toutes les dates, heures et sommes prononcées, dans l'ordre,
avec la phrase qui les entoure. Aucun modèle n'intervient : c'est
relevé dans le texte, donc rien ne peut être inventé ni oublié.

**04:12** · 4 novembre
  …je rencontre des impôts pour demain le 4 novembre à 11h. Puis le
  reste de la semaine…

**1:52:30** · 24 novembre
  …Fait qu'on a deux semaines. C'est-à-dire le 24 novembre, on se fait
  une rencontre ? C'était le 24 ? Non, le 17…

Une réunion se corrige en parlant. Les deux mentions figurent ici dans
l'ordre : la lecture tranche en une seconde.""",
    },
}
RESUME_DEFAUT = "compte_rendu"


class RelectureError(RuntimeError):
    pass


# QuotaError, LimiteMinute et FournisseurError viennent de fournisseurs :
# les redéfinir ici créait deux classes du même nom, et un isinstance qui
# répondait faux selon le module d'où venait l'exception.
RelectureError = FournisseurError


class Annulee(Exception):
    """L'arrêt a été demandé pendant la relecture.

    Une exception, et non une valeur de retour : la relecture est une
    pile de boucles imbriquées — fenêtres, essais, attentes de quota — et
    un code de retour devrait être relu et propagé à chaque étage. Il
    suffit d'en oublier un pour que l'arrêt soit sans effet, ce qui est
    exactement la panne qu'on corrige ici."""


def _halte(stop) -> None:
    """Lève si l'arrêt est demandé. Appelée partout où l'on peut rendre
    la main sans laisser de travail à moitié fait."""
    if stop and stop():
        raise Annulee()


def _dire(note, message: str, remplacer: bool = False) -> None:
    """Écrit une ligne au journal, en remplaçant la précédente si demandé.

    Tolérant sur la signature : les appelants anciens et les essais
    passent une fonction à un seul argument. Mieux vaut perdre le
    remplacement que lever une TypeError au milieu d'une relecture."""
    if not note:
        return
    try:
        note(message, remplacer)
    except TypeError:
        note(message)


def _patienter(secondes: float, stop=None, note=None) -> None:
    """Attend, mais en restant à l'écoute, et en le disant.

    L'attente de quota dure de vingt à soixante-quinze secondes. Dormir
    d'un bloc rendait « Arrêter » muet pendant tout ce temps — et c'est
    précisément le moment où l'on veut arrêter, puisque c'est le moment
    où il ne se passe rien.

    Le décompte sert au même constat vu de l'autre côté : une ligne figée
    pendant une minute ne se distingue pas d'un programme planté."""
    fin = time.time() + secondes
    dernier = -1
    while time.time() < fin:
        _halte(stop)
        reste = int(fin - time.time()) + 1
        if reste != dernier:
            dernier = reste
            _dire(note, f"limite par minute atteinte, reprise dans {reste} s", True)
        time.sleep(min(0.25, max(0.0, fin - time.time())))
    _halte(stop)


def _genre_limite_inutilise(exc: Exception) -> str:
    """« jour », « minute » ou « » — la distinction commande la conduite.

    Une limite par minute se franchit en patientant quelques secondes :
    c'est un ralentisseur. Une limite par jour ne se franchit pas : rien
    ne sert de réessayer, et continuer fenêtre après fenêtre ne fait que
    rejouer le même refus. Les traiter pareil, c'était abandonner une
    relecture entière pour une pause de trente secondes."""
    texte = str(exc)
    if "rate_limit" not in texte and "429" not in texte:
        return ""
    if "per day" in texte or "TPD" in texte or "RPD" in texte:
        return "jour"
    if "per minute" in texte or "TPM" in texte or "RPM" in texte:
        return "minute"
    return "jour"      # dans le doute, ne pas s'acharner


def _est_quota(exc: Exception) -> bool:
    return isinstance(exc, QuotaError)


def _secondes(exc: Exception) -> float:
    import re as _re
    t = _re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", str(exc))
    if not t:
        return 5.0
    h, m, sec = t.group(1), t.group(2), t.group(3)
    return int(h or 0) * 3600 + int(m or 0) * 60 + float(sec)


def modeles_disponibles(api_key: str) -> list[str]:
    """Quels modèles répondent encore, vérifié plutôt que supposé.

    Le message d'erreur conseillait d'en changer sans savoir si un autre
    était libre. Quand les trois sont épuisés, ce conseil fait perdre du
    temps ; autant poser la question."""
    libres = []
    for cle, m in MODELES.items():
        try:
            _client(api_key).chat.completions.create(
                model=m["id"], messages=[{"role": "user", "content": "ok"}],
                max_completion_tokens=1)
            libres.append(m["nom"])
        except Exception:  # noqa: BLE001
            continue
    return libres


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
    total = 0
    if attribution:
        # fenêtre de dix, et un verdict rendu pour chaque bloc
        fen = max(1, -(-len(blocs) // FENETRE_ATTRIBUTION))
        total += 500 * fen + corps / CARACTERES_PAR_JETON + len(blocs) * 12
    if texte:
        fen = max(1, -(-len(blocs) // FENETRE_TEXTE))
        total += 300 * fen + corps / CARACTERES_PAR_JETON * (1 + RECOUVREMENT / FENETRE_TEXTE)
        total += corps / CARACTERES_PAR_JETON * 0.5
    return int(total)


def _client(api_key: str):
    try:
        from groq import Groq
    except ImportError as exc:
        raise RelectureError("Le paquet groq n'est pas installé.") from exc
    return Groq(api_key=api_key)


def _appeler(api_key: str, modele: str, systeme: str, requete: str,
             json_attendu: bool = True, note=None, plafond: int = 0,
             schema: dict | None = None, stop=None) -> str:
    """Un appel, en patientant si la limite est celle de la minute."""
    for essai in range(REESSAIS):
        _halte(stop)
        try:
            return fournisseurs.appeler(api_key, modele, systeme, requete,
                                        schema=schema, note=note,
                                        plafond=plafond)
        except (LimiteMinute, Indisponible) as pause:
            if essai == REESSAIS - 1:
                raise
            delai = min(max(pause.secondes + 1.0, ATTENTE_MIN), ATTENTE_MAX)
            # Le décompte est écrit par _patienter, seconde par seconde,
            # en remplaçant sa propre ligne.
            _patienter(delai, stop, note)
    raise FournisseurError("Appel impossible.")


def _decoupage(blocs: list[dict], modele: str, note=None):
    """Un seul appel quand le transcript tient, sinon des fenêtres.

    C'est le seul endroit où la taille du modèle change la stratégie, et
    elle la change du tout au tout. Contre un million de jetons, une
    réunion de quatre-vingts minutes part entière et le modèle juge
    l'attribution en voyant la conversation complète : qui répond à qui,
    qui reprend la parole, qui approuve. Les fenêtres de dix blocs ne
    sont pas une précaution, c'est le prix d'un petit contexte — chacune
    juge à l'aveugle, sans savoir ce qui s'est dit deux minutes plus
    tôt."""
    jetons = int(sum(len(b["text"]) for b in blocs) / CARACTERES_PAR_JETON) + 800
    if fournisseurs.tient_en_un_appel(modele, jetons):
        if note:
            note(f"transcript entier en un seul appel ({jetons} jetons)")
        return [(0, 0, len(blocs))]
    return list(_fenetres(len(blocs), FENETRE_ATTRIBUTION))


def _entete(contexte: str) -> str:
    """Ce que l'utilisateur sait et que la transcription ne dit pas.

    Les noms propres, les sigles et les rôles sont ce que la machine rate
    le plus : « IMER » et « AEPP » n'existent dans aucun dictionnaire, et
    savoir qui préside aide à décider qui répond. On le place en tête de
    la requête plutôt que dans la consigne système, pour qu'il reste du
    contexte et non une instruction."""
    contexte = (contexte or "").strip()
    if not contexte:
        return ""
    return ("Contexte fourni par la personne qui a assisté à la réunion. "
            "Il sert à reconnaître les noms propres, les sigles et les rôles ; "
            "il ne dit pas ce qu'il faut corriger :\n"
            f"{contexte[:4000]}\n\n")


def _nom(bloc: dict, noms: dict) -> str:
    return noms.get(bloc["speaker"]) or bloc["speaker"].replace("SPEAKER_", "Voix ")


def _fenetres(total: int, taille: int = FENETRE_ATTRIBUTION):
    """Découpe en fenêtres qui se chevauchent.

    Le recouvrement n'est pas du luxe : une frontière mal placée se juge
    sur ce qui la précède, et une fenêtre qui commencerait pile dessus ne
    verrait que la moitié du problème."""
    debut = 0
    while debut < total:
        fin = min(debut + taille, total)
        yield max(0, debut - RECOUVREMENT), debut, fin
        debut = fin


def _tronque(exc: Exception) -> bool:
    """Réponse coupée avant la fin du JSON, faute de place."""
    texte = str(exc)
    return "json_validate_failed" in texte or "Failed to validate JSON" in texte


# Le modèle doit se prononcer sur CHAQUE bloc, et pas seulement signaler
# les erreurs. Demander « la liste des erreurs » rend la réponse vide la
# moins coûteuse, et le modèle la choisissait souvent : sur cinq fenêtres
# identiques, trois revenaient vides et deux trouvaient trois ou quatre
# corrections, à température nulle. En exigeant un verdict par bloc, la
# réponse vide devient invalide et détectable, et cinq essais identiques
# rendent exactement le même résultat.
SYSTEME_ATTRIBUTION = """Tu relis la transcription d'une conversation réelle.

Un logiciel a réparti les phrases entre les personnes en comparant les
voix. Il se trompe de deux façons : il coupe au milieu d'une proposition
et donne la fin à quelqu'un d'autre, ou il rate un changement de personne
et colle une réponse au locuteur précédent.

Tu juges sur le sens et la syntaxe, jamais sur le son. Une proposition
grammaticale appartient à une seule personne. Une question et sa réponse
appartiennent à deux personnes différentes. Une approbation (« exactement »,
« tout à fait », « oui ») vient de quelqu'un d'autre que celui qui vient
de parler.

Indice mécanique : quand un bloc se termine sans ponctuation forte et que
le suivant commence par une minuscule, la phrase a été coupée en deux et
la coupure est presque toujours mal placée. Regarde ces enchaînements en
premier.

Pour CHAQUE bloc numéroté, indique qui parle. Réponds en JSON :
{"blocs": [{"bloc": 0, "locuteur": "<nom exact>"}, ...]}

Un bloc peut aussi porter "deplacer": n, pour ramener ses n premiers mots
au bloc précédent (n positif) ou pousser ses |n| derniers mots au bloc
suivant (n négatif), quand la coupure tombe au milieu d'une proposition.

Réponds pour tous les blocs, sans exception, dans l'ordre. N'invente aucun
nom : n'emploie que ceux de la liste fournie."""

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


def _plafond_attribution(combien: int) -> int:
    """Un verdict par bloc, donc une réponse qui grandit avec le transcript.

    Mille cinq cents jetons suffisaient pour dix blocs et pas du tout
    pour six cents. Trop peu tronque la réponse ; trop réserve du quota
    pour rien."""
    return max(1500, min(32_000, 500 + combien * 28))


def _demander_attribution(blocs, noms, connus, debut, fin, api_key, modele,
                          contexte, note, stop=None):
    """Le verdict du modèle sur une fenêtre, vérifié puis traduit.

    Rend la liste brute des jugements. La couverture est contrôlée par
    l'appelant : une réponse qui ne parle que de trois blocs sur dix n'est
    pas une fenêtre sans erreur, c'est une fenêtre mal lue."""
    lignes = [f"[{i}] {_nom(blocs[i], noms)} : {blocs[i]['text']}"
              for i in range(debut, fin)]
    requete = (_entete(contexte)
               + f"Personnes présentes : {', '.join(connus)}\n\n"
               + "\n".join(lignes))
    brut = _appeler(api_key, modele, SYSTEME_ATTRIBUTION, requete, note=note,
                    plafond=_plafond_attribution(fin - debut),
                    schema=fournisseurs.SCHEMA_ATTRIBUTION, stop=stop)
    return fournisseurs.lire_json(brut).get("blocs", [])


def corriger_attribution(blocs: list[dict], noms: dict, api_key: str,
                         modele: str = MODELE_DEFAUT, note=None,
                         contexte: str = "", stop=None) -> list[dict]:
    """Corrections d'attribution proposées, sans rien appliquer."""
    connus = sorted({_nom(b, noms) for b in blocs})
    vers_id = {_nom(b, noms): b["speaker"] for b in blocs}
    corrections: list[dict] = []
    _dire(note, f"attribution : {len(blocs)} blocs, "
                f"{len(connus)} voix à départager")

    tentees = perdues = 0
    for _, debut, fin in _decoupage(blocs, modele, note):
        _halte(stop)
        tentees += 1
        try:
            verdicts = _demander_attribution(blocs, noms, connus, debut, fin,
                                             api_key, modele, contexte, note,
                                             stop)
        except Annulee:
            raise                       # jamais confondu avec une panne
        except Exception as exc:  # noqa: BLE001
            if _est_quota(exc):
                raise
            perdues += 1
            if note:
                note(f"relecture : fenêtre {debut}-{fin} ignorée ({exc})")
            continue

        vus = {v.get("bloc") for v in verdicts if isinstance(v.get("bloc"), int)}
        attendus = set(range(debut, fin))
        if len(vus & attendus) < len(attendus) * 0.7:
            # Une fenêtre à moitié lue n'est pas une fenêtre sans erreur.
            perdues += 1
            if note:
                note(f"fenêtre {debut}-{fin} : {len(vus & attendus)}/{len(attendus)} "
                     "blocs jugés, réponse écartée")
            continue

        for v in verdicts:
            index = v.get("bloc")
            if not isinstance(index, int) or index not in attendus:
                continue
            cible = str(v.get("locuteur") or "").strip()
            actuel = _nom(blocs[index], noms)
            if cible and cible in connus and cible != actuel:
                corrections.append({"type": "locuteur", "bloc": index,
                                    "avant": actuel, "apres": cible,
                                    "apres_id": vers_id.get(cible, "")})
            if v.get("deplacer"):
                try:
                    n = int(v["deplacer"])
                except (TypeError, ValueError):
                    continue
                voisin = index - 1 if n > 0 else index + 1
                if (n == 0 or abs(n) >= len(blocs[index]["words"])
                        or not 0 <= voisin < len(blocs)):
                    continue
                if blocs[voisin]["speaker"] == blocs[index]["speaker"]:
                    continue
                corrections.append({"type": "frontiere", "bloc": index, "mots": n})
        if note:
            note(f"attribution : {fin}/{len(blocs)} blocs, "
                 f"{len(corrections)} correction(s) trouvée(s)")

    # Hors de la boucle : une fenêtre perdue y sort par `continue` et
    # sauterait le contrôle. Avec un seul grand appel, perdre cette
    # fenêtre c'est perdre tout le transcript, et rendre une liste vide
    # ferait passer un échec complet pour une relecture sans rien à
    # corriger — la panne la plus trompeuse qui soit.
    if tentees and perdues == tentees:
        raise FournisseurError(
            "La relecture n'a abouti sur aucune partie du transcript "
            f"({perdues} tentative(s) perdue(s)). Rien n'a été corrigé. "
            "Réessayer, ou choisir un autre modèle dans la liste.")
    return corrections


def _demander_texte(blocs, debut, fin, api_key, modele, contexte, note,
                    profondeur: int = 0, stop=None):
    """Une fenêtre de correction, coupée en deux si la réponse déborde.

    La passe de texte renvoie chaque bloc réécrit en entier : sur une
    fenêtre trop large, le modèle s'arrête au milieu du JSON et l'appel
    entier est perdu. Plutôt que d'abandonner la fenêtre, on la scinde et
    on redemande. Deux niveaux suffisent à ramener dix blocs à deux ou
    trois ; au-delà, l'échec vient d'autre chose et remonte."""
    lignes = [f"[{i}] {blocs[i]['text']}" for i in range(debut, fin)]
    try:
        brut = _appeler(api_key, modele, SYSTEME_TEXTE,
                        _entete(contexte) + "\n".join(lignes), note=note,
                        plafond=JETONS_TEXTE, schema=fournisseurs.SCHEMA_TEXTE,
                        stop=stop)
        return fournisseurs.lire_json(brut).get("blocs", [])
    except Annulee:
        raise          # ne jamais prendre un arrêt pour une réponse tronquée
    except Exception as exc:  # noqa: BLE001
        if _est_quota(exc):
            raise
        coupable = _tronque(exc) or isinstance(exc, json.JSONDecodeError)
        if coupable and profondeur < 2 and fin - debut > 1:
            milieu = (debut + fin) // 2
            if note:
                note(f"réponse trop longue, fenêtre {debut}-{fin} coupée en deux")
            return (_demander_texte(blocs, debut, milieu, api_key, modele,
                                    contexte, note, profondeur + 1, stop)
                    + _demander_texte(blocs, milieu, fin, api_key, modele,
                                      contexte, note, profondeur + 1, stop))
        raise


def corriger_texte(blocs: list[dict], api_key: str, modele: str = MODELE_DEFAUT,
                   note=None, contexte: str = "", stop=None) -> list[dict]:
    """Corrections de texte proposées, filtrées sur leur fidélité."""
    corrections: list[dict] = []
    refusees = 0
    _dire(note, f"texte : {len(blocs)} blocs à relire")

    for _, debut, fin in _fenetres(len(blocs), FENETRE_TEXTE):
        _halte(stop)
        try:
            proposees = _demander_texte(blocs, debut, fin, api_key, modele,
                                        contexte, note, stop=stop)
        except (QuotaError, Annulee):
            # Annulee AVANT le filet à tout attraper. Sans cette ligne,
            # l'arrêt est pris pour une fenêtre en panne, noté comme tel
            # et la boucle enchaîne : le bouton ne fait rien, et rien ne
            # dit pourquoi. C'est exactement la panne qu'on corrige.
            raise
        except Exception as exc:  # noqa: BLE001
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
            note(f"texte : {fin}/{len(blocs)} blocs, "
                 f"{len(corrections)} correction(s) trouvée(s)")

    if refusees and note:
        note(f"{refusees} réécriture(s) trop libre(s) écartée(s)")
    return corrections


MOIS = ("janvier février mars avril mai juin juillet août septembre "
        "octobre novembre décembre").split()

# Repères chiffrés : dates, heures, montants. Rien d'autre ne mérite
# d'être extrait mécaniquement, et rien d'autre n'est aussi coûteux à
# rater dans un compte rendu.
_MOTIFS = [
    (r"\b(\d{1,2}|1er)\s+(" + "|".join(MOIS) + r")\b", "date"),
    (r"\b(\d{1,2})\s*h\s*(\d{2})?\b", "heure"),
    (r"\b(\d+(?:[,.]\d+)?)\s*(?:\$|dollars?|piastres?)\b", "montant"),
    (r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b", "jour"),
    # « Non, le 17 » : une correction de date se dit sans répéter le mois.
    # C'est justement la mention qu'il ne faut pas rater, puisque c'est
    # elle qui annule la précédente.
    (r"\ble\s+([12]?\d|3[01])\b(?!\s*(?:" + "|".join(MOIS) + r"))", "quantième"),
]


def _horloge(secondes: float) -> str:
    s = int(secondes)
    h, m, r = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{r:02d}" if h else f"{m:02d}:{r:02d}"


def reperes(blocs: list[dict], autour: int = 110) -> list[dict]:
    """Toutes les dates, heures et sommes prononcées, avec leur contexte.

    Extraction mécanique, sans modèle de langue — donc sans invention
    possible. C'est la réponse au seul défaut mesuré des comptes rendus :
    une réunion se corrige en parlant (« C'était le 24 ? — Non, le 17 »),
    et un modèle retient parfois la première version. Ici, les deux
    mentions apparaissent dans l'ordre, avec ce qui les entoure : la
    lecture tranche en une seconde.

    Ce n'est pas un résumé et cela ne le remplace pas ; c'est de quoi
    vérifier celui qu'on s'apprête à envoyer."""
    import re as _re

    texte = " ".join(b["text"] for b in blocs)
    # Correspondance position dans le texte -> seconde dans l'audio. On
    # suit les mots plutôt que les blocs : sans séparation des voix, un
    # transcript peut tenir en un seul bloc, et tous les repères
    # renverraient alors à 00:00.
    reperes_temps, position = [], 0
    for b in blocs:
        mots = b.get("words") or []
        if mots:
            curseur = position
            for mot in mots:
                reperes_temps.append((curseur, float(mot.get("start") or 0.0)))
                curseur += len(str(mot.get("text") or "")) + 1
        else:
            reperes_temps.append((position, float(b.get("start") or 0.0)))
        position += len(b["text"]) + 1

    import bisect
    bornes = [x[0] for x in reperes_temps]

    def quand(i: int) -> float:
        k = bisect.bisect_right(bornes, i) - 1
        return reperes_temps[k][1] if k >= 0 else 0.0

    vus, sortie = set(), []
    for motif, genre in _MOTIFS:
        for m in _re.finditer(motif, texte, _re.IGNORECASE):
            cle = (m.start() // 40, m.group(0).lower())
            if cle in vus:
                continue
            vus.add(cle)
            a = max(0, m.start() - autour)
            sortie.append({
                "genre": genre,
                "valeur": " ".join(m.group(0).split()),
                "seconde": quand(m.start()),
                "extrait": " ".join(texte[a:m.end() + autour].split()),
            })
    sortie.sort(key=lambda x: x["seconde"])
    return sortie


def resumer(blocs: list[dict], noms: dict, api_key: str,
            forme: str = "compte_rendu", modele: str = MODELE_DEFAUT,
            contexte: str = "") -> str:
    """Un résumé de la conversation, dans la forme demandée."""
    if forme not in RESUMES:
        forme = RESUME_DEFAUT
    fiche = RESUMES[forme]
    if fiche.get("mecanique"):
        # Relevé dans le texte, sans modèle : ni clé, ni quota, ni
        # invention possible. C'est la réponse au seul défaut mesuré des
        # comptes rendus — une date corrigée en cours de réunion dont la
        # première version se retrouve parfois retenue.
        lignes = ["# Dates et chiffres prononcés", "",
                  "Relevé mot à mot dans la transcription, dans l'ordre. "
                  "Quand une date est reprise ou corrigée, les deux mentions "
                  "apparaissent : la bonne est la dernière.", ""]
        for x in reperes(blocs):
            lignes.append(f"**{_horloge(x['seconde'])}** · {x['valeur']}")
            lignes.append(f"  …{x['extrait']}…")
            lignes.append("")
        return "\n".join(lignes).strip()
    corps = "\n".join(f"{_nom(b, noms)} : {b['text']}" for b in blocs)
    # Whisper produit beaucoup de texte ; on borne l'envoi plutôt que de
    # laisser l'appel échouer sur la limite du modèle.
    limite = 180_000 if fournisseurs.fiche(modele)["contexte"] > 100_000 else 60_000
    if len(corps) > limite:
        corps = corps[:limite] + "\n[…suite tronquée…]"
    systeme = (
        "Tu rédiges à partir de la transcription d'une réunion réelle. "
        "Tu produis " + fiche["consigne"] + ". "
        "N'invente aucune décision, aucun chiffre, aucun engagement qui ne "
        "figure pas dans la transcription. Si un point reste ambigu dans "
        "l'échange, dis qu'il est resté ambigu plutôt que de le trancher. "
        "Écris en français, dans la langue de la réunion."
        + PRUDENCE_ATTRIBUTION
    )
    try:
        return _appeler(api_key, modele, systeme, _entete(contexte) + corps,
                    json_attendu=False).strip()
    except Exception as exc:  # noqa: BLE001
        if _est_quota(exc):
            raise
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
