import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
n={'k':0}
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
    pg.route('**/api/version',lambda r,q:r.fulfill(**J(dict(installee='1.3.0',publiee='v1.3.1',retard=True,url='https://x'))))
    def maj(r,q):
        if q.method=='POST': r.fulfill(**J(dict(etat='cours'))); return
        n['k']+=1; r.fulfill(**J(dict(etat='cours',octets=n['k']*20e6,total=100e6) if n['k']<4 else dict(etat='fini',nom='Transcripteur-macOS-AppleSilicon.zip')))
    pg.route('**/api/mise-a-jour',maj)
    pg.route('**/api/seances',lambda r,q:r.fulfill(**J([])))
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(800)
    pg.add_script_tag(path=os.path.join(os.path.dirname(__file__),'..','..','transcripteur','static','seances.js')); pg.wait_for_timeout(1500)
    print('banner', pg.is_visible('#tr-maj-go')); pg.click('#tr-maj-go'); pg.wait_for_timeout(1600); print(pg.inner_text('#tr-maj-etat'))
    pg.wait_for_timeout(3000); print(pg.inner_text('#tr-maj-etat')); pg.screenshot(path='/tmp/tr/maj.png'); print(errs, pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
