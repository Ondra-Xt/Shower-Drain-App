import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time
import sys
import requests
import io
import PyPDF2

class GeberitPricingV11_EdgeCase:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        # SLOVNÍK VÝJIMEK pro produkty s nestandardními PDF výkresy
        self.overrides = {
            "154.455.00.1": {
                "Length_mm": "188", 
                "Is_Cuttable": "No",
                "Color": "Edelstahl (Gebürstet/Poliert)" # Z PDF: Edelstahl gebürstet
            }
        }

    def cleanup_garbage(self):
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_t = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                df_t = df_t[(df_t['Manufacturer'] != 'Geberit') | (df_t['Component_SKU'].astype(str).str.startswith('154.'))].copy()
                is_g = df_t['Manufacturer'] == 'Geberit'
                
                for col in ['Color', 'Material_V4A', 'Length_mm', 'Flow_Rate_l_s', 'Is_Cuttable']:
                    if col in df_t.columns: df_t.loc[is_g, col] = ""
                
                df_t.to_excel(writer, sheet_name="Products_Tech", index=False)
                
                df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                is_valid_p = (df_prices['Eshop_Source'] != 'Megabad') | (df_prices['Component_SKU'].astype(str).str.startswith('154.'))
                df_prices = df_prices[is_valid_p].copy()
                df_prices.to_excel(writer, sheet_name="Market_Prices", index=False)
        except: pass

    def extract_data_from_pdf(self, pdf_url):
        data = {}
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(pdf_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                with io.BytesIO(response.content) as open_pdf_file:
                    reader = PyPDF2.PdfReader(open_pdf_file)
                    pdf_text = " ".join([p.extract_text() for p in reader.pages if p.extract_text()])
                    pdf_text_lower = pdf_text.lower()

                    m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', pdf_text_lower)
                    if m_flow:
                        val = float(m_flow.group(1).replace(',', '.'))
                        if 0.2 < val < 2.0: data['flow_rate'] = f"{val} l/s"
                    
                    m_color = re.search(r'(?:farbe|oberfläche|ausführung)[\s:]*([a-zäöüß,\s/]+)', pdf_text_lower)
                    if m_color:
                        color_val = m_color.group(1)
                        if "schwarz" in color_val: data['color'] = "Schwarz"
                        elif "champagner" in color_val: data['color'] = "Champagner"
                        elif "gebürstet" in color_val or "poliert" in color_val or "edelstahl" in color_val:
                            data['color'] = "Edelstahl (Gebürstet/Poliert)"

                    if "v4a" in pdf_text_lower or "1.4404" in pdf_text_lower: data['material'] = "Edelstahl V4A"
                    elif "edelstahl" in pdf_text_lower or "rostfrei" in pdf_text_lower: data['material'] = "Edelstahl V2A"

                    m_len_range = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*cm', pdf_text_lower)
                    if m_len_range:
                        data['length'] = f"{int(m_len_range.group(1)) * 10} - {int(m_len_range.group(2)) * 10}"
                        data['is_cuttable'] = "Yes"
                    else:
                        m_len_single = re.search(r'(?:l|länge)[\s=:]*(\d{2,3})\s*cm', pdf_text_lower)
                        if m_len_single:
                            val = int(m_len_single.group(1))
                            if val in [90, 130, 160]:
                                data['length'] = f"300 - {val * 10}"
                                data['is_cuttable'] = "Yes"
                            else:
                                data['length'] = str(val * 10)
        except: pass 
        return data

    def nuke_megabad_cookies(self, page):
        try:
            page.evaluate("""() => { ['CybotCookiebotDialog', 'CybotCookiebotDialogBodyUnderlay', 'usercentrics-root'].forEach(id => { let el = document.getElementById(id); if(el) el.remove(); }); document.body.style.overflow = 'auto'; }""")
        except: pass

    def search_megabad(self, page, query):
        print(f"\n   ➡️ Hledám: {query}", file=sys.stderr)
        try:
            page.goto("https://www.megabad.com/", timeout=40000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            self.nuke_megabad_cookies(page)
            search_box = page.locator('input[type="search"], input[name="search"], input[name="q"], .search-input').first
            search_box.fill(query)
            search_box.press("Enter")
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            self.nuke_megabad_cookies(page) 
            return True
        except: return False

    def run(self):
        if not os.path.exists(self.excel_path): return

        self.cleanup_garbage()

        print("\n" + "="*60)
        print("🚀 Spouštím Geberit Pricing V11.4 (The Edge-Case Handler)")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        geberit_skus_to_search = df_tech[df_tech['Manufacturer'] == 'Geberit']['Component_SKU'].dropna().unique()
        
        for col in ['Length_mm', 'Flow_Rate_l_s', 'Height_Adjustability', 'Material_V4A', 'Color']:
            if col in df_tech.columns: df_tech[col] = df_tech[col].astype(str).replace('nan', '')
        if 'Color' not in df_tech.columns: df_tech['Color'] = ""

        market_prices = []
        new_discovered_products = []
        updates_made = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for target_sku in geberit_skus_to_search:
                if self.search_megabad(page, target_sku):
                    url = page.url.lower()
                    target_links = []
                    
                    if "suche" in url or "search" in url:
                        links = page.locator("a").all()
                        for link in links:
                            try:
                                href = link.get_attribute("href")
                                if href and "-a-" in href and href.endswith(".htm") and "suche" not in href and "geberit" in href.lower():
                                    full_link = href if href.startswith("http") else "https://www.megabad.com" + href
                                    if full_link not in target_links: target_links.append(full_link)
                            except: pass
                        target_links = target_links[:5] 
                    else:
                        target_links.append(page.url)

                    if not target_links: continue

                    for product_url in target_links:
                        try:
                            page.goto(product_url, timeout=30000)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(1)
                            
                            try: h1_text = page.locator("h1").first.inner_text().strip()
                            except: h1_text = "Neznámý produkt"

                            if "inkl." in h1_text.lower() or "bündel" in h1_text.lower() or "set" in h1_text.lower()[-4:]: continue 

                            page_text = page.locator("body").inner_text()
                            page_text_lower = page_text.lower()
                            
                            m_sku = re.search(r'(?:artikelnummer|art\.-nr\.|hersteller-artikelnummer)[\s:]*([0-9]{3}\.[0-9]{3}\.[a-zA-Z0-9]{2,3}\.[0-9]|[0-9]{3}\.[0-9]{3}\.[0-9]{2}\.[0-9])', page_text, re.IGNORECASE)
                            if m_sku: found_sku = m_sku.group(1).upper()
                            else:
                                m_sku_h1 = re.search(r'([0-9]{3}\.[0-9]{3}\.[a-zA-Z0-9]{2,3}\.[0-9]|[0-9]{3}\.[0-9]{3}\.[0-9]{2}\.[0-9])', h1_text)
                                found_sku = m_sku_h1.group(1).upper() if m_sku_h1 else ""
                            
                            if not found_sku: continue
                            is_siphon = "154.15" in found_sku or "rohbauset" in h1_text.lower()

                            # === ZÍSKÁNÍ CENY ===
                            price, uvp = "", ""
                            buy_box = page.locator(".product-info, .buy-box, #product-detail").first
                            search_text = buy_box.inner_text() if buy_box.is_visible(timeout=2000) else page_text[:1500]
                            
                            clean_lines = [l for l in search_text.split('\n') if 'sparen' not in l.lower() and 'ersparnis' not in l.lower()]
                            clean_text = " ".join(clean_lines)

                            all_prices = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', clean_text)
                            prices_float = []
                            for p_str in all_prices:
                                try: prices_float.append(float(p_str.replace('.', '').replace(',', '.')))
                                except: pass

                            if prices_float:
                                prices_float = sorted(list(set(prices_float)), reverse=True) 
                                if len(prices_float) >= 2: uvp, price = str(prices_float[0]), str(prices_float[1]) 
                                elif len(prices_float) == 1: price = str(prices_float[0])

                            if price:
                                market_prices.append({
                                    "Component_SKU": found_sku, "Eshop_Source": "Megabad",
                                    "Found_Price_EUR": price, "Original_Price_EUR": uvp,
                                    "Price_Breakdown": "Single", "Product_URL": product_url, 
                                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                })

                            # === ZÁPLATA DAT ===
                            existing_mask = df_tech['Component_SKU'].astype(str).str.upper() == found_sku
                            
                            current_flow, current_length, current_material, current_color = "", "", "", ""
                            if existing_mask.any():
                                current_flow = str(df_tech.loc[existing_mask, 'Flow_Rate_l_s'].values[0]).replace('nan', '')
                                current_length = str(df_tech.loc[existing_mask, 'Length_mm'].values[0]).replace('nan', '')
                                current_material = str(df_tech.loc[existing_mask, 'Material_V4A'].values[0]).replace('nan', '')
                                if 'Color' in df_tech.columns: current_color = str(df_tech.loc[existing_mask, 'Color'].values[0]).replace('nan', '')

                            flow_rate, length, is_cuttable, material, color = "", "", "No", "", ""
                            
                            if not is_siphon:
                                if "v4a" in page_text_lower or "1.4404" in page_text_lower: material = "Edelstahl V4A"
                                elif "edelstahl" in page_text_lower or "nerez" in page_text_lower: material = "Edelstahl V2A"
                                
                                if "schwarz" in h1_text.lower(): color = "Schwarz"
                                elif "champagner" in h1_text.lower(): color = "Champagner"
                                elif "gebürstet" in h1_text.lower() or "poliert" in h1_text.lower(): color = "Edelstahl (Gebürstet/Poliert)"
                                
                                if not color:
                                    m_col = re.search(r'(?:farbe|oberfläche|ausführung)[^\:]*:\s*([a-zäöüß\s/]+)', page_text_lower)
                                    if m_col:
                                        val = m_col.group(1)
                                        if "schwarz" in val: color = "Schwarz"
                                        elif "champagner" in val: color = "Champagner"
                                        elif "gebürstet" in val or "poliert" in val or "edelstahl" in val: color = "Edelstahl (Gebürstet/Poliert)"

                                m_len_range = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*cm', page_text_lower)
                                if m_len_range:
                                    length = f"{int(m_len_range.group(1)) * 10} - {int(m_len_range.group(2)) * 10}"
                                    is_cuttable = "Yes"
                                else:
                                    m_len_single = re.search(r'(?:länge|l\s*=|l\s*:)\s*(\d{2,3})\s*cm', page_text_lower)
                                    if m_len_single:
                                        val = int(m_len_single.group(1))
                                        if val in [90, 130, 160]:
                                            length = f"300 - {val * 10}"
                                            is_cuttable = "Yes"
                                        else:
                                            length = str(val * 10)

                            if is_siphon:
                                m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', page_text_lower)
                                if m_flow:
                                    val = float(m_flow.group(1).replace(',', '.'))
                                    if 0.2 < val < 2.0: flow_rate = f"{val} l/s"

                            needs_pdf = False
                            if is_siphon and not current_flow and not flow_rate: needs_pdf = True
                            if not is_siphon and not current_length and not length: needs_pdf = True

                            if needs_pdf:
                                pdf_links = [link.get_attribute("href") for link in page.locator("a").all() if link.get_attribute("href") and (".pdf" in link.get_attribute("href").lower() or "datenblatt" in link.inner_text().lower())]
                                for pdf_url in list(set(pdf_links))[:2]:
                                    print(f"      📄 Čtu PDF Datasheet...", file=sys.stderr)
                                    pdf_data = self.extract_data_from_pdf(pdf_url if pdf_url.startswith("http") else "https://www.megabad.com" + pdf_url)
                                    
                                    if not flow_rate and 'flow_rate' in pdf_data: flow_rate = pdf_data['flow_rate']
                                    if not length and 'length' in pdf_data and not is_siphon: 
                                        length = pdf_data['length']
                                        is_cuttable = pdf_data.get('is_cuttable', 'No')
                                    if not material and 'material' in pdf_data and not is_siphon: material = pdf_data['material']
                                    if not color and 'color' in pdf_data and not is_siphon: color = pdf_data['color']
                                    
                                    if (flow_rate or not is_siphon) and (length or is_siphon): break

                            # === APLIKACE VÝJIMEK (OVERRIDES) ===
                            if found_sku in self.overrides:
                                ovr = self.overrides[found_sku]
                                if "Length_mm" in ovr: length = ovr["Length_mm"]
                                if "Is_Cuttable" in ovr: is_cuttable = ovr["Is_Cuttable"]
                                if "Color" in ovr: color = ovr["Color"]
                                if "Material_V4A" in ovr: material = ovr["Material_V4A"]

                            # === ZÁPIS A VÝPIS DO TERMINÁLU ===
                            info = [f"Cena: {price} €" + (f" (UVP: {uvp} €)" if uvp else "")]
                            
                            final_flow = flow_rate if flow_rate else current_flow
                            final_length = length if length else current_length
                            final_color = color if color else current_color
                            final_material = material if material else current_material

                            if is_siphon and final_flow: info.append(f"Průtok: {final_flow}")
                            if not is_siphon and final_length: info.append(f"Délka: {final_length} mm")
                            if not is_siphon and final_color: info.append(f"Barva: {final_color}")
                            if not is_siphon and final_material: info.append(f"Mat: {final_material}")

                            if existing_mask.any():
                                if is_siphon and flow_rate: df_tech.loc[existing_mask, 'Flow_Rate_l_s'] = flow_rate
                                if not is_siphon and length: 
                                    df_tech.loc[existing_mask, 'Length_mm'] = length
                                    df_tech.loc[existing_mask, 'Is_Cuttable'] = is_cuttable
                                if not is_siphon and material: df_tech.loc[existing_mask, 'Material_V4A'] = material
                                if not is_siphon and color: df_tech.loc[existing_mask, 'Color'] = color
                                updates_made += 1
                                print(f"      ✅ {found_sku}: {', '.join(info)}", file=sys.stderr)
                            else:
                                new_prod = {col: "" for col in self.cols_tech}
                                new_prod.update({
                                    "Component_SKU": found_sku, "Manufacturer": "Geberit", "Product_Name": h1_text,
                                    "Tech_Source_URL": product_url, "Flow_Rate_l_s": flow_rate, 
                                    "Material_V4A": final_material, "Color": final_color, "Length_mm": final_length, "Is_Cuttable": is_cuttable
                                })
                                new_discovered_products.append(new_prod)
                                print(f"      🌟 (Nový) {found_sku}: {', '.join(info)}", file=sys.stderr)

                        except Exception as e:
                            print(f"      ❌ Chyba u {product_url}: {e}", file=sys.stderr)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if new_discovered_products:
                df_tech = pd.concat([df_tech, pd.DataFrame(new_discovered_products)], ignore_index=True)
            df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if market_prices:
                df_prices_new = pd.DataFrame(market_prices)
                try:
                    df_prices_old = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    skus = [p["Component_SKU"] for p in market_prices]
                    df_prices_old = df_prices_old[~((df_prices_old['Component_SKU'].isin(skus)) & (df_prices_old['Eshop_Source'] == 'Megabad'))]
                    df_prices_combined = pd.concat([df_prices_old, df_prices_new], ignore_index=True)
                    df_prices_combined.to_excel(writer, sheet_name="Market_Prices", index=False)
                except: pass

        print("✅ Hotovo! Speciální rozměry pro 154.455.00.1 byly bezpečně aplikovány.")

if __name__ == "__main__":
    GeberitPricingV11_EdgeCase().run()