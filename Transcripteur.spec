# -*- mode: python ; coding: utf-8 -*-
"""
Recette d'empaquetage, pour PyInstaller.

    pyinstaller Transcripteur.spec

Ce qui demande de l'attention, et qui ne se voit pas à l'exécution
depuis les sources :

Les fichiers qui ne sont pas du code. L'interface est faite de pages
HTML et de scripts lus sur le disque ; PyInstaller ne suit que les
`import`, donc il ne les emporterait pas, et l'application s'ouvrirait
sur une page blanche.

Les bibliothèques à code natif. sherpa-onnx et imageio-ffmpeg portent
des binaires — les modèles de voix d'un côté, ffmpeg de l'autre — que
l'analyse des imports ne voit pas davantage. `collect_all` va les
chercher.

Les modèles ONNX ne sont PAS dans le paquet. Trois cents mégaoctets
pour un téléchargement qui, chez la plupart des gens, n'en servira que
trente : ils arrivent au premier démarrage, dans le dossier de données.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

binaries, datas, hiddenimports = [], [], []

# Les pages, les scripts, et le mode d'emploi.
datas += [("transcripteur/static", "transcripteur/static")]

# Les paquets à contenu natif ou à chargement dynamique.
for paquet in ("sherpa_onnx", "imageio_ffmpeg"):
    b, d, h = collect_all(paquet)
    binaries += b
    datas += d
    hiddenimports += h

# keyring trouve son coffre par points d'entrée : les modules d'arrière-
# plan ne sont jamais importés nommément, donc jamais emportés, et la
# clé d'API n'aurait nulle part où aller.
hiddenimports += collect_submodules("keyring.backends")

# uvicorn charge ses protocoles par leur nom, en chaîne de caractères.
hiddenimports += collect_submodules("uvicorn")

a = Analysis(
    ["lancer.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Matplotlib et consorts arrivent dans les bagages de certaines
    # dépendances et pèsent des dizaines de mégaoctets pour rien.
    excludes=["tkinter", "matplotlib", "PIL", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Transcripteur",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Faux : pas de fenêtre noire derrière l'application. Le repli vers
    # le navigateur écrit dans une console qui n'existera pas, ce qui
    # est sans conséquence — le navigateur s'ouvre quand même.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Transcripteur",
)

app = BUNDLE(
    coll,
    name="Transcripteur.app",
    icon=None,
    bundle_identifier="com.vincentmarsolais.transcripteur",
    info_plist={
        "CFBundleName": "Transcripteur",
        "CFBundleDisplayName": "Transcripteur",
        "NSHighResolutionCapable": True,
        # Sans quoi macOS range l'application en anglais et l'ouvre avec
        # les formats de date du système plutôt que ceux d'ici.
        "CFBundleDevelopmentRegion": "fr_CA",
        "LSApplicationCategoryType": "public.app-category.productivity",
        # L'application ne sert aucune page à l'extérieur : elle parle à
        # son propre serveur, sur 127.0.0.1.
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
    },
)
