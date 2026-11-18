# Passation : interface « VM » du Transcripteur

Pour l'agent qui reprend le travail fonctionnel. Ce document dit où en est
l'interface, ce qu'on veut en faire ensuite, et ce qu'il ne faut pas casser.
La charte complète est dans le skill `~/.claude/skills/vm-ui/` (SKILL.md,
`assets/vm.css`, `assets/vm.js`, `assets/vm-notes-reference.*`). À lire en premier.

## 1. État actuel

- `transcripteur/static/index-vm.html` (servi sur `/vm`) est un **fichier généré**.
  Ne pas l'éditer à la main : tout est reconstruit par `outils/vm-build/build2.py`
  à partir de `body2.html` (balisage), `tr2.css` + `tr_keep.css` (styles), du JS de
  `orig_index.html` (patché par `rep()`/`cut()` dans build2) et de `i18n_en.js`.
  - Les chemins sont relatifs au dossier du script (`HERE`).
  - `python outils/vm-build/verif_vm.py` vérifie les identifiants que le JS attend
    (`INTERFACE CONFORME`). `harness.py` simule l'API pour Playwright.
- `transcripteur/static/branchement.js` (ton travail) remplace `askForKey` et
  fabrique l'écran des clés (`.setup`, `.role`, `.etiq`, `.pas`, `.keyrow`,
  `.setupnav`, `.setupaside`, `.setupmenu`). Le style de ces classes est dans
  `tr2.css` (section « key screen »). Si tu changes le balisage, change le style
  avec, ou garde ces noms.
- Le serveur n'a pas été touché côté interface. `/classique` garde l'ancienne page.

## 2. Règles dures (jamais négociables)

1. **Rien ne saute.** Toute transition est graduelle (opacité, translate, `grid-template-rows`).
   Pas de `display:none` qui bascule sans transition, pas de `scrollIntoView` sur la page.
2. **Aucun défilement, nulle part.** Ni page, ni écran de clés, ni site public.
   Quand il y a plus de matière que d'écran : pagination (`translate` d'une colonne),
   étapes, ou fiche repliée. Voir « Pagination » dans le skill. Les très longs
   paragraphes d'un seul locuteur sont découpés par phrases (≈420 caractères).
3. **On peut toujours revenir en arrière** (bouton Retour sur chaque écran).
4. Clair / sombre, FR / EN, listes déroulantes maison (`vm.select`), pas de flèches
   sauf icônes d'envoi et de téléchargement, pas de mots qui personnifient l'outil.
5. Texte minimal. Le reste va dans un bouton « i » (`.tipwrap` / `.info` / `.tipbody`).
6. Ne jamais écrire de fausse clé dans la vraie configuration de l'utilisateur
   (tests : `env -i HOME=/tmp/fakehome python -m transcripteur --port 799x --no-browser`).

## 3. Ce qu'on veut changer maintenant

### 3.1 Écran des clés : un pas par écran

Aujourd'hui (capture 34) : une page dense, quatre étapes en liste numérotée,
un champ, des notes, un lien « marche à suivre en détail » qui ouvre une autre
page longue (`/aide`, capture 35). Pour un non-développeur, c'est trop.

Cible : **un parcours dans la fenêtre, sans défilement, une seule chose par écran.**

```
Retour                                  Étape 2 / 5   ▬▬▬▬▬▬▬▬▬▬▬▬▬▬ (barre de progrès fine)

   OBLIGATOIRE                                 (étiquette, mono)
   GROQ                                        (géant, Archivo condensée)
   Ouvrir la page des clés.                    (UNE phrase, grande)

   [ Ouvrir console.groq.com ]                 (gros bouton, s'ouvre dans un onglet)
   J'y suis déjà                               (lien discret = passer au pas suivant)

   i  (bulle : pourquoi, ce que ça coûte, plafond quotidien)
```

Découpage proposé à partir de `guide.CLES[*]["etapes"]` (ne pas recopier les textes
ailleurs : ils vivent dans `guide.py`, l'interface les lit via `/api/guide`) :

| Écran | Contenu |
|---|---|
| 0 | « Deux services » : une phrase + « i » (`POURQUOI_DEUX`). Deux grosses pastilles : Groq (obligatoire), Google/Claude (facultatif, passer). |
| 1 | Groq, pas 1 : ouvrir le site (bouton). |
| 2 | Groq, pas 2 : se connecter. **Ne pas lister GitHub** parmi les façons de se connecter (voir 3.3). |
| 3 | Groq, pas 3 : créer la clé (« Create API Key »). Petite illustration du bouton, en SVG, trait fin. |
| 4 | Groq, pas 4 : coller la clé. Champ + « Enregistrer ». Vérification en place, message d'erreur dans le même cadre. |
| 5 | Fait. Une phrase, un bouton « Transcrire un enregistrement ». |

Détails :
- Le compteur « Étape n / N » devient une **barre continue** qui se remplit
  (`transform: scaleX`, jamais un saut). Ses segments ne sont pas des puces.
- Les autres services (facultatifs) arrivent après l'écran 5 comme une seconde
  boucle identique, précédée d'un seul écran « Ajouter Google / Claude ? Oui / Plus tard ».
- Le « i » remplace tous les paragraphes explicatifs (`pour_quoi`, `prix`, `limites`).
  `NOTIONS` (abonnement ≠ clé, où la clé est rangée) = quatre « i » ou un écran
  facultatif, jamais un mur de texte.
- **`/aide` ne doit plus être une longue page.** Soit elle réutilise le même
  parcours (une étape par écran, sans défilement), soit elle disparaît du
  parcours normal et reste seulement comme page envoyée par courriel, en
  pagination plutôt qu'en défilement. Même règle sur le site public.
- Transition entre écrans : l'écran sortant glisse de 24 px en s'effaçant,
  l'entrant arrive de l'autre côté (`translate` + `opacity`, 700–900 ms,
  `var(--vm-ease)`). Pas de rechargement du `#stage-area` à la volée sans animation.
- Clavier : Entrée = suivant, Échap = retour. Le champ de clé reçoit le focus
  **après** la transition (sinon le navigateur fait défiler : `overflow: clip`
  sur html/body, jamais `hidden`).
- Pour que ça tienne dans toutes les fenêtres : `zoom: var(--fit)` calculé par JS
  (déjà fait pour l'écran actuel, voir `fit()` dans build2).

### 3.2 Site public (`site/index.html`, capture 36)

Aujourd'hui : une page qui défile, trois boîtes de téléchargement, deux notes
techniques, une liste. Cible : **une fenêtre, un geste à la fois.**

- Détecter le système (`navigator.userAgentData?.platform` / `userAgent`) et
  proposer **un seul gros bouton** : « Télécharger pour macOS », « … pour Windows »,
  « … pour Linux ». Un « i » ou un petit lien « Autre système » ouvre les autres.
- **Regrouper macOS** : un seul choix « Mac », puis une question « Quelle puce ? »
  avec deux pastilles (Apple M1–M4 / Intel) et un « i » qui explique le menu
  Pomme → À propos de ce Mac. Aujourd'hui deux boîtes `macOS` côte à côte
  prêtent à confusion.
- **Ajouter Linux** (voir 3.4).
- Mode d'emploi en étapes dans la même fenêtre, après le téléchargement :
  1. Télécharger. 2. Ouvrir (la mise en garde « application non signée » est
  différente par système : un écran par système, avec le geste exact : clic droit
  → Ouvrir sur Mac, Informations complémentaires → Exécuter quand même sur Windows,
  `chmod +x` ou « Exécuter » sur Linux). 3. Brancher la clé (même parcours que 3.1,
  si possible partagé). 4. Premier enregistrement.
- La section « Ce qui reste chez vous » devient un « i » ou un seul écran à quatre
  lignes, pas un bloc en bas de page.
- Même identité que l'application : Archivo (largeur 62 %–125 %), IBM Plex Mono,
  Source Serif 4, papier/encre + une couleur de signal, grain, `vm.css` / `vm.js`
  inlinés (le site est un fichier statique, `outils/batir_site.py`).
  Le site actuel utilise une police système et un orange `#ff3d12` : à aligner sur
  le cobalt de l'application, ou à justifier.

### 3.3 Pas de GitHub pour l'utilisateur

Quelqu'un qui n'est pas développeur ne doit **jamais** arriver sur GitHub : page
de versions, « assets », liste de fichiers pour tous les systèmes, interface en
anglais. À retirer :
- Les trois liens `github.com/.../releases/latest` du site.
- Le pied de page « Code source et versions : github.com/… » (ou le déplacer dans
  un « i » « Pour les curieux », sans lien en première ligne).
- La mention « Google, **GitHub** ou une adresse courriel » dans l'étape de
  connexion de Groq (`guide.CLES[0]["etapes"][1]`) : proposer « Google ou une
  adresse courriel ».

Pour servir les fichiers sans GitHub :
- Dépôt de versions : le workflow `paquets.yml` produit déjà les paquets ; ajouter
  une étape qui les pousse vers un stockage public (Cloudflare R2 + domaine du
  Worker, ou Worker qui sert un binaire par chemin) et fait pointer les boutons vers
  `/telecharger/mac-silicon`, `/telecharger/mac-intel`, `/telecharger/windows`,
  `/telecharger/linux`. Le dépôt GitHub peut rester comme coulisse.
- Nom de fichier lisible : `Transcripteur-macOS-Apple.zip`, pas `…-arm64-v1.2.3.zip`.

### 3.4 Linux

- Ajouter une ligne `ubuntu-latest` à la matrice de `paquets.yml` (PyInstaller,
  `Transcripteur.spec`). Livrable : `.tar.gz` ou AppImage (préféré : un seul
  fichier, double-clic). Vérifier que `Demarrer.*` a son équivalent
  (`Demarrer.sh`) et que `ffmpeg` est embarqué.
- Trousseau : sur Linux, `keyring` demande Secret Service (GNOME Keyring /
  KWallet). Prévoir le repli sur un fichier à droits `600` et le dire dans le
  « i » de l'écran des clés, sinon la clé ne se sauvegarde pas sur les
  installations minimales.
- Les étapes du site (3.2) doivent avoir un écran « Ouvrir » propre à Linux.

## 4. Pièges déjà rencontrés (ne pas les refaire)

- `overflow: hidden` sur html/body : le navigateur y fait défiler au `focus()`.
  Utiliser `overflow: clip`.
- Les menus déroulants dans un repli : `overflow: visible` seulement une fois le
  repli totalement ouvert, via `transition: overflow 0s .95s allow-discrete`.
- Les listes déroulantes à colonnes : marqueur carré calé sur la première ligne
  du texte (`top: calc(padding + demi-interligne)`), pas à `50 %`.
- Un bloc de texte plus haut que la page ne pagine pas : le découper.
- Les classes `.top`, `.opts` existent dans l'ancienne CSS : les noms `bar` et
  `settings` ont été pris pour cette raison.
- `file://` : la page ne trouve pas le serveur et croit qu'il n'y a pas de clé.
  Un bandeau le dit désormais ; le message d'erreur reste en français clair.
- Après un `bascule` thème/langue, ne jamais retraduire le contenu de
  l'utilisateur : marquer `data-no-i18n`.

## 5. Vérifier

```
python outils/vm-build/build2.py     # régénère static/index-vm.html
python outils/vm-build/verif_vm.py   # structure
python -m transcripteur --port 7991 --no-browser   # puis ouvrir /vm
env -i HOME=/tmp/fakehome python -m transcripteur --port 7992 --no-browser   # sans clé
```
Tester à 1440×900, 1280×720 et 390×844 : `document.documentElement.scrollHeight - innerHeight`
doit valoir 0 sur chaque écran du parcours. Faire une capture par étape.

## 6. Mise à jour du 17 novembre (après une transcription de 2 h perdue)

- `server.py` : la clé Groq est éprouvée (`config.check_key`) avant de lancer un traitement.
- `pipeline.py` : la demande d'arrêt est surveillée toutes les 0,2 s (lecture du processus de séparation dans un fil). À vérifier avec une vraie séparation.
- Interface : bouton « Clés » dans la barre, « Changer la clé » dans l'alerte, durée restante + heure de fin sous le pourcentage, interrupteur « Détails » (journal en direct), titre à taille stable (plus de mise à l'échelle automatique), séparation forcée à « aucune » si l'interrupteur est éteint au lancement.
- **À examiner côté serveur** : l'estimation affichée avant le lancement (« Environ 18 min » pour un fichier de 45,8 Mo sans séparation) paraît trop haute ; revoir `couts` dans `/api/health`. Une transcription seule devrait prendre quelques minutes.
- L'application installée (`/Applications/Transcripteur.app`) ne contient aucun de ces correctifs tant que le paquet n'est pas reconstruit.
- Séparer les voix après coup : bouton « Séparer les voix » dans la barre (visible seulement si le transcript n'a qu'une voix) → `POST /api/jobs/{id}/voix` (nombre de voix Auto/1–8), même écran de progression, ETA, Arrêter, Détails. Si l'audio n'est plus sur la machine, le sélecteur de fichier s'ouvre. Éprouvé seulement contre une simulation de la route.
- Barre d'actions : les sous-options d'« Enregistrer » ont un autre registre (mono capitales, couleur de signal, trait vertical) que les actions de la barre.
- Écart à vérifier : l'application empaquetée affiche « Sous-titres nommés » ; le `index-vm.html` construit ici n'a pas cette entrée (Texte / Sous-titres / Données). Reporter dans `body2.html` si le serveur la gère.

## 7. v1.3.1 : raffiner la séparation des voix, mise à jour assistée

- `transcripteur/raffinage.py` : passe de raffinage après la séparation de base, dans le même processus (`diariseur.py`, donc arrêtable). Empreintes des extraits, regroupement d'abord des extraits longs (≥ 2,5 s), profils moyens, classement du reste avec marge de confiance (un extrait court incertain prend la voix de son voisin), deux tours de recalcul. Le nombre de voix imposé prime ; sinon il est cherché au plus grand écart de similarité entre fusions. Option `raffiner` (`Options.raffiner`, champ de formulaire `raffiner=1` sur `/api/jobs` et `/api/jobs/{id}/voix`), interrupteur dans l'interface (retenu dans localStorage `tr-refine`), défaut éteint.
- **Mesure** (`outils/mesure_raffinage.py`, deux enregistrements à la vérité connue, quatre modèles) : avec le nombre imposé, le raffinage rattrape l'effondrement de « VoxCeleb CAM++ » (1 voix pour 2 ou 3 demandées → 2 et 3) ; en détection libre il égale la base (5 bonnes réponses sur 8, ni mieux ni pire). Justesse tour par tour non mesurée : il manque un enregistrement annoté. À faire avant de le mettre par défaut.
- Mise à jour assistée : `POST/GET /api/mise-a-jour` télécharge `SITE/telecharger/<plateforme>` dans Téléchargements et le montre ; bouton dans la bannière de `seances.js`. Pas de remplacement automatique (paquets non signés).
- Les exports (`/api/enregistrer`) s'écrivent depuis le programme : la fenêtre intégrée ignore `download`.

## 8. Menus Mac et mise à jour continue (non livré, après v1.3.1)

- `fenetre.py::_menus` : menus de la barre du haut sous macOS seulement. Entrées « Rechercher une mise à jour… » et « Clés et services… » dans le menu Transcripteur (via `Menu("__app__")`), Fichier, Actions, Aide. Chaque entrée appelle `window.trMenu(action)` (défini dans `build2.py`), qui clique le bouton existant. Sans `menu=` (pywebview ancien, autre système) la fenêtre s'ouvre comme avant.
- **pywebview 6.2.1 ne porte aucun raccourci clavier sur ses entrées de menu** (la touche est vide) : ⌘O, ⌘S, ⌘N et ⌘, sont gérés dans la page, seulement quand `window.pywebview` existe. Les menus Édition (copier/coller) et Présentation sont ajoutés par pywebview.
- Non vérifié : l'aspect réel des menus (aucun accès à la barre de menus depuis les tests) et si `#pick.click()` lancé depuis un menu, sans geste de l'utilisateur, ouvre bien le sélecteur de fichier dans WebKit.
- Mise à jour : indicateur « Mise à jour disponible » dans la barre (`#majbtn`), visible sur tous les écrans ; revérification toutes les 3 h ; `/api/version?force=1` ignore la réponse gardée en mémoire ; notification `#toast` visible partout.

## 9. Après le disque plein du 17 novembre (v1.3.2 en préparation)

- **Cause probable du plantage et de « Erreur 500 »** : disque plein (un envoi arrêté à 13,6 Mo sur 48, « No space left on device »). Le programme ne vérifiait rien et n'écrivait aucun journal.
- `server.py` : espace libre vérifié avant l'envoi (≈ 6 fois la taille du fichier + 300 Mo, sinon 507 avec le chiffre) ; une écriture qui échoue pour manque de place est dite en clair et nettoie le dossier partiel ; un gestionnaire d'erreurs général remplace « Erreur 500 » par la raison et écrit la trace.
- `transcripteur/journal.py` : `journal.log` dans le dossier de données (macOS : `~/Library/Application Support/Transcripteur/`), tourne à 2 Mo, jamais bloquant. `pipeline.log` y écrit aussi. **À proposer dans l'interface** : un lien « Ouvrir le journal ».
- **Bug corrigé** : l'import `run_in_threadpool` manquait depuis la v1.3 ; la vérification de la clé au départ ne s'exécutait donc jamais (erreur avalée par le `try`). Elle fonctionne maintenant, mais elle bloque aussi quand Groq est injoignable : à confirmer que c'est voulu.
- Séances enregistrées : la liste ne dépasse plus ce qui tient sous le titre ; au-delà, bouton « Toutes les séances (N) » → liste pleine fenêtre paginée (`body.sc-all`). Corrige le titre poussé sous l'en-tête quand la liste avait 2 lignes ou plus.

## 10. Raffiner avec l'aide de l'utilisateur (v1.3.3 en préparation)

- **Confiance** : `raffinage._niveau_conf` (écart de ressemblance entre la meilleure voix et la suivante, 0–1). Posée sur chaque passage (`block["conf"]`, `pipeline.attacher_confiance`), marquée « ? » dans le texte sous 0,3. **Mesure d'ambiguïté, pas probabilité d'exactitude, non calibrée** (aucun enregistrement annoté pour le faire).
- **`raffinage.raffiner_guide`** : profils construits à partir d'exemples (noms donnés aux voix + passages désignés, éventuellement coupés), pas d'un regroupement calculé. Les exemples dissemblables sont écartés et signalés, sauf ceux que l'utilisateur a désignés (`forts`). Une voix sans nom reste une voix à part. **Empreintes gardées dans `empreintes.npz`** (dossier de la séance) : relancer après un nouvel exemple prend des secondes.
- `pipeline.raffiner_selon_noms`, route `POST /api/jobs/{id}/raffiner-noms` ({noms, exemples:[{start,end,nom}]}), `_run_guide`. `job.raffinage` = rapport (`part_incertaine`, `part_avant`, `secondes_exemples`, `incertains`).
- Interface (`build2.py`, bloc « Raffiner avec votre aide ») : onglets « Qui est qui » et « Passages à vérifier » (les plus incertains d'abord, avec « Écouter » et « Couper ici » à l'instant de la lecture pour dire qui parle quand), repères pour s'arrêter (≈ 20 s d'exemples par personne, part incertaine < 5 % : **repères indicatifs, non validés**).
- **Pas fait** : propositions automatiques de coupes (détecter les changements de voix dans un extrait) ; tests sur une vraie réunion (seulement des enregistrements de test de quelques secondes) ; mesure de la justesse tour par tour.

## 11. Identifier les voix AVANT l'analyse (refonte du raffinage guidé, v1.3.4 en préparation)

- **Pourquoi** : demander de nommer les groupes d'une séparation déjà faite revient à nommer des voix pêle-mêle. Le nouveau flux part du texte (même à une seule voix) : empreintes de chaque passage de parole (`enrolement.preparer`, minutes, gardées dans `enrolement.npz` + `enrolement.json`), puis des passages sont proposés pour qu'on dise qui parle (coupes possibles, nouvelles personnes ajoutées au fil de l'eau), puis tout est classé d'après ces exemples (`enrolement.etiqueter`). Aucune séparation lourde.
- Routes : `POST /api/jobs/{id}/enrolement/preparer` (fil, suivi par `GET /api/jobs/{id}?light=1`), `/enrolement/classer` (synchrone, secondes), `/enrolement/terminer` (fil). `pipeline.preparer_enrolement` / `terminer_enrolement`. L'audio converti `audio16k.wav` reste dans la séance (≈ 170 Mo pour 1 h 30) pour les extraits coupés.
- Propositions : d'abord des passages aussi différents que possible (échantillonnage du plus éloigné) tant qu'il y a moins de deux personnes ; ensuite ceux qui ressemblent le moins à une voix connue, puis ceux qui hésitent. Suggestion de nom affichée en pointillés.
- **Confiance, corrigée** : l'ancienne (écart entre les deux meilleures voix) restait élevée même pour un passage qui ne ressemble à personne. Elle est remplacée par : ressemblance absolue à la voix retenue comparée à celle des exemples de cette personne (10e centile) ; **contrôle sur les exemples** (chacun retiré, profils refaits, la bonne personne ressort-elle ? « 17 fois sur 20 ») ; exemples suspects signalés ; taux de suggestions confirmées. Reste une mesure relative aux exemples donnés : exemples faux ou mélangés, confiance trompeuse.
- Ancien chemin `raffiner-noms` / `raffiner_guide` conservé côté serveur, plus appelé par l'interface.
- **Pas testé sur une vraie réunion** (enregistrements de test de quelques secondes).

## 12. Accueil : un seul choix « Voix » (v1.3.5 en préparation)

- Le champ 02 devient un choix à trois options : **Texte seul** / **Avec mon aide** (défaut, retenu dans `localStorage` `tr-modevoix`) / **Automatique**. Seul « Automatique » ouvre les réglages de l'ancienne séparation (nombre de voix, raffinage). Le vrai interrupteur `#sep` reste dans le DOM (masqué) pour ne pas toucher à la logique d'origine : le sélecteur le pilote.
- « Avec mon aide » : le traitement part sans séparation, et dès que le texte est prêt (`tick`, branche `done`) l'identification des voix s'ouvre d'elle-même (`window.ouvrirIdentification`). Le choix pris **au lancement** (`window.__identifierApres`) fait foi, pas celui d'après.
- Les essais Playwright posent `tr-modevoix` via `harness.install(mode=...)` (défaut `aucune`) ; `modecheck.py` couvre les trois modes.

## 13. Identification : ligne du temps et transport (v1.3.7)

- Chaque passage a une **ligne du temps** (tête de lecture, clic pour se placer, morceaux colorés par personne, coupes déplaçables par glissement, double-clic pour en supprimer) et un **transport** : Lecture/Pause, ±0,5 s, ±2 s, Boucle, « Couper à la position », « Écouter ce morceau ». Clavier : Espace, C, ← →.
- **Piège** : la page d'origine a son propre raccourci Espace (`#deck`) ; deux bascules s'annulaient. Le raccourci de l'écran d'identification est en phase de capture avec `stopImmediatePropagation`.
- Une première version n'avait que « Écouter » et « Couper ici » sans position visible ni retour arrière : à reprendre comme exemple de ce qu'il ne faut pas livrer pour une tâche de découpe audio.
- Test : `tlcheck.py` (faux lecteur à horloge simulée ; un vrai lecteur audio n'a pas été essayé).

## 14. Profils par personne, fin des répétitions (v1.3.8)

- **Cause des répétitions** : `classer` n'excluait que les passages entièrement nommés (≥ 85 % couverts). Un passage coupé ou laissé de côté revenait. Le client envoie maintenant `vus` (tous les passages montrés) et le serveur ne les repropose jamais.
- `classer(..., vus, cible)` : avec `cible`, propose les passages les plus ressemblants au profil d'une personne (≥ 8 s d'écart entre eux) pour l'étoffer ; l'écran liste par personne ses échantillons (écouter, retirer) avec « Trouver plus de passages de X ».
- **Limite de fond, non résolue** : les passages sont découpés sur les pauses, pas sur les changements de voix ; un passage peut mêler deux personnes et contaminer un profil. Retours réels : contrôle 46/66 sur 6 personnes avec 7 à 31 s d'exemples. Pistes : fenêtres plus courtes (1,5–3 s) avec vote, ou modèle d'empreintes plus discriminant, à mesurer sur un enregistrement annoté.
