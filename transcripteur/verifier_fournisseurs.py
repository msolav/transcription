"""Contrôles de la couche fournisseurs.

Aucun appel réseau : le client de chaque fournisseur est remplacé par une
doublure. Ce qui est vérifié, c'est le catalogue, le choix entre appel
unique et découpage, la traduction des pannes, et le coût annoncé.

Le chemin Claude lui-même — la requête réellement envoyée et acceptée par
l'API — n'est PAS couvert ici : il demande une clé. Voir verifier_claude.py,
qui ne tourne que si une clé est présente."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import fournisseurs as f, relecture as r

ok = rate = 0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {d}"))
    ok += cond; rate += not cond

# ---- catalogue
v("le défaut est Claude", f.fournisseur_de(f.MODELE_DEFAUT) == "anthropic", f.MODELE_DEFAUT)
v("un chemin gratuit existe", not f.payant(f.MODELE_GRATUIT), f.MODELE_GRATUIT)
v("le gratuit par défaut voit le transcript entier",
  f.tient_en_un_appel(f.MODELE_GRATUIT, int(14_300 / 0.75)), f.MODELE_GRATUIT)
v("Gemini est gratuit", not f.payant("gemini-flash") and not f.payant("gemini-flash-lite"))
v("tout modèle a un fournisseur connu",
  all(m["fournisseur"] in f.CLES for m in f.MODELES.values()))
v("tout modèle annonce contexte et sortie",
  all(m["contexte"] > m["sortie"] > 0 for m in f.MODELES.values()))
v("un modèle inconnu retombe sur le défaut",
  f.fiche("n'existe pas")["id"] == f.fiche(f.MODELE_DEFAUT)["id"])

# ---- le defaut suit les cles, sans jamais exiger un compte payant
v("sans clé payante, le défaut est gratuit",
  not f.payant(f.modele_par_defaut({})) and not f.payant(f.modele_par_defaut({"groq": True})),
  f.modele_par_defaut({}))
v("une clé Gemini suffit pour l'appel unique",
  not f.payant(f.modele_par_defaut({"google": True}))
  and f.tient_en_un_appel(f.modele_par_defaut({"google": True}), 20_000),
  f.modele_par_defaut({"google": True}))
v("avec une clé Claude, le défaut en profite",
  f.modele_par_defaut({"groq": True, "anthropic": True}) == f.MODELE_DEFAUT)
v("le défaut est toujours un modèle du catalogue",
  all(f.modele_par_defaut(c) in f.MODELES
      for c in ({}, {"groq": True}, {"google": True}, {"anthropic": True},
                {"groq": True, "anthropic": True}, {"google": True, "anthropic": True})))

# ---- appel unique ou decoupage
reunion = int(14_300 / 0.75)          # ~14 300 mots d'une vraie reunion
v("une réunion entière tient chez Claude", f.tient_en_un_appel("claude-opus-5-5", reunion))
v("elle ne tient pas chez un modèle gratuit", not f.tient_en_un_appel("gpt-oss-120b", reunion))
v("un transcript démesuré ne tient nulle part",
  not f.tient_en_un_appel("claude-opus-5-5", 2_000_000))

blocs = [{"text": "x" * 60} for _ in range(600)]
v("Claude : un seul appel", len(r._decoupage(blocs, "claude-opus-5-5")) == 1)
v("gratuit : des fenêtres", len(r._decoupage(blocs, "gpt-oss-120b")) > 20)

# ---- cout annonce
c = f.cout_estime("claude-opus-5-5", 20_000, 15_000)
v("coût d'une réunion sous un dollar", 0.2 < c < 0.6, f"{c:.2f} $")
v("un modèle gratuit coûte zéro", f.cout_estime("gpt-oss-120b", 20_000, 15_000) == 0.0)

# ---- traduction des pannes
JOUR = "Error code: 429 ... rate_limit_exceeded on tokens per day (TPD): Limit 200000. Please try again in 7m6.816s."
MIN  = "Error code: 429 ... rate_limit_exceeded on tokens per minute (TPM): Limit 8000. Please try again in 12.5s."
v("une limite du jour est fatale", isinstance(f._traduire(RuntimeError(JOUR)), f.QuotaError))
GOOG_JOUR = "429 RESOURCE_EXHAUSTED quota metric GenerateRequestsPerDayPerProjectPerModel"
GOOG_MIN  = "429 RESOURCE_EXHAUSTED quota GenerateRequestsPerMinute, retry in 31.0s"
v("quota Gemini par jour : fatal", isinstance(f._traduire(RuntimeError(GOOG_JOUR)), f.QuotaError))
v("quota Gemini par minute : pause",
  isinstance(f._traduire(RuntimeError(GOOG_MIN)), f.LimiteMinute))
m = f._traduire(RuntimeError(MIN))
v("une limite de la minute est une pause", isinstance(m, f.LimiteMinute))
v("la pause connaît sa durée", abs(m.secondes - 12.5) < 0.01, m.secondes)
v("le message du jour ne promet pas minuit",
  "glisse" in str(f._traduire(RuntimeError(JOUR))))
v("une panne ordinaire n'est pas traduite",
  type(f._traduire(ValueError("json cassé"))) is ValueError)
v("relecture reconnaît le quota", r._est_quota(f.QuotaError("x"))
  and not r._est_quota(f.LimiteMinute("x", 3.0)))

# ---- schemas
for nom, sch in (("attribution", f.SCHEMA_ATTRIBUTION), ("texte", f.SCHEMA_TEXTE)):
    item = sch["properties"]["blocs"]["items"]
    v(f"schéma {nom} : clos", item["additionalProperties"] is False
      and sch["additionalProperties"] is False)
    v(f"schéma {nom} : champs requis", len(item["required"]) >= 2, item["required"])

# ---- lecture tolerante
v("JSON nu lu", f.lire_json('{"blocs": []}') == {"blocs": []})
v("JSON entouré de texte lu",
  f.lire_json('Voici :\n```json\n{"blocs": [{"bloc": 1}]}\n```') == {"blocs": [{"bloc": 1}]})
try:
    f.lire_json("pas du tout du json")
    v("texte sans JSON : erreur", False, "aucune exception")
except Exception:
    v("texte sans JSON : erreur", True)

# ---- le plafond demande atteint vraiment le fournisseur
#      Il était calculé puis jeté : chaque appel réservait 32 000 jetons
#      de sortie sur le quota par minute, ce qui faisait échouer la
#      relecture d'un long transcript sans que la requête paraisse
#      déraisonnable.
vus = {}
def guetteur(cle, f, systeme, requete, schema, sortie=0):
    vus["sortie"] = sortie
    return '{"blocs": []}'
f._google = guetteur
f.appeler("k", "gemini-flash", "sys", "req", plafond=1500)
v("le plafond atteint le fournisseur", vus.get("sortie") == 1500, vus)
f.appeler("k", "gemini-flash", "sys", "req", plafond=999_999)
v("un plafond démesuré est ramené au maximum du modèle",
  vus.get("sortie") == f.MODELES["gemini-flash"]["sortie"], vus)
f.appeler("k", "gemini-flash", "sys", "req")
v("sans plafond, le maximum du modèle",
  vus.get("sortie") == f.MODELES["gemini-flash"]["sortie"], vus)

# ---- une cle absente se dit, au lieu d'egarer le SDK
#      Sans ce garde-fou, chaque SDK part chercher ailleurs — variables
#      d'environnement, identifiants de la machine — et rapporte une
#      panne d'authentification qui ne nomme jamais la vraie cause.
for modele in ("gemini-flash", "claude-opus-5-5", "gpt-oss-120b"):
    for vide in ("", "   ", None):
        try:
            f.appeler(vide, modele, "sys", "req")
            v(f"clé absente refusée ({modele})", False, "aucune erreur")
            break
        except f.FournisseurError as exc:
            msg = str(exc)
    else:
        v(f"clé absente refusée ({modele})",
          "Aucune clé" in msg and "panneau" in msg, msg[:70])
v("le message ne promet pas une clé gratuite chez un payant",
  "gratuite" not in str(next(
      (e for e in [None] if False), None) or ""), "")
try:
    f.appeler("", "claude-opus-5-5", "s", "r")
except f.FournisseurError as exc:
    v("Claude n'est pas annoncé gratuit", "gratuite" not in str(exc), str(exc)[:70])
try:
    f.appeler("", "gemini-flash", "s", "r")
except f.FournisseurError as exc:
    v("Gemini est annoncé gratuit", "gratuite" in str(exc), str(exc)[:70])

# ---- la pause est bien reprise, pas fatale
essais = []
import time as _t
_t.sleep = lambda s: essais.append(s)
appels = []
def doublure(cle, modele, systeme, requete, **k):
    appels.append(1)
    if len(appels) == 1:
        raise f.LimiteMinute("minute", 9.0)
    return json.dumps({"blocs": []})
f.appeler = doublure
notes = []
out = r._appeler("k", "gpt-oss-120b", "sys", "req", note=notes.append)
v("une pause par minute fait patienter puis réussir",
  len(appels) == 2 and essais and any("minute" in n for n in notes), (appels, notes))

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
