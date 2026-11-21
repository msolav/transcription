import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for th in ['ink','']:
        pg=b.new_page(viewport=dict(width=1440,height=800)); install(pg); pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
        if th: pg.evaluate("document.documentElement.dataset.vm='ink'")
        pg.click('#sepafter'); pg.wait_for_timeout(1200); pg.screenshot(path=f'/tmp/tr/panel{th}.png',clip=dict(x=600,y=0,width=840,height=420))
    b.close()
