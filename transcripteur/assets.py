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

def _dossier_modeles() -> Path:
    """Où vivent les modèles ONNX.

    À côté du code quand on travaille depuis les sources — c'est là
    qu'ils sont déjà, et rien ne justifie de retélécharger 300 Mo.

    Mais dans le dossier de données dès que l'application est empaquetée.
    Un programme installé est en lecture seule : sous Applications sur
    un Mac, sous Program Files sur un Windows. Écrire dedans échoue, et
    cela échouerait au pire endroit — au premier démarrage, chez
    quelqu'un qui vient d'installer, avec pour seul symptôme un
    téléchargement qui n'aboutit jamais."""
    if getattr(sys, "frozen", False):
        from . import memoire
        return memoire.dossier() / "models"
    return Path(__file__).parent.parent / "models"


MODELS_DIR = _dossier_modeles()

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

# `justesse` est la part du temps de parole correctement attribuée, mesurée
# sur une conversation de 6,9 minutes à quatre voix — deux féminines, deux
# masculines — avec le nombre de voix imposé. C'est le défaut signalé par
# l'usage : les genres se séparent, les voix de même genre se confondent.
#
# Pourquoi ce champ existe : le classement se faisait sur `poids`,
# c'est-à-dire sur le coût de calcul. « Choisir pour moi » prenait donc le
# modèle le moins cher de la famille, et le faisait sans jamais regarder
# s'il attribuait juste. Entre le premier et le dernier des multilingues,
# il y a vingt-trois points d'écart.
#
# Mesuré sur des voix de synthèse, faute de corpus annoté sous la main :
# le classement vaut, les valeurs absolues sont à prendre comme un ordre
# de grandeur. 0.0 signifie « pas mesuré ».
@dataclass(frozen=True)
class Empreinte:
    cle: str
    fichier: str
    mo: float
    nom: str
    famille: str      # 'multi', 'anglais' ou 'chinois' — langues d'entraînement
    poids: float
    note: str
    justesse: float = 0.0


CATALOGUE = (
    Empreinte("voxceleb_campplus", "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
              28.2, "Multilingue CAM++", "multi", 0.9,
              "Rapide, mais le moins juste des multilingues à la mesure : "
              "il confond aussi des voix de genres différents.", 0.416),
    Empreinte("voxceleb_campplus_lm", "wespeaker_en_voxceleb_CAM++_LM.onnx",
              27.9, "Multilingue CAM++ (LM)", "multi", 0.9,
              "Même idée, autre équipe, affiné à marge large. Rapide, et "
              "plus juste que le CAM++ ordinaire sans l'être beaucoup.", 0.452),
    Empreinte("voxceleb_resnet", "wespeaker_en_voxceleb_resnet34_LM.onnx",
              25.3, "Multilingue ResNet34", "multi", 1.4,
              "Bon compromis, et le réglage retenu par défaut : nettement "
              "plus juste que les CAM++ pour une fois et demie leur temps.", 0.605),
    Empreinte("voxceleb_eres2net", "3dspeaker_speech_eres2net_sv_en_voxceleb_16k.onnx",
              25.3, "Multilingue ERes2Net", "multi", 2.2,
              "Le plus juste à la mesure, et le plus lent : deux fois et "
              "demie le temps du CAM++. À prendre quand l'attribution "
              "compte plus que l'attente.", 0.648),
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
    """Le catalogue, le plus adapté à la langue en tête.

    La langue d'abord, puis la justesse mesurée, et le coût seulement
    pour départager. L'ordre se faisait auparavant sur le coût seul :
    « choisir pour moi » prenait le modèle le plus rapide de la famille
    sans jamais regarder s'il attribuait juste, alors qu'il y a
    vingt-trois points d'écart entre le premier et le dernier des
    multilingues. Un modèle non mesuré garde son rang d'avant, derrière
    ceux qui le sont."""
    familles = ORDRE.get((langue or "").lower()[:2], ORDRE_DEFAUT)
    return sorted(CATALOGUE,
                  key=lambda e: (familles.index(e.famille), -e.justesse,
                                 e.poids, e.mo))


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


# ffmpeg n'est plus dans le paquet. C'était de loin le plus gros
# morceau : 165 Mo sur Linux, où imageio-ffmpeg livre un binaire
# statique, et quelques dizaines ailleurs — plus que tout le reste
# réuni. Or il ne sert qu'au moment où l'on traite un enregistrement,
# et beaucoup de machines l'ont déjà.
#
# On le prend donc dans cet ordre : celui du système, celui qu'on a
# déjà téléchargé, celui qui accompagne une installation depuis les
# sources, et en dernier recours on va le chercher.
#
# Depuis PyPI, et non chez un fournisseur de binaires : c'est la roue
# imageio-ffmpeg, celle-là même qui était dans le paquet jusqu'ici,
# versionnée et servie par l'endroit d'où viennent déjà toutes les
# autres dépendances. Trois miroirs différents pour trois systèmes
# auraient été trois occasions de télécharger autre chose.
PYPI_FFMPEG = "https://pypi.org/pypi/imageio-ffmpeg/json"

# Des fragments, et non l'étiquette complète de la roue. Les étiquettes
# bougent d'une version à l'autre — macosx_10_9 est devenu macosx_10_13,
# manylinux2014 est devenu manylinux_2_28 — et une table d'étiquettes
# exactes cesse de trouver son fichier au prochain téléversement, sans
# prévenir, chez quelqu'un qui installe six mois plus tard.
_FRAGMENTS = {
    ("darwin", "x86_64"): ("macosx", "x86_64"),
    ("darwin", "arm64"): ("macosx", "arm64"),
    ("win32", "amd64"): ("win_amd64",),
    ("win32", "arm64"): ("win_arm64",),
    ("win32", "x86"): ("win32",),
    ("linux", "x86_64"): ("linux", "x86_64"),
    ("linux", "aarch64"): ("linux", "aarch64"),
}


def _fragments_roue() -> tuple[str, ...] | None:
    import platform
    sys_nom = ("darwin" if sys.platform == "darwin"
               else "win32" if os.name == "nt" else "linux")
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        machine = "amd64" if sys_nom == "win32" else "x86_64"
    elif machine in ("arm64", "aarch64"):
        machine = "arm64" if sys_nom in ("darwin", "win32") else "aarch64"
    elif machine in ("i386", "i686", "x86"):
        machine = "x86"
    return _FRAGMENTS.get((sys_nom, machine))


def dossier_ffmpeg() -> Path:
    from . import memoire
    return memoire.dossier() / "ffmpeg"


def _ffmpeg_telecharge() -> Path | None:
    nom = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    chemin = dossier_ffmpeg() / nom
    return chemin if chemin.exists() and os.access(chemin, os.X_OK) else None


def recuperer_ffmpeg(note=None) -> Path:
    """Va chercher ffmpeg et le range dans le dossier de données."""
    import json
    import zipfile

    def dire(m: str) -> None:
        _ecrire(m + "\n")
        if note:
            note(m)

    fragments = _fragments_roue()
    if not fragments:
        raise RuntimeError(
            "Pas de ffmpeg tout prêt pour ce système. Installer ffmpeg "
            "(apt install ffmpeg, brew install ffmpeg) puis relancer.")

    dire("téléchargement de ffmpeg (une seule fois)")
    with urllib.request.urlopen(PYPI_FFMPEG, timeout=30) as r:
        infos = json.loads(r.read())

    roue = None
    for fichier in infos["urls"]:
        nom = fichier["filename"]
        if nom.endswith(".whl") and all(f in nom for f in fragments):
            roue = fichier["url"]
            break
    if not roue:
        raise RuntimeError(
            f"Aucune roue ffmpeg pour {'+'.join(fragments)}. Installer "
            "ffmpeg sur le système puis relancer.")

    cible = dossier_ffmpeg()
    cible.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "roue.whl"
        _download(roue, archive, "ffmpeg")
        with zipfile.ZipFile(archive) as z:
            noms = [n for n in z.namelist()
                    if "/binaries/ffmpeg" in n and not n.endswith("/")]
            if not noms:
                raise RuntimeError("Roue ffmpeg inattendue : binaire absent.")
            # Le plus gros : la roue peut contenir un script d'appoint
            # à côté du binaire.
            nom = max(noms, key=lambda n: z.getinfo(n).file_size)
            sortie = cible / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
            with z.open(nom) as src, open(sortie, "wb") as dst:
                shutil.copyfileobj(src, dst)
    sortie.chmod(0o755)
    dire("ffmpeg prêt")
    return sortie


def ffmpeg_exe(note=None) -> str:
    """Le ffmpeg à employer, téléchargé au besoin."""
    système = shutil.which("ffmpeg")
    if système:
        return système

    deja = _ffmpeg_telecharge()
    if deja:
        return str(deja)

    # Installation depuis les sources : la roue est dans l'environnement.
    try:
        import imageio_ffmpeg
        chemin = imageio_ffmpeg.get_ffmpeg_exe()
        if chemin and Path(chemin).exists():
            return chemin
    except Exception:  # noqa: BLE001
        pass

    try:
        return str(recuperer_ffmpeg(note))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "ffmpeg est introuvable et n'a pas pu être téléchargé. "
            "L'installer sur le système (apt install ffmpeg, "
            f"brew install ffmpeg) puis relancer. ({exc})"
        ) from exc


def _ecrire(texte: str) -> None:
    """Écrit sur la sortie standard, s'il y en a une.

    Une application empaquetée sans console — c'est le cas de la version
    installée, qui ouvre une fenêtre et pas un terminal — a `sys.stdout`
    à None. `print()` le sait et ne fait rien ; `sys.stdout.write` lève
    une AttributeError.

    Ce qui ne plantait pas l'application, mais pire : le téléchargement
    des modèles échouait en silence au premier démarrage, et la
    séparation des voix ne marchait plus jamais, avec pour seule trace
    un « 'NoneType' object has no attribute 'write' » au milieu d'un
    traitement. La barre de progression ne sert qu'à décorer une
    attente ; elle n'a pas à décider si le programme fonctionne."""
    flux = sys.stdout
    if flux is None:
        return
    try:
        flux.write(texte)
        flux.flush()
    except Exception:  # noqa: BLE001
        pass


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
        _ecrire(f"\r  {label:22s} [{'█' * filled}{'·' * (width - filled)}] "
                f"{done / 1048576:5.1f}/{total / 1048576:.1f} Mo")

    urllib.request.urlretrieve(url, tmp, reporthook=hook)
    tmp.replace(dst)
    _ecrire("\n")


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
