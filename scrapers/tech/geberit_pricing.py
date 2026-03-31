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

class GeberitPricingV17:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]

    def quarantine_excel(self):
        print("🧹 Spouštím úklid Excelu (Karanténa)...", file=sys.stderr)
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                is_valid = (df_tech['Manufacturer'] != 'Geberit') | (df_tech['Component_SKU'].astype(str).str.startswith('154.'))
                df_tech = df_tech[is_valid].copy()
                
                if 'Color' not in df_tech.columns: df_tech['Color'] = ""
                df_tech['Color'] = df_tech['Color'].astype(str).replace('nan', '')
                
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)

                df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                is_valid_p = (df_prices['Eshop_Source'] != 'Megabad') | (df_prices['Component_SKU'].astype(str).str.startswith('154.'))
                df_prices = df_prices[is_valid_p].copy()
                df_prices.to_excel(writer, sheet_name="Market_Prices", index=False)
                
            print("   ✅ Excel připraven a validován.\n", file=sys.stderr)
            return df_tech
        except Exception as e:
            print(f"   ⚠️ Chyba při čištění: {e}")
            return pd.DataFrame()

    def extract_material(self, text_lower):
        if "v4a" in text_lower or "1.4404" in text_lower: return "Edelstahl V4A"
        elif "edelstahl" in text_lower or "1.4301" in text_lower or "rostfrei" in text_lower: return "Edelstahl V2A"
        return ""

    def extract_flow_from_pdf(self, pdf_url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(pdf_url, headers=headers, timeout=10)
            if response.status_code == 200:
                with io.BytesIO(response.content) as open_pdf_file:
                    reader = PyPDF2.PdfReader(open_pdf_file)
                    pdf_text = " ".join([p.extract_text() for p in reader.pages if p.extract_text()])
                    m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', pdf_text.lower())
                    if m_flow:
                        val = float(m_flow.group(1).replace(',', '.'))
                        if 0.2 < val < 2.0: return f"{val} l/s"
        except: pass 
        return ""

    def search_megabad(self, page, query):
        print(f"\n   ➡️ Hledám: {query}", file=sys.stderr)
        try:
            page.goto("https://www.megabad.com/", timeout=40000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1)
            
            page.evaluate("""() => { ['CybotCookiebotDialog', 'CybotCookiebotDialogBodyUnderlay', 'usercentrics-root'].forEach(id => { let el = document.getElementById(id); if(el) el.remove(); }); document.body.style.overflow = 'auto'; }""")
            
            search_box = page.locator('input[type="search"], input[name="search"], input[name="q"], .search-input').first
            search_box.fill(query)
            search_box.press("Enter")
            
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            return True
        except Exception as e: 
            print(f"      ❌ Chyba při vyhledávání: {e}", file=sys.stderr)
            return False

    def run(self):
        if not os.path.exists(self.excel_path): return

        print("\n" + "="*60)
        print("🚀 Spouštím Geberit Pricing V17 (The Color Fixer)")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = self.quarantine_excel()
        if df_tech.empty: return
        
        geberit_skus = df_tech[df_tech['Manufacturer'] == 'Geberit']['Component_SKU'].dropna().unique()

        market_prices = []
        new_discovered = []
        updates_made = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for target_sku in geberit_skus:
                if self.search_megabad(page, target_sku):
                    url = page.url.lower()
                    target_links = []
                    
                    if "suche" in url or "search" in url:
                        found = page.locator("a").all()
                        for f in found:
                            try:
                                href = f.get_attribute("href")
                                if href and "-a-" in href and href.endswith(".htm") and "suche" not in href:
                                    target_links.append(href if href.startswith("http") else "https://www.megabad.com" + href)
                            except: pass
                        target_links = list(dict.fromkeys(target_links))[:3]
                    else: 
                        target_links = [page.url]

                    for product_url in target_links:
                        try:
                            page.goto(product_url, timeout=30000)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(1)
                            
                            try: h1_text = page.locator("h1").first.inner_text().strip()
                            except: h1_text = ""
                            if any(x in h1_text.lower() for x in ["inkl.", "bündel", " set"]): continue

                            page_text = page.locator("body").inner_text()
                            page_text_lower = page_text.lower()
                            
                            m_sku = re.search(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', page_text)
                            found_sku = m_sku.group(1).upper() if m_sku else ""
                            if not found_sku: 
                                sku_h1 = re.search(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', h1_text)
                                found_sku = sku_h1.group(1).upper() if sku_h1 else ""
                            
                            if not found_sku: continue
                            is_siphon = "154.15" in found_sku or "rohbauset" in h1_text.lower()

                            # --- CENA ---
                            price, uvp = "", ""
                            buy_box = page.locator(".product-info, .buy-box, #product-detail").first
                            search_text = buy_box.inner_text() if buy_box.is_visible(timeout=2000) else page_text[:2000]
                            
                            clean_txt = " ".join([l for l in search_text.split('\n') if 'sparen' not in l.lower()])
                            p_floats = sorted(list(set([float(p.replace('.', '').replace(',', '.')) for p in re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', clean_txt)])), reverse=True)
                            
                            if p_floats:
                                if len(p_floats) >= 2: uvp, price = str(p_floats[0]), str(p_floats[1])
                                else: price = str(p_floats[0])

                            if price:
                                market_prices.append({
                                    "Component_SKU": found_sku, "Eshop_Source": "Megabad",
                                    "Found_Price_EUR": price, "Original_Price_EUR": uvp,
                                    "Price_Breakdown": "Single", "Product_URL": product_url, 
                                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                                })

                            # --- BARVA (STRIKTNÍ LOGIKA H1 + SKU) ---
                            color = ""
                            h1_lower = h1_text.lower()
                            
                            if not is_siphon:
                                # 1. Nejdříve hledáme přesně v nadpisu z Megabadu
                                if "schwarz" in h1_lower and "chrom" in h1_lower: color = "Schwarz / Chrom"
                                elif "schwarz" in h1_lower: color = "Schwarz"
                                elif "champagner" in h1_lower: color = "Champagner"
                                elif "gebürstet" in h1_lower or "poliert" in h1_lower: color = "Edelstahl (Gebürstet/Poliert)"
                                
                                # 2. Pokud nadpis mlčí, použijeme pevné SKU kódy Geberitu (Vaše doporučení)
                                if not color:
                                    if ".KS." in found_sku: color = "Edelstahl (Gebürstet/Poliert)"
                                    elif ".QC." in found_sku or ".QB." in found_sku or ".14." in found_sku: color = "Schwarz"
                                    elif ".00." in found_sku: color = "Edelstahl (Gebürstet/Poliert)" # 00 je často základní nerez u roštů

                            # --- HTML SPECIFIKACE ---
                            flow, length, cuttable = "", "", "No"
                            mat = self.extract_material(page_text_lower)
                            
                            if not is_siphon:
                                m_len = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*cm', page_text_lower)
                                if m_len:
                                    length = f"{int(m_len.group(1))*10} - {int(m_len.group(2))*10}"
                                    cuttable = "Yes"
                                else:
                                    m_s_len = re.search(r'\b(30|40|50|60|70|80|90|100|110|120|130)\s*cm', page_text_lower)
                                    if m_s_len: length = str(int(m_s_len.group(1))*10)
                            else:
                                m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', page_text_lower)
                                if m_flow:
                                    val = float(m_flow.group(1).replace(',', '.'))
                                    if 0.2 < val < 2.0: flow = f"{val} l/s"

                            # --- PDF DEEP SCAN (Pouze pro průtok u sifonů!) ---
                            if is_siphon and not flow:
                                pdfs = [link.get_attribute("href") for link in page.locator("a").all() if link.get_attribute("href") and (".pdf" in link.get_attribute("href").lower() or "datenblatt" in link.inner_text().lower())]
                                for pdf_url in list(set(pdfs))[:2]:
                                    pdf_url = pdf_url if pdf_url.startswith("http") else "https://www.megabad.com" + pdf_url
                                    flow = self.extract_flow_from_pdf(pdf_url)
                                    if flow: break

                            # ZÁPIS A VÝPIS DO LOGU
                            existing = df_tech['Component_SKU'].astype(str).str.upper() == found_sku
                            
                            info = [f"Cena: {price} €"]
                            if not is_siphon and color: info.append(f"Barva: {color}")
                            if mat: info.append(f"Mat: {mat}")
                            if length: info.append(f"Délka: {length} mm")
                            if flow: info.append(f"Průtok: {flow}")
                            
                            if existing.any():
                                if color: df_tech.loc[existing, 'Color'] = color
                                if mat: df_tech.loc[existing, 'Material_V4A'] = mat
                                if flow: df_tech.loc[existing, 'Flow_Rate_l_s'] = flow
                                if length: 
                                    df_tech.loc[existing, 'Length_mm'] = length
                                    df_tech.loc[existing, 'Is_Cuttable'] = cuttable
                                updates_made += 1
                                print(f"      ✅ {found_sku} -> {', '.join(info)}", file=sys.stderr)
                            else:
                                new_row = {col: "" for col in self.cols_tech}
                                new_row.update({
                                    "Component_SKU": found_sku, "Manufacturer": "Geberit", "Product_Name": h1_text,
                                    "Tech_Source_URL": product_url, "Flow_Rate_l_s": flow, 
                                    "Material_V4A": mat, "Color": color, "Length_mm": length, "Is_Cuttable": cuttable
                                })
                                new_discovered.append(new_row)
                                print(f"      🌟 Nový Geberit: {found_sku} -> {', '.join(info)}", file=sys.stderr)

                        except Exception as e:
                            print(f"      ❌ Chyba u odkazu: {e}", file=sys.stderr)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if new_discovered: df_tech = pd.concat([df_tech, pd.DataFrame(new_discovered)], ignore_index=True)
            df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if market_prices:
                df_p_old = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                skus = [p["Component_SKU"] for p in market_prices]
                df_p_old = df_p_old[~((df_p_old['Component_SKU'].isin(skus)) & (df_p_old['Eshop_Source'] == 'Megabad'))]
                pd.concat([df_p_old, pd.DataFrame(market_prices)], ignore_index=True).to_excel(writer, sheet_name="Market_Prices", index=False)

        print("✅ Hotovo! Barvy jsou nyní chráněny proti falešným informacím z reklamních textů.")

if __name__ == "__main__":
    GeberitPricingV17().run()