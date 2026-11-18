import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for w,h in [(1440,900),(1280,720),(1920,1080)]:
        pg=b.new_page(viewport=dict(width=w,height=h)); install(pg); pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.wait_for_timeout(1500)
        s=[]
        for act in ['', "document.querySelector('.more summary').click()","document.querySelector('#sep').click()"]:
            if act: pg.evaluate(act)
            pg.wait_for_timeout(1500)
            s.append(pg.evaluate("[getComputedStyle(document.querySelector('.giant.got')).fontSize, document.querySelector('#capture').firstElementChild.style.zoom||getComputedStyle(document.querySelector('#dropzone')).zoom, document.documentElement.scrollHeight-innerHeight]"))
        print(w,h,s); pg.screenshot(path=f'/tmp/tr/s{w}.png')
    b.close()
