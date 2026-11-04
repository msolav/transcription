"""Contrôles du relevé mécanique des dates, heures et montants.

Aucun modèle, aucun réseau : c'est précisément l'intérêt de ce relevé.
Il répond au seul défaut mesuré des comptes rendus — une réunion se
corrige en parlant (« C'était le 24 ? — Non, le 17 »), et le modèle
retient parfois la version abandonnée. Ici les deux mentions figurent,
dans l'ordre, avec ce qui les entoure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import relecture

ok = rate = 0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {d}"))
    ok += cond; rate += not cond

def bloc(texte, t0, pas=0.4):
    mots = texte.split()
    return {"speaker": "SPEAKER_00", "start": t0, "end": t0 + len(mots) * pas,
            "words": [{"start": t0 + i * pas, "end": t0 + i * pas + 0.3, "text": m}
                      for i, m in enumerate(mots)], "text": texte}

BLOCS = [
    bloc("on se voit le 24 novembre pour la rencontre", 0.0),
    bloc("c'etait le 24 ? non, le 17. le 17 ? oui, deux semaines", 3600.0),
    bloc("l'adhesion est a 5 dollars par annee et on ouvre a 14h", 7200.0),
    bloc("mardi le 1er decembre a 14h il y a une journee de reflexion", 9000.0),
]
r = relecture.reperes(BLOCS)
val = [x["valeur"].lower() for x in r]

v("les dates sont relevées", any("24 novembre" in x for x in val), val)
v("la correction l'est aussi", any("17" in x for x in val), val)
v("les deux mentions coexistent",
  any("24 novembre" in x for x in val) and any("17" in x for x in val))
v("un montant est relevé", any("5" in x and "dollar" in x for x in val), val)
v("une heure est relevée", any("14" in x and "h" in x for x in val), val)
v("un jour de semaine est relevé", any("mardi" in x for x in val), val)

v("le relevé suit l'ordre du temps",
  all(r[i]["seconde"] <= r[i + 1]["seconde"] for i in range(len(r) - 1)))
v("les horodatages ne sont pas tous nuls",
  len({round(x["seconde"]) for x in r}) > 1, {round(x["seconde"]) for x in r})
v("chaque repère porte son contexte", all(len(x["extrait"]) > 20 for x in r))
v("le contexte contient la valeur",
  all(x["valeur"].split()[0].lower() in x["extrait"].lower() for x in r))

# la forme mecanique ne doit toucher ni cle ni reseau
appels = []
relecture.fournisseurs.appeler = lambda *a, **k: appels.append(1) or "ne devrait pas"
texte = relecture.resumer(BLOCS, {}, "", "reperes", "gemini-flash-lite")
v("aucun appel au modèle", not appels, f"{len(appels)} appel(s)")
v("fonctionne sans clé", "24 novembre" in texte and "17" in texte)
v("les horodatages sont rendus", ":" in texte and "**" in texte)

# un transcript d'un seul bloc doit quand meme donner des horodatages
un_seul = [bloc(" ".join(b["text"] for b in BLOCS), 0.0)]
r2 = relecture.reperes(un_seul)
v("un transcript d'un seul bloc reste horodaté",
  len({round(x["seconde"]) for x in r2}) > 1, {round(x["seconde"]) for x in r2})

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
