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
        "fr": "Deux services distincts, donc deux inscriptions.\n\n"
              "Groq : reconnaissance de la parole. Obligatoire — c'est "
              "lui qui produit le texte.\n\n"
              "Modèle d'IA au choix (Gemini, Claude) : rédaction du "
              "compte rendu à partir de ce texte. Facultatif. Sans lui, "
              "la sortie est le transcript brut.",
        "en": "Two separate services, two registrations.\n\n"
              "Groq: speech recognition. Required — it produces the "
              "text.\n\n"
              "An AI model of your choice (Gemini, Claude): drafting "
              "the minutes from that text. Optional. Without it, the "
              "output is the raw transcript.",
    },
}

QU_EST_CE_QU_UNE_CLE = {
    "titre": {"fr": "Ce qu'est une clé", "en": "What a key is"},
    "texte": {
        "fr": "Une clé d'API est une chaîne de caractères qui identifie "
              "le programme auprès du service. Sa portée se limite à ce "
              "service. Elle est révocable et remplaçable à tout "
              "moment, sans effet sur le compte.\n\n"
              "La plupart des services ne l'affichent qu'une fois, à la "
              "création.",
        "en": "An API key is a character string identifying the program "
              "to the service. Its scope is limited to that service. It "
              "is revocable and replaceable at any time, with no effect "
              "on the account.\n\n"
              "Most services display it once only, at creation.",
    },
}

OU_VA_LA_CLE = {
    "titre": {"fr": "Où elle est rangée", "en": "Where it is kept"},
    "texte": {
        "fr": "Stockage : trousseau du système — Trousseau d'accès "
              "(macOS), Gestionnaire d'identifiants (Windows), Secret "
              "Service, GNOME Keyring ou KWallet (Linux). Sans Secret "
              "Service : ~/.transcripteur.json, droits 0600.\n\n"
              "Transmission : au service propriétaire de la clé, et à "
              "lui seul.\n\n"
              "Traitement local : séparation des voix, sous-titres, "
              "stockage des transcriptions. Transmis à Groq : l'audio "
              "converti en MP3 mono.",
        "en": "Storage: the system keychain — Keychain Access (macOS), "
              "Credential Manager (Windows), Secret Service, GNOME "
              "Keyring or KWallet (Linux). With no Secret Service: "
              "~/.transcripteur.json, mode 0600.\n\n"
              "Transmission: to the service that owns the key, and to "
              "nothing else.\n\n"
              "Processed locally: voice separation, subtitles, "
              "transcript storage. Sent to Groq: the audio converted to "
              "mono MP3.",
    },
}

# L'abonnement pris pour une clé est la confusion la plus probable de ce
# public, et la plus coûteuse : on paie vingt dollars par mois avant de
# découvrir que cela ne donne rien ici.
PIEGE_ABONNEMENT = {
    "titre": {"fr": "Un abonnement n'est pas une clé",
              "en": "A subscription is not a key"},
    "texte": {
        "fr": "Un abonnement Claude Pro ou ChatGPT Plus ne fournit pas "
              "de clé d'API. Produits distincts, facturations "
              "distinctes : l'abonnement couvre l'usage du site web par "
              "une personne, la clé couvre l'accès par un programme.\n\n"
              "Un abonnement en cours ne dispense donc pas de créer une "
              "clé, et n'a pas à être résilié.",
        "en": "A Claude Pro or ChatGPT Plus subscription does not "
              "provide an API key. Separate products, separate "
              "billing: the subscription covers a person's use of the "
              "website, the key covers access by a program.\n\n"
              "An existing subscription therefore does not replace "
              "creating a key, and does not need cancelling.",
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
            "fr": "Obligatoire : toute la transcription passe par ce "
                  "service.",
            "en": "Required: all transcription goes through this "
                  "service.",
        },
        "prix": {"fr": "Gratuit, sans carte bancaire.",
                 "en": "Free, no credit card."},
        # Chaque pas porte un geste et un détail. Le geste est ce qui
        # s'affiche en grand, seul à l'écran : une phrase, un verbe, une
        # chose à faire. Le détail va derrière le bouton « i », pour qui
        # veut savoir pourquoi — et il n'encombre pas celui qui le sait
        # déjà. Les séparer ici plutôt que dans l'interface garde les
        # deux versions linguistiques ensemble, et une seule source.
        "etapes": [
            {"geste": {"fr": "Ouvrir la page des clés de Groq.",
                       "en": "Open the Groq keys page."},
             "detail": {"fr": "Ouvre console.groq.com/keys dans un "
                              "nouvel onglet.",
                        "en": "Opens console.groq.com/keys in a new "
                              "tab."}},
            # « GitHub » retiré de la liste : nommer un service de
            # développeurs à quelqu'un qui n'en est pas donne à croire
            # qu'il s'est trompé d'endroit.
            {"geste": {"fr": "Se connecter avec Google ou une adresse courriel.",
                       "en": "Sign in with Google or an email address."},
             "detail": {"fr": "Aucune carte bancaire n'est demandée.",
                        "en": "No credit card is required."}},
            {"geste": {"fr": "Créer une clé.",
                       "en": "Create a key."},
             "detail": {"fr": "Bouton « Create API Key ». Le nom "
                              "demandé est libre et sert uniquement à "
                              "identifier la clé dans la console.",
                        "en": "Button marked \"Create API Key\". The "
                              "name requested is free-form and only "
                              "identifies the key in the console."}},
            {"geste": {"fr": "Copier la clé, puis la coller ici.",
                       "en": "Copy the key, then paste it here."},
             "detail": {"fr": "Format : gsk_… Groq ne l'affiche "
                              "qu'une fois. En cas de perte, en créer "
                              "une autre.",
                        "en": "Format: gsk_… Groq displays it once "
                              "only. If lost, create another."}},
        ],
        "limites": {
            "fr": "Plafond quotidien sur le compte gratuit. Au "
                  "dépassement, le message indique l'heure de "
                  "réinitialisation.",
            "en": "Daily ceiling on the free account. When exceeded, the "
                  "message states the reset time.",
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
            "en": "Free option. Context window large enough to process "
                  "the transcript in a single request.",
        },
        "prix": {"fr": "Gratuit, sans carte bancaire.",
                 "en": "Free, no credit card."},
        "etapes": [
            {"geste": {"fr": "Ouvrir la page des clés de Google.",
                       "en": "Open the Google keys page."},
             "detail": {"fr": "Le bouton ouvre aistudio.google.com/apikey "
                              "dans un nouvel onglet.",
                        "en": "The button opens aistudio.google.com/apikey "
                              "in a new tab."}},
            {"geste": {"fr": "Se connecter avec un compte Google.",
                       "en": "Sign in with a Google account."},
             "detail": {"fr": "Aucune carte bancaire n'est demandée.",
                        "en": "No credit card is asked for."}},
            {"geste": {"fr": "Créer une clé.",
                       "en": "Create a key."},
             "detail": {"fr": "Bouton « Create API key ». Si un projet "
                              "est demandé, celui proposé par défaut "
                              "convient.",
                        "en": "Button marked \"Create API key\". If a "
                              "project is requested, the default one "
                              "is suitable."}},
            {"geste": {"fr": "Copier la clé, puis la coller ici.",
                       "en": "Copy the key, then paste it here."},
             "detail": {"fr": "Elle commence par AIza ou par AQ. — les deux "
                              "formats sont acceptés.",
                        "en": "It starts with AIza or with AQ. — both "
                              "formats are accepted."}},
        ],
        "limites": {
            "fr": "Quota exprimé en requêtes par jour, pas en volume de "
                  "texte. Un compte rendu consomme une à deux requêtes.",
            "en": "Quota measured in requests per day, not in volume of "
                  "text. One set of minutes uses one or two requests.",
        },
    },
    {
        "id": "anthropic",
        "nom": "Claude (Anthropic)",
        "requis": False,
        "role": {"fr": "Rédaction du compte rendu. Service payant.",
                 "en": "Drafting of the minutes. Paid service."},
        "pour_quoi": {
            "fr": "Pas de plafond quotidien. Utile lorsque les quotas "
                  "gratuits sont insuffisants.",
            "en": "No daily ceiling. Useful when the free quotas are "
                  "insufficient.",
        },
        "prix": {
            "fr": "Facturation à l'usage, sur crédit prépayé. Ordre de "
                  "grandeur : quelques dizaines de centimes par compte "
                  "rendu.",
            "en": "Billed by usage, from prepaid credit. Order of "
                  "magnitude: a few tens of cents per set of minutes.",
        },
        "etapes": [
            {"geste": {"fr": "Ouvrir la page des clés d'Anthropic.",
                       "en": "Open the Anthropic keys page."},
             "detail": {"fr": "Le bouton ouvre "
                              "console.anthropic.com/settings/keys dans un "
                              "nouvel onglet.",
                        "en": "The button opens "
                              "console.anthropic.com/settings/keys in a new "
                              "tab."}},
            {"geste": {"fr": "Créer un compte, puis y déposer du crédit.",
                       "en": "Create an account, then add credit to it."},
             "detail": {"fr": "Sans crédit, la clé existe mais chaque "
                              "demande est refusée. Une dizaine de dollars "
                              "durent très longtemps.",
                        "en": "With no credit the key exists but every "
                              "request is refused. Ten dollars or so lasts "
                              "a very long time."}},
            {"geste": {"fr": "Créer une clé.",
                       "en": "Create a key."},
             "detail": {"fr": "Cherche le bouton « Create Key ».",
                        "en": "Look for the button marked \"Create Key\"."}},
            {"geste": {"fr": "Copier la clé, puis la coller ici.",
                       "en": "Copy the key, then paste it here."},
             "detail": {"fr": "Elle commence par sk-ant-.",
                        "en": "It starts with sk-ant-."}},
        ],
        "limites": {
            "fr": "Pas de plafond quotidien. Le coût estimé est affiché "
                  "avant lancement.",
            "en": "No daily ceiling. The estimated cost is displayed "
                  "before launch.",
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
            # Le geste et le détail séparés : l'interface affiche l'un en
            # grand et range l'autre derrière un « i ». Rendus ensemble,
            # ils obligeraient l'interface à redécouper une phrase, ce
            # qu'elle ferait mal et dans une seule langue.
            "etapes": [{"geste": t(e["geste"], langue),
                        "detail": t(e["detail"], langue)}
                       for e in c["etapes"]],
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
                geste = escape(t(e["geste"], lg))
                detail = escape(t(e["detail"], lg))
                if i == 0 and adresse:
                    # Sur une page imprimée ou envoyée par courriel il
                    # n'y a pas de bouton pour ouvrir le site : il faut
                    # donc l'adresse, et cliquable. Quand le détail la
                    # nomme déjà, on rend ce mot-là cliquable au lieu de
                    # l'ajouter une seconde fois à la suite.
                    lien = (f'<a href="https://{escape(adresse)}" '
                            f'target="_blank" rel="noopener">'
                            f'{escape(adresse)}</a>')
                    if escape(adresse) in detail:
                        detail = detail.replace(escape(adresse), lien, 1)
                    else:
                        detail += " " + lien
                pas.append(f"<li><b>{geste}</b> {detail}</li>")
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
