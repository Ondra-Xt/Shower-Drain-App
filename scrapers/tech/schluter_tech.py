import pandas as pd
import re
import sys
import time
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

class SchluterTechScraperV22:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.hardcoded_pdf_url = "https://assets.schluter.com/asset/570120892212/document_00ifil951h3gbds93nevf4el4o/kerdiline-products.pdf?content-disposition=inline"
        self.local_pdf_name = "Schluter_KERDI_LINE_Datasheet.pdf"
        self.cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                f = open(self.excel_path, "r+"); f.close()
            except IOError:
                print(f"❌ ERROR: Soubor '{self.excel_path}' je otevřený v Excelu! Zavřete ho.", file=sys.stderr)
                sys.exit(1)

    def download_pdf_if_needed(self):
        should_download = False
        if not os.path.exists(self.local_pdf_name):
            should_download = True
        else:
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(self.local_pdf_name))
            if file_age > timedelta(days=2):
                should_download = True

        if should_download:
            print(f"📥 Aktualizuji PDF datasheet...", file=sys.stderr)
            try:
                req = urllib.request.Request(self.hardcoded_pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    with open(self.local_pdf_name, "wb") as out_file:
                        out_file.write(response.read())
            except Exception as e:
                print(f"⚠️ PDF download error: {e}", file=sys.stderr)

    def get_tasks(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            seen = set()
            for _, row in df.iterrows():
                name = str(row.get("Component_Name", ""))
                sku = str(row.get("Component_SKU", "")).strip()
                if any(x in name.lower() for x in ["schluter", "schlüter", "kerdi"]) and sku not in seen:
                    if sku and sku != "nan":
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except Exception as e:
            print(f"❌ Chyba čtení Excelu: {e}")
            return []

    def extract_tech_data(self, text):
        # Hledání průtoku: 0.4 l/s, 0,8 l/s, 1.0 l/sek atd.
        f_rate = "N/A"
        flow_match = re.search(r"(\d+[.,]\d+)\s*(l/s|l/sek|l/min)", text, re.IGNORECASE)
        if flow_match:
            val = flow_match.group(1).replace(',', '.')
            unit = flow_match.group(2).lower()
            if "min" in unit:
                try: val = f"{float(val)/60:.2f}"
                except: pass
            f_rate = f"{val} l/s"

        # Hledání výšky: 24 mm, 50-120 mm, atd.
        h_adj = "N/A"
        h_match = re.search(r"(?:Bauhöhe|Höhe|Einbauhöhe|Aufbauhöhe).*?(\d{1,3}(?:\s*-\s*\d{1,3})?)\s*mm", text, re.IGNORECASE)
        if h_match:
            h_adj = f"{h_match.group(1)} mm"
            
        return f_rate, h_adj

    def search_and_extract(self, page, sku, raw_name):
        # Generování dotazů: 1. Přesné SKU, 2. Ořezané SKU (bez délky), 3. Název
        sku_base = sku[:-4] if len(sku) > 8 else sku # Ořezává např. 2100 z konce
        clean_name = re.sub(r'\(.*?\)', '', raw_name).replace("Schlüter", "").strip()
        queries = [sku, sku_base, clean_name]
        
        shops = [
            {"name": "Bausep.de", "url": "https://www.bausep.de", "input": "input#search", "results": ".product-item-link"},
            {"name": "Benz24.de", "url": "https://benz24.de", "input": "input[name='q']", "results": ".product-item-link"}
        ]

        for shop in shops:
            try:
                print(f"  🛒 Shop: {shop['name']}")
                page.goto(shop['url'], wait_until="domcontentloaded", timeout=15000)
                
                try: # Zavřít cookies
                    page.locator("button#btn-cookie-allow, .cms-cookie-settings__accept-all").first.click(timeout=2000)
                except: pass

                for q in queries:
                    if len(q) < 4: continue
                    print(f"    🔍 Hledám: {q}")
                    
                    search_input = page.locator(shop['input']).first
                    search_input.click()
                    search_input.fill("")
                    search_input.type(q, delay=50)
                    page.keyboard.press("Enter")
                    
                    # Čekání na výsledek nebo detail
                    time.sleep(3) 

                    # 1. Kontrola, zda jsme v detailu
                    if page.locator("button#product-addtocart-button, .product-info-main, .product-detail-name").first.is_visible():
                        content = page.evaluate("document.body.innerText")
                        f, h = self.extract_tech_data(content)
                        if f != "N/A": return f, h, page.url

                    # 2. Kontrola, zda jsme v seznamu výsledků
                    first_hit = page.locator(shop['results']).first
                    if first_hit.is_visible():
                        first_hit.click()
                        time.sleep(2)
                        content = page.evaluate("document.body.innerText")
                        f, h = self.extract_tech_data(content)
                        if f != "N/A": return f, h, page.url
                            
            except Exception as e:
                print(f"    ⚠️ {shop['name']} error: {e}")
                continue
        return "N/A", "N/A", "N/A"

    def run(self):
        self.check_excel_access()
        self.download_pdf_if_needed()
        tasks = self.get_tasks()
        if not tasks: return

        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Nastavení reálného prohlížeče
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                print(f"\n🚀 Zpracovávám SKU: {sku}")
                
                res = {
                    "Component_SKU": sku, "Manufacturer": "Schlüter",
                    "Datasheet_URL": self.hardcoded_pdf_url, "Cert_EN1253": "Yes",
                    "Cert_EN18534": "Yes", "Color_Count": 1
                }

                sku_u = sku.upper()
                # ROŠTY (Grating) - nehledáme na webu
                if any(x in sku_u for x in ["KL1A", "ROST", "EDELSTAHL", "KL1RE"]):
                    res.update({
                        "Flow_Rate_l_s": "N/A", "Height_Adjustability": "N/A", 
                        "Sealing_Fleece": "No", "Material_V4A": "Edelstahl V4A (1.4404)",
                        "Tech_Source_URL": "Logic: Grating/Cover"
                    })
                else:
                    # TĚLO ŽLABU (Drain Body) - hledáme
                    f, h, url = self.search_and_extract(page, sku, task["name"])
                    res.update({
                        "Flow_Rate_l_s": f, "Height_Adjustability": h, 
                        "Tech_Source_URL": url, "Sealing_Fleece": "Yes", 
                        "Material_V4A": "Edelstahl V4A (1.4404)"
                    })
                
                # Odtoková logika podle SKU
                if "KLH" in sku_u: res["Vertical_Outlet_Option"] = "DN50 Horizontal"
                elif "KLV" in sku_u: res["Vertical_Outlet_Option"] = "DN50 Vertical"
                else: res["Vertical_Outlet_Option"] = "Check Drawing"

                results.append(res)
                print(f"   ✅ Výsledek: Průtok {res['Flow_Rate_l_s']} | Výška {res['Height_Adjustability']}")

            browser.close()

        if results:
            df_new = pd.DataFrame(results)
            # Zápis zpět do Excelu
            try:
                # Načteme existující data, abychom je mohli spojit nebo jen přepsat list
                with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df_new.to_excel(writer, sheet_name="Products_Tech", index=False)
                print(f"\n✅ Hotovo! Uloženo {len(results)} záznamů do listu 'Products_Tech'.")
            except Exception as e:
                print(f"❌ Chyba při ukládání: {e}")

if __name__ == "__main__":
    scraper = SchluterTechScraperV22()
    scraper.run()