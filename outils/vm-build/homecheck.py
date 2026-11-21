import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
S=lambda i: dict(id=f's{i}',fichier=f'Rencontre {i}.m4a',duree=5600,voix=6,audio_present=True,octets=150e6,touche_le='2026-11-17T18:37:00Z',relue=False)
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for w,h,n in [(1440,900,2),(1280,720,2),(1440,900,4),(1280,720,0)]:
        pg=b.new_page(viewport=dict(width=w,height=h)); install(pg)
        pg.route('**/api/seances',lambda r,q:r.fulfill(status=200,content_type='application/json',body=json.dumps(dict(seances=[S(i) for i in range(n)],total_octets=1.2e9,octets_son=201e6))))
        pg.goto(ORIGIN+'/'); pg.wait_for_timeout(700)
        pg.add_script_tag(path=os.path.join(os.path.dirname(__file__),'..','..','transcripteur','static','seances.js')); pg.wait_for_timeout(1300)
        r=pg.evaluate("(()=>{const t=document.querySelector('.giant.ask .a').getBoundingClientRect(),bar=document.querySelector('#bar').getBoundingClientRect(),l=document.querySelector('.tr-sc');return [Math.round(t.top),Math.round(bar.bottom),l?l.querySelectorAll('li').length:0,document.documentElement.scrollHeight-innerHeight]})()")
        print(w,h,'seances',n,'-> titre top',r[0],'/ bas du bandeau',r[1],'/ lignes',r[2],'/ débordement',r[3]); pg.screenshot(path=f'/tmp/tr/home_{h}_{n}.png'); pg.close()
    b.close()
