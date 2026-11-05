"""
Contrôles des sous-titres.

Un sous-titre faux ne se voit pas en relisant le fichier : il se voit à
l'écran, trois secondes, et on ne sait pas dire s'il était en avance ou
si c'est la phrase qui était longue. D'où des contrôles sur les
propriétés qu'on peut affirmer sans regarder la vidéo : rien qui
chevauche, rien de trop court, rien de trop long, aucun mot perdu, et
deux voix jamais dans la même réplique.
"""
import sys

from . import sous_titres as st

fails = []


def ok(nom, condition, detail=""):
    print(f"  {'OK ' if condition else 'ÉCHEC'} {nom}"
          f"{' — ' + detail if detail and not condition else ''}")
    if not condition:
        fails.append(nom)


def mots(texte: str, depart: float = 0.0, pas: float = 0.38,
         duree: float = 0.32) -> list[dict]:
    sortie, t = [], depart
    for m in texte.split():
        sortie.append({"start": round(t, 3), "end": round(t + duree, 3),
                       "text": m})
        t += pas
    return sortie


TIRADE = ("Bonjour à tous, merci d'être venus. Nous avons trois points à "
          "l'ordre du jour, et je voudrais qu'on garde du temps pour le "
          "dernier, parce que c'est celui qui touche au budget. Est-ce que "
          "tout le monde a reçu le document ?")

AUTRE = ("Oui, je l'ai lu hier soir. J'ai une question sur la deuxième "
         "ligne, celle des assurances, parce que le montant ne correspond "
         "pas à ce qu'on avait dit en septembre.")


def bloc(voix: str, texte: str, depart: float) -> dict:
    m = mots(texte, depart)
    return {"speaker": voix, "start": m[0]["start"], "end": m[-1]["end"],
            "words": m, "text": texte}


a = bloc("SPEAKER_00", TIRADE, 0.0)
b = bloc("SPEAKER_01", AUTRE, a["end"] + 1.2)
blocs = [a, b]

# --------------------------------------------------------- découpage simple

r = st.decouper(blocs)
ok("des répliques sont produites", len(r) > 4, f"{len(r)}")

ok("aucune réplique ne dépasse deux lignes",
   all(st.replier(x["text"]).count("\n") <= 1 for x in r))
longues = [x["text"] for x in r
           if any(len(ligne) > st.CHARS_PAR_LIGNE
                  for ligne in st.replier(x["text"]).split("\n"))]
ok("aucune ligne ne dépasse la largeur", not longues, str(longues[:2]))

ok("aucune réplique ne dure plus de six secondes",
   all(x["end"] - x["start"] <= st.MAX_DUREE + 0.01 for x in r),
   str([round(x["end"] - x["start"], 2) for x in r]))

# Une réplique peut rester courte si la suivante arrive tout de suite :
# ce qu'on vérifie, c'est qu'on l'a étirée dès qu'il y avait de la place.
courtes = [x for n, x in enumerate(r)
           if x["end"] - x["start"] < st.MIN_DUREE - 0.01
           and (n + 1 >= len(r)
                or r[n + 1]["start"] - x["start"] > st.MIN_DUREE + st.ECART)]
ok("les répliques trop courtes sont étirées quand il y a de la place",
   not courtes, str([(x["start"], x["end"]) for x in courtes[:2]]))

chevauchent = [(r[n]["end"], r[n + 1]["start"]) for n in range(len(r) - 1)
               if r[n]["end"] > r[n + 1]["start"]]
ok("aucune réplique n'en recouvre une autre", not chevauchent,
   str(chevauchent[:2]))

ordonnees = all(r[n]["start"] <= r[n + 1]["start"] for n in range(len(r) - 1))
ok("les répliques sont dans l'ordre", ordonnees)

ok("chaque réplique a une fin après son début",
   all(x["end"] >= x["start"] for x in r))

# Aucun mot ne doit disparaître en route : c'est l'erreur la plus grave,
# et la seule qu'on ne remarque pas en regardant l'aperçu.
def sans_espaces(texte: str) -> str:
    return "".join(texte.split())


attendu = sans_espaces(st._coller(a["words"]) + st._coller(b["words"]))
obtenu = sans_espaces("".join(x["text"] for x in r))
ok("aucun mot perdu ni ajouté", attendu == obtenu,
   f"{len(attendu)} caractères attendus, {len(obtenu)} obtenus")

# --------------------------------------------------------- une voix par réplique

ok("une réplique ne porte qu'une voix",
   all(x["speaker"] in ("SPEAKER_00", "SPEAKER_01") for x in r))
frontiere = [n for n in range(len(r) - 1)
             if r[n]["speaker"] != r[n + 1]["speaker"]]
ok("le changement de voix tombe entre deux répliques", len(frontiere) == 1,
   f"{len(frontiere)} changement(s)")

# --------------------------------------------------------- avec les noms

n = st.decouper(blocs, {"SPEAKER_00": "Thomas", "SPEAKER_01": "Amélie"},
                avec_noms=True)
ok("la première réplique porte le nom", n[0]["text"].startswith("Thomas : "))
premiere_autre = next(x for x in n if x["speaker"] == "SPEAKER_01")
ok("la première réplique de l'autre voix porte son nom",
   premiere_autre["text"].startswith("Amélie : "))
ok("le nom ne se répète pas à chaque réplique",
   sum(1 for x in n if x["text"].startswith("Thomas : ")) == 1,
   str([x["text"][:20] for x in n]))
ok("les noms ne font pas déborder la largeur",
   all(len(ligne) <= st.CHARS_PAR_LIGNE
       for x in n for ligne in st.replier(x["text"]).split("\n")),
   str([x["text"] for x in n
        if any(len(l) > st.CHARS_PAR_LIGNE
               for l in st.replier(x["text"]).split("\n"))][:1]))

# Une voix sans nom donné garde une étiquette lisible : « SPEAKER_00 »
# affiché par-dessus l'image n'apprend rien à personne.
sans_nom = st.decouper(blocs, {}, avec_noms=True)
ok("une voix sans nom reçoit une étiquette lisible",
   sans_nom[0]["text"].startswith("Voix 1 : "), sans_nom[0]["text"][:24])

# --------------------------------------------------------- rappel du nom

# Dans un tour très long, le nom doit reparaître : qui arrive en cours de
# route n'a jamais vu celui du début.
long_bloc = [bloc("SPEAKER_00", " ".join([TIRADE] * 6), 0.0)]
rappels = [x for x in st.decouper(long_bloc, {"SPEAKER_00": "Thomas"},
                                  avec_noms=True)
           if x["text"].startswith("Thomas : ")]
ok("le nom reparaît dans un tour long", len(rappels) > 1, f"{len(rappels)}")
ecarts = [round(rappels[i + 1]["start"] - rappels[i]["start"], 1)
          for i in range(len(rappels) - 1)]
ok("le rappel respecte l'intervalle prévu",
   all(e >= st.RAPPEL_NOM for e in ecarts), str(ecarts))

# --------------------------------------------------------- un silence coupe

# Un silence d'une seconde au milieu d'une phrase doit créer une coupe :
# garder les deux moitiés ensemble ferait rester le sous-titre affiché
# pendant le silence, donc en avance sur ce qui est dit.
coupe = mots("Donc voilà", 0.0) + mots("c'est ce que je proposais", 5.0)
une_voix = [{"speaker": "SPEAKER_00", "start": 0.0, "end": 8.0,
             "words": coupe, "text": ""}]
d = st.decouper(une_voix)
ok("un silence crée une coupe", len(d) >= 2, f"{len(d)} réplique(s)")

# --------------------------------------------------------- sans horodatage

vieux = [{"speaker": "SPEAKER_00", "start": 0.0, "end": 30.0,
          "text": "Un export ancien, sans les mots.", "words": []}]
try:
    st.decouper(vieux)
    ok("un transcript sans horodatage est refusé", False, "aucun refus")
except st.SansHorodatage as exc:
    ok("un transcript sans horodatage est refusé", True)
    ok("le refus dit quoi faire", "retranscrire" in str(exc).lower(), str(exc))

ok("un transcript vide ne lève rien", st.decouper([]) == [])

# --------------------------------------------------------- les formats

srt = st.vers_srt(r)
ok("le SRT numérote à partir de 1", srt.startswith("1\n"))
ok("le SRT sépare par des virgules", " --> " in srt and ",000" in srt or "," in srt.split("\n")[1])
ok("le SRT compte autant de blocs que de répliques",
   srt.count(" --> ") == len(r))

vtt = st.vers_vtt(r)
ok("le VTT s'annonce", vtt.startswith("WEBVTT\n"))
ok("le VTT sépare par des points", "." in vtt.split("\n")[3])
ok("le VTT compte autant de blocs que de répliques",
   vtt.count(" --> ") == len(r))

# Un « <rire> » noté dans le transcript serait pris pour une balise et
# effacerait la fin de la réplique à l'écran.
chevrons = st.decouper([{"speaker": "A", "start": 0, "end": 3,
                         "words": mots("il a dit <rire> puis rien"),
                         "text": ""}])
sortie = st.vers_vtt(chevrons)
ok("le VTT échappe les chevrons", "&lt;rire&gt;" in sortie and "<rire>" not in sortie)

ok("l'horodatage tient les heures", st.horodatage(3725.5, ",") == "01:02:05,500",
   st.horodatage(3725.5, ","))
ok("un arrondi ne fabrique pas une seconde de trop",
   st.horodatage(1.9999, ",") == "00:00:01,999", st.horodatage(1.9999, ","))

print(f"\n{'SOUS-TITRES CONFORMES' if not fails else str(len(fails)) + ' PROBLÈME(S)'}")
sys.exit(1 if fails else 0)
