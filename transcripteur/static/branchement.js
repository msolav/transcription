/* ============================================================
   Brancher les services : la marche à suivre pour les clés.

   Pourquoi ce travail vit dans un fichier à part plutôt que dans
   index.html. L'interface est en cours de refonte par ailleurs, et une
   première version de cet écran, écrite dedans, a été effacée par une
   réécriture du fichier quelques minutes plus tard. Ici, la surface de
   collision est nulle : le serveur ajoute lui-même la balise qui charge
   ce fichier, donc même une réécriture complète de la page ne fait rien
   perdre.

   Ce fichier est un script classique, chargé après celui de la page. Il
   voit donc ses déclarations de premier niveau — `$`, `api`,
   `escapeHtml`, `ready`, `vm` — et peut remplacer `askForKey`, qui est
   une fonction globale. Rien n'est importé, rien n'est exporté.

   Ce qu'il remplace, et pourquoi. L'écran d'origine ne demandait que la
   clé Groq, celle qui transcrit. La seconde clé, celle de l'IA qui
   rédige le compte rendu, n'était accessible que par un lien dans une
   note du panneau de relecture : l'outil demandait donc à chacun de
   deviner tout seul qu'il lui fallait un second service, lequel, et
   comment l'obtenir. C'était le trou le plus sérieux pour quelqu'un à
   qui on remet l'outil sans pouvoir s'asseoir à côté de lui.

   Le texte des consignes vient du serveur (/api/guide) et non d'ici. Il
   doit paraître à trois endroits — cet écran, la page autonome /aide
   qu'on envoie par courriel à quelqu'un qui n'a encore rien installé,
   et le README — et trois copies divergent en une semaine. Le serveur
   le rend déjà dans la langue demandée, ce qui nous dispense en plus de
   faire passer une vingtaine de phrases par le dictionnaire de vm.lang.
   ============================================================ */

(function () {
  'use strict';

  const L = (fr, en) => (window.vm && vm.lang ? vm.lang.t(fr, en) : fr);
  const esc = s => (typeof escapeHtml === 'function' ? escapeHtml(s)
    : String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;',
      '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]));

  /* La feuille de style voyage avec l'écran, pour la même raison que le
     reste : ne pas disputer le même <style> à deux mains. Elle n'invente
     pas de couleurs, elle emprunte les variables de la page. */
  const CSS = `
.setup h2 { margin: 0 0 6px; font: 800 clamp(1.5rem,2.6vw,2.1rem)/1.1 var(--vm-font-display, inherit); letter-spacing: -.03em; }
.setup .role { font-size: 1.0625rem; color: var(--vm-mute, #6b7280); margin: 0 0 20px; }
.setup .etiq { display: inline-block; font: 700 .6875rem/1 var(--vm-font-mono, ui-monospace, Menlo, monospace); letter-spacing: .1em; text-transform: uppercase; padding: .5em .6em .45em; border: 1px solid var(--vm-ink, currentColor); margin: 0 0 16px; }
.setup .etiq.oblig { background: var(--vm-ink, currentColor); color: var(--vm-paper, #fff); }
.setup .etiq.libre { border-color: var(--vm-accent, #2563eb); color: var(--vm-accent, #2563eb); }
.setup ol.pas { margin: 18px 0 10px; }
.setup ol.pas li { margin-bottom: 6px; }
.setupnav { display: flex; align-items: center; gap: 12px; font: 700 .75rem/1 var(--vm-font-mono, ui-monospace, Menlo, monospace); letter-spacing: .12em; text-transform: uppercase; color: var(--vm-mute, #6b7280); margin: 0 0 26px; }
.setupnav i { display: block; width: 26px; height: 3px; background: currentColor; opacity: .22; transition: opacity .5s var(--vm-ease, ease); }
.setupnav i.on { opacity: 1; color: var(--vm-accent, #2563eb); }
.setupaside { display: flex; gap: 20px; flex-wrap: wrap; align-items: center; margin-top: 24px; font-size: .9375rem; }
.setupaside button { background: none; border: 0; padding: 0; font: inherit; font-weight: 600; color: var(--vm-mute, #6b7280); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; transition: color .35s var(--vm-ease, ease); }
.setupaside button:hover { color: var(--vm-accent, #2563eb); }
.setupmenu { list-style: none; padding: 0; margin: 14px 0 0; border-top: 1px solid var(--vm-ink, currentColor); }
.setupmenu li { border-bottom: 1px solid var(--vm-mute, #6b7280); }
.setupmenu button { display: flex; width: 100%; gap: 16px; align-items: baseline; flex-wrap: wrap; text-align: left; background: none; border: 0; padding: 20px 2px; color: inherit; cursor: pointer; font: inherit; transition: padding-left .4s var(--vm-ease, ease), color .4s var(--vm-ease, ease); }
.setupmenu button:hover { padding-left: 10px; color: var(--vm-accent, #2563eb); }
.setupmenu .nom { font: 800 1.125rem var(--vm-font-display, inherit); letter-spacing: -.02em; }
.setupmenu .quoi { flex: 1; min-width: 12ch; color: var(--vm-mute, #6b7280); }
.setupmenu .etat { font: 700 .75rem/1 var(--vm-font-mono, ui-monospace, Menlo, monospace); letter-spacing: .1em; text-transform: uppercase; color: var(--vm-mute, #6b7280); white-space: nowrap; }
.setupmenu .etat.oui { color: var(--vm-accent, #2563eb); }
`;
  function styler() {
    if (document.getElementById('branchementcss')) return;
    const s = document.createElement('style');
    s.id = 'branchementcss';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  let guide = null, guideLangue = null;

  async function charger() {
    const lg = (window.vm && vm.lang ? vm.lang.get() : 'fr');
    if (guide && guideLangue === lg) return guide;
    const d = await api('/api/guide?langue=' + lg);
    guideLangue = lg;
    guide = d;
    return d;
  }

  /* `assistant` vrai au premier lancement : les clés se suivent, et la
     dernière recharge la page. Faux quand on revient par le socle : on
     montre le sommaire, et on y retourne après chaque enregistrement. */
  const etat = { assistant: true, pas: 0, presentes: {} };

  async function ouvrir(options) {
    styler();
    const dock = $('#dock');
    if (dock) dock.hidden = false;
    let d = null;
    try { d = await charger(); } catch (e) { d = null; }
    if (!d) {
      $('#stage-area').innerHTML = `<div class="setup"><h1>${L(
        'Serveur injoignable', 'Server unreachable')}</h1><p>${L(
        "La page n'a pas pu lire la marche à suivre. Vérifie que la fenêtre "
        + 'noire du programme est toujours ouverte, puis recharge cette page.',
        'The page could not load the setup instructions. Check that the '
        + "program's black window is still open, then reload this page.")
      }</p></div>`;
      return;
    }
    let h = null;
    try { h = await api('/api/health'); } catch (e) { h = null; }
    const o = options || {};
    etat.presentes = (h && h.cles) || {};
    /* Trois façons d'arriver ici. `sommaire` depuis le socle, pour
       changer une clé. `assistant` pour redérouler les étapes dans
       l'ordre même quand les clés sont déjà là — c'est ce qui permet de
       refaire la marche à suivre avec quelqu'un au téléphone, et de la
       vérifier sans vider son trousseau. Sinon, l'état décide : pas de
       clé Groq, donc premier lancement. */
    etat.assistant = o.assistant === true
      || (!o.sommaire && !etat.presentes.groq);
    etat.pas = 0;
    peindre();
  }

  function peindre() {
    if (!guide) return;
    if (!etat.assistant) return sommaire();
    /* L'assistant ne propose que les deux clés gratuites. Claude demande
       une carte bancaire : le mettre sur le chemin du premier lancement
       laisserait croire qu'il faut payer pour commencer, ce qui est faux
       et suffirait à faire reposer l'outil. */
    const suite = guide.cles.filter(c => c.requis || c.recommande);
    const c = suite[etat.pas];
    if (!c) { location.reload(); return; }
    ecran(c, {
      rang: etat.pas + 1,
      total: suite.length,
      apres: () => {
        etat.pas += 1;
        if (etat.pas >= suite.length) location.reload();
        else peindre();
      },
    });
  }

  /* Le sommaire : ce qui est branché, ce qui ne l'est pas, et de quoi
     changer n'importe laquelle sans traverser les autres. */
  function sommaire() {
    const lignes = guide.cles.map(c => {
      const oui = !!etat.presentes[c.id];
      const etiquette = oui ? L('branché', 'connected')
        : c.requis ? L('manquante', 'missing')
          : L('non branché', 'not connected');
      return `<li><button type="button" data-cle="${esc(c.id)}">
        <span class="nom">${esc(c.nom)}</span>
        <span class="quoi">${esc(c.role)}</span>
        <span class="etat${oui ? ' oui' : ''}">${etiquette}</span>
      </button></li>`;
    }).join('');
    $('#stage-area').innerHTML = `<div class="setup">
      <h1>${L('Clés et <em>services.</em>', 'Keys and <em>services.</em>')}</h1>
      <p>${L("L'outil écoute avec un service et rédige avec un autre. "
        + 'Choisis celui que tu veux brancher ou remplacer.',
        'The tool listens with one service and writes with another. '
        + 'Pick the one you want to connect or replace.')}</p>
      <ul class="setupmenu">${lignes}</ul>
      <div class="setupaside">
        <button type="button" id="setupback">${L('Retour', 'Back')}</button>
        <a href="/aide?langue=${guide.langue}" target="_blank" rel="noopener">${
          L('Tout lire, en une page', 'Read it all, on one page')}</a>
      </div>
    </div>`;
    $('#stage-area').querySelectorAll('[data-cle]').forEach(b => {
      b.onclick = () => ecran(
        guide.cles.find(x => x.id === b.dataset.cle),
        { apres: () => ouvrir({ sommaire: true }) });
    });
    $('#setupback').onclick = () => location.reload();
  }

  /* L'écran d'une clé : à quoi elle sert, ce qu'elle coûte, les pas à
     suivre, puis le champ. Dans cet ordre — on ne colle pas un secret
     dans un champ avant d'avoir compris ce qu'il paie. */
  function ecran(c, o) {
    if (!c) return;
    const etiq = c.requis
      ? `<span class="etiq oblig">${L('Obligatoire', 'Required')}</span>`
      : `<span class="etiq libre">${c.recommande
        ? L('Recommandé', 'Recommended') : L('Facultatif', 'Optional')}</span>`;
    const compteur = o.total > 1
      ? `<div class="setupnav">${
        Array.from({ length: o.total }, (_, i) =>
          `<i class="${o.rang >= i + 1 ? 'on' : ''}"></i>`).join('')
      }<span>${L('Étape', 'Step')} ${o.rang} / ${o.total}</span></div>`
      : '';
    /* Le premier pas porte l'adresse du fournisseur. La rendre cliquable
       évite de la recopier à la main, et c'est précisément là que les
       gens se perdent. */
    const pas = c.etapes.map((e, i) => {
      let t = esc(e);
      if (i === 0 && c.ou) {
        t = t.replace(esc(c.ou), `<a href="${esc(c.url)}" target="_blank"`
          + ` rel="noopener">${esc(c.ou)}</a>`);
      }
      return `<li>${t}</li>`;
    }).join('');

    $('#stage-area').innerHTML = `<div class="setup">
      ${compteur}
      ${etiq}
      <h2>${esc(c.nom)}</h2>
      <p class="role">${esc(c.role)}</p>
      <p>${esc(c.pour_quoi)}</p>
      <p><b>${esc(c.prix)}</b></p>
      <ol class="pas">${pas}</ol>
      <div class="keyrow">
        <input type="password" id="keyinput" spellcheck="false" autocomplete="off"
               placeholder="${esc(c.prefixes.join(' / '))}…"
               aria-label="${L('Clé', 'Key')} ${esc(c.nom)}">
        <button id="keysave">${L('Enregistrer', 'Save')}</button>
      </div>
      <div class="keyerr" id="keyerr"></div>
      <p class="keynote">${esc(c.limites)}</p>
      <div class="setupaside">
        ${c.requis ? '' : `<button type="button" id="setupskip">${L(
          'Plus tard — je rédige moi-même',
          "Later — I'll write the minutes myself")}</button>`}
        <a href="/aide?langue=${guide.langue}" target="_blank" rel="noopener">${
          L('La marche à suivre en détail', 'The setup guide in full')}</a>
      </div>
    </div>`;

    const input = $('#keyinput'), save = $('#keysave');
    input.focus();
    input.onkeydown = e => { if (e.key === 'Enter') save.click(); };
    const sauter = $('#setupskip');
    if (sauter) sauter.onclick = () => location.reload();
    save.onclick = async () => {
      $('#keyerr').textContent = '';
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
            key: input.value, fournisseur: c.id, langue: guide.langue,
          }),
        });
        etat.presentes[c.id] = true;
        if (c.id === 'groq') {
          ready = true;                      // liaison globale de la page
          const b = $('#changekey');
          if (b) b.hidden = false;
        }
        o.apres();
      } catch (err) {
        $('#keyerr').textContent = err.message;
        save.disabled = false;
        save.textContent = L('Enregistrer', 'Save');
      }
    };
  }

  // Remplace l'écran d'origine. `askForKey` est une fonction globale de
  // la page : la réaffecter suffit, les appels se résolvent à l'appel.
  window.askForKey = ouvrir;

  /* Le bouton du socle ouvrait l'écran de la clé Groq. Il ouvre
     maintenant le sommaire des trois services — c'est le seul endroit
     depuis lequel on peut brancher l'IA après coup. Le gestionnaire
     d'origine a capturé l'ancienne fonction au chargement, d'où la
     reliaison explicite. */
  const bouton = document.getElementById('changekey');
  if (bouton) {
    bouton.onclick = () => ouvrir({ sommaire: true });
    bouton.textContent = 'Clés et services';
    bouton.setAttribute('data-en', 'Keys and services');
    bouton.removeAttribute('data-fr');     // laisse vm.lang relire le français
    /* Il s'affiche même quand la clé Groq vient de l'environnement :
       celui qui rédige ses comptes rendus a encore une clé d'IA à
       brancher, et c'est par là qu'il la branche. */
    api('/api/health').then(h => { if (h.has_key) bouton.hidden = false; })
      .catch(() => {});
  }

  /* Le bandeau de simulation.
     Le programme démarré avec --simulation ne connaît aucune clé, pour
     montrer ce que voit quelqu'un qui vient de l'installer. Sans le
     dire, l'écran est indiscernable d'une panne : les clés ont l'air
     d'avoir disparu, et on va les chercher dans le trousseau — où elles
     sont, intactes, ce qui achève de brouiller la piste. */
  function bandeau() {
    api('/api/health').then(h => {
      if (!h || !h.vierge || document.getElementById('tr-sim')) return;
      const el = document.createElement('div');
      el.id = 'tr-sim';
      el.setAttribute('role', 'status');
      el.style.cssText = 'position:fixed;inset:0 0 auto 0;z-index:9999;'
        + 'padding:.3rem .7rem;text-align:center;background:var(--vm-accent,#ff3d12);'
        + 'color:var(--tr-on-accent,#fff);font:500 .72rem/1.3 '
        + 'var(--vm-font-mono,ui-monospace,monospace);letter-spacing:.06em;'
        + 'text-transform:uppercase;pointer-events:none';
      el.textContent = L(
        'Simulation de premier démarrage — aucune clé connue, le trousseau n\'est pas touché',
        'First-run simulation — no key known, the keychain is left alone');
      el.setAttribute('data-no-i18n', '');
      document.body.appendChild(el);
      if (window.vm && vm.lang) {
        vm.lang.onChange(() => {
          el.textContent = L(
            'Simulation de premier démarrage — aucune clé connue, le trousseau n\'est pas touché',
            'First-run simulation — no key known, the keychain is left alone');
        });
      }
    }).catch(() => {});
  }
  bandeau();

  // Le guide est rendu par le serveur dans une seule langue : changer de
  // langue demande de le relire, sinon l'écran reste dans l'ancienne.
  if (window.vm && vm.lang) {
    vm.lang.onChange(() => {
      if (!document.querySelector('.setup')) return;
      guide = null;
      ouvrir({ sommaire: !etat.assistant });
    });
  }
})();
