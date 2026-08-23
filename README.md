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

**Langue.** Choisir la bonne améliore la transcription, et réordonne la
liste des modèles de voix (voir plus bas). La détection automatique
existe mais se trompe sur les enregistrements courts.

**Modèle de voix.** Ce modèle transforme un extrait de parole en une
empreinte chiffrée ; deux extraits de la même personne doivent donner
deux empreintes proches. Ce qui décide de sa qualité, c'est la langue sur
laquelle il a été entraîné : un modèle nourri au mandarin sépare mal deux
francophones.

La liste se réordonne selon la langue choisie. En français, en espagnol,
en allemand, ce sont les modèles VoxCeleb qui viennent en tête : ils sont
entraînés sur des entretiens couvrant une centaine de nationalités, ce
qui en fait le choix le plus proche d'un modèle multilingue. En anglais,
TitaNet passe devant. En chinois, les modèles chinois.

Cet ordre traduit la langue d'entraînement, pas une précision mesurée.
Départager deux modèles d'une même famille demanderait un enregistrement
annoté que nous n'avons pas ; à l'intérieur d'une famille, le plus léger
est proposé en premier. Si deux personnes restent confondues, essayer une
autre architecture (ResNet34 plutôt que CAM++) coûte un téléchargement et
une nouvelle passe.

Rien n'est téléchargé tant qu'un modèle n'est pas réellement utilisé. La
liste indique, pour chacun, s'il est déjà sur la machine ou ce qu'il pèse.

**Nettoyage du son.** Utile, mais à dose légère : un débruiteur enlève le
souffle et la réverbération, et si on le pousse, il enlève aussi ce qui
distingue deux voix.

Mesuré sur dix minutes de réunion réelle, trois voix imposées, en
regardant comment le temps de parole se répartit entre les trois groupes :

| son | répartition |
|---|---|
| brut | 41,2 / 31,3 / 27,5 |
| nettoyage léger | 36,0 / 32,1 / 32,0 |
| nettoyage fort | 71,0 / 29,0 — une voix a disparu |

Le réglage léger est celui qui sépare le mieux, et il ne coûte presque
rien : une minute de calcul par dix-huit minutes d'enregistrement. C'est
le réglage par défaut.

Les réglages « Fort » et « Très fort » restent proposés pour un son
vraiment dégradé, mais dans notre essai ils faisaient fondre une personne
dans une autre. Après les avoir utilisés, écouter les extraits de chaque
voix avant de faire confiance au découpage.

Le nettoyage ne sert qu'à la séparation des voix : la transcription part
toujours du son d'origine, Whisper se débrouillant mieux avec du souffle
qu'avec des consonnes rabotées.

*Sur la manière dont ces chiffres ont été obtenus, et une erreur qu'ils
ont corrigée :* le nettoyage a d'abord été jugé à l'accord entre trois
modèles de voix entraînés séparément, qui montait de 49,9 % sur le son
brut à 70,9 % après nettoyage fort. Cet accord était réel et ne prouvait
rien : les modèles s'accordaient sur un découpage effondré. Deux modèles
d'accord à 99 % pour dire qu'une réunion à trois personnes n'en compte
que deux sont d'accord et ont tort. La répartition du temps de parole
rend cet effondrement visible, l'accord le masque. Toute mesure de
consensus a ce défaut : elle ne distingue pas la convergence vers le vrai
de la convergence vers la même erreur.

## Relire et résumer

Une fois le transcript obtenu, deux boutons font appel à un modèle de
langue à poids ouverts, servi par Groq avec la même clé. Rien à installer.

**Relire** propose des corrections sans rien écraser. L'attribution
d'abord : un modèle de langue voit que « avant d'être » et « accordés »
forment une seule proposition, qu'une question appelle une réponse, qu'un
« exactement » vient de quelqu'un d'autre. C'est ce qui répare les phrases
coupées en deux, qui représentaient un bloc sur cinq dans nos essais. Le
texte ensuite : coquilles, mots tronqués, ponctuation.

Chaque correction s'affiche en deux colonnes, actuel à gauche et proposé
à droite, sur la même portion de texte et à la même hauteur. Ce qui n'a
pas bougé est identique des deux côtés et sert de repère ; seuls les mots
retirés et ajoutés sont marqués. Pour un déplacement de frontière, la
comparaison porte sur la paire de blocs et non sur un seul, puisque c'est
la limite entre les deux qui se déplace.

Chaque correction se décoche. Un bouton bascule entre l'original et la
version relue ; les exports suivent ce qui est affiché. Refuser toutes les
corrections redonne exactement l'original.

Deux garde-fous. Une correction de texte qui s'éloigne trop de l'original
est refusée avant même d'être montrée : c'est le compte rendu d'une
réunion, ce qui a été dit prime sur ce qui aurait été mieux dit. Et un nom
de personne inventé par le modèle est ignoré ; seules les personnes déjà
identifiées dans l'enregistrement peuvent recevoir une réplique.

La limite, elle, est de fond : le modèle ne lit que du texte. Quand
quelqu'un termine la phrase d'un autre, la syntaxe ne montre aucune
rupture, et la relecture peut réunir sous un seul nom ce que deux
personnes ont dit. Seul le son porte cette information. C'est la raison
d'être du bouton de comparaison.

**Le contexte.** Un champ libre, sous les deux boutons, où écrire ce que
la transcription ne peut pas deviner : les sigles, les noms propres, le
rôle de chacun. « AEPP = Association des entreprises. Vincent développe le
site, Annie dirige, Dominique gère les locaux. » Trois lignes suffisent.

C'est ce qui manque le plus au correcteur : un sigle comme IMER ou AEPP
n'existe dans aucun dictionnaire, et Whisper le rend au son. Savoir qui
fait quoi aide aussi à décider qui répond à qui. Le texte est transmis
comme du contexte, pas comme une consigne, et il est retenu d'un panneau
à l'autre : ce qui vaut pour la relecture vaut pour le résumé.

**Ce que ça consomme.** Le forfait gratuit de Groq donne 200 000 jetons
par jour et par modèle. Une relecture complète d'une réunion de 80 minutes
en demande environ 120 000 : l'attribution seule 57 000, le texte seul
65 000. La fenêtre de dialogue annonce le montant avant de lancer, et il
se recalcule quand on décoche une des deux passes.

Le quota étant compté par modèle, en épuiser un ne bloque pas les autres :
changer de modèle dans la liste suffit à continuer le même jour. Si le
quota tombe en cours de route, la passe s'arrête net et le dit, plutôt que
de rendre une relecture à moitié faite qui aurait l'air terminée.

**Résumer** rédige un compte rendu, une liste de décisions et de suites à
donner, un résumé bref ou une synthèse par thème. La consigne interdit
d'inventer une décision qui ne figure pas dans l'échange, et demande de
signaler ce qui est resté ambigu plutôt que de trancher.

## Formats et limites

m4a, mp3, wav, flac, ogg, mp4, mov. Jusqu'à 2 Go.

Les fichiers longs sont découpés automatiquement avant l'envoi, et les
horodatages sont recalés sur la ligne de temps complète.

Compter une minute de calcul par quart d'heure d'enregistrement sur un
ordinateur récent, l'essentiel étant la séparation des voix. Celle-ci
utilise autant de cœurs que la machine en a physiquement
(`DIARIZE_THREADS` dans `pipeline.py`). Un modèle lourd comme
ERes2NetV2 triple ce temps sans rien apporter hors du chinois.

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
- Le catalogue des empreintes vit dans `assets.py` : chaque modèle y
  déclare sa taille, sa famille linguistique et son coût de calcul. En
  ajouter un tient en une ligne, à condition qu'il figure dans la release
  `speaker-recongition-models` de sherpa-onnx
