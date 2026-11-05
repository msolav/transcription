"""
Contrôles de la mémoire : ce qui est rangé, et ce à quoi elle s'accroche.

Une séance perdue ne se remarque pas tout de suite. On s'en aperçoit le
lendemain, devant une liste vide, quand il est trop tard pour refaire
les trois quarts d'heure de calcul — et on ne sait même pas si elle a
été mal rangée ou jamais rangée. D'où des contrôles sur l'aller-retour
complet : ce qui ressort de la base doit être ce qui y est entré, aux
accents et aux horodatages près.

Et les accroches, comme pour l'aperçu. seances.js lit trois variables de
l'interface et enveloppe une fonction. Les renommer de l'autre côté ne
lèverait rien : la liste resterait vide, les réglages ne reviendraient
pas, et rien ne le dirait.
"""
import os
import re
import sys
import tempfile
from pathlib import Path

from . import memoire, server

fails = []


def ok(nom, condition, detail=""):
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        fails.append(nom)


def sans_commentaires(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


STATIC = Path(__file__).parent / "static"
js = sans_commentaires((STATIC / "seances.js").read_text(encoding="utf-8"))

# ------------------------------------------------------- l'aller-retour

bac = Path(tempfile.mkdtemp(prefix="verif-memoire-"))
memoire.utiliser_dossier(bac)
memoire.preparer()

mots = [{"start": round(i * 0.37, 2), "end": round(i * 0.37 + 0.3, 2),
         "text": f"mot{i}"} for i in range(4000)]
blocs = [{"speaker": "SPEAKER_00", "start": 0.0, "end": 1480.0,
          "text": "Déjà vu, ça coûte 5 $ — « oui ».", "words": mots},
         {"speaker": "SPEAKER_01", "start": 1480.0, "end": 1600.0,
          "text": "D'accord.", "words": mots[:20]}]
job = {"id": "essai01", "filename": "Réunion du 3 — CA.mp4",
       "source": "", "duration": 1600.0, "video": True,
       "created_at": "2026-11-03T14:00:00+00:00",
       "speakers": [{"id": "SPEAKER_00", "index": 0},
                    {"id": "SPEAKER_01", "index": 1}],
       "blocks": blocs, "names": {"SPEAKER_00": "Amélie Côté"},
       "relecture": {"blocks": [], "corrections": [{"i": 2}]}}
memoire.enregistrer(job)
revenu = memoire.charger("essai01")

ok("la séance se recharge", revenu is not None)
ok("le nom du fichier garde ses accents et son tiret",
   revenu["filename"] == job["filename"], revenu["filename"])
ok("le texte est rendu caractère pour caractère",
   revenu["blocks"][0]["text"] == blocs[0]["text"], revenu["blocks"][0]["text"])
ok("tous les mots horodatés reviennent",
   sum(len(b["words"]) for b in revenu["blocks"])
   == sum(len(b["words"]) for b in blocs))
ok("les horodatages ne sont pas arrondis",
   revenu["blocks"][0]["words"][3]["start"] == mots[3]["start"],
   f"{revenu['blocks'][0]['words'][3]['start']} au lieu de {mots[3]['start']}")
ok("les noms donnés reviennent",
   revenu["names"] == job["names"], str(revenu["names"]))
ok("la relecture revient", revenu["relecture"] == job["relecture"])
ok("la date de création est conservée",
   revenu["created_at"] == job["created_at"], revenu["created_at"])
ok("une séance rouverte est déclarée terminée",
   revenu["status"] == "done" and revenu["progress"] == 1.0)

# Enregistrer deux fois ne doit pas créer deux séances : l'interface
# appelle à chaque nom tapé.
job["names"]["SPEAKER_01"] = "Thomas"
memoire.enregistrer(job)
memoire.enregistrer(job)
ok("réenregistrer ne duplique pas", len(memoire.liste()) == 1,
   str(len(memoire.liste())))
ok("la mise à jour est prise", memoire.charger("essai01")["names"]
   .get("SPEAKER_01") == "Thomas")

# Une séance sans transcript n'a rien à ranger : la ranger ferait une
# ligne vide dans la liste, qu'on ne pourrait ni rouvrir ni comprendre.
memoire.enregistrer({"id": "vide", "filename": "x", "blocks": []})
ok("une séance sans transcript n'est pas rangée",
   memoire.charger("vide") is None)

# Un enregistrement qui n'est plus sur le disque doit être déclaré
# absent, sinon l'interface propose un aperçu qui ne montrera rien.
job["source"] = "/chemin/qui/nexiste/pas.mp4"
memoire.enregistrer(job)
ok("un enregistrement disparu est signalé absent",
   not memoire.liste()[0]["audio_present"])
ok("et la séance rouverte le dit", memoire.charger("essai01")["sans_audio"])
ok("sans enregistrement, pas d'aperçu vidéo annoncé",
   not memoire.charger("essai01")["video"])

ok("la séance s'efface", memoire.oublier("essai01"))
ok("et ne revient pas", memoire.charger("essai01") is None)
ok("effacer une séance inconnue ne lève rien",
   memoire.oublier("jamais-vue") is False)

# ---------------------------------------------------------- les réglages

ok("les réglages par défaut sont complets",
   set(memoire.reglages()) == set(memoire.DEFAUTS))
ok("le nombre de voix tient dans un seul réglage",
   "count" in memoire.DEFAUTS and "diarize" not in memoire.DEFAUTS,
   str(sorted(memoire.DEFAUTS)))
memoire.retenir({"language": "fr", "count": "3", "inconnu": "x"})
r = memoire.reglages()
ok("un réglage connu est retenu", r["language"] == "fr" and r["count"] == "3")
ok("un réglage inconnu est ignoré sans tout faire échouer", "inconnu" not in r)
ok("les autres réglages gardent leur valeur par défaut",
   r["denoise"] == memoire.DEFAUTS["denoise"])

memoire.utiliser_dossier(None)

# ------------------------------------------------------ où vivent les données

# Hors du dossier du programme : une réinstallation, une mise à jour ou
# un `git clean` effacerait sinon toutes les séances d'un coup.
depot = Path(__file__).resolve().parent.parent
ok("les données vivent hors du dépôt",
   depot not in memoire.dossier().resolve().parents
   and memoire.dossier().resolve() != depot,
   str(memoire.dossier()))
ok("le dossier porte un nom reconnaissable",
   memoire.dossier().name == "Transcripteur", str(memoire.dossier()))

os.environ["TRANSCRIPTEUR_DONNEES"] = "/tmp/essai-donnees"
ok("la variable d'environnement passe devant",
   str(memoire.dossier()) == "/tmp/essai-donnees", str(memoire.dossier()))
del os.environ["TRANSCRIPTEUR_DONNEES"]

# ------------------------------------------------------------ les routes

chemins = {getattr(r, "path", "") for r in server.app.routes}
for route in ("/api/reglages", "/api/seances", "/api/seances/{seance_id}",
              "/api/seances/{seance_id}/audio"):
    ok(f"la route {route} existe", route in chemins)

ok("seances.js est posé dans les pages", "seances.js" in server._GREFFES)

# ------------------------------------------------- ce que la page prête

# Lus par leur nom nu : ce sont des `let` du premier niveau, qui vivent
# dans l'environnement lexical global et non sur window.
VARIABLES = ("job", "jobId", "names")
# Enveloppée : déclaration `function`, donc propriété de window.
FONCTIONS = ("render",)
# Commandes que les deux interfaces doivent avoir. #count est le seul
# endroit où le nombre de voix existe vraiment : c'est lui que lit le
# formulaire, et lui seul qu'il faut rétablir pour que le traitement
# reparte sur le bon réglage.
COMMANDES = ("count", "lang", "emb", "clean", "go")
# L'interrupteur, les pastilles et le nombre vers lequel l'interrupteur
# revient : les commandes visibles de la refonte, absentes de l'ancienne
# interface qui réglait #count en direct. Elles vont ensemble — en
# rétablir une sans les autres laisserait l'écran contredire le
# formulaire — d'où un contrôle sur le groupe plutôt que sur chacune.
TRIO = ("sep", "numchips")

ok("seances.js ne cherche pas les variables sur window",
   not re.search(r"window\.(job|jobId|names|lastN)\b", js))
for c in TRIO:
    ok(f"seances.js sait régler #{c}", f"#{c}" in js)
for c in COMMANDES:
    ok(f"seances.js emprunte #{c}", f"'#{c}'" in js or f'"#{c}"' in js
       or f"#{c}" in js)

for nom in ("index.html", "index-vm.html"):
    page = STATIC / nom
    if not page.exists():
        continue
    html = page.read_text(encoding="utf-8")
    for v in VARIABLES:
        ok(f"{nom} : {v} est déclaré au premier niveau",
           re.search(rf"(?:^|[,(\s])(?:let|var|const)\s[^;]*\b{v}\b", html,
                     re.M) is not None)
    for f in FONCTIONS:
        ok(f"{nom} : {f} est une déclaration de fonction",
           re.search(rf"^function\s+{f}\s*\(", html, re.M) is not None,
           "déclarée autrement, elle n'est plus enveloppable")
    for c in COMMANDES:
        ok(f"{nom} : #{c} existe", f'id="{c}"' in html)
    # Tout ou rien : l'interrupteur, les pastilles et `lastN` forment un
    # seul mécanisme. En garder deux sur trois après une refonte
    # donnerait un écran qui affiche un réglage et un formulaire qui en
    # envoie un autre — la panne la plus difficile à voir de toutes,
    # puisque les deux ont l'air corrects séparément.
    presents = [c for c in TRIO if f'id="{c}"' in html]
    presents += (["lastN"] if re.search(r"\blet\s+lastN\b", html) else [])
    ok(f"{nom} : les commandes visibles du nombre de voix vont ensemble",
       len(presents) in (0, len(TRIO) + 1),
       f"présentes : {presents or 'aucune'}")
    if presents:
        ok(f"{nom} : elles écrivent bien dans #count",
           re.search(r"setCount\s*\(", html) is not None)
    # Le nombre de voix doit rester dans un <select> : les deux
    # commandes visibles y écrivent, et c'est lui que lit le formulaire.
    ok(f"{nom} : #count est une liste de choix",
       re.search(r"<select[^>]*id=\"count\"", html) is not None)
    ok(f"{nom} : « ne pas séparer » s'écrit none",
       re.search(r"<select[^>]*id=\"count\".*?value=\"none\"", html,
                 re.S) is not None)
    # Le point d'ancrage de la liste des séances.
    ok(f"{nom} : la rangée de dépôt existe",
       'class="pickrow"' in html or 'id="dropzone"' in html)

print(f"\n{'MÉMOIRE CONFORME' if not fails else str(len(fails)) + ' PROBLÈME(S)'}")
sys.exit(1 if fails else 0)
