/* Le Worker du site : deux pages statiques, et les téléchargements.
 *
 * Les boutons pointent sur /telecharger/<plateforme> et non sur GitHub.
 * Quelqu'un qui n'est pas développeur, envoyé sur une page de versions,
 * y trouve une liste de fichiers pour tous les systèmes, des sommes de
 * contrôle et une interface en anglais ; il en conclut qu'il s'est
 * trompé d'endroit, et il a raison.
 *
 * Pour l'instant ces chemins redirigent vers le fichier du dépôt — pas
 * vers la page de versions, vers le fichier même, qui se télécharge
 * sans rien afficher. Le jour où les paquets vivront sur R2, seule la
 * table ci-dessous change ; les adresses publiques, elles, ne bougent
 * pas, et les liens déjà envoyés par courriel continuent de marcher.
 */

const DEPOT = 'msolav/transcription';

const PAQUETS = {
  'mac-silicon': 'Transcripteur-macOS-AppleSilicon.zip',
  'mac-intel': 'Transcripteur-macOS-Intel.zip',
  'windows': 'Transcripteur-Windows.zip',
  'linux': 'Transcripteur-Linux.zip',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const m = url.pathname.match(/^\/telecharger\/([a-z-]+)\/?$/);

    if (m) {
      const fichier = PAQUETS[m[1]];
      if (!fichier) {
        return new Response('Plateforme inconnue.', {
          status: 404, headers: { 'content-type': 'text/plain; charset=utf-8' },
        });
      }
      return Response.redirect(
        `https://github.com/${DEPOT}/releases/latest/download/${fichier}`, 302);
    }

    return env.ASSETS.fetch(request);
  },
};
