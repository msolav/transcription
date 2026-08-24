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

# Modèles à poids ouverts servis par Groq. La clé est déjà là, il n'y a
# donc ni compte à créer ni gigaoctet à télécharger.
# `effort` : ces modèles réfléchissent avant de répondre, et ce
# raisonnement est facturé sur le même plafond que la réponse. Sans le
# brider, GPT-OSS épuise les jetons alloués en réflexion et ne rend rien
# du tout — un JSON vide, refusé par le serveur. Qwen, lui, rejette le
# paramètre : il faut donc le déclarer par modèle plutôt que l'envoyer à
# tous.
MODELES = {
    "gpt-oss-120b": {"id": "openai/gpt-oss-120b", "nom": "GPT-OSS 120B",
                     "effort": True,
                     "note": "Le plus fiable des trois. À préférer pour l'attribution."},
    "gpt-oss-20b": {"id": "openai/gpt-oss-20b", "nom": "GPT-OSS 20B",
                    "effort": True,
                    "note": "Plus rapide et moins cher, un peu moins sûr."},
    "qwen3.6-27b": {"id": "qwen/qwen3.6-27b", "nom": "Qwen 3.6 27B",
                    "effort": False,
                    "note": "Autre famille : utile en deuxième avis. Plus bavard, "
                            "donc plus lent à quota égal."},
}
MODELE_DEFAUT = "gpt-oss-120b"

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
ATTENTE_MAX = 75.0    # secondes d'attente acceptées sur une limite par minute
REESSAIS = 3
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


def _genre_limite(exc: Exception) -> str:
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
    return _genre_limite(exc) == "jour"


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


def _quota_error(exc: Exception, api_key: str) -> "QuotaError":
    """Message fondé sur ce qui est vrai à cet instant, pas sur une règle.

    La version précédente affirmait que chaque modèle a son propre quota
    et invitait à en changer. C'était inutile quand les trois étaient
    épuisés, ce qui arrive vite : une relecture complète en consomme la
    moitié. On regarde donc qui répond encore avant de conseiller."""
    quand = f" Réessayer dans {_delai(exc)}." if _delai(exc) else ""
    try:
        libres = modeles_disponibles(api_key)
    except Exception:  # noqa: BLE001
        libres = []
    if libres:
        suite = (" D'autres modèles répondent encore : "
                 + ", ".join(libres) + ". Les choisir dans la liste.")
    else:
        suite = (" Les autres modèles sont épuisés aussi. Le décompte glisse "
                 "sur la journée, donc l'attente indiquée ci-dessus est la "
                 "bonne, souvent quelques minutes seulement. Pour consommer "
                 "moins, ne lancer qu'une des deux passes : l'attribution est "
                 "celle qui corrige le découpage.")
    return QuotaError("Quota quotidien de jetons épuisé chez Groq." + quand + suite)


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
             json_attendu: bool = True, note=None, plafond: int = 0) -> str:
    """Un appel, en patientant si la limite est celle de la minute."""
    for essai in range(REESSAIS):
        try:
            return _appeler_une_fois(api_key, modele, systeme, requete,
                                     json_attendu, plafond)
        except Exception as exc:  # noqa: BLE001
            if _genre_limite(exc) != "minute" or essai == REESSAIS - 1:
                raise
            pause = min(_secondes(exc) + 1.0, ATTENTE_MAX)
            if note:
                note(f"limite par minute atteinte, reprise dans {pause:.0f} s")
            time.sleep(pause)
    raise RelectureError("Appel impossible.")


def _appeler_une_fois(api_key: str, modele: str, systeme: str, requete: str,
                      json_attendu: bool = True, plafond: int = 0) -> str:
    fiche = MODELES.get(modele, MODELES[MODELE_DEFAUT])
    params = dict(
        model=fiche["id"],
        messages=[{"role": "system", "content": systeme},
                  {"role": "user", "content": requete}],
        temperature=0.0,
    )
    if fiche.get("effort"):
        params["reasoning_effort"] = "low"
    if json_attendu:
        params["response_format"] = {"type": "json_object"}
        params["max_completion_tokens"] = plafond or JETONS_TEXTE
    reponse = _client(api_key).chat.completions.create(**params)
    return reponse.choices[0].message.content or ""


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


def _demander_attribution(blocs, noms, connus, debut, fin, api_key, modele,
                          contexte, note):
    """Le verdict du modèle sur une fenêtre, vérifié puis traduit.

    Rend la liste brute des jugements. La couverture est contrôlée par
    l'appelant : une réponse qui ne parle que de trois blocs sur dix n'est
    pas une fenêtre sans erreur, c'est une fenêtre mal lue."""
    lignes = [f"[{i}] {_nom(blocs[i], noms)} : {blocs[i]['text']}"
              for i in range(debut, fin)]
    requete = (_entete(contexte)
               + f"Personnes présentes : {', '.join(connus)}\n\n"
               + "\n".join(lignes))
    brut = _appeler(api_key, modele, SYSTEME_ATTRIBUTION, requete,
                    note=note, plafond=JETONS_ATTRIBUTION)
    return json.loads(brut).get("blocs", [])


def corriger_attribution(blocs: list[dict], noms: dict, api_key: str,
                         modele: str = MODELE_DEFAUT, note=None,
                         contexte: str = "") -> list[dict]:
    """Corrections d'attribution proposées, sans rien appliquer."""
    connus = sorted({_nom(b, noms) for b in blocs})
    vers_id = {_nom(b, noms): b["speaker"] for b in blocs}
    corrections: list[dict] = []

    for _, debut, fin in _fenetres(len(blocs), FENETRE_ATTRIBUTION):
        try:
            verdicts = _demander_attribution(blocs, noms, connus, debut, fin,
                                             api_key, modele, contexte, note)
        except Exception as exc:  # noqa: BLE001
            if _est_quota(exc):
                raise _quota_error(exc, api_key) from exc
            if note:
                note(f"relecture : fenêtre {debut}-{fin} ignorée ({exc})")
            continue

        vus = {v.get("bloc") for v in verdicts if isinstance(v.get("bloc"), int)}
        attendus = set(range(debut, fin))
        if len(vus & attendus) < len(attendus) * 0.7:
            # Une fenêtre à moitié lue n'est pas une fenêtre sans erreur.
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
            note(f"relecture de l'attribution : {fin}/{len(blocs)} blocs")
    return corrections


def _demander_texte(blocs, debut, fin, api_key, modele, contexte, note,
                    profondeur: int = 0):
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
                        plafond=JETONS_TEXTE)
        return json.loads(brut).get("blocs", [])
    except Exception as exc:  # noqa: BLE001
        if _est_quota(exc):
            raise _quota_error(exc, api_key) from exc
        coupable = _tronque(exc) or isinstance(exc, json.JSONDecodeError)
        if coupable and profondeur < 2 and fin - debut > 1:
            milieu = (debut + fin) // 2
            if note:
                note(f"réponse trop longue, fenêtre {debut}-{fin} coupée en deux")
            return (_demander_texte(blocs, debut, milieu, api_key, modele,
                                    contexte, note, profondeur + 1)
                    + _demander_texte(blocs, milieu, fin, api_key, modele,
                                      contexte, note, profondeur + 1))
        raise


def corriger_texte(blocs: list[dict], api_key: str, modele: str = MODELE_DEFAUT,
                   note=None, contexte: str = "") -> list[dict]:
    """Corrections de texte proposées, filtrées sur leur fidélité."""
    corrections: list[dict] = []
    refusees = 0

    for _, debut, fin in _fenetres(len(blocs), FENETRE_TEXTE):
        try:
            proposees = _demander_texte(blocs, debut, fin, api_key, modele,
                                        contexte, note)
        except QuotaError:
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
            note(f"relecture du texte : {fin}/{len(blocs)} blocs")

    if refusees and note:
        note(f"{refusees} réécriture(s) trop libre(s) écartée(s)")
    return corrections


def resumer(blocs: list[dict], noms: dict, api_key: str,
            forme: str = "compte_rendu", modele: str = MODELE_DEFAUT,
            contexte: str = "") -> str:
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
        return _appeler(api_key, modele, systeme, _entete(contexte) + corps,
                    json_attendu=False).strip()
    except Exception as exc:  # noqa: BLE001
        if _est_quota(exc):
            raise _quota_error(exc, api_key) from exc
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
