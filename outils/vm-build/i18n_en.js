
/* ---------- English (interface chrome is translated in the markup via data-en; these are the strings JS and the server create) ---------- */
vm.lang.add({
  exact: {
    // stages (server)
    `En attente`: `Waiting`, `Envoi du fichier`: `Uploading the file`, `Préparation de l'envoi`: `Preparing the upload`, `Nettoyage du son`: `Cleaning the audio`,
    `Conversion`: `Converting`, `Reconnaissance de la langue`: `Detecting the language`, `Séparation des voix`: `Separating the voices`, `Transcription`: `Transcribing`,
    `Assemblage`: `Putting it together`, `Extraits d'écoute`: `Preparing the listening samples`, `Terminé`: `Done`, `Arrêt`: `Stopped`, `Arrêté`: `Stopped`,
    `Arrêt en cours…`: `Stopping…`, `Arrêté — change les réglages et relance`: `Stopped. Change the settings and run it again.`,
    // buttons and states
    `Transcrire`: `Transcribe`, `Transcrire à nouveau`: `Transcribe again`, `Envoi…`: `Uploading…`, `Traitement en cours`: `Processing`, `Réessayer`: `Try again`, `Relancer`: `Run again`,
    `Arrêter le traitement`: `Stop processing`, `Arrêt…`: `Stopping…`, `Changer`: `Change`, `Vérification…`: `Checking…`, `Enregistrer`: `Save`,
    // languages
    `Français`: `French`, `Anglais`: `English`, `Espagnol`: `Spanish`, `Allemand`: `German`, `Italien`: `Italian`, `Portugais`: `Portuguese`, `Néerlandais`: `Dutch`,
    `Chinois (mandarin)`: `Chinese (Mandarin)`, `Japonais`: `Japanese`, `Coréen`: `Korean`, `Russe`: `Russian`, `Ukrainien`: `Ukrainian`, `Polonais`: `Polish`,
    `Tchèque`: `Czech`, `Roumain`: `Romanian`, `Grec`: `Greek`, `Turc`: `Turkish`, `Arabe`: `Arabic`, `Hébreu`: `Hebrew`, `Indonésien`: `Indonesian`,
    `Vietnamien`: `Vietnamese`, `Suédois`: `Swedish`, `Danois`: `Danish`, `Norvégien`: `Norwegian`, `Finnois`: `Finnish`, `Détection automatique`: `Detect automatically`,
    `Laisser détecter`: `Let it detect`, `Ne pas séparer — beaucoup plus rapide`: `Do not separate — much faster`, `1 seule personne`: `1 person only`,
    `Choisir pour moi, selon la langue`: `Choose for me, based on the language`, `Aucun — garder le son tel quel`: `None — keep the audio as it is`,
    // count / model / cleanup hints
    `Le texte seul, sans chercher qui parle. C'est l'étape la plus longue : sur une réunion de deux heures, quelques minutes au lieu d'une heure. Les comptes rendus et résumés n'en ont pas besoin.`:
      `Text only, without working out who is speaking. That is the longest step: on a two-hour meeting, a few minutes instead of an hour. Minutes and summaries don't need it.`,
    `Le nombre de personnes sera deviné. Moins fiable que de l'indiquer.`: `The number of people will be guessed. Less reliable than telling it.`,
    `Un seul locuteur : rien à séparer, donc aussi rapide que l'option ci-dessus.`: `A single speaker: nothing to separate, so as fast as the option above.`,
    `La séparation est nettement plus fiable quand le nombre est indiqué, mais elle reste approximative sur un micro unique dans une salle.`:
      `Separation is much more reliable when the number is given, but it stays approximate with a single microphone in a room.`,
    `Le modèle sera choisi d'après la langue indiquée.`: `The model will be chosen from the language given.`,
    `La langue sera reconnue sur une minute d'enregistrement, puis le modèle choisi en conséquence. Si l'enregistrement mêle plusieurs langues, indiquer la langue principale donne un meilleur résultat.`:
      `The language will be detected from one minute of the recording, then the model chosen to match. If the recording mixes several languages, giving the main one gives a better result.`,
    `Le son part tel quel. À essayer si l'enregistrement est déjà propre, ou si le nettoyage dégrade le résultat.`:
      `The audio is used as it is. Worth trying if the recording is already clean, or if cleanup makes the result worse.`,
    // voice models and cleaners (server notes)
    `Entraîné sur VoxCeleb, une centaine de nationalités. Rapide.`: `Trained on VoxCeleb, about a hundred nationalities. Fast.`,
    `Même idée, autre équipe, affiné à marge large. Rapide.`: `Same idea, different team, tuned with a wide margin. Fast.`,
    `Architecture différente : à essayer quand les CAM++ confondent deux voix.`: `Different architecture: try it when the CAM++ models confuse two voices.`,
    `Encore une autre architecture, sur les mêmes données.`: `Yet another architecture, on the same data.`,
    `Anglais uniquement, mais réputé solide. Lent et lourd.`: `English only, but known to be solid. Slow and heavy.`,
    `Version légère du précédent.`: `Lightweight version of the previous one.`,
    `L'ancien réglage par défaut. Correct en anglais, jamais pensé pour le français.`: `The former default. Fine in English, never designed for French.`,
    `Mandarin uniquement. Trois fois plus lent, sans avantage hors chinois.`: `Mandarin only. Three times slower, with no advantage outside Chinese.`,
    `Mandarin, sur des enregistrements variés.`: `Mandarin, on varied recordings.`,
    `Enlève le souffle sans toucher au timbre. C'est ce qui a donné la meilleure séparation dans nos mesures, et c'est presque instantané.`:
      `Removes hiss without touching the voice's character. It gave the best separation in our measurements, and it is almost instant.`,
    `Nettoie beaucoup plus, mais a fait disparaître une voix sur trois dans notre enregistrement d'essai. À réserver à un son très dégradé, et à vérifier en écoutant les extraits.`:
      `Cleans much more, but made one voice in three disappear in our test recording. Keep it for very poor audio, and check by listening to the samples.`,
    `Encore plus agressif, avec le même risque de confondre deux personnes. Deux fois plus lent que le précédent.`:
      `Even more aggressive, with the same risk of merging two people. Twice as slow as the previous one.`,
    // sign-in key screen
    `Une clé,`: `One key,`, `et c'est tout.`: `and that's it.`,
    `La reconnaissance de la parole passe par Groq. Il te faut une clé gratuite, à coller une seule fois.`: `Speech recognition goes through Groq. You need a free key, to paste just once.`,
    `Ouvre`: `Open`, `Connecte-toi (Google ou e-mail, sans carte bancaire)`: `Sign in (Google or e-mail, no credit card)`, `Clique sur`: `Click`, `et copie ce qui s'affiche`: `and copy what appears`,
    `La clé est rangée dans ton dossier personnel, sur cette machine. Elle n'est envoyée qu'à Groq.`: `The key is stored in your personal folder, on this machine. It is only sent to Groq.`,
    // review panel
    `Relecture`: `Review`, `Corriger l'attribution`: `Fix who said what`, `Corriger le texte`: `Fix the text`, `Lancer`: `Start`, `Fermer`: `Close`,
    `Contexte : sigles, noms propres, rôle de chacun. Par exemple « AEPP = Association des entreprises. Vincent développe le site, Annie dirige, Dominique gère les locaux. »`:
      `Context: acronyms, proper names, each person's role. For example “AEPP = Association of businesses. Vincent builds the website, Annie is the director, Dominique manages the premises.”`,
    `L'original n'est pas modifié : les corrections s'affichent ici une par une et se décochent. L'attribution se juge sur la syntaxe, ce qui répare les phrases coupées en deux — mais une personne qui termine la phrase d'une autre reste indétectable par ce moyen.`:
      `The original is not changed: corrections appear here one by one and can be unticked. Who said what is judged from the grammar, which repairs sentences cut in two — but a person finishing someone else's sentence cannot be detected that way.`,
    `Relecture en cours`: `Review in progress`, `lecture des premiers blocs…`: `reading the first blocks…`, `Aucune correction proposée.`: `No corrections suggested.`,
    `Appliquer la sélection`: `Apply the selection`, `Actuel`: `Current`, `Proposé`: `Proposed`, `devient`: `becomes`,
    `Voir l'original`: `Show the original`, `Voir la version relue`: `Show the reviewed version`, `Rien à relire`: `Nothing to review`, `Il faut un transcript terminé.`: `A finished transcript is needed first.`,
    `Lit la réunion entière d'un seul coup.`: `Reads the whole meeting at once.`, `Lit par tranches de dix blocs`: `Reads in slices of ten blocks`,
    `, sans voir le reste de la réunion.`: `, without seeing the rest of the meeting.`, `pour la lecture d'un seul tenant.`: `to read the whole meeting at once.`,
    `Ajouter une clé Gemini (gratuite)`: `Add a Gemini key (free)`,
    `Gratuit, sans carte bancaire, sur`: `Free, no credit card, at`, `. La clé est rangée dans le trousseau du système et n'est envoyée qu'à`: `. The key is stored in the system keychain and is only sent to`,
    // review models (server notes)
    `Le plus capable. Voit la réunion entière d'un coup.`: `The most capable. Sees the whole meeting at once.`,
    `Deux fois moins cher qu'Opus, même contexte.`: `Half the price of Opus, same context.`, `Quelques centimes par réunion.`: `A few cents per meeting.`,
    `Gratuit, et voit la réunion entière d'un coup. Peu de requêtes par jour, ce qui suffit largement.`: `Free, and sees the whole meeting at once. Few requests per day, which is plenty.`,
    `Plus de requêtes par jour, un peu moins fin.`: `More requests per day, slightly less fine-grained.`, `Gratuit, par tranches de dix blocs. Quota quotidien.`: `Free, in slices of ten blocks. Daily quota.`,
    `Gratuit et rapide, un peu moins sûr.`: `Free and fast, slightly less reliable.`,
    // summary panel
    `Résumé`: `Summary`, `Rédiger`: `Write it`, `Rédaction…`: `Writing…`, `Aperçu de la forme`: `Preview of the format`, `Contexte : sigles, noms propres, rôle de chacun.`: `Context: acronyms, proper names, each person's role.`,
    `Copier`: `Copy`, `Enregistrer .txt`: `Save as .txt`, `Résumé copié`: `Summary copied`,
    `Compte rendu`: `Meeting minutes`, `Décisions et suites à donner`: `Decisions and follow-ups`, `Résumé bref`: `Short summary`, `Par thème`: `By topic`,
    `Transcript lisible`: `Readable transcript`, `Questions soulevées`: `Questions raised`,
    // transcript screen
    `· écoute puis nomme, le texte se met à jour`: `· listen, then name them; the text updates`, `Donne le même nom à deux cartes pour les fusionner`: `Give two cards the same name to merge them`,
    `Nommer`: `Name`, `Écouter cette voix`: `Listen to this voice`, `Arrêter l'écoute`: `Stop listening`, `Lecture`: `Play`,
    `Texte copié.`: `Text copied.`, `Copie refusée par le navigateur.`: `Copy refused by the browser.`
  },
  rules: [
    [/^Relecture en cours$/, () => `Correction in progress`],
    [/^Relecture arrêtée$/, () => `Correction stopped`],
    [/^Arrêt…$/, () => `Stopping…`],
    [/^arrêt demandé$/, () => `stop requested`],
    [/^Aucune correction n'a été trouvée avant l'arrêt\. Le transcript\s+est inchangé\.$/, () => `No correction was found before the stop. The transcript is unchanged.`],
    [/^Séparation des voix (\d+) %$/, (m, n) => `Separating the voices ${n} %`],
    [/^Transcription (\d+)\/(\d+)$/, (m, a, b) => `Transcribing ${a}/${b}`],
    [/^(.+) — sur cet ordinateur$/, (m, n) => `${n} — on this computer`],
    [/^(.+) — (\d+) Mo à télécharger$/, (m, n, mo) => `${n} — ${mo} MB to download`],
    [/^(.+) — clé manquante$/, (m, n) => `${n} — key missing`],
    [/^(\d+) voix détectées?$/, (m, n) => `${n} ${n === '1' ? 'voice' : 'voices'} detected`],
    [/^(\d+) cartes? fusionnées? par le nom$/, (m, n) => `${n} ${n === '1' ? 'card' : 'cards'} merged by name`],
    [/^Ne montrer que les (\d+) principales$/, (m, n) => `Show only the ${n} main ones`],
    [/^Afficher les (\d+) voix$/, (m, n) => `Show all ${n} voices`],
    [/^Écouter la voix (\d+)$/, (m, n) => `Listen to voice ${n}`],
    [/^(\S+) de parole$/, (m, t) => `${t} of speech`],
    [/^(\d+) prises?$/, (m, n) => `${n} ${n === '1' ? 'turn' : 'turns'}`],
    [/^extraits pris à (.+)$/, (m, t) => `samples taken at ${t}`],
    [/^(\d+) correction\(s\) proposée\(s\)$/, (m, n) => `${n} suggested correction(s)`],
    [/^(\d+) correction\(s\) appliquée\(s\)$/, (m, n) => `${n} correction(s) applied`],
    [/^bloc (\d+)$/, (m, n) => `block ${n}`],
    [/^bloc (\d+) — « (.*) » (rendus au bloc précédent|passés au bloc suivant)$/, (m, n, w, s) => `block ${n} — “${w}” ${s.startsWith('rendus') ? 'given back to the previous block' : 'passed to the next block'}`],
    [/^Ajouter une clé (.+)$/, (m, n) => `Add a ${n} key`],
    [/^(.+) enregistré\.$/, (m, n) => `${n} saved.`],
    [/^(\S+) écoulées(?: — (.*))?$/, (m, t, eta) => `${t} elapsed` + (eta ? ' — ' + eta : '')],
    [/^plus d'une heure restante$/, () => `more than an hour left`], [/^moins d'une minute restante$/, () => `less than a minute left`],
    [/^encore (\d+) min environ$/, (m, n) => `about ${n} min left`],
    [/^encore (\d+) h (\d+) environ$/, (m, h, n) => `about ${h} h ${n} left`]
  ],
  parts: [
    [`Entraîné sur VoxCeleb, une centaine de nationalités. Rapide.`, `Trained on VoxCeleb, about a hundred nationalities. Fast.`],
    [`Même idée, autre équipe, affiné à marge large. Rapide.`, `Same idea, different team, tuned with a wide margin. Fast.`],
    [`Architecture différente : à essayer quand les CAM++ confondent deux voix.`, `Different architecture: try it when the CAM++ models confuse two voices.`],
    [`Encore une autre architecture, sur les mêmes données.`, `Yet another architecture, on the same data.`],
    [`Anglais uniquement, mais réputé solide. Lent et lourd.`, `English only, but known to be solid. Slow and heavy.`],
    [`Version légère du précédent.`, `Lightweight version of the previous one.`],
    [`L'ancien réglage par défaut. Correct en anglais, jamais pensé pour le français.`, `The former default. Fine in English, never designed for French.`],
    [`Mandarin uniquement. Trois fois plus lent, sans avantage hors chinois.`, `Mandarin only. Three times slower, with no advantage outside Chinese.`],
    [`Mandarin, sur des enregistrements variés.`, `Mandarin, on varied recordings.`],
    [`Enlève le souffle sans toucher au timbre. C'est ce qui a donné la meilleure séparation dans nos mesures, et c'est presque instantané.`, `Removes hiss without touching the voice's character. It gave the best separation in our measurements, and it is almost instant.`],
    [`Nettoie beaucoup plus, mais a fait disparaître une voix sur trois dans notre enregistrement d'essai. À réserver à un son très dégradé, et à vérifier en écoutant les extraits.`, `Cleans much more, but made one voice in three disappear in our test recording. Keep it for very poor audio, and check by listening to the samples.`],
    [`Encore plus agressif, avec le même risque de confondre deux personnes. Deux fois plus lent que le précédent.`, `Even more aggressive, with the same risk of merging two people. Twice as slow as the previous one.`],
    [`Le plus capable. Voit la réunion entière d'un coup.`, `The most capable. Sees the whole meeting at once.`],
    [`Deux fois moins cher qu'Opus, même contexte.`, `Half the price of Opus, same context.`],
    [`Quelques centimes par réunion.`, `A few cents per meeting.`],
    [`Gratuit, et voit la réunion entière d'un coup. Peu de requêtes par jour, ce qui suffit largement.`, `Free, and sees the whole meeting at once. Few requests per day, which is plenty.`],
    [`Plus de requêtes par jour, un peu moins fin.`, `More requests per day, slightly less fine-grained.`],
    [`Gratuit, par tranches de dix blocs. Quota quotidien.`, `Free, in slices of ten blocks. Daily quota.`],
    [`Gratuit et rapide, un peu moins sûr.`, `Free and fast, slightly less reliable.`],
    [/\bMultilingue\b/g, 'Multilingual'], [/\bAnglais\b/g, 'English'], [/\bChinois\b/g, 'Chinese'], [/\banglais\b/g, 'English'],
    ['(grand)', '(large)'], ['(petit)', '(small)'], [/\bTrès fort\b/g, 'Very strong'], [/\bFort\b/g, 'Strong'], [/\bLéger\b/g, 'Light'],
    [/\(gratuite?\)/g, '(free)'], [/ Environ (\d+[.,]\d)× le temps de calcul du plus rapide\./g, ' About $1× the compute time of the fastest.'],
    [' Le téléchargement se fera au lancement, une seule fois.', ' The download happens at launch, once only.'],
    [/ Compter environ une minute de calcul par (\d+) minutes d'enregistrement\./g, ' Allow about one minute of processing per $1 minutes of recording.'],
    [/Environ (\d+) 000 jetons pour (\d+) blocs?\./g, 'About $1,000 tokens for $2 blocks.'],
    [` Facturé à l'usage : quelques dizaines de centimes.`, ` Billed by use: a few tens of cents.`],
    [` Modèle gratuit, soumis à un quota quotidien — s'il est épuisé, en choisir un autre dans la liste.`, ` Free model with a daily quota. If it runs out, pick another one from the list.`]
  ]
});
vm.lang.onChange(() => { if (typeof job !== 'undefined' && job && job.status === 'done') render(); });
vm.lang.enable({ default: 'fr' });
