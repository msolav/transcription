import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome')
    for w,h in [(1000,700),(1440,900),(2000,1000),(2560,1300)]:
        pg=b.new_page(viewport=dict(width=w,height=h)); st=install(pg); st['hold']=True; pg.goto(ORIGIN+'/'); pg.wait_for_timeout(900)
        pg.set_input_files('#file','/tmp/tr/meeting.wav'); pg.click('#go'); pg.wait_for_timeout(1200)
        pg.evaluate("document.querySelector('#verbosebtn').click(); clearInterval(poll)")
        for txt in ['8 %','88 %','100 %']:
            pg.evaluate(f"document.querySelector('#pct').textContent='{txt}'"); pg.wait_for_timeout(1300)
            r=pg.evaluate("""(()=>{const e=document.querySelector('#pct'),r=document.createRange();r.selectNodeContents(e);const t=r.getBoundingClientRect(),wr=document.querySelector('.pctwrap').getBoundingClientRect(),v=document.querySelector('#verbose').getBoundingClientRect(),fs=parseFloat(getComputedStyle(e).fontSize);
              return [Math.round(wr.width),Math.round(t.width),Math.round(fs),Math.round(t.right-wr.left),Math.round(v.left-wr.left),Math.round(t.height/(fs*0.8)*10)/10]})()""")
            print(f"{w}x{h} {txt:>5} | moitié {r[0]:>4}px, texte {r[1]:>4}px ({round(100*r[1]/r[0])} %), corps {r[2]:>4}px | sort de sa moitié: {r[3]>r[0]} | lignes {r[5]}")
        pg.screenshot(path=f'/tmp/tr/split_{w}.png'); pg.close()
    b.close()
