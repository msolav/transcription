/* Le Worker du site : deux pages statiques, et les téléchargements.
 *
 * Les boutons pointent sur /telecharger/<plateforme>. Personne ne doit
 * atterrir sur une page de versions GitHub : liste de fichiers pour
 * tous les systèmes, sommes de contrôle, interface en anglais — on en
 * conclut qu'on s'est trompé d'endroit.
 *
 * Le fichier est relayé, pas redirigé. Une redirection renvoyait vers
 * github.com, et quand la version n'était pas encore publiée elle y
 * affichait « Not Found » sur fond noir, sans un mot d'explication et
 * sans retour possible. Ici l'adresse reste la nôtre, et l'absence de
 * version se dit dans une phrase.
 *
 * Le jour où les paquets vivront sur R2, seule ORIGINE change.
 */

const DEPOT = 'msolav/transcription';

const PAQUETS = {
  'mac-silicon': 'Transcripteur-macOS-AppleSilicon.zip',
  'mac-intel': 'Transcripteur-macOS-Intel.zip',
  'windows': 'Transcripteur-Windows.zip',
  'linux': 'Transcripteur-Linux.tar.gz',
};

const ORIGINE = (fichier) =>
  `https://github.com/${DEPOT}/releases/latest/download/${fichier}`;

function page(titre, texte, code) {
  return new Response(
    `<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${titre}</title>
<style>body{margin:0;min-height:100svh;display:grid;place-items:center;
padding:2rem;background:#f1efe9;color:#0c0c0b;font:16px/1.5 system-ui,sans-serif;
text-align:center}@media(prefers-color-scheme:dark){body{background:#0c0c0b;
color:#f1efe9}}h1{font-size:1.6rem;margin:0 0 .6rem}p{margin:0 0 1.2rem;
max-width:32rem;color:#6b6a65}a{color:inherit}</style>
<div><h1>${titre}</h1><p>${texte}</p><p><a href="/">Retour</a></p></div>`,
    { status: code, headers: { 'content-type': 'text/html; charset=utf-8' } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const m = url.pathname.match(/^\/telecharger\/([a-z-]+)\/?$/);
    if (!m) return env.ASSETS.fetch(request);

    const fichier = PAQUETS[m[1]];
    if (!fichier) {
      return page('Plateforme inconnue',
        'Ce lien ne correspond à aucun système.', 404);
    }

    let amont;
    try {
      amont = await fetch(ORIGINE(fichier), {
        headers: { 'user-agent': 'transcripteur-site' },
        redirect: 'follow',
      });
    } catch (e) {
      return page('Téléchargement indisponible',
        'Le fichier n’a pas pu être récupéré. Réessayer dans un moment.', 502);
    }

    if (!amont.ok) {
      return page('Pas encore disponible',
        `Le paquet pour ce système n’est pas encore publié. `
        + `Il arrivera à la prochaine version.`, 404);
    }

    // On réécrit les en-têtes : le nom du fichier doit être lisible
    // dans le dossier de téléchargements, et la taille connue pour que
    // le navigateur affiche une progression plutôt qu'un compteur fou.
    const entetes = new Headers();
    entetes.set('content-type', 'application/octet-stream');
    entetes.set('content-disposition', `attachment; filename="${fichier}"`);
    const taille = amont.headers.get('content-length');
    if (taille) entetes.set('content-length', taille);
    entetes.set('cache-control', 'public, max-age=3600');

    return new Response(amont.body, { status: 200, headers: entetes });
  },
};
