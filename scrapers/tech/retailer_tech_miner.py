import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os
import sys

class RetailerTechMinerV2:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_tech"): os.makedirs("debug_tech")

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ CHYBA: Soubor '{self.excel_path}' je otevřený! Zavřete ho.")
                sys.exit(1)

    def get_urls_from_market_prices(self):
        """Načte URL adresy z Market_Prices, preferuje Hornbach."""
        if not os.path.exists(self.excel_path): return []
        try:
            df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
            tasks = {}
            for _, row in df_prices.iterrows():
                sku = str(row["Component_SKU"]).strip()
                url = str(row["Product_URL"])
                source = str(row["Eshop_Source"])
                
                if "http" not in url: continue
                
                # Uložíme si úkol. Pokud narazíme na Hornbach, přepíšeme případný Megabad (Hornbach má lepší data)
                if sku not in tasks:
                    tasks[sku] = {"sku": sku, "url": url, "source": source}
                elif source == "Hornbach":
                    tasks[sku] = {"sku": sku, "url": url, "source": source}
            
            return list(tasks.values())
        except Exception as e:
            print(f"⚠️ Chyba čtení Excelu: {e}")
            return []

    def parse_hornbach_table(self, page):
        """Čte strukturovaná data z tabulky Hornbachu."""
        specs = {}
        
        # Hornbach používá různé struktury, zkusíme najít tu správnou
        # 1. Expandovat "Mehr anzeigen"
        try: 
            page.locator("button:has-text('Mehr anzeigen'), button:has-text('Alle Details anzeigen')").click(timeout=1000)
        except: pass
        
        # 2. Hledáme řádky tabulky specifikací
        # Selektory pro klíč a hodnotu
        rows = page.locator("tr, dl div, .attributes-table-row").all()
        
        for row in rows:
            try:
                # Zkusíme různé varianty pro Key a Value
                key = ""
                val = ""
                
                # Varianta A: Table row (th/td)
                if row.locator("th").count() > 0:
                    key = row.locator("th").first.inner_text().strip().lower()
                    val = row.locator("td").first.inner_text().strip()
                
                # Varianta B: Definition list (dt/dd)
                elif row.locator("dt").count() > 0:
                    key = row.locator("dt").first.inner_text().strip().lower()
                    val = row.locator("dd").first.inner_text().strip()
                
                if key and val:
                    specs[key] = val
            except: pass
            
        return specs

    def analyze_specs(self, specs_dict, full_text_lower):
        """Převede surová data z e-shopu na naše parametry."""
        res = {
            "Flow_Rate": "N/A", "Material_V4A": "No (Standard)", 
            "Cert_EN1253": "No", "Cert_EN18534": "No",
            "Height_Adjustability": "N/A", "Sales_Price_UVP": "N/A",
            "Outlet_Direction": "Check Drawing", "Sealing_Fleece": "No",
            "Colors_Available": 1,
            "Identity_Verified": "YES"
        }
        
        # Pomocná funkce pro hledání v dict i textu
        def find_val(keywords):
            # 1. Hledání v tabulce (přesnější)
            for k, v in specs_dict.items():
                if any(kw in k for kw in keywords):
                    return v
            return None

        # 1. Flow Rate (Ablaufleistung)
        val = find_val(["ablaufleistung", "schluckvermögen", "flow"])
        if val:
            res["Flow_Rate"] = val
        else:
            # Fallback text
            match = re.search(r'(\d+[.,]\d+)\s*l/s', full_text_lower)
            if match: res["Flow_Rate"] = f"{match.group(1)} l/s"

        # 2. Material
        val = find_val(["material", "werkstoff"])
        combined_text = (str(val) + full_text_lower).lower()
        if "1.4404" in combined_text or "v4a" in combined_text or "316l" in combined_text:
            res["Material_V4A"] = "YES (V4A)"
        
        # 3. Certifikace (Norm)
        if "1253" in full_text_lower: res["Cert_EN1253"] = "YES"
        if "18534" in full_text_lower: res["Cert_EN18534"] = "YES"

        # 4. Height (Bauhöhe)
        val = find_val(["bauhöhe", "einbauhöhe", "höhe", "height"])
        if val:
            res["Height_Adjustability"] = val
        else:
            match = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*mm', full_text_lower)
            if match: res["Height_Adjustability"] = f"{match.group(1)}-{match.group(2)}"

        # 5. Outlet (Ablauf)
        val = find_val(["ablauf", "ausrichtung", "abgang"])
        combined_text = (str(val) + full_text_lower).lower()
        if "senkrecht" in combined_text: res["Outlet_Direction"] = "Vertical"
        elif "waagerecht" in combined_text: res["Outlet_Direction"] = "Horizontal"

        # 6. Fleece
        if "dichtvlies" in full_text_lower or "sealing fleece" in full_text_lower:
            res["Sealing_Fleece"] = "YES (Likely)"

        # 7. Colors
        # U Hornbachu je barva často jeden řádek, např. "Farbe: Schwarz" -> Count = 1
        # Pokud chceme varianty, museli bychom hledat dropdown, to je složité. 
        # Necháme 1, pokud nenajdeme explicitně jinak.
        
        return res

    def run(self):
        self.check_excel_access()
        tasks = self.get_urls_from_market_prices()
        print(f"🚀 Start: {len(tasks)} produktů k vytěžení.")
        
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for task in tasks:
                sku = task['sku']
                url = task['url']
                
                print(f"🔍 SKU {sku} ({task['source']})...")
                
                try:
                    page.goto(url, timeout=60000)
                    
                    # 1. Detekce Search Page -> Klik na první produkt
                    if "/s/" in page.url or page.locator("article, .product-card").count() > 1:
                        print("      ⚠️ Jsem na vyhledávání. Klikám na první produkt...")
                        first_prod = page.locator("article a, .product-card a").first
                        if first_prod.count() > 0:
                            first_prod.click()
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                        else:
                            print("      ❌ Žádný produkt v seznamu.")
                            continue
                    
                    # 2. Cookies
                    try: page.locator("#onetrust-accept-btn-handler, button:has-text('Alle akzeptieren')").first.click(timeout=2000)
                    except: pass
                    
                    # 3. Těžba dat
                    if task['source'] == "Hornbach":
                        # Hornbach specifická tabulka
                        raw_specs = self.parse_hornbach_table(page)
                        full_text = page.locator("body").inner_text().lower()
                        
                        clean_data = self.analyze_specs(raw_specs, full_text)
                    else:
                        # Megabad fallback (jen text)
                        text = page.locator("body").inner_text()
                        clean_data = self.analyze_specs({}, text.lower())
                    
                    clean_data["Component_SKU"] = sku
                    clean_data["Tech_Source_URL"] = page.url
                    
                    # Výrobce
                    title = page.title()
                    if "Geberit" in title: clean_data["Manufacturer"] = "Geberit"
                    elif "Tece" in title or "TECE" in title: clean_data["Manufacturer"] = "TECE"
                    elif "Hansgrohe" in title: clean_data["Manufacturer"] = "Hansgrohe"
                    else: clean_data["Manufacturer"] = "Unknown"

                    print(f"      ✅ Data: {clean_data}")
                    results.append(clean_data)

                except Exception as e:
                    print(f"      🔥 Chyba: {e}")
                
                time.sleep(1)

            browser.close()

        if results:
            df = pd.DataFrame(results)
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                try: start = writer.sheets['Products_Tech'].max_row
                except: start = 0
                header = True if start == 0 else False
                df.to_excel(writer, sheet_name="Products_Tech", index=False, header=header, startrow=start)
            print("✅ Data uložena.")

if __name__ == "__main__":
    miner = RetailerTechMinerV2()
    miner.run()