import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.set_default_timeout(6000); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg); st['hold']=True; pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.wait_for_timeout(800); pg.click('#go'); pg.wait_for_timeout(1500)
    pg.click('#verbosebtn',force=True); pg.wait_for_timeout(1500)
    print(pg.evaluate("[document.querySelector('#verbose').innerText.slice(0,200), document.querySelector('#eta').textContent, document.documentElement.scrollHeight-innerHeight]"))
    pg.screenshot(path='/tmp/tr/verb.png'); b.close()
print(errs)
