/* Les séances passées, et les réglages de la dernière fois.
 *
 * Avant, fermer la fenêtre noire effaçait tout : il fallait avoir pensé
 * à enregistrer un .json, savoir où il était allé, et le rouvrir à la
 * main. Maintenant le serveur garde les séances ; ce fichier les montre
 * et permet d'y revenir.
 *
 * Deux choses, donc. Une liste sous la zone de dépôt, avec de quoi
 * rouvrir, jeter l'enregistrement en gardant le texte, ou tout
 * supprimer. Et le rétablissement des réglages — langue, modèle,
 * nombre de voix — parce que personne n'en change d'une réunion à
 * l'autre et que les reposer chaque fois est une corvée qu'on finit par
 * expédier.
 *
 * Comme branchement.js et apercu.js, ce fichier vit à part de
 * l'interface : une refonte du HTML ne peut pas l'effacer. Il emprunte
 * `job`, `jobId`, `names` (des `let` du premier niveau, lisibles et
 * assignables par leur nom nu, absents de window) et `render`, `api`,
 * `$` (des déclarations, donc sur window). verifier_memoire.py vérifie
 * que ces appuis existent encore.
 */
(() => {
  'use strict';

  const L = (fr, en) => (window.vm && vm.lang ? vm.lang.t(fr, en) : fr);
  const $$ = (s) => document.querySelector(s);

  const CSS = `
.tr-sc { margin: 1.2rem 0 0; }
.tr-sc[hidden] { display: none; }
.tr-sc > h3 { margin: 0 0 .5rem; font: 500 var(--vm-s, .75rem)/1.2
  var(--vm-font-mono, ui-monospace, monospace); letter-spacing: .08em;
  text-transform: uppercase; color: var(--vm-mute, #666); display: flex;
  gap: .6rem; align-items: baseline; }
.tr-sc > h3 em { font-style: normal; margin-left: auto; font-size: .92em; }
/* Les purges, au bout de la ligne de titre : discrètes au repos, elles
   ne doivent pas se cliquer en visant autre chose. */
.tr-sc .sc-purge { display: flex; gap: .4rem; align-items: center; }
.tr-sc .sc-purge button { font: inherit; letter-spacing: inherit;
  text-transform: inherit; background: none; border: 0; cursor: pointer;
  padding: .25em .5em; color: var(--vm-mute, #666); opacity: .7;
  white-space: nowrap; transition: opacity .3s, color .3s; }
.tr-sc .sc-purge button:hover { opacity: 1; color: var(--vm-ink, #111); }
.tr-sc .sc-purge button.danger:hover { color: var(--tr-warn, #b4341f); }
.tr-sc .sc-purge button[data-sur="1"] { opacity: 1;
  color: var(--tr-warn, #b4341f); }
.tr-sc ul { list-style: none; margin: 0; padding: 0;
  border-top: 1px solid color-mix(in oklab, var(--vm-ink, #000) 15%, transparent); }
.tr-sc li { display: flex; align-items: center; gap: .7rem; padding: .5rem 0;
  border-bottom: 1px solid color-mix(in oklab, var(--vm-ink, #000) 10%, transparent); }
.tr-sc .nom { font-weight: 600; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; min-width: 0; }
.tr-sc .meta { font: var(--vm-s, .75rem)/1.2 var(--vm-font-mono, ui-monospace, monospace);
  color: var(--vm-mute, #666); white-space: nowrap; }
.tr-sc .pousse { margin-left: auto; }
.tr-sc button { font: 500 var(--vm-s, .75rem)/1.2 var(--vm-font-mono, ui-monospace, monospace);
  letter-spacing: .04em; text-transform: uppercase; cursor: pointer;
  padding: .3rem .6rem; color: var(--vm-ink, #000); background: transparent;
  border: 1px solid color-mix(in oklab, var(--vm-ink, #000) 22%, transparent);
  transition: background var(--vm-d-shut, .3s) var(--vm-ease-out, ease); }
.tr-sc button:hover { background: color-mix(in oklab, var(--vm-ink, #000) 8%, transparent); }
.tr-sc button.danger:hover { background: var(--tr-warn, #c93a14); color: #fff;
  border-color: var(--tr-warn, #c93a14); }
.tr-sc .vide { color: var(--vm-mute, #666); font-size: .92em; padding: .4rem 0; }
.tr-maj { margin: .9rem 0 0; font: 500 var(--vm-s, .75rem)/1.4
  var(--vm-font-mono, ui-monospace, monospace); letter-spacing: .04em;
  text-transform: uppercase; color: var(--vm-mute, #666); }
.tr-maj a { color: var(--vm-accent, #ff3d12); }
`;

  function styler() {
    if (document.getElementById('tr-sc-css')) return;
    const s = document.createElement('style');
    s.id = 'tr-sc-css';
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ------------------------------------------------------ mise en forme

  function duree(secondes) {
    const s = Math.max(0, Math.round(secondes || 0));
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h ? `${h} h ${String(m).padStart(2, '0')}` : `${m} min`;
  }

  function poids(octets) {
    if (!octets) return '';
    const mo = octets / 1048576;
    return mo >= 1024 ? `${(mo / 1024).toFixed(1)} Go` : `${Math.round(mo)} Mo`;
  }

  function quand(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return '';
    const lg = (window.vm && vm.lang ? vm.lang.get() : 'fr') === 'en'
      ? 'en-CA' : 'fr-CA';
    return d.toLocaleDateString(lg, { day: 'numeric', month: 'short' })
      + ' ' + d.toLocaleTimeString(lg, { hour: '2-digit', minute: '2-digit' });
  }

  // ---------------------------------------------------------- la liste

  let hote = null;

  function placer() {
    if (hote) return hote;
    const ancre = $$('.pickrow') || $$('#dropzone');
    if (!ancre) return null;
    styler();
    hote = document.createElement('section');
    hote.className = 'tr-sc';
    hote.id = 'seances';
    hote.hidden = true;
    ancre.after(hote);
    return hote;
  }

  /* Pendant un traitement, la liste n'a plus lieu d'être : on ne peut
     ni rouvrir ni supprimer tant que ça tourne, et elle occupe la
     hauteur dont le pourcentage géant a besoin. Dans une fenêtre
     courte, c'est elle qui faisait déborder l'écran. */
  function enTraitement() {
    const s = document.getElementById('status');
    return !!(s && !s.hidden);
  }

  async function peindre() {
    if (!placer()) return;
    if (enTraitement()) { hote.hidden = true; return; }
    let d = null;
    try { d = await api('/api/seances'); } catch (e) { return; }
    const liste = (d && d.seances) || [];
    if (!liste.length) { hote.hidden = true; return; }
    hote.hidden = false;

    const total = d.place && d.place.octets ? poids(d.place.octets) : '';
    /* Deux purges, et l'ordre compte : jeter les sons récupère presque
       toute la place sans perdre une ligne de texte, et c'est donc ce
       qu'on propose en premier. Tout effacer vient après, et le dit. */
    const avecSon = liste.filter(s => s.audio_present).length;
    const octetsSon = liste.reduce((t, s) => t + (s.audio_present ? (s.octets || 0) : 0), 0);
    hote.innerHTML = `
      <h3><span>${L('Séances enregistrées', 'Saved sessions')}</span>
        ${total ? `<em title="${escapeHtml(d.place.dossier)}">${total}</em>` : ''}
        <span class="sc-purge">
          ${avecSon ? `<button data-act="tous-sons"
              title="${L('Garde tous les textes. L’aperçu et la séparation des voix ne seront plus possibles.',
                         'Keeps every transcript. Preview and voice separation will no longer be possible.')}"
            >${L('Jeter les sons', 'Drop all audio')} (${poids(octetsSon)})</button>` : ''}
          <button class="danger" data-act="tout"
            title="${L('Textes et enregistrements. Sans retour possible.',
                       'Transcripts and recordings. No way back.')}"
            >${L('Tout effacer', 'Delete everything')}</button>
        </span></h3>
      <ul>${liste.map(ligne).join('')}</ul>`;

    hote.querySelectorAll('.sc-purge button').forEach(b => {
      b.onclick = () => purger(b.dataset.act, b, liste.length, avecSon, octetsSon);
    });

    hote.querySelectorAll('button[data-id]').forEach(b => {
      b.onclick = () => agir(b.dataset.act, b.dataset.id, b);
    });
  }

  function ligne(s) {
    const bouts = [duree(s.duree)];
    if (s.voix > 1) bouts.push(L(`${s.voix} voix`, `${s.voix} voices`));
    if (s.relue) bouts.push(L('relue', 'proofread'));
    // Dire ce qui manque plutôt que de laisser découvrir à l'usage que
    // l'aperçu et la séparation des voix ne marchent plus.
    if (!s.audio_present) bouts.push(L('texte seul', 'text only'));
    else if (s.octets) bouts.push(poids(s.octets));
    return `<li>
      <span class="nom">${escapeHtml(s.fichier)}</span>
      <span class="meta">${quand(s.touche_le)} · ${bouts.join(' · ')}</span>
      <span class="pousse"></span>
      <button data-act="ouvrir" data-id="${s.id}">${L('Rouvrir', 'Reopen')}</button>
      ${s.audio_present ? `<button data-act="audio" data-id="${s.id}"
          title="${L('Libère de la place. Le texte reste ; l’aperçu et la séparation des voix ne seront plus possibles.',
                     'Frees space. The text stays; preview and voice separation will no longer be possible.')}"
        >${L('Jeter le son', 'Drop audio')}</button>` : ''}
      <button class="danger" data-act="effacer" data-id="${s.id}"
        >${L('Supprimer', 'Delete')}</button>
    </li>`;
  }

  async function agir(acte, id, bouton) {
    if (acte === 'ouvrir') return ouvrir(id);

    // Deux clics plutôt qu'une fenêtre de confirmation : la fenêtre
    // s'expédie sans lire, le bouton qui change de mot se remarque.
    if (bouton.dataset.sur !== '1') {
      const avant = bouton.textContent;
      bouton.dataset.sur = '1';
      bouton.textContent = L('Confirmer', 'Confirm');
      setTimeout(() => {
        if (bouton.dataset.sur === '1') {
          bouton.dataset.sur = '';
          bouton.textContent = avant;
        }
      }, 4000);
      return;
    }
    const url = acte === 'audio'
      ? `/api/seances/${id}/audio` : `/api/seances/${id}`;
    try { await api(url, { method: 'DELETE' }); } catch (e) { alert(e.message); }
    peindre();
  }


  /* Les deux purges. Même geste en deux temps que pour une séance : le
     premier clic change le mot du bouton, le second agit. Une fenêtre
     de confirmation s'expédie sans lire ; un bouton qui dit ce qu'il va
     emporter se remarque.
     Six secondes plutôt que quatre : ce qui part ici ne revient pas. */
  async function purger(acte, bouton, combien, avecSon, octetsSon) {
    const tout = acte === 'tout';
    if (bouton.dataset.sur !== '1') {
      const avant = bouton.innerHTML;
      bouton.dataset.sur = '1';
      bouton.textContent = tout
        ? L(`Effacer ${combien} séance${combien > 1 ? 's' : ''} — sans retour`,
            `Delete ${combien} session${combien > 1 ? 's' : ''} — no way back`)
        : L(`Jeter ${avecSon} enregistrement${avecSon > 1 ? 's' : ''} (${poids(octetsSon)})`,
            `Drop ${avecSon} recording${avecSon > 1 ? 's' : ''} (${poids(octetsSon)})`);
      setTimeout(() => {
        if (bouton.dataset.sur === '1') { bouton.dataset.sur = ''; bouton.innerHTML = avant; }
      }, 6000);
      return;
    }
    try {
      await api(`/api/seances${tout ? '' : '?audio_seulement=1'}`, { method: 'DELETE' });
    } catch (e) { alert(e.message); }
    peindre();
  }

  async function ouvrir(id) {
    try {
      const rouverte = await api(`/api/seances/${id}`, { method: 'POST' });
      // Les mêmes affectations que la réouverture d'un .json. `job`,
      // `jobId` et `names` sont des `let` du premier niveau : le nom nu
      // atteint la liaison globale, `window.job` ne l'atteindrait pas.
      job = rouverte;
      jobId = rouverte.id;
      names = rouverte.names || {};
      render();
    } catch (e) {
      alert(e.message);
    }
  }

  // ------------------------------------------------------- les réglages

  /* Poser une valeur sur une liste que le programme remplit lui-même.
     #emb et #clean sont vides au chargement : leur contenu arrive d'un
     appel au serveur. Y écrire trop tôt ne lève rien et ne fait rien —
     le choix retombe sur le premier élément venu dès que la liste se
     remplit. On attend donc que l'option existe. */
  function poserListe(sel, valeur, essais = 25, stable = 0) {
    if (valeur === '' || valeur == null) return;
    const el = $$(sel);
    if (!el) return;

    if ([...el.options].some(o => o.value === valeur)) {
      if (el.value === valeur) {
        stable += 1;
      } else {
        el.value = valeur;
        stable = 0;
        // Les listes de la maison se redessinent sur « change » : les
        // régler en silence laisserait le bouton afficher l'ancien
        // choix pendant que le formulaire porte le nouveau.
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }
    }
    // On réaffirme le choix un moment, au lieu de le poser une fois.
    // La liste des modèles est reconstruite quand la langue change — y
    // compris par le rétablissement de la langue, trois lignes plus
    // haut — et cette reconstruction écrasait la valeur qu'on venait
    // d'écrire, sans rien signaler : l'écran affichait « auto » et le
    // modèle choisi la veille était perdu. Trois lectures d'affilée
    // sans dérive valent reconstruction terminée.
    if (essais > 0 && stable < 3) {
      setTimeout(() => poserListe(sel, valeur, essais - 1, stable), 120);
    }
  }

  /* Le nombre de voix tient dans un seul endroit : le <select> caché
     #count, où 'none' veut dire « ne pas séparer », 'auto' « chercher
     combien », et un chiffre le nombre annoncé. L'interrupteur et les
     pastilles n'en sont que deux commandes. Les régler sans régler
     #count laisse l'écran dire une chose et le formulaire en envoyer
     une autre — et c'est le formulaire qui gagne, en silence. */
  function poserNombre(r) {
    const choix = String(r.count || 'none');
    const count = $$('#count');
    if (!count) return;
    count.value = choix;
    count.dispatchEvent(new Event('change', { bubbles: true }));

    const separe = choix !== 'none';
    const inter = $$('#sep');
    if (inter) {
      inter.classList.toggle('on', separe);
      inter.setAttribute('aria-checked', String(separe));
    }
    // `lastN` est le nombre vers lequel l'interrupteur revient quand on
    // le rallume. Sans lui, rallumer après coup retomberait sur « auto »
    // alors que les pastilles afficheraient encore le bon chiffre.
    if (separe && typeof lastN !== 'undefined') lastN = choix;
    document.querySelectorAll('#numchips button').forEach(
      b => b.classList.toggle('on', separe && b.dataset.v === choix));
  }

  async function retablir() {
    let r = null;
    try { r = await api('/api/reglages'); } catch (e) { return; }
    if (!r) return;
    const langue = $$('#lang');
    if (langue && r.language !== '' && r.language != null) {
      langue.value = r.language;
      langue.dispatchEvent(new Event('change', { bubbles: true }));
    }
    poserNombre(r);
    poserListe('#emb', r.embedding);
    poserListe('#clean', r.denoise);
  }

  // ---------------------------------------------------------- démarrage

  /* Retenir ce qui vient d'être lancé.
     En phase de capture, donc avant le gestionnaire de la page : celui-
     ci désactive le bouton et vide des champs en chemin, et lire après
     lui rendrait l'état d'après plutôt que le choix fait. */
  function retenirLancement() {
    const go = $$('#go');
    if (!go) return;
    go.addEventListener('click', () => {
      const v = (sel) => { const el = $$(sel); return el ? el.value : ''; };
      api('/api/reglages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          language: v('#lang'), count: v('#count') || 'none',
          embedding: v('#emb'), denoise: v('#clean'),
        }),
      }).catch(() => {});
    }, true);
  }

  /* Une version plus récente existe-t-elle ? Relevé une fois par
     lancement. Sans cela, personne n'apprend jamais qu'une correction
     est sortie : il n'y a pas de mise à jour automatique, et rien dans
     l'application ne le dit. En cas d'échec on se tait — une panne de
     réseau n'est pas une nouvelle à annoncer. */
  async function majDisponible() {
    let v = null;
    try { v = await api('/api/version'); } catch (e) { return; }
    if (!v || !v.retard || document.getElementById('tr-maj')) return;
    const ancre = $$('.pickrow') || $$('#dropzone');
    if (!ancre) return;
    styler();
    const el = document.createElement('p');
    el.id = 'tr-maj';
    el.className = 'tr-maj';
    el.setAttribute('data-no-i18n', '');
    el.innerHTML = L(
      `Version ${v.publiee} disponible — installée : ${v.installee}.`,
      `Version ${v.publiee} available — installed: ${v.installee}.`)
      + ` <a href="${v.url}" target="_blank" rel="noopener">`
      + L('Télécharger', 'Download') + '</a>';
    ancre.after(el);
  }

  /* Exposée pour l'import de la bibliothèque : après un dépôt, la liste
     doit se remettre à jour sans recharger la page. `peindre` est une
     fonction du module, invisible de l'extérieur sans cela. */
  window.repeindreSeances = peindre;

  function demarrer() {
    retablir();
    majDisponible();
    peindre();
    retenirLancement();

    // Une séance qui vient d'aboutir doit apparaître dans la liste sans
    // qu'on recharge la page. On se greffe sur le retour à l'accueil et
    // sur la fin d'un traitement plutôt que de sonder le serveur.
    const vraiRender = window.render;
    if (typeof vraiRender === 'function') {
      window.render = function () {
        const r = vraiRender.apply(this, arguments);
        clearTimeout(demarrer._t);
        demarrer._t = setTimeout(peindre, 400);
        return r;
      };
    }
    if (window.vm && vm.lang && vm.lang.onChange) vm.lang.onChange(peindre);

    // Le passage en traitement et le retour se voient sur #status :
    // on s'y accroche plutôt que de sonder l'état en boucle.
    const statut = document.getElementById('status');
    if (statut) {
      new MutationObserver(() => {
        clearTimeout(demarrer._s);
        demarrer._s = setTimeout(peindre, 250);
      }).observe(statut, { attributes: true, attributeFilter: ['hidden'] });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
