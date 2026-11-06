/* Le Worker du site : deux pages statiques, et les téléchargements.
 *
 * Les boutons pointent sur /telecharger/<plateforme>. Personne ne doit
 * atterrir sur une page de versions GitHub : liste de fichiers pour
 * tous les systèmes, sommes de contrôle, interface en anglais — on en
 * conclut qu'on s'est trompé d'endroit.
 *
 * Le fichier est relayé, jamais redirigé. Une redirection renvoyait
 * vers github.com, et tant que la version n'était pas publiée elle y
 * affichait « Not Found » sur fond noir, sans un mot ni retour
 * possible.
 *
 * D'où vient le fichier : de R2 s'il y est, du dépôt sinon — et dans
 * ce cas on le range dans R2 en passant. Pas d'étape de téléversement
 * dans la chaîne de construction, donc pas de clé d'accès à confier à
 * GitHub ; et le premier à télécharger une version nouvelle la dépose
 * pour les suivants. Si R2 tombe ou se vide, le dépôt reste derrière :
 * le téléchargement ralentit, il ne casse pas.
 */

const DEPOT = 'msolav/transcription';

const PAQUETS = {
  'mac-silicon': 'Transcripteur-macOS-AppleSilicon.zip',
  'mac-intel': 'Transcripteur-macOS-Intel.zip',
  'windows': 'Transcripteur-Windows.zip',
  'linux': 'Transcripteur-Linux.tar.gz',
};

const VERSION = 'v1.0';
const AMONT = (f) => `https://github.com/${DEPOT}/releases/download/${VERSION}/${f}`;

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

function entetes(fichier, taille, source) {
  const h = new Headers();
  h.set('content-type', 'application/octet-stream');
  h.set('content-disposition', `attachment; filename="${fichier}"`);
  if (taille) h.set('content-length', String(taille));
  h.set('cache-control', 'public, max-age=3600');
  h.set('x-source', source);          // pour savoir d'où il est venu
  return h;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const m = url.pathname.match(/^\/telecharger\/([a-z-]+)\/?$/);
    if (!m) return env.ASSETS.fetch(request);

    const fichier = PAQUETS[m[1]];
    if (!fichier) {
      return page('Plateforme inconnue',
        'Ce lien ne correspond à aucun système.', 404);
    }

    const cle = `${VERSION}/${fichier}`;

    // 1. R2, si le paquet y est déjà.
    if (env.PAQUETS) {
      try {
        const objet = await env.PAQUETS.get(cle);
        if (objet) {
          return new Response(objet.body,
            { headers: entetes(fichier, objet.size, 'r2') });
        }
      } catch (e) { /* on passera par le dépôt */ }
    }

    // 2. Sinon le dépôt.
    let amont;
    try {
      amont = await fetch(AMONT(fichier), {
        headers: { 'user-agent': 'transcripteur-site' },
        redirect: 'follow',
      });
    } catch (e) {
      return page('Téléchargement indisponible',
        'Le fichier n’a pas pu être récupéré. Réessayer dans un moment.', 502);
    }
    if (!amont.ok || !amont.body) {
      return page('Pas encore disponible',
        'Le paquet pour ce système n’est pas encore publié. '
        + 'Il arrivera à la prochaine version.', 404);
    }

    const taille = amont.headers.get('content-length');

    // 3. Et on le range au passage, sans faire attendre qui télécharge :
    //    le flux est dédoublé, une moitié part vers le navigateur,
    //    l'autre vers R2. La taille est donnée à put() — sans elle, un
    //    flux interrompu déposerait un fichier tronqué, que les
    //    suivants téléchargeraient en croyant l'avoir en entier.
    if (env.PAQUETS && taille) {
      const [pourVous, pourR2] = amont.body.tee();
      ctx.waitUntil(
        env.PAQUETS.put(cle, pourR2, {
          httpMetadata: { contentType: 'application/octet-stream' },
        }).catch(() => {}));
      return new Response(pourVous,
        { headers: entetes(fichier, taille, 'amont-rangé') });
    }

    return new Response(amont.body,
      { headers: entetes(fichier, taille, 'amont') });
  },
};
