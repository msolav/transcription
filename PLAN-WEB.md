# Version web — portée

Ce qu'il faudrait écrire pour que quelqu'un puisse transcrire une
réunion sans rien installer, et ce que cela coûte. Rien n'est construit :
ce document sert à décider.

## Ce que c'est

Une page servie par le Worker existant, qui fait tout le travail dans
l'onglet. Aucun serveur de calcul, aucune base, aucun compte. L'audio ne
part qu'à Groq, avec la clé de la personne — exactement comme
l'application installée. L'argument de confidentialité tient donc mot
pour mot : *le traitement se fait sur votre ordinateur*.

Ce que ce n'est pas : un service hébergé. Faire tourner ffmpeg et
onnxruntime sur un serveur reste hors de portée des Workers, et payer le
calcul de ses utilisateurs n'a aucun sens quand ils apportent déjà leur
propre clé gratuite. Cette partie-là du refus reste vraie.

## Pourquoi c'est possible, vérifié et non supposé

**Groq accepte les appels directs depuis un navigateur.** Préflight
mesuré le 7 novembre 2026 sur `api.groq.com/openai/v1/audio/transcriptions` :

    access-control-allow-origin: *
    access-control-allow-methods: GET,HEAD,PUT,PATCH,POST,DELETE
    access-control-allow-headers: authorization,content-type

Pas de mandataire à écrire, donc pas de serveur, donc pas de facture.

Les deux fournisseurs de relecture l'acceptent aussi, même jour, même
méthode. Gemini répond en renvoyant l'origine demandée et autorise
`x-goog-api-key`. Anthropic répond `*` et autorise `x-api-key` avec
`anthropic-dangerous-direct-browser-access`. La relecture du compte
rendu tient donc aussi dans l'onglet.

**La séparation des voix tourne en WebAssembly.** sherpa-onnx publie
`build-wasm-simd-speaker-diarization.sh` et pousse le résultat sur un
espace HuggingFace qui fonctionne. Mêmes modèles que l'application :
pyannote-segmentation-3.0 (6 Mo) plus un modèle d'empreintes (25 à 28 Mo).

**La conversion ne demande pas ffmpeg.** `decodeAudioData` puis un
`OfflineAudioContext` à 16 kHz donnent le mono dont le reste a besoin.

## La contrainte qui décide de tout : la mémoire

`decodeAudioData` développe le fichier entier à sa fréquence d'origine
avant qu'on puisse le réduire. Un `AudioBuffer` plafonne à 2 Go. La durée
maximale n'est donc pas un chiffre unique, elle dépend du fichier :

    durée max = 2 Go / (Hz × canaux × 4 octets)

| Fichier typique | Plafond |
|---|---|
| Vidéo 48 kHz stéréo | 93 min |
| Audio 44,1 kHz stéréo | 101 min |
| 44,1 kHz mono | 203 min |
| Dictaphone 16 kHz mono | 559 min |

Mesuré dans Chrome de bureau, fichiers 48 kHz stéréo :

| Durée | Tampon brut | Résultat |
|---|---|---|
| 15 min | 330 Mo | passe, 12 s |
| 30 min | 659 Mo | passe, 10 s |
| 60 min | 1 318 Mo | passe, 31 s |
| 90 min | 1 978 Mo | passe, 35 s |
| 120 min | 2 637 Mo | **échec** — `EncodingError` |

La formule prédit 93 min ; la mesure casse entre 90 et 120. Elle tient.

Deux conséquences. La réunion de 2 h 35 de l'autre jour ne passerait pas
en stéréo 48 kHz. Et il faut annoncer le plafond **avant** le dépôt, pas
après trente-cinq secondes de décodage — le code qui lit déjà la durée
du fichier pour l'estimation de temps sait aussi lire sa fréquence et son
nombre de canaux.

Il existe une sortie : **WebCodecs** (`AudioDecoder` + un démultiplexeur
MP4) décode par tranches et ne tient jamais le fichier entier en mémoire.
Le plafond disparaît. C'est un travail réel, et c'est le seul endroit de
ce plan où la complexité est sérieuse.

## L'architecture : une seule couture

L'interface ne parle au serveur que par une fonction, `api(chemin,
options)`, plus un `fetch` isolé pour les noms de voix. Vingt chemins en
tout. Une version web n'est donc pas une réécriture : c'est une
implémentation locale de ces vingt chemins, et le même
`index-vm.html` par-dessus.

| Chemin | En local |
|---|---|
| `/api/health`, `/api/models`, `/api/guide` | constantes figées à la construction |
| `/api/reglages` | `localStorage` |
| `/api/key` | `localStorage` — **et c'est une vraie différence**, voir plus bas |
| `/api/jobs` POST | lance le traitement dans un Worker |
| `/api/jobs/{id}`, `/cancel`, `/names` | état en mémoire |
| `/api/seances`, `/api/jobs/import` | IndexedDB, ou rien au premier jet |
| `/sample/`, `/media/` | `URL.createObjectURL` sur le fichier déposé |
| `/api/version` | le Worker le sert déjà |
| `/api/ouvrir` | `window.open` |
| `/api/relecture*` | appels directs aux fournisseurs, CORS vérifié |

Le portage de `sous_titres.py` (découpage en sous-titres) est du JS
direct : il ne lit que des horodatages.

## Palier 1 — transcription seule

Ce que ça fait : déposer, convertir, découper en tranches sous la limite
de Groq, envoyer, rendre le texte, exporter. Pas de séparation des voix,
pas de nettoyage.

Pourquoi en premier : aucun modèle à télécharger, pas de WASM, pas de
fils d'exécution, pas d'en-têtes particuliers. C'est la moitié du
pipeline et la plus demandée — qui veut juste le texte d'une réunion n'a
besoin de rien d'autre.

À écrire :

- le décodage et la réduction à 16 kHz ;
- le découpage en tranches : `DEFAULT_MAX_MB = 24`, mêmes règles que
  `split_audio`, avec ré-encodage en MP3 ou en WAV. **Point ouvert :** le
  navigateur n'encode pas le MP3 nativement. Soit `lamejs` (petit), soit
  envoyer du WAV à Groq — qui l'accepte, mais le WAV 16 kHz mono fait
  1,9 Mo la minute, donc douze minutes par tranche au lieu de quarante ;
- l'envoi à Groq, trois tranches en parallèle comme `TRANSCRIBE_WORKERS` ;
- `decouper_sans_voix` et la mise en blocs, portés de Python ;
- les exports.

Limites à dire sur la page : le plafond de durée, et que fermer l'onglet
perd le travail.

## Palier 2 — avec séparation des voix

Ajoute : les modèles WASM (31 à 34 Mo, mis en cache), la segmentation, le
regroupement, l'attribution des répliques, les extraits d'écoute.

À écrire :

- récupérer la construction WASM de sherpa-onnx plutôt que la compiler
  (emsdk 3.1.53 exigé, une version précise) ;
- les en-têtes **COOP/COEP** sur le Worker, sans quoi pas de
  `SharedArrayBuffer`, donc pas de fils, donc un WASM mono-fil nettement
  plus lent que les quatre cœurs de l'application ;
- le portage de `assign_speakers`, `snap_boundaries`, `clean_turns`,
  `build_blocks` — du JS pur, mais il faudra les mêmes vérificateurs,
  sinon les deux versions divergeront en silence.

**Inconnue à mesurer avant de s'engager :** la vitesse réelle du WASM.
L'application native tourne à ×0,30 du temps réel sur une vraie réunion.
Si le WASM mono-fil est trois fois plus lent, une réunion d'une heure
demande une heure et demie d'onglet ouvert — ce qui se défend mal.
Cette mesure est à faire sur l'espace HuggingFace existant, avant
d'écrire quoi que ce soit.

## Ce qui est moins bien que l'application installée

Il faut le dire sur la page plutôt que de le laisser découvrir.

1. **La clé n'est plus dans le trousseau.** `localStorage` est lisible
   par n'importe quel script de la même origine. Le site n'en charge
   aucun d'ailleurs, mais c'est un cran en dessous, et ça se dit.
2. **Rien ne survit à l'onglet** tant qu'IndexedDB n'est pas écrit.
3. **Le plafond de durée.**
4. **La machine travaille pendant tout ce temps**, onglet ouvert, et un
   portable sur batterie n'aime pas.

## Ordre proposé

1. Mesurer la vitesse du WASM sur l'espace HuggingFace. Une heure de
   travail, et elle décide si le palier 2 vaut la peine.
2. Trancher la question de l'encodage des tranches : `lamejs` ou WAV.
3. Palier 1, avec `decodeAudioData` et son plafond annoncé.
4. WebCodecs seulement si le plafond gêne vraiment.
5. Palier 2 si la mesure du point 1 est bonne.

## Sources

- <https://github.com/k2-fsa/sherpa-onnx/blob/master/build-wasm-simd-speaker-diarization.sh>
- <https://github.com/k2-fsa/sherpa-onnx/blob/master/.github/workflows/wasm-simd-hf-space-speaker-diarization.yaml>
- <https://github.com/groq/groq-typescript>
