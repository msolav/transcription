"""Contrôle d'un fournisseur vivant, contre la véritable API.

Ne tourne que si une clé est disponible (ANTHROPIC_API_KEY, le trousseau,
ou l'ancien fichier). Sans clé, il s'annonce ignoré plutôt que réussi :
un contrôle qu'on n'a pas pu faire n'est pas un contrôle qui passe.

Ce qu'il vérifie et que rien d'autre ne peut vérifier hors ligne : que la
requête telle qu'on la construit est acceptée, que la sortie structurée
rend bien un JSON conforme au schéma, et qu'un transcript entier passe en
un seul appel."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import fournisseurs as f, config

# Le fournisseur à éprouver se choisit en argument ; par défaut, le
# premier dont une clé est disponible.
demande = sys.argv[1] if len(sys.argv) > 1 else ""
CHOIX = {"anthropic": "claude-haiku-5-5", "google": "gemini-flash-lite",
         "groq": "gpt-oss-20b"}
if demande:
    candidats = [demande]
else:
    candidats = [x for x in CHOIX if config.get_key(x)]
cle = fournisseur = ""
for nom in candidats:
    if config.get_key(nom):
        cle, fournisseur = config.get_key(nom), nom
        break
if not cle:
    print("IGNORÉ : aucune clé disponible pour " + (demande or "aucun fournisseur"))
    for nom, fiche in config.FOURNISSEURS.items():
        etat = "présente" if config.get_key(nom) else "absente"
        print(f"  {fiche['nom']:20s} {etat:9s} ({fiche['env']})")
    print("  Pour en éprouver un : export <VARIABLE>=... puis relancer.")
    sys.exit(0)
modele = CHOIX[fournisseur]
print(f"fournisseur éprouvé : {config.FOURNISSEURS[fournisseur]['nom']} "
      f"({f.fiche(modele)['nom']})\n")

ok = rate = 0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {d}"))
    ok += cond; rate += not cond

BLOCS = [
 ("Vincent", "selon la nature de l'activité vous allez recevoir des propositions "
             "ils vont être réévalués avant d'être"),
 ("Annie",   "accordés exactement vous"),
 ("Vincent", "allez faire ça à l'interne par l'IMER, blablabla Tout à fait."),
 ("Annie",   "Un peu comme avec Milton Park."),
]
lignes = "\n".join(f"[{i}] {q} : {t}" for i, (q, t) in enumerate(BLOCS))

from transcripteur.relecture import SYSTEME_ATTRIBUTION
req = f"Personnes présentes : Annie, Vincent\n\n{lignes}"

try:
    brut = f.appeler(cle, modele, SYSTEME_ATTRIBUTION, req,
                     schema=f.SCHEMA_ATTRIBUTION)
    v("la requête est acceptée", bool(brut), repr(brut)[:80])
    d = f.lire_json(brut)
    v("la réponse est du JSON", isinstance(d, dict))
    v("elle suit le schéma", isinstance(d.get("blocs"), list), d)
    verdicts = d.get("blocs", [])
    v("un verdict par bloc", len(verdicts) == len(BLOCS), f"{len(verdicts)}/{len(BLOCS)}")
    v("chaque verdict nomme un locuteur connu",
      all(x.get("locuteur") in {"Annie", "Vincent"} for x in verdicts), verdicts)
    v("aucun champ hors schéma",
      all(set(x) <= {"bloc", "locuteur", "deplacer"} for x in verdicts), verdicts)
    corrige = [x for x in verdicts
               if x.get("deplacer") or (x.get("locuteur") != BLOCS[x["bloc"]][0]
                                        if isinstance(x.get("bloc"), int)
                                        and x["bloc"] < len(BLOCS) else False)]
    print(f"\n  {len(corrige)} correction(s) proposée(s) sur cet extrait "
          f"(quatre erreurs y sont connues) :")
    for x in corrige:
        print(f"      bloc {x['bloc']} -> {x.get('locuteur')}"
              + (f", déplacer {x['deplacer']} mot(s)" if x.get("deplacer") else ""))
except Exception as exc:
    v("la requête est acceptée", False, str(exc)[:200])

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
