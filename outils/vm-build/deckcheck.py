import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); install(pg)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
    pg.evaluate("""(()=>{let t=0,pause=true;const e=document.querySelector('#player');Object.defineProperty(e,'currentTime',{get:()=>t,set:v=>{t=v},configurable:true});Object.defineProperty(e,'paused',{get:()=>pause,configurable:true});Object.defineProperty(e,'duration',{get:()=>112,configurable:true});e.play=()=>{pause=false;return Promise.resolve()};e.pause=()=>{pause=true}})()""")
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    t=lambda: round(pg.evaluate("document.querySelector('#player').currentTime"),1)
    print('blocs:',pg.evaluate("shown.map(b=>[Math.round(b.start),Math.round(b.end)])"))
    pg.evaluate("document.querySelector('#player').currentTime=70"); pg.wait_for_timeout(300)
    pg.click('#first'); pg.wait_for_timeout(500); print('Début: 70 ->',t())
    pg.evaluate("document.querySelector('#player').currentTime=10"); pg.wait_for_timeout(300)
    pg.click('#fwd'); pg.wait_for_timeout(300); print('+10 s: 10 ->',t())
    pg.evaluate("document.querySelector('#player').currentTime=10"); pg.wait_for_timeout(300)
    pg.click('#next'); pg.wait_for_timeout(500); print('Suivant (réplique): 10 ->',t(),'| page',pg.evaluate("page"))
    pg.click('#prev'); pg.wait_for_timeout(500); print('Précédent:',t())
    print('erreurs',errs); b.close()
