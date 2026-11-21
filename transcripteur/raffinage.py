"""
Raffiner la séparation des voix.

La séparation de base regroupe les empreintes vocales en un seul passage.
Une erreur de départ — deux personnes fondues en une, une interjection de
deux secondes attribuée au hasard — reste dans le résultat. Ici on fait
l'inverse, dans l'ordre où une personne s'y prendrait :

  1. Calculer l'empreinte de chaque extrait.
  2. Ne retenir d'abord que les extraits longs : seuls ils portent une
     empreinte fiable. Les regrouper entre eux.
  3. Faire un profil par voix (la moyenne de ses extraits).
  4. Classer ensuite tout le reste — les extraits courts compris — sur ces
     profils. Un extrait court dont le rattachement est incertain prend la
     voix de son voisin plutôt qu'une voix au hasard.
  5. Recalculer les profils avec ce qu'on vient de classer, et recommencer.

Le nombre de voix donné par la personne prime. Sinon il est cherché dans
l'écart entre les fusions du regroupement : tant que deux groupes se
ressemblent à peu près autant que les précédents, on les fusionne ; au
premier grand saut, ce sont deux personnes.

Rend les mêmes « tours » que la séparation de base, pour que le reste du
programme n'ait rien à savoir de cette étape.
"""

from __future__ import annotations

from pathlib import Path

FEN = 5.0          # durée maximale d'un extrait, en secondes
MIN_SUR = 2.5      # un extrait de cette durée ou plus porte une empreinte fiable
MIN_COURT = 0.6    # en dessous, on ne calcule pas d'empreinte
VOIX_MAX = 8
PART_MIN = 0.03    # une voix qui parle moins que cela de la durée est du bruit
MARGE = 0.06       # écart minimal entre le meilleur profil et le suivant


def _unites(tours, duree_audio):
    """Découpe les tours en extraits de FEN secondes au plus."""
    u = []
    for i, (a, b, _) in enumerate(tours):
        t = a
        while t < b - 1e-6:
            fin = min(b, t + FEN)
            if b - fin < MIN_COURT and fin < b:     # ne laisse pas de miette
                fin = b
            u.append((t, fin, i))
            t = fin
    return u


def _empreintes(audio, unites, extracteur, avance):
    import numpy as np
    sr = 16000
    sortie = []
    n = len(unites)
    for k, (a, b, _) in enumerate(unites):
        if b - a < MIN_COURT:
            sortie.append(None)
        else:
            s = extracteur.create_stream()
            s.accept_waveform(sample_rate=sr, waveform=audio[int(a * sr):int(b * sr)])
            s.input_finished()
            e = np.array(extracteur.compute(s), dtype=np.float32)
            nrm = np.linalg.norm(e)
            sortie.append(e / nrm if nrm > 0 else None)
        if avance and k % 25 == 0:
            avance(k / n)
    return sortie


def _agglomerer(E, poids, cible):
    """Regroupement hiérarchique, liaison moyenne, similarité cosinus.

    Rend (étiquettes, sauts). `sauts` = similarité de chaque fusion, dans
    l'ordre. Si `cible` est donné, on s'arrête à ce nombre de groupes."""
    import numpy as np
    n = len(E)
    groupes = [[i] for i in range(n)]
    S = E @ E.T
    moy = S.copy()                      # similarité moyenne entre groupes
    actifs = list(range(n))
    taille = [1.0] * n
    sauts = []
    while len(actifs) > 1:
        if cible and len(actifs) <= cible:
            break
        sous = moy[np.ix_(actifs, actifs)].copy()
        np.fill_diagonal(sous, -2)
        k = int(np.argmax(sous))
        i, j = actifs[k // len(actifs)], actifs[k % len(actifs)]
        sauts.append(float(moy[i, j]))
        ti, tj = taille[i], taille[j]
        for m in actifs:
            if m not in (i, j):
                moy[i, m] = moy[m, i] = (moy[i, m] * ti + moy[j, m] * tj) / (ti + tj)
        taille[i] = ti + tj
        groupes[i] += groupes[j]
        actifs.remove(j)
    etiq = np.zeros(n, dtype=int)
    for g, i in enumerate(actifs):
        for m in groupes[i]:
            etiq[m] = g
    return etiq, sauts


def _nombre_de_voix(sauts, n):
    """Le nombre de groupes au plus grand écart de similarité entre fusions.

    `sauts` va des fusions les plus sûres aux plus douteuses. Entre deux
    extraits de la même personne la similarité reste haute (0,85 et plus
    sur les modèles essayés) ; entre personnes différentes elle tombe.
    La chute la plus brutale marque ce passage."""
    import numpy as np
    if n <= 1 or not sauts:
        return max(1, n)
    s = np.array(sauts)
    if len(s) == 1:
        return 1 if s[0] > 0.75 else 2
    chutes = s[:-1] - s[1:]
    debut = max(0, len(chutes) - (VOIX_MAX - 1))
    k = debut + int(np.argmax(chutes[debut:]))
    if chutes[k] < 0.06:                # aucun vrai écart
        return 1 if s[-1] > 0.75 else 2
    return int(min(max(n - (k + 1), 1), VOIX_MAX))


def raffiner(audio, tours, extracteur, nombre=-1, avance=None, dire=None,
             confiances=None):
    """Raffine des tours (début, fin, étiquette). Rend la même forme.

    Si `confiances` est une liste, elle reçoit un niveau de confiance de 0 à 1
    par tour rendu (voir `_niveau_conf`)."""
    import numpy as np
    if not tours:
        return tours
    dire = dire or (lambda m: None)
    duree = len(audio) / 16000
    unites = _unites(tours, duree)
    dire(f"raffinage : {len(tours)} tours découpés en {len(unites)} extraits "
         f"de {FEN:.0f} s au plus ; calcul de l'empreinte vocale de chacun")
    quart = [0]

    def progres(r):
        if avance:
            avance(r * 0.8)
        if int(r * 4) > quart[0] and r < 1:
            quart[0] = int(r * 4)
            dire(f"empreintes : {int(r * len(unites))} / {len(unites)} extraits")
    emp = _empreintes(audio, unites, extracteur, progres)
    ok = [k for k, e in enumerate(emp) if e is not None]
    if len(ok) < 2:
        return tours

    dur = np.array([u[1] - u[0] for u in unites])
    sur = [k for k in ok if dur[k] >= MIN_SUR]
    if len(sur) < max(4, nombre if nombre and nombre > 0 else 2) :
        sur = sorted(ok, key=lambda k: -dur[k])[:max(8, len(ok) // 3)]

    # Au plus 400 extraits sûrs, répartis dans le temps : le regroupement
    # est quadratique, et 400 suffisent à fixer les profils.
    if len(sur) > 400:
        pas = len(sur) / 400
        sur = [sur[int(i * pas)] for i in range(400)]

    dire(f"{len(ok)} extraits mesurés ; {len(sur)} extraits longs et sûrs "
         f"(≥ {MIN_SUR} s) retenus pour fixer les voix")
    E = np.stack([emp[k] for k in sur])
    cible = nombre if nombre and nombre > 0 else None
    etiq, sauts = _agglomerer(E, dur[sur], cible)
    if not cible:
        cible = _nombre_de_voix(sauts, len(sur))
        etiq, _ = _agglomerer(E, dur[sur], cible)
    dire(f"regroupement des extraits sûrs : {cible} voix "
         + ("(nombre imposé)" if nombre and nombre > 0 else "(nombre estimé d'après l'écart de ressemblance)"))
    if avance:
        avance(0.85)

    def profils(selection, labels):
        P = []
        for g in sorted(set(labels)):
            idx = [selection[i] for i, l in enumerate(labels) if l == g]
            p = sum(emp[k] * dur[k] for k in idx)
            P.append(p / np.linalg.norm(p))
        return np.stack(P)

    P = profils(sur, list(etiq))

    def classer(P):
        return _classer(P, emp, ok, dur)

    lab, conf = classer(P)
    dire(f"profils de {len(P)} voix construits ; classement des {len(ok)} extraits")
    for passe in range(2):              # raffinage : profils recalculés
        surs = [k for k in ok if lab[k] >= 0 and (dur[k] >= MIN_SUR or conf[k] >= MARGE)]
        if len(set(lab[k] for k in surs)) < 2 and cible and cible > 1:
            break
        P = profils(surs, [lab[k] for k in surs])
        lab, conf = classer(P)
        dire(f"reclassement, passe {passe + 1}/2 : {len(set(l for l in lab if l >= 0))} voix, "
             f"{sum(1 for k in ok if conf[k] < MARGE)} extraits encore incertains")
    if avance:
        avance(0.95)

    # Une voix qui parle à peine n'en est pas une, sauf si on a annoncé le nombre.
    if not (nombre and nombre > 0):
        total = sum(dur)
        parts = {g: sum(dur[k] for k in range(len(unites)) if lab[k] == g) / total
                 for g in set(lab) if g >= 0}
        petits = [g for g, p in parts.items() if p < PART_MIN]
        if petits and len(parts) > 1:
            grands = [g for g in parts if g not in petits]
            if grands:
                for k in range(len(unites)):
                    if lab[k] in petits:
                        s = P @ emp[k] if emp[k] is not None else None
                        lab[k] = grands[int(np.argmax([s[g] for g in grands]))] if s is not None else grands[0]

    # Reconstruction : on rassemble les extraits consécutifs de même voix.
    sortie, confs, nom, classement = _reconstruire(unites, lab, conf, dur)
    if confiances is not None:
        confiances.extend(confs)
    if avance:
        avance(1.0)
    dire(f"raffinage terminé : {len(classement)} voix, {len(sortie)} tours "
         f"(séparation de base : {len({t[2] for t in tours})} voix, {len(tours)} tours)")
    return sortie


def _niveau_conf(marge: float) -> float:
    """Écart de ressemblance entre la meilleure voix et la suivante, ramené à 0–1.

    Un écart de 0,2 ou plus vaut 1. C'est une mesure d'ambiguïté, pas une
    probabilité : elle dit « ce passage ressemble nettement à une seule voix »
    ou « il hésite entre deux », sans garantir que la voix retenue est la bonne."""
    return max(0.0, min(1.0, marge / 0.2))


def _classer(P, emp, ok, dur):
    """Classe chaque extrait sur le profil le plus proche. Rend (étiquettes, écarts)."""
    import numpy as np
    n = len(emp)
    lab = [-1] * n
    conf = [0.0] * n
    for k in ok:
        s = P @ emp[k]
        o = np.argsort(-s)
        marge = s[o[0]] - (s[o[1]] if len(o) > 1 else -1)
        lab[k], conf[k] = int(o[0]), float(marge)
    # Un extrait court et douteux prend la voix du voisin.
    for k in range(n):
        douteux = lab[k] < 0 or (dur[k] < MIN_SUR and conf[k] < MARGE)
        if douteux:
            for d in range(1, n):
                for v in (k - d, k + d):
                    if 0 <= v < n and lab[v] >= 0 and not (
                            dur[v] < MIN_SUR and conf[v] < MARGE):
                        lab[k] = lab[v]
                        break
                else:
                    continue
                break
    return lab, conf


def _reconstruire(unites, lab, conf, dur):
    """Rassemble les extraits consécutifs de même voix.

    Rend (tours, confiances, nom_par_étiquette, étiquettes_par_temps_de_parole)."""
    temps = {}
    for k in range(len(unites)):
        temps[lab[k]] = temps.get(lab[k], 0.0) + dur[k]
    classement = sorted(temps, key=lambda g: -temps[g])
    nom = {g: f"SPEAKER_{r:02d}" for r, g in enumerate(classement)}
    sortie, cs, ds = [], [], []
    for k, (a, b, _) in enumerate(unites):
        etiquette = nom[lab[k]]
        c = conf[k] * dur[k]
        if sortie and sortie[-1][2] == etiquette and a - sortie[-1][1] <= 0.5:
            sortie[-1][1] = b
            cs[-1] += c
            ds[-1] += dur[k]
        else:
            sortie.append([a, b, etiquette])
            cs.append(c)
            ds.append(dur[k])
    confs = [_niveau_conf(cs[i] / max(ds[i], 1e-6)) for i in range(len(sortie))]
    return [tuple(t) for t in sortie], confs, nom, classement


def raffiner_guide(audio, tours, extracteur, graines, avance=None, dire=None,
                   controle=None, forts=None, cache=None):
    """Raffine d'après des exemples donnés par la personne.

    `graines` : {étiquette: [(début, fin), ...]} — des passages dont la
    personne a dit qui parle. Les profils viennent de ces exemples seulement,
    pas d'un regroupement calculé. Tout le reste est classé sur eux.

    Un exemple qui ne ressemble pas aux autres de la même étiquette — un
    extrait qui mélange deux voix, ou un même nom donné à deux personnes — est
    écarté et signalé, plutôt que de fausser le profil.

    `forts` : les exemples que la personne a désignés elle-même — jamais
    écartés. `cache` : fichier où garder les empreintes. Les calculer prend
    des minutes ; une fois gardées, ajouter un exemple et recalculer le
    classement prend quelques secondes, ce qui rend possible d'ajuster à
    petits coups. Les extraits (leurs bornes) sont ceux du premier calcul.

    Rend (tours, confiances, etiquette_par_voix, rapport). `controle` est
    appelé régulièrement et peut lever pour interrompre."""
    import numpy as np
    dire = dire or (lambda m: None)
    controle = controle or (lambda: None)
    forts = forts or {}
    unites, emp = None, None
    if cache is not None and Path(cache).exists():
        try:
            d = np.load(cache, allow_pickle=False)
            unites = [(float(x), float(y), 0) for x, y in zip(d["a"], d["b"])]
            emp = [d["emb"][i] if d["valide"][i] else None for i in range(len(unites))]
            dire(f"empreintes retrouvées en mémoire : {len(unites)} extraits, aucun recalcul")
        except Exception:  # noqa: BLE001
            unites, emp = None, None
    if unites is None:
        unites = _unites(tours, len(audio) / 16000)
        dire(f"raffinage guidé : {len(tours)} passages découpés en {len(unites)} extraits ; "
             f"calcul de l'empreinte vocale de chacun")
        quart = [0]

        def progres(r):
            controle()
            if avance:
                avance(r * 0.8)
            if int(r * 4) > quart[0] and r < 1:
                quart[0] = int(r * 4)
                dire(f"empreintes : {int(r * len(unites))} / {len(unites)} extraits")
        emp = _empreintes(audio, unites, extracteur, progres)
        if cache is not None:
            try:
                dim = next(e for e in emp if e is not None).shape[0]
                np.savez(cache, a=np.array([u[0] for u in unites]), b=np.array([u[1] for u in unites]),
                         emb=np.stack([e if e is not None else np.zeros(dim, dtype=np.float32) for e in emp]),
                         valide=np.array([e is not None for e in emp]))
            except Exception:  # noqa: BLE001
                pass
    ok = [k for k, e in enumerate(emp) if e is not None]
    dur = np.array([u[1] - u[0] for u in unites])
    if len(ok) < 2:
        raise ValueError("Pas assez de parole exploitable pour calculer les voix.")

    def couvert(k, intervalles):
        a, b, _ = unites[k]
        return sum(max(0.0, min(b, y) - max(a, x)) for x, y in intervalles) / (b - a)

    etiquettes, amorces, rapport = [], [], {"ecartes": {}, "sans_exemple": []}
    for nom in sorted(graines):
        idx = [k for k in ok if couvert(k, graines[nom]) >= 0.6]
        if not idx:
            rapport["sans_exemple"].append(nom)
            dire(f"« {nom} » : aucun extrait exploitable parmi les exemples, ignoré")
            continue
        if len(idx) >= 3:
            c = sum(emp[k] * dur[k] for k in idx)
            c = c / np.linalg.norm(c)
            sims = np.array([float(emp[k] @ c) for k in idx])
            protege = {k for k in idx if forts.get(nom) and couvert(k, forts[nom]) >= 0.6}
            garde = [k for k, v in zip(idx, sims)
                     if k in protege or v >= max(float(np.median(sims)) - 0.2, 0.25)]
            if len(garde) >= 2 and len(garde) < len(idx):
                rapport["ecartes"][nom] = len(idx) - len(garde)
                dire(f"« {nom} » : {len(idx) - len(garde)} extraits écartés parce qu'ils ne "
                     f"ressemblent pas aux autres (voix mélangées, ou même nom donné à deux personnes ?)")
                idx = garde
        etiquettes.append(nom)
        amorces.append(idx)
        dire(f"« {nom} » : {len(idx)} extraits d'exemple retenus")
    if len(etiquettes) < 2:
        raise ValueError("Il faut au moins deux personnes avec des exemples pour raffiner.")

    def profils(groupes):
        return np.stack([_unit(sum(emp[k] * dur[k] for k in g)) for g in groupes])

    fixe = {}
    for i, g in enumerate(amorces):
        for k in g:
            fixe[k] = i
    P = profils(amorces)
    if avance:
        avance(0.85)
    lab, conf = _classer(P, emp, ok, dur)
    for k, i in fixe.items():
        lab[k], conf[k] = i, 0.2
    dire(f"profils de {len(P)} personnes construits ; classement des {len(ok)} extraits")
    for passe in range(2):
        controle()
        groupes = [[] for _ in etiquettes]
        for k in ok:
            if k in fixe or (lab[k] >= 0 and (dur[k] >= MIN_SUR or conf[k] >= MARGE)):
                groupes[lab[k]].append(k)
        P = profils([g if g else amorces[i] for i, g in enumerate(groupes)])
        lab, conf = _classer(P, emp, ok, dur)
        for k, i in fixe.items():
            lab[k], conf[k] = i, 0.2
        dire(f"reclassement, passe {passe + 1}/2 : "
             f"{sum(1 for k in ok if conf[k] < MARGE)} extraits encore incertains")
    if avance:
        avance(0.95)

    sortie, confs, nom, classement = _reconstruire(unites, lab, conf, dur)
    etiquette_par_voix = {nom[g]: etiquettes[g] for g in classement if g >= 0}
    rapport["incertains"] = sum(1 for c in confs if c < 0.3)
    rapport["secondes_exemples"] = {etiquettes[i]: round(float(sum(dur[k] for k in g)), 1)
                                    for i, g in enumerate(amorces)}
    total_parole = float(sum(dur[k] for k in ok)) or 1.0
    rapport["part_incertaine"] = round(float(sum(dur[k] for k in ok if conf[k] < MARGE)) / total_parole, 3)
    if avance:
        avance(1.0)
    dire(f"raffinage guidé terminé : {len(classement)} voix, {len(sortie)} passages, "
         f"{rapport['incertains']} encore incertains")
    return sortie, confs, etiquette_par_voix, rapport


def _unit(v):
    import numpy as np
    return v / np.linalg.norm(v)
