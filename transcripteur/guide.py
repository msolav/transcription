"""
Le mode d'emploi des clés, en français et en anglais, comme donnée.

Pourquoi ici plutôt que dans l'interface : ce texte doit paraître à trois
endroits qui n'ont pas la même durée de vie. Dans l'application, au
premier lancement, quand personne n'a encore de clé. Dans une page
autonome qu'on envoie par courriel à quelqu'un qui n'a pas encore
installé le programme — et qui ne peut donc pas lire une page servie par
le programme. Dans le README, pour celui qui lit le dépôt. Trois copies
divergent en une semaine ; une source unique ne divergent pas.

Le public visé n'a pas de formation technique et ne sait pas ce qu'est
une clé d'API. Les consignes disent donc ce qu'on cherche à obtenir
avant de nommer le bouton qui l'obtient : « cherche le bouton qui crée
une clé — "Create API Key" » survit à un changement d'intitulé chez le
fournisseur, « clique sur Create API Key » laisse l'utilisateur bloqué
devant une page qui ne contient plus ce mot.

Les quotas annoncés restent qualitatifs. Les chiffres exacts changent
sans préavis et nous ne les mesurons pas : promettre « deux cents
requêtes » qu'on n'a pas comptées est le genre de détail inventé qui
coûte la confiance de celui qui compte dessus.
"""

from __future__ import annotations

from . import config

# Un texte bilingue est un dictionnaire à deux entrées. `verifier_guide`
# s'assure qu'aucune des deux ne manque : une phrase sans anglais ne se
# voit pas en français, et se découvre devant la personne à qui on avait
# promis une interface bilingue.
LANGUES = ("fr", "en")


def t(texte, langue: str = "fr") -> str:
    """La version demandée d'un texte bilingue, le français par défaut."""
    if isinstance(texte, str):
        return texte
    return texte.get(langue) or texte.get("fr") or ""


# ----------------------------------------------------------- les notions

POURQUOI_DEUX = {
    "titre": {"fr": "Pourquoi deux inscriptions",
              "en": "Why two sign-ups"},
    "texte": {
        "fr": "L'outil fait deux métiers. Le premier écoute l'enregistrement "
              "et écrit ce qui a été dit : c'est Groq qui s'en charge. Le "
              "second lit ce texte et en tire un compte rendu : c'est une "
              "intelligence artificielle, celle de ton choix. Deux "
              "entreprises différentes, donc deux inscriptions.\n\n"
              "La première est obligatoire — sans elle, rien ne se "
              "transcrit. La seconde est facultative : sans elle tu obtiens "
              "le texte brut de la réunion, ce qui suffit si tu rédiges le "
              "compte rendu toi-même.",
        "en": "The tool does two jobs. The first listens to the recording "
              "and writes down what was said — Groq handles that. The "
              "second reads that text and drafts the minutes — an AI of "
              "your choosing handles that. Two different companies, so two "
              "sign-ups.\n\n"
              "The first is required: without it, nothing gets transcribed. "
              "The second is optional: without it you still get the raw "
              "text of the meeting, which is enough if you write the "
              "minutes yourself.",
    },
}

QU_EST_CE_QU_UNE_CLE = {
    "titre": {"fr": "Ce qu'est une clé", "en": "What a key is"},
    "texte": {
        "fr": "Une clé d'API est une longue suite de caractères que l'outil "
              "présente au service pour dire « c'est bien moi qui demande ». "
              "Ce n'est pas le mot de passe de ton compte : elle ne donne "
              "accès qu'à ce seul service, et tu peux la supprimer pour en "
              "créer une autre quand tu veux, sans rien casser ailleurs.\n\n"
              "Copie-la au moment où elle s'affiche. La plupart des services "
              "ne la remontrent jamais ensuite — ils en recréent une, ce qui "
              "n'est pas grave non plus.",
        "en": "An API key is a long string of characters that the tool shows "
              "a service to say \"this really is me asking\". It is not your "
              "account password: it opens that one service and nothing else, "
              "and you can delete it and make another whenever you like, "
              "without breaking anything.\n\n"
              "Copy it the moment it appears. Most services never show it "
              "again afterwards — they just make you a new one, which is no "
              "trouble either.",
    },
}

OU_VA_LA_CLE = {
    "titre": {"fr": "Où elle est rangée", "en": "Where it is kept"},
    "texte": {
        "fr": "Dans le trousseau de ton système — Trousseau d'accès sur Mac, "
              "Gestionnaire d'identifiants sur Windows. Sur cette machine, "
              "et nulle part ailleurs. Elle n'est envoyée qu'au service "
              "auquel elle appartient, et elle ne traîne pas en clair dans "
              "un fichier que tes sauvegardes recopient.\n\n"
              "La séparation des voix, elle, se calcule entièrement sur "
              "cette machine. Seul l'audio, compressé en MP3 mono, part chez "
              "Groq pour la reconnaissance de la parole.",
        "en": "In your system keychain — Keychain Access on a Mac, "
              "Credential Manager on Windows. On this machine, nowhere else. "
              "It is only ever sent to the service it belongs to, and it is "
              "not left in plain text in a file your backups copy.\n\n"
              "Separating the voices, for its part, is computed entirely on "
              "this machine. Only the audio, compressed to mono MP3, goes to "
              "Groq for speech recognition.",
    },
}

# L'abonnement pris pour une clé est la confusion la plus probable de ce
# public, et la plus coûteuse : on paie vingt dollars par mois avant de
# découvrir que cela ne donne rien ici.
PIEGE_ABONNEMENT = {
    "titre": {"fr": "Un abonnement n'est pas une clé",
              "en": "A subscription is not a key"},
    "texte": {
        "fr": "Un abonnement Claude Pro, ou ChatGPT Plus, ne donne pas de "
              "clé d'API. Ce sont deux produits distincts, avec deux "
              "factures distinctes : l'abonnement paie l'usage du site par "
              "un humain, la clé paie l'usage du service par un programme "
              "comme celui-ci.\n\n"
              "Si tu as déjà un abonnement, il ne sert à rien ici, et il "
              "n'y a rien à annuler : prends la clé gratuite de Gemini.",
        "en": "A Claude Pro or ChatGPT Plus subscription does not give you an "
              "API key. They are two separate products with two separate "
              "bills: the subscription pays for a human using the website, "
              "the key pays for a program like this one using the service."
              "\n\nIf you already have a subscription it is of no use here, "
              "and there is nothing to cancel: take the free Gemini key.",
    },
}


# -------------------------------------------------------------- les clés

# L'ordre compte : c'est celui dans lequel on les demande. Groq d'abord
# parce que rien ne fonctionne sans elle, Gemini ensuite parce que c'est
# le choix gratuit mesuré comme fiable, Claude en dernier parce qu'il
# demande une carte bancaire et n'est pas nécessaire.
CLES = [
    {
        "id": "groq",
        "nom": "Groq",
        "requis": True,
        "role": {"fr": "Transcrit la parole en texte.",
                 "en": "Turns speech into text."},
        "pour_quoi": {
            "fr": "Sans cette clé, l'outil ne peut rien faire : c'est elle "
                  "qui transforme l'enregistrement en texte.",
            "en": "Without this key the tool can do nothing at all: it is "
                  "what turns the recording into text.",
        },
        "prix": {"fr": "Gratuit, sans carte bancaire.",
                 "en": "Free, no credit card."},
        "etapes": [
            {"fr": "Ouvre console.groq.com/keys",
             "en": "Open console.groq.com/keys"},
            {"fr": "Connecte-toi avec Google, GitHub ou une adresse "
                   "courriel. Aucune carte bancaire n'est demandée.",
             "en": "Sign in with Google, GitHub or an email address. No "
                   "credit card is asked for."},
            {"fr": "Cherche le bouton qui crée une clé — « Create API Key ». "
                   "Donne-lui le nom que tu veux, « Transcripteur » par "
                   "exemple : ce nom ne sert qu'à t'y retrouver.",
             "en": "Find the button that creates a key — \"Create API Key\". "
                   "Give it any name you like, \"Transcripteur\" for "
                   "instance: the name is only there to help you recognise "
                   "it later."},
            {"fr": "Copie la clé affichée, puis reviens ici et colle-la.",
             "en": "Copy the key it shows you, then come back here and paste "
                   "it in."},
        ],
        "limites": {
            "fr": "Le compte gratuit a un plafond quotidien. L'usage normal "
                  "d'une association l'atteint rarement ; quand il est "
                  "atteint, le message annonce l'heure à laquelle reprendre.",
            "en": "The free account has a daily ceiling. Normal use by a "
                  "community organisation rarely reaches it; when it is "
                  "reached, the message tells you what time to come back.",
        },
    },
    {
        "id": "google",
        "nom": "Gemini (Google)",
        "requis": False,
        "recommande": True,
        "role": {"fr": "Rédige le compte rendu à partir du texte.",
                 "en": "Drafts the minutes from the text."},
        "pour_quoi": {
            "fr": "C'est le choix gratuit, et celui que nous avons mesuré "
                  "comme le plus fiable : il lit la réunion entière d'un "
                  "seul tenant au lieu de la découper en tranches.",
            "en": "This is the free option, and the one we measured as the "
                  "most dependable: it reads the whole meeting in one piece "
                  "instead of chopping it into slices.",
        },
        "prix": {"fr": "Gratuit, sans carte bancaire.",
                 "en": "Free, no credit card."},
        "etapes": [
            {"fr": "Ouvre aistudio.google.com/apikey",
             "en": "Open aistudio.google.com/apikey"},
            {"fr": "Connecte-toi avec un compte Google. Aucune carte "
                   "bancaire n'est demandée.",
             "en": "Sign in with a Google account. No credit card is asked "
                   "for."},
            {"fr": "Cherche le bouton qui crée une clé — « Create API key ». "
                   "Si on te demande de choisir un projet, celui qui est "
                   "proposé convient.",
             "en": "Find the button that creates a key — \"Create API key\". "
                   "If you are asked to pick a project, the one it suggests "
                   "will do."},
            {"fr": "Copie la clé affichée, puis reviens ici et colle-la.",
             "en": "Copy the key it shows you, then come back here and paste "
                   "it in."},
        ],
        "limites": {
            "fr": "Le compte gratuit limite le nombre de requêtes par jour, "
                  "pas le volume de texte — ce qui tombe bien, puisqu'un "
                  "compte rendu tient en une ou deux requêtes. De quoi "
                  "couvrir plusieurs réunions par jour.",
            "en": "The free account limits how many requests you make per "
                  "day, not how much text they carry — which suits us, since "
                  "one set of minutes takes one or two requests. Enough for "
                  "several meetings a day.",
        },
    },
    {
        "id": "anthropic",
        "nom": "Claude (Anthropic)",
        "requis": False,
        "role": {"fr": "Rédige le compte rendu, un peu mieux, contre "
                       "paiement.",
                 "en": "Drafts the minutes, somewhat better, for a fee."},
        "pour_quoi": {
            "fr": "Le plus capable des trois, et sans plafond quotidien. À "
                  "ne faire que si le choix gratuit ne te suffit pas — pour "
                  "un compte rendu de réunion, il suffit presque toujours.",
            "en": "The most capable of the three, and with no daily ceiling. "
                  "Worth doing only if the free option is not enough for you "
                  "— for meeting minutes, it almost always is.",
        },
        "prix": {
            "fr": "Payant, à l'usage. Il faut déposer du crédit d'avance : "
                  "une dizaine de dollars durent très longtemps, un compte "
                  "rendu coûtant quelques dizaines de centimes au plus.",
            "en": "Paid, by usage. You have to put credit in up front: ten "
                  "dollars or so lasts a very long time, one set of minutes "
                  "costing a few tens of cents at most.",
        },
        "etapes": [
            {"fr": "Ouvre console.anthropic.com/settings/keys",
             "en": "Open console.anthropic.com/settings/keys"},
            {"fr": "Crée un compte, puis dépose du crédit : sans crédit, la "
                   "clé existe mais chaque demande est refusée.",
             "en": "Create an account, then add credit: with no credit the "
                   "key exists but every request is refused."},
            {"fr": "Cherche le bouton qui crée une clé — « Create Key ».",
             "en": "Find the button that creates a key — \"Create Key\"."},
            {"fr": "Copie la clé affichée, puis reviens ici et colle-la.",
             "en": "Copy the key it shows you, then come back here and paste "
                   "it in."},
        ],
        "limites": {
            "fr": "Pas de plafond quotidien : tu paies ce que tu consommes, "
                  "et le panneau affiche le coût estimé avant de lancer.",
            "en": "No daily ceiling: you pay for what you use, and the panel "
                  "shows the estimated cost before it starts.",
        },
    },
]


# ------------------------------------------------------- quand ça casse

# Les trois pannes réellement rencontrées, dans l'ordre de fréquence
# observée. Un message d'erreur qu'on a prévu cesse d'être une panne.
PANNES = [
    {
        "symptome": {"fr": "« Quota quotidien atteint »",
                     "en": "\"Daily quota reached\""},
        "remede": {
            "fr": "Le compte gratuit a servi sa ration du jour. Le message "
                  "donne l'heure de reprise, et elle est juste : le décompte "
                  "glisse, l'attente est souvent de quelques minutes. Sinon, "
                  "choisis un autre modèle dans la liste.",
            "en": "The free account has had its ration for the day. The "
                  "message gives you a time to come back and it is accurate: "
                  "the count slides, so the wait is often only a few "
                  "minutes. Otherwise pick another model from the list.",
        },
    },
    {
        "symptome": {"fr": "« Modèle momentanément saturé »",
                     "en": "\"Model momentarily saturated\""},
        "remede": {
            "fr": "Rien à voir avec toi : le service gratuit a trop de monde "
                  "à cet instant. Un autre modèle de la liste répondra tout "
                  "de suite.",
            "en": "Nothing to do with you: the free service has too many "
                  "people on it at that moment. Another model in the list "
                  "will answer straight away.",
        },
    },
    {
        "symptome": {"fr": "« Clé refusée »", "en": "\"Key refused\""},
        "remede": {
            "fr": "Recopie-la : une espace restée au bout suffit à la "
                  "casser. Vérifie aussi que c'est la bonne case — une clé "
                  "Groq ne fonctionne pas chez Gemini, et chaque clé a son "
                  "début reconnaissable. Si tu l'as supprimée chez le "
                  "fournisseur, il faut en créer une autre.",
            "en": "Copy it again: one space left on the end is enough to "
                  "break it. Check it is the right box, too — a Groq key "
                  "does not work at Gemini, and each key has its own "
                  "recognisable beginning. If you deleted it at the "
                  "provider, you need to make a new one.",
        },
    },
]


# ------------------------------------------------------------- assemblage

def pour_interface(langue: str = "fr") -> dict:
    """Le guide dans une seule langue, prêt à afficher.

    Le préfixe attendu et l'adresse du fournisseur sont lus dans
    `config.FOURNISSEURS` au lieu d'être recopiés ici : deux listes
    d'adresses finissent par ne plus dire la même chose, et c'est
    l'interface qui aurait tort la première."""
    cles = []
    for c in CLES:
        fiche = config.FOURNISSEURS.get(c["id"], {})
        prefixes = fiche.get("prefixe", ())
        prefixes = list(prefixes) if isinstance(prefixes, tuple) else [prefixes]
        cles.append({
            "id": c["id"],
            "nom": c["nom"],
            "requis": c["requis"],
            "recommande": c.get("recommande", False),
            "role": t(c["role"], langue),
            "pour_quoi": t(c["pour_quoi"], langue),
            "prix": t(c["prix"], langue),
            "limites": t(c["limites"], langue),
            "etapes": [t(e, langue) for e in c["etapes"]],
            "url": "https://" + fiche.get("ou", ""),
            "ou": fiche.get("ou", ""),
            "prefixes": prefixes,
        })
    notions = [POURQUOI_DEUX, QU_EST_CE_QU_UNE_CLE, PIEGE_ABONNEMENT,
               OU_VA_LA_CLE]
    return {
        "langue": langue,
        "notions": [{"titre": t(n["titre"], langue),
                     "texte": t(n["texte"], langue)} for n in notions],
        "cles": cles,
        "pannes": [{"symptome": t(p["symptome"], langue),
                    "remede": t(p["remede"], langue)} for p in PANNES],
    }


# ------------------------------------------------- la page autonome

# Rendue des deux langues à la fois, avec un bouton qui bascule. Une page
# qu'on envoie par courriel doit s'ouvrir sans serveur et sans réseau :
# celui qui la lit n'a pas encore installé le programme, c'est même la
# raison pour laquelle on la lui envoie.
_STYLE = """
:root { --encre:#17150f; --papier:#f6f4ee; --trait:#d6d1c4; --signal:#1b4ddb; }
@media (prefers-color-scheme:dark) {
  :root { --encre:#eceaE3; --papier:#14130f; --trait:#332f27; --signal:#8fa8ff; } }
* { box-sizing:border-box; }
body { margin:0 auto; padding:clamp(1.5rem,5vw,4rem) 1.5rem 6rem; max-width:40rem;
  background:var(--papier); color:var(--encre); font:400 1.0625rem/1.65
  ui-serif, Georgia, "Times New Roman", serif; }
h1 { font:600 clamp(2rem,7vw,3rem)/1.05 ui-sans-serif, system-ui, sans-serif;
  letter-spacing:-.02em; margin:0 0 .4em; }
h2 { font:600 1.4rem/1.2 ui-sans-serif, system-ui, sans-serif; letter-spacing:-.01em;
  margin:3rem 0 .6em; padding-top:1.4rem; border-top:3px solid var(--encre); }
h3 { font:600 1.0625rem/1.3 ui-sans-serif, system-ui, sans-serif; margin:2rem 0 .3em; }
p, li { margin:0 0 .9em; }
ol, ul { padding-left:1.3em; }
ol { counter-reset:pas; list-style:none; padding-left:0; }
ol li { counter-increment:pas; position:relative; padding-left:2.4em; }
ol li::before { content:counter(pas); position:absolute; left:0; top:.1em;
  font:600 .8rem/1.5em ui-sans-serif, system-ui, sans-serif; width:1.5em;
  text-align:center; border:1px solid var(--trait); border-radius:50%; }
a { color:var(--signal); text-decoration-thickness:1px; text-underline-offset:.15em; }
code { font:.9em var(--mono, ui-monospace, Menlo, monospace); background:color-mix(in srgb, var(--encre) 8%, transparent);
  padding:.1em .35em; border-radius:.2em; }
.chapeau { font-size:1.2rem; color:color-mix(in srgb, var(--encre) 72%, transparent); }
.etiq { display:inline-block; font:600 .7rem/1 ui-sans-serif, system-ui, sans-serif;
  letter-spacing:.08em; text-transform:uppercase; padding:.4em .55em;
  border:1px solid var(--trait); border-radius:.2em; margin:0 0 .8em;
  vertical-align:.15em; }
.etiq.oblig { background:var(--encre); color:var(--papier); border-color:var(--encre); }
.panne { border-left:3px solid var(--trait); padding-left:1rem; margin:0 0 1.4em; }
.panne b { font-family:ui-sans-serif, system-ui, sans-serif; }
.bascule { position:sticky; top:0; float:right; display:flex; gap:2px;
  background:var(--papier); padding:.4rem 0 .4rem .6rem; }
.bascule button { font:600 .75rem/1 ui-sans-serif, system-ui, sans-serif;
  letter-spacing:.1em; padding:.6em .7em .5em; background:none; color:inherit;
  border:0; border-bottom:2px solid transparent; cursor:pointer; opacity:.5; }
.bascule button[aria-pressed=true] { opacity:1; border-bottom-color:currentColor; }
html[lang=fr] .en, html[lang=en] .fr { display:none; }
@media print { .bascule { display:none; } a[href^=http]::after { content:" (" attr(href) ")";
  font-size:.8em; word-break:break-all; } }
"""


def _p(texte: str) -> str:
    """Un texte en paragraphes, les sauts doubles faisant la coupure."""
    from html import escape
    return "".join(f"<p>{escape(bloc).strip()}</p>"
                   for bloc in texte.split("\n\n") if bloc.strip())


def _bl(obj, balise: str = "div") -> str:
    """Le même contenu dans les deux langues, côte à côte dans le DOM."""
    return "".join(
        f'<{balise} class="{lg}" lang="{lg}">{_p(t(obj, lg))}</{balise}>'
        for lg in LANGUES)


def _bl_ligne(obj, balise: str = "span") -> str:
    from html import escape
    return "".join(
        f'<{balise} class="{lg}" lang="{lg}">{escape(t(obj, lg))}</{balise}>'
        for lg in LANGUES)


_TITRES = {
    "page": {"fr": "Brancher le Transcripteur",
             "en": "Connecting the Transcripteur"},
    "chapeau": {
        "fr": "Ce qu'il faut faire une seule fois, avant la première "
              "réunion. Compte dix minutes, et aucune carte bancaire.",
        "en": "What has to be done once, before the first meeting. Give it "
              "ten minutes, and no credit card.",
    },
    "cles": {"fr": "Les clés, une par une", "en": "The keys, one at a time"},
    "pannes": {"fr": "Si quelque chose refuse",
               "en": "If something refuses"},
    "oblig": {"fr": "Obligatoire", "en": "Required"},
    "facul": {"fr": "Facultatif", "en": "Optional"},
    "conseil": {"fr": "Recommandé", "en": "Recommended"},
    "debut": {"fr": "La clé commence par", "en": "The key starts with"},
    "fin": {
        "fr": "Une fois les clés collées, elles ne sont plus redemandées. "
              "Pour en changer, le bouton est au bas de la page de "
              "l'application.",
        "en": "Once the keys are pasted in, you are not asked for them "
              "again. To change one, the button is at the bottom of the "
              "application's page.",
    },
}


def page_html(langue: str = "fr") -> str:
    """La page autonome, les deux langues dedans, `langue` affichée."""
    from html import escape
    morceaux = [
        "<!doctype html>",
        f'<html lang="{langue if langue in LANGUES else "fr"}">',
        "<head><meta charset=utf-8>",
        '<meta name=viewport content="width=device-width,initial-scale=1">',
        f"<title>{escape(t(_TITRES['page'], langue))}</title>",
        f"<style>{_STYLE}</style></head><body>",
        '<div class="bascule" role="group" aria-label="Langue / Language">'
        '<button type=button data-l=fr lang=fr>FR</button>'
        '<button type=button data-l=en lang=en>EN</button></div>',
        f"<h1>{_bl_ligne(_TITRES['page'])}</h1>",
        f'<div class="chapeau">{_bl(_TITRES["chapeau"])}</div>',
    ]

    for notion in (POURQUOI_DEUX, QU_EST_CE_QU_UNE_CLE, PIEGE_ABONNEMENT,
                   OU_VA_LA_CLE):
        morceaux.append(f"<h2>{_bl_ligne(notion['titre'])}</h2>")
        morceaux.append(_bl(notion["texte"]))

    morceaux.append(f"<h2>{_bl_ligne(_TITRES['cles'])}</h2>")
    for c in CLES:
        fiche = config.FOURNISSEURS.get(c["id"], {})
        prefixes = fiche.get("prefixe", ())
        prefixes = list(prefixes) if isinstance(prefixes, tuple) else [prefixes]
        etiquette = _TITRES["oblig"] if c["requis"] else (
            _TITRES["conseil"] if c.get("recommande") else _TITRES["facul"])
        classe = "etiq oblig" if c["requis"] else "etiq"
        morceaux.append(
            f"<h3>{escape(c['nom'])}</h3>"
            f'<span class="{classe}">{_bl_ligne(etiquette)}</span> '
            f"{_bl_ligne(c['role'])}")
        morceaux.append(_bl(c["pour_quoi"]))
        morceaux.append(_bl(c["prix"]))
        # L'adresse du premier pas devient un lien, comme dans
        # l'application : c'est exactement là que les gens se perdent, et
        # recopier une adresse à la main en introduit une faute.
        adresse = fiche.get("ou", "")
        for lg in LANGUES:
            pas = []
            for i, e in enumerate(c["etapes"]):
                texte = escape(t(e, lg))
                if i == 0 and adresse:
                    texte = texte.replace(
                        escape(adresse),
                        f'<a href="https://{escape(adresse)}" target="_blank"'
                        f' rel="noopener">{escape(adresse)}</a>')
                pas.append(f"<li>{texte}</li>")
            morceaux.append(f'<ol class="{lg}" lang="{lg}">{"".join(pas)}</ol>')
        morceaux.append(
            f"<p>{_bl_ligne(_TITRES['debut'])} "
            + " / ".join(f"<code>{escape(p)}</code>" for p in prefixes)
            + f'. <a href="https://{escape(fiche.get("ou", ""))}" '
              f'target="_blank" rel="noopener">{escape(fiche.get("ou", ""))}'
              "</a></p>")
        morceaux.append(_bl(c["limites"]))

    morceaux.append(f"<h2>{_bl_ligne(_TITRES['pannes'])}</h2>")
    for p in PANNES:
        morceaux.append(
            f'<div class="panne"><b>{_bl_ligne(p["symptome"])}</b>'
            f"{_bl(p['remede'])}</div>")

    morceaux.append(_bl(_TITRES["fin"]))
    morceaux.append("""<script>
(function () {
  var html = document.documentElement, boutons = document.querySelectorAll('.bascule button');
  function poser(l) {
    html.lang = l;
    boutons.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.l === l); });
    try { localStorage.setItem('vm-lang', l); } catch (e) {}
  }
  var garde = null;
  try { garde = localStorage.getItem('vm-lang'); } catch (e) {}
  poser(garde === 'en' || garde === 'fr' ? garde : html.lang);
  boutons.forEach(function (b) { b.onclick = function () { poser(b.dataset.l); }; });
})();
</script></body></html>""")
    return "\n".join(morceaux)


if __name__ == "__main__":  # python -m transcripteur.guide > aide.html
    print(page_html("fr"))
