"""Contrôles de la relecture : application, réversibilité, garde-fou.

Aucun appel réseau : on vérifie la mécanique, pas le modèle de langue.
À relancer après toute retouche de relecture.py."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from transcripteur import relecture

def bloc(speaker, texte, t0):
    mots = texte.split()
    words = [{"start": t0+i*0.4, "end": t0+i*0.4+0.35, "text": m} for i, m in enumerate(mots)]
    return {"speaker": speaker, "start": words[0]["start"], "end": words[-1]["end"],
            "words": words, "text": texte}

noms = {"SPEAKER_00": "Vincent", "SPEAKER_01": "Annie"}
ok = 0; rate = 0
def verifie(nom, condition, detail=""):
    global ok, rate
    print(("  ok   " if condition else "  RATE ") + nom + ("" if condition else f"  -> {detail}"))
    globals().__setitem__('ok', ok + bool(condition)); globals().__setitem__('rate', rate + (not condition))

# 1. reattribution simple
b = [bloc("SPEAKER_00", "ils vont etre reevalues", 0), bloc("SPEAKER_01", "avant d etre accordes", 10)]
r = relecture.appliquer(b, [{"type":"locuteur","bloc":1,"avant":"Annie","apres":"Vincent"}], noms)
verifie("reattribution", r[1]["speaker"] == "SPEAKER_00", r[1]["speaker"])
verifie("original intact", b[1]["speaker"] == "SPEAKER_01", b[1]["speaker"])

# 2. frontiere : les 2 premiers mots du bloc 1 remontent au bloc 0
b = [bloc("SPEAKER_00", "ils vont etre reevalues avant d", 0), bloc("SPEAKER_01", "etre accordes exactement vous", 10)]
r = relecture.appliquer(b, [{"type":"frontiere","bloc":1,"mots":2}], noms)
verifie("frontiere +2 mots", r[0]["text"].endswith("etre accordes") and r[1]["text"].startswith("exactement"),
        f"{r[0]['text']!r} | {r[1]['text']!r}")
verifie("horodatage recale", r[1]["start"] == r[1]["words"][0]["start"], r[1]["start"])

# 3. frontiere negative : les 2 derniers mots descendent au bloc suivant
b = [bloc("SPEAKER_00", "se mobiliser ensemble qui va", 0), bloc("SPEAKER_01", "accepter les activites", 10)]
r = relecture.appliquer(b, [{"type":"frontiere","bloc":0,"mots":-2}], noms)
verifie("frontiere -2 mots", r[0]["text"] == "se mobiliser ensemble" and r[1]["text"].startswith("qui va"),
        f"{r[0]['text']!r} | {r[1]['text']!r}")

# 4. texte corrige
b = [bloc("SPEAKER_00", "il y a un comite qui est parmi les citoyens", 0)]
r = relecture.appliquer(b, [{"type":"texte","bloc":0,"avant":b[0]["text"],
                             "apres":"Il y a un comité qui est parmi les citoyens."}], noms)
verifie("texte corrige", r[0]["text"].startswith("Il y a un comité"), r[0]["text"])

# 5. garde-fou de fidelite
from difflib import SequenceMatcher
origine = "ils vont etre reevalues avant d etre accordes"
reecrit = "Les propositions seront examinees par le comite competent."
verifie("reecriture rejetee", SequenceMatcher(None, origine, reecrit).ratio() < relecture.FIDELITE_MIN,
        f"{SequenceMatcher(None, origine, reecrit).ratio():.2f}")
correcte = "Ils vont être réévalués avant d'être accordés."
verifie("correction acceptee", SequenceMatcher(None, origine, correcte).ratio() >= relecture.FIDELITE_MIN,
        f"{SequenceMatcher(None, origine, correcte).ratio():.2f}")

# 6. fenetres couvrantes
vues = set()
for _, d, f in relecture._fenetres(40):
    vues.update(range(d, f))
verifie("fenetres couvrantes", vues == set(range(40)), sorted(set(range(40)) - vues))

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
