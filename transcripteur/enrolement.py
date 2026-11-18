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
LOT = 4            # passages proposés à la fois

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
    with wave.open(str(wav), "rb") as w:
        for k, p in enumerate(passages):
            if k % 20 == 0:
                controle()
                if avance:
                    avance(k / max(n, 1))
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
    np.savez(dossier / "enrolement.npz",
             a=np.array([p["start"] for p in passages]), b=np.array([p["end"] for p in passages]),
             emb=np.stack([e if e is not None else np.zeros(dim, dtype=np.float32) for e in emb]),
             valide=np.array(valide))
    (dossier / "enrolement.json").write_text(json.dumps({
        "modele": modele,
        "textes": [" ".join(m["text"].strip() for m in p["mots"]).strip() for p in passages],
    }, ensure_ascii=False), encoding="utf-8")
    if avance:
        avance(1.0)
    dire(f"{sum(valide)} empreintes exploitables sur {n} passages")
    return n


def charger(dossier: Path) -> dict:
    import numpy as np
    d = np.load(dossier / "enrolement.npz", allow_pickle=False)
    meta = json.loads((dossier / "enrolement.json").read_text(encoding="utf-8"))
    return {"a": d["a"], "b": d["b"], "emb": d["emb"], "valide": d["valide"],
            "textes": meta["textes"], "modele": meta["modele"]}


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

    def passage(k, **plus):
        return {"index": k, "start": float(E["a"][k]), "end": float(E["b"][k]),
                "text": E["textes"][k], **plus}

    rapport = {"personnes": personnes, "passages": n, "total_exemples": sum(len(v) for v in amorces.values()),
               "secondes": {p: round(float(sum(dur[k] for k, nom in etiquette.items() if nom == p)), 1)
                            for p in personnes}}
    pris = set(etiquette) | {int(i) for i in (vus or [])}

    if cible and cible in personnes:
        c = personnes.index(cible)
        cand = [k for k in valides if k not in pris and dur[k] >= 1.5]
        cand.sort(key=lambda k: -float(sims[k][c]))
        choisis = []
        for k in cand:
            if all(abs(E["a"][k] - E["a"][j]) > 8 for j in choisis):
                choisis.append(k)
            if len(choisis) >= LOT * 2:
                break
        rapport["part_incertaine"] = None
        rapport["etat"] = "profil"
        rapport["cible"] = cible
        return {"propositions": [passage(k, suggestion=cible, motif="profil",
                                         conf=round(max(0.0, min(1.0, float(sims[k][c]))), 2))
                                 for k in choisis], "rapport": rapport}

    if len(personnes) < 2:
        # Pas encore deux personnes : des passages aussi différents que possible,
        # pour que chaque voix ait une chance d'apparaître.
        cand = [k for k in valides if k not in pris and dur[k] >= 3.0]
        choisis: list[int] = []
        if cand:
            ref = [E["emb"][k] for k in pris] + ([] if P is None else list(P))
            if not ref:
                depart = max(cand, key=lambda k: dur[k])     # le passage le plus long
                choisis.append(depart)
                ref = [E["emb"][depart]]
            while len(choisis) < LOT and len(choisis) < len(cand):
                R = np.stack(ref)
                eloigne = max((k for k in cand if k not in choisis),
                              key=lambda k: float(1.0 - (R @ E["emb"][k]).max()))
                choisis.append(eloigne)
                ref.append(E["emb"][eloigne])
        rapport["part_incertaine"] = None
        rapport["etat"] = "debut"
        return {"propositions": [passage(k, suggestion="", conf=0.0, motif="diversite") for k in choisis],
                "rapport": rapport}

    # Deux personnes ou plus : classement de tout le reste, puis les plus incertains.
    controle, seuils, suspects = _mesures(personnes, amorces)
    rapport["controle"] = controle
    rapport["suspects"] = [{"nom": nom, "index": k, "start": float(E["a"][k]), "end": float(E["b"][k]),
                            "text": E["textes"][k]} for nom, k, _ in suspects if k >= 0][:5]
    marges = np.zeros(n)
    meilleur = [-1] * n
    maxsim = np.zeros(n)
    atypique = [False] * n
    for k in valides:
        s = sims[k]
        o = np.argsort(-s)
        marges[k] = float(s[o[0]] - (s[o[1]] if len(o) > 1 else -1))
        meilleur[k] = int(o[0])
        maxsim[k] = float(s[o[0]])
        # Un passage plus éloigné de sa voix retenue que 9 exemples de cette personne sur 10
        # ne lui ressemble pas assez : « confiant » ne suffit pas, il doit être typique.
        atypique[k] = maxsim[k] < seuils.get(personnes[meilleur[k]], 0.3) - 0.05 or maxsim[k] < 0.3
    incertains = [k for k in valides if k not in pris and (marges[k] < MARGE or atypique[k])]
    rapport["part_incertaine"] = round(float(sum(dur[k] for k in incertains)) / total, 3)
    rapport["etat"] = "classement"
    cand = [k for k in valides if k not in pris and dur[k] >= 1.5]
    # d'abord ce qui ressemble à personne (une personne de plus ?), puis ce qui hésite
    cand.sort(key=lambda k: (0 if atypique[k] else 1, marges[k]))
    choisis = []
    for k in cand:
        if marges[k] >= MARGE * 2 and not atypique[k]:
            break
        if all(abs(E["a"][k] - E["a"][j]) > 10 for j in choisis):
            choisis.append(k)
        if len(choisis) >= LOT:
            break
    props = [passage(k, suggestion=personnes[meilleur[k]],
                     conf=0.0 if atypique[k] else round(max(0.0, min(1.0, float(marges[k]) / 0.2)), 2),
                     motif="inconnu" if atypique[k] else "hesite") for k in choisis]
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
