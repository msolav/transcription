# Transcripteur

Interface locale pour transcrire un enregistrement et séparer les voix.
Whisper (via Groq) écrit le texte, pyannote détecte qui parle quand, et les
deux sorties sont recollées sur la ligne de temps.

Le serveur tourne sur ta machine. Seul l'audio compressé part chez Groq pour
la reconnaissance vocale ; la détection des voix reste locale.

## Installation

```bash
pip install -r requirements.txt
```

ffmpeg doit être présent sur le système :

| Système | Commande |
|---|---|
| macOS | `brew install ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| Windows | `winget install Gyan.FFmpeg` |

## Configuration

```bash
export GROQ_API_KEY="..."   # console.groq.com
export HF_TOKEN="..."       # huggingface.co/settings/tokens
```

Sur Windows PowerShell : `$env:GROQ_API_KEY="..."`.

Il faut aussi accepter les conditions des deux dépôts, avec le compte qui a
émis le token :

- https://hf.co/pyannote/speaker-diarization-3.1
- https://hf.co/pyannote/segmentation-3.0

N'en accepter qu'un donne une erreur 401 qui ne dit pas laquelle manque.

## Lancement

```bash
python -m transcripteur
```

Le navigateur s'ouvre sur http://127.0.0.1:7878. Options : `--port`,
`--host`, `--no-browser`.

## Utilisation

Dépose un fichier dans le panneau de gauche, choisis la langue et le nombre
de voix si tu le connais, lance. Une fois le traitement fini, chaque voix
détectée apparaît en haut avec un extrait de six secondes pris dans son plus
long passage. Écoute, tape un nom, la transcription se met à jour pendant
la frappe.

Un clic sur un horodatage relance la lecture du fichier d'origine à cet
instant (le fichier ne repart pas sur le réseau, il est lu depuis le
navigateur).

Exports : texte brut, sous-titres `.srt` avec le nom du locuteur en préfixe,
et `.json` contenant les mots horodatés si tu veux retraiter derrière.

## Notes

- Le premier lancement télécharge les modèles pyannote (~100 Mo), ensuite ils
  sont en cache dans `~/.cache/huggingface`.
- La diarisation utilise CUDA ou Apple MPS si disponible, sinon le CPU.
  Compte quelques minutes de CPU par heure d'audio.
- Un seul traitement à la fois : deux en parallèle se ralentissent l'un
  l'autre plus qu'ils ne se répartissent le travail.
- Les fichiers au-delà de 24 Mo une fois convertis sont découpés
  automatiquement, et les horodatages de chaque morceau sont recalés sur la
  ligne de temps globale.
- Indiquer le nombre exact de personnes améliore nettement la séparation par
  rapport à la détection automatique.
- Les travaux sont gardés en mémoire vive et effacés à l'arrêt du serveur.
