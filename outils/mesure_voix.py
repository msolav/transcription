"""Le nombre de voix annoncé aide-t-il vraiment la séparation ?

L'interface l'affirme : « La séparation est nettement plus fiable quand
le nombre est indiqué. » C'est une consigne, donnée à quelqu'un qui n'a
aucun moyen de la vérifier. On la vérifie ici, sur deux enregistrements
dont on connaît la vérité, et sur chaque modèle d'empreintes installé.

Aucun appel à un fournisseur : tout est local.
"""
import sys, wave, numpy as np
sys.path.insert(0, "/Users/solav/Documents/Scripts/voice_trascription/Transcripteur")
from transcripteur import assets, pipeline

CAS = [("voix/reunion.wav", 2), ("voix/trois.wav", 3)]
MODELES = ["voxceleb_resnet", "voxceleb_campplus", "campplus_zh_en", "titanet_small"]


def lire(p):
    w = wave.open(p)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return (a.astype(np.float32) / 32768.0)


def voix(tours):
    return len({t[2] for t in tours})


print(f"{'fichier':16} {'modèle':20} {'demandé':>8} {'trouvé':>7} {'tours':>6}  verdict")
print("-" * 76)
resultats = {}
for chemin, vrai in CAS:
    audio = lire(chemin)
    for m in MODELES:
        try:
            assets.ensure_models(m)
        except Exception as e:
            print(f"{chemin:16} {m:20} modèle indisponible : {str(e)[:30]}")
            continue
        for demande in (None, vrai):
            try:
                tours = (pipeline.diarize(audio, demande, pipeline._noop, (0, 0),
                                          pipeline.CLUSTER_THRESHOLD, m)
                         if demande else
                         pipeline.diarize_auto(audio, pipeline._noop, (0, 0),
                                               pipeline.CLUSTER_THRESHOLD, m))
                n = voix(tours)
            except Exception as e:
                print(f"{chemin:16} {m:20} ÉCHEC {str(e)[:40]}")
                continue
            etiq = "auto" if demande is None else str(demande)
            verdict = "juste" if n == vrai else ("FUSIONNE" if n < vrai else "découpe trop")
            print(f"{chemin.split('/')[-1]:16} {m:20} {etiq:>8} {n:>7} {len(tours):>6}  {verdict}")
            resultats[(chemin, m, etiq)] = n

print("\n--- où annoncer le nombre fait PIRE que laisser chercher ---")
pires = 0
for chemin, vrai in CAS:
    for m in MODELES:
        a = resultats.get((chemin, m, "auto"))
        d = resultats.get((chemin, m, str(vrai)))
        if a is None or d is None:
            continue
        if abs(d - vrai) > abs(a - vrai):
            print(f"  {chemin.split('/')[-1]} / {m} : auto={a}, annoncé {vrai}→{d} (vrai={vrai})")
            pires += 1
if not pires:
    print("  aucun")
