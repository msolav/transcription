"""Contrôles de la passe de texte : troncature, scission, contexte.

Les doublures acceptent **k : elles se sont brisées deux fois parce que
la signature de _appeler avait gagné un paramètre.

Aucun appel réseau : le client Groq est remplacé par des doublures."""
import sys, json
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from transcripteur import relecture as r

TRONQUE = ("Error code: 400 - {'error': {'message': \"Failed to validate JSON. Please adjust "
           "your prompt.\", 'code': 'json_validate_failed', 'failed_generation': ''}}")
def bloc(sp, t, t0):
    m=t.split()
    return {"speaker": sp, "start": t0, "end": t0+len(m)*.4,
            "words":[{"start":t0+i*.4,"end":t0+i*.4+.35,"text":w} for i,w in enumerate(m)],
            "text": t}
blocs=[bloc("SPEAKER_00", f"phrase numero {i} de la reunion", i*10) for i in range(10)]

ok=rate=0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ")+nom+("" if cond else f"  -> {d}"))
    ok+=cond; rate+=not cond

v("un JSON tronque est reconnu", r._tronque(RuntimeError(TRONQUE)))
v("un 429 n'est pas pris pour une troncature", not r._tronque(RuntimeError("429 rate_limit")))

# echoue tant que la fenetre depasse 3 blocs : doit se scinder puis reussir
tailles=[]
def capricieux(api_key, modele, systeme, requete, **k):
    n=requete.count("\n")+1
    tailles.append(n)
    if n > 3: raise RuntimeError(TRONQUE)
    return json.dumps({"blocs":[]})
r._appeler = capricieux
notes=[]
res = r.corriger_texte(blocs, "k", note=notes.append)
v("la fenetre trop longue est scindee, pas perdue", res == [] and any(t<=3 for t in tailles),
  f"tailles demandees : {tailles}")
v("la scission est signalee", any("coupée en deux" in n for n in notes), notes)
v("aucune fenetre annoncee ignoree", not any("ignorée" in n for n in notes), notes)

# echec permanent : on abandonne apres deux scissions, sans boucler
appels=[]
def toujours(api_key, modele, systeme, requete, **k):
    appels.append(1); raise RuntimeError(TRONQUE)
r._appeler = toujours
notes.clear()
res = r.corriger_texte(blocs[:4], "k", note=notes.append)
v("un echec permanent finit par renoncer", res == [] and any("ignorée" in n for n in notes), notes)
v("la recursion est bornee", len(appels) <= 8, f"{len(appels)} appels")

# le contexte remonte bien dans la requete
recu=[]
def espion(api_key, modele, systeme, requete, **k):
    recu.append(requete); return json.dumps({"blocs":[]})
r._appeler = espion
r.corriger_texte(blocs[:2], "k", contexte="AEPP = Association des entreprises")
v("le contexte atteint le modele", any("AEPP = Association" in x for x in recu))
r.corriger_texte(blocs[:2], "k")
v("sans contexte, rien n'est ajoute", not recu[-1].startswith("Contexte"))

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
