from playwright.sync_api import sync_playwright
import time
import re
import os

class ReuterTesterV8:
    def __init__(self):
        self.sku = "154.150.00.1"
        self.brand = "Geberit"
        # Cesta pro uložení dat prohlížeče (vytvoří se složka v aktuálním adresáři)
        self.user_data_dir = os.path.join(os.getcwd(), "reuter_user_data")

    def clean_price(self, text):
        if not text: return None
        clean_text = text.lower().replace("reuter", "").replace("preis", "").replace("€", "").strip()
        if re.search(r'\d+,\d{2}', clean_text):
            clean_text = clean_text.replace(".", "").replace(",", ".")
        match = re.search(r'(\d+\.?\d*)', clean_text)
        if match: return float(match.group(1))
        return None

    def run(self):
        print(f"🚀 Startuji Reuter Tester v8 s trvalým profilem...")
        
        with sync_playwright() as p:
            # Spouštíme prohlížeč s uživatelskými daty
            # Pokud se objeví Captcha, vyřeš ji a příště už by se neměla objevit
            context = p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized'
                ],
                locale="de-DE",
                viewport={"width": 1920, "height": 1080}
            )
            
            page = context.pages[0] if context.pages else context.new_page()

            print("🌍 Otevírám reuter.de...")
            page.goto("https://www.reuter.de/", timeout=90000)

            # --- MANUÁLNÍ ZÁSAH ---
            print("🛑 Nyní máš čas vyřešit Captchu nebo bannery přímo v prohlížeči.")
            print("👉 Jakmile uvidíš hlavní stránku Reuter, skript bude pokračovat.")
            
            # Čekáme, dokud se neobjeví vyhledávací ikona nebo input (znamení, že jsme prošli)
            try:
                page.wait_for_selector(".header-search__toggle, input#search", timeout=60000)
            except:
                print("⚠️ Stránka se nenačetla včas. Zkus ji v okně obnovit (F5).")
                page.pause() # Tady se skript zastaví a můžeš ladit

            # --- HLEDÁNÍ ---
            query = f"{self.brand} {self.sku}"
            print(f"🔍 Vyhledávám: {query}")
            
            try:
                # Zkusíme přímo input, pokud není, tak přes lupu
                search_input = page.locator("input#search, input[name='q']").first
                if not search_input.is_visible():
                    page.locator(".header-search__toggle, .icon-search").first.click()
                    time.sleep(1)
                
                search_input.click()
                search_input.fill("") # Vymazat
                search_input.type(query, delay=100)
                page.keyboard.press("Enter")
                
                page.wait_for_load_state("networkidle")
                time.sleep(5)
                
                # Výběr produktu
                product = page.locator("a.product-link, .product-card a, article a").first
                if product.is_visible():
                    product.click()
                    time.sleep(3)
                    
                    # Cena
                    price_el = page.locator(".reuter-price, span[data-testid='product-price']").first
                    if price_el.is_visible():
                        val = self.clean_price(price_el.text_content())
                        print(f"🎉 ÚSPĚCH! CENA: {val} €")
                    else:
                        print("⚠️ Cena nenalezena na detailu.")
                else:
                    print("❌ Produkt nenalezen.")
                    
            except Exception as e:
                print(f"❌ Chyba během interakce: {e}")
                page.pause()

            print("🏁 Zavírám za 10s (data profilu zůstanou uložena)...")
            time.sleep(10)
            context.close()

if __name__ == "__main__":
    tester = ReuterTesterV8()
    tester.run()