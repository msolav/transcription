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
rep("`<h4>Relecture en cours</h4><pre>${", "`<h4>Relecture en cours</h4><pre data-no-i18n>${")
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
    $('#fname').textContent = base; $('#fmeta').textContent = (ext ? ext + '  ·  ' : '') + mb + ' ' + vm.lang.t('Mo', 'MB'); }
  zone.classList.add('filled');
  $('#clear').onclick = () => location.reload();
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
  const fitCap = () => {
    if (!cap || document.body.classList.contains('back')) return;
    cap.style.setProperty('--fit', 1);
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
    const r = [...zone.children].map(e => e.getBoundingClientRect())
      .filter(x => x.height > 0);
    if (!r.length) return;
    const besoin = Math.max(...r.map(x => x.bottom)) - Math.min(...r.map(x => x.top));
    const place = zone.clientHeight;
    if (place > 60 && besoin > place + 2) {
      cap.style.setProperty('--fit',
        Math.max(.55, (place / besoin) * 0.97).toFixed(3));
    }
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
