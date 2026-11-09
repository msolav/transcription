"""Les quelques fonctions de texte que tout le monde partage.

Elles vivaient dans `pipeline`, qui est le plus lourd module du paquet :
il amène `assets`, donc les téléchargements de modèles, et par ses
importations tardives numpy et sherpa-onnx. `sous_titres` n'avait besoin
que de recoller des mots, et traînait tout cela derrière lui.

Ici, rien que la bibliothèque standard — et même pas elle. C'est ce qui
permet à la bibliothèque de démarrer sans les quarante mégaoctets de
sherpa-onnx.
"""

from __future__ import annotations

# Pas d'espace avant ces signes-là, et pas d'espace après ceux qui
# ouvrent. La règle française voudrait une espace fine insécable avant
# « ; : ! ? » ; Whisper ne la produit pas, et l'ajouter ici ferait
# diverger le texte du transcript de celui que l'on a reçu.
_COLLE_AVANT = ",.;:!?…%)]}"
_COLLE_APRES = "’'([{"


def join_words(words: list[dict]) -> str:
    """Recolle les mots avec des espaces, sans en mettre avant la ponctuation."""
    out = ""
    for word in words:
        text = word["text"]
        if out and not (text[:1] in _COLLE_AVANT or out[-1:] in _COLLE_APRES):
            out += " "
        out += text
    return out.strip()
