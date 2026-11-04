"""Aucun nom non défini dans le code de l'application.

C'est le contrôle qui manquait. Un remplacement trop large avait laissé
`config.get_key(fournisseurs.fournisseur_de(modele))` dans une fonction
où `modele` n'était calculé que deux lignes plus bas : le serveur
répondait 502 et l'interface affichait « name 'modele' is not defined ».
Python ne s'en aperçoit qu'à l'exécution de la ligne fautive, donc
seulement quand quelqu'un clique sur le bouton.

Les tests ne couvrent pas chaque branche de chaque gestionnaire ; cette
analyse statique, si."""
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).parent
# Ce qui compte vraiment : un nom qui n'existe pas fait tomber la requête.
# Les imports inutilisés sont du rangement, pas des pannes.
GRAVES = ("undefined name", "syntax error")

sortie = subprocess.run(
    [sys.executable, "-m", "pyflakes", *[str(p) for p in sorted(RACINE.glob("*.py"))]],
    capture_output=True, text=True).stdout

graves = [l for l in sortie.splitlines()
          if any(g in l.lower() for g in GRAVES)]
autres = [l for l in sortie.splitlines() if l and l not in graves]

for ligne in graves:
    print("  GRAVE " + ligne.replace(str(RACINE) + "/", ""))
for ligne in autres[:8]:
    print("  (rangement) " + ligne.replace(str(RACINE) + "/", ""))

print(f"\n{len(graves)} nom(s) non défini(s), {len(autres)} remarque(s) de rangement")
sys.exit(1 if graves else 0)
