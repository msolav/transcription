"""Les routes de correction et de résumé, posées sur n'importe quelle
application.

Pourquoi un module à part. Elles servent dans les deux programmes : on
corrige et on résume aussi bien juste après une transcription que des
mois plus tard en rouvrant une séance dans la bibliothèque. Les recopier
d'un fichier à l'autre, c'est garantir qu'un jour une correction faite
d'un seul côté créera deux comportements pour le même bouton.

Ce que le module ne sait pas : où vivent les travaux. Chaque application
le lui dit par un `Depot` — trois méthodes, rien de plus. La
bibliothèque n'a pas de travail en cours, elle tient simplement les
séances qu'on vient d'ouvrir ; l'application complète a les deux.
"""

from __future__ import annotations

import threading
from typing import Protocol

from fastapi import HTTPException

from . import config, fournisseurs, relecture


class Depot(Protocol):
    """Ce que les routes ont besoin de savoir des travaux."""

    verrou: threading.Lock

    def lire(self, job_id: str) -> dict | None:
        """Le travail, ou None s'il est inconnu."""

    def retenir(self, job_id: str) -> None:
        """Range le travail, sans jamais lever."""


def expliquer_cle(exc: Exception, fournisseur: str) -> str:
    """Rend un refus de clé lisible, en nommant d'où venait la clé.

    Une variable d'environnement l'emporte sur le trousseau : une clé
    révoquée oubliée dans un shell est envoyée à la place de la bonne, et
    le message du fournisseur ne dit jamais laquelle il a reçue."""
    message = str(exc)
    if not message.startswith("CLE_REFUSEE::"):
        return message
    fiche = config.FOURNISSEURS.get(fournisseur, {})
    source = config.source_cle(fournisseur)
    ou = {"environnement": f"de la variable {fiche.get('env', '')}",
          "trousseau": "du trousseau du système",
          "simulation": "de la simulation de premier démarrage",
          "fichier": "de l'ancien fichier de configuration"}.get(source, "de nulle part")
    suite = ""
    if source == "environnement":
        suite = (f" Elle vient {ou}, qui l'emporte sur le trousseau : si une"
                 f" clé valide y est enregistrée, relancer le programme après"
                 f" « unset {fiche.get('env', '')} ».")
    elif source:
        suite = f" Elle vient {ou}."
    return message.split("::", 1)[1] + suite


def lancer_relecture(depot: Depot, job_id: str, attribution: bool, texte: bool,
                     modele: str, contexte: str = "") -> None:
    """Relit un transcript, dans un fil à part.

    Rien n'est appliqué ici : on range des propositions que l'interface
    affiche côte à côte avec l'original. C'est l'utilisateur qui tranche."""
    job = depot.lire(job_id)
    if not job:
        return

    def note(message: str, remplacer: bool = False) -> None:
        """Ajoute une ligne au journal, ou récrit la dernière.

        Le décompte d'une attente de quota s'écrit une fois par seconde :
        empilé, il chasserait tout le reste du journal en une minute."""
        with depot.verrou:
            lignes = list(job["relecture"]["notes"])
            if remplacer and lignes:
                lignes[-1] = message
            else:
                lignes.append(message)
            job["relecture"]["notes"] = lignes[-12:]

    def stop() -> bool:
        with depot.verrou:
            r = job.get("relecture") or {}
        return bool(r.get("cancel"))

    corrections: list = []
    try:
        blocs, noms = job["blocks"], job["names"]
        cle = config.get_key(fournisseurs.fournisseur_de(modele))
        if attribution:
            corrections += relecture.corriger_attribution(
                blocs, noms, cle, modele, note=note, contexte=contexte, stop=stop)
        if texte:
            corrections += relecture.corriger_texte(
                blocs, cle, modele, note=note, contexte=contexte, stop=stop)
        apercu = relecture.appliquer(blocs, corrections, noms) if corrections else blocs
        with depot.verrou:
            job["relecture"].update(status="done", corrections=corrections,
                                    blocks=apercu)
    except relecture.Annulee:
        # Les corrections déjà trouvées sont conservées : une passe
        # d'attribution terminée vaut quelque chose même si l'on arrête
        # avant celle du texte.
        apercu = (relecture.appliquer(job["blocks"], corrections, job["names"])
                  if corrections else job["blocks"])
        with depot.verrou:
            job["relecture"].update(status="cancelled", corrections=corrections,
                                    blocks=apercu, cancel=False)
    except Exception as exc:  # noqa: BLE001
        with depot.verrou:
            job["relecture"].update(status="error", error=str(exc))


def brancher(app, depot: Depot, modeles=None) -> None:
    """Pose les routes sur l'application donnée.

    `modeles` restreint les fournisseurs proposés. La bibliothèque n'en
    offre que deux — Groq et Gemini, les gratuits : embarquer les clients
    d'Anthropic et d'OpenAI lui coûterait cinquante-six mégaoctets, pour
    des services payants qu'on utilise de toute façon depuis
    l'application complète."""

    def catalogue() -> dict:
        tout = fournisseurs.MODELES
        return {k: v for k, v in tout.items()
                if modeles is None or v["fournisseur"] in modeles}

    def defaut(cles: dict) -> str:
        choix = fournisseurs.modele_par_defaut(cles)
        # Le défaut global peut désigner un fournisseur absent d'ici ; on
        # retombe alors sur le premier disponible de ce catalogue-ci.
        if choix in catalogue():
            return choix
        dispo = [k for k, v in catalogue().items() if cles.get(v["fournisseur"])]
        return dispo[0] if dispo else next(iter(catalogue()), "")

    @app.post("/api/key")
    def enregistrer_cle(payload: dict) -> dict:
        key = str(payload.get("key", ""))
        f = str(payload.get("fournisseur") or "groq")
        langue = "en" if str(payload.get("langue") or "fr") == "en" else "fr"
        if f not in config.FOURNISSEURS:
            raise HTTPException(400, "Fournisseur inconnu.")
        probleme = config.check_key(key, f, langue)
        if probleme:
            raise HTTPException(400, probleme)
        config.set_key(key, f)
        return {"cles": config.cles_presentes()}

    @app.delete("/api/key")
    def oublier_cle(fournisseur: str = "groq") -> dict:
        config.clear_key(fournisseur)
        return {"cles": config.cles_presentes()}

    @app.get("/api/relecture")
    def options_relecture() -> dict:
        cles = config.cles_presentes()
        return {
            "modeles": [{"cle": k, "nom": v["nom"], "note": v["note"],
                         "dispo": bool(cles.get(v["fournisseur"]))}
                        for k, v in catalogue().items()],
            "defaut": defaut(cles),
            "resumes": [{"cle": k, "nom": v["nom"], "apercu": v["apercu"]}
                        for k, v in relecture.RESUMES.items()],
            "resume_defaut": relecture.RESUME_DEFAUT,
        }

    @app.get("/api/relecture/modeles")
    def modeles_relecture() -> dict:
        cles = config.cles_presentes()
        liste = []
        for cle, m in catalogue().items():
            liste.append({
                "cle": cle, "nom": m["nom"], "note": m["note"],
                "fournisseur": m["fournisseur"],
                "gratuit": not fournisseurs.payant(cle),
                "dispo": bool(cles.get(m["fournisseur"])),
                "un_appel": m["contexte"] > 100_000,
            })
        liste.sort(key=lambda x: (not x["dispo"], not x["gratuit"]))
        fiches = {}
        for nom, f in config.FOURNISSEURS.items():
            if modeles is not None and nom not in modeles:
                continue
            fiches[nom] = dict(f, gratuit=bool(
                fournisseurs.CLES.get(nom, {}).get("gratuit")))
        return {"modeles": liste, "defaut": defaut(cles), "fournisseurs": fiches}

    @app.get("/api/jobs/{job_id}/cout")
    def cout_relecture(job_id: str, attribution: int = 1, texte: int = 1) -> dict:
        """Estimation avant de lancer, pour ne pas épuiser un quota sans le voir."""
        job = depot.lire(job_id)
        if not job:
            raise HTTPException(404, "Tâche inconnue.")
        return {"jetons": relecture.estimer_jetons(
            job["blocks"], bool(attribution), bool(texte)),
            "blocs": len(job["blocks"])}

    @app.post("/api/jobs/{job_id}/relire")
    def relire(job_id: str, payload: dict) -> dict:
        with depot.verrou:
            job = depot.lire(job_id)
            if not job:
                raise HTTPException(404, "Tâche inconnue.")
            if job.get("status") not in (None, "done"):
                raise HTTPException(400, "La transcription n'est pas terminée.")
            if (job.get("relecture") or {}).get("status") == "running":
                raise HTTPException(409, "Une relecture est déjà en cours.")
            job["relecture"] = {"status": "running", "notes": [], "corrections": [],
                                "blocks": [], "error": None}
        threading.Thread(
            target=lancer_relecture,
            args=(depot, job_id, bool(payload.get("attribution", True)),
                  bool(payload.get("texte", True)),
                  str(payload.get("modele") or defaut(config.cles_presentes())),
                  str(payload.get("contexte") or "")),
            daemon=True).start()
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/relire/annuler")
    def annuler_relecture(job_id: str) -> dict:
        """Demande l'arrêt de la relecture en cours.

        Un drapeau, relu entre chaque fenêtre et pendant les attentes de
        quota — celles-ci durent de vingt à soixante-quinze secondes, et
        c'est là qu'on veut arrêter puisque c'est là qu'il ne se passe
        rien."""
        with depot.verrou:
            job = depot.lire(job_id)
            if not job:
                raise HTTPException(404, "Tâche inconnue.")
            r = job.get("relecture") or {}
            if r.get("status") == "running":
                r["cancel"] = True
                r["notes"] = (r.get("notes") or []) + ["arrêt demandé"]
            return {"status": r.get("status") or "none"}

    @app.post("/api/jobs/{job_id}/resume")
    def resume(job_id: str, payload: dict) -> dict:
        job = depot.lire(job_id)
        if not job:
            raise HTTPException(404, "Tâche inconnue.")
        blocs = (job["relecture"]["blocks"]
                 if (job.get("relecture") or {}).get("blocks") else job["blocks"])
        modele = str(payload.get("modele") or defaut(config.cles_presentes()))
        try:
            texte = relecture.resumer(
                blocs, job["names"],
                config.get_key(fournisseurs.fournisseur_de(modele)),
                str(payload.get("forme") or relecture.RESUME_DEFAUT),
                modele, str(payload.get("contexte") or ""))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                502, "Résumé impossible : "
                + expliquer_cle(exc, fournisseurs.fournisseur_de(modele))) from exc
        return {"texte": texte}

    @app.post("/api/jobs/{job_id}/appliquer")
    def appliquer(job_id: str, payload: dict) -> dict:
        """Ré-applique un sous-ensemble de corrections.

        On recalcule à partir de l'original, jamais à partir de la
        version déjà corrigée, sinon les refus successifs s'empileraient
        sur un texte déjà modifié."""
        job = depot.lire(job_id)
        if not job or not job.get("relecture"):
            raise HTTPException(404, "Aucune relecture pour cette tâche.")
        gardees = payload.get("corrections") or []
        try:
            apercu = relecture.appliquer(job["blocks"], gardees, job["names"])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, f"Corrections inapplicables : {exc}") from exc
        with depot.verrou:
            job["relecture"]["blocks"] = apercu
        depot.retenir(job_id)
        return {"blocks": apercu}
