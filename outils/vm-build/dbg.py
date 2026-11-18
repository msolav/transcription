import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome');errs=[]; pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:print('ERR',e)); st=install(pg); st['hold']=True; pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.wait_for_timeout(800)
    ov=lambda: pg.evaluate("document.documentElement.scrollHeight-innerHeight")
    print('before go',ov()); pg.click('#go'); pg.wait_for_timeout(2500); print('running',ov()); pg.screenshot(path='/tmp/tr/run.png')
    print(pg.evaluate("[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().bottom>innerHeight+1&&getComputedStyle(e).position!='fixed').slice(0,6).map(e=>e.tagName+'#'+e.id+'.'+e.className+' '+Math.round(e.getBoundingClientRect().bottom))"))
    pg.evaluate("document.querySelector('#verbosebtn').click()"); pg.wait_for_timeout(1500); print('verbose',ov()); pg.screenshot(path='/tmp/tr/run2.png'); print(pg.evaluate("(()=>{let o=[],e=document.querySelector('#verbose');while(e&&e!==document.documentElement){const r=e.getBoundingClientRect(),c=getComputedStyle(e);o.push(e.tagName+'#'+e.id+'.'+e.className+' x'+Math.round(r.x)+' w'+Math.round(r.width)+' pos:'+c.position+' tr:'+c.translate+' zoom:'+c.zoom);e=e.parentElement}return o})()")); print(pg.evaluate("[scrollY, document.body.className, document.querySelector('#verbose').getBoundingClientRect().toJSON(), document.querySelector('#capture').getBoundingClientRect().toJSON()]")); b.close()
