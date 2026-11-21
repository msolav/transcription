import os,sys; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from harness import *
with sync_playwright() as p:
    b=p.chromium.launch(channel='chrome'); pg=b.new_page(viewport=dict(width=1440,height=900)); install(pg); pg.goto(ORIGIN+'/'); pg.wait_for_timeout(1200)
    v=lambda: pg.evaluate("[document.querySelector('#count').value, document.querySelector('#sep').getAttribute('aria-checked')]")
    print('start',v())
    pg.click('#numchips button[data-v="6"]',force=True); pg.wait_for_timeout(500); print('chip 6 while off ->',v())
    pg.click('#sep'); pg.wait_for_timeout(500); print('switch off ->',v())
    b.close()
