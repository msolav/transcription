import os
HERE = os.path.dirname(os.path.abspath(__file__))
import os, re
KIT = os.path.expanduser('~/.claude/skills/vm-ui/assets/')
OUT = '/Users/solav/Documents/Scripts/voice_trascription/Transcripteur/transcripteur/static/index-vm.html'
orig = open(os.path.join(HERE, 'orig_index.html'), encoding='utf-8').read()
js = re.search(r'<script>(.*)</script>', orig, re.S).group(1)

def rep(old, new, count=1):
    global js
    assert old in js, 'MISSING: ' + old[:70]
    js = js.replace(old, new, count)

# ---- loader instead of the 2px bar ----
rep("let names = {};", "let names = {};\nconst busy = vm.busy($('#busyHost'));\nfunction enh(root) { root.querySelectorAll('select').forEach(s => vm.select(s)); }")
rep("$('#fill').style.width = (ratio * 100) + '%';", "busy.set(ratio);")
rep("$('#status').hidden = false;", "$('#status').hidden = false; busy.start(); busy.set(0.01); { const wk = $('#working'); if (wk) wk.hidden = false; }")
rep("function idle(label) {\n  clearInterval(poll);", "function idle(label) {\n  clearInterval(poll);\n  busy.stop();\n  { const wk = $('#working'); if (wk) wk.hidden = true; }")
rep("idle('Terminé');", "idle('Transcrire à nouveau');")
rep("  $('#go').disabled = false;\n}\n\n/* ---------- lancement", "  $('#go').disabled = false;\n  const gh = $('#gohint'); if (gh) gh.hidden = true;\n}\n\n/* ---------- lancement")
# ---- dropdowns created inside panels ----
rep("  const majCout = async () => {", "  enh(p);\n  const majCout = async () => {")
rep("  $('#sctx').value = contexteMemo;", "  enh(p);\n  $('#sctx').value = contexteMemo;")
# ---- no arrows; no inline styles from the old design ----
rep("<b>${escapeHtml(c.avant)}</b> → <b class=\"ap\">${escapeHtml(c.apres)}</b>", "<b>${escapeHtml(c.avant)}</b> devient <b class=\"ap\">${escapeHtml(c.apres)}</b>")
js = re.sub(r'<button id="expand" style="[^"]*">', '<button id="expand">', js)
# ---- user content is never translated or altered ----
rep('<div class="doc" id="doc"></div>', '<div class="doc" id="doc" data-no-i18n></div>')
rep("<p>${peindre(d, '-')}</p>", "<p data-no-i18n>${peindre(d, '-')}</p>")
rep("<p>${peindre(d, '+')}</p>", "<p data-no-i18n>${peindre(d, '+')}</p>")
rep('<p class="extrait">', '<p class="extrait" data-no-i18n>')
rep('<pre id="stexte">', '<pre id="stexte" data-no-i18n>')
rep("`<pre>${escapeHtml(t)}</pre>`", "`<pre data-no-i18n>${escapeHtml(t)}</pre>`")
# Le journal de relecture porte maintenant data-no-i18n à la source :
# il a un id, un bouton d'arrêt à côté, et n'est plus réécrit à chaque
# sondage. Le marquer ici obligerait à recopier tout le gabarit.
assert 'id="relnotes" data-no-i18n' in js, \
    "le journal de relecture doit rester hors traduction"
# ---- default voice labels follow the language (also in exports) ----
rep("return `Voix ${s ? s.index + 1 : '?'}`;", "return `${vm.lang.t('Voix', 'Voice')} ${s ? s.index + 1 : '?'}`;")
rep('<div class="tag">Voix ${s.index + 1}</div>', '<div class="tag">${vm.lang.t(\'Voix\', \'Voice\')} ${s.index + 1}</div>')


def cut(start, end, new):
    global js
    a = js.index(start); b = js.index(end, a)
    js = js[:a] + new + js[b:]

# ---- progress drives the giant number's weight ----
rep("$('#pct').textContent = Math.round(ratio * 100) + ' %';", "$('#pct').textContent = Math.round(ratio * 100) + ' %'; document.documentElement.style.setProperty('--prog', ratio);")

# ---- accept(): fill the hero instead of replacing the drop zone ----
cut("  zone.outerHTML = `<div class=\"filetag\"", "  $('#go').disabled = false;", r"""  { const dot = file.name.lastIndexOf('.'), base = dot > 0 ? file.name.slice(0, dot) : file.name, ext = dot > 0 ? file.name.slice(dot) : '';
    $('#fname').textContent = base; $('#fmeta').textContent = (ext ? ext + '  ·  ' : '') + mb + ' ' + vm.lang.t('Mo', 'MB');
    /* La taille du titre suit la longueur du nom. Une quinzaine de
       caractères tiennent en pleine taille ; au-delà, on divise. Deux
       lignes au plus, le reste en points de suspension — un nom de
       fichier n'a pas à occuper l'écran entier. */
    $('#fname').style.setProperty('--n', Math.max(1, base.length / 15).toFixed(2)); }
  zone.classList.add('filled');
  if (window.dureeDuFichier) dureeDuFichier(file).then(s => poserDuree(s));
  /* Retirer le fichier remettait l'écran à zéro en rechargeant la page.
     Un rechargement ne s'interpole pas : le titre repassait de « nom du
     fichier » à « Déposer un fichier » d'un seul coup, ce qui se lisait
     comme un saut. Les mêmes gestes que `render()` fait déjà, sans
     détruire la page : le CSS repasse alors d'un titre à l'autre en
     fondu, comme à l'arrivée du fichier. */
  $('#clear').onclick = () => {
    picked = null;
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    $('#player').removeAttribute('src');
    zone.classList.remove('filled');
    $('#file').value = '';           // sans quoi le même fichier ne se redépose pas
    $('#go').disabled = true;
    if (window.poserDuree) poserDuree(0);
    $('#alerts').innerHTML = '';
  };
""")

# ---- voices: proportional columns ----
cut("  const strips = (expanded ? ranked", "  $('#dock').hidden = false;", r"""  const strips = (expanded ? ranked : ranked.slice(0, CARD_LIMIT)).map(s => `
    <div class="strip" style="--c:${s.color};--sh:${Math.max(s.share, .08).toFixed(3)}">
      <div class="top">
        <button class="play" data-i="${s.index}" ${s.has_sample ? '' : 'disabled'}
                aria-label="${vm.lang.t('Écouter la voix', 'Listen to voice')} ${s.index + 1}">${PLAY_ICON}</button>
        <div class="who">
          <div class="tag">${vm.lang.t('Voix', 'Voice')} ${s.index + 1}</div>
          <input type="text" data-id="${s.id}" value="${escapeHtml(names[s.id] || '')}"
                 placeholder="${vm.lang.t('Nommer', 'Name')}" maxlength="60" spellcheck="false">
        </div>
      </div>
      <div class="stat"><span>${clock(s.speaking_seconds)}</span><span>${Math.round(s.share * 100)} %</span></div>
    </div>`).join('');

""")

# ---- notes sheet ----
cut("  $('#stage-area').innerHTML = `\n    ${multi ?", "  document.querySelectorAll('.strip input')", r"""  const fn = job.filename || '', dt = fn.lastIndexOf('.');
  const title = `${escapeHtml(dt > 0 ? fn.slice(0, dt) : fn)}${dt > 0 ? `<i>${escapeHtml(fn.slice(dt))}</i>` : ''}`;
  $('#stage-area').innerHTML = `<div class="sheet">
    <h1 class="title" data-no-i18n>${title}</h1>
    <p class="metaline"><span data-no-i18n>${clock(job.duration || 0)}</span>${multi ? `<span>${job.speakers.length} ${vm.lang.t(job.speakers.length > 1 ? 'voix' : 'voix', job.speakers.length > 1 ? 'voices' : 'voice')}</span>` : ''}</p>
    ${multi ? `<section class="channels">
      <header>
        <h2><span data-en="Name the voices">Nommer les voix</span>
          <span class="tipwrap"><button class="info" type="button" aria-expanded="false" aria-label="${vm.lang.t("Plus d'infos", 'More info')}">i</button><span class="tipbody"><span id="mergenote"></span></span></span></h2>
        ${ranked.length > CARD_LIMIT ? `<button id="expand">${expanded
            ? 'Ne montrer que les ' + CARD_LIMIT + ' principales'
            : 'Afficher les ' + ranked.length + ' voix'}</button>` : ''}
      </header>
      <div class="strips">${strips}</div>
    </section>` : ''}
    <div class="doc" id="doc"></div>
  </div>
  <div class="spine" id="spine" aria-hidden="true"></div>`;

""")

# ---- turns: timecode / speaker / text ----
cut("    return `<div class=\"turn ${same", "  }).join('');", r"""    const parts = []; { const sn = b.text.match(/[^.!?…]+[.!?…]*\s*/g) || [b.text]; let cur = ''; for (const x of sn) { if (cur && (cur + x).length > 420) { parts.push(cur); cur = ''; } cur += x; } if (cur) parts.push(cur); }
    let acc = 0; const tot = b.text.length || 1;
    return parts.map((tx, k) => { const ts = b.start + (b.end - b.start) * acc / tot; acc += tx.length;
      return `<div class="turn ${same || k ? 'same' : ''}" ${k ? `data-c="${i}"` : `data-i="${i}"`} data-ts="${ts}" style="--c:${colorOf(b.speaker)}">
        <button class="tc" data-t="${ts}">${clock(ts)}</button>
        <div class="who">${escapeHtml(labelOf(b.speaker))}</div>
        <p>${escapeHtml(tx.trim())}</p>
      </div>`; }).join('');
""")
rep("  paintLive();\n}\n\n/* ---------- lecteur", "  paintSpine();\n  paintLive();\n}\n\n/* ---------- lecteur")
rep("$('#clock').textContent = `${clock(now)} / ${clock(span)}`;", "$('#clock').innerHTML = `<b>${clock(now)}</b> / ${clock(span)}`; spineTick(ratio); chunkFollow(now);")

# ---- drawer closes gradually ----
rep("function closePanel() { $('#panneau').hidden = true; $('#panneau').innerHTML = ''; }",
"""let closing = 0;
function closePanel() {
  const p = $('#panneau'); if (p.hidden) return;
  p.classList.add('leaving'); const my = ++closing;
  setTimeout(() => { if (my !== closing) return; p.hidden = true; p.innerHTML = ''; p.classList.remove('leaving'); }, 620);
}
{ const P = $('#panneau'); new MutationObserver(() => { if (!P.hidden) { closing++; P.classList.remove('leaving'); } }).observe(P, { attributes: true, attributeFilter: ['hidden'] }); }""")

# ---- back / no-scroll patches ----
rep("function render() {\n", "function render() {\n  document.body.classList.remove('back'); $('#status').hidden = true; busy.stop(); document.documentElement.style.setProperty('--prog', 0);\n  picked = null; $('#dropzone').classList.remove('filled'); $('#file').value = ''; $('#go').disabled = true; $('#go').textContent = vm.lang.t('Transcrire', 'Transcribe');\n")
rep("$('#clear').onclick = () => location.reload();", "$('#clear').onclick = () => { picked = null; zone.classList.remove('filled'); $('#go').disabled = true; $('#file').value = ''; };") if "$('#clear').onclick = () => location.reload();" in js else None
rep("fetch(p, o).then(", "fetch(p, o).catch(() => { throw new Error(vm.lang.t('Le serveur ne répond pas. Le relancer, puis recharger la page.', 'The server is not responding. Restart it, then reload the page.')); }).then(")
rep("  idle('Réessayer');\n}", "  idle('Réessayer'); $('#status').hidden = true; busy.stop(); document.documentElement.style.setProperty('--prog', 0);\n}")
rep("      setStage('Arrêté — change les réglages et relance', 0);", "      $('#status').hidden = true; busy.stop(); document.documentElement.style.setProperty('--prog', 0);\n      $('#alerts').innerHTML = `<div class=\"alert\" data-en=\"Stopped. Change the settings and restart.\">Arrêté. Modifier les réglages puis relancer.</div>`;")
# paged notes
js = js.replace('<div class="sheet">\n    <h1 class="title"', '<div class="pageview" id="pageview"><div class="sheet" id="sheet">\n    <h1 class="title"')
js = js.replace('    <div class="doc" id="doc"></div>\n  </div>\n  <div class="spine" id="spine" aria-hidden="true"></div>`;',
  '    <div class="doc" id="doc"></div>\n  </div></div>\n  <div class="pager"><button id="pgprev" aria-label="${vm.lang.t(\'Page précédente\', \'Previous page\')}">−</button><span><b id="pg">1</b> / <b id="pgn">1</b></span><button id="pgnext" aria-label="${vm.lang.t(\'Page suivante\', \'Next page\')}">+</button></div>\n  <div class="spine" id="spine" aria-hidden="true"></div>`;')
assert 'id="pageview"' in js and 'class="pager"' in js
rep("  paintSpine();\n  paintLive();\n}\n\n/* ---------- lecteur", "  layoutPages();\n  paintSpine();\n  paintLive();\n}\n\n/* ---------- lecteur")
a = js.index("      if (follow && !player.paused) {\n        const box"); e = js.index("      }\n", js.index("scrollIntoView({ behavior: 'smooth', block: 'center' })", a)) + len("      }\n")
js = js[:a] + "      if (follow && !player.paused) pageToEl(el);\n" + js[e:]

rep("  } catch {\n    note.textContent = '';\n  }\n}\n\nfunction describeModel", """  } catch {
    note.textContent = '';
    if (!sel.options.length) sel.innerHTML = '<option value="auto">' + vm.lang.t('Choisir pour moi, selon la langue', 'Choose for me, based on the language') + '</option>';
    if (!$('#clean').options.length) $('#clean').innerHTML = '<option value="">' + vm.lang.t('Aucun — garder le son tel quel', 'None — keep the sound as is') + '</option>';
    if ((loadModels.tries = (loadModels.tries || 0) + 1) < 8) setTimeout(loadModels, 2500);
  }
}

function describeModel""")

js = js.replace("const poids = n.telecharge ? 'sur cet ordinateur' : `${Math.round(n.mo)} Mo à télécharger`;\n      return `<option value=\"${n.cle}\">${escapeHtml(n.nom)} — ${poids}</option>`;",
                "const poids = n.telecharge ? '' : ` — ${Math.round(n.mo)} Mo à télécharger`;\n      return `<option value=\"${n.cle}\">${escapeHtml(n.nom)}${poids}</option>`;")
js = js.replace("const poids = m.telecharge ? 'sur cet ordinateur' : `${Math.round(m.mo)} Mo à télécharger`;\n        return `<option value=\"${m.cle}\">${escapeHtml(m.nom)} — ${poids}</option>`;",
                "const poids = m.telecharge ? '' : ` — ${Math.round(m.mo)} Mo à télécharger`;\n        return `<option value=\"${m.cle}\">${escapeHtml(m.nom)}${poids}</option>`;")
assert "sur cet ordinateur' :" not in js

# ---- add-ons: margin timeline, info popovers, save menu, hero click ----
addon = r"""
/* ---------- combien de temps, et ce que coûte chaque option ----------

   La question se pose avant de lancer, pas après : séparer les voix sur
   une réunion de deux heures et demie ajoute trois quarts d'heure, et
   c'est un choix qu'on ne peut faire que si on le sait. Une fois le
   calcul parti, le seul recours est d'arrêter et de tout reprendre.

   La durée vient du navigateur, qui lit l'en-tête du fichier sans le
   téléverser — rien ne part sur le réseau tant que « Transcrire » n'est
   pas pressé. Les coûts viennent du serveur, de la même table qui
   découpe la barre de progression : une seule source, donc l'annonce et
   la barre ne peuvent pas se contredire. */
{
  let couts = null, secondes = 0;

  api('/api/health').then(h => { couts = h && h.couts; majEstim(); }).catch(() => {});

  /* La durée sans téléverser : un élément média sur un blob local. Tous
     les conteneurs ne la rendent pas (certains .m4a sans en-tête de
     durée, un fichier tronqué), et certains ne répondent jamais — d'où
     le délai de garde. Sans durée, on n'annonce rien : une estimation
     inventée est pire que pas d'estimation. */
  window.dureeDuFichier = function (file) {
    return new Promise(res => {
      let rendu = false;
      const el = document.createElement(
        (file.type || '').startsWith('video') ? 'video' : 'audio');
      const url = URL.createObjectURL(file);
      const fini = v => {
        if (rendu) return;
        rendu = true; URL.revokeObjectURL(url); el.src = ''; res(v || 0);
      };
      el.preload = 'metadata';
      el.onloadedmetadata = () => fini(isFinite(el.duration) ? el.duration : 0);
      el.onerror = () => fini(0);
      setTimeout(() => fini(0), 5000);
      el.src = url;
    });
  };

  function dire(s) {
    const m = Math.round(s / 60);
    if (m < 1) return vm.lang.t('moins d’une minute', 'under a minute');
    if (m < 60) return m + ' min';
    return Math.floor(m / 60) + ' h ' + String(m % 60).padStart(2, '0');
  }

  /* Les mêmes étapes que pipeline.process choisira, dans le même ordre
     et aux mêmes conditions. Le nettoyage ne tourne que si la séparation
     tourne : sans voix à séparer, il n'y a rien à nettoyer pour. */
  function etapes() {
    const sep = $('#count') && $('#count').value !== 'none';
    const l = ['conversion'];
    if (sep && $('#clean') && $('#clean').value) l.push('nettoyage');
    if ($('#emb') && $('#emb').value === 'auto' && $('#lang') && !$('#lang').value) l.push('langue');
    if (sep) l.push($('#count').value === 'auto' ? 'voix_auto' : 'voix');
    return l.concat(['tranches', 'transcription', 'assemblage']);
  }

  /* Le coût de la séparation suit le modèle d'empreintes : le ResNet34
     sert de référence (poids 1,4), un ERes2Net demande la moitié de
     temps en plus. Même rapport que côté serveur, sinon l'annonce et la
     barre se contrediraient. */
  const POIDS_REF = 1.4;
  function echelleVoix() {
    const sel = $('#emb');
    /* `catalogue` est une liaison de premier niveau : visible ici, mais
       absente de window. L'interroger par window.catalogue rendait
       toujours undefined, et l'échelle serait restée à 1 sans que rien
       ne le signale — la même panne muette que pour l'aperçu vidéo. */
    if (!sel || typeof catalogue === 'undefined' || !catalogue.length) return 1;
    let cle = sel.value;
    if (cle === 'auto') {
      // « Choisir pour moi » : le premier du classement, qui est celui
      // que le serveur retiendra.
      const t = catalogue[0];
      return t && t.poids ? t.poids / POIDS_REF : 1;
    }
    const m = catalogue.find(x => x.cle === cle);
    return m && m.poids ? m.poids / POIDS_REF : 1;
  }

  const somme = l => l.reduce((t, e) => t + (couts[e] || 0)
    * (e.indexOf('voix') === 0 ? echelleVoix() : 1), 0);

  window.majEstim = function majEstim() {
    const box = $('#estim'), cv = $('#coutvoix'), cn = $('#coutnet');
    if (!box) return;
    if (!couts || !secondes) {
      box.hidden = true;
      if (cv) cv.textContent = '';
      if (cn) cn.textContent = '';
      return;
    }
    const total = somme(etapes()) * secondes;
    box.hidden = false;
    box.textContent = vm.lang.t('Environ ', 'About ') + dire(total)
      + vm.lang.t(' de traitement', ' of processing');

    /* Ce que chaque option ajoute, et non ce qu'elle coûte dans
       l'absolu : la question posée devant l'écran est « est-ce que je
       la garde ? ». Couper la séparation emporte le nettoyage avec
       elle, et le chiffre le dit. */
    const sep = $('#count') && $('#count').value !== 'none';
    if (cv) {
      const sans = somme(etapes().filter(
        e => e !== 'voix' && e !== 'voix_auto' && e !== 'nettoyage')) * secondes;
      cv.textContent = sep ? '+ ' + dire(total - sans) : '';
    }
    if (cn) {
      const net = sep && $('#clean') && $('#clean').value;
      cn.textContent = net ? '+ ' + dire(couts.nettoyage * secondes) : '';
    }
  };

  window.poserDuree = function (s) { secondes = s || 0; majEstim(); };

  /* ---------- le récapitulatif pendant le traitement ----------

     Figé au lancement, et non relu à l'affichage : ce qu'on veut savoir
     en regardant une barre à 53 %, c'est avec quoi ce calcul-là tourne.
     Les commandes, elles, gardent la valeur courante — qui peut déjà
     avoir servi à préparer la fois suivante. */
  function etiquette(sel) {
    const el = $(sel);
    if (!el || !el.options) return '';
    const o = el.options[el.selectedIndex];
    return o ? o.textContent.trim() : '';
  }

  window.figerRecap = function () {
    const t = $('#recaptxt'), b = $('#recap');
    if (!t || !b) return;
    const sep = $('#count') && $('#count').value !== 'none';
    const n = sep ? $('#count').value : '';
    const bouts = [etiquette('#lang') || vm.lang.t('Langue auto', 'Auto language')];
    bouts.push(sep
      ? (n === 'auto' ? vm.lang.t('Voix : auto', 'Voices: auto')
        : vm.lang.t('Voix : ', 'Voices: ') + n)
      : vm.lang.t('Sans séparation', 'No separation'));
    if (sep) {
      /* Le modèle de voix seulement s'il a été choisi : sur « auto »,
         l'étiquette est « Choisir pour moi, selon la langue », une
         phrase qui n'apprend rien et mange la ligne. Le vrai modèle
         n'est connu qu'une fois la langue reconnue, et il est écrit au
         journal. */
      if ($('#emb') && $('#emb').value !== 'auto') bouts.push(etiquette('#emb'));
      bouts.push($('#clean') && $('#clean').value
        ? vm.lang.t('Nettoyage : ', 'Cleanup: ') + etiquette('#clean')
        : vm.lang.t('Sans nettoyage', 'No cleanup'));
    }
    t.textContent = bouts.filter(Boolean).join('  ·  ');
    b.hidden = false;
    b.setAttribute('aria-expanded', 'false');
    const p = $('#reglages');
    if (p) p.removeAttribute('data-ouvert');
  };

  const recap = $('#recap');
  let repliePlus = false;
  if (recap) recap.onclick = () => {
    const p = $('#reglages');
    const plus = document.querySelector('.settings .more');
    const ouvert = recap.getAttribute('aria-expanded') === 'true';
    recap.setAttribute('aria-expanded', ouvert ? 'false' : 'true');
    if (p) { if (ouvert) p.removeAttribute('data-ouvert'); else p.setAttribute('data-ouvert', ''); }
    /* « Plus d'options » s'ouvre avec le reste : on vient voir les
       quatre réglages du calcul en cours, et deux d'entre eux vivent
       là-dedans. Son état d'avant est rendu à la fermeture.

       Par un clic sur le sommaire, et non en posant `open` : c'est
       vm.js qui tient ce pli, à travers une classe sur un conteneur
       intérieur. Écrire `open` ouvrait le <details> sans déplier son
       contenu — le panneau restait fermé à l'écran. Un clic appelé
       depuis le code traverse `pointer-events: none`. */
    const somm = plus && plus.querySelector(':scope > summary');
    const deplie = () => plus && !plus.querySelector(':scope > .vm-fold.off');
    if (somm) {
      if (ouvert) { if (repliePlus && deplie()) somm.click(); }
      else { repliePlus = !deplie(); if (repliePlus) somm.click(); }
    }
  };

  /* Le lancement passe par #go ; on fige au même instant, avant que
     l'écran ne bascule. */
  const go = $('#go');
  if (go) go.addEventListener('click', () => figerRecap(), true);

  ['#lang', '#count', '#emb', '#clean'].forEach(s => {
    const el = $(s);
    if (el) el.addEventListener('change', () => majEstim());
  });
  /* Les pastilles du nombre de voix et l'interrupteur écrivent dans
     #count par programme, ce qui ne déclenche pas « change ». */
  const chips = $('#numchips'), bascule = $('#sep');
  if (chips) chips.addEventListener('click', () => setTimeout(majEstim, 0));
  if (bascule) bascule.addEventListener('click', () => setTimeout(majEstim, 0));
  if (window.vm && vm.lang) vm.lang.onChange(() => majEstim());
}

/* ---------- retrouver la lecture après avoir lu ailleurs ----------

   Le suivi se coupe tout seul dès qu'on tourne une page à la main, et
   c'est voulu : sinon la page se dérobe sous les yeux de qui lit un
   passage plus loin. Mais il ne revenait jamais, et le seul témoin
   était une case de deux millimètres dans la barre. On repart en
   lecture sans s'en apercevoir, et le texte reste en arrière.

   Deux réponses. Un bouton qui ramène au passage en cours, visible
   seulement quand la situation existe. Et le suivi qui se réarme à la
   relance de la lecture — mais seulement s'il s'était coupé tout seul :
   l'avoir décoché à la main est une décision, pas un accident. */
{
  let coupeAMain = false;
  const bouton = $("#follow"), retour = $("#revenir");

  /* `follow` est une liaison de premier niveau : lisible depuis ici,
     absente de window, donc impossible à surveiller. L'état du bouton
     en est le reflet fidèle — setFollow le tient à jour — et c'est lui
     qu'on interroge. */
  const suit = () => !!bouton && bouton.classList.contains('on');

  function majRetour() {
    if (!retour) return;
    const p = (typeof player !== 'undefined') ? player : null;
    retour.hidden = !(p && !p.paused && !suit());
  }

  function rejoindre() {
    const vif = document.querySelector('.turn.live');
    if (vif && typeof pageToEl === 'function') pageToEl(vif);
  }

  /* Délégué sur le document, en phase de capture, et non posé sur le
     bouton : l'affichage du transcript réassigne `#follow.onclick` au
     moment où il monte le lecteur. Un gestionnaire posé ici au
     chargement était donc écrasé, et le décochage à la main repassait
     pour un décochage automatique — le suivi se rallumait tout seul à
     la lecture suivante, contre la volonté exprimée. Mesuré : c'est le
     seul des cinq cas d'épreuve qui échouait.
     La capture passe avant le onclick, donc `suit()` y donne encore
     l'état d'avant le clic. */
  document.addEventListener('click', ev => {
    const c = ev.target.closest && ev.target.closest('#follow, #revenir');
    if (!c) return;
    if (c.id === 'follow') {
      coupeAMain = suit();        // on s'apprête à le couper à la main
      setTimeout(majRetour, 0);
      return;
    }
    coupeAMain = false;
    if (typeof setFollow === 'function') setFollow(true);
    /* Ramener la page tout de suite : attendre la réplique suivante
       laisserait le texte en arrière pendant une minute entière. */
    rejoindre();
    majRetour();
  }, true);

  if (typeof player !== 'undefined' && player) {
    player.addEventListener('play', () => {
      if (!suit() && !coupeAMain && typeof setFollow === 'function') {
        setFollow(true);
        rejoindre();
      }
      majRetour();
    });
    player.addEventListener('pause', majRetour);

    /* Début et fin. `seek` borne et recale la page ; l'appeler plutôt
       que d'écrire currentTime garde le reste de la barre d'accord. */
    const aller = t => (typeof seek === 'function')
      ? seek(t) : (player.currentTime = t);
    const d = $('#first'), f = $('#last');
    if (d) d.onclick = () => aller(0);
    if (f) f.onclick = () => {
      /* Une poignée de dixièmes avant la fin : se poser exactement
         dessus déclenche la fin de lecture, et le lecteur se range au
         lieu de montrer le dernier passage. */
      const fin = player.duration;
      aller(isFinite(fin) && fin > 0.4 ? fin - 0.3 : 0);
    };

    /* Le suivi se coupe aussi depuis la molette et depuis la frise,
       sans passer par le bouton : on relit donc l'état au fil de la
       lecture plutôt que de s'accrocher à chaque appelant. */
    player.addEventListener('timeupdate', majRetour);
  }

  /* ---------- rejoindre les cartes de nommage ----------

     Elles ouvrent le document ; sur une réunion de deux heures, elles
     sont à cinquante pages de l'endroit où l'on vient de repérer une
     attribution fausse. Le bouton de la barre y mène, et le nom affiché
     devant chaque réplique y mène aussi — en visant la bonne carte. */
  function versNoms(idVoix) {
    if (typeof setPage === 'function') setPage(0);
    /* Le suivi ramènerait la page sur la lecture dans la seconde : on
       le coupe, et « Revenir à la lecture » reste là pour le rendre. */
    if (typeof setFollow === 'function' && suit()) setFollow(false);
    majRetour();
    const champ = idVoix
      ? document.querySelector(`.strip input[data-id="${CSS.escape(idVoix)}"]`)
      : document.querySelector('.strip input');
    if (champ) { champ.focus(); champ.select(); }
  }

  const versB = $('#versnoms');
  if (versB) versB.onclick = () => versNoms();

  /* Délégué : les répliques sont repeintes à chaque changement de nom
     et à chaque page. */
  document.addEventListener('click', ev => {
    const qui = ev.target.closest && ev.target.closest('.turn .who');
    if (!qui) return;
    const tour = qui.closest('.turn');
    const bloc = tour && shown[+tour.dataset.i];
    versNoms(bloc && bloc.speaker);
  });
}

/* ---------- après l'ajout d'une clé, sans recharger la page ----------

   branchement.js vit dans son propre fichier : il ne voit pas les
   liaisons de premier niveau d'ici, donc il ne peut pas vider lui-même
   les caches qui dépendent des clés. C'est pour cela qu'il rechargeait
   la page — une façon brutale d'obtenir le même effet, qui emportait
   aussi l'animation et tout ce qui n'était qu'en mémoire.

   Trois caches, et rien d'autre à défaire : la liste des modèles de
   relecture, les options de relecture, et le bandeau de simulation qui
   n'a plus lieu d'être une fois une clé posée. */
window.apresCles = function () {
  relOpts = null;
  modelesRelecture = null;
  const b = $('#changekey');
  if (b) b.hidden = false;
  api('/api/health').then(h => {
    const bandeau = document.getElementById('tr-sim');
    if (bandeau && h && !h.vierge) bandeau.remove();
  }).catch(() => {});
};

/* ---------- opened as a plain file (no server behind it): say so, with the way out ---------- */
if (location.protocol === 'file:') {
  const w = $('#perime'); w.hidden = false; w.removeAttribute('data-fr');
  w.setAttribute('data-en', 'This page is open as a plain file, without the program behind it, so nothing can load or be saved. Start Demarrer.command, then open http://localhost:7878/vm in the browser.');
  w.textContent = 'Cette page est ouverte comme un simple fichier, sans le programme derrière : rien ne peut se charger ni s’enregistrer. Lancer Demarrer.command, puis ouvrir http://localhost:7878/vm dans le navigateur.';
}

/* ---------- key screen (ours or the server's branchement.js): back button + fit to one screen ---------- */
{
  const sa = $('#stage-area');
  const fit = () => { const s = sa.querySelector('.setup'); if (!s) return; s.style.setProperty('--fit', 1);
    const need = s.scrollHeight, have = s.clientHeight; if (need > have + 2) s.style.setProperty('--fit', Math.max(.55, have / need * .96).toFixed(3)); };
  const addBack = () => { const s = sa.querySelector('.setup'); if (!s || s.querySelector('.backbtn')) return;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'linkbtn backbtn'; b.setAttribute('data-en', 'Back'); b.textContent = vm.lang.t('Retour', 'Back');
    b.onclick = () => { if (job && job.blocks) { render(); return; } document.body.classList.add('back');
      setTimeout(() => { sa.innerHTML = ''; $('#dock').hidden = true; document.body.classList.remove('back'); }, 1100); };
    s.prepend(b); };
  new MutationObserver(() => { addBack(); fit(); }).observe(sa, { childList: true, subtree: true });
  addEventListener('resize', fit);

  /* L'écran de dépôt et de progression se réduit de la même façon. Le
     pourcentage géant est dimensionné en vw : dans une fenêtre large
     mais courte, il dépasse par le haut et pousse le reste hors de
     l'écran, qui ne doit jamais défiler. On mesure, et on réduit. */
  const cap = $('#capture');

  /* Le facteur est une cible, jamais une valeur posée : zoom ne
     s'interpole pas tout seul, donc c'est une boucle rAF qui fait le
     trajet. Sans elle, retirer un fichier changeait la hauteur du bloc
     et le titre sautait d'un cran à l'autre en une image. */
  let viseFit = 1, fitCourant = 1, fitRaf = 0;
  const poser = v => { fitCourant = v; cap.style.setProperty('--fit', v.toFixed(4)); };
  const glisserFit = () => {
    const d = viseFit - fitCourant;
    if (Math.abs(d) < .0015) { poser(viseFit); fitRaf = 0; return; }
    poser(fitCourant + d * .16);
    fitRaf = requestAnimationFrame(glisserFit);
  };
  /* Bande morte : la seconde qui s'écrit dans « 00:17 écoulées » fait
     muter l'arbre chaque seconde. Sans seuil, chaque battement
     redimensionnait l'écran d'un demi pour cent — le tremblement qu'on
     voyait pendant tout un traitement. */
  const viser = v => {
    if (Math.abs(v - viseFit) < .012) return;
    viseFit = v;
    if (!fitRaf) fitRaf = requestAnimationFrame(glisserFit);
  };

  function mesurer() {
    if (!cap || document.body.classList.contains('back')) return;
    /* Deux pièges ici, et le second a coûté deux essais.
       scrollHeight ne voit QUE le débordement par le bas ; or le
       contenu de la zone de dépôt est calé en bas, donc il déborde par
       le HAUT — le titre géant était coupé pendant que scrollHeight
       annonçait zéro.
       Et ce n'est pas .capture qui déborde : c'est #dropzone, qui a
       `flex: 1 1 0; min-height: 0` et se laisse écraser pendant que son
       contenu, lui, garde sa taille. C'est donc lui qu'il faut mesurer. */
    const zone = $('#dropzone');
    if (!zone) return;
    /* Mesure prise à zoom 1, toujours, et le zoom courant remis avant
       de rendre la main : la valeur obtenue est alors absolue.
       Mesurer au zoom courant et en déduire une correction relative
       boucle sur soi-même — réduire laisse de la place, la place fait
       grandir, et l'écran respire sans fin. Essayé, mesuré : trente
       secondes sans jamais se stabiliser.
       Il n'y a pas de clignotement : rien n'est peint entre les deux
       écritures, qui sont dans la même tâche. */
    cap.style.setProperty('--fit', 1);
    const r = [...zone.children].map(e => e.getBoundingClientRect())
      .filter(x => x.height > 0);
    const place = zone.clientHeight;
    cap.style.setProperty('--fit', fitCourant.toFixed(4));
    if (!r.length || !(place > 60)) return;
    const besoin = Math.max(...r.map(x => x.bottom)) - Math.min(...r.map(x => x.top));
    viser(besoin > place + 2
      ? Math.max(.55, (place / besoin) * .97)
      : 1);
  }

  /* Une mesure par image au plus, et une dernière quand les
     transitions d'opacité et de graisse (1,1 s) ont fini de bouger :
     mesurer pendant qu'un bloc s'efface donne une hauteur qui n'existe
     à aucun moment. */
  let attente = 0, repos = 0;
  const fitCap = () => {
    if (!attente) attente = requestAnimationFrame(() => { attente = 0; mesurer(); });
    clearTimeout(repos);
    repos = setTimeout(mesurer, 1200);
  };
  if (cap) {
    new ResizeObserver(fitCap).observe(cap);
    new MutationObserver(fitCap).observe(cap, { childList: true, subtree: true });
    addEventListener('resize', fitCap);
    fitCap();
  }
}

/* ---------- margin timeline ---------- */
function spineDur() { return (job && job.duration) || (shown.length ? shown[shown.length - 1].end : 1) || 1; }
function paintSpine() {
  const sp = $('#spine'); if (!sp) return;
  const dur = spineDur();
  sp.innerHTML = shown.map((b, i) => `<i data-i="${i}" style="--c:${colorOf(b.speaker)};top:${(b.start / dur * 100).toFixed(3)}%;height:${Math.max((b.end - b.start) / dur * 100, .3).toFixed(3)}%"></i>`).join('') + '<b class="vw"></b><b class="ph"></b>';
  sp.onclick = e => {
    const r = sp.getBoundingClientRect(), t = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)) * dur;
    let k = 0; for (let i = 0; i < shown.length; i++) if (shown[i].start <= t) k = i;
    const el = document.querySelector(`.turn[data-i="${k}"]`); if (el) { if (follow && !player.paused) setFollow(false); setPage(pageFor(el)); }
  };
  spineView();
}
function spineTick(r) { const sp = $('#spine'); if (sp) sp.style.setProperty('--p', r); }
let spineRaf = 0;
function spineView() {
  const sp = $('#spine'); if (!sp || !shown.length) return;
  const vp = $('#pageview'); if (!vp) return;
  const top = offs[page], end = top + vp.clientHeight; let a = -1, z = -1;
  document.querySelectorAll('.turn').forEach(t => { const i = +(t.dataset.i ?? t.dataset.c); if (t.offsetTop + t.offsetHeight > top && t.offsetTop < end) { if (a < 0) a = i; z = i; } });
  const dur = spineDur();
  if (a < 0) { sp.style.setProperty('--vt', '0%'); sp.style.setProperty('--vh', '8%'); return; }
  const t0 = page === 0 ? 0 : shown[a].start;
  sp.style.setProperty('--vt', (t0 / dur * 100) + '%'); sp.style.setProperty('--vh', Math.max((shown[z].end - t0) / dur * 100, 1.5) + '%');
}
/* ---------- pages ---------- */
let page = 0, offs = [0], pageLock = 0;
function layoutPages() {
  const vp = $('#pageview'), col = $('#sheet'); if (!vp || !col) return;
  const H = vp.clientHeight - 16; offs = [0]; let start = 0;
  col.querySelectorAll('.turn').forEach(t => { if (t.offsetTop + t.offsetHeight - start > H && t.offsetTop - 12 > start) { start = t.offsetTop - 12; offs.push(start); } });
  setPage(Math.min(page, offs.length - 1));
}
function setPage(k) {
  const col = $('#sheet'); if (!col) return;
  page = Math.max(0, Math.min(offs.length - 1, k));
  col.style.translate = `0 ${-offs[page]}px`; col.classList.toggle('paged', page > 0);
  const g = $('#pg'), n = $('#pgn'); if (g) g.textContent = page + 1; if (n) n.textContent = offs.length;
  spineView();
}
function pageFor(el) { let k = 0; for (let i = 0; i < offs.length; i++) if (offs[i] <= el.offsetTop) k = i; return k; }
function chunkFollow(now) {
  if (liveIndex < 0 || !follow || player.paused || !document.querySelector(`.turn[data-c="${liveIndex}"]`)) return;
  const all = [...document.querySelectorAll(`.turn[data-i="${liveIndex}"], .turn[data-c="${liveIndex}"]`)]; let cur = all[0];
  all.forEach(t => { if (+t.dataset.ts <= now) cur = t; });
  if (!cur.classList.contains('live')) { document.querySelectorAll('.turn.live').forEach(t => t.classList.remove('live')); cur.classList.add('live'); pageToEl(cur); }
}
function pageToEl(el) { const k = pageFor(el); if (k !== page) setPage(k); }
function nav(d) { if (follow && !player.paused) setFollow(false); setPage(page + d); }
document.addEventListener('wheel', e => {
  if (!$('#pageview') || e.target.closest('.panneau, .vm-sel')) return;
  e.preventDefault(); if (Date.now() < pageLock || Math.abs(e.deltaY) < 8) return; pageLock = Date.now() + 750; nav(e.deltaY > 0 ? 1 : -1);
}, { passive: false });
let ty = null; document.addEventListener('touchstart', e => { ty = e.touches[0].clientY; }, { passive: true });
document.addEventListener('touchend', e => { if (ty === null || !$('#pageview') || e.target.closest('.panneau, .scrub')) { ty = null; return; } const dy = ty - e.changedTouches[0].clientY; ty = null; if (Math.abs(dy) > 50) nav(dy > 0 ? 1 : -1); }, { passive: true });
document.addEventListener('keydown', e => {
  if (!$('#pageview') || /^(input|textarea|select)$/i.test(e.target.tagName || '')) return;
  if (e.key === 'PageDown') { e.preventDefault(); nav(1); } else if (e.key === 'PageUp') { e.preventDefault(); nav(-1); }
  else if (e.key === 'Home') { e.preventDefault(); nav(-99); } else if (e.key === 'End') { e.preventDefault(); nav(99); }
});
addEventListener('resize', layoutPages);
if (document.fonts) document.fonts.ready.then(layoutPages);

/* ---------- info popovers, save menu, new, hero click ---------- */
document.addEventListener('click', e => {
  const b = e.target.closest('.info');
  document.querySelectorAll('.info[aria-expanded="true"]').forEach(x => { if (x !== b) x.setAttribute('aria-expanded', 'false'); });
  if (b) b.setAttribute('aria-expanded', b.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
  else if (!e.target.closest('.tipbody')) { /* closed above */ }
  const sw = $('.savewrap'), sm = e.target.closest('#savemenu');
  if (sm) { sw.classList.toggle('open'); sm.setAttribute('aria-expanded', String(sw.classList.contains('open'))); }
  else if (sw && sw.classList.contains('open') && !e.target.closest('.savegroup')) { sw.classList.remove('open'); $('#savemenu').setAttribute('aria-expanded', 'false'); }
  else if (e.target.closest('.savegroup button')) setTimeout(() => { sw.classList.remove('open'); $('#savemenu').setAttribute('aria-expanded', 'false'); }, 250);
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.info[aria-expanded="true"]').forEach(x => x.setAttribute('aria-expanded', 'false')); });
$('#newjob').onclick = () => document.body.classList.toggle('back');
const setCount = v => { const c = $('#count'); c.value = v; c.dispatchEvent(new Event('change')); };
let lastN = 'auto';
document.addEventListener('click', e => {
  const t = e.target.closest('#sep'), c = e.target.closest('#numchips button'), pg = e.target.closest('#pgprev, #pgnext');
  if (t) { const on = !t.classList.contains('on'); t.classList.toggle('on', on); t.setAttribute('aria-checked', String(on)); setCount(on ? lastN : 'none'); }
  if (c) { lastN = c.dataset.v; document.querySelectorAll('#numchips button').forEach(x => x.classList.toggle('on', x === c)); setCount(lastN); }
  if (pg) nav(pg.id === 'pgnext' ? 1 : -1);
});
$('#hero').addEventListener('click', e => { if (!picked && !e.target.closest('.tipwrap, button, a')) $('#file').click(); });
"""
js = js.rstrip() + "\n" + addon + "\n"

# ---- English map + enable ----
en = open(os.path.join(HERE, 'i18n_en.js'), encoding='utf-8').read()
en = re.sub(r"`([^`]*)`(\s*):(\s*)`", r"[`\1`]\2:\3`", en)
js = js.rstrip() + "\n" + en + "\n"


import base64
svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' fill='#0c0c0b'/><path d='M10 11h44v15H40v28H24V26H10z' fill='#f1f0ec'/><rect y='54' width='64' height='10' fill='#1f3bff'/></svg>"
from urllib.parse import quote
FAV = "<link rel=\"icon\" type=\"image/svg+xml\" href=\"data:image/svg+xml," + quote(svg) + "\">\n<link rel=\"apple-touch-icon\" href=\"data:image/png;base64," + open(os.path.join(HERE, 'apple.b64')).read().strip() + "\">\n<meta name=\"theme-color\" content=\"#0c0c0b\">\n"

head = '''<!DOCTYPE html>
<html lang="fr" data-vm-voice="calm" data-vm-accent="cobalt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Transcripteur</title>
'''+FAV+'''<script>try{var t=localStorage.getItem('vm-theme');if(t?t==='ink':matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.dataset.vm='ink'}catch(e){}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,100..900&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,300..700&display=swap" rel="stylesheet">
<style>
'''
out = head + open(KIT + 'vm.css').read() + open(os.path.join(HERE, 'tr_keep.css')).read() + open(os.path.join(HERE, 'tr2.css')).read() + "</style>\n</head>\n" + open(os.path.join(HERE, 'body2.html'), encoding='utf-8').read()
out += "\n<script>\n" + open(KIT + 'vm.js').read() + "\n</script>\n<script>" + js + "</script>\n</body>\n</html>\n"
open(OUT, 'w', encoding='utf-8').write(out)
print('written', len(out))
