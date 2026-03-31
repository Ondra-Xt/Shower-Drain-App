import pandas as pd
import re
import sys
import time
import os
import urllib.parse
import datetime
import requests
import io
from playwright.sync_api import sync_playwright

try:
    import pdfplumber
except ImportError:
    print("❌ CHYBA: Chybí knihovna 'pdfplumber'.", file=sys.stderr)
    sys.exit(1)

class EasyDrainTechScraperV12:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.tech_cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]
        self.price_cols = [
            "Component_SKU", "Eshop_Source", "Found_Price_EUR", 
            "Price_Breakdown", "Product_URL", "Timestamp"
        ]

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.", file=sys.stderr)
                sys.exit(1)

    def get_tasks(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            seen = set()
            for _, row in df.iterrows():
                name = str(row["Component_Name"]).strip()
                sku = str(row["Component_SKU"]).strip()
                if any(x in name.lower() for x in ["easy drain", "easydrain", "ess "]):
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except Exception as e:
            print(f"⚠️ Chyba při čtení Excelu: {e}", file=sys.stderr)
            return []

    def analyze_text_data(self, text):
        data = {}
        clean_text = text.replace('\n', ' ').replace('\r', ' ')
        clean_text = re.sub(r'\s+', ' ', clean_text)
        lower_text = clean_text.lower()

        # 1. PRŮTOK
        match_flow_min = re.search(r'(\d+(?:[.,]\d+)?)\s*l/min', clean_text, re.IGNORECASE)
        match_flow_sec = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', clean_text, re.IGNORECASE)
        
        if match_flow_sec:
            val = float(match_flow_sec.group(1).replace(',', '.'))
            if 0.2 <= val <= 2.5: data["Flow_Rate_l_s"] = f"{val} l/s"
        elif match_flow_min:
            val = float(match_flow_min.group(1).replace(',', '.'))
            val_sec = round(val / 60.0, 2)
            if 0.2 <= val_sec <= 2.5: data["Flow_Rate_l_s"] = f"{val_sec} l/s"

        # 2. VÝŠKA
        h_text = re.sub(r'Sperrwasserhöhe.{0,20}\d+\s*(?:mm)?', '', clean_text, flags=re.IGNORECASE)
        match_single = re.search(r'(?:Einbautiefe|Bauhöhe|Installation depth|ab)[^\d]{0,40}?(\d{2,3})\s*mm', h_text, re.IGNORECASE)
        if match_single:
            val = int(match_single.group(1))
            if val > 35: data["Height_Adjustability"] = f"{val} mm"

        # 3. ODTOK
        match_dn = re.search(r'DN\s*(\d+(?:\s*/\s*\d+)?)', clean_text)
        if match_dn:
            data["Vertical_Outlet_Option"] = f"DN {match_dn.group(1).replace(' ', '')}"

        # 4. MATERIÁL
        if "1.4404" in lower_text or "v4a" in lower_text: data["Material_V4A"] = "Edelstahl V4A (1.4404)"
        elif "1.4301" in lower_text or "v2a" in lower_text: data["Material_V4A"] = "Edelstahl V2A (1.4301)"
        elif "edelstahl" in lower_text: data["Material_V4A"] = "Edelstahl (Typ nezjištěn)"
        elif "abs" in lower_text or "polypropylen" in lower_text: data["Material_V4A"] = "Kunststoff/ABS"

        # 5. CERTIFIKACE
        if "1253" in lower_text and "din" in lower_text: data["Cert_EN1253"] = "Yes"
        
        # 6. SEALING FLEECE
        if any(x in lower_text for x in ["wps", "water protection system", "dichtvlies", "abdichtungsset", "kerdi"]):
            data["Sealing_Fleece"] = "Yes (WPS)"
        
        return data

    def download_and_read_pdf(self, pdf_url):
        print(f"         📥 Stahuji PDF: {pdf_url} ...", file=sys.stderr)
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(pdf_url, headers=headers, timeout=15)
            if response.status_code == 200:
                full_text = ""
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    for page in pdf.pages[:3]:
                        txt = page.extract_text()
                        if txt: full_text += txt + " "
                print(f"         📝 PDF přečteno ({len(full_text)} znaků).", file=sys.stderr)
                return full_text
            return ""
        except Exception as e:
            print(f"         ⚠️ Chyba PDF: {e}", file=sys.stderr)
            return ""

    def search_saniweb_price(self, page, sku):
        """Cílené hledání na Saniweb.de s proklikem na detail."""
        print(f"         🛒 Saniweb.de: Hledám cenu...", file=sys.stderr)
        
        # Saniweb používá parametr sSearch
        search_query = f"Easy Drain {sku}"
        url = f"https://www.saniweb.de/search?sSearch={urllib.parse.quote(search_query)}"
        
        try:
            page.goto(url, timeout=30000)
            
            # Cookie banner (Saniweb má specifický)
            try: page.locator(".cookie-permission--accept-button").click(timeout=1500)
            except: pass
            
            time.sleep(2)
            
            # 1. Najít první relevantní produkt v seznamu
            # Hledáme .product--box nebo .product--info
            product_link = page.locator(".product--info a, .product--title").first
            
            if product_link.is_visible():
                href = product_link.get_attribute("href")
                title = product_link.inner_text()
                
                print(f"         🔎 Nalezen produkt: {title}", file=sys.stderr)
                print(f"         🚀 Přecházím na detail: {href}", file=sys.stderr)
                
                # Kliknutí na detail
                product_link.click()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
                
                # 2. Extrakce ceny z detailu
                price = "N/A"
                
                # Zkusíme nejpřesnější meta tag
                try:
                    meta_price = page.locator('meta[itemprop="price"]').get_attribute("content")
                    if meta_price:
                        price = float(meta_price)
                except: pass
                
                # Fallback na viditelný text
                if price == "N/A":
                    try:
                        price_text = page.locator(".product--price, .price--content").first.inner_text()
                        match = re.search(r'(\d+[.,]\d{2})', price_text)
                        if match:
                            price = float(match.group(1).replace('.', '').replace(',', '.'))
                    except: pass
                
                if price != "N/A":
                    print(f"         💰 Cena nalezena: {price} EUR", file=sys.stderr)
                    return price, page.url
            else:
                print(f"         ⚠️ Žádné produkty nenalezeny pro '{search_query}'.", file=sys.stderr)

        except Exception as e:
            print(f"         ⚠️ Chyba Saniweb: {e}", file=sys.stderr)
            
        return "N/A", "N/A"

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks: 
            print("⚠️ POZOR: V Excelu nejsou žádné produkty Easy Drain.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím EasyDrain Tech Scraper V12 (Saniweb Deep-Dive)...", file=sys.stderr)
        tech_results = []
        price_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám: {sku}\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku, "Manufacturer": "Easy Drain",
                    "Tech_Source_URL": "N/A", "Datasheet_URL": "N/A",
                    "Flow_Rate_l_s": "N/A", "Material_V4A": "N/A",
                    "Cert_EN1253": "No", "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A", "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No", "Color_Count": 1
                }

                # 1. EasyDrain.de (Výrobce - Technická data)
                series_slug = "compact" 
                if "modulo" in raw_name.lower(): series_slug = "modulo-design"
                elif "multi" in raw_name.lower(): series_slug = "multi"
                
                target_url = f"https://www.easydrain.de/serie/{series_slug}/"
                
                try:
                    page.goto(target_url, timeout=30000)
                    time.sleep(2)
                    try: page.locator("button#cookie-accept").click(timeout=1000)
                    except: pass
                    
                    extracted_data["Tech_Source_URL"] = target_url
                    
                    for i in range(1, 6):
                        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/5});")
                        time.sleep(0.3)
                    
                    buttons = page.locator(".accordion-title, .tab-title, button:has-text('Technische'), button:has-text('Download')").all()
                    for b in buttons:
                        try: b.click(force=True, timeout=500); time.sleep(0.1)
                        except: pass

                    web_text = page.evaluate("document.body.innerText")
                    analyzed = self.analyze_text_data(web_text)
                    extracted_data.update({k: v for k, v in analyzed.items() if v})
                    
                    pdf_links = page.locator("a[href*='.pdf']").all()
                    for l in pdf_links:
                        href = l.get_attribute("href")
                        if href and ("datenblatt" in href.lower() or "datasheet" in href.lower()):
                            extracted_data["Datasheet_URL"] = href
                            break

                except Exception as e:
                    print(f"         ⚠️ Chyba EasyDrain: {e}", file=sys.stderr)

                # 2. Saniweb.de (Cena - Deep Dive)
                price, shop_url = self.search_saniweb_price(page, sku)

                if price != "N/A":
                    price_results.append({
                        "Component_SKU": sku, "Eshop_Source": "Saniweb.de",
                        "Found_Price_EUR": price, "Price_Breakdown": "Single",
                        "Product_URL": shop_url,
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

                print(f"         ✅ Materiál:     {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:       {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Výška:        {extracted_data['Height_Adjustability']}", file=sys.stderr)
                print(f"         ✅ Odtok:        {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                print(f"         ✅ Fleece (WPS): {extracted_data['Sealing_Fleece']}", file=sys.stderr)
                print(f"         💰 Cena EUR:     {price} (Saniweb)", file=sys.stderr)
                
                tech_results.append(extracted_data)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if tech_results:
                df = pd.DataFrame(tech_results)[self.tech_cols]
                try: 
                    old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    for sku in df['Component_SKU']:
                        old = old[old['Component_SKU'].astype(str) != str(sku)]
                    df = pd.concat([old, df], ignore_index=True)
                except: pass
                df.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if price_results:
                df_p = pd.DataFrame(price_results)[self.price_cols]
                try:
                    old_p = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    for _, row in df_p.iterrows():
                        old_p = old_p[~((old_p['Component_SKU'].astype(str) == str(row['Component_SKU'])) & (old_p['Eshop_Source'] == row['Eshop_Source']))]
                    df_p = pd.concat([old_p, df_p], ignore_index=True)
                except: pass
                df_p.to_excel(writer, sheet_name="Market_Prices", index=False)

        print("\n✅ Hotovo! Easy Drain data uložena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = EasyDrainTechScraperV12()
    scraper.run()