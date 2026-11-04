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
from pathlib import Path

CONFIG_PATH = Path.home() / ".transcripteur.json"
SERVICE = "transcripteur"

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
}


def _load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _trousseau():
    try:
        import keyring
        return keyring
    except Exception:  # noqa: BLE001
        return None


def get_key(fournisseur: str = "groq") -> str:
    """Environnement, puis trousseau, puis ancien fichier."""
    fiche = FOURNISSEURS.get(fournisseur)
    if not fiche:
        return ""
    depuis_env = os.environ.get(fiche["env"], "").strip()
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
    data = _load()
    data[FOURNISSEURS[fournisseur]["ancien"]] = key
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
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
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


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


def check_key(key: str, fournisseur: str = "groq") -> str | None:
    """None si la clé fonctionne, sinon le message à afficher."""
    key = key.strip()
    fiche = FOURNISSEURS.get(fournisseur)
    if not fiche:
        return "Fournisseur inconnu."
    if not key:
        return "Clé vide."
    attendus = fiche["prefixe"]
    attendus = attendus if isinstance(attendus, tuple) else (attendus,)
    if not key.startswith(attendus):
        return (f"Une clé {fiche['nom']} commence par "
                + " ou ".join(attendus) + ". Vérifie ce que tu as collé.")
    try:
        if fournisseur == "groq":
            from groq import Groq
            Groq(api_key=key).models.list()
        elif fournisseur == "google":
            from google import genai
            genai.Client(api_key=key).models.generate_content(
                model="gemini-3.5-flash-lite", contents="ok")
        else:
            import anthropic
            # Un appel minuscule : c'est la seule façon de distinguer une
            # clé refusée d'une clé simplement mal recopiée.
            anthropic.Anthropic(api_key=key).messages.create(
                model="claude-haiku-5-5", max_tokens=1,
                messages=[{"role": "user", "content": "ok"}])
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "401" in message or "invalid_api_key" in message or "authentication" in message:
            return f"Clé refusée par {fiche['nom']}."
        if "credit" in message.lower() or "billing" in message.lower():
            return (f"Clé valide, mais le compte {fiche['nom']} n'a pas de crédit. "
                    "Ajouter du crédit, ou choisir un modèle gratuit.")
        return f"Vérification impossible : {message}"
    return None
