/* Le parcours du site : télécharger, ouvrir, la clé.
 *
 * Même règle que l'application : un geste par écran, aucun défilement,
 * Retour partout. Les textes sont écrits à plat — ce qu'il faut faire,
 * ce que fait le programme, ce qui part sur le réseau. Pas de
 * rassurance, pas de formules.
 */
(function () {
  'use strict';

  var L = function (fr, en) {
    return (window.vm && vm.lang) ? vm.lang.t(fr, en) : fr;
  };
  var $ = function (s) { return document.querySelector(s); };

  var SORTIE = 360, ENTREE = 440;

  /* ------------------------------------------------ le système */

  function systeme() {
    var d = navigator.userAgentData;
    var p = (d && d.platform) || '';
    var ua = navigator.userAgent || '';
    if (/mac/i.test(p) || /Mac OS X|Macintosh/.test(ua)) return 'mac';
    if (/win/i.test(p) || /Windows/.test(ua)) return 'windows';
    if (/linux/i.test(p) || /Linux|X11/.test(ua)) return 'linux';
    return '';
  }

  var NOMS = { mac: 'macOS', windows: 'Windows', linux: 'Linux' };

  /* Gestes d'ouverture, par système. Les paquets ne sont pas signés :
     chaque système prévient à sa façon, et le geste diffère. */
  var OUVRIR = {
    mac: {
      fr: ['Déplacer Transcripteur.app dans Applications.',
           'Clic droit sur l’application, puis Ouvrir.',
           'Ouvrir de nouveau dans la fenêtre d’avertissement.'],
      en: ['Move Transcripteur.app to Applications.',
           'Right-click the app, then Open.',
           'Click Open again in the warning dialog.'],
    },
    windows: {
      fr: ['Décompresser le dossier.',
           'Lancer Transcripteur.exe.',
           'Si Windows affiche un avertissement : Informations complémentaires, puis Exécuter quand même.'],
      en: ['Extract the folder.',
           'Run Transcripteur.exe.',
           'If Windows shows a warning: More info, then Run anyway.'],
    },
    linux: {
      fr: ['tar -xzf Transcripteur-Linux.tar.gz',
           'cd Transcripteur && ./Transcripteur',
           'WebKitGTK est requis : libwebkit2gtk-4.1 sur Debian et Ubuntu.'],
      en: ['tar -xzf Transcripteur-Linux.tar.gz',
           'cd Transcripteur && ./Transcripteur',
           'WebKitGTK is required: libwebkit2gtk-4.1 on Debian and Ubuntu.'],
    },
  };

  var POURQUOI = {
    fr: 'Les paquets ne sont pas signés. La signature coûte 99 $ US par an '
      + 'chez Apple et un certificat payant chez Microsoft ; le système '
      + 'prévient donc à la première ouverture, une fois.',
    en: 'The packages are unsigned. Signing costs US$99 a year from Apple '
      + 'and a paid certificate from Microsoft, so the system warns on first '
      + 'launch, once.',
  };

  var PUCE = {
    fr: 'Menu Pomme → À propos de ce Mac. La ligne « Puce » indique M1, M2, '
      + 'M3 ou M4 ; « Processeur » indique Intel.',
    en: 'Apple menu → About This Mac. A "Chip" line means M1, M2, M3 or M4; '
      + 'a "Processor" line means Intel.',
  };

  /* ------------------------------------------------ les écrans */

  var etat = { file: [], i: 0, os: systeme(), cible: '' };

  function depart() {
    return etat.os
      ? [{ v: 'accueil' }, { v: 'ouvrir' }, { v: 'cle' }]
      : [{ v: 'accueil' }, { v: 'systeme' }, { v: 'ouvrir' }, { v: 'cle' }];
  }

  function demarrer() {
    etat.file = depart();
    etat.i = 0;
    peindre(1);
    $('#retour').onclick = reculer;
    document.addEventListener('click', function (e) {
      var b = e.target.closest('.info');
      document.querySelectorAll('.info[aria-expanded="true"]').forEach(function (x) {
        if (x !== b) x.setAttribute('aria-expanded', 'false');
      });
      if (b) {
        b.setAttribute('aria-expanded',
          b.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') reculer();
    });
    addEventListener('resize', ajuster);
  }

  function avancer() { if (etat.i < etat.file.length - 1) glisser(etat.i + 1, 1); }
  function reculer() { if (etat.i > 0) glisser(etat.i - 1, -1); }

  function glisser(vers, sens) {
    var v = $('#vue');
    v.classList.add('part');
    if (sens < 0) v.style.translate = '24px 0';
    setTimeout(function () { etat.i = vers; peindre(sens); }, SORTIE);
  }

  function peindre(sens) {
    var v = $('#vue');
    var e = etat.file[etat.i];
    v.innerHTML = vue(e);
    brancher();

    document.body.dataset.ecran = e.v;
    $('#retour').hidden = etat.i === 0;
    $('#compte').textContent = etat.i === 0 ? ''
      : L('Étape', 'Step') + ' ' + etat.i + ' / ' + (etat.file.length - 1);
    $('.jauge i').style.setProperty(
      '--part', ((etat.i + 1) / etat.file.length).toFixed(3));

    v.classList.remove('part');
    v.style.translate = '';
    v.classList.add('vient');
    if (sens < 0) v.style.translate = '-24px 0';
    void v.offsetWidth;
    v.style.transition = 'opacity ' + ENTREE + 'ms var(--vm-ease), translate '
      + ENTREE + 'ms var(--vm-ease)';
    v.classList.remove('vient');
    v.style.translate = '0 0';
    ajuster();
  }

  /* Rien ne doit déborder : on réduit plutôt que de laisser défiler. */
  function ajuster() {
    var s = document.querySelector('.scene');
    if (!s) return;
    s.style.setProperty('--fit', 1);
    var besoin = s.scrollHeight, place = s.clientHeight;
    if (besoin > place + 2) {
      s.style.setProperty('--fit',
        Math.max(.55, place / besoin * .97).toFixed(3));
    }
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
        "'": '&#39;' }[c];
    });
  }

  function bulle(texte) {
    return '<span class="tipwrap"><button class="info" type="button"'
      + ' aria-expanded="false" aria-label="' + L('Détails', 'Details')
      + '">i</button><span class="tipbody">' + esc(texte) + '</span></span>';
  }

  var FLECHE = '<svg viewBox="0 0 24 24" aria-hidden="true">'
    + '<path d="M12 3v13M6 11l6 6 6-6M4 21h16"/></svg>';

  function vue(e) {
    if (e.v === 'accueil') return vueAccueil();
    if (e.v === 'systeme') return vueSysteme();
    if (e.v === 'puce') return vuePuce();
    if (e.v === 'ouvrir') return vueOuvrir();
    return vueCle();
  }

  function vueAccueil() {
    var os = etat.os;
    var bouton = os
      ? '<button type="button" class="gros" data-x="telecharger">' + FLECHE
        + L('Télécharger pour ', 'Download for ') + NOMS[os] + '</button>'
        + '<button type="button" class="discret" data-x="systeme">'
        + L('Autre système', 'Other system') + '</button>'
      : '<button type="button" class="gros" data-x="systeme">' + FLECHE
        + L('Télécharger', 'Download') + '</button>';

    return '<h1>Transcripteur</h1>'
      + '<p class="dit">' + L(
        'Transcription de réunions avec séparation des locuteurs. '
        + 'Le traitement se fait sur votre ordinateur. '
        + 'macOS, Windows et Linux.',
        'Meeting transcription with speaker separation. Processing runs on '
        + 'your own computer. macOS, Windows and Linux.') + '</p>'
      + bouton
      + '<dl class="spec">'
      + '<dt>' + L('Formats', 'Formats') + '</dt><dd>'
      + L('Audio et vidéo, jusqu’à 2 Go.', 'Audio and video, up to 2 GB.')
      + '</dd>'
      + '<dt>' + L('Local', 'Local') + '</dt><dd>'
      + L('Séparation des voix, sous-titres, stockage des transcriptions.',
          'Voice separation, subtitles, transcript storage.') + '</dd>'
      + '<dt>' + L('Réseau', 'Network') + '</dt><dd>'
      + L('L’audio compressé est envoyé à Groq pour la reconnaissance de la '
          + 'parole. Rien d’autre ne sort.',
          'Compressed audio is sent to Groq for speech recognition. Nothing '
          + 'else leaves the machine.') + '</dd>'
      + '<dt>' + L('Compte', 'Account') + '</dt><dd>'
      + L('Aucun. Une clé d’API Groq, gratuite, est requise.',
          'None. A free Groq API key is required.') + '</dd>'
      + '</dl>';
  }

  function vueSysteme() {
    return '<span class="etiq">' + L('Système', 'System') + '</span>'
      + '<h2>' + L('Choisir', 'Choose') + '</h2>'
      + '<div class="choix">'
      + puce('mac', 'macOS', L('10.15 ou plus récent', '10.15 or newer'))
      + puce('windows', 'Windows', L('10 ou 11', '10 or 11'))
      + puce('linux', 'Linux', L('x86-64, glibc 2.35+', 'x86-64, glibc 2.35+'))
      + '</div>';
  }

  function puce(id, nom, note) {
    return '<button type="button" class="puce" data-os="' + id + '"><b>'
      + nom + '</b><span>' + note + '</span></button>';
  }

  function vuePuce() {
    return '<span class="etiq">macOS</span>'
      + '<h2>' + L('Quelle puce ?', 'Which chip?') + '</h2>'
      + '<p class="dit">' + L(
        'Les deux paquets ne sont pas interchangeables : le mauvais ne '
        + 'démarre pas.', 'The two packages are not interchangeable: the '
        + 'wrong one will not start.') + ' ' + bulle(L(PUCE.fr, PUCE.en))
      + '</p>'
      + '<div class="choix">'
      + puce2('mac-silicon', 'Apple M1 – M4', L('Puces Apple', 'Apple chips'))
      + puce2('mac-intel', 'Intel', L('Processeurs Intel', 'Intel processors'))
      + '</div>';
  }

  function puce2(cible, nom, note) {
    return '<button type="button" class="puce" data-cible="' + cible
      + '"><b>' + nom + '</b><span>' + note + '</span></button>';
  }

  function vueOuvrir() {
    var os = etat.os || 'mac';
    var pas = OUVRIR[os][(window.vm && vm.lang ? vm.lang.get() : 'fr')] || OUVRIR[os].fr;
    return '<span class="etiq">' + NOMS[os] + '</span>'
      + '<h2>' + L('Ouvrir', 'Open') + '</h2>'
      + '<dl class="spec">'
      + pas.map(function (p, i) {
        return '<dt>' + String(i + 1).padStart(2, '0') + '</dt><dd>'
          + esc(p) + '</dd>';
      }).join('')
      + '</dl>'
      + '<p class="dit">' + L('Une seule fois.', 'Once only.') + ' '
      + bulle(L(POURQUOI.fr, POURQUOI.en)) + '</p>'
      + '<button type="button" class="gros" data-x="suivant">'
      + L('Suite', 'Next') + '</button>';
  }

  function vueCle() {
    return '<span class="etiq">' + L('Clé d’API', 'API key') + '</span>'
      + '<h2>Groq</h2>'
      + '<p class="dit">' + L(
        'La reconnaissance de la parole passe par Groq. Une clé est requise : '
        + 'gratuite, sans carte bancaire. L’application la demande au premier '
        + 'démarrage et guide la création, étape par étape.',
        'Speech recognition goes through Groq. A key is required: free, no '
        + 'credit card. The app asks for it on first launch and walks through '
        + 'creating one, step by step.') + '</p>'
      + '<a class="gros" href="/aide/">' + L('Marche à suivre', 'Instructions')
      + '</a>';
  }

  /* ------------------------------------------------ les actions */

  function brancher() {
    var v = $('#vue');

    v.querySelectorAll('[data-x]').forEach(function (b) {
      b.onclick = function () {
        var q = b.dataset.x;
        if (q === 'suivant') return avancer();
        if (q === 'systeme') {
          etat.file.splice(etat.i + 1, 0, { v: 'systeme' });
          return avancer();
        }
        if (q === 'telecharger') return choisirOs(etat.os);
      };
    });

    v.querySelectorAll('[data-os]').forEach(function (b) {
      b.onclick = function () { choisirOs(b.dataset.os); };
    });

    v.querySelectorAll('[data-cible]').forEach(function (b) {
      b.onclick = function () { telecharger(b.dataset.cible); };
    });
  }

  function choisirOs(os) {
    etat.os = os;
    if (os === 'mac') {
      // Un seul choix « Mac », puis la question de la puce : deux
      // boîtes macOS côte à côte sur l'accueil prêtent à confusion.
      etat.file.splice(etat.i + 1, 0, { v: 'puce' });
      return avancer();
    }
    telecharger(os);
  }

  function telecharger(cible) {
    etat.cible = cible;
    // Le téléchargement part, et l'écran suivant explique l'ouverture.
    var a = document.createElement('a');
    a.href = '/telecharger/' + cible;
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
    // La suite du parcours est l'ouverture, puis la clé.
    var reste = etat.file.slice(etat.i + 1).filter(function (x) {
      return x.v === 'ouvrir' || x.v === 'cle';
    });
    if (!reste.length) etat.file.push({ v: 'ouvrir' }, { v: 'cle' });
    while (etat.file[etat.i + 1] && etat.file[etat.i + 1].v !== 'ouvrir') {
      etat.file.splice(etat.i + 1, 1);
    }
    avancer();
  }

  if (window.vm && vm.lang) {
    vm.lang.enable({ default: 'fr' });
    vm.lang.onChange(function () { peindre(1); });
  }
  demarrer();
})();
