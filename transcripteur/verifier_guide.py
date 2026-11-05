"""
Contrôles du mode d'emploi des clés : bilingue partout, et d'accord avec
le reste du code.

Deux pannes à prévenir, et aucune des deux ne se voit en relisant le
fichier. Une phrase sans traduction se révèle devant la personne à qui
on avait promis l'anglais, et seulement à cet endroit-là. Une adresse
recopiée ici cesse un jour de valoir celle de `config`, et c'est le
guide qui envoie les gens au mauvais endroit — l'erreur la plus chère de
toutes, puisque celui qui la subit n'a aucun moyen de savoir qu'il suit
une mauvaise consigne.
"""
import re
import sys

from . import config, guide

fails = []


def ok(nom, condition, detail=""):
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        fails.append(nom)


# ------------------------------------------------- bilinguisme complet

def paires(obj, chemin="") -> list[tuple[str, dict]]:
    """Tous les textes bilingues de l'arbre, avec leur chemin."""
    trouve = []
    if isinstance(obj, dict):
        if set(obj) == set(guide.LANGUES) or (
                "fr" in obj and "en" in obj and len(obj) == 2):
            return [(chemin, obj)]
        for k, v in obj.items():
            trouve += paires(v, f"{chemin}.{k}" if chemin else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            trouve += paires(v, f"{chemin}[{i}]")
    return trouve


arbre = {"notions": [guide.POURQUOI_DEUX, guide.QU_EST_CE_QU_UNE_CLE,
                     guide.PIEGE_ABONNEMENT, guide.OU_VA_LA_CLE],
         "cles": guide.CLES, "pannes": guide.PANNES, "titres": guide._TITRES}
toutes = paires(arbre)
ok(f"les {len(toutes)} textes sont des paires fr/en", bool(toutes))

vides = [c for c, p in toutes if not (p.get("fr") or "").strip()
         or not (p.get("en") or "").strip()]
ok("aucune des deux langues ne manque", not vides, ", ".join(vides[:4]))

# Une traduction oubliée se recopie le plus souvent telle quelle : deux
# versions identiques sont donc le symptôme, pas une coïncidence.
jumelles = [c for c, p in toutes if p["fr"].strip() == p["en"].strip()]
ok("aucune traduction recopiée du français", not jumelles,
   ", ".join(jumelles[:4]))

# Le français ne doit pas déborder dans l'anglais. Ces mots-là n'ont pas
# d'homographe anglais courant, donc les trouver côté anglais signale un
# fragment resté dans l'autre langue.
FRANCISMES = re.compile(
    r"\b(?:une?|des|le|la|les|du|est|sont|pour|avec|sans|qui|que|dans|"
    r"tu|ton|ta|il faut|clé|cette|cela)\b", re.I)
contamines = [c for c, p in toutes if FRANCISMES.search(p["en"])]
ok("l'anglais ne contient pas de fragment français", not contamines,
   ", ".join(contamines[:4]))

# ------------------------------------------------- les fiches sont complètes

CHAMPS = ("id", "nom", "requis", "role", "pour_quoi", "prix", "etapes",
          "limites")
for c in guide.CLES:
    manquants = [ch for ch in CHAMPS if ch not in c]
    ok(f"{c.get('id', '?')} : fiche complète", not manquants,
       ", ".join(manquants))
    ok(f"{c['id']} : connu de config", c["id"] in config.FOURNISSEURS)
    ok(f"{c['id']} : au moins trois pas", len(c.get("etapes", [])) >= 3)

# Personne ne doit être envoyé chez GitHub. Quelqu'un qui n'est pas
# développeur y arrive sur une page de versions en anglais, avec une
# liste de fichiers pour tous les systèmes, et conclut qu'il s'est
# trompé d'endroit. Le mot n'a donc rien à faire dans une marche à
# suivre — pas même comme façon de se connecter à Groq.
github = [c["id"] for c in guide.CLES if "github" in str(c).lower()]
ok("aucune fiche n'envoie chez GitHub", not github, ", ".join(github))

ok("une seule clé obligatoire",
   sum(1 for c in guide.CLES if c["requis"]) == 1)
ok("une seule clé recommandée",
   sum(1 for c in guide.CLES if c.get("recommande")) == 1)

# ---------------------------------------- l'adresse vient d'un seul endroit

for langue in guide.LANGUES:
    d = guide.pour_interface(langue)
    for c in d["cles"]:
        attendu = config.FOURNISSEURS[c["id"]]["ou"]
        ok(f"{c['id']} ({langue}) : adresse tirée de config",
           c["ou"] == attendu and c["url"] == "https://" + attendu,
           f"{c['url']} au lieu de https://{attendu}")
        # Le premier pas doit nommer l'adresse quelque part : « ouvrir la
        # console » sans dire laquelle laisse chercher dans un menu qu'on
        # ne connaît pas. Elle a quitté le geste, qui ne dit plus que
        # l'action, pour le détail — c'est là qu'il faut la trouver.
        premier = c["etapes"][0]
        ok(f"{c['id']} ({langue}) : le premier pas donne l'adresse",
           attendu in (premier["geste"] + " " + premier["detail"]),
           str(premier)[:120])

        # Le geste s'affiche seul, en grand, au milieu de l'écran : une
        # phrase qui déborde y casse la mise en page et fait défiler une
        # page qui ne doit jamais défiler. Le détail, lui, vit derrière
        # un bouton « i » et peut s'étendre.
        for n, pas in enumerate(c["etapes"]):
            manque = [ch for ch in ("geste", "detail") if not pas.get(ch)]
            ok(f"{c['id']} ({langue}) : pas {n + 1} complet", not manque,
               ", ".join(manque))
            ok(f"{c['id']} ({langue}) : pas {n + 1}, geste assez court",
               len(pas.get("geste", "")) <= 64,
               f"{len(pas.get('geste', ''))} caractères : « {pas.get('geste')} »")
        prefixes = config.FOURNISSEURS[c["id"]]["prefixe"]
        prefixes = list(prefixes) if isinstance(prefixes, tuple) else [prefixes]
        ok(f"{c['id']} ({langue}) : préfixes tirés de config",
           c["prefixes"] == prefixes)

# Rien ne doit rester sous forme de dictionnaire : `t()` oublié laisse
# un « {'fr': … } » dans l'interface, lisible et absurde.
import json as _json
for langue in guide.LANGUES:
    brut = _json.dumps(guide.pour_interface(langue), ensure_ascii=False)
    ok(f"aucun texte non résolu ({langue})", "'fr':" not in brut
       and '"fr":' not in brut.replace('"langue"', ''))

# ------------------------------------------------------ la page autonome

page = guide.page_html("fr")
ok("la page s'ouvre sur le français", page.startswith('<!doctype html>\n<html lang="fr"')
   or '<html lang="fr"' in page[:80])
ok("la page anglaise s'annonce en anglais", '<html lang="en"' in guide.page_html("en"))
ok("une seule langue est visible à la fois",
   "html[lang=fr] .en" in page and "html[lang=en] .fr" in page)
ok("la bascule est présente",
   page.count("data-l=fr") == 1 and page.count("data-l=en") == 1)
ok("les deux langues sont dans le document",
   'class="fr"' in page and 'class="en"' in page)
ok("la page est autonome", "<style>" in page and "</script>" in page
   and "src=" not in page)
ok("aucune accolade de gabarit oubliée",
   "{'fr'" not in page and '{"fr"' not in page)
for c in guide.CLES:
    ok(f"la page nomme {c['nom']}", c["nom"] in page)
    # Le premier pas doit mener au fournisseur d'un clic, dans les deux
    # langues : recopier une adresse à la main y introduit une faute.
    adresse = config.FOURNISSEURS[c["id"]]["ou"]
    listes = [b for b in re.findall(r"<ol class=\"\w\w\".*?</ol>", page, re.S)
              if adresse in b]
    ok(f"la page lie l'adresse de {c['id']} dans les deux langues",
       len(listes) == len(guide.LANGUES)
       and all(f'href="https://{adresse}"' in b for b in listes),
       f"{len(listes)} liste(s) citant l'adresse")
for texte in ("Create API Key", "Create API key"):
    ok(f"la page nomme « {texte} »", texte in page)
ok("la page s'imprime avec les adresses", "@media print" in page)

# Les deux langues doivent peser à peu près pareil : un écart marqué
# trahit un bloc traduit à moitié.
fr = sum(len(p["fr"]) for _, p in toutes)
en = sum(len(p["en"]) for _, p in toutes)
ok("les deux versions ont un volume comparable", 0.75 < en / fr < 1.35,
   f"{fr} caractères en français, {en} en anglais")

# ------------------------------------------- l'accroche dans les pages

# branchement.js est posé par le serveur dans les deux interfaces et
# emprunte quelques points d'ancrage à la page. Les renommer de l'autre
# côté — ce qui arrive pendant une refonte — ne lèverait aucune erreur :
# l'écran de branchement se contenterait de ne plus rien afficher, et
# personne ne pourrait plus enregistrer de clé. Mieux vaut l'apprendre
# ici que par quelqu'un qui n'arrive pas à démarrer.
from pathlib import Path

STATIC = Path(__file__).parent / "static"
js = (STATIC / "branchement.js").read_text(encoding="utf-8")

EMPRUNTS = ("stage-area", "dock", "changekey")   # identifiants de la page
GLOBALES = ("$", "api", "escapeHtml", "ready", "askForKey")
CLASSES = ("setup", "keyrow", "keyerr", "keynote")

for ident in EMPRUNTS:
    ok(f"branchement.js lit #{ident}", f"'#{ident}'" in js or f'"{ident}"' in js)

for nom in ("index.html", "index-vm.html"):
    page_ui = STATIC / nom
    if not page_ui.exists():
        continue
    html = page_ui.read_text(encoding="utf-8")
    for ident in EMPRUNTS:
        ok(f"{nom} : #{ident} existe", f'id="{ident}"' in html)
    for g in GLOBALES:
        # `\b` ne vaut rien après « $ » : les deux côtés sont des
        # non-mots, donc il n'y a pas de frontière à trouver.
        motif = (r"(?:const|let|var|function)\s+\$\s*="
                 if g == "$" else
                 rf"(?:const|let|var|function)\s+{re.escape(g)}\b")
        ok(f"{nom} : {g} est déclaré au premier niveau",
           bool(re.search(motif, html)))
    for c in CLASSES:
        ok(f"{nom} : la classe .{c} est habillée", f".{c}" in html)

print(f"\n{'GUIDE CONFORME' if not fails else str(len(fails)) + ' PROBLÈME(S)'}")
sys.exit(1 if fails else 0)
