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
