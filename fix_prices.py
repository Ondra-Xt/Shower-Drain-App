import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time

class PricingAgentV29:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_screens"): os.makedirs("debug_screens")

    def get_components_to_price(self):
        if not os.path.exists(self.excel_path): return []
        try:
            df_bom = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            items = df_bom[["Component_SKU", "Component_Name"]].dropna().drop_duplicates()
            tasks = []
            for _, row in items.iterrows():
                sku = str(row["Component_SKU"]).strip()
                name = str(row["Component_Name"])
                brand = ""
                if "Geberit" in name: brand = "Geberit"
                elif "TECE" in name: brand = "TECE"
                elif "Hansgrohe" in name or "RainDrain" in name or "uBox" in name: brand = "Hansgrohe"
                elif "Kaldewei" in name: brand = "Kaldewei"
                elif "Alca" in name: brand = "Alca"
                tasks.append({"sku": sku, "brand": brand})
            return tasks
        except Exception as e:
            print(f"⚠️ Chyba Excel: {e}")
            return []

    def clean_price(self, text):
        if not text: return None
        clean_text = text.lower()
        clean_text = clean_text.replace("ihr preis", "").replace("preis", "").replace("stückpreis", "")
        clean_text = clean_text.replace("€", "").replace("eur", "").replace("ab", "").replace("von", "").replace("*", "").strip()
        
        if "uvp" in clean_text or "statt" in clean_text: return None 
        
        if re.search(r'\d+,\d{2}', clean_text): 
            clean_text = clean_text.replace(".", "").replace(",", ".")
        match = re.search(r'(\d+\.?\d*)', clean_text)
        if match:
            try: return float(match.group(1))
            except: return None
        return None

    def normalize_sku(self, sku):
        return str(sku).replace(".", "").replace(" ", "").strip()

    def handle_cookies(self, page):
        selectors = ["#onetrust-accept-btn-handler", "button:has-text('Alle akzeptieren')", ".cookie-box__button--accept"]
        for sel in selectors:
            try:
                if page.locator(sel).first.count() > 0:
                    page.locator(sel).first.click(force=True, timeout=500)
            except: pass

    def is_search_page(self, page, shop_name):
        """Detekuje, zda jsme na seznamu výsledků."""
        url = page.url
        if shop_name == "Hornbach":
            if "/s/" in url: return True
            if page.locator("article").count() > 1: return True
        elif shop_name == "Megabad":
            if "suche" in url or "search" in url: return True
            if page.locator(".search-result").count() > 0: return True
            # Pokud je tam hodně odkazů s obrázky, je to asi seznam
            if page.locator(".product-list-item").count() > 1: return True
        return False

    def extract_price_from_buybox(self, page):
        """Hledá cenu striktně uvnitř produktového kontejneru."""
        
        # 1. NAJDI KONTEJNER (BuyBox)
        # Pokud ho nenajde, NESMÍ hledat v body!
        buybox = None
        potential_boxes = [
            ".product-detail",          # Megabad hlavní
            ".product-main",            # Hornbach hlavní
            "#product-details", 
            "main",                     # HTML5 Main (bezpečné)
            ".buybox--price"
        ]
        
        for box in potential_boxes:
            if page.locator(box).count() > 0:
                buybox = page.locator(box).first
                break # Našli jsme nejlepší shodu
        
        if not buybox:
            # Pokud nenajdeme main kontejner, jsme asi na špatné stránce nebo na seznamu
            # Vracíme None, abychom nečetli nesmysly
            return None

        # 2. Selektory uvnitř BuyBoxu
        selectors = [
            "[data-testid='price-main']", 
            ".product-detail-price__price", 
            ".price__amount", 
            ".current-price-container",
            ".price-value",
            ".price-wrapper"
        ]
        
        for sel in selectors:
            if buybox.locator(sel).count() > 0:
                txt = buybox.locator(sel).first.text_content()
                val = self.clean_price(txt)
                if val:
                    print(f"      ✅ Cena (Selector '{sel}'): {val} €")
                    return val

        # 3. Textový sken (JEN UVNITŘ BUYBOXU)
        try:
            text = buybox.inner_text()
            matches = re.findall(r'(?:Preis|Stück|Aktuell).*?(\d{1,5}[.,]\d{2})\s*€?', text, re.IGNORECASE | re.DOTALL)
            if not matches:
                matches = re.findall(r'(\d{1,5}[.,]\d{2})\s*€', text)

            valid_prices = []
            for m in matches:
                val = self.clean_price(m)
                if val and 5 < val < 5000:
                    valid_prices.append(val)
            
            # Pokud najdeme víc cen, vezmeme tu nejnižší (často "ab X €") nebo první
            # Ale jsme v BuyBoxu, takže riziko chyby je malé
            if valid_prices:
                return valid_prices[0]
        except: pass
        return None

    def check_product_on_detail(self, page, sku, brand):
        try:
            # Rychlá kontrola - jsme vůbec na detailu?
            if self.is_search_page(page, "Megabad") or self.is_search_page(page, "Hornbach"):
                return None, "IsListPage"

            body_text = page.locator("body").inner_text().lower()
            
            if brand and brand.lower() not in body_text:
                return None, "BrandMismatch"

            sku_clean = self.normalize_sku(sku)
            found_sku = False
            
            if sku.lower() in body_text: found_sku = True
            elif sku_clean in self.normalize_sku(body_text): found_sku = True
            if sku_clean in page.url: found_sku = True
            
            try: 
                mpn = page.locator("meta[property='product:retailer_item_id']").get_attribute("content")
                if mpn and sku_clean in self.normalize_sku(mpn): found_sku = True
            except: pass

            if not found_sku:
                return None, "SkuMismatch"

            price = self.extract_price_from_buybox(page)
            if price: return price, "OK"
            
            return None, "PriceNotFound"
        except: return None, "Error"

    def search_manual(self, page, shop_name, query):
        print(f"🔍 {shop_name}: Hledám '{query}'...")
        try:
            if shop_name == "Hornbach":
                page.goto("https://www.hornbach.de/", timeout=60000)
                self.handle_cookies(page)
                if not page.locator("input[data-testid='search-input']").is_visible():
                     try: page.locator(".header-search-toggler").click(timeout=1000)
                     except: pass
                inp = page.locator("input[data-testid='search-input'], input[type='search']").first
                inp.click(force=True)
                inp.fill(query)
                page.keyboard.press("Enter")
                
            elif shop_name == "Megabad":
                page.goto("https://www.megabad.com/", timeout=60000)
                self.handle_cookies(page)
                time.sleep(2)
                found = False
                inputs = page.locator("input#search, input[name='q'], input[type='search']").all()
                if not inputs:
                    try: page.locator(".search-toggle, .header-search-icon").first.click(timeout=1000)
                    except: pass
                    time.sleep(1)
                    inputs = page.locator("input[type='text']").all()
                for inp in inputs:
                    if inp.is_visible():
                        inp.click(force=True)
                        inp.fill(query)
                        page.keyboard.press("Enter")
                        found = True
                        break
                if not found: return False
            
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4)
            return True
        except: return False

    def process_results(self, page, sku, brand, shop_name):
        # 1. JSME NA SEZNAMU? (STRICT CHECK)
        is_list = self.is_search_page(page, shop_name)
        
        if not is_list:
            # Pokud nejsme na seznamu, asi jsme na detailu -> Zkusíme cenu
            print("      📍 Vypadá to na detail produktu (nebo prázdnou stránku).")
            price, status = self.check_product_on_detail(page, sku, brand)
            if price: return price, page.url
        else:
            print("      🛑 Jsem na seznamu, hledání ceny PŘESKOČENO. Jdu na odkazy.")

        # 2. Hledání odkazů
        print("      📋 Procházím seznam...")
        product_links = []
        try:
            all_links = page.locator("a").all()
            for link in all_links:
                href = link.get_attribute("href")
                if not href or len(href) < 5: continue
                if any(x in href for x in ["javascript", "#", "login", "cart", "wishlist"]): continue
                
                is_candidate = False
                
                if shop_name == "Hornbach":
                    if "/p/" in href: is_candidate = True
                elif shop_name == "Megabad":
                    # MEGABAD FILTR:
                    # Hledáme "-a-" (Artikel)
                    # Ignorujeme "-k-" (Kategorie)
                    if "-a-" in href and "-k-" not in href:
                         is_candidate = True
                    # Záloha pro staré URL
                    elif "/product/" in href:
                         is_candidate = True

                if is_candidate:
                    if href.startswith("/"):
                         base = "https://www.hornbach.de" if shop_name == "Hornbach" else "https://www.megabad.com"
                         full = base + href
                    elif href.startswith("http"): full = href
                    else: continue
                    if full not in product_links: product_links.append(full)
        except: pass

        product_links = list(dict.fromkeys(product_links))
        
        # Prioritizace
        norm_sku = self.normalize_sku(sku)
        top = [l for l in product_links if norm_sku in l]
        rest = [l for l in product_links if l not in top]
        final_list = (top + rest)[:5]

        if not final_list:
            print("      ⚠️ Žádné odkazy.")
            return None, None

        print(f"      🔎 Zkouším {len(final_list)} odkazů...")

        for i, link in enumerate(final_list):
            print(f"      👉 ({i+1}) {link} ...")
            try:
                page.goto(link, timeout=20000)
                time.sleep(2)
                price, status = self.check_product_on_detail(page, sku, brand)
                if price: return price, link
                else: print(f"      ↪️ Nesedí ({status})")
            except: pass
            
        return None, None

    def run(self):
        tasks = self.get_components_to_price()
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            for task in tasks:
                sku = task['sku']
                brand = task['brand']
                query = f"{brand} {sku}".strip()
                
                shops = ["Hornbach", "Megabad"]
                if brand in ["Geberit", "TECE"]: shops = ["Megabad"]
                
                found = False
                for shop in shops:
                    if self.search_manual(page, shop, query):
                        p_val, u_val = self.process_results(page, sku, brand, shop)
                        if p_val:
                            results.append([sku, shop, p_val, "Single", u_val, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")])
                            found = True
                            break 
                
                if not found: print(f"❌ Nenalezeno: {brand} {sku}")

            browser.close()

        if results: self.save_prices(results)

    def save_prices(self, results):
        df_new = pd.DataFrame(results, columns=["Component_SKU", "Eshop_Source", "Found_Price_EUR", "Price_Breakdown", "Product_URL", "Timestamp"])
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            try: start_row = writer.sheets['Market_Prices'].max_row
            except: start_row = 0
            df_new.to_excel(writer, sheet_name="Market_Prices", index=False, header=(start_row == 0), startrow=start_row)
        print(f"✅ Uloženo {len(results)} cen.")

if __name__ == "__main__":
    agent = PricingAgentV29()
    agent.run()