import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time
import sys

class TecePricingBotProtected:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def search_megabad(self, page, query):
        search_term = f"{query}"
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
        elif "edelstahl" in text_l: material = "Edelstahl"
        
        if "schwarz" in h1_l or "schwarz" in text_l: color = "Schwarz"
        elif "champagner" in h1_l or "champagner" in text_l: color = "Champagner"
        elif "vergoldet" in h1_l or "gold" in text_l: color = "Gold"
        elif "kupfer" in h1_l or "kupfer" in text_l: color = "Kupfer"
        elif "matt" in h1_l or "gebürstet" in h1_l: color = "Edelstahl (Matt)"
        elif "glänzend" in h1_l or "poliert" in h1_l: color = "Edelstahl (Glänzend)"
        elif "weiß" in h1_l or "weiss" in text_l: color = "Weiß"
        
        return color, material

    def is_empty(self, val):
        v = str(val).strip().lower()
        return v in ['nan', 'none', '', '--', 'nat', 'tbd', 'tece komponent']

    def extract_price(self, text):
        if not text: return None
        val = text.replace("€", "").replace("*", "").strip()
        val = re.sub(r'[^\d,.-]', '', val)
        if ',' in val and '.' in val: val = val.replace('.', '').replace(',', '.')
        elif ',' in val: val = val.replace(',', '.')
        try: return float(val)
        except: return None

    def run(self):
        if not os.path.exists(self.excel_path): 
            print("❌ Excel nenalezen!")
            return

        print("\n" + "="*60)
        print("🚀 Spouštím: TECE Pricing Bot (FINÁLNÍ SKALPEL + ANTI-GRUNDPREIS)")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        
        col_brand = df_tech.columns[0]
        col_name = df_tech.columns[1]
        col_sku = df_tech.columns[2]
        col_length = df_tech.columns[4]
        
        df_tech[col_sku] = df_tech[col_sku].astype(str).str.replace('.0', '', regex=False).str.strip()
        
        for col in ['Color', 'Material_V4A', 'Is_Cuttable', 'Length_mm', 'Flow_Rate_l_s']:
            if col not in df_tech.columns: df_tech[col] = ""
            df_tech[col] = df_tech[col].astype(object)
        
        is_tece = df_tech[col_brand].astype(str).str.strip() == 'TECE'
        skus_to_search = df_tech[is_tece][col_sku].dropna().unique()

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
                    
                    target_url = None
                    if "suche" not in page.url.lower():
                        target_url = page.url
                    else:
                        for link in page.locator(".product-box a, .product-wrapper a, .list-item a, .product-card a").all():
                            try:
                                href = link.get_attribute("href")
                                if href and target_sku.lower() in href.lower():
                                    if "set" not in href.lower() or "set" in target_sku.lower():
                                        target_url = "https://www.megabad.com" + href if href.startswith("/") else href
                                        break
                            except: pass
                        
                        if not target_url:
                            for link in page.locator(".product-box a, .product-wrapper a, .list-item a, .product-card a").all():
                                try:
                                    href = link.get_attribute("href")
                                    if href and target_sku.lower() in href.lower():
                                        target_url = "https://www.megabad.com" + href if href.startswith("/") else href
                                        break
                                except: pass

                    if target_url:
                        try:
                            if page.url != target_url:
                                page.goto(target_url, timeout=40000)
                                page.wait_for_load_state("networkidle", timeout=3000)
                                time.sleep(1.5)
                        except: pass
                    else:
                        print(f"      ⚠️ Přeskakuji: Na Megabadu nebyly nalezeny relevantní produkty.", file=sys.stderr)
                        continue
                    
                    try:
                        page_text = page.locator("body").inner_text()
                        try: h1_text = page.locator("h1").first.inner_text().strip()
                        except: h1_text = "Neznámý produkt"

                        clean_sku = target_sku.replace(" ", "")
                        clean_page_text = page_text.replace(" ", "").lower()
                        
                        in_title = clean_sku in h1_text.replace(" ", "").replace(".", "")
                        in_attributes = bool(re.search(r'(?:artikelnummer|hersteller-nr|art\.-nr|hersteller-artikelnummer)[\s.:]*' + clean_sku, clean_page_text))
                        
                        if not (in_title or in_attributes):
                            print(f"      ⚠️ Přeskakuji: Falešný výsledek (Kód {target_sku} není hlavní produkt).", file=sys.stderr)
                            continue

                        # ========================================================
                        # EXTRAKCE CENY - VERZE SKALPEL
                        # ========================================================
                        price, uvp = "", ""

                        # 1. TABULKA VARIANT (Nejspolehlivější pro položky s více délkami)
                        table_row = page.locator(f"tr:has-text('{target_sku}')").first
                        if table_row.is_visible(timeout=500):
                            row_text = table_row.inner_text().replace('\xa0', ' ')
                            prices_in_row = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', row_text)
                            v_prices = []
                            for p_str in prices_in_row:
                                val = self.extract_price(p_str)
                                if val and val > 0.5: v_prices.append(val)
                            
                            if v_prices:
                                v_prices_sorted = sorted(list(set(v_prices)))
                                price = str(v_prices_sorted[0]) # Menší v řádku = Prodejní
                                if len(v_prices_sorted) > 1:
                                    uvp = str(v_prices_sorted[-1]) # Větší v řádku = UVP

                        # 2. META TAGY (Extrémně přesné)
                        if not price:
                            try:
                                meta_price = page.locator('meta[itemprop="price"]').first
                                if meta_price.count() > 0:
                                    val = meta_price.get_attribute("content")
                                    if val:
                                        p_val = self.extract_price(val)
                                        if p_val and p_val > 0.5: price = str(p_val)
                            except: pass

                        # 3. TEXTOVÁ ANALÝZA S POKROČILÝM ČIŠTĚNÍM
                        if not price:
                            buy_box = page.locator('.product-detail-buy, .buy-box, .product-info, #product-detail').first
                            if buy_box.is_visible(timeout=500):
                                bb_text = buy_box.inner_text().replace('\xa0', ' ')
                            else:
                                bb_text = page_text[:1500].replace('\xa0', ' ')

                            # --- NOVÉ ČIŠTĚNÍ JEDNOTKOVÝCH CEN A ZÁVOREK ---
                            # Smaže závorky s cenou (např. "(34,39 € / m)")
                            bb_text = re.sub(r'\(\s*\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:€|EUR).*?\)', '', bb_text, flags=re.IGNORECASE)
                            # Smaže cenu s lomítkem (např. "34,39 € / m" nebo "34,39 € / Stk")
                            bb_text = re.sub(r'\d{1,3}(?:\.\d{3})*,\d{2}\s*(?:€|EUR)\s*/\s*[a-zA-Z]+', '', bb_text, flags=re.IGNORECASE)

                            bb_text = re.sub(r'Bei Zahlung per Vorkasse.*?zahlen dann nur[^\d]*(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:€|EUR)?', '', bb_text, flags=re.IGNORECASE|re.DOTALL)
                            bb_text = re.sub(r'Ihre Ersparnis.*?€', '', bb_text, flags=re.IGNORECASE|re.DOTALL)

                            clean_lines = []
                            bad_words = ['versand', 'zzgl', 'exkl', 'netto', 'sparen', 'ersparnis', 'rabatt', 'vorkasse', 'skonto', 'zahlen dann nur']
                            for line in bb_text.split('\n'):
                                l_low = line.lower()
                                if any(bw in l_low for bw in bad_words) or '%' in l_low:
                                    continue
                                clean_lines.append(line)
                            
                            clean_bb = " ".join(clean_lines)

                            # Explicitní UVP
                            uvp_match = re.search(r'(?:UVP|Statt)[^\d]*(\d{1,3}(?:\.\d{3})*,\d{2})', clean_bb, re.IGNORECASE)
                            if uvp_match:
                                u_val = self.extract_price(uvp_match.group(1))
                                if u_val and u_val > 0.5: uvp = str(u_val)

                            # Hledání platné ceny
                            all_prices = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:€|EUR)', clean_bb)
                            valid_prices = []
                            for p_str in all_prices:
                                val = self.extract_price(p_str)
                                if val and val > 0.5:
                                    if not uvp or str(val) != uvp:
                                        valid_prices.append(val)
                            
                            if valid_prices:
                                valid_prices = sorted(list(set(valid_prices)))
                                price = str(valid_prices[0]) # Nejnižší CENA, která NENÍ UVP ani Netto
                            elif uvp and not price:
                                price = uvp
                                uvp = ""

                        # 4. FIX UVP PŘES CSS (Když nám UVP chybí)
                        if not uvp:
                            try:
                                uvp_el = page.locator('.price-standard, .price-uvp, del, .buy-box .uvp').first
                                if uvp_el.is_visible(timeout=500):
                                    u_val = self.extract_price(uvp_el.inner_text())
                                    if u_val and u_val > 0.5 and str(u_val) != price:
                                        uvp = str(u_val)
                            except: pass

                        # Finální kontrola
                        if price and uvp:
                            if float(price) > float(uvp):
                                price, uvp = uvp, price # Prohodíme, UVP musí být vyšší
                            elif float(price) == float(uvp):
                                uvp = ""

                        # ========================================================

                        if price:
                            market_prices.append({
                                "Component_SKU": target_sku, "Eshop_Source": "Megabad",
                                "Found_Price_EUR": float(price), "Original_Price_EUR": uvp,
                                "Price_Breakdown": "Single", "Product_URL": page.url, 
                                "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            prices_found += 1

                        length, is_cuttable = "", ""
                        text_l = page_text.lower()
                        
                        m_len = re.search(r'\b(70|80|90|100|120|150)\s*cm', text_l)
                        if m_len: 
                            length = str(int(m_len.group(1)) * 10)
                        elif re.search(r'(\d{3,4})\s*mm', h1_text):
                            length = re.search(r'(\d{3,4})\s*mm', h1_text).group(1)

                        color, material = self.get_color_and_material(page_text, h1_text)

                        info = [f"Cena: {price} €" + (f" (UVP: {uvp} €)" if uvp else "")] if price else ["❌ Cenu se nepodařilo přečíst"]
                        
                        existing_mask = df_tech[col_sku].astype(str) == target_sku
                        if existing_mask.any():
                            row_idx = df_tech.index[existing_mask].tolist()[0]
                            changed = False

                            if self.is_empty(df_tech.at[row_idx, col_name]):
                                df_tech.at[row_idx, col_name] = h1_text
                                changed = True
                                
                            if length and self.is_empty(df_tech.at[row_idx, col_length]):
                                df_tech.at[row_idx, col_length] = length
                                info.append(f"+Délka")
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
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
    MASTER_EXCEL = os.path.join(base_dir, "benchmark_master_v3_fixed.xlsx")
    
    bot = TecePricingBotProtected(excel_path=MASTER_EXCEL)
    bot.run()