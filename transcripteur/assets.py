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
from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).parent.parent / "models"

SEG_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
           "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2")
SEG_FILE = MODELS_DIR / "sherpa-onnx-pyannote-segmentation-3-0" / "model.onnx"

# Empreintes vocales.
#
# Un modèle d'empreinte transforme un extrait de voix en un vecteur, et
# deux extraits de la même personne doivent donner deux vecteurs proches.
# Ce qui décide de la qualité, c'est la langue sur laquelle le modèle a
# été entraîné : un modèle nourri au mandarin sépare mal deux Québécois.
#
# Les modèles VoxCeleb sont entraînés sur des entretiens YouTube couvrant
# une centaine de nationalités. C'est ce qui existe de plus proche d'un
# modèle multilingue ici, donc le choix par défaut hors anglais et chinois.
#
# `poids` est le coût de calcul relatif, 1.0 étant le CAM++ chinois+anglais.
# Cinq valeurs sont mesurées sur un même extrait de 10 minutes, sur la même
# machine ; les autres restent estimées d'après la taille et l'architecture.
# C'est un avertissement sur le temps d'attente, jamais un classement de
# qualité. Surprise de la mesure : à architecture et taille identiques, le
# CAM++ VoxCeleb coûte près du double du CAM++ chinois+anglais.

@dataclass(frozen=True)
class Empreinte:
    cle: str
    fichier: str
    mo: float
    nom: str
    famille: str      # 'multi', 'anglais' ou 'chinois' — langues d'entraînement
    poids: float
    note: str


CATALOGUE = (
    Empreinte("voxceleb_campplus", "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
              28.2, "Multilingue CAM++", "multi", 1.8,
              "Entraîné sur VoxCeleb, une centaine de nationalités. Rapide."),
    Empreinte("voxceleb_campplus_lm", "wespeaker_en_voxceleb_CAM++_LM.onnx",
              27.9, "Multilingue CAM++ (LM)", "multi", 2.1,
              "Même idée, autre équipe, affiné à marge large. Rapide."),
    Empreinte("voxceleb_resnet", "wespeaker_en_voxceleb_resnet34_LM.onnx",
              25.3, "Multilingue ResNet34", "multi", 1.7,
              "Architecture différente : à essayer quand les CAM++ confondent deux voix."),
    Empreinte("voxceleb_eres2net", "3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx",
              25.3, "Multilingue ERes2Net", "multi", 1.8,
              "Encore une autre architecture, sur les mêmes données."),
    Empreinte("titanet_large", "nemo_en_titanet_large.onnx",
              96.7, "Anglais TitaNet (grand)", "anglais", 2.6,
              "Anglais uniquement, mais réputé solide. Lent et lourd."),
    Empreinte("titanet_small", "nemo_en_titanet_small.onnx",
              38.4, "Anglais TitaNet (petit)", "anglais", 1.2,
              "Version légère du précédent."),
    Empreinte("campplus_zh_en", "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
              27.0, "Chinois + anglais CAM++", "chinois", 1.0,
              "L'ancien réglage par défaut. Correct en anglais, jamais pensé pour le français."),
    Empreinte("eres2netv2_zh", "3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx",
              68.1, "Chinois ERes2NetV2", "chinois", 3.6,
              "Mandarin uniquement. Trois fois plus lent, sans avantage hors chinois."),
    Empreinte("cnceleb_resnet", "wespeaker_zh_cnceleb_resnet34_LM.onnx",
              25.3, "Chinois CN-Celeb ResNet34", "chinois", 1.6,
              "Mandarin, sur des enregistrements variés."),
)

EMB_BASE = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speaker-recongition-models/")

PAR_CLE = {e.cle: e for e in CATALOGUE}
DEFAULT_EMBEDDING = "voxceleb_campplus"

# Anciens noms, pour ne pas casser une configuration déjà enregistrée.
ALIAS = {"standard": "campplus_zh_en", "renforce": "eres2netv2_zh", "anglais": "titanet_large"}

# Ordre de présentation selon la langue choisie. Ce classement traduit la
# langue d'entraînement de chaque modèle, pas une précision mesurée : nous
# n'avons pas d'enregistrement annoté pour départager les modèles d'une
# même famille.
ORDRE = {
    "en": ("anglais", "multi", "chinois"),
    "zh": ("chinois", "multi", "anglais"),
}
ORDRE_DEFAUT = ("multi", "anglais", "chinois")


def resoudre(cle: str | None) -> str:
    """Nom de modèle valide, en acceptant les anciens intitulés."""
    if not cle or cle == "auto":
        return DEFAULT_EMBEDDING
    cle = ALIAS.get(cle, cle)
    return cle if cle in PAR_CLE else DEFAULT_EMBEDDING


def conseilles(langue: str | None = None) -> list[Empreinte]:
    """Le catalogue, le plus adapté à la langue en tête."""
    familles = ORDRE.get((langue or "").lower()[:2], ORDRE_DEFAUT)
    return sorted(CATALOGUE, key=lambda e: (familles.index(e.famille), e.poids, e.mo))


def resoudre_pour_langue(langue: str | None) -> str:
    """Le modèle le mieux adapté à une langue, sans rien demander à personne.

    Sert quand l'utilisateur laisse le choix au programme : on prend la tête
    du classement pour cette langue. Une langue inconnue ou indéterminée
    ramène au multilingue, qui est le pari raisonnable dans le doute."""
    return conseilles(langue)[0].cle


def est_telecharge(cle: str) -> bool:
    return (MODELS_DIR / PAR_CLE[resoudre(cle)].fichier).exists()


def inventaire(langue: str | None = None) -> list[dict]:
    """Ce que l'interface affiche : modèles classés, avec leur état."""
    return [
        {"cle": e.cle, "nom": e.nom, "mo": e.mo, "famille": e.famille,
         "note": e.note, "poids": e.poids, "telecharge": est_telecharge(e.cle)}
        for e in conseilles(langue)
    ]


# Nettoyage du signal.
#
# Un débruiteur enlève le souffle, la ventilation, la réverbération. Il
# enlève aussi, si on le laisse faire, ce qui distingue deux voix.
#
# Mesuré sur dix minutes de la vraie réunion, trois voix imposées, en
# regardant la répartition du temps de parole entre les trois groupes :
#
#   son brut        ResNet34   41,2 / 31,3 / 27,5
#   nettoyage léger ResNet34   36,0 / 32,1 / 32,0   <- le plus équilibré
#   nettoyage fort  ResNet34   71,0 / 29,0          <- une voix a disparu
#
# Le nettoyage léger améliore. Le nettoyage fort efface une personne : le
# regroupement ne trouve plus que deux voix là où il y en a trois, et
# c'est reproductible sur les trois modèles d'empreintes essayés.
#
# Avertissement sur la méthode, parce que l'erreur a été commise ici :
# nous avons d'abord jugé le nettoyage à l'accord entre modèles
# indépendants, qui montait de 49,9 % à 70,9 %. Cet accord était réel et
# ne voulait rien dire — les modèles s'accordaient sur un découpage
# effondré. Deux modèles d'accord à 99 % pour dire qu'une réunion à trois
# n'a que deux voix sont d'accord et ont tort. La répartition du temps de
# parole, elle, rend l'effondrement visible.

DEB_BASE = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speech-enhancement-models/")


@dataclass(frozen=True)
class Debruiteur:
    cle: str
    fichier: str
    mo: float
    nom: str
    famille: str      # 'gtcrn' ou 'dpdfnet' : deux API différentes
    vitesse: float    # multiple du temps réel, mesuré sur un fil
    note: str


DEBRUITEURS = (
    Debruiteur("leger", "gtcrn_simple.onnx", 0.5, "Léger", "gtcrn", 18.3,
               "Enlève le souffle sans toucher au timbre. C'est ce qui a donné "
               "la meilleure séparation dans nos mesures, et c'est presque "
               "instantané."),
    Debruiteur("recommande", "dpdfnet_baseline.onnx", 8.4, "Fort", "dpdfnet", 11.5,
               "Nettoie beaucoup plus, mais a fait disparaître une voix sur trois "
               "dans notre enregistrement d'essai. À réserver à un son très "
               "dégradé, et à vérifier en écoutant les extraits."),
    Debruiteur("maximum", "dpdfnet2.onnx", 9.8, "Très fort", "dpdfnet", 5.8,
               "Encore plus agressif, avec le même risque de confondre deux "
               "personnes. Deux fois plus lent que le précédent."),
)
DEB_PAR_CLE = {d.cle: d for d in DEBRUITEURS}
DEBRUITEUR_DEFAUT = "leger"


def inventaire_debruiteurs() -> list[dict]:
    return [{"cle": d.cle, "nom": d.nom, "mo": d.mo, "note": d.note,
             "vitesse": d.vitesse, "telecharge": (MODELS_DIR / d.fichier).exists()}
            for d in DEBRUITEURS]


def ensure_denoiser(cle: str, note=None):
    """Télécharge le débruiteur au besoin et rend (chemin, famille)."""
    d = DEB_PAR_CLE.get(cle) or DEB_PAR_CLE[DEBRUITEUR_DEFAUT]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    fichier = MODELS_DIR / d.fichier
    if not fichier.exists():
        message = f"téléchargement du nettoyeur « {d.nom} » ({d.mo:.0f} Mo, une seule fois)"
        print(message)
        if note:
            note(message)
        _download(DEB_BASE + d.fichier, fichier, "nettoyage du son")
    return fichier, d.famille


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

    dernier = [-1]

    def hook(count: int, block: int, total: int) -> None:
        if total <= 0:
            return
        done = min(count * block, total)
        # Une ligne par pour cent : le retour chariot se voit dans un
        # terminal, mais redirigé vers un fichier il produit des mégaoctets
        # de barre de progression.
        cent = int(100 * done / total)
        if cent == dernier[0] and done < total:
            return
        dernier[0] = cent
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


def ensure_models(embedding: str = DEFAULT_EMBEDDING,
                  note=None) -> tuple[Path, Path]:
    """Retourne (segmentation, empreintes), en téléchargeant au besoin.

    `note` reçoit les messages destinés au journal de l'interface, pour que
    l'attente d'un téléchargement de 30 Mo ne ressemble pas à un blocage."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    emp = PAR_CLE[resoudre(embedding)]
    emb_file = MODELS_DIR / emp.fichier

    def dire(message: str) -> None:
        print(message)
        if note:
            note(message)

    if not SEG_FILE.exists():
        dire("téléchargement du modèle de segmentation (6 Mo, une seule fois)")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "seg.tar.bz2"
            _download(SEG_URL, archive, "segmentation")
            with tarfile.open(archive, "r:bz2") as tar:
                tar.extractall(MODELS_DIR)
        if not SEG_FILE.exists():
            raise RuntimeError("Modèle de segmentation absent après extraction.")

    if not emb_file.exists():
        dire(f"téléchargement du modèle « {emp.nom} » ({emp.mo:.0f} Mo, une seule fois)")
        _download(EMB_BASE + emp.fichier, emb_file, "empreintes vocales")
        dire(f"modèle « {emp.nom} » prêt")

    return SEG_FILE, emb_file


def models_ready() -> bool:
    """Le strict nécessaire pour démarrer sans attendre un téléchargement."""
    return SEG_FILE.exists() and est_telecharge(DEFAULT_EMBEDDING)
