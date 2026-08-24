"""Contrôles de la lecture des verdicts d'attribution.

Aucun appel réseau : les réponses du modèle sont des enregistrements.
Ce qui est vérifié ici, c'est la traduction verdicts -> corrections, et
surtout le refus d'une fenêtre à moitié jugée : c'est ce cas-là qui
faisait passer une lecture ratée pour une absence d'erreur."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import relecture

def bloc(sp, texte):
    mots = texte.split()
    return {"speaker": sp, "start": 0.0, "end": len(mots) * 0.4,
            "words": [{"start": i * 0.4, "end": i * 0.4 + 0.35, "text": m}
                      for i, m in enumerate(mots)], "text": texte}

BLOCS = [
    bloc("SPEAKER_00", "ils vont être réévalués avant d'être"),
    bloc("SPEAKER_01", "accordés exactement vous"),
    bloc("SPEAKER_00", "allez faire ça à l'interne"),
    bloc("SPEAKER_01", "Un peu comme avec Milton Park."),
]
NOMS = {"SPEAKER_00": "Vincent", "SPEAKER_01": "Annie"}

ok = rate = 0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {d}"))
    ok += cond; rate += not cond

def rejoue(reponse, note=None):
    relecture._appeler = lambda *a, **k: json.dumps(reponse)
    return relecture.corriger_attribution(BLOCS, NOMS, "k", note=note)

# 1. verdicts complets, une reattribution et un deplacement
c = rejoue({"blocs": [
    {"bloc": 0, "locuteur": "Vincent"},
    {"bloc": 1, "locuteur": "Annie", "deplacer": 1},
    {"bloc": 2, "locuteur": "Annie"},
    {"bloc": 3, "locuteur": "Annie"}]})
v("réattribution détectée", any(x["type"] == "locuteur" and x["bloc"] == 2 for x in c), c)
v("déplacement détecté", any(x["type"] == "frontiere" and x["bloc"] == 1 for x in c), c)
v("bloc inchangé ignoré", not any(x["bloc"] == 0 for x in c), c)

# 2. tout est correct : aucune correction, mais la fenetre a bien ete lue
c = rejoue({"blocs": [{"bloc": i, "locuteur": NOMS[BLOCS[i]["speaker"]]}
                      for i in range(4)]})
v("fenêtre sans erreur : zéro correction", c == [], c)

# 3. reponse a moitie jugee : ecartee, pas prise pour une absence d'erreur
notes = []
c = rejoue({"blocs": [{"bloc": 0, "locuteur": "Vincent"}]}, note=notes.append)
v("fenêtre à moitié jugée écartée", c == [] and any("jugés" in n for n in notes), notes)

# 4. reponse vide : ecartee de la meme facon
notes.clear()
c = rejoue({"blocs": []}, note=notes.append)
v("réponse vide écartée", c == [] and any("jugés" in n for n in notes), notes)

# 5. un nom invente est ignore
c = rejoue({"blocs": [{"bloc": i, "locuteur": "Quelqu'un d'autre"} for i in range(4)]})
v("nom inventé ignoré", c == [], c)

# 6. un deplacement absurde est ignore
c = rejoue({"blocs": [{"bloc": i, "locuteur": NOMS[BLOCS[i]["speaker"]]} for i in range(4)]
            + [{"bloc": 1, "locuteur": "Annie", "deplacer": 99}]})
v("déplacement plus long que le bloc ignoré", c == [], c)

# 7. l'identifiant technique accompagne la reattribution
c = rejoue({"blocs": [{"bloc": 2, "locuteur": "Annie"}] +
                     [{"bloc": i, "locuteur": NOMS[BLOCS[i]["speaker"]]} for i in (0, 1, 3)]})
r = [x for x in c if x["type"] == "locuteur"]
v("identifiant transporté", r and r[0].get("apres_id") == "SPEAKER_01", r)

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
