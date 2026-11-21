import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
H.JOB['speakers']=H.JOB['speakers'][:1]            # texte sans séparation : une seule voix
for b in H.JOB['blocks']: b['speaker']=H.JOB['speakers'][0]['id']
posted={'classer':[],'terminer':[]}; errs=[]
def prop(k,s,e,t,sug='',motif='diversite'): return dict(index=k,start=s,end=e,text=t,suggestion=sug,conf=0.0,motif=motif)
LOT1=[prop(0,5,12,'Bonjour tout le monde, merci d\'être là.'),prop(1,300,307,'On passe au budget des locaux.'),prop(2,900,907,'Je ne suis pas d\'accord.')]
LOT2=[prop(3,40,47,'Oui mais le délai est trop court.','Alice','hesite'),prop(4,500,506,'Voyons ce que dit le contrat.','Bob','inconnu')]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
    pg.route('**/enrolement/preparer',lambda r,q:r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))
    def classer(r,q):
        d=json.loads(q.post_data); posted['classer'].append(d)
        if not d['exemples']: r.fulfill(**J(dict(propositions=LOT1,rapport=dict(personnes=[],etat='debut',part_incertaine=None,secondes={}))))
        else: r.fulfill(**J(dict(propositions=LOT2,rapport=dict(personnes=['Alice','Bob'],etat='classement',part_incertaine=0.22,secondes={'Alice':12.0,'Bob':7.0},controle=dict(justes=1,sur=2),suspects=[]))))
    pg.route('**/enrolement/classer',classer)
    pg.route('**/enrolement/terminer',lambda r,q:(posted['terminer'].append(json.loads(q.post_data)),r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))[1])
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1000)
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    pg.click('#sepafter'); pg.wait_for_timeout(600); print('bouton « identifier » visible (texte à une voix):', pg.is_visible('#aidego'), '|', pg.inner_text('#aidego'))
    pg.click('#aidego'); pg.wait_for_timeout(2500); print('passages proposés:', pg.evaluate("document.querySelectorAll('#aide .ar-pass').length"), '| Terminer activé:', pg.is_enabled('[data-a="terminer"]'))
    pg.screenshot(path='/tmp/tr/enrol1.png')
    # nouvelle personne « Alice » sur le 1er, puis « Bob » sur le 2e
    for k,nom in [(0,'Alice'),(1,'Bob')]:
        if k==1: pg.click('[data-a="pass-s"]'); pg.wait_for_timeout(200)
        pg.click('[data-a="nouv"]'); pg.fill('#aide input.ar-new',nom); pg.press('#aide input.ar-new','Enter'); pg.wait_for_timeout(250)
    pg.click('[data-a="continuer"]'); pg.wait_for_timeout(1500)
    print('2e lot:', pg.evaluate("document.querySelectorAll('#aide .ar-pass').length"), '| suggestions en pointillés:', pg.evaluate("document.querySelectorAll('#aide .chip.sug').length"), '| Terminer activé:', pg.is_enabled('[data-a="terminer"]'))
    pg.click('#aide .ar-pass >> .chip >> nth=0'); pg.wait_for_timeout(200); pg.screenshot(path='/tmp/tr/enrol2.png')
    pg.click('[data-a="terminer"]'); pg.wait_for_timeout(1200)
    print('envoyé à « terminer »:', json.dumps(posted['terminer'][0],ensure_ascii=False)); print('erreurs:',errs,'| débordement',pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
