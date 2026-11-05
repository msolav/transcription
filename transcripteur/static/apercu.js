/* Aperçu dans l'image, et sous-titres.
 *
 * Trois choses, qui n'en font qu'une pour qui s'en sert : une vidéo
 * déposée se relit dans un cadre au-dessus du lecteur, les sous-titres
 * s'affichent dessus, et les mêmes sous-titres s'enregistrent en .srt
 * avec ou sans le nom des voix.
 *
 * Pourquoi un fichier à part plutôt que dans l'interface. Une première
 * version de l'écran des clés, écrite dans index-vm.html, a disparu
 * pendant une réécriture du fichier — sans erreur, sans trace, il n'y
 * avait plus qu'à s'en apercevoir. Ici il n'y a rien à effacer, et les
 * deux interfaces reçoivent la même chose sans qu'on la pose deux fois.
 *
 * Ce que ce fichier emprunte à la page : les variables globales `job`,
 * `jobId`, `objectUrl`, l'élément #player, et les fonctions setupDeck,
 * queueSave et exportAs, qu'il enveloppe. Une déclaration `function` au
 * premier niveau d'un script classique est une propriété de l'objet
 * global : la réassigner change bel et bien ce qu'appelle la page. Un
 * `let` du premier niveau, non — mais il se lit, ce qui suffit ici.
 * verifier_apercu.py contrôle que ces points d'appui existent toujours.
 *
 * Le lecteur est un <video> même pour un fichier audio. L'API est la
 * même à l'identique (HTMLMediaElement), donc tout le code de lecture de
 * la page fonctionne sans y toucher, et il n'y a pas deux lecteurs à
 * tenir en accord. Sur un audio, le cadre reste simplement caché.
 */
(() => {
  'use strict';

  const L = (fr, en) => (window.vm && vm.lang ? vm.lang.t(fr, en) : fr);

  // Les sous-titres passent par <track> : c'est le navigateur qui les
  // affiche, au bon moment, y compris en plein écran. Les dessiner nous-
  // mêmes aurait voulu une horloge de plus, qui aurait dérivé.
  const CSS = `
.tr-ap { margin: 0 0 .5rem; border: 1px solid color-mix(in oklab, var(--vm-ink, #000) 18%, transparent);
  background: var(--vm-paper-2, #e6e3da); overflow: hidden; }
.tr-ap[hidden] { display: none; }
.tr-ap-bar { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
  padding: .3rem .5rem; border-bottom: 1px solid color-mix(in oklab, var(--vm-ink, #000) 12%, transparent);
  font: 500 var(--vm-s, .75rem)/1.2 var(--vm-font-mono, ui-monospace, monospace);
  letter-spacing: .04em; text-transform: uppercase; }
.tr-ap-bar .tr-ap-t { color: var(--vm-mute, #666); margin-right: auto;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 14rem; }
.tr-ap-bar button { font: inherit; letter-spacing: inherit; text-transform: inherit;
  color: var(--vm-ink, #000); background: transparent; cursor: pointer; padding: .25rem .5rem;
  border: 1px solid color-mix(in oklab, var(--vm-ink, #000) 22%, transparent);
  transition: background var(--vm-d-shut, .3s) var(--vm-ease-out, ease),
              color var(--vm-d-shut, .3s) var(--vm-ease-out, ease); }
.tr-ap-bar button:hover { background: color-mix(in oklab, var(--vm-ink, #000) 8%, transparent); }
.tr-ap-bar button[aria-pressed="true"] { color: var(--tr-on-accent, #fff);
  background: var(--vm-accent, #ff3d12); border-color: var(--vm-accent, #ff3d12); }
.tr-ap-bar button[disabled] { opacity: .4; cursor: default; }
.tr-ap-scene { position: relative; display: grid; place-items: center;
  background: var(--vm-paper-2, #e6e3da); }
/* La hauteur commande, pas la largeur. Étirée sur toute la largeur du
   socle, une vidéo 16:9 fait huit cents pixels de haut : elle recouvre
   le document qu'on est en train de lire, et la deuxième ligne de
   sous-titre passe sous le bord. En bornant la hauteur et en laissant
   la largeur suivre, le cadre garde la taille qu'on lui a demandée quel
   que soit le format du fichier. */
.tr-ap-scene video { display: block; width: auto; height: auto;
  max-width: 100%; max-height: var(--tr-ap-h, 24vh); background: #000; }
.tr-ap.grand .tr-ap-scene video { max-height: 56vh; }
/* ::cue plutôt qu'un calque à nous : le plein écran emporte les
   sous-titres avec la vidéo, ce qu'un calque posé à côté ne fait pas. */
.tr-ap-scene video::cue { background: rgba(8, 8, 7, .78); color: #f1efe9;
  font-family: var(--vm-font-display, system-ui), sans-serif; font-weight: 500;
  line-height: 1.3; }
.tr-ap-vide { padding: .6rem .7rem; color: var(--vm-mute, #666);
  font: var(--vm-s, .75rem)/1.4 var(--vm-font-mono, ui-monospace, monospace); }
`;

  function styler() {
    if (document.getElementById('tr-ap-css')) return;
    const s = document.createElement('style');
    s.id = 'tr-ap-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* Lire les variables de la page.
     `job`, `jobId` et `objectUrl` sont déclarés par un `let` au premier
     niveau de l'interface. Un tel `let` n'est PAS une propriété de
     window — contrairement à une déclaration `function` — mais il vit
     dans l'environnement lexical global, que ce script partage : le nom
     nu se résout, `window.job` vaut undefined. Écrit avec le préfixe,
     ce fichier ne montait jamais l'aperçu, sans lever d'erreur : il
     croyait simplement qu'aucun traitement n'était chargé.
     `typeof` sur un nom inconnu ne lève rien, d'où le garde-fou, qui
     laisse ce script fonctionner dans une page qui ne les déclare pas. */
  const leJob = () => (typeof job !== 'undefined' ? job : null);
  const sonId = () => (typeof jobId !== 'undefined' ? jobId : null);
  const sonUrl = () => (typeof objectUrl !== 'undefined' ? objectUrl : null);

  const etat = { noms: true, titres: true, grand: false, monte: false, vu: '' };
  let cadre = null, scene = null, piste = null;

  const player = () => document.getElementById('player');

  // ------------------------------------------------------------ le cadre

  function construire() {
    const dock = document.getElementById('dock');
    const lecteur = player();
    if (!dock || !lecteur) return null;
    // Un <audio> ne montrera jamais d'image : plutôt que d'ouvrir un
    // cadre noir que rien ne viendra remplir, on s'abstient.
    if (lecteur.tagName !== 'VIDEO') return null;

    styler();
    const el = document.createElement('div');
    el.className = 'tr-ap';
    el.id = 'apercu';
    el.hidden = true;
    el.innerHTML = `
      <div class="tr-ap-bar">
        <span class="tr-ap-t" id="tr-ap-nom"></span>
        <button type="button" id="tr-ap-st" aria-pressed="true"></button>
        <button type="button" id="tr-ap-noms" aria-pressed="true"></button>
        <button type="button" id="tr-ap-taille"></button>
        <button type="button" id="tr-ap-plein"></button>
        <button type="button" id="tr-ap-fermer" aria-label="Fermer">✕</button>
      </div>
      <div class="tr-ap-scene"></div>`;

    // Le cadre se glisse au-dessus du lecteur, dans le même dock : la
    // barre de défilement, « Suivre » et les flèches commandent déjà la
    // vidéo, puisque c'est le même élément.
    dock.insertBefore(el, dock.firstChild);
    scene = el.querySelector('.tr-ap-scene');
    scene.appendChild(lecteur);
    lecteur.hidden = false;
    lecteur.setAttribute('playsinline', '');

    // Un .wmv ou un .flv se transcrit très bien — ffmpeg lit tout — mais
    // aucun navigateur ne sait l'afficher. Sans ce message, le cadre
    // resterait noir et muet, et rien n'expliquerait pourquoi.
    lecteur.addEventListener('error', () => {
      if (scene.querySelector('.tr-ap-vide')) return;
      scene.insertAdjacentHTML('beforeend',
        `<p class="tr-ap-vide">${L(
          'Ce format de vidéo ne s\'affiche pas dans un navigateur. La '
          + 'transcription et les sous-titres fonctionnent quand même ; '
          + 'pour voir l\'image, convertir le fichier en .mp4.',
          'This video format will not display in a browser. The transcript '
          + 'and the subtitles still work; to see the picture, convert the '
          + 'file to .mp4.')}</p>`);
    });

    el.querySelector('#tr-ap-st').onclick = () => {
      etat.titres = !etat.titres;
      appliquerTitres();
      etiquettes();
    };
    el.querySelector('#tr-ap-noms').onclick = () => {
      etat.noms = !etat.noms;
      poserPiste(true);
      etiquettes();
    };
    el.querySelector('#tr-ap-taille').onclick = () => {
      etat.grand = !etat.grand;
      el.classList.toggle('grand', etat.grand);
      etiquettes();
    };
    el.querySelector('#tr-ap-plein').onclick = () => {
      // Le plein écran porte sur la scène et non sur la vidéo seule :
      // ainsi les sous-titres restent dans le cadre qui s'agrandit.
      const cible = scene;
      if (document.fullscreenElement) document.exitFullscreen();
      else if (cible.requestFullscreen) cible.requestFullscreen().catch(() => {});
    };
    el.querySelector('#tr-ap-fermer').onclick = () => {
      el.hidden = true;
      const l = player();
      if (l) l.pause();
    };
    return el;
  }

  function etiquettes() {
    if (!cadre) return;
    const seule = !(leJob() && leJob().separe);
    const b = id => cadre.querySelector('#' + id);
    b('tr-ap-st').textContent = etat.titres
      ? L('Sous-titres', 'Subtitles') : L('Sans sous-titres', 'No subtitles');
    b('tr-ap-st').setAttribute('aria-pressed', String(etat.titres));
    b('tr-ap-noms').textContent = L('Noms', 'Names');
    b('tr-ap-noms').setAttribute('aria-pressed', String(etat.noms && !seule));
    // Une seule voix : nommer n'apprend rien, et le bouton laisserait
    // croire que la séparation a eu lieu.
    b('tr-ap-noms').disabled = seule || !etat.titres;
    b('tr-ap-noms').title = seule
      ? L('Les voix ne sont pas séparées.', 'Voices are not separated.') : '';
    b('tr-ap-taille').textContent = etat.grand
      ? L('Réduire', 'Smaller') : L('Agrandir', 'Larger');
    b('tr-ap-plein').textContent = L('Plein écran', 'Full screen');
    b('tr-ap-nom').textContent = (leJob() && leJob().filename) || '';
  }

  // ------------------------------------------------------- les sous-titres

  function poserPiste(forcer) {
    const lecteur = player();
    if (!lecteur || !sonId()) return;
    const veut = `/api/jobs/${sonId()}/soustitres.vtt?noms=${
      etat.noms && leJob() && leJob().separe ? 1 : 0}&v=${etat.vu}`;
    if (!forcer && piste && piste.src.endsWith(veut)) return;

    if (piste) piste.remove();
    piste = document.createElement('track');
    piste.kind = 'subtitles';
    piste.label = L('Transcription', 'Transcript');
    piste.srclang = 'fr';
    piste.default = true;
    piste.src = veut;
    lecteur.appendChild(piste);
    // mode se règle après que le navigateur a pris la piste en compte ;
    // réglé avant, il est écrasé.
    piste.addEventListener('load', appliquerTitres, { once: true });
    setTimeout(appliquerTitres, 0);
  }

  function appliquerTitres() {
    const lecteur = player();
    if (!lecteur) return;
    for (const t of lecteur.textTracks) {
      t.mode = etat.titres ? 'showing' : 'hidden';
    }
  }

  // ------------------------------------------------------------- montage

  function monter() {
    const job = leJob();
    if (!job || !sonId()) return;
    if (!cadre) cadre = construire();
    if (!cadre) return;

    const lecteur = player();
    // Le blob du fichier déposé évite un aller-retour ; sinon on
    // redemande l'enregistrement au serveur, ce qui fait tenir l'aperçu
    // après un rechargement de page.
    const voulu = sonUrl() || `/api/jobs/${sonId()}/media`;
    if (lecteur && lecteur.getAttribute('src') !== voulu && !sonUrl()) {
      lecteur.src = voulu;
    }

    cadre.hidden = !job.video;
    if (!job.video) return;

    const vide = scene.querySelector('.tr-ap-vide');
    if (!job.sous_titrable) {
      if (!vide) {
        scene.insertAdjacentHTML('beforeend',
          `<p class="tr-ap-vide">${L(
            'Ce transcript ne porte pas les horodatages des mots : pas de sous-titres possibles.',
            'This transcript carries no word timestamps, so no subtitles can be made.')}</p>`);
      }
    } else {
      if (vide) vide.remove();
      poserPiste(false);
    }
    etiquettes();
  }

  // --------------------------------------------- les deux boutons d'export

  function boutons() {
    const groupe = document.querySelector('.savegroup .sg');
    if (!groupe || document.getElementById('tr-srt-noms')) return;
    const srt = groupe.querySelector('[data-x="srt"]');
    if (!srt) return;
    // Deux boutons explicites plutôt qu'un bouton et un réglage caché
    // ailleurs : on sait avant de cliquer ce qu'on va obtenir, et le
    // choix ne dépend pas de l'état d'un aperçu qu'on n'a pas ouvert.
    srt.textContent = 'Sous-titres';
    srt.setAttribute('data-en', 'Subtitles');
    const avec = document.createElement('button');
    avec.id = 'tr-srt-noms';
    avec.type = 'button';
    avec.setAttribute('data-x', 'srt-noms');
    avec.textContent = 'Sous-titres nommés';
    avec.setAttribute('data-en', 'Subtitles with names');
    avec.title = 'Chaque réplique commence par le nom de la voix';
    avec.setAttribute('data-en-title', 'Each line starts with the speaker name');
    srt.after(avec);
    avec.onclick = () => telecharger(true);
  }

  function telecharger(avecNoms) {
    if (!sonId()) return;
    const a = document.createElement('a');
    a.href = `/api/jobs/${sonId()}/soustitres.srt?noms=${avecNoms ? 1 : 0}`;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  // ------------------------------------------------------- les greffes

  function greffer() {
    const vraiDeck = window.setupDeck;
    if (typeof vraiDeck === 'function') {
      window.setupDeck = function () {
        const r = vraiDeck.apply(this, arguments);
        try { monter(); boutons(); } catch (e) { console.warn('aperçu', e); }
        return r;
      };
    }

    // Renommer une voix doit changer les sous-titres : autrement
    // l'aperçu affiche encore « Voix 2 » à côté du document qui dit
    // « Amélie », et on ne sait plus lequel croire.
    const vraiSave = window.queueSave;
    if (typeof vraiSave === 'function') {
      window.queueSave = function () {
        const r = vraiSave.apply(this, arguments);
        etat.vu = String(Date.now());
        clearTimeout(greffer._t);
        greffer._t = setTimeout(() => { if (cadre && !cadre.hidden) poserPiste(true); }, 700);
        return r;
      };
    }

    // Le .srt de la page était taillé à 84 caractères, sans tenir compte
    // des phrases ni des silences, et nommait la voix à chaque réplique.
    // On passe par le serveur, qui applique les règles du sous-titrage.
    const vraiExport = window.exportAs;
    if (typeof vraiExport === 'function') {
      window.exportAs = function (kind) {
        if (kind === 'srt') return telecharger(false);
        if (kind === 'srt-noms') return telecharger(true);
        return vraiExport.apply(this, arguments);
      };
    }
  }

  function demarrer() {
    greffer();
    boutons();
    if (window.vm && vm.lang && vm.lang.onChange) {
      vm.lang.onChange(() => { etiquettes(); if (cadre && !cadre.hidden) poserPiste(true); });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
