"""
Rangement des clés d'API, une par fournisseur.

Deux clés distinctes, parce qu'elles paient deux choses différentes :
Groq transcrit la parole (son offre gratuite suffit), Claude relit
l'attribution. On peut n'en fournir qu'une.

Les clés vont dans le trousseau du système — Keychain sur macOS,
Gestionnaire d'identifiants sur Windows — et non dans un fichier du
dossier personnel. Une clé d'API est un moyen de paiement : elle n'a pas
sa place en clair dans un JSON que n'importe quelle sauvegarde recopie.
Le fichier reste lu en second, pour les clés déjà posées par une version
précédente, et une variable d'environnement l'emporte sur tout le reste.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

CONFIG_PATH = Path.home() / ".transcripteur.json"
SERVICE = "transcripteur"

# ------------------------------------------------------------------ vierge
#
# Sur le poste où l'on écrit le programme, les clés sont là depuis des
# mois : dans le trousseau, et souvent aussi dans une variable
# d'environnement du shell. Le premier écran — celui qui explique où
# prendre une clé et comment la coller — ne s'affiche donc plus jamais.
# C'est précisément l'écran que personne d'autre ne peut éviter, et le
# seul qu'on ne peut pas relire par-dessus l'épaule de quelqu'un.
#
# TRANSCRIPTEUR_VIERGE=1 fait oublier au programme tout ce qu'il sait :
# les variables d'environnement sont ignorées, le trousseau du système
# n'est ni lu ni écrit, et les clés saisies pendant la simulation vont
# dans un fichier jetable. Le trousseau réel ressort intact — une
# simulation qui effacerait la vraie clé en coûterait une rotation.
def en_simulation() -> bool:
    """Relu à chaque appel, pour qu'un essai puisse basculer le mode."""
    return os.environ.get("TRANSCRIPTEUR_VIERGE", "").strip() not in ("", "0")


def bacen_simulation() -> Path:
    return Path(tempfile.gettempdir()) / "transcripteur-simulation.json"


def oublier_simulation() -> None:
    """Remet la simulation à zéro, sans toucher au trousseau réel."""
    bacen_simulation().unlink(missing_ok=True)


def _fichier() -> Path:
    return bacen_simulation() if en_simulation() else CONFIG_PATH

# Par fournisseur : la variable d'environnement d'usage, la clé héritée
# dans l'ancien fichier, et le préfixe attendu.
FOURNISSEURS = {
    "groq": {"env": "GROQ_API_KEY", "ancien": "groq_key", "prefixe": "gsk_",
             "nom": "Groq", "ou": "console.groq.com/keys"},
    # Google émet deux formats de clé : l'ancien « AIza… » et le plus
    # récent « AQ.… ». N'en accepter qu'un refusait des clés parfaitement
    # valides, en accusant l'utilisateur de les avoir mal collées.
    "google": {"env": "GEMINI_API_KEY", "ancien": "google_key",
               "prefixe": ("AIza", "AQ."), "nom": "Gemini (Google)",
               "ou": "aistudio.google.com/apikey"},
    "anthropic": {"env": "ANTHROPIC_API_KEY", "ancien": "anthropic_key",
                  "prefixe": "sk-ant-", "nom": "Claude (Anthropic)",
                  "ou": "console.anthropic.com/settings/keys"},
    # OpenAI émet des clés « sk-… » et « sk-proj-… » selon qu'elles
    # appartiennent au compte ou à un projet. N'accepter que la seconde
    # forme refuserait des clés valides : on s'en tient au préfixe commun.
    "openai": {"env": "OPENAI_API_KEY", "ancien": "openai_key",
               "prefixe": "sk-", "nom": "ChatGPT (OpenAI)",
               "ou": "platform.openai.com/api-keys"},
}


def _load() -> dict:
    try:
        return json.loads(_fichier().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _trousseau():
    # En simulation, on rend None : le trousseau n'est alors ni interrogé
    # ni modifié, ce qui met les vraies clés hors d'atteinte.
    if en_simulation():
        return None
    try:
        import keyring
        return keyring
    except Exception:  # noqa: BLE001
        return None


def source_cle(fournisseur: str) -> str:
    """D'où vient la clé en service : « environnement », « trousseau »,
    « fichier » ou « » si aucune.

    La distinction n'est pas décorative. Une variable d'environnement
    l'emporte sur le trousseau, donc une clé révoquée oubliée dans un
    shell continue d'être envoyée alors qu'une clé valide dort à côté. Le
    fournisseur répond « clé invalide » sans dire laquelle, et rien dans
    l'interface ne laisse deviner qu'il en existe deux."""
    fiche = FOURNISSEURS.get(fournisseur)
    if not fiche:
        return ""
    if not en_simulation() and os.environ.get(fiche["env"], "").strip():
        return "environnement"
    kr = _trousseau()
    if kr:
        try:
            if (kr.get_password(SERVICE, fournisseur) or "").strip():
                return "trousseau"
        except Exception:  # noqa: BLE001
            pass
    if (_load().get(fiche["ancien"]) or "").strip():
        return "simulation" if en_simulation() else "fichier"
    return ""


def get_key(fournisseur: str = "groq") -> str:
    """Environnement, puis trousseau, puis ancien fichier."""
    fiche = FOURNISSEURS.get(fournisseur)
    if not fiche:
        return ""
    depuis_env = "" if en_simulation() else os.environ.get(fiche["env"], "").strip()
    if depuis_env:
        return depuis_env
    kr = _trousseau()
    if kr:
        try:
            garde = kr.get_password(SERVICE, fournisseur)
            if garde:
                return garde.strip()
        except Exception:  # noqa: BLE001
            pass
    return (_load().get(fiche["ancien"]) or "").strip()


def set_key(key: str, fournisseur: str = "groq") -> None:
    key = key.strip()
    kr = _trousseau()
    if kr:
        try:
            kr.set_password(SERVICE, fournisseur, key)
            return
        except Exception:  # noqa: BLE001
            pass
    # Sans trousseau disponible, on retombe sur le fichier, en le
    # réservant à son propriétaire.
    cible = _fichier()
    data = _load()
    data[FOURNISSEURS[fournisseur]["ancien"]] = key
    cible.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        cible.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def clear_key(fournisseur: str = "groq") -> None:
    kr = _trousseau()
    if kr:
        try:
            kr.delete_password(SERVICE, fournisseur)
        except Exception:  # noqa: BLE001
            pass
    data = _load()
    if data.pop(FOURNISSEURS.get(fournisseur, {}).get("ancien", ""), None) is not None:
        _fichier().write_text(json.dumps(data, indent=2), encoding="utf-8")


def cles_presentes() -> dict:
    """Quels fournisseurs sont configurés — sans révéler les clés."""
    return {f: bool(get_key(f)) for f in FOURNISSEURS}


def migrer_vers_trousseau() -> list[str]:
    """Déplace les clés de l'ancien fichier vers le trousseau, une fois."""
    data, deplacees = _load(), []
    kr = _trousseau()
    if not kr:
        return []
    for f, fiche in FOURNISSEURS.items():
        valeur = (data.get(fiche["ancien"]) or "").strip()
        if not valeur:
            continue
        try:
            kr.set_password(SERVICE, f, valeur)
            data.pop(fiche["ancien"])
            deplacees.append(f)
        except Exception:  # noqa: BLE001
            continue
    if deplacees:
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return deplacees


def check_key(key: str, fournisseur: str = "groq",
              langue: str = "fr") -> str | None:
    """None si la clé fonctionne, sinon le message à afficher.

    Bilingue, parce que ces messages-là sont les premiers que quelqu'un
    voit : refuser une clé en français à quelqu'un qui a mis l'interface
    en anglais, c'est le laisser devant le seul écran qu'il ne peut pas
    franchir. Le reste de l'application peut se traduire plus tard ; pas
    celui-ci."""
    def dit(fr: str, en: str) -> str:
        return en if langue == "en" else fr

    key = key.strip()
    fiche = FOURNISSEURS.get(fournisseur)
    if not fiche:
        return dit("Fournisseur inconnu.", "Unknown provider.")
    if not key:
        return dit("Clé vide.", "Empty key.")
    attendus = fiche["prefixe"]
    attendus = attendus if isinstance(attendus, tuple) else (attendus,)
    if not key.startswith(attendus):
        debuts = " ou ".join(attendus) if langue != "en" else " or ".join(attendus)
        return dit(
            f"Une clé {fiche['nom']} commence par {debuts}. Vérifie ce que "
            f"tu as collé : c'est peut-être la clé d'un autre service.",
            f"A {fiche['nom']} key starts with {debuts}. Check what you "
            f"pasted — it may be the key for another service.")
    # Chaque client est retenu dans une variable le temps de l'appel. Un
    # client construit dans l'expression même est ramassé avant que la
    # requête n'aboutisse, et le SDK répond « Cannot send a request, as
    # the client has been closed ». Ce n'est pas une subtilité de style :
    # écrit ainsi, le contrôle de la clé Gemini échouait toujours, donc
    # aucune clé Gemini ne pouvait être enregistrée — valide ou non.
    try:
        if fournisseur == "groq":
            from groq import Groq
            client = Groq(api_key=key)
            client.models.list()
        elif fournisseur == "google":
            from google import genai
            client = genai.Client(api_key=key)
            client.models.generate_content(
                model="gemini-3.5-flash-lite", contents="ok")
        else:
            import anthropic
            # Un appel minuscule : c'est la seule façon de distinguer une
            # clé refusée d'une clé simplement mal recopiée.
            client = anthropic.Anthropic(api_key=key)
            client.messages.create(
                model="claude-haiku-5-5", max_tokens=1,
                messages=[{"role": "user", "content": "ok"}])
    except Exception as exc:  # noqa: BLE001
        from . import fournisseurs
        message = str(exc)
        if fournisseurs.auth_echouee(message):
            return dit(
                f"Clé refusée par {fiche['nom']}. Recopie-la depuis "
                f"{fiche['ou']} — une espace restée au bout suffit à la "
                f"casser. Si tu l'as supprimée là-bas, il faut en créer "
                f"une autre.",
                f"Key refused by {fiche['nom']}. Copy it again from "
                f"{fiche['ou']} — one space left on the end is enough to "
                f"break it. If you deleted it there, you need to make a "
                f"new one.")
        if "credit" in message.lower() or "billing" in message.lower():
            return dit(
                f"Clé valide, mais le compte {fiche['nom']} n'a pas de "
                "crédit. Y déposer du crédit, ou choisir un modèle gratuit.",
                f"The key is valid, but the {fiche['nom']} account has no "
                "credit. Add credit there, or choose a free model.")
        return dit(f"Vérification impossible : {message}",
                   f"Could not verify: {message}")
    return None
