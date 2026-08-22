"""Rangement de la clé Groq, pour ne pas la redemander à chaque lancement."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

CONFIG_PATH = Path.home() / ".transcripteur.json"


def _load() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def get_key() -> str:
    """La variable d'environnement l'emporte sur le fichier."""
    return (os.environ.get("GROQ_API_KEY") or _load().get("groq_key") or "").strip()


def set_key(key: str) -> None:
    data = _load()
    data["groq_key"] = key.strip()
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # lisible par le seul propriétaire
    except OSError:
        pass


def clear_key() -> None:
    data = _load()
    data.pop("groq_key", None)
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_key(key: str) -> str | None:
    """Retourne None si la clé fonctionne, sinon le message à afficher."""
    key = key.strip()
    if not key:
        return "Clé vide."
    if not key.startswith("gsk_"):
        return "Une clé Groq commence par gsk_. Vérifie ce que tu as collé."
    try:
        from groq import Groq
        Groq(api_key=key).models.list()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "401" in message or "invalid_api_key" in message:
            return "Clé refusée par Groq."
        return f"Vérification impossible : {message}"
    return None
