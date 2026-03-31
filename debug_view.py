from playwright.sync_api import sync_playwright
import time

def run():
    print("Spouštím prohlížeč...")
    # headless=False znamená, že uvidíš okno prohlížeče
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        url = "https://www.megabad.com/hersteller-kaldewei-duschrinnen-flowline-zero-a-1358942.htm"
        
        print(f"Jdu na stránku: {url}")
        page.goto(url)
        
        # Počkáme 10 vteřin, aby ses mohl podívat, co se děje
        print("Čekám 10 vteřin... (podívej se do otevřeného okna)")
        time.sleep(10)
        
        # Zkusíme cvičně najít nadpis a cenu
        try:
            title = page.locator("h1").first.inner_text()
            print(f"VIDÍM NADPIS: {title}")
        except:
            print("NEVIDÍM NADPIS (H1)")
            
        # Uděláme screenshot pro jistotu
        page.screenshot(path="co_vidi_robot.png")
        print("Screenshot uložen jako 'co_vidi_robot.png'")
        
        browser.close()
        print("Hotovo.")

if __name__ == "__main__":
    run()