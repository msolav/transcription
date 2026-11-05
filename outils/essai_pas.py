"""Le parcours des clés : un pas par fenêtre, sans défilement."""
import glob, sys
from playwright.sync_api import sync_playwright

U = "http://127.0.0.1:7991/"
ech = []
def ok(n, c, d=""):
    print(f"  {'OK ' if c else 'ÉCHEC'} {n}" + (f" — {d}" if d and not c else ""))
    if not c: ech.append(n)

sh = sorted(glob.glob('/Users/solav/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-*/chrome-headless-shell'))[-1]

def deborde(pg):
    return pg.evaluate("document.documentElement.scrollHeight - innerHeight")

with sync_playwright() as p:
    nav = p.chromium.launch(executable_path=sh)
    for w, h in ((1440, 900), (1280, 720), (390, 844)):
        ctx = nav.new_context(viewport={"width": w, "height": h}, locale="fr-CA")
        pg = ctx.new_page(); err = []
        pg.on("pageerror", lambda e: err.append(str(e)))
        pg.goto(U, wait_until="networkidle"); pg.wait_for_timeout(1500)
        print(f"\n{w}×{h}")
        ok("l'écran des clés s'ouvre seul", pg.locator(".setup").count() == 1)
        ok("une barre de progrès, pas des puces", pg.locator(".setupbar i").count() == 1)
        ok("un bouton Retour", pg.locator(".backbtn").count() == 1)
        ok("aucun défilement (intro)", deborde(pg) == 0, str(deborde(pg)))

        # intro -> pas 1
        pg.locator('[data-x="suivant"]').click(); pg.wait_for_timeout(1100)
        txt = pg.locator("#ecran").text_content()
        ok("le pas 1 parle de Groq", "GROQ" in pg.locator("#ecran h2").text_content().upper(), txt[:80])
        ok("le compteur s'affiche", "1 / 4" in pg.locator("#setuptop").text_content(),
           pg.locator("#setuptop").text_content())
        ok("une seule phrase, un seul geste", pg.locator(".geste").count() == 1)
        ok("un gros bouton d'action", pg.locator(".gros").count() >= 1)
        ok("un « i » pour le détail", pg.locator("#ecran .info").count() == 1,
           str(pg.locator("#ecran .info").count()))
        ok("aucun défilement (pas 1)", deborde(pg) == 0, str(deborde(pg)))
        part = float(pg.evaluate("getComputedStyle(document.querySelector('.setupbar i')).transform.split(',')[0].replace('matrix(','')"))
        ok("la barre a avancé", 0 < part < 1, str(part))

        if w == 1440:
            pg.screenshot(path="pas1.png")
            # avancer jusqu'au champ
            pg.locator('[data-x="suivant"]').click(); pg.wait_for_timeout(1000)   # j'y suis déjà
            pg.locator('[data-x="suivant"]').click(); pg.wait_for_timeout(1000)   # c'est fait
            pg.locator('[data-x="suivant"]').click(); pg.wait_for_timeout(1000)   # c'est fait
            ok("on arrive au champ de la clé", pg.locator("#keyinput").count() == 1)
            ok("le champ a le focus", pg.evaluate("document.activeElement.id") == "keyinput",
               pg.evaluate("document.activeElement.id"))
            ok("aucun défilement au focus", deborde(pg) == 0, str(deborde(pg)))
            ok("compteur 4 / 4", "4 / 4" in pg.locator("#setuptop").text_content(),
               pg.locator("#setuptop").text_content())
            pg.screenshot(path="pas4.png")
            # une clé refusée doit s'afficher dans le même cadre
            pg.fill("#keyinput", "pas-une-cle")
            pg.click("#keysave"); pg.wait_for_timeout(2500)
            msg = pg.locator("#keyerr").text_content()
            ok("une clé invalide est refusée en place", len(msg) > 10, msg[:60])
            ok("le refus est en français", "clé" in msg.lower(), msg[:60])
            ok("aucun défilement après l'erreur", deborde(pg) == 0, str(deborde(pg)))
            print("      refus :", msg[:90])
            # Retour
            pg.locator(".backbtn").click(); pg.wait_for_timeout(1000)
            ok("Retour remonte d'un pas", "3 / 4" in pg.locator("#setuptop").text_content(),
               pg.locator("#setuptop").text_content())
            # Échap aussi
            pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
            ok("Échap remonte aussi", "2 / 4" in pg.locator("#setuptop").text_content(),
               pg.locator("#setuptop").text_content())
        ok("aucune erreur JS", not err, str(err[:1]))
        ctx.close()
    nav.close()

print(f"\n{'PARCOURS CONFORME' if not ech else str(len(ech)) + ' PROBLÈME(S)'}")
sys.exit(1 if ech else 0)
