import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for th in ['ink','']:
        pg=b.new_page(viewport=dict(width=1440,height=500)); install(pg); pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1000)
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
        if th: pg.evaluate("document.documentElement.dataset.vm='ink'")
        pg.click('#savemenu'); pg.wait_for_timeout(1500); pg.screenshot(path=f'/tmp/tr/bar{th}.png',clip=dict(x=0,y=0,width=1100,height=80))
    b.close()
