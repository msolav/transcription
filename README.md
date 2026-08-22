# Transcripteur

Transcrit un enregistrement et sépare les voix. Dépose un fichier, écoute
chaque voix détectée, donne-lui un nom, récupère le texte.

## Démarrage

**macOS / Linux** : double-clique sur `Demarrer.command`
**Windows** : double-clique sur `Demarrer.bat`

Le premier lancement installe ce qu'il faut et télécharge 34 Mo de modèles.
Compte deux ou trois minutes. Les suivants démarrent en quelques secondes.

Le navigateur s'ouvre tout seul. Une fenêtre noire reste ouverte à côté :
c'est le programme, la fermer l'arrête.

Sur macOS, si un double-clic affiche « développeur non identifié » ou ne
fait rien : clic droit sur `Demarrer.command`, puis **Ouvrir**, puis
**Ouvrir** de nouveau dans la fenêtre d'avertissement. C'est à faire une
seule fois. Si le fichier s'ouvre dans un éditeur de texte au lieu de se
lancer, ouvre le Terminal, tape `chmod +x ` (avec l'espace), glisse le
fichier dedans, Entrée, puis double-clique.

## La clé Groq

À la première ouverture, la page demande une clé. Elle est gratuite :

1. https://console.groq.com/keys
2. Connexion par Google ou e-mail, sans carte bancaire
3. **Create API Key**, copier, coller dans la page

Elle est enregistrée dans `~/.transcripteur.json` et n'est plus redemandée.

## Ce qui part sur le réseau, et ce qui reste

La séparation des voix tourne entièrement sur la machine. Seul l'audio
compressé en MP3 mono part chez Groq pour la reconnaissance de la parole.
Rien n'est conservé après la fermeture du programme.

## Si Python manque

Le lanceur le dit et donne le lien. Sur Windows, cocher **Add Python to
PATH** pendant l'installation, sinon le lanceur ne le trouvera pas.

macOS a souvent déjà Python 3. Si ce n'est pas le cas, la première
exécution de `python3` propose d'installer les outils Xcode ; accepter
suffit.

## Réglages qui changent quelque chose

**Nombre de voix.** L'indiquer quand on le connaît. En détection
automatique le regroupement se trompe parfois d'une voix, surtout sur un
enregistrement compressé ou bruité.

**Langue.** Choisir la bonne améliore la transcription. La détection
automatique existe mais se trompe sur les enregistrements courts.

## Formats et limites

m4a, mp3, wav, flac, ogg, mp4, mov. Jusqu'à 2 Go.

Les fichiers longs sont découpés automatiquement avant l'envoi, et les
horodatages sont recalés sur la ligne de temps complète.

Compter une minute de calcul par quart d'heure d'enregistrement sur un
ordinateur récent, l'essentiel étant la séparation des voix.

Deux personnes qui se coupent la parole sont attribuées à celle qui parle
le plus fort sur le passage. Sur des entretiens à tour de rôle propre, ça
ne se remarque pas ; sur une réunion à quatre qui se chevauche, il y aura
des corrections à faire à la main.

## Si c'est long

La fenêtre noire affiche chaque étape avec le temps écoulé. Sur un
enregistrement de deux heures, compter une trentaine de secondes de
conversion, autant de découpage, puis l'envoi à Groq.

Si une étape reste bloquée bien au-delà, copier ce qu'affiche la fenêtre :
c'est là que se lit l'étape en cause.

## Réglages de l'attribution

Dans `transcripteur/pipeline.py`, en haut du fichier :

- `MIN_TURN_AUDIO` (0,30 s) : durée en dessous de laquelle un tour de
  parole détecté est traité comme un bruit d'écoute et non comme une
  prise de parole. C'est le premier réglage à toucher si des « hum » se
  transforment en répliques, ou à l'inverse si des réponses très brèves
  disparaissent.
- `MIN_TURN_WORDS` (2) : au-delà, une suite de mots est toujours
  considérée comme une vraie réplique.
- `BOUNDARY_WINDOW` (4 mots) : de combien une frontière peut se déplacer
  pour tomber sur une fin de phrase plutôt qu'au milieu d'un groupe.

L'ordre du traitement compte : les tours trop brefs sont écartés sur la
seule foi de l'audio, puis les frontières sont recalées sur la ponctuation
et les silences, et seulement ensuite les répliques restantes sont jugées.
Juger avant de recaler faisait passer la queue d'une phrase (« 100%. »
séparé de son « À ») pour une réplique à part entière.

## Sorties

Texte brut, sous-titres `.srt` avec le nom du locuteur, et `.json` avec les
mots horodatés pour retraiter ailleurs.

## Pour les curieux

- Séparation des voix : sherpa-onnx (segmentation pyannote + empreintes
  3D-Speaker CAM++), en ONNX, sans PyTorch
- Transcription : Whisper large-v3-turbo via Groq
- ffmpeg fourni par le paquet `imageio-ffmpeg`, rien à installer
- Le seuil de regroupement est réglé à 0.65, valeur qui retrouve le bon
  nombre de locuteurs aussi bien sur WAV que sur AAC dans nos essais
