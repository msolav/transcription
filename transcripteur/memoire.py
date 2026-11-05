"""
Ce que le programme retient d'une fois sur l'autre.

Jusqu'ici il ne retenait rien. Un transcript vivait dans un dictionnaire
en mémoire et dans un dossier temporaire ; fermer la fenêtre noire
effaçait les deux. Pour garder une réunion, il fallait penser à
enregistrer un .json, savoir où il était allé, et le rouvrir à la main.
Celui qui ne le savait pas perdait trois quarts d'heure de calcul sans
s'en rendre compte avant le lendemain.

Une base SQLite dans le dossier de données du système, et rien d'autre.
Pas de compte, pas de mot de passe, pas de serveur. Ce qu'un compte
retiendrait — la langue habituelle, le modèle préféré, les séances
passées — ne concerne que cette machine-ci ; le demander à un serveur
reviendrait à dresser un registre de qui transcrit quoi, à protéger une
adresse courriel de plus, et à dresser un deuxième mur devant un outil
dont le premier, la clé d'API, est déjà le plus dur à franchir.

Les enregistrements eux-mêmes ne sont pas rangés dans la base : elle ne
garde que le texte et le chemin du fichier. Un fichier de deux heures
pèse plus que tous les transcripts d'une année réunis.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Les réglages de traitement, et ce qu'ils valent quand rien n'a encore
# été choisi. Ce qui touche à l'apparence — thème, langue de l'interface
# — reste au navigateur : c'est le système de design qui en décide, et
# la même install peut servir deux personnes qui n'ont pas le même goût.
# `count` porte à lui seul la question des voix, comme dans l'interface :
# « none » pour ne pas séparer, « auto » pour chercher combien, un
# chiffre pour l'annoncer. Le découper en un booléen et un nombre, comme
# le fait le formulaire envoyé au serveur, perd de l'information — « 1 »
# et « ne pas séparer » produisent le même traitement mais ne sont pas le
# même choix, et l'écran rouvert ne montrerait plus celui qui a été fait.
DEFAUTS = {
    "language": "",            # "" = détection automatique
    "count": "none",
    "embedding": "",
    "denoise": "",
    "modele_relecture": "",
    "garder_enregistrement": True,
}

_verrou = threading.Lock()
_dossier_force: Path | None = None


def dossier() -> Path:
    """Le dossier de données, à l'endroit où le système les attend.

    Un dossier caché dans le répertoire personnel conviendrait sur un
    Mac de développeur et détonnerait partout ailleurs : sur Windows, il
    n'est ni visible, ni sauvegardé, ni effacé par une désinstallation.
    Puisque le programme est destiné à être installé par quelqu'un qui
    n'ouvrira jamais un terminal, il range ses données là où le système
    sait les trouver."""
    if _dossier_force is not None:
        return _dossier_force
    # Une variable d'environnement passe devant : c'est ce qui permet
    # d'éprouver la mémoire sans toucher aux vraies séances, et de poser
    # les données ailleurs — un disque externe, un dossier synchronisé —
    # sans toucher au programme.
    impose = os.environ.get("TRANSCRIPTEUR_DONNEES", "").strip()
    if impose:
        return Path(impose).expanduser()
    perso = Path.home()
    if sys.platform == "darwin":
        base = perso / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (perso / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (perso / ".local" / "share"))
    return base / "Transcripteur"


def utiliser_dossier(chemin: Path | str | None) -> None:
    """Déplace la base, pour les essais. None rend le dossier du système."""
    global _dossier_force
    _dossier_force = Path(chemin) if chemin is not None else None


def base() -> Path:
    return dossier() / "transcripteur.sqlite3"


def seances_dir() -> Path:
    """Où vivent les fichiers d'une séance.

    Ils vivaient dans un dossier temporaire. Deux défauts : le système
    l'efface quand il veut, donc l'aperçu vidéo et la séparation des
    voix après coup ne survivaient pas à un redémarrage ; et rien ne les
    effaçait jamais vraiment, donc ils s'accumulaient hors de vue. Ici
    ils sont à un endroit connu, dont on peut dire la taille et que
    l'utilisateur peut vider."""
    return dossier() / "seances"


SCHEMA = """
CREATE TABLE IF NOT EXISTS reglages (
  cle     TEXT PRIMARY KEY,
  valeur  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seances (
  id         TEXT PRIMARY KEY,
  fichier    TEXT NOT NULL,
  source     TEXT NOT NULL DEFAULT '',
  duree      REAL NOT NULL DEFAULT 0,
  video      INTEGER NOT NULL DEFAULT 0,
  cree_le    TEXT NOT NULL,
  touche_le  TEXT NOT NULL,
  blocs      TEXT NOT NULL,
  voix       TEXT NOT NULL DEFAULT '[]',
  noms       TEXT NOT NULL DEFAULT '{}',
  relecture  TEXT
);

CREATE INDEX IF NOT EXISTS seances_date ON seances (touche_le DESC);
"""


@contextmanager
def _co():
    """Une connexion par opération, sérialisée par un verrou.

    sqlite3 n'aime pas qu'une connexion traverse les fils, et le serveur
    en a plusieurs : un pour la requête, un pour le traitement. Ouvrir à
    chaque fois coûte une fraction de milliseconde et évite toute une
    catégorie de pannes qui ne se produisent qu'une fois sur vingt."""
    dossier().mkdir(parents=True, exist_ok=True)
    with _verrou:
        co = sqlite3.connect(base(), timeout=10.0)
        co.row_factory = sqlite3.Row
        try:
            # WAL : une lecture pendant une écriture ne bloque pas, ce
            # qui arrive à chaque sondage de l'interface.
            co.execute("PRAGMA journal_mode=WAL")
            yield co
            co.commit()
        finally:
            co.close()


def preparer() -> None:
    with _co() as co:
        co.executescript(SCHEMA)


def _maintenant() -> str:
    return datetime.now(timezone.utc).isoformat()


# ----------------------------------------------------------- les réglages

def reglages() -> dict:
    """Les réglages retenus, complétés par les valeurs par défaut."""
    valeurs = dict(DEFAUTS)
    try:
        with _co() as co:
            for ligne in co.execute("SELECT cle, valeur FROM reglages"):
                if ligne["cle"] in DEFAUTS:
                    try:
                        valeurs[ligne["cle"]] = json.loads(ligne["valeur"])
                    except json.JSONDecodeError:
                        pass
    except sqlite3.Error:
        # Une base illisible ne doit pas empêcher de transcrire : on
        # retombe sur les valeurs par défaut, et l'outil fonctionne.
        return dict(DEFAUTS)
    return valeurs


def retenir(valeurs: dict) -> dict:
    """Enregistre les réglages connus, ignore les autres.

    Ignorer plutôt que refuser : l'interface envoie l'état entier de son
    formulaire, et un champ nouveau ne doit pas faire échouer la
    sauvegarde de tous les autres."""
    retenus = {c: v for c, v in valeurs.items() if c in DEFAUTS}
    if retenus:
        with _co() as co:
            co.executemany(
                "INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
                [(c, json.dumps(v)) for c, v in retenus.items()])
    return reglages()


# ------------------------------------------------------------ les séances

def enregistrer(job: dict) -> None:
    """Range une séance, ou met à jour celle qui porte le même identifiant.

    Appelée à chaque moment où le travail de quelqu'un vient de changer :
    fin de transcription, nom donné à une voix, relecture appliquée,
    voix séparées après coup. Jamais à intervalle régulier — une
    sauvegarde périodique écrit surtout quand rien n'a bougé, et manque
    la seule seconde qui comptait."""
    if not job.get("blocks"):
        return
    source = str(job.get("source") or "")
    if source and not Path(source).exists():
        source = ""
    with _co() as co:
        co.execute(
            """INSERT INTO seances
                 (id, fichier, source, duree, video, cree_le, touche_le,
                  blocs, voix, noms, relecture)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 fichier=excluded.fichier, source=excluded.source,
                 duree=excluded.duree, video=excluded.video,
                 touche_le=excluded.touche_le, blocs=excluded.blocs,
                 voix=excluded.voix, noms=excluded.noms,
                 relecture=excluded.relecture""",
            (job["id"], job.get("filename") or "sans nom", source,
             float(job.get("duration") or 0.0), 1 if job.get("video") else 0,
             job.get("created_at") or _maintenant(), _maintenant(),
             json.dumps(job["blocks"], ensure_ascii=False),
             json.dumps(job.get("speakers") or [], ensure_ascii=False),
             json.dumps(job.get("names") or {}, ensure_ascii=False),
             json.dumps(job["relecture"], ensure_ascii=False)
             if job.get("relecture") else None))


def _poids(chemin: Path) -> int:
    total = 0
    if not chemin.exists():
        return 0
    for f in chemin.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            continue
    return total


def liste() -> list[dict]:
    """De quoi dresser la liste des séances, sans lire les transcripts.

    Les blocs ne sont pas chargés : sur une réunion de deux heures, ils
    pèsent quelques mégaoctets, et la liste en afficherait dix."""
    sorties = []
    try:
        with _co() as co:
            lignes = co.execute(
                """SELECT id, fichier, source, duree, video, cree_le, touche_le,
                          json_array_length(voix) AS nb_voix,
                          relecture IS NOT NULL AS relue,
                          length(blocs) AS poids_texte
                     FROM seances ORDER BY touche_le DESC""").fetchall()
    except sqlite3.Error:
        return []
    for l in lignes:
        dossier_seance = seances_dir() / l["id"]
        sorties.append({
            "id": l["id"],
            "fichier": l["fichier"],
            "duree": l["duree"],
            "video": bool(l["video"]),
            "cree_le": l["cree_le"],
            "touche_le": l["touche_le"],
            "voix": l["nb_voix"] or 0,
            "relue": bool(l["relue"]),
            # L'enregistrement est-il encore là ? C'est ce qui décide si
            # l'on peut rouvrir avec l'aperçu et la séparation des voix,
            # ou seulement avec le texte.
            "audio_present": bool(l["source"]) and Path(l["source"]).exists(),
            "octets": _poids(dossier_seance) + (l["poids_texte"] or 0),
        })
    return sorties


def charger(seance_id: str) -> dict | None:
    """Le contenu complet d'une séance, en forme de job."""
    try:
        with _co() as co:
            l = co.execute("SELECT * FROM seances WHERE id = ?",
                           (seance_id,)).fetchone()
    except sqlite3.Error:
        return None
    if not l:
        return None
    source = l["source"] or ""
    if source and not Path(source).exists():
        source = ""
    return {
        "id": l["id"],
        "filename": l["fichier"],
        "source": source,
        "work_dir": str(seances_dir() / l["id"]),
        "status": "done",
        "stage": "Séance rouverte",
        "progress": 1.0,
        "error": None,
        "duration": l["duree"],
        "speakers": json.loads(l["voix"]),
        "blocks": json.loads(l["blocs"]),
        "names": json.loads(l["noms"]),
        "notes": ["séance rouverte depuis la mémoire du programme"],
        "relecture": json.loads(l["relecture"]) if l["relecture"] else None,
        "cancel": False,
        "created_at": l["cree_le"],
        "video": bool(l["video"]) and bool(source),
        "sans_audio": not source,
    }


def oublier(seance_id: str) -> bool:
    """Efface une séance et ses fichiers. Sans retour en arrière."""
    import shutil
    with _co() as co:
        n = co.execute("DELETE FROM seances WHERE id = ?", (seance_id,)).rowcount
    shutil.rmtree(seances_dir() / seance_id, ignore_errors=True)
    return bool(n)


def liberer_audio(seance_id: str) -> bool:
    """Jette l'enregistrement, garde le texte.

    Le cas courant d'un disque qui se remplit : les transcripts ne
    pèsent rien, les enregistrements pèsent tout. Les séparer permet de
    faire de la place sans rien perdre de ce qui a été écrit."""
    import shutil
    dossier_seance = seances_dir() / seance_id
    for f in dossier_seance.glob("source.*"):
        f.unlink(missing_ok=True)
    for reste in ("audio16k.wav",):
        (dossier_seance / reste).unlink(missing_ok=True)
    shutil.rmtree(dossier_seance / "tranches", ignore_errors=True)
    with _co() as co:
        n = co.execute("UPDATE seances SET source = '' WHERE id = ?",
                       (seance_id,)).rowcount
    return bool(n)


def place_occupee() -> dict:
    """Ce que le programme occupe sur le disque, et où."""
    return {
        "dossier": str(dossier()),
        "octets": _poids(seances_dir()) + (base().stat().st_size
                                           if base().exists() else 0),
        "seances": _poids(seances_dir()),
    }
