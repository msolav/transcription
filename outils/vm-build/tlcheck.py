import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
H.JOB['speakers']=H.JOB['speakers'][:1]
for b in H.JOB['blocks']: b['speaker']=H.JOB['speakers'][0]['id']
posted=[]; errs=[]
J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    pg.route('**/enrolement/preparer',lambda r,q:r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))
    pg.route('**/enrolement/classer',lambda r,q:r.fulfill(**J(dict(propositions=[dict(index=0,start=100,end=120,text='Bonjour tout le monde, merci d\'être là. Alors je commence.',suggestion='',conf=0,motif='diversite')],rapport=dict(personnes=[],etat='debut',part_incertaine=None,secondes={})))))
    pg.route('**/enrolement/terminer',lambda r,q:(posted.append(json.loads(q.post_data)),r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))[1])
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
    # faux lecteur : horloge simulée, lecture/pause
    pg.evaluate("""(()=>{let t=0,pause=true,last=performance.now();const e=document.querySelector('#player');
      setInterval(()=>{const n=performance.now();if(!pause)t+=(n-last)/1000;last=n},50);
      Object.defineProperty(e,'currentTime',{get:()=>t,set:v=>{t=v},configurable:true});Object.defineProperty(e,'paused',{get:()=>pause,configurable:true});
      e.play=()=>{pause=false;return Promise.resolve()};e.pause=()=>{pause=true}})()""")
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    pg.evaluate("document.querySelector('#player').currentTime=0"); pg.click('#sepafter'); pg.wait_for_timeout(500); pg.click('#aidego'); pg.wait_for_timeout(2500)
    box=pg.query_selector('#aide .ar-tl').bounding_box(); print('ligne du temps visible:',bool(box), '| largeur',round(box['width']))
    pg.mouse.click(box['x']+box['width']*0.5, box['y']+20); pg.wait_for_timeout(300)
    t=pg.evaluate("document.querySelector('#player').currentTime"); print('clic au milieu -> position',round(t,1),'s (attendu ≈110)')
    pg.click('[data-a="basc"]'); pg.wait_for_timeout(1200); print('lecture en cours:', not pg.evaluate("document.querySelector('#player').paused"), '| tête de lecture avance:', round(pg.evaluate("document.querySelector('#player').currentTime")-t,1),'s')
    pg.keyboard.press('Space'); pg.wait_for_timeout(300); print('Espace -> pause:', pg.evaluate("document.querySelector('#player').paused"))
    pg.keyboard.press('ArrowLeft'); pg.wait_for_timeout(200); print('← recule d\'1 s -> ', round(pg.evaluate("document.querySelector('#player').currentTime"),1))
    pg.click('[data-a="nudge"][data-d="-2"]'); pg.wait_for_timeout(200); print('−2 s ->', round(pg.evaluate("document.querySelector('#player').currentTime"),1))
    pg.evaluate("document.querySelector('#player').currentTime=108"); pg.wait_for_timeout(300); pg.keyboard.press('c'); pg.wait_for_timeout(400)
    print('coupe par la touche C ->', pg.evaluate("document.querySelectorAll('#aide .tl-cut').length"),'coupe(s),', pg.evaluate("document.querySelectorAll('#aide .ar-seg').length"),'morceaux')
    cut=pg.query_selector('#aide .tl-cut').bounding_box(); box=pg.query_selector('#aide .ar-tl').bounding_box()
    pg.mouse.move(cut['x']+7,cut['y']+10); pg.mouse.down(); pg.mouse.move(box['x']+box['width']*0.7,cut['y']+10,steps=5); pg.mouse.up(); pg.wait_for_timeout(400)
    print('coupe déplacée à ≈', round(100+20*(pg.query_selector('#aide .tl-cut').bounding_box()['x']+7-box['x'])/box['width'],1),'s (attendu ≈114)')
    for j,nom in [(0,'Alice'),(1,'Bob')]:
        pg.click(f'[data-a="nouv"][data-j="{j}"]'); pg.fill('#aide input.ar-new',nom); pg.press('#aide input.ar-new','Enter'); pg.wait_for_timeout(250)
    pg.screenshot(path='/tmp/tr/tl.png')
    pg.click('[data-a="terminer"]'); pg.wait_for_timeout(1000)
    print('envoyé:', [(round(e['start'],1),round(e['end'],1),e['nom']) for e in posted[0]['exemples']]); print('erreurs:',errs,'| débordement',pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
