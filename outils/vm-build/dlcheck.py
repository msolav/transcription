import os,sys,json; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import harness as H
from harness import *
errs=[]; reqs=[]
MOD=dict(modeles=[dict(cle='voxceleb_resnet',nom='Multilingue ResNet34',mo=25.3,famille='multi',note='Bon compromis.',poids=1.4,telecharge=True),
                  dict(cle='voxceleb_resnet293',nom='Multilingue ResNet293',mo=109.0,famille='multi',note='Le plus profond.',poids=4.6,telecharge=False)],defaut='voxceleb_resnet',nettoyeurs=[],nettoyeur_defaut='')
etat=dict(n=0)
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); pg.on('pageerror',lambda e:errs.append(str(e))); install(pg)
    J=lambda d: dict(status=200,content_type='application/json',body=json.dumps(d))
    pg.route('**/api/models',lambda r,q:r.fulfill(**J(dict(MOD,modeles=[dict(m,telecharge=True) if (etat['n']>=3 and m['cle']=='voxceleb_resnet293') else m for m in MOD['modeles']]))))
    pg.route('**/api/models?*',lambda r,q:r.fulfill(**J(dict(MOD,modeles=[dict(m,telecharge=True) if (etat['n']>=3 and m['cle']=='voxceleb_resnet293') else m for m in MOD['modeles']]))))
    pg.route('**/api/models/voxceleb_resnet293/telecharger',lambda r,q:(reqs.append('POST'),r.fulfill(**J(dict(etat='en_cours',recu=0,total=114000000))))[1])
    def e(r,q):
        etat['n']+=1; n=etat['n']
        r.fulfill(**J(dict(etat='pret') if n>=3 else dict(etat='en_cours',recu=n*40000000,total=114000000)))
    pg.route('**/api/models/voxceleb_resnet293/etat',e)
    pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
    pg.click('summary:has-text("Plus d\'options")'); pg.wait_for_timeout(500)
    print('bouton caché pour « Choisir pour moi »:', not pg.is_visible('#embgetwrap'))
    pg.evaluate("document.querySelector('#emb').value='voxceleb_resnet293'; document.querySelector('#emb').dispatchEvent(new Event('change'))"); pg.wait_for_timeout(500)
    print('bouton visible:',pg.is_visible('#embget'),'|',pg.inner_text('#embget'))
    pg.click('#embget'); pg.wait_for_timeout(900); print('progression:',pg.inner_text('#embst'))
    pg.wait_for_timeout(2600); print('après la fin: bouton caché:', not pg.is_visible('#embgetwrap'),'| POST envoyé:',reqs)
    print('champs ajoutés visibles:',pg.is_visible('#stt'),pg.is_visible('#vocab'),'| valeur par défaut stt:',pg.evaluate("document.querySelector('#stt').value"))
    pg.fill('#vocab','Karina, Marcello'); pg.screenshot(path='/tmp/tr/opts.png'); print('erreurs:',errs,'| débordement',pg.evaluate("document.documentElement.scrollHeight-innerHeight"))
    b.close()
