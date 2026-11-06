# Transcripteur

Transcrit un enregistrement — audio ou vidéo — et sépare les voix. Dépose
un fichier, écoute chaque voix détectée, donne-lui un nom, récupère le
texte. Une vidéo se relit sous-titrée dans la page.

## Démarrage

### L'application installée

La façon normale, pour qui ne veut rien savoir de Python.

**macOS** — décompresser, glisser `Transcripteur.app` dans Applications.
À la première ouverture : clic droit sur l'application, **Ouvrir**, puis
**Ouvrir** de nouveau. Une seule fois. L'application n'est pas signée —
signer demande un compte Apple à 99 $ US par an — et macOS prévient
toujours dans ce cas.

**Windows** — décompresser le dossier où l'on veut, lancer
`Transcripteur.exe`. Si l'écran bleu « Windows a protégé votre
ordinateur » apparaît : **Informations complémentaires**, puis
**Exécuter quand même**. Une seule fois également.

L'application s'ouvre dans sa propre fenêtre, sans barre d'adresse et
sans fenêtre noire à côté. Au premier démarrage elle télécharge une
trentaine de mégaoctets de modèles, pendant qu'on branche sa clé.

Les paquets se construisent tout seuls à partir d'une étiquette de
version (`git tag v1.0 && git push --tags`) : voir
`.github/workflows/paquets.yml`. Localement :

```
pip install pyinstaller
pyinstaller --noconfirm Transcripteur.spec
python outils/eprouver_paquet.py      # le paquet démarre-t-il vraiment
```

### Depuis les sources

**macOS / Linux** : double-clique sur `Demarrer.command`
**Windows** : double-clique sur `Demarrer.bat`

Ou, si Python est déjà là :

```
python lancer.py            la fenêtre, comme l'application installée
python -m transcripteur     le serveur et le navigateur, avec les options
```

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

## Les clés

L'outil fait deux métiers, et chacun passe par un service différent.
**Groq** écoute l'enregistrement et écrit ce qui a été dit : sa clé est
obligatoire, elle est gratuite et ne demande pas de carte bancaire.
**Une IA**, Gemini par défaut, lit ce texte et en tire un compte rendu :
sa clé est facultative, gratuite elle aussi. Sans elle on obtient le
texte brut, ce qui suffit à qui rédige lui-même.

À la première ouverture, la page déroule les deux étapes dans l'ordre et
vérifie chaque clé au moment où elle est collée. Pour en changer plus
tard : **Clés et services**, au bas de la page.

La marche à suivre complète, en français et en anglais, est servie à
l'adresse `/aide` pendant que le programme tourne. C'est une page
autonome : elle s'enregistre, s'envoie par courriel et s'ouvre sans
serveur — utile pour quelqu'un qui n'a encore rien installé. Pour en
écrire une copie sans lancer le programme :

```
python -m transcripteur.guide > aide.html
```

Un abonnement Claude Pro ou ChatGPT Plus ne donne pas de clé d'API : ce
sont deux produits distincts, avec deux factures distinctes. Il n'y a
rien à acheter pour se servir de cet outil.

## Ce qui part sur le réseau, et ce qui reste

La séparation des voix tourne entièrement sur la machine. Seul l'audio
compressé en MP3 mono part chez Groq pour la reconnaissance de la parole,
et le texte chez l'IA choisie si l'on demande un compte rendu. Rien n'est
conservé après la fermeture du programme.

Les clés vont dans le trousseau du système — Trousseau d'accès sur macOS,
Gestionnaire d'identifiants sur Windows — et non dans un fichier du
dossier personnel : une clé d'API est un moyen de paiement, elle n'a pas
sa place en clair dans un JSON que la moindre sauvegarde recopie. Une
variable d'environnement (`GROQ_API_KEY`, `GEMINI_API_KEY`,
`ANTHROPIC_API_KEY`) l'emporte sur le trousseau, ce qui est commode pour
un essai et piégeux ensuite : une clé révoquée oubliée dans un shell
continue d'être envoyée à la place de la bonne. Le message de refus dit
d'où venait la clé qu'il a reçue.

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

## Ce que l'outil affirme, et ce qu'il n'affirme pas

La séparation des voix, sur un micro unique dans une salle, se trompe
souvent. Mesuré sur une réunion de 83 minutes : un quart des blocs sont
coupés en pleine phrase, et la personne à qui revient la fin n'est pas
toujours la bonne.

Demander à un modèle de langue de réparer cela a été essayé et mesuré.
Le résultat ne le justifie pas : en un seul appel sur le transcript
entier, le modèle approuve tout et ne corrige qu'un bloc sur six cents ;
par tranches, il propose une trentaine de corrections qui *dégradent*
le découpage au lieu de l'améliorer. Un modèle de langue ne sait pas qui
a parlé ; il ne peut que deviner à partir de la syntaxe, et là où le
texte se tient dans les deux sens, il devine mal.

L'outil ne cherche donc plus à affirmer qui a dit quoi. Il restitue ce
qui s'est dit, décidé et confié, et ne nomme une personne que lorsque la
conversation la désigne — quelqu'un se nomme, on l'interpelle. Un nom
prononcé pendant la réunion est une information fiable ; la répartition
des voix ne l'est pas. Les étiquettes « Voix 1 », « Voix 2 » ne sortent
jamais dans un document : une tâche sans responsable désigné est écrite
comme telle.

Un compte rendu qui attribue une décision à la mauvaise personne est
plus nuisible qu'un compte rendu qui n'en nomme aucune : l'erreur y est
invisible, et elle se propage.

## Sept formes de restitution

Compte rendu, décisions et suites à donner, résumé bref, par thème,
transcript lisible, questions soulevées — et un relevé des dates et
chiffres. Chaque forme affiche un aperçu de ce qu'elle donne, pour qu'on
la choisisse sans avoir à la payer pour la découvrir.

**Le relevé des dates n'emploie aucun modèle de langue.** Il est tiré du
texte à la lecture : rien ne peut y être inventé ni oublié. Il existe
parce qu'un compte rendu rédigé par un modèle a été mesuré sur une
réunion réelle de 2 h 42 : vingt-sept affirmations vérifiables sur
trente étaient exactes, et l'erreur qui comptait portait sur une date
corrigée en séance.

    « C'est-à-dire le 24 novembre, on se fait une rencontre ?
      C'était le 24 ? Non, le 17. Le 17 ? Oui, deux semaines. »

Le compte rendu avait retenu le 24 — la date proposée puis abandonnée.
C'est l'erreur la plus coûteuse qu'un compte rendu puisse contenir,
parce qu'elle est invisible à la relecture : la date fausse y a l'air
aussi sûre que les autres. Demander au modèle de suivre les corrections
aide, sans régler le cas des passages confus. Le relevé, lui, montre les
deux mentions dans l'ordre avec leur contexte : la lecture tranche en
une seconde.

**Relire** propose des corrections sans rien écraser. L'attribution
d'abord : un modèle de langue voit que « avant d'être » et « accordés »
forment une seule proposition, qu'une question appelle une réponse, qu'un
« exactement » vient de quelqu'un d'autre.

Le modèle se prononce sur chaque bloc, pas seulement sur ceux qu'il juge
fautifs. C'est ce qui rend la passe fiable : tant qu'on lui demandait la
seule liste des erreurs, la réponse vide restait la moins coûteuse et il
la choisissait souvent — sur cinq fenêtres identiques, à température
nulle, trois revenaient vides. En exigeant un verdict par bloc, une
réponse incomplète devient détectable : elle est écartée et signalée, au
lieu de passer pour une fenêtre sans erreur. Cinq essais identiques
rendent désormais exactement le même résultat. C'est ce qui répare les phrases
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

Groq applique deux limites de nature différente, et elles n'appellent pas
la même conduite. Le décompte quotidien glisse sur la journée plutôt que
de se remettre à zéro à minuit : l'attente annoncée se compte souvent en
minutes, pas en heures. Celle de la minute (8 000 jetons) est un ralentisseur :
le programme patiente le temps annoncé et reprend, en le disant dans le
journal. Celle du jour ne se franchit pas : la passe s'arrête net plutôt
que de rendre une relecture à moitié faite qui aurait l'air terminée.

Quand le quota du jour tombe, le message regarde d'abord quels modèles
répondent encore avant de conseiller quoi que ce soit. Une version
précédente affirmait qu'il suffisait de changer de modèle ; c'est faux
quand les trois sont épuisés, ce qui arrive vite puisqu'une relecture
complète en consomme la moitié.

**Résumer** rédige un compte rendu, une liste de décisions et de suites à
donner, un résumé bref ou une synthèse par thème. La consigne interdit
d'inventer une décision qui ne figure pas dans l'échange, et demande de
signaler ce qui est resté ambigu plutôt que de trancher.

## Vidéo et sous-titres

Une vidéo se dépose comme un audio : seule la bande-son est traitée,
l'image est ignorée par la transcription. mp4, mov, m4v, mkv, webm, avi
et quelques autres.

Une fois le texte écrit, la vidéo se relit dans un cadre au-dessus du
lecteur, sous-titrée. Le cadre a quatre boutons : couper les sous-titres,
afficher ou non le nom des voix, agrandir, passer en plein écran. La
barre de lecture, « Suivre » et les flèches du document commandent la
vidéo comme elles commandaient l'audio.

Les sous-titres s'enregistrent en `.srt` sous deux formes, depuis
**Enregistrer** : sans les noms, et avec le nom de la voix en tête de
réplique. Le nom reparaît toutes les trente secondes dans un tour long,
pour qui arrive en cours de route.

Ils ne sont pas découpés sur les tours de parole : un tour de réunion
dure couramment deux minutes, ce qui donnerait un pavé immobile à
l'écran. Ils sont retaillés depuis les horodatages des mots, deux lignes
de quarante-deux caractères au plus, une seconde au moins à l'écran et
six au plus, en coupant de préférence sur une fin de phrase, sinon sur
un silence, sinon sur une virgule. Une réplique ne franchit jamais un
changement de voix.

Un transcript rouvert depuis un export ancien, sans horodatage des mots,
ne peut pas être sous-titré : répartir le texte au prorata des
caractères donnerait des sous-titres d'aspect normal et faux de
plusieurs secondes. L'outil refuse plutôt que de les fabriquer.

Un format de vidéo que le navigateur ne sait pas afficher — `.wmv`,
`.flv` — se transcrit quand même : seule l'image manque, et le cadre le
dit.

## Ce que le programme retient

Il ne retenait rien : fermer la fenêtre noire effaçait tout, et garder
une réunion voulait dire penser à enregistrer un `.json`, savoir où il
était allé, et le rouvrir à la main.

Maintenant les séances restent. Sous la zone de dépôt, la liste des
transcriptions passées : la date, la durée, le nombre de voix, la place
occupée. **Rouvrir** rend le texte, les noms donnés aux voix, la
relecture et — si l'enregistrement est encore là — l'aperçu vidéo et la
possibilité de séparer les voix après coup. Rien n'est recalculé et rien
n'est repayé.

Les réglages de la dernière transcription reviennent d'eux-mêmes :
langue, nombre de voix, modèle, nettoyage du son. Personne n'en change
d'une réunion à l'autre.

**Jeter le son** libère de la place en gardant le texte — les
transcripts ne pèsent rien, les enregistrements pèsent tout.
**Supprimer** efface la séance et ses fichiers, en deux clics.

Tout cela vit dans un fichier SQLite et un dossier de séances, à
l'endroit où le système range les données d'une application :

| | |
|---|---|
| macOS | `~/Library/Application Support/Transcripteur` |
| Windows | `%APPDATA%\Transcripteur` |
| Linux | `~/.local/share/transcripteur` ou `$XDG_DATA_HOME` |

`TRANSCRIPTEUR_DONNEES=/un/autre/chemin` les met ailleurs — un disque
externe, un dossier synchronisé.

Pas de compte, pas de mot de passe, pas de serveur. Ce qu'un compte
retiendrait ne concerne que cette machine, et le demander à un serveur
reviendrait à tenir un registre de qui transcrit quoi.

## Voir ce que voit quelqu'un d'autre

Sur la machine où l'outil a été installé, les clés sont là depuis
longtemps : l'écran qui explique où en prendre une ne s'affiche plus
jamais, alors que c'est le seul que personne d'autre ne peut éviter.

```
python -m transcripteur --simulation
```

Le programme démarre comme chez quelqu'un qui vient de l'installer :
aucune clé connue, les variables d'environnement ignorées, le trousseau
du système ni lu ni écrit. Un bandeau le rappelle en haut de la page.
Les clés saisies pendant la simulation vont dans un fichier jetable, que
`--oublier-simulation` efface. Les vraies clés ne sont jamais touchées.

## Formats et limites

m4a, mp3, wav, flac, ogg, aiff, opus — et côté vidéo mp4, mov, m4v, mkv,
webm, avi, mpg, wmv, flv, ts, 3gp. Jusqu'à 2 Go.

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

Texte brut, sous-titres `.srt` — avec ou sans le nom des voix — et
`.json` avec les mots horodatés pour retraiter ailleurs. Les mêmes
sous-titres sont servis en WebVTT sur
`/api/jobs/<id>/soustitres.vtt?noms=1`, pour un lecteur extérieur.

## Licence

MIT. Utilisation, modification et redistribution libres, y compris
commerciales, à condition de conserver la mention de droit d'auteur.
Voir `LICENSE`.

Le dépôt était public depuis août sans licence, ce qui revenait à tout
montrer sans rien permettre : le droit d'auteur s'applique par défaut,
et personne — pas même l'association à qui l'outil est destiné —
n'avait le droit de s'en servir.

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
