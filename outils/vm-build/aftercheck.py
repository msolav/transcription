import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
full=dict(H.JOB); one=dict(H.JOB, speakers=H.JOB['speakers'][:1])
H.JOB.clear(); H.JOB.update(one)
errs=[]; posted=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg)
    def voix(route,req):
        posted.append(req.post_data[:80] if req.post_data else ''); H.JOB.clear(); H.JOB.update(full); st['polls']=0
        route.fulfill(status=202,content_type='application/json',body='{"id":"j1"}')
    pg.route('**/api/jobs/j1/voix',voix)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1000)
    pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(5500)
    print('button visible', pg.is_visible('#sepafter'))
    pg.click('#sepafter'); pg.wait_for_timeout(900); pg.click('#afterchips button[data-v="3"]'); pg.screenshot(path='/tmp/tr/after1.png',clip=dict(x=0,y=0,width=1100,height=330))
    pg.click('#sepgo'); pg.wait_for_timeout(600); print('status shown', pg.is_visible('#status'))
    pg.wait_for_timeout(4500)
    print('doc back', pg.is_visible('#doc'), 'button hidden now', not pg.is_visible('#sepafter'), 'posted', posted, 'overflow', pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
print(errs)
