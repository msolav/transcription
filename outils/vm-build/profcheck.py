import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
H.JOB['speakers']=H.JOB['speakers'][:1]
for b in H.JOB['blocks']: b['speaker']=H.JOB['speakers'][0]['id']
errs=[]; req=[]
J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
P=lambda k,s,sug='',m='diversite': dict(index=k,start=s,end=s+8,text=f'Passage {k}',suggestion=sug,conf=0.5,motif=m)
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    pg.route('**/enrolement/preparer',lambda r,q:r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))
    def classer(r,q):
        d=json.loads(q.post_data); req.append(d)
        if d.get('cible'): r.fulfill(**J(dict(propositions=[P(7,300,d['cible'],'profil'),P(8,420,d['cible'],'profil')],rapport=dict(personnes=['Alice','Bob'],etat='profil',cible=d['cible'],secondes={'Alice':8,'Bob':8}))))
        elif not d['exemples']: r.fulfill(**J(dict(propositions=[P(1,10),P(2,100)],rapport=dict(personnes=[],etat='debut',secondes={}))))
        else: r.fulfill(**J(dict(propositions=[P(5,50,'Alice','hesite')],rapport=dict(personnes=['Alice','Bob'],etat='classement',part_incertaine=.2,secondes={'Alice':8,'Bob':8},controle=dict(justes=1,sur=2),suspects=[]))))
    pg.route('**/enrolement/classer',classer)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900); pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    pg.click('#sepafter'); pg.wait_for_timeout(500); pg.click('#aidego'); pg.wait_for_timeout(2500)
    for k,nom in [(0,'Alice'),(1,'Bob')]:
        pg.click(f'[data-a="nouv"][data-r="{k}"]'); pg.fill('#aide input.ar-new',nom); pg.press('#aide input.ar-new','Enter'); pg.wait_for_timeout(250)
    pg.click('[data-a="continuer"]'); pg.wait_for_timeout(1500)
    print('vus envoyés au 2e appel:', req[-1]['vus'], '| profils affichés:', pg.evaluate("document.querySelectorAll('#aide .ar-pf').length"))
    pg.click('[data-a="plus-de"][data-n="Alice"]'); pg.wait_for_timeout(1500)
    print('cible envoyée:', req[-1]['cible'], '| vus:', req[-1]['vus'], '| passages proposés:', pg.evaluate("[...document.querySelectorAll('#aide .ar-pass b')].map(x=>x.textContent)"))
    pg.click('[data-a="voir-ech"][data-n="Alice"]'); pg.wait_for_timeout(400); print('échantillons d\'Alice listés:', pg.evaluate("document.querySelectorAll('#aide .pf-e').length"))
    pg.click('[data-a="retire-ech"][data-n="Alice"]'); pg.wait_for_timeout(1500); print('après retrait -> exemples envoyés:', len(req[-1]['exemples']))
    pg.screenshot(path='/tmp/tr/prof.png'); print('erreurs:',errs,'| débordement',pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
