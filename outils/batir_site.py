#!/usr/bin/env python3
"""
Fabrique le petit site public : où prendre le programme, et comment
obtenir une clé.

Deux pages, aucune base de données, aucun compte, rien à tenir en
marche. C'est la seule part de cet outil qui ait une raison d'être en
ligne : celui qui en a besoin ne peut pas encore lire une page servie
par le programme — il n'a pas de clé, et souvent rien d'installé.

La page d'aide n'est pas écrite ici. Elle sort de guide.py, d'où
sortent aussi l'assistant de premier lancement et le README : une
marche à suivre recopiée à trois endroits finit par dire trois choses
différentes, et c'est la copie publique, lue par ceux qui ne peuvent
rien vérifier, qui ferait le plus de dégâts.

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

SORTIE = RACINE / "site"
DEPOT = "msolav/transcription"

# Une seule couleur de signal, du papier, de l'encre, et de grandes
# lettres : la page d'accueil doit ressembler à l'outil qu'elle propose.
GABARIT = """<!doctype html>
<html lang="fr">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcripteur — transcrire une réunion, sur sa propre machine</title>
<meta name="description" content="Transcrit une réunion et sépare les voix,
 sur votre ordinateur. Gratuit, sans compte. Mac et Windows.">
<style>
  :root {{ --paper:#f1efe9; --ink:#0c0c0b; --mute:#6b6a65; --accent:#ff3d12; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --paper:#0c0c0b; --ink:#f1efe9; --mute:#9a978f; }} }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink);
    font:17px/1.55 ui-sans-serif, system-ui, -apple-system, sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .page {{ max-width: 46rem; margin: 0 auto; padding: 4rem 1.5rem 6rem; }}
  h1 {{ font-size: clamp(2.6rem, 9vw, 5rem); line-height:.95; margin:0 0 1rem;
    letter-spacing:-.04em; font-weight:800; }}
  h2 {{ font-size:1.05rem; letter-spacing:.08em; text-transform:uppercase;
    margin:3.5rem 0 1rem; font-family:ui-monospace, monospace; color:var(--mute); }}
  .chapeau {{ font-size:1.25rem; max-width:34rem; }}
  .regle {{ height:5px; background:var(--ink); margin:2.5rem 0 0; }}
  .regle + .regle {{ height:1px; margin-top:3px; }}
  a {{ color:var(--ink); text-underline-offset:3px; }}
  a:hover {{ color:var(--accent); }}
  .boite {{ border:1px solid color-mix(in oklab, var(--ink) 20%, transparent);
    padding:1.1rem 1.2rem; margin:.7rem 0; display:flex; gap:1rem;
    align-items:baseline; flex-wrap:wrap; }}
  .boite b {{ font-size:1.1rem; }}
  .boite .quoi {{ color:var(--mute); font-size:.92rem; }}
  .boite a.bouton {{ margin-left:auto; text-decoration:none; font-weight:600;
    background:var(--accent); color:#fff; padding:.5rem 1rem; white-space:nowrap; }}
  ul {{ padding-left:1.1rem; }} li {{ margin:.45rem 0; }}
  .note {{ color:var(--mute); font-size:.95rem; }}
  footer {{ margin-top:5rem; color:var(--mute); font-size:.9rem; }}
  .bascule {{ position:fixed; top:1rem; right:1rem; font-family:ui-monospace,monospace;
    font-size:.8rem; letter-spacing:.1em; }}
  .bascule a {{ text-decoration:none; padding:.2rem .4rem; }}
  .bascule a.ici {{ background:var(--ink); color:var(--paper); }}
  html[lang=fr] .en, html[lang=en] .fr {{ display:none; }}
</style>

<nav class="bascule">
  <a href="#" data-l="fr" class="ici">FR</a><a href="#" data-l="en">EN</a>
</nav>

<div class="page">
  <h1>Transcripteur</h1>

  <p class="chapeau fr">Transcrit une réunion et sépare les voix. Sur votre
    ordinateur, pas sur un serveur. Gratuit, sans compte à créer.</p>
  <p class="chapeau en">Transcribes a meeting and separates the voices. On your
    own computer, not on a server. Free, with no account to create.</p>

  <div class="regle"></div><div class="regle"></div>

  <h2><span class="fr">Télécharger</span><span class="en">Download</span></h2>

  <div class="boite">
    <b>macOS</b>
    <span class="quoi fr">Puce Apple M1 à M4</span>
    <span class="quoi en">Apple M1–M4 chip</span>
    <a class="bouton" href="{sorties}">Apple Silicon</a>
  </div>
  <div class="boite">
    <b>macOS</b>
    <span class="quoi fr">Processeur Intel</span>
    <span class="quoi en">Intel processor</span>
    <a class="bouton" href="{sorties}">Intel</a>
  </div>
  <div class="boite">
    <b>Windows</b>
    <span class="quoi fr">Windows 10 ou 11</span>
    <span class="quoi en">Windows 10 or 11</span>
    <a class="bouton" href="{sorties}">Windows</a>
  </div>

  <p class="note fr">Menu Pomme → À propos de ce Mac indique laquelle des deux
    versions prendre. L'autre ne s'ouvrira pas, et sans rien expliquer.
    L'application n'est pas signée : à la première ouverture, clic droit →
    <b>Ouvrir</b> sur Mac, <b>Informations complémentaires → Exécuter quand
    même</b> sur Windows. Une seule fois.</p>
  <p class="note en">The Apple menu → About This Mac tells you which of the two
    to take. The other one will not open, and will not say why. The app is
    unsigned: on first launch, right-click → <b>Open</b> on Mac,
    <b>More info → Run anyway</b> on Windows. Once only.</p>

  <h2><span class="fr">Il vous faut une clé</span><span class="en">You need a key</span></h2>

  <p class="fr">La reconnaissance de la parole passe par un service extérieur,
    Groq, dont l'offre gratuite suffit largement. Il faut y créer une clé —
    c'est gratuit, sans carte bancaire, et cela prend cinq minutes.
    <a href="aide/">La marche à suivre, pas à pas</a>.</p>
  <p class="en">Speech recognition goes through an outside service, Groq, whose
    free tier is more than enough. You need to create a key there — free, no
    credit card, about five minutes.
    <a href="aide/">Step-by-step instructions</a>.</p>

  <h2><span class="fr">Ce qui reste chez vous</span><span class="en">What stays with you</span></h2>

  <ul class="fr">
    <li>La séparation des voix se fait sur votre machine, hors ligne.</li>
    <li>Seul l'audio, compressé, part chez Groq pour être transcrit.</li>
    <li>Les transcriptions sont rangées sur votre disque. Aucun compte,
      aucun serveur, personne ne tient le relevé de ce que vous transcrivez.</li>
    <li>Votre clé va dans le trousseau du système, jamais dans un fichier.</li>
  </ul>
  <ul class="en">
    <li>Voice separation happens on your machine, offline.</li>
    <li>Only the audio, compressed, goes to Groq to be transcribed.</li>
    <li>Transcripts are kept on your own disk. No account, no server, nobody
      keeping a record of what you transcribe.</li>
    <li>Your key goes into the system keychain, never into a file.</li>
  </ul>

  <footer>
    <span class="fr">Code source et versions :</span>
    <span class="en">Source code and releases:</span>
    <a href="https://github.com/{depot}">github.com/{depot}</a>
  </footer>
</div>

<script>
  (function () {{
    var h = document.documentElement;
    try {{ var m = localStorage.getItem('tr-site-lang'); if (m) h.lang = m; }} catch (e) {{}}
    if (!localStorage.getItem('tr-site-lang') && !navigator.language.startsWith('fr')) h.lang = 'en';
    function peindre() {{
      document.querySelectorAll('.bascule a').forEach(function (a) {{
        a.classList.toggle('ici', a.dataset.l === h.lang);
      }});
    }}
    document.querySelectorAll('.bascule a').forEach(function (a) {{
      a.onclick = function (e) {{
        e.preventDefault(); h.lang = a.dataset.l;
        try {{ localStorage.setItem('tr-site-lang', h.lang); }} catch (err) {{}}
        peindre();
      }};
    }});
    peindre();
  }})();
</script>
</html>
"""


def batir() -> Path:
    if SORTIE.exists():
        shutil.rmtree(SORTIE)
    SORTIE.mkdir(parents=True)

    sorties = f"https://github.com/{DEPOT}/releases/latest"
    (SORTIE / "index.html").write_text(
        GABARIT.format(depot=DEPOT, sorties=sorties), encoding="utf-8")

    # La page d'aide vient du même endroit que l'assistant du programme.
    # Un dossier plutôt qu'un fichier .html : « /aide/ » se sert alors
    # pareil ici et sur Cloudflare, sans redirection sur le seul lien
    # qui compte vraiment.
    aide = SORTIE / "aide"
    aide.mkdir()
    (aide / "index.html").write_text(guide.page_html("fr"), encoding="utf-8")

    # Rien à indexer de plus, et surtout pas les archives de versions.
    (SORTIE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n", encoding="utf-8")

    return SORTIE


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--servir", action="store_true",
                         help="Montrer le site sur http://127.0.0.1:8080")
    args = parseur.parse_args()

    dossier = batir()
    poids = sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())
    print(f"{dossier} — {len(list(dossier.iterdir()))} fichiers, "
          f"{poids / 1024:.0f} Ko")

    if args.servir:
        import functools
        import http.server

        handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                    directory=str(dossier))
        print("http://127.0.0.1:8080 — Ctrl+C pour arrêter")
        http.server.HTTPServer(("127.0.0.1", 8080), handler).serve_forever()
