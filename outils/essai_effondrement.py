"""Le rattrapage quand un modèle regroupe tout le monde.

Mesuré : « VoxCeleb CAM++ », le modèle par défaut, rend une seule voix
dès qu'on lui impose un nombre — sur les deux enregistrements d'essai.
C'est le pire résultat possible, et il arrive précisément à qui a suivi
la consigne de l'interface.
"""
import sys, wave, numpy as np
sys.path.insert(0, "/Users/solav/Documents/Scripts/voice_trascription/Transcripteur")
from transcripteur import assets, pipeline

ech = []
def ok(n, c, d=""):
    print(f"  {'OK ' if c else 'ÉCHEC'} {n}" + (f" — {d}" if d and not c else ""))
    if not c: ech.append(n)

def lire(p):
    w = wave.open(p)
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

notes = []
pipeline._notify = notes.append

for chemin, vrai in (("voix/reunion.wav", 2), ("voix/trois.wav", 3)):
    print(f"\n{chemin} — {vrai} voix, modèle par défaut ({assets.DEFAULT_EMBEDDING})")
    notes.clear()
    audio = lire(chemin)
    tours = pipeline.diarize(audio, vrai, pipeline._noop, (0, 0),
                             pipeline.CLUSTER_THRESHOLD, assets.DEFAULT_EMBEDDING)
    n = len({t[2] for t in tours})
    ok(f"plus d'une voix malgré l'effondrement du modèle", n > 1, f"{n} voix")
    ok(f"le bon nombre est retrouvé", n == vrai, f"{n} au lieu de {vrai}")
    ok("l'utilisateur est prévenu de la reprise",
       any("imposant" in m or "Reprise" in m for m in notes), str(notes))

# Un modèle qui n'a pas le défaut ne doit pas être ralenti par le garde-fou.
print("\nvoix/trois.wav — un modèle qui fonctionne (campplus_zh_en)")
notes.clear()
tours = pipeline.diarize(lire("voix/trois.wav"), 3, pipeline._noop, (0, 0),
                         pipeline.CLUSTER_THRESHOLD, "campplus_zh_en")
n = len({t[2] for t in tours})
ok("il trouve toujours les trois voix", n == 3, f"{n} voix")
# `_notify` reçoit aussi le journal ordinaire : ce qu'on vérifie,
# c'est l'absence du message de reprise, pas l'absence de messages.
ok("et rien n'a été repris inutilement",
   not any("imposant" in m or "Reprise" in m for m in notes), str(notes))

print(f"\n{'RATTRAPAGE CONFORME' if not ech else str(len(ech)) + ' PROBLÈME(S)'}")
sys.exit(1 if ech else 0)
