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

# 6. voix non nommees : le tour aller-retour du locuteur
#    C'est le cas qui a produit 48 blocs « Voix ? » dans un vrai transcript.
vides = {"SPEAKER_00": "", "SPEAKER_01": ""}
b = [bloc("SPEAKER_00", "ils vont etre reevalues", 0), bloc("SPEAKER_01", "avant d etre accordes", 10)]
affiche = relecture._nom(b[1], vides)
r = relecture.appliquer(b, [{"type":"locuteur","bloc":1,"avant":affiche,
                             "apres":relecture._nom(b[0], vides),
                             "apres_id":"SPEAKER_00"}], vides)
verifie("voix non nommees : identifiant conserve", r[1]["speaker"] == "SPEAKER_00", r[1]["speaker"])

# meme chose sans apres_id, comme le ferait une correction plus ancienne
r = relecture.appliquer(b, [{"type":"locuteur","bloc":1,"avant":affiche,
                             "apres":relecture._nom(b[0], vides)}], vides)
verifie("repli par le nom affiche", r[1]["speaker"] == "SPEAKER_00", r[1]["speaker"])

# un nom intraduisible ne doit rien casser
r = relecture.appliquer(b, [{"type":"locuteur","bloc":1,"avant":affiche,
                             "apres":"Quelqu un d autre"}], vides)
verifie("nom inconnu : bloc laisse tel quel", r[1]["speaker"] == "SPEAKER_01", r[1]["speaker"])

# 7. fenetres couvrantes
vues = set()
for _, d, f in relecture._fenetres(40):
    vues.update(range(d, f))
verifie("fenetres couvrantes", vues == set(range(40)), sorted(set(range(40)) - vues))

# 8. l'arret pendant la relecture
#
# Deux endroits, et deux seulement, ou la relecture passe son temps :
# l'appel au modele, et l'attente quand la limite par minute est
# atteinte. Cette attente dure de vingt a soixante-quinze secondes, et
# c'est justement la qu'on veut arreter, puisque c'est la qu'il ne se
# passe rien. Un sleep d'un bloc rendait le bouton muet pendant tout ce
# temps.
#
# Le piege verifie ici n'est pas l'arret lui-meme mais son filet : les
# boucles de relecture attrapent Exception pour qu'une fenetre en panne
# n'emporte pas tout le travail. Annulee etant une exception, elle y
# tombait, etait notee comme une fenetre ratee, et la boucle enchainait.
# Le bouton n'aurait rien fait, et rien ne l'aurait dit.
import threading
import time

BLOCS = [{"speaker": f"SPEAKER_0{i % 3}", "start": i * 5.0, "end": i * 5.0 + 4.0,
          "text": f"Replique numero {i}, assez longue pour peser.", "words": []}
         for i in range(60)]
NOMS = {"SPEAKER_00": "Karina", "SPEAKER_01": "Annie", "SPEAKER_02": "Elaine"}

_vrai_appeler = relecture.fournisseurs.appeler
_vrai_decoupage = relecture._decoupage
# Plusieurs fenetres : un transcript qui tient en un seul appel ne fait
# qu'un tour de boucle, plus court que le delai avant l'arret, et
# l'essai mesurerait la fin normale au lieu de l'arret.
relecture._decoupage = lambda blocs, modele, note=None: [
    (0, i, i + 2) for i in range(0, 100, 2)]


def _arret(nom, bouchon, plafond):
    relecture.fournisseurs.appeler = bouchon
    stop = {"v": False}
    bilan = {}

    def courir():
        t0 = time.time()
        try:
            relecture.corriger_attribution(BLOCS, NOMS, "cle", "gemini-flash",
                                           note=lambda m: None,
                                           stop=lambda: stop["v"])
            bilan["r"] = "terminee sans s'arreter"
        except relecture.Annulee:
            bilan["r"] = "Annulee"
        except Exception as exc:  # noqa: BLE001
            bilan["r"] = f"{type(exc).__name__}"
        bilan["t"] = time.time() - t0

    fil = threading.Thread(target=courir)
    fil.start()
    time.sleep(1.0)
    stop["v"] = True
    fil.join(timeout=plafond + 5)
    delai = max(bilan.get("t", 999) - 1.0, 0)
    verifie(f"arret {nom}",
            not fil.is_alive() and bilan.get("r") == "Annulee" and delai <= plafond,
            f"{bilan.get('r', 'toujours en vie')}, {delai:.2f} s")


def _lent(*a, **k):
    time.sleep(0.4)
    return '{"blocs": []}'


def _quota(*a, **k):
    raise relecture.fournisseurs.LimiteMinute("limite par minute", secondes=60.0)


_arret("pendant les appels", _lent, 1.5)
_arret("pendant une attente de quota", _quota, 1.0)

# 9. le journal dit ce qui se passe
#
# Et surtout : le decompte d'attente se recrit sur sa ligne. Empile une
# fois par seconde, il chassait tout le reste du journal en une minute,
# et il ne reste plus que « reprise dans 3 s » repete douze fois.
_lignes = []


def _note(m, remplacer=False):
    if remplacer and _lignes:
        _lignes[-1] = m
    else:
        _lignes.append(m)


relecture._decoupage = lambda b, m, n=None: [(0, i, i + 10) for i in range(0, 30, 10)]
_tours = {"n": 0}


def _repond(*a, **k):
    _tours["n"] += 1
    if _tours["n"] == 2:
        raise relecture.fournisseurs.LimiteMinute("limite", secondes=2.0)
    return ('{"blocs": [' + ",".join(
        f'{{"bloc": {j}, "locuteur": "Annie"}}' for j in range(30)) + ']}')


relecture.fournisseurs.appeler = _repond
_corr = relecture.corriger_attribution(BLOCS[:30], NOMS, "cle", "gemini-flash",
                                       note=_note)
verifie("journal : la passe s'annonce",
        any(l.startswith("attribution : 30 blocs") for l in _lignes), _lignes[:1])
verifie("journal : les corrections se comptent au fil de l'eau",
        any("correction(s) trouvee(s)" in l.replace("é", "e") for l in _lignes),
        _lignes)
verifie("journal : le decompte d'attente tient sur une seule ligne",
        sum(1 for l in _lignes if l.startswith("limite par minute")) == 1,
        [l for l in _lignes if l.startswith("limite par minute")])

relecture.fournisseurs.appeler = _vrai_appeler
relecture._decoupage = _vrai_decoupage

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
