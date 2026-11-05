"""
Contrôles de l'aperçu vidéo et de ses accroches dans l'interface.

apercu.js est posé par le serveur dans les pages, et emprunte à
l'interface une poignée de points d'appui : des identifiants, trois
fonctions qu'il enveloppe, trois variables qu'il lit. Les renommer de
l'autre côté — ce qui arrive à chaque refonte — ne lèverait aucune
erreur. L'aperçu ne s'afficherait simplement plus, ou s'afficherait sans
sous-titres, et il faudrait s'en apercevoir.

C'est déjà arrivé deux fois en écrivant ce fichier. Une première fois
parce qu'un commentaire de l'interface mentionnait « apercu.js », ce qui
suffisait à faire croire au serveur que le script était déjà posé — il
n'était alors chargé nulle part. Une seconde parce que `job`, `jobId` et
`objectUrl` sont déclarés par un `let` : ils vivent dans l'environnement
lexical global, mais ne sont pas des propriétés de window, et le code
écrit `window.job` croyait qu'aucun traitement n'était chargé. Aucune
des deux pannes n'a produit le moindre message.
"""
import re
import sys
from pathlib import Path

from . import pipeline, server, sous_titres

fails = []


def ok(nom, condition, detail=""):
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        fails.append(nom)


STATIC = Path(__file__).parent / "static"
js = (STATIC / "apercu.js").read_text(encoding="utf-8")


def sans_commentaires(source: str) -> str:
    """Le code seul.

    Un contrôle qui lit aussi les commentaires se trompe dans les deux
    sens : il accuse un commentaire qui cite la tournure interdite —
    c'est arrivé ici même — et il absout du code fautif dont un
    commentaire voisin dit le contraire."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


code = sans_commentaires(js)

# ------------------------------------------------- la pose par le serveur

ok("apercu.js est dans la liste des greffes", "apercu.js" in server._GREFFES)
for nom in ("index.html", "index-vm.html"):
    page = STATIC / nom
    if not page.exists():
        continue
    html = page.read_text(encoding="utf-8")
    # La recherche porte sur la balise et non sur le nom du fichier :
    # un commentaire qui cite « apercu.js » ferait sauter la pose.
    rendu = server._page(nom).body.decode("utf-8")
    for greffe in server._GREFFES:
        ok(f"{nom} : {greffe} est posé une seule fois",
           rendu.count(f'src="/static/{greffe}"') == 1,
           f"{rendu.count(f'src=/static/{greffe}')} fois")

# ------------------------------------------------- ce que la page prête

# Identifiants empruntés.
EMPRUNTS = ("player", "dock")
# Variables lues. Déclarées par un `let` : lisibles par leur nom nu,
# absentes de window. apercu.js doit donc les lire sans préfixe.
VARIABLES = ("job", "jobId", "objectUrl")
# Fonctions enveloppées. Déclarées par `function` : propriétés de window,
# donc réassignables — c'est ce qui permet de les envelopper.
FONCTIONS = ("setupDeck", "queueSave", "exportAs")

for ident in EMPRUNTS:
    ok(f"apercu.js lit #{ident}", f"'{ident}'" in code or f'"{ident}"' in code)

ok("apercu.js ne cherche pas les variables sur window",
   not re.search(r"window\.(job|jobId|objectUrl)\b", code),
   "window.job / window.jobId / window.objectUrl : toujours undefined")
ok("apercu.js s'abstient quand le lecteur n'est pas un <video>",
   "tagName !== 'VIDEO'" in code or 'tagName !== "VIDEO"' in code)

for nom in ("index.html", "index-vm.html"):
    page = STATIC / nom
    if not page.exists():
        continue
    html = page.read_text(encoding="utf-8")

    for ident in EMPRUNTS:
        ok(f"{nom} : #{ident} existe", f'id="{ident}"' in html)

    # Le lecteur doit être un <video>. En <audio>, tout continue de
    # fonctionner — sauf l'image, qui ne s'affiche jamais, sans erreur.
    ok(f"{nom} : #player est un <video>",
       re.search(r"<video[^>]*id=\"player\"", html) is not None,
       "un <audio> ne montrera jamais l'image")

    for v in VARIABLES:
        ok(f"{nom} : {v} est déclaré au premier niveau",
           re.search(rf"(?:^|[,(\s])(?:let|var|const)\s[^;]*\b{v}\b", html,
                     re.M) is not None)

    for f in FONCTIONS:
        # `function` et non `const` : une arrow function au premier
        # niveau n'est pas sur window, donc plus enveloppable.
        ok(f"{nom} : {f} est une déclaration de fonction",
           re.search(rf"^function\s+{f}\s*\(", html, re.M) is not None,
           "déclarée autrement, elle n'est plus sur window")

    # Les sous-titres doivent être atteignables depuis la barre, avec et
    # sans les noms. Les deux interfaces s'y prennent autrement : la
    # refonte a un menu déroulant où apercu.js greffe le second bouton,
    # l'ancienne a quatre boutons à plat et le porte dans son markup.
    # Ce qui compte est le résultat : les deux chemins existent.
    greffe = "savegroup" in html and re.search(r'class="sg"', html)
    ok(f"{nom} : les sous-titres sans noms sont atteignables",
       'data-x="srt"' in html)
    ok(f"{nom} : les sous-titres nommés sont atteignables",
       'data-x="srt-noms"' in html or bool(greffe),
       "ni bouton dans le markup, ni groupe où le greffer")

    # Le sélecteur de fichier doit accepter la vidéo, sinon le fichier
    # est grisé dans la fenêtre du système et paraît refusé.
    m = re.search(r'id="file"[^>]*accept="([^"]*)"', html) \
        or re.search(r'accept="([^"]*)"[^>]*id="file"', html)
    ok(f"{nom} : le sélecteur accepte la vidéo",
       m is not None and "video/" in m.group(1),
       m.group(1) if m else "pas d'attribut accept")

# ------------------------------------------------- les routes du serveur

chemins = {getattr(r, "path", "") for r in server.app.routes}
for route in ("/api/jobs/{job_id}/media",
              "/api/jobs/{job_id}/soustitres.vtt",
              "/api/jobs/{job_id}/soustitres.srt"):
    ok(f"la route {route} existe", route in chemins)

# Les adresses écrites dans le JS doivent être celles du serveur.
for bout in ("/media", "/soustitres.vtt", "/soustitres.srt"):
    ok(f"apercu.js appelle {bout}", bout in js)

# ------------------------------------------------- les formats reconnus

ok("le mp4 est reconnu comme une vidéo", pipeline.est_video(Path("a.mp4")))
ok("le MOV aussi, quelle que soit la casse", pipeline.est_video(Path("A.MOV")))
ok("un m4a n'est pas une vidéo", not pipeline.est_video(Path("a.m4a")))
ok("un wav non plus", not pipeline.est_video(Path("a.wav")))

# Chaque extension vidéo doit avoir un type MIME, sinon le navigateur
# reçoit « application/octet-stream » et refuse de lire le fichier.
sans_type = [e for e in pipeline.EXTENSIONS_VIDEO if e not in server._TYPES_MEDIA]
ok("chaque extension vidéo a son type MIME", not sans_type, str(sans_type))

# ------------------------------------------------- les réglages du format

ok("deux lignes au plus", sous_titres.LIGNES_MAX == 2)
ok("une largeur de sous-titrage courante",
   36 <= sous_titres.CHARS_PAR_LIGNE <= 44, str(sous_titres.CHARS_PAR_LIGNE))
ok("une durée minimale lisible", sous_titres.MIN_DUREE >= 1.0)
ok("une durée maximale qui ne fige pas l'écran", sous_titres.MAX_DUREE <= 7.0)
ok("les répliques ne se touchent pas", sous_titres.ECART > 0)

print(f"\n{'APERÇU CONFORME' if not fails else str(len(fails)) + ' PROBLÈME(S)'}")
sys.exit(1 if fails else 0)
