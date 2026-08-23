/* Contrôles de la comparaison mot à mot affichée dans le panneau de
   relecture. Optionnel : ne tourne que si node est installé.
       node transcripteur/verifier_diff.js                              */
const fs = require('fs'), path = require('path');
const h = fs.readFileSync(path.join(__dirname, 'static', 'index.html'), 'utf8');
const js = h.match(/<script>([\s\S]*)<\/script>/)[1];
const escapeHtml = s => String(s).replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
eval(js.slice(js.indexOf('const DIFF_MAX_MOTS'), js.indexOf('function comparer(')));

let ok = 0, rate = 0;
const v = (nom, cond, d) => { console.log((cond ? '  ok   ' : '  RATE ') + nom +
  (cond ? '' : '  -> ' + d)); cond ? ok++ : rate++; };

let d = diffMots("ils vont etre reevalues avant d etre accordes",
                 "Ils vont être réévalués avant d'être accordés.");
v("mots inchanges reperes", d.some(p => p.t === '=' && p.mots.includes('vont')));
v("gauche sans les ajouts", !peindre(d, '-').includes('réévalués'), peindre(d, '-'));
v("droite sans les retraits", !peindre(d, '+').includes('reevalues'), peindre(d, '+'));

d = diffMots("il y a un comite", "il y a un comité qui decide");
v("insertion marquee a droite", peindre(d, '+').includes('<mark class="mis">'));
v("insertion absente a gauche", !peindre(d, '-').includes('decide'));

d = diffMots("se mobiliser ensemble se mobiliser", "se mobiliser ensemble");
v("suppression marquee a gauche", peindre(d, '-').includes('<mark class="ote">'));

d = diffMots("rien ne change ici", "rien ne change ici");
v("aucun marquage si identique",
  !peindre(d, '-').includes('<mark') && !peindre(d, '+').includes('<mark'));

d = diffMots("a < b", "a > b");
v("le HTML est echappe", !peindre(d, '+').includes('<b'), peindre(d, '+'));

const long = n => Array.from({ length: n }, (_, i) => 'mot' + i).join(' ');
const t0 = Date.now(); diffMots(long(400), long(400).replace(/mot50 /, 'MOT50 '));
v("400 mots diffes rapidement", Date.now() - t0 < 300, (Date.now() - t0) + ' ms');
const t1 = Date.now(); const enorme = diffMots(long(4000), long(4000));
v("bloc demesure : repli sans figer", Date.now() - t1 < 200 && enorme.length === 2,
  (Date.now() - t1) + ' ms');

console.log(`\n${ok} reussis, ${rate} echecs`);
process.exit(rate ? 1 : 0);
