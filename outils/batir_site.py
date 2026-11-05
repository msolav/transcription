#!/usr/bin/env python3
"""
Fabrique le site public : où prendre le programme, et comment obtenir
une clé.

Deux pages, aucune base de données, aucun compte. C'est la seule part de
cet outil qui ait une raison d'être en ligne : celui qui a besoin du
mode d'emploi ne peut pas encore lire une page servie par le programme,
puisqu'il n'a ni clé ni rien d'installé.

Les sources sont dans outils/site/ : page.html (gabarit), site.css,
site.js, worker.js. Le kit vm.css / vm.js est inliné depuis le skill,
pour que le site ait les mêmes polices, la même couleur de signal, le
même grain et la même bascule clair/sombre que l'application — un site
en police système avec un autre accent se lit comme un autre produit.

La page d'aide n'est pas écrite ici : elle sort de guide.py, comme
l'assistant de premier lancement et le README.

    python outils/batir_site.py           écrit dans site/
    python outils/batir_site.py --servir  et le montre sur 8080
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from transcripteur import guide  # noqa: E402

SOURCES = Path(__file__).resolve().parent / "site"
SORTIE = RACINE / "site"
KIT = Path.home() / ".claude" / "skills" / "vm-ui" / "assets"


def kit(nom: str) -> str:
    """Le fichier du kit, ou rien s'il n'est pas là.

    Le skill vit hors du dépôt. Sans lui, le site s'affiche quand même —
    site.css ne dépend du kit que pour les variables de thème, qu'il
    redéclare ci-dessous en repli — mais sans bascule clair/sombre ni
    grain. On le dit plutôt que de livrer une page silencieusement
    dégradée."""
    f = KIT / nom
    return f.read_text(encoding="utf-8") if f.exists() else ""


# Repli minimal : si le kit manque, la page garde ses couleurs plutôt
# que de tomber sur du noir sur noir.
REPLI = """
:root { --vm-paper:#f1efe9; --vm-paper-2:#e6e3da; --vm-ink:#0c0c0b;
  --vm-mute:#6b6a65; --vm-accent:#1a40ff; --tr-on-accent:#fff;
  --vm-ease: cubic-bezier(.77,0,.175,1);
  --vm-ease-out: cubic-bezier(.16,1,.3,1); }
@media (prefers-color-scheme: dark) {
  :root { --vm-paper:#0c0c0b; --vm-paper-2:#161614; --vm-ink:#f1efe9;
    --vm-mute:#9a978f; } }
"""


def batir() -> Path:
    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    SORTIE.mkdir(parents=True)

    page = (SOURCES / "page.html").read_text(encoding="utf-8")
    vm_css, vm_js = kit("vm.css"), kit("vm.js")
    page = page.replace("/*VM_CSS*/", (vm_css or REPLI))
    page = page.replace("/*SITE_CSS*/",
                        (SOURCES / "site.css").read_text(encoding="utf-8"))
    page = page.replace("/*VM_JS*/", vm_js)
    page = page.replace("/*SITE_JS*/",
                        (SOURCES / "site.js").read_text(encoding="utf-8"))
    (SORTIE / "index.html").write_text(page, encoding="utf-8")

    # Un dossier plutôt qu'un fichier .html : « /aide/ » se sert alors
    # pareil en local et sur Cloudflare, sans redirection sur le seul
    # lien qui compte vraiment.
    aide = SORTIE / "aide"
    aide.mkdir()
    (aide / "index.html").write_text(guide.page_html("fr"), encoding="utf-8")

    (SORTIE / "robots.txt").write_text("User-agent: *\nAllow: /\n",
                                       encoding="utf-8")
    if not vm_css:
        print("  (kit vm-ui absent : thème et grain réduits)")
    return SORTIE


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--servir", action="store_true",
                         help="Montrer le site sur http://127.0.0.1:8080")
    args = parseur.parse_args()

    dossier = batir()
    poids = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())
    print(f"{dossier} — {poids / 1024:.0f} Ko")

    if args.servir:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(dossier))
        print("http://127.0.0.1:8080 — Ctrl+C pour arrêter")
        http.server.HTTPServer(("127.0.0.1", 8080), handler).serve_forever()
