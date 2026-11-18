import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for w,h in [(1000,700),(1440,900),(2000,865)]:
        pg=b.new_page(viewport=dict(width=w,height=h)); st=install(pg); st['hold']=True; pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelector('#eta').textContent='Encore environ 6 min · fin vers 05:42 PM'; document.querySelector('#verbosebtn').click()"); pg.wait_for_timeout(1500)
        print(w,h,pg.evaluate("(()=>{const a=document.querySelector('#eta').getBoundingClientRect(),v=document.querySelector('#verbose').getBoundingClientRect();return [Math.round(a.right),Math.round(v.left),a.right<=v.left]})()"))
    b.close()
