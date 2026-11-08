/* ============================================================
   L'écran des clés : un pas par fenêtre.
   ============================================================

   Ce que remplace ce fichier : une page dense — quatre étapes en liste
   numérotée, un champ, deux notes, un lien vers une page plus longue
   encore. Tout y était vrai et rien n'y était faisable, parce qu'on
   demandait à quelqu'un qui n'a jamais vu de clé d'API de lire d'abord
   et d'agir ensuite.

   Ici, une seule chose par écran : une phrase, un geste, et un bouton
   « i » pour qui veut savoir pourquoi. Le reste du parcours est une
   barre fine qui se remplit. On peut toujours revenir.

   Ce fichier vit hors de index-vm.html, qui est engendré : une première
   version de cet écran, écrite dans la page, a disparu à la
   régénération suivante, sans erreur et sans trace.

   Il emprunte à la page `$`, `api`, `escapeHtml`, `ready`, `vm`, et
   remplace `askForKey`. Les textes ne sont pas écrits ici : ils
   viennent de guide.py par /api/guide, dans la langue demandée. Trois
   copies d'une marche à suivre divergent en une semaine, et c'est la
   copie que lit le débutant qui fait le plus de dégâts.
   ============================================================ */

(function () {
  'use strict';

  const L = (fr, en) => (window.vm && vm.lang ? vm.lang.t(fr, en) : fr);
  const esc = s => (typeof escapeHtml === 'function' ? escapeHtml(s)
    : String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;',
      '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]));

  // Sortir : 360 ms, entrer : 440 ms. Ensemble, les 700 à 900 ms de la
  // charte — assez pour qu'on voie le mouvement, trop court pour qu'on
  // l'attende.
  const SORTIE = 360, ENTREE = 440;

  const CSS = `
.setup { display: flex; flex-direction: column; }
.setupbar { position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: color-mix(in oklab, var(--vm-ink) 12%, transparent); }
.setupbar i { display: block; height: 100%; background: var(--vm-accent);
  transform-origin: left center; transform: scaleX(var(--part, 0));
  transition: transform .8s var(--vm-ease); }
.setuptop { position: absolute; top: 14px; right: var(--pad); z-index: 2;
  font: 500 .7rem/1 var(--vm-font-mono); letter-spacing: .12em;
  text-transform: uppercase; color: var(--vm-mute); }

/* L'écran qui glisse. Rien d'autre ne bouge : la barre, le compteur et
   le bouton Retour restent en place d'un pas à l'autre, sinon le regard
   les suit au lieu de lire. */
.setup > .ecran { display: flex; flex-direction: column; align-items: flex-start;
  gap: 18px; max-width: min(1100px, 92vw); width: 100%; opacity: 1; translate: 0 0;
  transition: opacity ${SORTIE}ms var(--vm-ease), translate ${SORTIE}ms var(--vm-ease); }
.ecran.part { opacity: 0; translate: -24px 0; }
.ecran.vient { opacity: 0; translate: 24px 0; transition: none; }

.etiq { font: 700 .7rem/1 var(--vm-font-mono); letter-spacing: .14em;
  text-transform: uppercase; color: var(--vm-mute); }
.etiq.oblig { color: var(--vm-accent); }
.geste { font: 300 clamp(1.2rem, 2.6vw, 1.75rem)/1.25 var(--vm-font-display, inherit);
  margin: 0; max-width: 26em; }

/* Les gestes à faire dans l'autre onglet : numérotés, sur toute la
   largeur, chacun sa colonne quand la fenêtre le permet. */
.gestes { list-style: none; counter-reset: g; margin: .4rem 0 0; padding: 0;
  display: grid; gap: 1.4rem 2.2rem; width: 100%;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr)); }
.gestes li { counter-increment: g; display: flex; flex-direction: column;
  gap: .3rem; padding-top: .8rem;
  border-top: 2px solid color-mix(in oklab, var(--vm-ink) 20%, transparent); }
.gestes li::before { content: counter(g, decimal-leading-zero);
  font: 500 .7rem/1 var(--vm-font-mono); letter-spacing: .12em;
  color: var(--vm-accent); }
.gestes b { font: 600 1.05rem/1.25 var(--vm-font-display, inherit); }
.gestes span { color: var(--vm-mute); font-size: .95rem; line-height: 1.45; }
.actes { display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap;
  margin-top: .4rem; }
.gros { font: 600 1rem/1 var(--vm-font-display, inherit); letter-spacing: -.01em;
  padding: 1rem 1.5rem; border: 0; cursor: pointer; color: var(--tr-on-accent, #fff);
  background: var(--vm-accent); transition: filter .4s var(--vm-ease-out); }
.gros:hover { filter: brightness(1.12); }
.discret { font: 400 .92rem/1 inherit; color: var(--vm-mute);
  background: none; border: 0; padding: 4px 0; cursor: pointer;
  text-decoration: underline; text-underline-offset: 3px; }
.discret:hover { color: var(--vm-accent); }
.pastilles { display: flex; gap: 12px; flex-wrap: wrap; }
.pastille { flex: 1 1 15rem; text-align: left; padding: 1rem 1.2rem; cursor: pointer;
  background: none; color: inherit; font: inherit;
  border: 1px solid color-mix(in oklab, var(--vm-ink) 22%, transparent);
  transition: border-color .4s var(--vm-ease-out), background .4s var(--vm-ease-out); }
.pastille:hover { border-color: var(--vm-accent);
  background: color-mix(in oklab, var(--vm-accent) 7%, transparent); }
.pastille b { display: block; font: 800 1.15rem/1.1 var(--vm-font-display, inherit); }
.pastille span { color: var(--vm-mute); font-size: .92rem; }
.pastille em { font-style: normal; color: var(--vm-accent); font: 700 .68rem var(--vm-font-mono);
  letter-spacing: .12em; text-transform: uppercase; display: block; margin-bottom: 4px; }
.etat-oui { color: var(--tr-ok, #2c7a3f); }
`;

  function styler() {
    if (document.getElementById('tr-setup-css')) return;
    const s = document.createElement('style');
    s.id = 'tr-setup-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  let guide = null;

  async function charger() {
    if (guide) return guide;
    const lg = (window.vm && vm.lang ? vm.lang.get() : 'fr');
    guide = await api('/api/guide?langue=' + lg);
    return guide;
  }

  /* `file` est la suite d'écrans à traverser, `i` celui qu'on regarde.
     Elle se construit au départ et se complète en route : répondre
     « oui » à « ajouter l'IA ? » y insère quatre pas de plus, ce qui
     allonge la barre de progrès au lieu de la faire mentir. */
  const etat = { file: [], i: 0, presentes: {}, sommaire: false };

  /* Deux écrans par service, non quatre. Ouvrir le site, s'y
     connecter, créer la clé : trois gestes qui se font d'affilée dans
     l'autre onglet, sans revenir ici entre chaque. Les séparer
     obligeait à faire l'aller-retour trois fois pour lire trois
     phrases. Ils tiennent sur un écran ; le champ garde le sien, parce
     que c'est là qu'on revient. */
  function pasDe(c, option) {
    return [{ type: 'gestes', c, option }, { type: 'cle', c, option }];
  }

  function construire(o) {
    const cles = guide.cles;
    const groq = cles.find(c => c.id === 'groq') || cles[0];
    if (o.sommaire) return [{ type: 'sommaire' }];
    const f = [{ type: 'intro' }];
    if (!etat.presentes.groq) f.push(...pasDe(groq));
    f.push({ type: 'offre' });
    return f;
  }

  async function ouvrir(options) {
    styler();
    const o = options || {};
    const dock = $('#dock');
    if (dock) dock.hidden = false;

    let d = null;
    try { d = await charger(); } catch (e) { d = null; }
    if (!d) {
      $('#stage-area').innerHTML = `<div class="setup"><h2>${L(
        'Serveur injoignable', 'Server unreachable')}</h2><p class="geste">${L(
        "Cette page n'a pas pu lire la marche à suivre. Vérifier que la "
        + 'fenêtre noire du programme est toujours ouverte, puis recharger.',
        'This page could not load the setup instructions. Check that the '
        + "program's black window is still open, then reload.")}</p></div>`;
      return;
    }

    let h = null;
    try { h = await api('/api/health'); } catch (e) { h = null; }
    etat.presentes = (h && h.cles) || {};
    etat.sommaire = o.sommaire === true
      || (o.assistant !== true && etat.presentes.groq && !o.service);

    if (o.service) {
      const c = d.cles.find(x => x.id === o.service);
      etat.file = c ? [...pasDe(c, !c.requis), { type: 'fini', retour: true }]
        : [{ type: 'sommaire' }];
    } else {
      etat.file = construire({ sommaire: etat.sommaire });
    }
    etat.i = 0;
    cadre();
    peindre(0);
  }

  /* Le cadre ne bouge plus ensuite : barre, compteur, Retour. Seul
     `.ecran` est remplacé, et il glisse. */
  function cadre() {
    $('#stage-area').innerHTML = `<div class="setup">
      <div class="setupbar"><i></i></div>
      <button type="button" class="linkbtn backbtn" data-en="Back">${
        L('Retour', 'Back')}</button>
      <span class="setuptop" id="setuptop"></span>
      <div class="ecran" id="ecran"></div>
    </div>`;
    $('.backbtn').onclick = reculer;
  }

  function avancer() {
    if (etat.i >= etat.file.length - 1) return terminer();
    glisser(etat.i + 1);
  }

  function reculer() {
    if (etat.i > 0) return glisser(etat.i - 1, -1);
    sortir();
  }

  /* Quitter l'écran des clés. S'il y a déjà un transcript affiché, on y
     retourne ; sinon on rouvre l'écran de dépôt. Le même geste que le
     bouton Retour que la page injecte d'ordinaire. */
  function sortir() {
    if (typeof job !== 'undefined' && job && job.blocks && job.blocks.length) {
      if (typeof render === 'function') { render(); return; }
    }
    document.body.classList.add('back');
    setTimeout(() => {
      $('#stage-area').innerHTML = '';
      const dock = $('#dock');
      if (dock) dock.hidden = true;
      document.body.classList.remove('back');
    }, 1100);
  }

  function terminer() {
    /* Les clés nouvelles changent l'état de la page entière — modèles
       de relecture, bouton des réglages, bandeau de simulation — et le
       plus court était de tout recharger. Trop court : un rechargement
       ne s'interpole pas, donc l'écran de dépôt surgissait au lieu de
       paraître, et tout ce qui n'était qu'en mémoire disparaissait avec
       la page.

       La page expose maintenant `apresCles()`, qui vide les caches qui
       dépendent des clés sans rien détruire d'autre. Le repli de
       l'écran des clés est celui du bouton « Retour », déjà réglé : la
       classe `back` dévoile la capture pendant que l'écran s'efface,
       et le CSS fait le reste. Le rechargement reste en repli pour une
       page qui n'aurait pas la fonction. */
    if (typeof window.apresCles !== 'function') return location.reload();
    window.apresCles();
    const sa = document.getElementById('stage-area');
    if (!sa) return;
    document.body.classList.add('back');
    setTimeout(() => {
      sa.innerHTML = '';
      const d = document.getElementById('dock');
      if (d) d.hidden = true;
      document.body.classList.remove('back');
    }, 1100);
  }

  function glisser(vers, sens) {
    const e = document.getElementById('ecran');
    if (!e) { etat.i = vers; return peindre(sens || 1); }
    e.classList.add('part');
    if ((sens || 1) < 0) e.style.translate = '24px 0';
    setTimeout(() => { etat.i = vers; peindre(sens || 1); }, SORTIE);
  }

  function peindre(sens) {
    const e = document.getElementById('ecran');
    if (!e) return;
    const ecran = etat.file[etat.i];
    if (!ecran) return terminer();

    e.innerHTML = contenu(ecran);

    // Les pas numérotés portent le compteur ; les écrans de bascule
    // (intro, offre, sommaire) n'en font pas partie et le laissent vide
    // plutôt que d'annoncer « Étape 1 / 6 » devant une question.
    const pas = etat.file.filter(
      x => x.type === 'gestes' || x.type === 'cle');
    const rang = pas.indexOf(ecran) + 1;
    const top = document.getElementById('setuptop');
    if (top) {
      top.textContent = rang > 0
        ? `${L('Étape', 'Step')} ${rang} / ${pas.length}` : '';
    }
    // Au tout premier écran d'un premier démarrage, Retour ne mène
    // nulle part : on retombe sur l'écran de dépôt, où rien ne peut
    // encore se faire faute de clé. On le cache là, et seulement là.
    const retour = document.querySelector('.backbtn');
    if (retour) retour.hidden = etat.i === 0 && !etat.presentes.groq;

    const barre = document.querySelector('.setupbar');
    if (barre) {
      barre.style.setProperty(
        '--part', ((etat.i + 1) / Math.max(etat.file.length, 1)).toFixed(3));
    }

    brancher(ecran);

    // Entrée : on pose l'écran décalé sans transition, on force un
    // reflow, puis on le relâche. Sans le reflow le navigateur groupe
    // les deux écritures et l'écran apparaît d'un coup.
    e.classList.remove('part');
    e.style.translate = '';
    e.classList.add('vient');
    if ((sens || 1) < 0) e.style.translate = '-24px 0';
    void e.offsetWidth;
    e.style.transition = `opacity ${ENTREE}ms var(--vm-ease), `
      + `translate ${ENTREE}ms var(--vm-ease)`;
    e.classList.remove('vient');
    e.style.translate = '0 0';

    // Le focus arrive APRÈS la transition : posé avant, le navigateur
    // fait défiler la page vers le champ, et la page ne doit jamais
    // défiler. `preventScroll` en plus, par ceinture et bretelles.
    setTimeout(() => {
      const champ = document.getElementById('keyinput');
      if (champ) { try { champ.focus({ preventScroll: true }); } catch (x) { champ.focus(); } }
    }, ENTREE);
  }

  function bulle(titre, texte, haut) {
    if (!texte) return '';
    return `<span class="tipwrap${haut ? ' up' : ''}"><button class="info"
      type="button" aria-expanded="false" aria-label="${L('Plus d\'infos',
      'More info')}">i</button><span class="tipbody">${
      titre ? `<b>${esc(titre)}</b>` : ''}<span>${esc(texte)}</span></span></span>`;
  }

  function contenu(s) {
    if (s.type === 'intro') return vueIntro();
    if (s.type === 'gestes' || s.type === 'cle') return vuePas(s);
    if (s.type === 'offre') return vueOffre();
    if (s.type === 'fini') return vueFini();
    return vueSommaire();
  }

  // ------------------------------------------------------------ écrans

  function vueIntro() {
    const n = guide.notions || [];
    const pourquoi = n[0] || {};
    return `
      <span class="etiq">${L('Avant de commencer', 'Before we start')}</span>
      <h2>${L('Deux services', 'Two services')}</h2>
      <p class="geste">${L(
        'Deux services, deux clés. Groq assure la reconnaissance de la '
        + 'parole ; un modèle d\'IA, facultatif, rédige le compte rendu.',
        'Two services, two keys. Groq handles speech recognition; an AI '
        + 'model, optional, drafts the minutes.')} ${
      bulle(pourquoi.titre || '', pourquoi.texte || '')}</p>
      <button type="button" class="gros" data-x="suivant">${
      L('Commencer', 'Start')}</button>`;
  }

  function vuePas(s) {
    const c = s.c;
    const etiq = c.requis
      ? `<span class="etiq oblig">${L('Obligatoire', 'Required')}</span>`
      : `<span class="etiq">${c.recommande ? L('Recommandé', 'Recommended')
        : L('Facultatif', 'Optional')}</span>`;

    if (s.type === 'cle') {
      const dernier = c.etapes[c.etapes.length - 1];
      return `${etiq}
        <h2>${esc(c.nom)}</h2>
        <p class="geste">${esc(dernier.geste)} ${bulle(c.nom, dernier.detail)}</p>
        <div class="keyrow">
          <input type="password" id="keyinput" spellcheck="false"
                 autocomplete="off" placeholder="${esc(c.prefixes.join(' / '))}…"
                 aria-label="${L('Clé', 'Key')} ${esc(c.nom)}">
          <button id="keysave">${L('Enregistrer', 'Save')}</button>
        </div>
        <div class="keyerr" id="keyerr"></div>`;
    }

    // Les gestes qui se font dans l'autre onglet, d'un seul tenant.
    const gestes = c.etapes.slice(0, -1).map((e, n) => `
      <li><b>${esc(e.geste)}</b><span>${esc(e.detail)}</span></li>`).join('');

    return `${etiq}
      <h2>${esc(c.nom)}</h2>
      <p class="geste">${esc(c.role)}</p>
      <ol class="gestes">${gestes}</ol>
      <div class="actes">
        <button type="button" class="gros" data-x="ouvrirsite">${
      L('Ouvrir', 'Open')} ${esc(c.ou)}</button>
        <button type="button" class="discret" data-x="suivant">${
      L('Clé déjà créée', 'Key already created')}</button>
      </div>`;
  }

  function vueOffre() {
    const ia = guide.cles.find(c => c.recommande);
    if (!ia || etat.presentes[ia.id]) return vueFini();
    return `
      <span class="etiq">${L('Facultatif', 'Optional')}</span>
      <h2>${L('Le compte rendu', 'The minutes')}</h2>
      <p class="geste">${L(
        'Rédaction automatique du compte rendu à partir du transcript. '
        + 'Sans cette clé, la sortie est le transcript seul.',
        'Automatic drafting of minutes from the transcript. Without this '
        + 'key, the output is the transcript alone.')} ${
      bulle(ia.nom, ia.pour_quoi)}</p>
      <button type="button" class="gros" data-x="ajouter">${
      L('Ajouter', 'Add')} ${esc(ia.nom)}</button>
      <button type="button" class="discret" data-x="fini">${
      L('Plus tard', 'Later')}</button>`;
  }

  function vueFini() {
    return `
      <span class="etiq etat-oui">${L('Terminé', 'Done')}</span>
      <h2>${L('Configuré', 'Configured')}</h2>
      <p class="geste">${L(
        'Clés enregistrées dans le trousseau du système.',
        'Keys stored in the system keychain.')}</p>
      <button type="button" class="gros" data-x="fini">${
      L('Transcrire un enregistrement', 'Transcribe a recording')}</button>`;
  }

  function vueSommaire() {
    const lignes = guide.cles.map(c => {
      const oui = !!etat.presentes[c.id];
      return `<button type="button" class="pastille" data-service="${esc(c.id)}">
        <em>${c.requis ? L('Obligatoire', 'Required')
        : c.recommande ? L('Recommandé', 'Recommended')
          : L('Facultatif', 'Optional')}</em>
        <b>${esc(c.nom)}</b>
        <span class="${oui ? 'etat-oui' : ''}">${oui
        ? L('branché — changer la clé', 'connected — change the key')
        : esc(c.role)}</span></button>`;
    }).join('');
    return `
      <span class="etiq">${L('Services', 'Services')}</span>
      <h2>${L('Clés', 'Keys')}</h2>
      <div class="pastilles">${lignes}</div>`;
  }

  // ------------------------------------------------------- les actions

  function brancher(s) {
    const e = document.getElementById('ecran');
    if (!e) return;

    e.querySelectorAll('[data-x]').forEach(b => {
      const quoi = b.dataset.x;
      b.onclick = () => {
        if (quoi === 'suivant') return avancer();
        if (quoi === 'fini') return terminer();
        if (quoi === 'ouvrirsite') {
          /* Par le serveur, et non window.open : dans la fenêtre de
             l'application empaquetée, window.open n'ouvre rien, et le
             bouton ne faisait donc rien — au premier pas, celui qu'on
             ne peut pas contourner. Le navigateur reste le repli. */
          api('/api/ouvrir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: s.c.url }),
          }).catch(() => { window.open(s.c.url, '_blank', 'noopener'); });
          return avancer();
        }
        if (quoi === 'ajouter') {
          const ia = guide.cles.find(c => c.recommande);
          // Insérés ici même : la barre s'allonge au lieu de mentir.
          etat.file.splice(etat.i + 1, 0, ...pasDe(ia, true));
          etat.file.push({ type: 'fini' });
          return avancer();
        }
      };
    });

    e.querySelectorAll('[data-service]').forEach(b => {
      b.onclick = () => ouvrir({ service: b.dataset.service });
    });

    const save = document.getElementById('keysave');
    if (save) save.onclick = () => enregistrer(s.c, save);
    const champ = document.getElementById('keyinput');
    if (champ) champ.onkeydown = ev => { if (ev.key === 'Enter') save.click(); };
  }

  async function enregistrer(c, save) {
    const champ = document.getElementById('keyinput');
    const err = document.getElementById('keyerr');
    err.textContent = '';
    save.disabled = true;
    save.textContent = L('Vérification…', 'Checking…');
    try {
      /* La langue part avec la clé : c'est le serveur qui rédige le
         refus, et un refus en français devant quelqu'un qui a mis
         l'interface en anglais le laisse sur le seul écran qu'il ne
         peut pas franchir. */
      await api('/api/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: champ.value, fournisseur: c.id, langue: guide.langue,
        }),
      });
      etat.presentes[c.id] = true;
      if (c.id === 'groq') {
        ready = true;                       // liaison globale de la page
        const b = $('#changekey');
        if (b) b.hidden = false;
      }
      avancer();
    } catch (ex) {
      err.textContent = ex.message;
      save.disabled = false;
      save.textContent = L('Enregistrer', 'Save');
    }
  }

  // ------------------------------------------------------- le clavier

  document.addEventListener('keydown', ev => {
    if (!document.querySelector('.setup')) return;
    if (ev.key === 'Escape') { ev.preventDefault(); return reculer(); }
    if (ev.key !== 'Enter') return;
    // Entrée dans le champ : c'est « Enregistrer » qui répond.
    if (ev.target && ev.target.id === 'keyinput') return;
    const suite = document.querySelector('#ecran .gros');
    if (suite) { ev.preventDefault(); suite.click(); }
  });

  // --------------------------------------------------- les accroches

  window.askForKey = ouvrir;

  const bouton = document.getElementById('changekey');
  if (bouton) {
    bouton.onclick = () => ouvrir({ sommaire: true });
    bouton.textContent = 'Clés et services';
    bouton.setAttribute('data-en', 'Keys and services');
    bouton.removeAttribute('data-fr');
    api('/api/health').then(h => { if (h.has_key) bouton.hidden = false; })
      .catch(() => {});
  }

  /* Le bandeau de simulation.
     Démarré avec --simulation, le programme ne connaît aucune clé, pour
     montrer ce que voit quelqu'un qui vient d'installer. Sans le dire,
     l'écran est indiscernable d'une panne : les clés ont l'air d'avoir
     disparu, et on va les chercher dans le trousseau — où elles sont,
     intactes, ce qui achève de brouiller la piste. */
  function bandeau() {
    const dire = () => L(
      'Simulation de premier démarrage — aucune clé connue, le trousseau n\'est pas touché',
      'First-run simulation — no key known, the keychain is left alone');
    api('/api/health').then(h => {
      if (!h || !h.vierge || document.getElementById('tr-sim')) return;
      const el = document.createElement('div');
      el.id = 'tr-sim';
      el.setAttribute('role', 'status');
      el.setAttribute('data-no-i18n', '');
      // En bas et à droite, en pastille : en bandeau pleine largeur il
      // recouvrait le titre de la page et la bascule de langue, ce qui
      // est beaucoup de dégâts pour une mention de service.
      el.style.cssText = 'position:fixed;right:10px;bottom:10px;z-index:9999;'
        + 'max-width:min(22rem,70vw);padding:.35rem .6rem;'
        + 'background:var(--vm-accent,#ff3d12);'
        + 'color:var(--tr-on-accent,#fff);font:500 .64rem/1.25 '
        + 'var(--vm-font-mono,ui-monospace,monospace);letter-spacing:.05em;'
        + 'text-transform:uppercase;pointer-events:none';
      el.textContent = dire();
      document.body.appendChild(el);
      if (window.vm && vm.lang) vm.lang.onChange(() => { el.textContent = dire(); });
    }).catch(() => {});
  }
  bandeau();

  // Le guide est rendu par le serveur dans une seule langue : changer
  // de langue demande de le relire, sinon l'écran reste dans l'ancienne.
  if (window.vm && vm.lang) {
    vm.lang.onChange(() => {
      if (!document.querySelector('.setup')) return;
      guide = null;
      ouvrir({ sommaire: etat.sommaire });
    });
  }
})();
