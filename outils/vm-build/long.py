import os
HERE = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0,HERE)
import harness as H
from harness import *
t=' '.join(f"Phrase numéro {i} qui parle de choses et d'autres pour remplir la page." for i in range(160))
H.JOB['blocks']=[dict(H.blocks[0],start=0,end=720,text=t)]; H.JOB['duration']=720
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e)+(e.stack or '')[:400])); install(pg)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
    pg.set_input_files('#file',os.path.join(HERE, 'meeting.wav')); pg.click('#go'); pg.wait_for_timeout(5500)
    print(pg.evaluate("[document.querySelectorAll('.turn').length, document.querySelector('#pgn').textContent]"))
    for i in range(3):
        pg.mouse.move(600,500); pg.mouse.wheel(0,200); pg.wait_for_timeout(1200)
    pg.screenshot(path='long.png'); print(pg.evaluate("document.querySelector('#pg').textContent"), errs)
    b.close()
