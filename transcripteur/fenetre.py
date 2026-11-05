"""
L'application dans sa propre fenêtre.

C'est le point d'entrée de la version installée. Le programme reste ce
qu'il est — un serveur local et une page — mais sans barre d'adresse,
sans onglet, et sans fenêtre noire à côté qu'il ne faut pas fermer.

Trois choses que la version en ligne de commande pouvait se permettre et
pas celle-ci.

Le port. 7878 peut déjà servir à autre chose sur la machine de quelqu'un
d'autre ; en ligne de commande on le voit échouer et on en change, dans
une fenêtre on ne verrait rien. On en demande donc un au système.

Les modèles. `main()` les télécharge avant de démarrer, en écrivant dans
le terminal. Ici il n'y a pas de terminal : la première ouverture
resterait muette une minute ou deux, ce qui est exactement la durée au
bout de laquelle on décide qu'un programme est cassé. Le serveur démarre
donc tout de suite et les modèles se téléchargent derrière — pendant que
la personne branche sa clé, ce qu'elle doit faire de toute façon.

Et le repli. Si le système n'a pas de quoi afficher une fenêtre — un
Windows sans WebView2, un Linux sans WebKit — pywebview lève. Plutôt que
de mourir devant quelqu'un qui vient d'installer, on ouvre le navigateur
et on continue.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

TITRE = "Transcripteur"


def port_libre() -> int:
    """Un port dont le système garantit qu'il est disponible."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def servir(port: int) -> threading.Thread:
    """Démarre le serveur dans un fil, et le rend.

    uvicorn.Server plutôt que uvicorn.run : hors du fil principal, le
    second n'installe pas ses gestionnaires de signaux, mais il appelle
    aussi asyncio.run, qui y est interdit. Le premier s'en accommode —
    `capture_signals` se contente de ne rien faire quand il n'est pas
    sur le fil principal."""
    import uvicorn

    from .server import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port,
                            log_level="warning")
    serveur = uvicorn.Server(config)
    fil = threading.Thread(target=serveur.run, daemon=True)
    fil.start()
    return fil


def attendre(port: int, secondes: float = 30.0) -> bool:
    fin = time.time() + secondes
    while time.time() < fin:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.2)
    return False


def modeles_en_fond() -> None:
    """Télécharge les modèles sans bloquer l'ouverture.

    Un échec ici n'empêche pas de se servir du programme : le traitement
    les retéléchargera au premier besoin, en l'écrivant cette fois dans
    le journal de l'interface, où on peut le lire."""
    def tache() -> None:
        try:
            from . import assets
            assets.ensure_models()
        except Exception as exc:  # noqa: BLE001
            print(f"Modèles non téléchargés pour l'instant : {exc}")

    threading.Thread(target=tache, daemon=True).start()


def ouvrir(url: str) -> bool:
    """La fenêtre. Faux si le système n'en donne pas."""
    try:
        import webview
    except Exception as exc:  # noqa: BLE001
        print(f"Fenêtre indisponible ({exc}), ouverture dans le navigateur.")
        return False
    try:
        webview.create_window(TITRE, url, width=1280, height=860,
                              min_size=(900, 600), text_select=True)
        # Sur macOS, l'interface graphique n'existe que sur le fil
        # principal : c'est pour cela que le serveur est dans l'autre.
        webview.start()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"Fenêtre impossible ({exc}), ouverture dans le navigateur.")
        return False


def main() -> None:
    # Deux portes de service, pour pouvoir éprouver l'application
    # empaquetée. Une construction qui réussit ne prouve rien : les
    # pannes d'empaquetage — un fichier oublié, une bibliothèque native
    # absente — n'apparaissent qu'au démarrage. Or sans port connu on ne
    # sait pas où frapper, et sans moyen de retenir la fenêtre, l'essai
    # reste bloqué devant une interface que personne ne regarde.
    impose = os.environ.get("TRANSCRIPTEUR_PORT", "").strip()
    port = int(impose) if impose.isdigit() else port_libre()
    sans_fenetre = os.environ.get("TRANSCRIPTEUR_SANS_FENETRE", "").strip() not in ("", "0")

    url = f"http://127.0.0.1:{port}/vm"
    servir(port)

    if not attendre(port):
        print("Le serveur n'a pas démarré.")
        sys.exit(1)

    modeles_en_fond()

    if sans_fenetre:
        print(f"{TITRE} sert sur {url} (sans fenêtre).")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        return

    if ouvrir(url):
        return                      # la fenêtre s'est fermée : on s'arrête

    # Repli : le navigateur du système. Le fil du serveur étant un
    # démon, il faut tenir le fil principal en vie, sinon le programme
    # se termine à la seconde où la page s'ouvre.
    webbrowser.open(url)
    print(f"\n{TITRE} : {url}")
    print("Laisse cette fenêtre ouverte. Ferme-la pour arrêter le programme.\n")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
