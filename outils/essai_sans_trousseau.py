"""Sans Secret Service, la clé doit quand même être enregistrée.

Le cas d'une installation Linux minimale : keyring est présent mais ne
trouve aucun coffre, et lève. Si rien ne rattrape, la clé est perdue en
silence — l'écran annonce qu'elle est enregistrée, et elle ne l'est pas.
"""
import os, stat, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/Users/solav/Documents/Scripts/voice_trascription/Transcripteur")

maison = Path(tempfile.mkdtemp(prefix="sans-trousseau-"))
os.environ["HOME"] = str(maison)
for v in ("GROQ_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    os.environ.pop(v, None)

from transcripteur import config
config.CONFIG_PATH = maison / ".transcripteur.json"

ech = []
def ok(n, c, d=""):
    print(f"  {'OK ' if c else 'ÉCHEC'} {n}" + (f" — {d}" if d and not c else ""))
    if not c: ech.append(n)

# On simule l'absence de coffre : keyring lève, comme sur une machine
# sans GNOME Keyring ni KWallet.
class CoffreAbsent:
    @staticmethod
    def get_password(*a): raise RuntimeError("No recommended backend")
    @staticmethod
    def set_password(*a): raise RuntimeError("No recommended backend")
    @staticmethod
    def delete_password(*a): raise RuntimeError("No recommended backend")

config._trousseau = lambda: CoffreAbsent

print("Sans Secret Service")
ok("aucune clé au départ", config.get_key("groq") == "")
config.set_key("gsk_essai_sans_coffre", "groq")
ok("la clé est tout de même enregistrée",
   config.get_key("groq") == "gsk_essai_sans_coffre", config.get_key("groq"))
ok("elle atterrit dans le fichier de repli", config.CONFIG_PATH.exists(),
   str(config.CONFIG_PATH))
mode = stat.S_IMODE(config.CONFIG_PATH.stat().st_mode)
ok("lisible par le seul propriétaire (0600)", mode == 0o600, oct(mode))
ok("la source est nommée", config.source_cle("groq") == "fichier",
   config.source_cle("groq"))
ok("cles_presentes la voit", config.cles_presentes().get("groq") is True)
config.clear_key("groq")
ok("et elle s'efface", config.get_key("groq") == "")

import shutil; shutil.rmtree(maison, ignore_errors=True)
print(f"\n{'REPLI CONFORME' if not ech else str(len(ech)) + ' PROBLÈME(S)'}")
sys.exit(1 if ech else 0)
