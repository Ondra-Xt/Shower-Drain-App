import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time
import sys

class ViegaPricingBotProtected:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def search_megabad(self, page, query):
        search_term = f"Viega {query}"
        print(f"\n   ➡️ Hledám: {search_term}", file=sys.stderr)
        try:
            page.goto("https://www.megabad.com/", timeout=40000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            
            try:
                page.evaluate("""() => { 
                    ['CybotCookiebotDialog', 'usercentrics-root'].forEach(id => { 
                        let el = document.getElementById(id); if(el) el.remove(); 
                    }); document.body.style.overflow = 'auto'; 
                }""")
            except: pass

            search_box = page.locator('input[type="search"], input[name="search"], .search-input').first
            search_box.fill(search_term)
            search_box.press("Enter")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            return True
        except: return False

    def get_color_and_material(self, text, h1):
        text_l, h1_l = text.lower(), h1.lower()
        color, material = "", ""
        
        if "v4a" in text_l or "1.4404" in text_l: material = "Edelstahl V4A"
        elif "kunststoff" in text_l: material = "Kunststoff"
        
        if "schwarz" in h1_l or "schwarz" in text_l: color = "Schwarz"
        elif "champagner" in h1_l or "champagner" in text_l: color = "Champagner"
        elif "vergoldet" in h1_l or "gold" in text_l: color = "Gold"
        elif "kupfer" in h1_l or "kupfer" in text_l: color = "Kupfer"
        elif "matt" in h1_l or "gebürstet" in h1_l: color = "Edelstahl (Matt)"
        elif "glänzend" in h1_l or "poliert" in h1_l: color = "Edelstahl (Glänzend)"
        
        return color, material

    def is_empty(self, val):
        v = str(val).strip().lower()
        return v in ['nan', 'none', '', '--', 'nat']

    def run(self):
        if not os.path.exists(self.excel_path): 
            print("❌ Excel nenalezen!")
            return

        print("\n" + "="*60)
        print("🚀 Spouštím KROK 2: Viega Pricing Bot (DOBRÉ CENY + PŘÍSNÉ SKU)")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        df_tech['Component_SKU'] = df_tech['Component_SKU'].astype(str).str.replace('.0', '', regex=False).str.strip()
        
        is_viega = df_tech['Manufacturer'].astype(str).str.strip() == 'Viega'
        skus_to_search = df_tech[is_viega]['Component_SKU'].dropna().unique()
        
        for col in ['Length_mm', 'Flow_Rate_l_s', 'Material_V4A', 'Color', 'Is_Cuttable']:
            if col not in df_tech.columns: df_tech[col] = ""

        market_prices = []
        updates_made = 0
        prices_found = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()

            for target_sku in skus_to_search:
                target_sku = str(target_sku)
                if self.search_megabad(page, target_sku):
                    
                    if "-a-" not in page.url or ".htm" not in page.url:
                        target_url = None
                        
                        for link in page.locator(".product-box a, .product-wrapper a, .list-item a").all():
                            try:
                                href = link.get_attribute("href")
                                if href and "-a-" in href and ".htm" in href:
                                    target_url = "https://www.megabad.com" + href if href.startswith("/") else href
                                    break
                            except: pass
                        
                        if not target_url:
                            for link in page.locator("a").all():
                                try:
                                    href = link.get_attribute("href")
                                    if href and "-a-" in href and ".htm" in href and "suche" not in href.lower() and "login" not in href.lower():
                                        target_url = "https://www.megabad.com" + href if href.startswith("/") else href
                                        break
                                except: pass
                        
                        if target_url:
                            try:
                                page.goto(target_url, timeout=40000)
                                page.wait_for_load_state("networkidle", timeout=3000)
                                time.sleep(1.5)
                            except: pass
                        else:
                            print(f"      ⚠️ Přeskakuji: Na Megabadu nebyly nalezeny žádné relevantní produkty.", file=sys.stderr)
                            continue
                    
                    try:
                        page_text = page.locator("body").inner_text()
                        try: h1_text = page.locator("h1").first.inner_text().strip()
                        except: h1_text = "Neznámý produkt"
                        
                        # --- PŘÍSNÁ KONTROLA SKU (Obrana proti kódům 446567 a 737160) ---
                        clean_sku = target_sku.replace(" ", "")
                        clean_page_text = page_text.replace(" ", "").lower()
                        
                        in_title = clean_sku in h1_text.replace(" ", "").replace(".", "")
                        
                        # Hledáme, jestli je na stránce výslovně napsáno "Artikelnummer: 123456"
                        in_attributes = bool(re.search(r'(?:artikelnummer|hersteller-nr|art\.-nr|hersteller-artikelnummer)[\s.:]*' + clean_sku, clean_page_text))
                        
                        if not (in_title or in_attributes):
                            print(f"      ⚠️ Přeskakuji: Falešný výsledek (Kód {target_sku} není hlavní produkt této stránky).", file=sys.stderr)
                            continue
                        # ------------------------------------------------------------------

                        # --- ÚSPĚŠNÁ EXTRAKCE CENY Z PŮVODNÍHO KÓDU ---
                        price, uvp = "", ""
                        
                        try:
                            meta_price = page.locator('meta[itemprop="price"], [itemprop="price"]').first
                            if meta_price.count() > 0:
                                val = meta_price.get_attribute("content")
                                if not val: 
                                    val = meta_price.inner_text().replace("€", "").replace("*", "").strip()
                                if val:
                                    val = re.sub(r'[^\d,.-]', '', val)
                                    if ',' in val and '.' in val: val = val.replace('.', '').replace(',', '.')
                                    elif ',' in val: val = val.replace(',', '.')
                                    price = str(float(val))
                        except: pass

                        if not price:
                            buy_box = page.locator(".buy-box, .product-info, #product-detail").first
                            search_text = buy_box.inner_text() if buy_box.count() > 0 else page_text[:2000]
                            search_text = search_text.replace('\xa0', ' ')
                            clean_text = " ".join([l for l in search_text.split('\n') if 'sparen' not in l.lower() and 'ersparnis' not in l.lower()])
                            
                            all_prices = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:€|EUR)', clean_text)
                            prices_float = []
                            for p_str in all_prices:
                                try: prices_float.append(float(p_str.replace('.', '').replace(',', '.')))
                                except: pass

                            if prices_float:
                                prices_float = sorted(list(set(prices_float)), reverse=True) 
                                if len(prices_float) >= 2: 
                                    uvp, price = str(prices_float[0]), str(prices_float[1]) 
                                elif len(prices_float) == 1: 
                                    price = str(prices_float[0])

                        # --- Zápis nalezené ceny ---
                        if price:
                            market_prices.append({
                                "Component_SKU": target_sku, "Eshop_Source": "Megabad",
                                "Found_Price_EUR": float(price), "Original_Price_EUR": uvp,
                                "Price_Breakdown": "Single", "Product_URL": page.url, 
                                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            prices_found += 1

                        # Extrakce chybějících parametrů (ochrana proti přepsání)
                        length, is_cuttable = "", ""
                        text_l = page_text.lower()
                        
                        if "vario" in text_l:
                            length = "300 - 1200" 
                            is_cuttable = "Yes"
                        else:
                            m_len = re.search(r'\b(70|80|90|100|120)\s*cm', text_l)
                            if m_len: 
                                length = str(int(m_len.group(1)) * 10)
                                if "cleviva" in text_l: is_cuttable = "Yes" 

                        flow_rate = ""
                        flows = re.findall(r'(\d+(?:[.,]\d+)?)\s*l/s', text_l)
                        if flows:
                            flows_float = sorted(list(set([float(f.replace(',', '.')) for f in flows])))
                            valid_flows = [str(f) for f in flows_float if 0.3 <= f <= 1.5]
                            if valid_flows: flow_rate = " / ".join(valid_flows)

                        color, material = self.get_color_and_material(page_text, h1_text)

                        info = [f"Cena: {price} €" + (f" (UVP: {uvp} €)" if uvp else "")] if price else ["❌ Cenu se nepodařilo přečíst"]
                        
                        existing_mask = df_tech['Component_SKU'].astype(str) == target_sku
                        if existing_mask.any():
                            row_idx = df_tech.index[existing_mask].tolist()[0]
                            changed = False

                            if flow_rate and self.is_empty(df_tech.at[row_idx, 'Flow_Rate_l_s']):
                                df_tech.at[row_idx, 'Flow_Rate_l_s'] = flow_rate
                                info.append(f"+Průtok")
                                changed = True
                                
                            if length and self.is_empty(df_tech.at[row_idx, 'Length_mm']):
                                df_tech.at[row_idx, 'Length_mm'] = length
                                df_tech.at[row_idx, 'Is_Cuttable'] = is_cuttable if is_cuttable else "No"
                                info.append(f"+Délka")
                                changed = True
                                
                            if material and self.is_empty(df_tech.at[row_idx, 'Material_V4A']):
                                df_tech.at[row_idx, 'Material_V4A'] = material
                                changed = True
                                
                            if color and self.is_empty(df_tech.at[row_idx, 'Color']):
                                df_tech.at[row_idx, 'Color'] = color
                                info.append(f"+Barva")
                                changed = True
                                
                            if changed: updates_made += 1
                            
                            print(f"      ✅ {target_sku}: {', '.join(info)}", file=sys.stderr)

                    except Exception as e:
                        print(f"      ❌ Chyba u {target_sku}: {e}", file=sys.stderr)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if market_prices:
                df_prices_new = pd.DataFrame(market_prices)
                try:
                    df_prices_old = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    skus = [p["Component_SKU"] for p in market_prices]
                    df_prices_old = df_prices_old[~((df_prices_old['Component_SKU'].isin(skus)) & (df_prices_old['Eshop_Source'] == 'Megabad'))]
                    df_prices_combined = pd.concat([df_prices_old, df_prices_new], ignore_index=True)
                    df_prices_combined.to_excel(writer, sheet_name="Market_Prices", index=False)
                except:
                    df_prices_new.to_excel(writer, sheet_name="Market_Prices", index=False)

        print(f"\n✅ Hotovo! Nalezeno {prices_found} správných cenových záznamů.")

if __name__ == "__main__":
    ViegaPricingBotProtected().run()