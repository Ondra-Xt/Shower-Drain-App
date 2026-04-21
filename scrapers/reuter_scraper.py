from playwright.sync_api import sync_playwright
from models.product import Product
import json
import time
import re

class ReuterScraper:
    def __init__(self):
        pass

    def scrape(self, url: str):
        print(f"🕵️‍♂️ Infiltruji Reuter (Detailista): {url}")
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, 
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="de-DE",
                timezone_id="Europe/Berlin"
            )
            page = context.new_page()
            
            try:
                try:
                    page.goto(url, timeout=60000)
                except: pass

                print("\n🛑 POZOR: ROBOT ČEKÁ NA TEBE 🛑")
                try:
                    page.locator("h1").first.wait_for(state="visible", timeout=0)
                except:
                    return []
                time.sleep(2)

                title = "Neznámý produkt"
                if page.locator("h1").count() > 0:
                    title = page.locator("h1").first.text_content().strip()
                print(f"📦 Nadpis: {title}")
                
                # Záchranný manévr
                if "kaldewei" not in title.lower():
                    print("🚨 PŘESMĚROVÁNÍ! Hledám ručně...")
                    page.goto(f"https://www.reuter.de/search?q=Kaldewei+Flowline+Zero+900")
                    time.sleep(3)
                    
                    try:
                        page.wait_for_selector("a[href*='/p/']", timeout=10000)
                        all_links = page.locator("a[href*='/p/']").all()
                        target = None
                        for link in all_links:
                            lt = link.text_content().lower()
                            if "kaldewei" in lt and "flow" in lt:
                                target = link
                                break
                        
                        if target:
                            target.click()
                            page.locator("h1").first.wait_for(state="visible", timeout=30000)
                            title = page.locator("h1").first.text_content().strip()
                            print(f"📦 Nový nadpis: {title}")
                        else:
                            return []
                    except: return []

                # Stahování ceny
                final_price = 0.0
                original_price = None
                breakdown_text = "Pouze hlavní produkt"

                # JSON
                scripts = page.locator('script[type="application/ld+json"]').all()
                found_json = False
                for script in scripts:
                    try:
                        data = json.loads(script.text_content())
                        items = data if isinstance(data, list) else [data]
                        for item in items:
                            if item.get('@type') == 'Product':
                                offers = item.get('offers', {})
                                if isinstance(offers, list): offers = offers[0]
                                p_val = float(str(offers.get('price', 0)))
                                if p_val > 0:
                                    final_price = p_val
                                    found_json = True
                                break
                    except: continue
                    if found_json: break

                # HTML Fallback
                if final_price == 0:
                    text = page.locator("body").inner_text()
                    matches = re.findall(r'(\d{1,4}[.,]\d{2})\s*(?:€|EUR)', text)
                    prices = [float(m.replace('.', '').replace(',', '.')) for m in matches if 20 < float(m.replace('.', '').replace(',', '.')) < 5000]
                    if prices:
                        u = sorted(list(set(prices)), reverse=True)
                        final_price = u[1] if len(u) >= 2 else u[0]
                        if len(u) >= 2: original_price = u[0]

                # Sifon
                print("➕ Hledám sifon...")
                price_els = page.locator("text=/\\d+[.,]\\d{2}\\s*€/").all()
                siphon_price = 0.0
                keywords = ["ablauf", "siphon", "garnitur", "ka 90"]

                for el in price_els:
                    try:
                        if not el.is_visible(): continue
                        txt = el.inner_text()
                        m = re.search(r'(\d{1,4}[.,]\d{2})', txt)
                        if not m: continue
                        val = float(m.group(1).replace('.', '').replace(',', '.'))
                        if 80.0 < val < 350.0 and abs(val - final_price) > 1.0:
                             parent = el.locator("..").inner_text().lower()
                             if any(k in parent for k in keywords):
                                 siphon_price = val
                                 print(f"   -> Sifon: {val} EUR")
                                 break
                    except: continue

                if siphon_price > 0:
                    final_price += siphon_price
                    # Zapíšeme složení
                    breakdown_text = f"Kryt ({final_price - siphon_price}) + Sifon ({siphon_price})"
                    title += " (Set)"

                if final_price > 0:
                    product = Product(
                        name=title,
                        price=final_price,
                        original_price=original_price,
                        url=url,
                        price_breakdown=breakdown_text # Ukládáme
                    )
                    results.append(product)

            except Exception as e:
                print(f"💥 Chyba: {e}")
            finally:
                time.sleep(2)
                browser.close()
                
        return results