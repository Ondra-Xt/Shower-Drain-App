from playwright.sync_api import sync_playwright
import time

def debug_geberit_catalog():
    print("🕵️‍♂️ DEBUG: Inspekce Geberit Katalogu...")
    # Zkusíme hledat CleanLine80
    url = "https://catalog.geberit.de/de-DE/search/?q=CleanLine80"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"🌍 Jdu na: {url}")
        page.goto(url, timeout=60000)
        
        # 1. Cookies (zkusíme zavřít, aby nezacláněly)
        try:
            page.wait_for_selector("button#onetrust-accept-btn-handler", timeout=3000)
            page.locator("button#onetrust-accept-btn-handler").click()
            print("🍪 Cookies zavřeny.")
        except:
            print("ℹ️ Cookie banner zmizel nebo nebyl nalezen.")

        print("⏳ Čekám 5 sekund na načtení výsledků...")
        time.sleep(5)
        
        # 2. Výpis všech odkazů na stránce
        print("\n📋 NALEZENÉ ODKAZY (LINKS):")
        print("="*60)
        
        links = page.locator("a").all()
        count = 0
        for link in links:
            if not link.is_visible(): continue
            try:
                txt = link.inner_text().strip()
                href = link.get_attribute("href")
                # Vypíšeme jen ty zajímavé (obsahující 'product' nebo '154')
                if href and ("/product/" in href or "154" in href or "CleanLine" in txt):
                    print(f"LINK: Text='{txt}' | Href='{href}'")
                    count += 1
            except: continue
            
        print("="*60)
        print(f"Celkem nalezeno {count} relevantních odkazů.")
        
        # 3. Screenshot pro jistotu
        page.screenshot(path="debug_geberit_view.png")
        print("📸 Screenshot uložen jako 'debug_geberit_view.png'")
        
        browser.close()

if __name__ == "__main__":
    debug_geberit_catalog()