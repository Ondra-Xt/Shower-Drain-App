import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time

class PricingAgentV42:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_screens"): os.makedirs("debug_screens")
        if not os.path.exists("debug_html"): os.makedirs("debug_html")

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
        if "spar" in clean_text or "sie sparen" in clean_text: return None
        if "monat" in clean_text or "rate" in clean_text: return None 
        # UVP zde mazat nebudeme, protože ho teď chceme hledat, 
        # ale funkce clean_price má vracet jen číslo.
        
        clean_text = clean_text.replace("ihr preis", "").replace("preis", "").replace("stückpreis", "")
        clean_text = clean_text.replace("€", "").replace("eur", "").replace("ab", "").replace("von", "").replace("*", "").strip()
        
        # Odstraníme slova UVP/Statt pro extrakci čísla
        clean_text = clean_text.replace("uvp", "").replace("statt", "").replace("doporučená", "")

        if re.search(r'\d+,\d{2}', clean_text): 
            clean_text = clean_text.replace(".", "").replace(",", ".")
        match = re.search(r'(\d+\.?\d*)', clean_text)
        if match:
            try: return float(match.group(1))
            except: return None
        return None

    def normalize_sku(self, sku):
        return str(sku).replace(".", "").replace("-", "").replace(" ", "").strip().lower()

    def handle_cookies(self, page):
        selectors = [
            "#onetrust-accept-btn-handler", 
            "button:has-text('Alle akzeptieren')", 
            ".cookie-box__button--accept",
            "button[data-testid='uc-accept-all-button']"
        ]
        for sel in selectors:
            try:
                if page.locator(sel).first.is_visible():
                    page.locator(sel).first.click(force=True, timeout=500)
                    time.sleep(0.5)
            except: pass

    def is_search_page(self, page, shop_name):
        url = page.url.lower()
        if "/s/" in url or "suche" in url or "search" in url: return True
        if shop_name == "Hornbach" and page.locator("article").count() > 1: return True
        if shop_name == "Megabad" and (page.locator(".search-result").count() > 0 or page.locator(".product-list-item").count() > 1): return True
        return False

    def validate_product_identity(self, page, target_sku, brand):
        url = page.url.lower()
        if "/s/" in url or "suche" in url or "search" in url: return False, "IsSearchPage"

        target_clean = self.normalize_sku(target_sku)
        try: h1 = page.locator("h1").first.inner_text().lower()
        except: h1 = ""
        body_text = page.locator("body").inner_text().lower()

        if brand.lower() not in body_text: return False, "BrandMismatch"

        if target_clean in self.normalize_sku(url): return True, "OK_UrlMatch"
        if target_clean in self.normalize_sku(h1): return True, "OK_TitleMatch"
        try:
            mpn = page.locator("meta[property='product:retailer_item_id']").get_attribute("content")
            if mpn and target_clean in self.normalize_sku(mpn): return True, "OK_MetaMatch"
        except: pass

        try:
            rows = page.locator("tr, .product-features li, dl, .data-row").all()
            for row in rows:
                row_text = self.normalize_sku(row.inner_text())
                if target_clean in row_text:
                    return True, "OK_TableMatch"
        except: pass

        if target_clean in self.normalize_sku(body_text):
             return True, "OK_LooseTextMatch"

        return False, f"SkuMismatch (Hledal: {target_sku})"

    def extract_price_ultimate(self, page):
        """Hledá PRODEJNÍ cenu."""
        # 1. Meta
        try:
            meta_price = page.locator("meta[itemprop='price']").get_attribute("content")
            if meta_price:
                val = float(meta_price.replace(",", "."))
                if val > 1: return val
        except: pass

        # 2. JSON-LD
        try:
            scripts = page.locator("script[type='application/ld+json']").all()
            for s in scripts:
                content = s.text_content()
                if '"price":' in content:
                    match = re.search(r'"price":\s*"?(\d+\.?\d*)"?', content)
                    if match:
                        val = float(match.group(1))
                        if val > 1: return val
        except: pass

        # 3. Selektory
        selectors = [
            "[data-testid='price-main']", ".price-large", ".product-detail-price__price", 
            ".current-price-container", ".price--content", ".price__amount", "#product-price", ".final-price"
        ]
        
        main_area = page.locator("main, .product-detail, #content").first
        if main_area.count() == 0: main_area = page.locator("body")

        for sel in selectors:
            if main_area.locator(sel).count() > 0:
                txt = main_area.locator(sel).first.text_content()
                val = self.clean_price(txt)
                if val and val > 1: return val
        return None

    def extract_original_price(self, page, selling_price):
        """Hledá PŮVODNÍ cenu (UVP/RRP/Statt), která musí být vyšší než prodejní."""
        if not selling_price: return None
        
        # Selektory pro přeškrtnutou cenu
        old_price_selectors = [
            ".old-price", ".price-strike", ".price--line-through", 
            ".product-price--crossed", ".uvp-price", ".regular-price"
        ]
        
        main_area = page.locator("main, .product-detail, #content").first
        if main_area.count() == 0: main_area = page.locator("body")

        # 1. Zkusíme selektory
        for sel in old_price_selectors:
            if main_area.locator(sel).count() > 0:
                txt = main_area.locator(sel).first.text_content()
                val = self.clean_price(txt)
                if val and val > selling_price:
                    return val

        # 2. Zkusíme Regex v textu (Hledáme "UVP", "statt", "Doporučená")
        try:
            text = main_area.inner_text()
            # Regex pro: Slovo "UVP/statt" ... nějaké znaky ... číslo
            patterns = [
                r'UVP.*?(\d{1,5}[.,]\d{2})',
                r'statt.*?(\d{1,5}[.,]\d{2})',
                r'Doporučená.*?(\d{1,5}[.,]\d{2})',
                r'Bisher.*?(\d{1,5}[.,]\d{2})'
            ]
            
            for pat in patterns:
                matches = re.findall(pat, text, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    val = self.clean_price(m)
                    # Musí být vyšší než prodejní cena (např. o víc než 2 EUR)
                    if val and val > selling_price + 2:
                        return val
        except: pass
        
        return None

    def process_results(self, page, sku, brand, shop_name):
        if not self.is_search_page(page, shop_name):
            valid, status = self.validate_product_identity(page, sku, brand)
            if valid:
                print(f"      📍 Rovnou správný detail ({status}).")
                price = self.extract_price_ultimate(page)
                if price:
                    orig_price = self.extract_original_price(page, price)
                    if orig_price: print(f"         🏷️ Původní cena: {orig_price} € (Sleva: {round((1-price/orig_price)*100)}%)")
                    return price, orig_price, page.url
            else:
                 print(f"      📍 Není to správný detail ({status}). Jdu na odkazy.")

        print("      📋 Procházím seznam výsledků...")
        product_links = []
        try:
            all_links = page.locator("a").all()
            for link in all_links:
                href = link.get_attribute("href")
                if not href or len(href) < 5: continue
                if any(x in href for x in ["javascript", "#", "login", "cart", "wishlist", "bewertung"]): continue
                
                is_candidate = False
                if shop_name == "Hornbach" and "/p/" in href: is_candidate = True
                elif shop_name == "Megabad":
                    if ("-a-" in href or "/product/" in href) and "-k-" not in href: is_candidate = True

                if is_candidate:
                    if href.startswith("/"):
                         base = "https://www.hornbach.de" if shop_name == "Hornbach" else "https://www.megabad.com"
                         full = base + href
                    elif href.startswith("http"): full = href
                    else: continue
                    if full not in product_links: product_links.append(full)
        except: pass

        product_links = list(dict.fromkeys(product_links))
        
        norm_sku = self.normalize_sku(sku)
        top = [l for l in product_links if norm_sku in l]
        rest = [l for l in product_links if l not in top]
        final_list = (top + rest)[:12] 

        if not final_list:
            print("      ⚠️ Žádné odkazy.")
            return None, None, None

        print(f"      🔎 Nalezeno {len(final_list)} kandidátů. Iteruji...")

        for i, link in enumerate(final_list):
            print(f"      👉 ({i+1}/{len(final_list)}) {link} ...")
            try:
                page.goto(link, timeout=20000)
                time.sleep(2.5)
                self.handle_cookies(page)

                valid, status = self.validate_product_identity(page, sku, brand)
                
                if valid:
                    print(f"         ✅ SKU SHODA ({status})!")
                    price = self.extract_price_ultimate(page)
                    
                    if price: 
                        print(f"         💰 CENA: {price} €")
                        orig_price = self.extract_original_price(page, price)
                        if orig_price: 
                            print(f"         🏷️ Původní cena: {orig_price} €")
                        else:
                            print("         ℹ️ Původní cena nenalezena.")
                            
                        return price, orig_price, link
                    else:
                        print("         ⚠️ Produkt sedí, ale cena nenalezena.")
                        if "UrlMatch" in status or "TitleMatch" in status:
                            return None, None, link
                else:
                    print(f"         ❌ SKU NESEDÍ ({status}). Jdu na další...")
                    
            except Exception as e:
                print(f"         ☠️ Chyba: {e}")
            
        return None, None, None

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
                        p_val, o_val, u_val = self.process_results(page, sku, brand, shop)
                        if p_val:
                            # Přidána o_val (Original Price) do výsledků
                            results.append([sku, shop, p_val, o_val, "Single", u_val, datetime.datetime.now().strftime("%Y-%m-%d %H:%M")])
                            found = True
                            break 
                
                if not found: print(f"❌ Nenalezeno: {brand} {sku}")

            browser.close()

        if results: self.save_prices(results)

    def save_prices(self, results):
        # Přidán sloupec 'Original_Price_EUR'
        df_new = pd.DataFrame(results, columns=["Component_SKU", "Eshop_Source", "Found_Price_EUR", "Original_Price_EUR", "Price_Breakdown", "Product_URL", "Timestamp"])
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            try: start_row = writer.sheets['Market_Prices'].max_row
            except: start_row = 0
            df_new.to_excel(writer, sheet_name="Market_Prices", index=False, header=(start_row == 0), startrow=start_row)
        print(f"✅ Uloženo {len(results)} cen (včetně slev).")

if __name__ == "__main__":
    agent = PricingAgentV42()
    agent.run()