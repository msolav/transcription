# -*- mode: python ; coding: utf-8 -*-
#
# La bibliothèque : conserver et relire, rien d'autre.
#
# Tout l'intérêt de ce paquet est son poids. Les exclusions ci-dessous
# ne sont donc pas une optimisation, elles sont la raison d'être du
# fichier : sans elles, PyInstaller suit les importations tardives de
# `pipeline` et embarque sherpa-onnx — quarante mégaoctets — pour du
# code que ce programme n'appelle jamais.
#
# Mesuré : 34 Mo contre 101, et 17,4 Mo compressés contre 46.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

RACINE = Path(SPECPATH)

# L'icône, partagée avec l'application complète. Même motif : ce sont
# les mêmes séances, vues par un programme plus petit.
_icones = RACINE / "outils" / "icone"
_ico = _icones / "icone.ico"
_icns = _icones / "icone.icns"
ICO = str(_ico) if _ico.exists() else None
ICNS = str(_icns) if _icns.exists() else None

# Groq et Gemini restent : la bibliothèque corrige et résume, et ce
# sont les deux services gratuits. Anthropic et OpenAI partent — leurs
# clients pèsent 29 et 27 Mo à eux seuls, ce qui ferait passer ce paquet
# de 33 Mo à près de 90, soit presque l'application complète, pour des
# services payants qu'on utilise de toute façon depuis celle-ci.
EXCLUS = [
    "sherpa_onnx", "numpy",
    "anthropic", "openai",
    "imageio_ffmpeg",
]

a = Analysis(
    [str(RACINE / "lancer_bibliotheque.py")],
    pathex=[str(RACINE)],
    binaries=[],
    # La page est celle de l'application complète : une seule interface
    # pour deux programmes, sinon les deux listes de séances finissent
    # par ne plus se ressembler.
    datas=[("transcripteur/static", "transcripteur/static")],
    # uvicorn charge ses protocoles par leur nom, en chaîne de
    # caractères : sans cela ils ne sont jamais vus comme importés.
    hiddenimports=collect_submodules("uvicorn"),
    excludes=EXCLUS,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Bibliotheque",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=ICO,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Bibliotheque",
)

app = BUNDLE(
    coll,
    name="Bibliotheque.app",
    icon=ICNS,
    bundle_identifier="com.vincentmarsolais.transcripteur.bibliotheque",
    info_plist={
        "CFBundleName": "Bibliothèque",
        "CFBundleDisplayName": "Bibliothèque",
        "NSHighResolutionCapable": True,
        "CFBundleDevelopmentRegion": "fr_CA",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
