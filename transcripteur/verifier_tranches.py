"""Contrôles du découpage et de la reprise à l'envoi.

Aucun appel réseau : le client Groq est remplacé par une doublure.
Ce qui est couvert : une tranche ne dépasse jamais le plafond de durée,
un dépassement de délai se rejoue, une clé refusée ne se rejoue pas."""
import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from transcripteur import pipeline

ok = rate = 0
def v(nom, cond, d=""):
    global ok, rate
    print(("  ok   " if cond else "  RATE ") + nom + ("" if cond else f"  -> {d}"))
    ok += cond; rate += not cond

def tranches(minutes, max_mb=24):
    d = minutes * 60
    budget = min(max_mb * 1048576 * 0.92 / pipeline.MP3_BYTES_PER_SECOND,
                 pipeline.MAX_CHUNK_SECONDS)
    parts = max(1, math.ceil(d / budget))
    return parts, d / parts

# 1. aucune tranche ne depasse le plafond, quelle que soit la duree
for minutes in (5, 45, 83, 162, 240, 480):
    parts, duree = tranches(minutes)
    v(f"{minutes:3d} min : tranches de {duree/60:.0f} min",
      duree <= pipeline.MAX_CHUNK_SECONDS + 1, f"{duree/60:.1f} min")

# 2. le plafond de duree prime sur celui de la taille
parts_gros, duree_gros = tranches(162, max_mb=200)
v("un quota de taille généreux ne rallonge pas les tranches",
  duree_gros <= pipeline.MAX_CHUNK_SECONDS + 1, f"{duree_gros/60:.1f} min")

# 3. reprise sur depassement de delai
essais = []
import time as _t
_t.sleep = lambda s: None
class FausseTranscription:
    def create(self, **k):
        essais.append(1)
        if len(essais) < 3:
            raise RuntimeError("Request timed out.")
        return {"segments": [], "words": [], "text": ""}
class FauxClient:
    def __init__(self, **k): self.audio = type("A", (), {"transcriptions": FausseTranscription()})()
import groq
groq.Groq = FauxClient
tmp = Path(__import__("tempfile").mkdtemp()) / "t.mp3"
tmp.write_bytes(b"\0" * 32)
try:
    pipeline.transcribe_chunk(tmp, 0.0, "fr", "gsk_faux")
    v("un dépassement de délai est rejoué", len(essais) == 3, f"{len(essais)} essais")
except Exception as exc:
    v("un dépassement de délai est rejoué", False, str(exc)[:70])

# 4. une cle refusee ne se rejoue pas : inutile et trompeur
essais.clear()
class CleRefusee(FausseTranscription):
    def create(self, **k):
        essais.append(1)
        raise RuntimeError("Error code: 401 invalid_api_key")
FauxClient.__init__ = lambda self, **k: setattr(
    self, "audio", type("A", (), {"transcriptions": CleRefusee()})())
try:
    pipeline.transcribe_chunk(tmp, 0.0, "fr", "gsk_faux")
    v("une clé refusée ne se rejoue pas", False, "aucune exception")
except pipeline.PipelineError as exc:
    v("une clé refusée ne se rejoue pas",
      len(essais) == 1 and "refus" in str(exc).lower(), f"{len(essais)} essais")

# ---- sans separation des voix : des paragraphes, pas un pave
#      Le transcript entier tenait dans un seul bloc : deux heures de
#      texte d'un trait, un seul horodatage, rien a suivre en lecture.
mots = []
t = 0.0
for i in range(4000):
    mots.append({"start": t, "end": t + 0.35,
                 "text": ("fin." if i % 35 == 34 else f"mot{i}")})
    t += 0.42 + (2.5 if i % 60 == 59 else 0.0)
paras = pipeline.decouper_sans_voix(mots)
v("un monologue est découpé", len(paras) > 20, f"{len(paras)} paragraphes")
durees = [x["end"] - x["start"] for x in paras]
v("aucun paragraphe interminable",
  max(durees) <= pipeline.PARAGRAPHE_MAX_SECONDES + 1, f"{max(durees):.0f}s")
v("chaque paragraphe a son horodatage",
  len({round(x["start"], 2) for x in paras}) == len(paras))
v("aucun mot perdu",
  sum(len(x["words"]) for x in paras) == len(mots),
  f'{sum(len(x["words"]) for x in paras)} / {len(mots)}')
v("l'ordre est conservé",
  all(paras[i]["start"] <= paras[i + 1]["start"] for i in range(len(paras) - 1)))
v("aucun paragraphe vide", all(x["text"].strip() for x in paras))

print(f"\n{ok} reussis, {rate} echecs")
sys.exit(1 if rate else 0)
