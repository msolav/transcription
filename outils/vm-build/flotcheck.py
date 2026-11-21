import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
import copy
base=H.JOB['blocks']; H.JOB['blocks']=[]
for r in range(5):
    for b in copy.deepcopy(base):
        b['start']+=r*120; b['end']+=r*120
        for w in b.get('words',[]): w['start']+=r*120; w['end']+=r*120
        H.JOB['blocks'].append(b)
H.JOB['duration']=600
errs=[]; req=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    pg.route('**/enrolement/terminer',lambda r,q:(req.append(json.loads(q.post_data)),r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))[1])
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
    pg.evaluate("""(()=>{let t=0,pause=true;const e=document.querySelector('#player');Object.defineProperty(e,'currentTime',{get:()=>t,set:v=>{t=v},configurable:true});Object.defineProperty(e,'paused',{get:()=>pause,configurable:true});Object.defineProperty(e,'duration',{get:()=>600,configurable:true});e.play=()=>{pause=false;return Promise.resolve()};e.pause=()=>{pause=true}})()""")
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    print('pages:',pg.evaluate('offs.length'))
    pg.evaluate('setPage(2)'); pg.wait_for_timeout(1500); page=pg.evaluate('page'); print('page courante:',page)
    idx=pg.evaluate("[...document.querySelectorAll('.turn .who')].findIndex(w=>{const r=w.getBoundingClientRect();return r.top>150&&r.top<innerHeight-150&&w.offsetParent})")
    print('idx visible:',idx)
    pg.evaluate(f"document.querySelectorAll('.turn .who')[{idx}].dispatchEvent(new MouseEvent('click',{{bubbles:true}}))"); pg.wait_for_timeout(900)
    print('panneau visible:',pg.is_visible('#flotnom'),'| page inchangée:',pg.evaluate("page")==page)
    cur=pg.evaluate("document.querySelector('#flotnom .chip.on').textContent"); print('voix actuelle:',cur)
    other=pg.evaluate("[...document.querySelectorAll('#flotnom .chip:not(.on)')].map(c=>c.textContent)[0]")
    pg.click(f'#flotnom .chip:not(.on) >> nth=0'); pg.wait_for_timeout(700)
    print('réattribuée à:',pg.evaluate("document.querySelector('#flotnom .chip.on').textContent"),'| corrections:',pg.inner_text('#flotnom footer span'),'| page inchangée:',pg.evaluate("page")==page,'| raffiner activé:',pg.is_enabled('#flotnom [data-f="raff"]'))
    pg.fill('#flotnom .fl-nom','Zoé'); pg.wait_for_timeout(400); print('renommée -> étiquettes visibles:',pg.evaluate("[...new Set([...document.querySelectorAll('.turn .who')].map(x=>x.textContent.trim()))]"))
    # lecteur
    pg.evaluate("document.querySelector('#player').currentTime=200"); pg.click('#first'); pg.wait_for_timeout(600); print('Début: 200 ->',round(pg.evaluate("document.querySelector('#player').currentTime"),1),'| page',pg.evaluate("page"))
    t0=pg.evaluate("document.querySelector('#player').currentTime"); pg.click('#next'); pg.wait_for_timeout(500); t1=pg.evaluate("document.querySelector('#player').currentTime")
    print('Suivant:',round(t0,1),'->',round(t1,1),'| ts des répliques:',pg.evaluate("[...document.querySelectorAll('.turn')].slice(0,3).map(t=>Math.round(t.dataset.ts))"))
    print('erreurs:',errs,'| débordement',pg.evaluate("document.documentElement.scrollHeight-innerHeight")); pg.screenshot(path='/tmp/tr/flot.png'); b.close()
