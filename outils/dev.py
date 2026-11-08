#!/usr/bin/env python3
"""Le tour de développement : éditer, recharger, voir.

Pourquoi ce fichier existe. Pour voir une modification, le chemin était :
poser une étiquette, attendre une dizaine de minutes que les quatre
paquets se construisent, télécharger, glisser dans Applications, passer
Gatekeeper, répondre au trousseau. Un quart d'heure pour déplacer un
titre de deux pixels. Et l'application installée est un paquet figé :
elle porte sa propre copie du code, qu'aucune modification du dépôt ne
touche — relancer ne sert donc à rien non plus.

Ici, rien n'est empaqueté. Le serveur sert le dépôt tel qu'il est :

    Interface (HTML, CSS, JS)   on reconstruit, on recharge l'onglet.
                                Le serveur relit index-vm.html à chaque
                                requête : il n'a pas à redémarrer.
    Python                      le serveur redémarre tout seul.

L'empaquetage reste pour les versions, pas pour les essais.

    python3 outils/dev.py                   http://127.0.0.1:7878/
    python3 outils/dev.py --simulation      comme au premier démarrage,
                                            aucune clé connue, le vrai
                                            trousseau n'est pas touché
    python3 outils/dev.py --port 9000
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BATIR = RACINE / "outils" / "vm-build" / "build2.py"

# Ce script vit dans outils/ : sans cette ligne, il ne voit pas le
# paquet qu'il sert. Le sous-processus, lui, reçoit PYTHONPATH.
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

# Les fichiers dont index-vm.html est fabriqué. Les modifier à la main
# dans index-vm.html ne sert à rien : la prochaine construction les
# écrase — c'est arrivé, et l'aperçu vidéo est resté mort un moment sans
# que rien ne le signale.
SOURCES_UI = [
    RACINE / "outils" / "vm-build" / "body2.html",
    RACINE / "outils" / "vm-build" / "tr2.css",
    RACINE / "outils" / "vm-build" / "tr_keep.css",
    RACINE / "outils" / "vm-build" / "orig_index.html",
    RACINE / "outils" / "vm-build" / "i18n_en.js",
    RACINE / "outils" / "vm-build" / "build2.py",
]


def empreinte(fichiers) -> tuple:
    out = []
    for f in fichiers:
        try:
            out.append(f.stat().st_mtime_ns)
        except OSError:
            out.append(0)
    return tuple(out)


def batir(premier: bool = False) -> bool:
    """Refabrique index-vm.html. Rend True si ça a marché."""
    r = subprocess.run([sys.executable, str(BATIR)], cwd=RACINE,
                       capture_output=True, text=True)
    if r.returncode:
        # L'erreur va à l'écran et la boucle continue : une faute de
        # frappe dans le CSS ne doit pas faire tomber le serveur.
        sys.stderr.write(f"\n  interface — échec de la construction\n{r.stderr}\n")
        return False
    if not premier:
        # flush : sans lui, la ligne reste dans le tampon tant que le
        # terminal n'est pas un vrai terminal, et on croit que rien ne
        # s'est reconstruit.
        print(f"  interface refaite — recharger l'onglet  "
              f"({time.strftime('%H:%M:%S')})", flush=True)
    return True


def surveiller() -> None:
    """Reconstruit l'interface dès qu'une de ses sources change."""
    etat = empreinte(SOURCES_UI)
    while True:
        time.sleep(0.6)
        neuf = empreinte(SOURCES_UI)
        if neuf != etat:
            etat = neuf
            batir()


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=7878)
    p.add_argument("--simulation", action="store_true",
                   help="aucune clé connue, comme au premier démarrage")
    p.add_argument("--sans-navigateur", action="store_true")
    args = p.parse_args()

    if not batir(premier=True):
        sys.exit(1)
    threading.Thread(target=surveiller, daemon=True).start()

    env = dict(os.environ)
    env["PYTHONPATH"] = str(RACINE) + os.pathsep + env.get("PYTHONPATH", "")
    if args.simulation:
        env["TRANSCRIPTEUR_VIERGE"] = "1"
        # Le bac à sable de la simulation est un fichier temporaire qui
        # survit à l'arrêt : les clés saisies pendant un essai y restent,
        # et l'essai suivant démarrait avec elles. Autrement dit, on ne
        # pouvait simuler un premier démarrage qu'une seule fois. Le
        # vrai trousseau n'est pas touché — c'est tout l'intérêt de ce
        # bac.
        from transcripteur import config
        config.oublier_simulation()
        # Une clé laissée dans le shell l'emporte sur le trousseau, donc
        # aussi sur le bac vide : la simulation afficherait Groq comme
        # déjà branché. On les retire de l'environnement du serveur
        # seulement ; le shell de l'utilisateur n'est pas modifié.
        for fiche in config.FOURNISSEURS.values():
            env.pop(fiche["env"], None)

    url = f"http://127.0.0.1:{args.port}/"
    print(f"\n  {url}")
    print("  interface : enregistrer un fichier, recharger l'onglet")
    print("  python    : le serveur redémarre tout seul")
    if args.simulation:
        print("  simulation : aucune clé connue, le trousseau n'est pas touché")
    print("  Ctrl+C pour arrêter\n", flush=True)

    if not args.sans_navigateur:
        threading.Timer(1.8, lambda: webbrowser.open(url)).start()

    # Le navigateur plutôt que la fenêtre pywebview : outils de
    # développement, console, rechargement immédiat. La fenêtre native
    # n'a d'intérêt qu'à la fin, pour voir ce que voit l'utilisateur.
    #
    # --reload de uvicorn surveille le code Python et relance le serveur ;
    # --reload-dir le limite au paquet, sinon il surveille tout le dépôt,
    # y compris dist/ et build/, et se relance sans arrêt.
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", "transcripteur.server:app",
            "--host", "127.0.0.1", "--port", str(args.port),
            "--reload", "--reload-dir", str(RACINE / "transcripteur"),
            "--log-level", "warning",
        ], cwd=RACINE, env=env)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
