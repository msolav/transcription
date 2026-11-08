# Bibliothèque — portée

Un second programme, bien plus petit, qui ne fait que **conserver et
relire** : la liste des séances, le texte, et l'écoute synchronisée. Pas
de transcription, pas de séparation des voix, pas de clé d'API.

À qui il sert : à qui transcrit ailleurs — dans la version web, ou sur
une autre machine — et veut garder ses comptes rendus quelque part de
durable, avec l'audio pour les réécouter.

Rien n'est construit. Ce document sert à décider.

## Pourquoi pas le navigateur seul

Trois chemins ont été éprouvés le 7 novembre 2026, et deux sont fermés.

**La page web ne peut pas parler à l'application locale.** Depuis
`https://transcripteur.solav.workers.dev`, un `fetch` vers
`http://127.0.0.1:7878` est refusé par Chrome :

    blocked by CORS policy: Permission was denied for this request
    to access the `loopback` address space.

Ce n'est pas un en-tête qui manque. Le serveur d'essai renvoyait
`Access-Control-Allow-Origin`, `Allow-Headers` et
`Allow-Private-Network` : la requête n'est jamais sortie du navigateur,
le serveur local n'a rien vu passer. S'ajoute un second obstacle :
`port_libre()` tire un port au hasard à chaque lancement — 63580, 63581,
63582 sur trois essais — donc la page n'aurait même pas su où frapper.

**Le dossier partagé ne marche pas dans Safari.** `showDirectoryPicker`
permettrait à la page d'écrire dans un vrai dossier, lisible aussi par
l'application. Mesuré présent dans Chrome ; absent de Safari et de
Firefox, et MDN classe l'interface « not Baseline » pour cette raison.
C'est le navigateur de l'auteur : chemin écarté.

**Reste le programme local**, qui sert sa propre page sur 127.0.0.1.
Là, aucune restriction : ce n'est plus une page publique qui tend la
main vers la machine, c'est quelqu'un qui ouvre son propre programme.

## Ce que ça pèse

Mesuré, pas estimé : le même programme privé de ce qu'une bibliothèque
n'utilise pas — `sherpa_onnx`, `numpy`, `keyring`, `cryptography`, et
les clients des fournisseurs.

| | non compressé | compressé |
|---|---|---|
| application complète | 101 Mo | 46 Mo |
| bibliothèque | **34 Mo** | **17,4 Mo** |

Les quarante mégaoctets de `sherpa_onnx` font à eux seuls la moitié de
l'application complète. Ce qui reste est Python, FastAPI et uvicorn :
c'est le plancher, et on n'ira pas plus bas sans changer de langage.

## L'audio, et un bénéfice inattendu

La bibliothèque doit permettre l'écoute, donc garder le son. Pas
l'original : une version compressée suffit, et le navigateur la lit
sans rien installer.

| une réunion de 2 h 35 | |
|---|---|
| `source.m4a`, gardé aujourd'hui | 151 Mo |
| avec le wav 16 kHz, pendant le traitement | 470 Mo |
| mp3 mono à 64 kbit/s | **71 Mo** |

L'application sait déjà faire ce fichier : `to_mp3()` existe, et les
tranches envoyées à Groq sont déjà de ce format. Garder le mp3 plutôt
que l'original divise chaque séance par deux — et rend beaucoup moins
probable le disque plein qui a emporté une transcription de deux heures
et demie le 7 novembre.

**Mesuré, et la réponse est non.** Le mp3 ne peut pas remplacer
l'original si l'on veut pouvoir séparer les voix après coup. Même
conversation de 6,8 minutes, même modèle (ERes2Net), même nombre de voix
imposé :

| source | exact | même genre | autre genre |
|---|---|---|---|
| wav 16 kHz | **69,3 %** | 29,3 % | 1,3 % |
| mp3 mono 64 kbit/s | **38,9 %** | 15,9 % | **45,2 %** |

Trente points perdus, et surtout les erreurs entre genres différents
passent de 1,3 % à 45,2 % : à ce débit, le mp3 n'emporte plus de quoi
distinguer une voix d'une autre. Il reste parfaitement écoutable — c'est
ce qu'on lui demande ici — mais ce n'est plus un signal pour un modèle
d'empreintes.

Donc : le mp3 sert à **écouter**, jamais à **séparer**. La bibliothèque
n'a besoin que d'écouter, et 71 Mo par réunion de deux heures et demie
lui suffisent. L'application complète, elle, garde l'original tant que
quelqu'un peut vouloir y revenir — c'est le réglage
`garder_enregistrement` qui existe déjà. Les deux usages ne demandent
pas le même fichier, et c'est la seule conclusion à retenir.

## Ce qu'il faut écrire

Le plus gros est déjà là. `memoire.py` n'importe que la bibliothèque
standard — base, liste, chargement, suppression, place occupée. Les
exports (texte, sous-titres, json) ne lisent que des horodatages.

- **`transcripteur/bibliotheque.py`** : une petite application FastAPI
  avec les seules routes de la bibliothèque. `server.py` ne convient
  pas : il importe `pipeline` au premier niveau, qui amène `assets`,
  donc tout le reste.
- **`join_words`** sort de `pipeline` vers un module sans dépendances,
  pour que `sous_titres.py` cesse d'entraîner le pipeline derrière lui.
- **Une page allégée** : la liste des séances, le lecteur, le texte, les
  exports. Reprendre `seances.js` et la vue de lecture, sans l'écran de
  dépôt ni les réglages.
- **`Bibliotheque.spec`** : la liste d'exclusions ci-dessus.
- **Une quatrième ligne dans `paquets.yml`**, ou un second lot : quatre
  paquets de plus à construire et à publier.
- **L'import** : déposer un `.json` exporté, avec son mp3 à côté.

## Ce que ça coûte en entretien

Un second produit, quatre paquets de plus à chaque version, et une
interface qui partage son code avec la première sans être la même. Le
risque n'est pas la taille du travail, c'est la dérive : deux listes de
séances qui finissent par ne plus se ressembler.

Garde-fou : la bibliothèque ne reçoit **aucun code à elle**. Elle
n'expose qu'un sous-ensemble de ce que l'application fait déjà, et les
vérificateurs existants couvrent les deux.

## Ordre proposé

1. Mesurer la séparation des voix sur un mp3 mono 64 kbit/s. Si elle
   tient, le mp3 remplace l'original ; sinon il s'y ajoute et la
   question de la place reste entière.
2. Sortir `join_words`, écrire `bibliotheque.py`, éprouver qu'elle
   démarre sans numpy ni sherpa-onnx.
3. La page allégée.
4. Le spec, la construction, la publication.
