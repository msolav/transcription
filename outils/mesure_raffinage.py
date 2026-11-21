"""Le raffinage fait-il mieux que la séparation de base ?

Même enregistrements, même modèles que mesure_voix.py (vérité connue :
nombre de voix). On compare le nombre trouvé, en détection libre et avec
le nombre imposé, avant et après raffinage. Tout est local.

    .venv/bin/python outils/mesure_raffinage.py [dossier_voix]
"""
import sys, time, wave
import numpy as np
sys.path.insert(0, ".")
from transcripteur import assets, pipeline, raffinage
import sherpa_onnx

DOSSIER = sys.argv[1] if len(sys.argv) > 1 else "../scratch/voix"
CAS = [("reunion.wav", 2), ("trois.wav", 3)]
MODELES = ["voxceleb_resnet", "voxceleb_campplus", "campplus_zh_en", "titanet_small"]


def lire(p):
    w = wave.open(p)
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return a.astype(np.float32) / 32768.0


def base(audio, seg, emb, nombre):
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg)), num_threads=4),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb), num_threads=4),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=nombre, threshold=pipeline.CLUSTER_THRESHOLD),
        min_duration_on=0.3, min_duration_off=0.5)
    r = sherpa_onnx.OfflineSpeakerDiarization(cfg).process(audio).sort_by_start_time()
    return [(float(x.start), float(x.end), f"SPEAKER_{x.speaker:02d}") for x in r]


def voix(t):
    return len({x[2] for x in t})


print(f"{'fichier':12} {'modèle':18} {'vrai':>4} | {'libre':>5} {'→ raff.':>7} | {'imposé':>6} {'→ raff.':>7} | {'s':>5}")
print("-" * 80)
ok = {"base": 0, "raff": 0}; tot = 0
for f, vrai in CAS:
    audio = lire(f"{DOSSIER}/{f}")
    for m in MODELES:
        try:
            seg, emb = assets.ensure_models(m)
        except Exception as e:
            print(f"{f:12} {m:18} indisponible ({e})"); continue
        ext = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb), num_threads=4))
        t0 = time.time()
        libre = base(audio, seg, emb, -1); lr = raffinage.raffiner(audio, libre, ext, -1)
        imp = base(audio, seg, emb, vrai); ir = raffinage.raffiner(audio, imp, ext, vrai)
        print(f"{f:12} {m:18} {vrai:>4} | {voix(libre):>5} {voix(lr):>7} | {voix(imp):>6} {voix(ir):>7} | {time.time()-t0:>5.1f}")
        tot += 1; ok["base"] += voix(libre) == vrai; ok["raff"] += voix(lr) == vrai
print("-" * 80)
print(f"détection libre : bon nombre de voix  base {ok['base']}/{tot}   raffiné {ok['raff']}/{tot}")
