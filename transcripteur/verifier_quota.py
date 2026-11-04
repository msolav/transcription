"""Un 429 doit interrompre la passe, pas la degrader en silence."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from transcripteur import relecture, fournisseurs

MESSAGE = ("Quota quotidien atteint chez ce fournisseur. Réessayer dans 1h21m9.936s. "
           "Le décompte glisse sur la journée.")

def bloc(sp, texte, t0):
    mots = texte.split()
    return {"speaker": sp, "start": t0, "end": t0+len(mots)*0.4,
            "words": [{"start": t0+i*0.4, "end": t0+i*0.4+0.35, "text": m}
                      for i, m in enumerate(mots)], "text": texte}
blocs = [bloc("SPEAKER_00" if i % 2 else "SPEAKER_01", f"phrase numero {i} de la reunion", i*10)
         for i in range(80)]
noms = {"SPEAKER_00": "Vincent", "SPEAKER_01": "Annie"}

appels = []
def refus(*a, **k):
    appels.append(1)
    raise fournisseurs.QuotaError(MESSAGE)
fournisseurs.appeler = refus

ok = rate = 0
def verifie(nom, cond, detail=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {detail}"))
    if cond: ok += 1
    else: rate += 1

verifie("un quota est reconnu", relecture._est_quota(fournisseurs.QuotaError(MESSAGE)))
verifie("une pause par minute n'est pas un quota",
        not relecture._est_quota(fournisseurs.LimiteMinute("x", 3.0)))

for nom, appel in (("attribution", lambda: relecture.corriger_attribution(blocs, noms, "k", "gpt-oss-120b")),
                   ("texte", lambda: relecture.corriger_texte(blocs, "k", "gpt-oss-120b")),
                   ("resume", lambda: relecture.resumer(blocs, noms, "k", modele="gpt-oss-120b"))):
    appels.clear()
    try:
        appel()
        verifie(f"{nom} s'arrete net", False, "aucune exception levee")
    except relecture.QuotaError as exc:
        verifie(f"{nom} s'arrete net", True)
        verifie(f"{nom} : un seul appel avant l'arret", len(appels) == 1, f"{len(appels)} appels")
        verifie(f"{nom} : le message dit quoi faire",
                "1h21m" in str(exc) and "glisse" in str(exc), str(exc)[:110])
    except Exception as exc:
        verifie(f"{nom} s'arrete net", False, f"{type(exc).__name__}: {exc}")

# une panne ordinaire, elle, doit rester rattrapee par fenetre
def panne(*a, **k):
    raise RuntimeError("json invalide")
fournisseurs.appeler = panne
# Il faut plusieurs fenetres pour que l'enonce ait un sens : avec une
# seule, une panne ordinaire EST une panne totale, et doit le dire.
LONG = ("on reprend le point concernant les locaux et les activites "
        "prevues pour la saison avec le comite de quartier ") * 4
gros = [bloc("SPEAKER_00" if i % 2 else "SPEAKER_01", f"[{i}] {LONG}", i*10)
        for i in range(40)]
tours = {"n": 0}
def une_sur_deux(*a, **k):
    tours["n"] += 1
    if tours["n"] == 1:
        raise RuntimeError("json invalide")
    debut = (tours["n"] - 1) * 10
    return json.dumps({"blocs": [{"bloc": i, "locuteur": "Annie"}
                                 for i in range(debut, min(debut + 10, 40))]})
fournisseurs.appeler = une_sur_deux
try:
    r = relecture.corriger_attribution(gros, noms, "k", "gpt-oss-120b")
    verifie("une panne ordinaire n'arrete pas les autres fenetres", True)
except Exception as exc:
    verifie("une panne ordinaire n'arrete pas les autres fenetres", False, str(exc)[:80])

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
