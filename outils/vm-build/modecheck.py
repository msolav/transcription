import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
H.JOB['speakers']=H.JOB['speakers'][:1]
for b in H.JOB['blocks']: b['speaker']=H.JOB['speakers'][0]['id']
errs=[]
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    def essai(mode):
        pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); st=install(pg, mode=None); sent=[]
        pg.on('request',lambda r: sent.append(r.post_data or '') if r.url.endswith('/api/jobs') and r.method=='POST' else None)
        J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
        pg.route('**/enrolement/preparer',lambda r,q:r.fulfill(status=202,content_type='application/json',body='{"id":"j1"}'))
        pg.route('**/enrolement/classer',lambda r,q:r.fulfill(**J(dict(propositions=[dict(index=0,start=5,end=12,text='Bonjour',suggestion='',conf=0,motif='diversite')],rapport=dict(personnes=[],etat='debut',part_incertaine=None,secondes={})))))
        pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1000)
        defaut=pg.evaluate("document.querySelector('#vmode .on').dataset.m")
        if mode!='défaut': pg.click(f'#vmode [data-m="{mode}"]'); pg.wait_for_timeout(900)
        vis=pg.evaluate("[document.querySelector('#vauto').classList.contains('open'), document.querySelector('#count').value, document.querySelector('#sep').classList.contains('on')]")
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(7500)
        diar=any('name="diarize"' in x and 'true' in x.split('name="diarize"')[1][:20] for x in sent)
        ouvert=pg.evaluate("document.body.classList.contains('aide-on')")
        print(f"mode {mode:7} (défaut={defaut}) | réglages auto visibles={vis[0]} count={vis[1]} | séparation demandée={diar} | identification ouverte toute seule={ouvert} | débordement {pg.evaluate('document.documentElement.scrollHeight-innerHeight')}")
        if mode=='défaut': pg.screenshot(path='/tmp/tr/mode_aide.png')
        pg.close()
    for m in ['défaut','aucune','auto']: essai(m)
    # écran d'accueil avec le mode « Automatique »
    pg=b.new_page(viewport=dict(width=1440,height=900)); install(pg, mode=None); pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900); pg.click('#vmode [data-m="auto"]'); pg.wait_for_timeout(1100); pg.screenshot(path='/tmp/tr/mode_auto.png'); pg.close()
    b.close()
print('erreurs:',errs)
