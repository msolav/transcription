"""Contrôles des limites de débit : par minute on patiente, par jour on
s'arrête. Aucun appel réseau, le client Groq est remplacé."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from transcripteur import relecture as r

JOUR = "429 rate_limit_exceeded ... on tokens per day (TPD): Limit 200000. Please try again in 1h21m9.936s."
MIN  = "429 rate_limit_exceeded ... on tokens per minute (TPM): Limit 8000. Please try again in 12.5s."
ok=rate=0
def v(n,c,d=""):
    global ok,rate
    print(("  ok   " if c else "  RATE ")+n+("" if c else "  -> "+str(d))); ok+=c; rate+=not c

v("limite par jour reconnue", r._genre_limite(RuntimeError(JOUR))=="jour")
v("limite par minute reconnue", r._genre_limite(RuntimeError(MIN))=="minute")
v("seule celle du jour est fatale",
  r._est_quota(RuntimeError(JOUR)) and not r._est_quota(RuntimeError(MIN)))
v("delai converti en secondes", abs(r._secondes(RuntimeError(MIN))-12.5)<0.01, r._secondes(RuntimeError(MIN)))
v("delai en heures converti", abs(r._secondes(RuntimeError(JOUR))-4869.936)<1, r._secondes(RuntimeError(JOUR)))

# une limite par minute doit patienter puis reussir, pas tout abandonner
essais=[]
import time as _t
_t.sleep = lambda s: essais.append(s)
def capricieux(*a, **k):
    essais.append("appel")
    if essais.count("appel")==1: raise RuntimeError(MIN)
    return json.dumps({"corrections":[]})
r._appeler_une_fois = capricieux
notes=[]
def bloc(sp,t,t0):
    m=t.split()
    return {"speaker":sp,"start":t0,"end":t0+len(m)*.4,
            "words":[{"start":t0+i*.4,"end":t0+i*.4+.35,"text":w} for i,w in enumerate(m)],"text":t}
blocs=[bloc("SPEAKER_00", f"phrase {i} de la reunion", i*10) for i in range(5)]
res = r.corriger_attribution(blocs, {"SPEAKER_00":"Annie"}, "k", note=notes.append)
v("la limite par minute fait patienter, pas abandonner",
  essais.count("appel")==2 and any(isinstance(x,float) for x in essais), essais)
v("l'attente est annoncee", any("minute" in n for n in notes), notes)

# la limite du jour, elle, arrete tout des le premier refus
appels=[]
def refus(*a, **k):
    appels.append(1); raise RuntimeError(JOUR)
r._appeler_une_fois = refus
r.modeles_disponibles = lambda k: []
try:
    r.corriger_attribution(blocs, {"SPEAKER_00":"Annie"}, "k")
    v("la limite du jour arrete tout", False, "aucune exception")
except r.QuotaError as e:
    v("la limite du jour arrete tout", len(appels)==1, f"{len(appels)} appels")
    v("le message ne promet pas d'alternative qui n'existe pas",
      "epuises" in str(e).replace("é","e").replace("è","e") or "aussi" in str(e), str(e))
r.modeles_disponibles = lambda k: ["Qwen 3.6 27B"]
appels.clear()
try: r.corriger_attribution(blocs, {"SPEAKER_00":"Annie"}, "k")
except r.QuotaError as e:
    v("quand un modele reste libre, il est nomme", "Qwen 3.6 27B" in str(e), str(e))

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
