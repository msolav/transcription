"""ffmpeg n'est plus dans le paquet : il doit s'obtenir au besoin."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/Users/solav/Documents/Scripts/voice_trascription/Transcripteur")

bac = Path(tempfile.mkdtemp(prefix="ffmpeg-essai-"))
os.environ["TRANSCRIPTEUR_DONNEES"] = str(bac)

from transcripteur import assets

ech = []
def ok(n, c, d=""):
    print(f"  {'OK ' if c else 'ÉCHEC'} {n}" + (f" — {d}" if d and not c else ""))
    if not c: ech.append(n)

# On cache celui du système ET celui de l'environnement, pour forcer le
# téléchargement — c'est le seul chemin que l'application installée
# empruntera, et le seul qu'on n'a jamais éprouvé.
assets.shutil.which = lambda n: None
vrai_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
def sans_imageio(nom, *a, **k):
    if nom == "imageio_ffmpeg":
        raise ImportError("absent du paquet")
    return vrai_import(nom, *a, **k)
import builtins; builtins.__import__ = sans_imageio

notes = []
print("Sans ffmpeg nulle part")
ok("rien de déjà téléchargé", assets._ffmpeg_telecharge() is None)
chemin = assets.ffmpeg_exe(note=notes.append)
builtins.__import__ = vrai_import

ok("un chemin est rendu", bool(chemin), str(chemin))
ok("il est dans le dossier de données", str(bac) in chemin, chemin)
p = Path(chemin)
ok("le fichier existe", p.exists())
ok("il est exécutable", os.access(p, os.X_OK))
ok("il pèse ce qu'un ffmpeg pèse", p.stat().st_size > 20_000_000,
   f"{p.stat().st_size/1048576:.0f} Mo")
ok("l'utilisateur est prévenu", any("ffmpeg" in n for n in notes), str(notes))

v = subprocess.run([str(p), "-version"], capture_output=True, text=True)
ok("il s'exécute", v.returncode == 0, (v.stderr or "")[:80])
print("     ", (v.stdout or "").splitlines()[0][:70] if v.stdout else "")

# Deuxième appel : il doit être réutilisé, pas retéléchargé.
notes.clear()
assets.shutil.which = lambda n: None
encore = assets.ffmpeg_exe(note=notes.append)
ok("le second appel réutilise le fichier", encore == chemin and not notes,
   f"{encore} / {notes}")

# Et il convertit vraiment.
son = bac / "a.wav"
subprocess.run([str(p), "-f", "lavfi", "-i", "sine=f=440:d=1", "-y", str(son)],
               capture_output=True)
ok("il convertit un fichier", son.exists() and son.stat().st_size > 1000)

shutil.rmtree(bac, ignore_errors=True)
print(f"\n{'FFMPEG DIFFÉRÉ CONFORME' if not ech else str(len(ech)) + ' PROBLÈME(S)'}")
sys.exit(1 if ech else 0)
