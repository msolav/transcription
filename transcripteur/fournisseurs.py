"""
Les modèles de langue qui relisent le transcript, et comment les appeler.

Un seul point d'entrée, `appeler`, et deux familles derrière.

Ce qui sépare vraiment ces familles n'est pas leur qualité mais la
taille de ce qu'elles acceptent. Les modèles servis par Groq tiennent
dans quelques milliers de jetons de réponse : il faut leur donner le
transcript par tranches de dix blocs, et toute la fragilité du
découpage vient de là — une tranche mal lue, une réponse coupée, un
verdict rendu sur la moitié d'une fenêtre. Claude accepte un million de
jetons : une réunion de quatre-vingts minutes fait vingt mille jetons,
donc elle part en un seul appel, et le modèle voit la conversation
entière au moment de décider qui parle. Cette différence-là ne se
rattrape pas par du réglage.

D'où `contexte` sur chaque modèle : la relecture s'en sert pour choisir
entre un appel unique et un découpage, plutôt que d'imposer le découpage
à tout le monde par précaution.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------- catalogue

# `contexte` est le nombre de jetons d'entrée acceptés, `sortie` le
# plafond de réponse raisonnable pour cette tâche. `effort` signale les
# modèles qui raisonnent avant de répondre et facturent ce raisonnement
# sur le même plafond que la réponse : sans le brider, GPT-OSS épuise ses
# jetons en réflexion et ne rend rien.
MODELES = {
    # ---- Anthropic : le transcript entier en un appel
    "claude-opus-5-5": {
        "nom": "Claude Opus 5.5", "fournisseur": "anthropic",
        "id": "claude-opus-5-5", "contexte": 1_000_000, "sortie": 32_000,
        "prix": (4.0, 20.0),
        "note": "Le plus capable. Voit la réunion entière d'un coup.",
    },
    "claude-sonnet-5-5": {
        "nom": "Claude Sonnet 5.5", "fournisseur": "anthropic",
        "id": "claude-sonnet-5-5", "contexte": 1_000_000, "sortie": 32_000,
        "prix": (2.0, 10.0),
        "note": "Deux fois moins cher qu'Opus, même contexte.",
    },
    "claude-haiku-5-5": {
        "nom": "Claude Haiku 5.5", "fournisseur": "anthropic",
        "id": "claude-haiku-5-5", "contexte": 1_000_000, "sortie": 32_000,
        "prix": (0.10, 0.50),
        "note": "Quelques centimes par réunion.",
    },
    # ---- Google : gratuit, et assez large pour le transcript entier
    #
    # Les offres gratuites n'ont pas toutes la même forme, et c'est la
    # forme qui compte ici. Groq donne mille requêtes par jour mais huit
    # mille jetons par minute : généreux en requêtes, avare en jetons,
    # exactement l'inverse de ce qu'il nous faut, d'où les soixante
    # tranches. Google donne peu de requêtes par jour mais deux cent
    # cinquante mille jetons par minute, et notre travail tient en une à
    # trois requêtes énormes par réunion. Vingt requêtes par jour, c'est
    # six réunions.
    "gemini-flash": {
        "nom": "Gemini Flash (gratuit)", "fournisseur": "google",
        "id": "gemini-3.8-flash", "contexte": 1_000_000, "sortie": 32_000,
        "prix": (0.0, 0.0),
        "note": "Gratuit, et voit la réunion entière d'un coup. "
                "Peu de requêtes par jour, ce qui suffit largement.",
    },
    "gemini-flash-lite": {
        "nom": "Gemini Flash Lite (gratuit)", "fournisseur": "google",
        "id": "gemini-3.5-flash-lite", "contexte": 1_000_000, "sortie": 32_000,
        "prix": (0.0, 0.0),
        "note": "Plus de requêtes par jour, un peu moins fin.",
    },
    # ---- Groq : gratuit, mais par tranches
    "gpt-oss-120b": {
        "nom": "GPT-OSS 120B (gratuit)", "fournisseur": "groq",
        "id": "openai/gpt-oss-120b", "contexte": 8_000, "sortie": 1_500,
        "effort": True, "prix": (0.0, 0.0),
        "note": "Gratuit, par tranches de dix blocs. Quota quotidien.",
    },
    "gpt-oss-20b": {
        "nom": "GPT-OSS 20B (gratuit)", "fournisseur": "groq",
        "id": "openai/gpt-oss-20b", "contexte": 8_000, "sortie": 1_500,
        "effort": True, "prix": (0.0, 0.0),
        "note": "Gratuit et rapide, un peu moins sûr.",
    },
}
MODELE_DEFAUT = "claude-opus-5-5"
MODELE_GRATUIT = "gemini-flash"
MODELE_TRANCHES = "gpt-oss-120b"   # le repli quand seule une clé Groq existe


def modele_par_defaut(cles: dict) -> str:
    """Le meilleur modèle que les clés présentes permettent d'appeler.

    Figer Claude comme défaut rendait l'application muette au premier
    lancement de quelqu'un qui n'a pas de compte payant — l'API Anthropic
    n'a pas d'offre gratuite, il faut y déposer du crédit. Figer le modèle
    gratuit, à l'inverse, priverait d'un contexte d'un million de jetons
    ceux qui ont une clé. Le défaut suit donc ce qui est configuré, et
    l'utilisateur garde la main dans la liste."""
    if cles.get("anthropic"):
        return MODELE_DEFAUT
    if cles.get("google"):
        return MODELE_GRATUIT
    return MODELE_TRANCHES

CLES = {
    "anthropic": {"nom": "Claude (Anthropic)", "prefixe": "sk-ant-",
                  "ou": "console.anthropic.com"},
    "groq": {"nom": "Groq", "prefixe": "gsk_", "ou": "console.groq.com"},
    "google": {"nom": "Gemini (Google)", "prefixe": "AIza",
               "ou": "aistudio.google.com/apikey"},
}


class FournisseurError(RuntimeError):
    pass


class QuotaError(FournisseurError):
    """Plafond quotidien atteint : réessayer ne sert à rien."""


class Indisponible(FournisseurError):
    """Le modèle est momentanément saturé. Comme une limite par minute,
    cela se franchit en patientant — ce n'est pas une panne de la requête."""

    def __init__(self, message: str, secondes: float = 20.0):
        super().__init__(message)
        self.secondes = secondes


class LimiteMinute(FournisseurError):
    """Seau par minute vidé : il suffit de patienter."""

    def __init__(self, message: str, secondes: float):
        super().__init__(message)
        self.secondes = secondes


def fiche(modele: str) -> dict:
    return MODELES.get(modele) or MODELES[MODELE_DEFAUT]


def fournisseur_de(modele: str) -> str:
    return fiche(modele)["fournisseur"]


def payant(modele: str) -> bool:
    return fiche(modele)["prix"][0] > 0


def cout_estime(modele: str, jetons_entree: int, jetons_sortie: int) -> float:
    entree, sortie = fiche(modele)["prix"]
    return jetons_entree / 1e6 * entree + jetons_sortie / 1e6 * sortie


def tient_en_un_appel(modele: str, jetons: int) -> bool:
    """Le transcript entier passe-t-il, en gardant la place de répondre ?"""
    f = fiche(modele)
    return jetons + f["sortie"] < f["contexte"] * 0.8


# ------------------------------------------------------------------ appels

def appeler(cle: str, modele: str, systeme: str, requete: str,
            schema: dict | None = None, note=None) -> str:
    """Rend le texte de la réponse. `schema` impose la forme du JSON."""
    f = fiche(modele)
    if f["fournisseur"] == "anthropic":
        return _anthropic(cle, f, systeme, requete, schema)
    if f["fournisseur"] == "google":
        return _google(cle, f, systeme, requete, schema)
    return _groq(cle, f, systeme, requete, schema)


def _anthropic(cle: str, f: dict, systeme: str, requete: str,
               schema: dict | None) -> str:
    """Un appel à Claude.

    Deux choix méritent un mot. La forme de la réponse est imposée par
    `output_config.format` plutôt que demandée dans la consigne : le JSON
    est alors valide par construction, ce qui retire la panne qui nous a
    le plus coûté — une réponse bien formée mais vide, ou tronquée au
    milieu d'un objet. Et la réflexion est laissée en mode adaptatif :
    décider si « accordés » appartient à la phrase précédente est
    exactement le genre de jugement qui en profite.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise FournisseurError("Le paquet anthropic n'est pas installé.") from exc

    params = dict(
        model=f["id"],
        max_tokens=f["sortie"],
        system=systeme,
        messages=[{"role": "user", "content": requete}],
        thinking={"type": "adaptive"},
    )
    reglages: dict = {"effort": "high"}
    if schema:
        reglages["format"] = {"type": "json_schema", "schema": schema}
    params["output_config"] = reglages

    client = anthropic.Anthropic(api_key=cle) if cle else anthropic.Anthropic()
    try:
        reponse = client.messages.create(**params)
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc) from exc

    if getattr(reponse, "stop_reason", None) == "refusal":
        raise FournisseurError(
            "Le modèle a refusé de traiter cet extrait. "
            "C'est inattendu sur un compte rendu de réunion : "
            "réessayer avec un autre modèle.")

    morceaux = [b.text for b in reponse.content
                if getattr(b, "type", "") == "text" and getattr(b, "text", "")]
    return "".join(morceaux).strip()


def _google(cle: str, f: dict, systeme: str, requete: str,
            schema: dict | None) -> str:
    """Un appel à Gemini.

    Même parti pris que pour Claude : la forme de la réponse est imposée
    par un schéma plutôt que demandée dans la consigne, de sorte qu'un
    JSON vide ou tronqué ne soit pas une réponse possible."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise FournisseurError("Le paquet google-genai n'est pas installé.") from exc

    reglages = dict(system_instruction=systeme, temperature=0.0,
                    max_output_tokens=f["sortie"])
    if schema:
        reglages["response_mime_type"] = "application/json"
        reglages["response_json_schema"] = schema

    # Le client doit vivre jusqu'à la fin de l'appel : construit à la
    # volée dans l'expression, il est ramassé avant que la requête
    # n'aboutisse, et le SDK répond « client has been closed ».
    client = genai.Client(api_key=cle)
    try:
        reponse = client.models.generate_content(
            model=f["id"], contents=requete,
            config=types.GenerateContentConfig(**reglages))
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc) from exc

    texte = getattr(reponse, "text", None)
    if not texte:
        raise FournisseurError(
            "Réponse vide de Gemini. Si cela se répète, essayer un autre modèle.")
    return texte.strip()


def _groq(cle: str, f: dict, systeme: str, requete: str,
          schema: dict | None) -> str:
    try:
        from groq import Groq
    except ImportError as exc:
        raise FournisseurError("Le paquet groq n'est pas installé.") from exc

    params = dict(
        model=f["id"],
        messages=[{"role": "system", "content": systeme},
                  {"role": "user", "content": requete}],
        temperature=0.0,
        max_completion_tokens=f["sortie"],
    )
    if f.get("effort"):
        params["reasoning_effort"] = "low"
    if schema:
        params["response_format"] = {"type": "json_object"}

    try:
        reponse = Groq(api_key=cle).chat.completions.create(**params)
    except Exception as exc:  # noqa: BLE001
        raise _traduire(exc) from exc
    return (reponse.choices[0].message.content or "").strip()


# --------------------------------------------------------------- erreurs

def _traduire(exc: Exception) -> Exception:
    """Range une panne de fournisseur dans l'une de nos trois catégories.

    La distinction par minute / par jour n'est pas cosmétique : la
    première se franchit en patientant, la seconde pas du tout. Les
    confondre faisait abandonner une relecture entière pour une pause de
    trente secondes."""
    texte = str(exc)
    # Saturation passagère : les offres gratuites en voient beaucoup.
    if ("503" in texte or "UNAVAILABLE" in texte or "high demand" in texte
            or "overloaded" in texte):
        return Indisponible("Modèle momentanément saturé.", _secondes(texte) or 20.0)
    bride = ("429" in texte or "rate_limit" in texte
             or "RESOURCE_EXHAUSTED" in texte)
    if not bride:
        return exc
    # Google nomme la métrique épuisée dans le message ; Groq écrit la
    # période en toutes lettres.
    jour = ("per day" in texte or "TPD" in texte or "RPD" in texte
            or "PerDay" in texte)
    if jour:
        return QuotaError(_message_quota(texte))
    return LimiteMinute("Limite par minute atteinte.", _secondes(texte))


def _message_quota(texte: str) -> str:
    attente = _delai(texte)
    return ("Quota quotidien atteint chez ce fournisseur."
            + (f" Réessayer dans {attente}." if attente else "")
            + " Le décompte glisse sur la journée : l'attente annoncée est"
              " la bonne, souvent quelques minutes. Les modèles Claude n'ont"
              " pas de plafond quotidien — ils se paient à l'usage, quelques"
              " dizaines de centimes par réunion.")


def _delai(texte: str) -> str:
    import re
    t = re.search(r"try again in ([\dhms.]+)", texte)
    return t.group(1).rstrip(".") if t else ""


def _secondes(texte: str) -> float:
    import re
    t = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?([\d.]+)s", texte)
    if not t:
        return 5.0
    h, m, s = t.group(1), t.group(2), t.group(3)
    return int(h or 0) * 3600 + int(m or 0) * 60 + float(s)


# ---------------------------------------------------------------- schémas

# Imposé à Claude par `output_config.format`, et décrit dans la consigne
# pour les modèles Groq qui ne savent pas contraindre leur sortie.
SCHEMA_ATTRIBUTION = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blocs"],
    "properties": {
        "blocs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["bloc", "locuteur"],
                "properties": {
                    "bloc": {"type": "integer"},
                    "locuteur": {"type": "string"},
                    "deplacer": {"type": "integer"},
                },
            },
        },
    },
}

SCHEMA_TEXTE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["blocs"],
    "properties": {
        "blocs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["bloc", "texte"],
                "properties": {
                    "bloc": {"type": "integer"},
                    "texte": {"type": "string"},
                },
            },
        },
    },
}


def lire_json(brut: str) -> dict:
    """Lit la réponse, en tolérant une enveloppe de texte autour du JSON."""
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        debut, fin = brut.find("{"), brut.rfind("}")
        if debut >= 0 and fin > debut:
            return json.loads(brut[debut:fin + 1])
        raise
