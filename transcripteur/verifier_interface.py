"""Contrôles structurels de l'interface, à relancer après chaque retouche."""
import re, sys
from pathlib import Path
h = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
script = re.search(r'<script>(.*)</script>', h, re.S).group(1)
fails = []

def ok(name, condition, detail=""):
    print(f"  {'OK ' if condition else 'ÉCHEC'} {name}{' — ' + detail if detail and not condition else ''}")
    if not condition: fails.append(name)

used = sorted(set(re.findall(r"\$\('#([\w-]+)'\)", script)))
declared = set(re.findall(r'id="([\w-]+)"', h))
missing = [u for u in used if u not in declared]
ok(f"les {len(used)} identifiants lus existent", not missing, ", ".join(missing))

for ident in ("emb","embnote","clean","cleannote","lang","count","go","stop",
              "journal","deck","dock","doc","player","sampler"):
    ok(f"#{ident} présent", f'id="{ident}"' in h)

main = h[h.index('<main'):h.index('</main>')]
ok("le lecteur est hors de la zone re-rendue", 'id="deck"' not in main)
ok("le socle est hors de la zone re-rendue", 'id="dock"' not in main)
ok("un seul lecteur", h.count('id="deck"') == 1)

for field in ("emb","clean","lang","count"):
    ok(f"#{field} envoyé au serveur", f"$('#{field}').value" in script)

for endpoint in ("/api/jobs","/api/key","/cancel","/names","/sample/"):
    ok(f"appel {endpoint}", endpoint in script)

ok("fusion par le nom", "function mergedBlocks" in script and "function keyOf" in script)
ok("icônes lecture/pause", "PAUSE_ICON" in script and "PLAY_ICON" in script)

# Les listes déroulantes peuplées par le serveur ne doivent pas contenir
# d'options écrites en dur : c'est le serveur qui décide de l'ordre et de
# ce qui est déjà téléchargé.
for vide in ("emb", "clean"):
    balise = re.search(r'<select id="' + vide + r'">(.*?)</select>', h, re.S)
    ok(f"#{vide} est rempli par le serveur", bool(balise) and not balise.group(1).strip())

ok("catalogue demandé au serveur", "/api/models" in script)

# La barre d'export contient aussi des boutons qui ne sont pas des exports.
# Les câbler en bloc écrasait leurs gestionnaires et lançait un
# téléchargement « .undefined » : le sélecteur doit être restreint.
ok("les exports ne câblent que [data-x]",
   ".exportbar button[data-x]" in script)
barre = re.search(r'<div class="exportbar">(.*?)</div>', h, re.S)
sans_x = re.findall(r'<button (?![^>]*data-x)[^>]*id="([\w-]+)"', barre.group(1) if barre else "")
for bouton in sans_x:
    ok(f"#{bouton} a son propre gestionnaire", f"$('#{bouton}').onclick" in script)
ok("langue relit le catalogue", "'#lang'" in script and "loadModels" in script)

print(f"\n{'INTERFACE CONFORME' if not fails else str(len(fails)) + ' PROBLÈME(S)'}")
sys.exit(1 if fails else 0)
