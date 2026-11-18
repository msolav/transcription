import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
posted=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    pg.on('request',lambda r: posted.append(r.post_data or '') if r.url.endswith('/api/jobs') and r.method=='POST' else None)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1000)
    pg.click('#vmode [data-m="auto"]'); pg.wait_for_timeout(1000)
    print('refine dimmed when sep off', pg.evaluate("getComputedStyle(document.querySelector('.refine')).opacity"))
    pg.wait_for_timeout(300); print('opacity when on', pg.evaluate("getComputedStyle(document.querySelector('.refine')).opacity"))
    pg.click('#refine'); pg.wait_for_timeout(500); pg.screenshot(path='/tmp/tr/refine.png')
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(1500)
    print('raffiner posted', any('name="raffiner"' in x for x in posted), 'errs', errs, 'overflow', pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
