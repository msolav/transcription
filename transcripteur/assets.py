"""
Récupération des ressources externes : binaire ffmpeg et modèles ONNX.

Rien n'est demandé à l'utilisateur : ffmpeg arrive avec le paquet
imageio-ffmpeg, les modèles sont téléchargés une fois depuis les releases
GitHub de sherpa-onnx. Aucun compte, aucun jeton, aucune licence à accepter.
"""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"

SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
SEG_FILE = MODELS_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"

# Empreintes vocales. Aucun de ces modèles n'est meilleur dans l'absolu :
# tout dépend de la voix des personnes et de la prise de son. Le premier
# est léger et suffit souvent ; les autres valent d'être essayés quand
# deux personnes se retrouvent confondues.
EMBEDDINGS = {
    "standard": "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
    "renforce": "3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx",
    "anglais": "nemo_en_titanet_large.onnx",
}
DEFAULT_EMBEDDING = "standard"
EMB_BASE = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speaker-recongition-models/")


def ffmpeg_exe() -> str:
    """ffmpeg du système s'il existe, sinon celui fourni par imageio-ffmpeg."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Aucun ffmpeg utilisable. Installe le paquet imageio-ffmpeg "
            f"ou ffmpeg sur le système. ({exc})"
        ) from exc


def _download(url: str, dst: Path, label: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")

    def hook(count: int, block: int, total: int) -> None:
        if total <= 0:
            return
        done = min(count * block, total)
        width = 28
        filled = int(width * done / total)
        sys.stdout.write(
            f"\r  {label:22s} [{'█' * filled}{'·' * (width - filled)}] "
            f"{done / 1048576:5.1f}/{total / 1048576:.1f} Mo"
        )
        sys.stdout.flush()

    urllib.request.urlretrieve(url, tmp, reporthook=hook)
    tmp.replace(dst)
    sys.stdout.write("\n")


def ensure_models(embedding: str = DEFAULT_EMBEDDING) -> tuple[Path, Path]:
    """Retourne (segmentation, empreintes), en téléchargeant au besoin."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    name = EMBEDDINGS.get(embedding, EMBEDDINGS[DEFAULT_EMBEDDING])
    emb_file = MODELS_DIR / name

    if not SEG_FILE.exists():
        print("Premier lancement : téléchargement des modèles (une seule fois, ~34 Mo)")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "seg.tar.bz2"
            _download(SEG_URL, archive, "segmentation")
            with tarfile.open(archive, "r:bz2") as tar:
                tar.extractall(MODELS_DIR)
        if not SEG_FILE.exists():
            raise RuntimeError("Modèle de segmentation absent après extraction.")

    if not emb_file.exists():
        print(f"Téléchargement du modèle de voix « {embedding} »…")
        _download(EMB_BASE + name, emb_file, "empreintes vocales")

    return SEG_FILE, emb_file


def models_ready() -> bool:
    return SEG_FILE.exists() and (MODELS_DIR / EMBEDDINGS[DEFAULT_EMBEDDING]).exists()
