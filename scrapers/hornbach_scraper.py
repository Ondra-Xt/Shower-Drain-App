from playwright.sync_api import sync_playwright
from models.product import Product
import re

class HornbachScraper:
    def __init__(self):
        pass

    def scrape(self, url: str):
        print(f"🔨 Jdu makat na Hornbach: {url}")
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(url, timeout=60000)
                try:
                    page.locator("button[data-testid='cookie-accept-all-btn']").click(timeout=2000)
                except: pass

                title = "Neznámý produkt"
                if page.locator("h1").count() > 0:
                    title = page.locator("h1").first.text_content().strip()
                print(f"📦 Název: {title}")

                print("💰 Hledám ceny komponent...")
                page_text = page.locator("body").inner_text()
                matches = re.findall(r'(\d{1,4}[.,]\d{2})', page_text)
                
                valid_prices = []
                for m in matches:
                    try:
                        clean = m.replace(',', '.')
                        if clean.count('.') > 1: clean = clean.replace('.', '', 1)
                        val = float(clean)
                        if 30.0 < val < 800.0:
                            valid_prices.append(val)
                    except: continue
                
                final_price = 0.0
                breakdown_text = None  # Tady budeme ukládat text "X + Y"

                if valid_prices:
                    u = sorted(list(set(valid_prices)), reverse=True)
                    print(f"   -> Nalezené ceny: {u}")
                    
                    main_price = u[0]
                    siphon_price = 0.0
                    
                    # Logika detekce
                    remaining_prices = []
                    if len(u) >= 2:
                        ratio = u[1] / u[0]
                        if ratio > 0.8: # Ceny jsou si blízké = UVP + Sleva
                            print(f"   -> {u[0]} vypadá jako UVP. Hlavní cena je {u[1]}.")
                            main_price = u[1]
                            remaining_prices = u[2:]
                            breakdown_text = f"Hlavní cena: {main_price}"
                        else:
                            # Ceny daleko od sebe = Rošt + Něco
                            main_price = u[0]
                            remaining_prices = u[1:]
                            breakdown_text = f"Rošt: {main_price}"
                    else:
                        remaining_prices = u[1:]
                        breakdown_text = f"Cena: {main_price}"

                    # Hledáme sifon
                    for p in remaining_prices:
                        if 50.0 < p < 300.0:
                            siphon_price = p
                            print(f"   -> Sifon nalezen: {siphon_price}")
                            break
                    
                    if siphon_price > 0:
                        final_price = main_price + siphon_price
                        # Zapíšeme si, co jsme sečetli
                        breakdown_text = f"Rošt ({main_price}) + Sifon ({siphon_price})"
                        print(f"🧩 Složení: {breakdown_text}")
                    else:
                        final_price = main_price
                
                if final_price > 0:
                    product = Product(
                        name=title,
                        price=final_price,
                        url=url,
                        price_breakdown=breakdown_text # Ukládáme složení
                    )
                    results.append(product)

            except Exception as e:
                print(f"💥 Chyba: {e}")
            finally:
                browser.close()
                
        return results