import os
HERE = os.path.dirname(os.path.abspath(__file__))
import json, re, wave, struct, math, sys
from playwright.sync_api import sync_playwright

HTML = open('/Users/solav/Documents/Scripts/voice_trascription/Transcripteur/transcripteur/static/index-vm.html', encoding='utf-8').read()
ORIGIN = 'http://tr.test'

# ---- fixture: a short French meeting ----
COLORS = ['#e4572e', '#2f7ed8', '#2b9a6a', '#8a5cc2']
speakers = [dict(id=f's{i}', index=i, color=COLORS[i], speaking_seconds=[260, 190, 120][i], share=[.46, .33, .21][i], turns=[9, 7, 4][i],
                 has_sample=True, sample_start=5 + 20 * i, sample_seconds=8, extraits=[5 + 20 * i], montage=False) for i in range(3)]
lines = [(0, 's0', "Bonjour tout le monde, merci d'être là. On commence par le budget des locaux."),
         (14, 's1', "Oui, j'ai regardé les chiffres hier soir. Le loyer augmente de huit pour cent à partir de janvier."),
         (31, 's0', "C'est plus que prévu. Est-ce qu'on peut renégocier avec le propriétaire avant la fin du mois ?"),
         (47, 's2', "Je peux l'appeler demain matin. Il m'a déjà dit qu'il était ouvert à une discussion."),
         (66, 's1', "Parfait. Alors la décision est prise : Dominique appelle le propriétaire, et on se revoit jeudi."),
         (85, 's0', "Très bien. Dernier point : le site Web. Vincent, où en est-on ?"),
         (97, 's2', "La nouvelle version sera en ligne la semaine prochaine, il reste les tests sur mobile.")]
blocks = []
for i, (t, s, text) in enumerate(lines):
    end = lines[i + 1][0] if i + 1 < len(lines) else t + 14
    ws = text.split(); step = (end - t - 1) / max(len(ws), 1)
    blocks.append(dict(start=t, end=end - 1, speaker=s, text=text, words=[dict(text=w, start=t + k * step, end=t + (k + 1) * step) for k, w in enumerate(ws)]))
JOB = dict(id='j1', status='done', stage='Terminé', progress=1.0, filename='reunion-conseil.m4a', duration=112, names={}, speakers=speakers, blocks=blocks, relecture=None, notes=['Conversion…', 'Séparation des voix…'])
MODELS = dict(modeles=[
    dict(cle='voxceleb_campplus', nom='Multilingue CAM++', mo=28.2, note="Entraîné sur VoxCeleb, une centaine de nationalités. Rapide.", poids=1.8, telecharge=True),
    dict(cle='voxceleb_resnet', nom='Multilingue ResNet34', mo=25.3, note="Architecture différente : à essayer quand les CAM++ confondent deux voix.", poids=1.7, telecharge=False),
    dict(cle='titanet_large', nom='Anglais TitaNet (grand)', mo=96.7, note="Anglais uniquement, mais réputé solide. Lent et lourd.", poids=2.6, telecharge=False)],
    nettoyeurs=[dict(cle='leger', nom='Léger', mo=.5, note="Enlève le souffle sans toucher au timbre. C'est ce qui a donné la meilleure séparation dans nos mesures, et c'est presque instantané.", vitesse=18.3, telecharge=True),
                dict(cle='recommande', nom='Fort', mo=8.4, note="Nettoie beaucoup plus, mais a fait disparaître une voix sur trois dans notre enregistrement d'essai. À réserver à un son très dégradé, et à vérifier en écoutant les extraits.", vitesse=11.5, telecharge=False)],
    nettoyeur_defaut='leger')
RMOD = dict(modeles=[dict(cle='gemini-flash', nom='Gemini Flash (gratuit)', fournisseur='google', dispo=True, gratuit=True, un_appel=True, note="Gratuit, et voit la réunion entière d'un coup. Peu de requêtes par jour, ce qui suffit largement."),
                     dict(cle='gpt-oss-120b', nom='GPT-OSS 120B (gratuit)', fournisseur='groq', dispo=True, gratuit=True, un_appel=False, note="Gratuit, par tranches de dix blocs. Quota quotidien.")],
            defaut='gemini-flash', fournisseurs=dict(google=dict(nom='Google', prefixe='AIza', ou='aistudio.google.com/apikey', gratuit=True)))
ROPTS = dict(modeles=[dict(cle='gemini-flash', nom='Gemini Flash (gratuit)'), dict(cle='gpt-oss-120b', nom='GPT-OSS 120B (gratuit)')], defaut='gemini-flash',
             resumes=[dict(cle='compte_rendu', nom='Compte rendu', apercu='## Contexte\nRéunion du conseil, 83 minutes.'), dict(cle='bref', nom='Résumé bref', apercu='La réunion a porté sur les locaux.')])
CORR = [dict(type='locuteur', bloc=3, avant='Voix 3', apres='Dominique'), dict(type='texte', bloc=4, avant="Parfait. Alors la décision est prise : Dominique appelle le propriétaire", apres="Parfait. La décision est prise : Dominique appelle le propriétaire")]

def make_wav(path, secs=12):
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(2 * math.pi * 330 * i / 16000))) for i in range(16000 * secs)))

def install(page, has_key=True, state=None):
    state = state if state is not None else {}
    state.setdefault('polls', 0)
    def handler(route):
        req = route.request; url = req.url
        if not url.startswith(ORIGIN): return route.continue_()
        path = url[len(ORIGIN):]
        def J(o): route.fulfill(status=200, content_type='application/json', body=json.dumps(o))
        if path == '/' or path.startswith('/?'): return route.fulfill(status=200, content_type='text/html', body=HTML)
        if path.startswith('/api/health'): return J(dict(has_key=has_key, key_from_env=False, code_perime=False))
        if path.startswith('/api/models'): return J(MODELS)
        if path.startswith('/api/relecture/modeles'): return J(RMOD)
        if path.startswith('/api/relecture'): return J(ROPTS)
        if path.startswith('/api/jobs/import'): return J(JOB)
        if path == '/api/jobs' and req.method == 'POST': return J(dict(id='j1'))
        if '/cout' in path: return J(dict(jetons=12000, blocs=7))
        if '/relire' in path: state['rel'] = True; return J({})
        if '/resume' in path: return J(dict(texte="Réunion du conseil.\n\nDécision : Dominique appelle le propriétaire demain."))
        if '/names' in path or '/cancel' in path: return J({})
        if re.match(r'/api/jobs/j1\?light=1', path) or re.match(r'/api/jobs/j1\?light=0', path):
            if state.get('rel'): return J(dict(JOB, relecture=dict(status='done', corrections=CORR, blocks=blocks)))
            state['polls'] += 1
            if state.get('hold'): return J(dict(JOB, status='running', stage='Séparation des voix 38 %', progress=.38, notes=['Conversion…', 'Séparation des voix…']))
            if state['polls'] < 2: return J(dict(JOB, status='running', stage='Séparation des voix 38 %', progress=.38, notes=['Conversion…']))
            return J(JOB)
        if path.startswith('/api/jobs/j1'): return J(JOB)
        return route.fulfill(status=404, body='{}')
    page.route('**/*', handler)
    return state
