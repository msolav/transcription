"""Contrôles de la lecture des verdicts d'attribution.

Aucun appel réseau : les réponses du modèle sont des enregistrements.
Ce qui est vérifié ici, c'est la traduction verdicts -> corrections, et
surtout le refus d'une fenêtre à moitié jugée : c'est ce cas-là qui
faisait passer une lecture ratée pour une absence d'erreur."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import relecture, fournisseurs

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
    fournisseurs.appeler = lambda *a, **k: json.dumps(reponse)
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

# 3. reponse a moitie jugee : ecartee — et comme c'est l'unique fenetre,
#    la passe entiere a echoue et doit le dire plutot que rendre [].
notes = []
try:
    c = rejoue({"blocs": [{"bloc": 0, "locuteur": "Vincent"}]}, note=notes.append)
    v("fenêtre à moitié jugée : échec annoncé", False, f"a rendu {c!r}")
except relecture.FournisseurError:
    v("fenêtre à moitié jugée : échec annoncé", any("jugés" in n for n in notes), notes)

# 4. reponse vide : ecartee de la meme facon
notes.clear()
try:
    c = rejoue({"blocs": []}, note=notes.append)
    v("réponse vide : échec annoncé", False, f"a rendu {c!r}")
except relecture.FournisseurError:
    v("réponse vide : échec annoncé", any("jugés" in n for n in notes), notes)

# 4b. plusieurs fenetres, une seule perdue : le reste doit survivre.
#     C'est la contrepartie de la regle ci-dessus — elle ne doit pas
#     transformer un incident local en echec total.
# Des blocs assez longs pour que le transcript ne tienne pas en un seul
# appel chez un modele a petit contexte : sans cela il n'y a qu'une
# fenetre, et le cas qu'on veut couvrir n'existe pas.
LONG = ("on reprend le point precedent concernant les locaux et les "
        "activites prevues pour la saison a venir avec le comite ") * 4
GROS = [bloc("SPEAKER_00" if i % 2 else "SPEAKER_01", f"[{i}] {LONG}")
        for i in range(40)]
tours = {"n": 0}
def alterne(*a, **k):
    tours["n"] += 1
    if tours["n"] == 1:
        raise relecture.FournisseurError("fenêtre perdue")
    debut = (tours["n"] - 1) * 10
    return json.dumps({"blocs": [{"bloc": i, "locuteur": "Annie"}
                                 for i in range(debut, min(debut + 10, 40))]})
relecture.fournisseurs.appeler = alterne
notes.clear()
c = relecture.corriger_attribution(GROS, NOMS, "k", "gpt-oss-120b", note=notes.append)
v("une fenêtre perdue parmi d'autres n'annule pas le reste",
  len(c) > 0 and any("ignorée" in n for n in notes), f"{len(c)} corrections")

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

# 8. toutes les fenetres perdues : erreur franche, pas une liste vide
#    Avec un seul grand appel, c'est tout le transcript qui est perdu.
def casse(*a, **k):
    raise relecture.FournisseurError("saturé")
relecture.fournisseurs.appeler = casse
try:
    r = relecture.corriger_attribution(BLOCS, NOMS, "k", "gemini-flash")
    v("tout perdu : erreur franche", False, f"a rendu {r!r} au lieu de lever")
except relecture.FournisseurError as exc:
    v("tout perdu : erreur franche", "aucune partie" in str(exc), str(exc)[:70])

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
