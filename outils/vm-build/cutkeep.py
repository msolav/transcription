import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
H.JOB['speakers']=H.JOB['speakers'][:1]
for b in H.JOB['blocks']: b['speaker']=H.JOB['speakers'][0]['id']
J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d)); errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); install(pg)
    pg.route('**/enrolement/preparer',lambda r,q:r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))
    pg.route('**/enrolement/classer',lambda r,q:r.fulfill(**J(dict(propositions=[dict(index=0,start=100,end=140,text='t',suggestion='',conf=0,motif='diversite')],rapport=dict(personnes=[],etat='debut',secondes={})))))
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
    pg.evaluate("""(()=>{let t=0;const e=document.querySelector('#player');Object.defineProperty(e,'currentTime',{get:()=>t,set:v=>{t=v},configurable:true});Object.defineProperty(e,'paused',{get:()=>true,configurable:true});e.play=()=>Promise.resolve();e.pause=()=>{}})()""")
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    pg.click('#sepafter'); pg.wait_for_timeout(500); pg.click('#aidego'); pg.wait_for_timeout(2500)
    pg.click('[data-a="nouv"]'); pg.fill('#aide input.ar-new','Alice'); pg.press('#aide input.ar-new','Enter'); pg.wait_for_timeout(300)
    noms=lambda: pg.evaluate("[...document.querySelectorAll('#aide .tl-seg')].map(x=>x.style.backgroundColor)")
    print('1 morceau, coloré:', noms())
    for t in (110,125,135):
        pg.evaluate(f"document.querySelector('#player').currentTime={t}"); pg.keyboard.press('c'); pg.wait_for_timeout(250)
    c=noms(); print('après 3 coupes:', len(c),'morceaux, couleurs identiques:', len(set(c))==1 and c[0]!='rgba(128, 128, 128, 0.35)')
    pg.click('[data-a="nouv"]'); pg.fill('#aide input.ar-new','Bob'); pg.press('#aide input.ar-new','Enter'); pg.wait_for_timeout(300)
    pg.evaluate("document.querySelector('#player').currentTime=120"); pg.keyboard.press('c'); pg.wait_for_timeout(300)
    print('après nommage du morceau 2 puis une coupe au milieu du 3e:', len(noms()),'morceaux ; couleurs:', noms())
    pg.evaluate("document.querySelector('#aide .tl-cut').dispatchEvent(new MouseEvent('dblclick',{bubbles:true}))"); pg.wait_for_timeout(300); print('coupe supprimée -> morceaux:',len(noms()),'couleurs:',noms()); print('erreurs:',errs)
    b.close()
