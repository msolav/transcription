"""
Identifier les voix avant l'analyse, d'après des échantillons de la personne.

La séparation automatique regroupe les voix d'abord et demande ensuite de
nommer les groupes — qui sont alors déjà mélangés. Ici c'est l'inverse :

  1. On découpe la parole (d'après les mots horodatés) en passages de quelques
     secondes, et on calcule l'empreinte vocale de chacun. C'est rapide (quelques
     minutes), contrairement à la séparation complète.
  2. On propose à la personne quelques passages bien choisis — d'abord des
     passages très différents les uns des autres, pour que chaque voix ait une
     chance d'apparaître — et elle dit qui parle. Elle peut couper un passage où
     plusieurs personnes parlent. De nouvelles personnes s'ajoutent au fil de l'eau.
  3. Les empreintes des passages désignés fixent un profil par personne ; tout le
     reste est classé sur ces profils. On propose ensuite les passages les plus
     incertains, et on mesure ce qui reste d'incertain pour dire quand s'arrêter.

Les empreintes sont gardées dans la séance : proposer la suite d'après un nouvel
exemple prend quelques secondes.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

SR = 16000
PAUSE = 0.6        # silence qui coupe un passage
MIN_PASSAGE = 2.5  # un passage ne se coupe pas avant cette durée
MAX_PASSAGE = 7.0  # durée maximale d'un passage
MIN_EMPREINTE = 0.8
MARGE = 0.06       # écart sous lequel un passage hésite entre deux voix
LOT = 4            # plages proposées à la fois
PLAGE_MAX = 60.0   # durée maximale d'une plage proposée (assez pour un profil solide en un seul geste)
PLAGE_ECART = 4.0  # silence au-delà duquel une plage s'arrête
FEN = 2.0          # fenêtre d'empreinte fine (secondes) : assez courte pour voir un changement de voix
PAS_FEN = 2.0      # pas entre deux fenêtres (mesuré : 2 s coûte moitié moins qu’1 s, pour une pureté équivalente)
RABOT = 0.5        # on rogne autant aux deux bouts d'une plage : la fenêtre de bord peut déborder sur une autre voix

_extracteurs: dict = {}


def decouper(mots: list[dict]) -> list[dict]:
    """Passages de parole : (début, fin, texte), d'après les pauses entre mots."""
    passages: list[dict] = []
    cur: list[dict] = []
    for m in mots:
        if cur:
            pause = m["start"] - cur[-1]["end"]
            long = cur[-1]["end"] - cur[0]["start"]
            if (pause >= PAUSE and long >= MIN_PASSAGE) or long >= MAX_PASSAGE:
                passages.append({"start": cur[0]["start"], "end": cur[-1]["end"], "mots": cur})
                cur = []
        cur.append(m)
    if cur:
        passages.append({"start": cur[0]["start"], "end": cur[-1]["end"], "mots": cur})
    # un passage trop court rejoint le précédent
    fusion: list[dict] = []
    for p in passages:
        if fusion and p["end"] - p["start"] < 1.0 and p["start"] - fusion[-1]["end"] < 1.0:
            fusion[-1]["end"] = p["end"]
            fusion[-1]["mots"] += p["mots"]
        else:
            fusion.append(p)
    return fusion


def _extracteur(modele: str, fils: int = 2):
    import sherpa_onnx
    if modele not in _extracteurs:
        _extracteurs[modele] = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=modele, num_threads=fils))
    return _extracteurs[modele]


def _empreinte(extracteur, samples):
    import numpy as np
    s = extracteur.create_stream()
    s.accept_waveform(sample_rate=SR, waveform=samples)
    s.input_finished()
    e = np.array(extracteur.compute(s), dtype=np.float32)
    n = float(np.linalg.norm(e))
    return e / n if n > 0 else None


def lire_wav(chemin: Path, a: float, b: float):
    """Un extrait du fichier audio converti, sans le charger en entier."""
    import numpy as np
    with wave.open(str(chemin), "rb") as w:
        w.setpos(max(0, int(a * SR)))
        brut = w.readframes(max(1, int((b - a) * SR)))
    return np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0


def preparer(wav: Path, mots: list[dict], modele: str, dossier: Path,
             avance=None, dire=None, controle=None) -> int:
    """Découpe la parole et garde l'empreinte de chaque passage. Rend leur nombre."""
    import numpy as np
    dire = dire or (lambda m: None)
    controle = controle or (lambda: None)
    passages = decouper(mots)
    dire(f"parole découpée en {len(passages)} passages ; calcul de l'empreinte vocale de chacun")
    ext = _extracteur(modele, 4)
    emb, valide = [], []
    n = len(passages)
    part = (lambda f: avance(0.55 * f)) if avance else None
    with wave.open(str(wav), "rb") as w:
        for k, p in enumerate(passages):
            if k % 20 == 0:
                controle()
                if part:
                    part(k / max(n, 1))
                if k and k % max(1, n // 4) == 0:
                    dire(f"empreintes : {k} / {n} passages")
            if p["end"] - p["start"] < MIN_EMPREINTE:
                emb.append(None)
                valide.append(False)
                continue
            w.setpos(int(p["start"] * SR))
            brut = w.readframes(int((p["end"] - p["start"]) * SR))
            e = _empreinte(ext, np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0)
            emb.append(e)
            valide.append(e is not None)
    dim = next((e.shape[0] for e in emb if e is not None), 0)
    dire(f"{sum(valide)} empreintes de passages ; empreintes fines pour repérer les plages d'une seule voix")
    fa, fb, fz, fok = fenetres(wav, mots, modele,
                               (lambda f: avance(0.55 + 0.45 * f)) if avance else None, dire, controle)
    np.savez(dossier / "enrolement.npz",
             a=np.array([p["start"] for p in passages]), b=np.array([p["end"] for p in passages]),
             emb=np.stack([e if e is not None else np.zeros(dim, dtype=np.float32) for e in emb]),
             valide=np.array(valide), fa=fa, fb=fb, fz=fz, fok=fok)
    (dossier / "enrolement.json").write_text(json.dumps({
        "modele": modele,
        "textes": [" ".join(m["text"].strip() for m in p["mots"]).strip() for p in passages],
    }, ensure_ascii=False), encoding="utf-8")
    if avance:
        avance(1.0)
    dire(f"{sum(valide)} empreintes exploitables sur {n} passages")
    return n


def _paroles(mots: list[dict], ecart: float = 1.0) -> list[tuple[float, float]]:
    """Suites de mots séparés de moins d'`ecart` secondes : là où quelqu'un parle."""
    spans: list[list[float]] = []
    for m in mots:
        if spans and m["start"] - spans[-1][1] < ecart:
            spans[-1][1] = max(spans[-1][1], m["end"])
        else:
            spans.append([m["start"], m["end"]])
    return [(a, b) for a, b in spans if b - a >= 1.0]


def fenetres(wav: Path, mots: list[dict], modele: str, avance=None, dire=None, controle=None):
    """Empreinte de fenêtres de 2 s (pas de 1 s) sur toute la parole.

    Les passages entiers (jusqu'à 7 s) enjambent souvent un changement de voix ; c'est
    à cette échelle plus fine qu'on voit où une voix s'arrête. Rend (débuts, fins, empreintes)."""
    import numpy as np
    controle = controle or (lambda: None)
    dire = dire or (lambda m: None)
    bornes: list[tuple[float, float]] = []
    for a, b in _paroles(mots):
        if b - a < FEN:
            bornes.append((a, b))
            continue
        t = a
        while t + FEN <= b + 1e-6:
            bornes.append((t, t + FEN))
            t += PAS_FEN
        if bornes[-1][1] < b - 0.4:
            bornes.append((b - FEN, b))
    ext = _extracteur(modele, 4)
    emb, ok = [], []
    n = len(bornes)
    dire(f"{n} fenêtres de {FEN:.0f} s pour repérer les changements de voix")
    with wave.open(str(wav), "rb") as w:
        for i, (a, b) in enumerate(bornes):
            if i % 40 == 0:
                controle()
                if avance:
                    avance(i / max(n, 1))
            w.setpos(int(a * SR))
            brut = w.readframes(int((b - a) * SR))
            e = _empreinte(ext, np.frombuffer(brut, dtype=np.int16).astype(np.float32) / 32768.0)
            emb.append(e)
            ok.append(e is not None)
    dim = next((e.shape[0] for e in emb if e is not None), 0)
    return (np.array([a for a, _ in bornes]), np.array([b for _, b in bornes]),
            np.stack([e if e is not None else np.zeros(dim, dtype=np.float32) for e in emb]),
            np.array(ok))


def seuil_fenetres(F: dict, paires: int = 6000) -> float:
    """Ressemblance qui sépare « même voix » de « voix différente », sans aucune étiquette.

    On tire des paires de fenêtres éloignées l'une de l'autre : dans une réunion à
    plusieurs voix, leur ressemblance a deux masses, l'une haute (même personne), l'autre
    basse. Le seuil d'Otsu tombe dans la vallée qui les sépare. On y ajoute une marge
    qui privilégie la pureté : mieux vaut une plage plus courte qu'une plage mêlée."""
    import numpy as np
    idx = [i for i in range(len(F["fa"])) if F["fok"][i]]
    if len(idx) < 40:
        return 0.6
    rng = np.random.default_rng(1)
    sims = []
    for _ in range(paires):
        i, j = rng.choice(idx, 2, replace=False)
        if abs(F["fa"][i] - F["fa"][j]) >= 3.0:
            sims.append(float(F["fz"][i] @ F["fz"][j]))
    h, bords = np.histogram(sims, bins=60, range=(-0.2, 1.0))
    h = h.astype(float)
    centres = (bords[:-1] + bords[1:]) / 2
    meilleur, seuil = -1.0, 0.6
    for k in range(5, 55):
        w0, w1 = h[:k].sum(), h[k:].sum()
        if w0 < 20 or w1 < 20:
            continue
        m0 = (h[:k] * centres[:k]).sum() / w0
        m1 = (h[k:] * centres[k:]).sum() / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > meilleur:
            meilleur, seuil = v, float(centres[k])
    return min(0.9, max(0.4, seuil + 0.05))


def plages_fines(F: dict, tau: float, exclus: list[tuple[float, float]] | None = None) -> list[dict]:
    """Les plus longues suites de fenêtres qui ont toutes l'air de la même voix.

    Une fenêtre rejoint la plage si sa ressemblance au profil moyen de la plage atteint
    `tau`. Les fenêtres tombant dans une zone `exclus` (déjà montrée ou nommée) ou sans
    empreinte coupent la plage. Chaque bout est rogné de RABOT secondes, et une plage
    s'arrête à PLAGE_MAX."""
    import numpy as np
    exclus = exclus or []
    n = len(F["fa"])
    sorties: list[dict] = []
    cur = None

    def dedans(t):
        return any(a <= t <= b for a, b in exclus)

    def clore():
        nonlocal cur
        if cur is None:
            return
        ks = cur["ks"]
        a, b = float(F["fa"][ks[0]]) + RABOT, float(F["fb"][ks[-1]]) - RABOT
        if b - a >= 3.0:
            c = cur["somme"] / np.linalg.norm(cur["somme"])
            sims = [float(F["fz"][k] @ c) for k in ks]
            sorties.append({"fk": ks, "start": a, "end": b, "centre": c, "dur": b - a, "pire": min(sims)})
        cur = None

    for k in range(n):
        if not F["fok"][k] or dedans((F["fa"][k] + F["fb"][k]) / 2):
            clore()
            continue
        if cur is not None:
            ecart = float(F["fa"][k] - F["fb"][cur["ks"][-1]])
            c = cur["somme"] / np.linalg.norm(cur["somme"])
            if (ecart <= PLAGE_ECART and float(F["fz"][k] @ c) >= tau
                    and float(F["fb"][k] - F["fa"][cur["ks"][0]]) <= PLAGE_MAX):
                cur["ks"].append(k)
                cur["somme"] = cur["somme"] + F["fz"][k]
                continue
            clore()
        cur = {"ks": [k], "somme": F["fz"][k].copy()}
    clore()
    return sorties


def seuil_meme_voix(E: dict) -> float:
    """Ressemblance au-dessus de laquelle deux passages voisins sont pris pour la même voix.

    Calibrée sur le fichier lui-même : un passage coupé seulement parce qu'il atteignait
    la durée maximale, sans pause, est presque toujours suivi du même locuteur. Le
    20e centile de leur ressemblance donne un seuil qui tient compte du modèle de voix
    (les échelles diffèrent d'un modèle à l'autre) et de la qualité de l'enregistrement.
    Faute d'assez de paires, 0,5."""
    import numpy as np
    n = len(E["a"])
    sims = [float(E["emb"][k] @ E["emb"][k + 1]) for k in range(n - 1)
            if E["valide"][k] and E["valide"][k + 1] and E["a"][k + 1] - E["b"][k] < 0.45]
    t = float(np.percentile(sims, 20)) if len(sims) >= 12 else 0.5
    return min(0.8, max(0.35, t))


def plages(E: dict, tau: float, exclus: set | None = None) -> list[dict]:
    """Les plus longues suites de passages voisins qui ont l'air d'une seule voix.

    Un passage rejoint la plage en cours si sa ressemblance au profil moyen de la plage
    atteint `tau` et si le silence qui les sépare reste court. Les passages `exclus`
    (déjà montrés ou nommés) et ceux sans empreinte coupent la plage : on n'enjambe pas
    ce qu'on ne peut pas vérifier. Une plage s'arrête à `PLAGE_MAX` secondes."""
    import numpy as np
    exclus = exclus or set()
    n = len(E["a"])
    sorties: list[dict] = []
    cur = None

    def clore():
        nonlocal cur
        if cur is None:
            return
        c = cur["somme"] / np.linalg.norm(cur["somme"])
        sims = [float(E["emb"][k] @ c) for k in cur["ks"]]
        sorties.append({"ks": cur["ks"], "start": float(E["a"][cur["ks"][0]]),
                        "end": float(E["b"][cur["ks"][-1]]), "centre": c,
                        "dur": float(sum(E["b"][k] - E["a"][k] for k in cur["ks"])),
                        "pire": min(sims)})
        cur = None

    for k in range(n):
        if k in exclus or not E["valide"][k]:
            clore()
            continue
        d = float(E["b"][k] - E["a"][k])
        if cur is not None:
            ecart = float(E["a"][k] - E["b"][cur["ks"][-1]])
            c = cur["somme"] / np.linalg.norm(cur["somme"])
            if (ecart <= PLAGE_ECART and float(E["emb"][k] @ c) >= tau
                    and float(E["b"][k] - E["a"][cur["ks"][0]]) <= PLAGE_MAX):
                cur["ks"].append(k)
                cur["somme"] = cur["somme"] + E["emb"][k] * d
                continue
            clore()
        cur = {"ks": [k], "somme": E["emb"][k] * d}
    clore()
    return sorties


def charger(dossier: Path) -> dict:
    import numpy as np
    d = np.load(dossier / "enrolement.npz", allow_pickle=False)
    meta = json.loads((dossier / "enrolement.json").read_text(encoding="utf-8"))
    E = {"a": d["a"], "b": d["b"], "emb": d["emb"], "valide": d["valide"],
         "textes": meta["textes"], "modele": meta["modele"], "F": None}
    if "fa" in d.files:       # les séances préparées avant les fenêtres fines n'en ont pas
        E["F"] = {"fa": d["fa"], "fb": d["fb"], "fz": d["fz"], "fok": d["fok"]}
    return E


def _profil_et_classement(E: dict, exemples: list[dict], wav: Path | None):
    """Profils d'après les exemples, puis classement de tous les passages.

    Rend (etiquettes_exemples, personnes, P, sims) où `etiquettes_exemples` est
    {indice_de_passage: nom} pour les passages couverts par un exemple."""
    import numpy as np
    n = len(E["a"])
    dur = E["b"] - E["a"]
    etiquette: dict[int, str] = {}
    amorces: dict[str, list] = {}
    for ex in exemples:
        nom = (ex.get("nom") or "").strip()
        a, b = float(ex["start"]), float(ex["end"])
        if not nom or b - a <= 0:
            continue
        couvre = False
        for k in range(n):
            if not E["valide"][k]:
                continue
            ov = min(b, E["b"][k]) - max(a, E["a"][k])
            if ov / max(dur[k], 1e-6) >= 0.85:          # passage entièrement dans l'exemple
                etiquette[k] = nom
                amorces.setdefault(nom, []).append((E["emb"][k], float(dur[k]), k))
                couvre = True
        if not couvre and b - a >= MIN_EMPREINTE and wav is not None:
            # exemple plus court qu'un passage (une coupe) : son empreinte propre
            e = _empreinte(_extracteur(E["modele"]), lire_wav(wav, a, b))
            if e is not None:
                amorces.setdefault(nom, []).append((e, b - a, -1))
    personnes = sorted(amorces)
    if not personnes:
        return etiquette, [], None, None, amorces
    P = np.stack([sum(e * d for e, d, _ in lst) for lst in (amorces[p] for p in personnes)])
    P = P / np.linalg.norm(P, axis=1, keepdims=True)
    sims = E["emb"] @ P.T
    return etiquette, personnes, P, sims, amorces


def _mesures(personnes, amorces):
    """Ce que les exemples permettent de vérifier (la personne connaît la bonne réponse).

    Pour chaque exemple, on le retire, on refait les profils sans lui et on regarde si
    la bonne personne ressort : un contrôle sur des réponses connues. On en tire aussi
    le seuil de ressemblance propre à chaque personne (le 10e centile de ses exemples)
    et la liste des exemples qui ne ressemblent pas aux autres de leur personne."""
    import numpy as np
    S = {p: sum(e * d for e, d, _ in amorces[p]) for p in personnes}
    justes = comptes = 0
    propres = {p: [] for p in personnes}
    suspects = []
    for p in personnes:
        if len(amorces[p]) < 2:
            continue
        for e, d, k in amorces[p]:
            sims = []
            for q in personnes:
                v = S[q] - (e * d if q == p else 0)
                nv = float(np.linalg.norm(v))
                sims.append(float(e @ v) / nv if nv > 0 else -1.0)
            comptes += 1
            justes += int(int(np.argmax(sims)) == personnes.index(p))
            propres[p].append(sims[personnes.index(p)])
            if int(np.argmax(sims)) != personnes.index(p):
                suspects.append((p, k, sims[personnes.index(p)]))
    seuils = {p: (float(np.percentile(v, 10)) if len(v) >= 3 else (min(v) - 0.05 if v else 0.3))
              for p, v in propres.items()}
    return {"justes": justes, "sur": comptes}, seuils, suspects


def classer(dossier: Path, exemples: list[dict], wav: Path | None = None,
            vus: list | None = None, cible: str | None = None) -> dict:
    """Où en est-on, et quels passages montrer ensuite ?

    `vus` : indices de passages déjà montrés (nommés, coupés ou laissés de côté) —
    jamais proposés deux fois. `cible` : le nom d'une personne dont on veut trouver
    d'autres passages, pour étoffer son profil."""
    import numpy as np
    E = charger(dossier)
    n = len(E["a"])
    dur = E["b"] - E["a"]
    valides = [k for k in range(n) if E["valide"][k]]
    total = float(sum(dur[k] for k in valides)) or 1.0
    etiquette, personnes, P, sims, amorces = _profil_et_classement(E, exemples, wav)

    F = E.get("F")

    def plage(r, **plus):
        t = " ".join(E["textes"][k] for k in r["ks"]).strip()
        if len(t) > 220:
            t = t[:130].rstrip() + " … " + t[-80:].lstrip()
        return {"index": int(r["ks"][0]), "indices": [int(k) for k in r["ks"]],
                "start": r["start"], "end": r["end"], "text": t, "nb": len(r["ks"]),
                "solide": bool(r["pire"] >= tau - 0.05), **plus}

    rapport = {"personnes": personnes, "passages": n, "total_exemples": sum(len(v) for v in amorces.values()),
               "secondes": {p: round(float(sum(dur[k] for k, nom in etiquette.items() if nom == p)), 1)
                            for p in personnes}}
    pris = set(etiquette) | {int(i) for i in (vus or [])}
    if F is not None:
        # Plages repérées sur des fenêtres de 2 s : une voix, du début à la fin.
        tau = seuil_fenetres(F)
        runs = plages_fines(F, tau, [(float(E["a"][k]), float(E["b"][k])) for k in pris])
        for r in runs:
            r["ks"] = [k for k in range(n) if min(r["end"], float(E["b"][k])) - max(r["start"], float(E["a"][k])) >= 0.3]
        runs = [r for r in runs if r["ks"]]
    else:
        # Séance préparée avant les fenêtres fines : plages de passages entiers, moins fiables.
        tau = seuil_meme_voix(E)
        runs = plages(E, tau, pris)
    rapport["plages"] = {"seuil": round(tau, 3), "nombre": len(runs), "fines": F is not None,
                         "secondes_max": round(max((r["dur"] for r in runs), default=0.0), 1)}

    if cible and cible in personnes:
        c = personnes.index(cible)
        cand = [r for r in runs if r["dur"] >= 4.0] or runs
        # d'abord ce qui ressemble le plus à la personne, et à ressemblance voisine, le plus long
        cand.sort(key=lambda r: (-round(float(P[c] @ r["centre"]) / 0.05), -r["dur"]))
        rapport["part_incertaine"] = None
        rapport["etat"] = "profil"
        rapport["cible"] = cible
        return {"propositions": [plage(r, suggestion=cible, motif="profil",
                                       conf=round(max(0.0, min(1.0, float(P[c] @ r["centre"]))), 2))
                                 for r in cand[:LOT * 2]], "rapport": rapport}

    if len(personnes) < 2:
        # Pas encore deux personnes : les plus longues plages d'une seule voix, aussi
        # différentes que possible les unes des autres, pour que chaque voix apparaisse.
        longues = sorted(runs, key=lambda r: -r["dur"])
        choisis: list[dict] = []
        if longues:
            seuil = max(8.0, 0.4 * longues[min(9, len(longues) - 1)]["dur"])
            cand = [r for r in longues if r["dur"] >= seuil] or longues[:LOT * 3]
            ref = [E["emb"][k] for k in pris if E["valide"][k]] + ([] if P is None else list(P))
            if not ref:
                choisis.append(cand[0])
                ref = [cand[0]["centre"]]
            while len(choisis) < LOT and len(choisis) < len(cand):
                R_ = np.stack(ref)
                suiv = max((r for r in cand if r not in choisis),
                           key=lambda r: float(1.0 - (R_ @ r["centre"]).max()) * (r["dur"] ** 0.5))
                choisis.append(suiv)
                ref.append(suiv["centre"])
        rapport["part_incertaine"] = None
        rapport["etat"] = "debut"
        return {"propositions": [plage(r, suggestion="", conf=0.0, motif="diversite") for r in choisis],
                "rapport": rapport}

    # Deux personnes ou plus : classement de tout le reste, puis les plus longues plages douteuses.
    controle, seuils, suspects = _mesures(personnes, amorces)
    rapport["controle"] = controle
    rapport["suspects"] = [{"nom": nom, "index": k, "start": float(E["a"][k]), "end": float(E["b"][k]),
                            "text": E["textes"][k]} for nom, k, _ in suspects if k >= 0][:5]
    marges = np.zeros(n)
    meilleur = [-1] * n
    maxsim = np.zeros(n)
    atypique = [False] * n
    for k in valides:
        s_ = sims[k]
        o = np.argsort(-s_)
        marges[k] = float(s_[o[0]] - (s_[o[1]] if len(o) > 1 else -1))
        meilleur[k] = int(o[0])
        maxsim[k] = float(s_[o[0]])
        # Un passage plus éloigné de sa voix retenue que 9 exemples de cette personne sur 10
        # ne lui ressemble pas assez : « confiant » ne suffit pas, il doit être typique.
        atypique[k] = maxsim[k] < seuils.get(personnes[meilleur[k]], 0.3) - 0.05 or maxsim[k] < 0.3
    incertains = [k for k in valides if k not in pris and (marges[k] < MARGE or atypique[k])]
    rapport["part_incertaine"] = round(float(sum(dur[k] for k in incertains)) / total, 3)
    rapport["etat"] = "classement"

    def mesure(r):
        s_ = P @ r["centre"]
        o = np.argsort(-s_)
        marge = float(s_[o[0]] - (s_[o[1]] if len(o) > 1 else -1))
        ms = float(s_[o[0]])
        aty = ms < seuils.get(personnes[int(o[0])], 0.3) - 0.05 or ms < 0.3
        return int(o[0]), marge, aty

    douteuses = []
    for r in runs:
        m, marge, aty = mesure(r)
        if r["dur"] >= 1.5 and (aty or marge < MARGE * 2):
            douteuses.append((r, m, marge, aty))
    # les plus longues d'abord ; ce qui ne ressemble à personne (une personne de plus ?) passe devant
    douteuses.sort(key=lambda x: -(x[0]["dur"] * (1.5 if x[3] else 1.0)))
    props = [plage(r, suggestion=personnes[m],
                   conf=0.0 if aty else round(max(0.0, min(1.0, marge / 0.2)), 2),
                   motif="inconnu" if aty else "hesite") for r, m, marge, aty in douteuses[:LOT]]
    return {"propositions": props, "rapport": rapport}


def etiqueter(dossier: Path, exemples: list[dict], mots: list[dict], wav: Path | None = None):
    """Un nom pour chaque mot : d'abord les exemples, puis le classement.

    Rend (tours, confiances, personnes) : des tours (début, fin, nom) au grain
    du mot, prêts pour `build_blocks`, et leur confiance."""
    import numpy as np
    E = charger(dossier)
    n = len(E["a"])
    etiquette, personnes, P, sims, amorces = _profil_et_classement(E, exemples, wav)
    _, seuils, _ = _mesures(personnes, amorces)
    if len(personnes) < 2:
        raise ValueError("Il faut au moins deux personnes avec des exemples.")
    nom_passage, conf_passage = [""] * n, [1.0] * n
    for k in range(n):
        if k in etiquette:
            nom_passage[k], conf_passage[k] = etiquette[k], 1.0
        elif E["valide"][k]:
            s = sims[k]
            o = np.argsort(-s)
            nom_passage[k] = personnes[int(o[0])]
            conf_passage[k] = max(0.0, min(1.0, float(s[o[0]] - s[o[1]]) / 0.2))
            if float(s[o[0]]) < seuils.get(personnes[int(o[0])], 0.3) - 0.05 or float(s[o[0]]) < 0.3:
                conf_passage[k] = 0.0       # ne ressemble pas assez à la voix retenue
    # les passages sans empreinte (trop courts) prennent le nom du voisin
    for k in range(n):
        if not nom_passage[k]:
            for d in range(1, n):
                voisins = [v for v in (k - d, k + d) if 0 <= v < n and nom_passage[v]]
                if voisins:
                    nom_passage[k], conf_passage[k] = nom_passage[voisins[0]], 0.0
                    break
    starts = E["a"]
    etiq_mot, conf_mot = [], []
    for m in mots:
        milieu = (m["start"] + m["end"]) / 2
        # un exemple désigné (même coupé) l'emporte sur le classement
        nom = None
        for ex in exemples:
            if ex.get("nom") and float(ex["start"]) <= milieu <= float(ex["end"]):
                nom = ex["nom"].strip()
        if nom:
            etiq_mot.append(nom)
            conf_mot.append(1.0)
            continue
        k = int(np.searchsorted(starts, milieu, side="right")) - 1
        k = min(max(k, 0), n - 1)
        etiq_mot.append(nom_passage[k])
        conf_mot.append(conf_passage[k])
    tours, confs = [], []
    for m, nom, c in zip(mots, etiq_mot, conf_mot):
        if tours and tours[-1][2] == nom and m["start"] - tours[-1][1] <= 0.7:
            tours[-1][1] = m["end"]
            confs[-1].append(c)
        else:
            tours.append([m["start"], m["end"], nom])
            confs.append([c])
    return [tuple(t) for t in tours], [float(np.mean(c)) for c in confs], personnes
