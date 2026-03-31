import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os
import sys

class UniversalTechAgentV3:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_tech"): os.makedirs("debug_tech")
        
        self.brand_domains = {
            "Hansgrohe": "hansgrohe.com",
            "Geberit": "geberit.com",
            "TECE": "tece.com",
            "Alca": "alcadrain.com",
            "Dallmer": "dallmer.com",
            "Viega": "viega.com",
            "ESS": "easydrain.com",
            "Schlueter": "schluter.com",
            "Schuette": "fjschuette.com"
        }

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ CHYBA: Soubor '{self.excel_path}' je otevřený! Zavřete ho.")
                sys.exit(1)

    def get_pending_tasks(self):
        if not os.path.exists(self.excel_path): return []
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                brand = "Unknown"
                for b in self.brand_domains.keys():
                    if b.lower() in name.lower() or b.lower() in str(row.get("Parent_Product_SKU", "")).lower():
                        brand = b
                        break
                if brand != "Unknown":
                    tasks.append({"sku": sku, "brand": brand, "name": name})
            
            seen = set()
            unique_tasks = []
            for t in tasks:
                if t['sku'] not in seen:
                    unique_tasks.append(t)
                    seen.add(t['sku'])
            return unique_tasks
        except Exception as e:
            print(f"⚠️ Chyba Excelu: {e}")
            return []

    def clean_specs(self, text, sku=""):
        text_lower = text.lower()
        specs = {
            "Flow_Rate": "N/A", "Material_V4A": "No (Standard)", 
            "Cert_EN1253": "No", "Cert_EN18534": "No",
            "Height_Adjustability": "N/A", "Sales_Price_UVP": "N/A",
            "Outlet_Direction": "Check Drawing", "Sealing_Fleece": "No",
            "Colors_Available": 1,
            "Identity_Verified": "NO"
        }
        
        # --- 1. Identity Check ---
        # Zkoušíme najít SKU v textu (i s mezerami pro TECE, např. 601 200)
        sku_clean = sku.replace(".", "").replace(" ", "")
        sku_spaced = sku[:3] + " " + sku[3:] if len(sku) == 6 and sku.isdigit() else sku
        
        if sku.lower() in text_lower or sku_clean in text_lower or sku_spaced in text_lower:
            specs["Identity_Verified"] = "YES"

        # --- 2. Flow Rate (Rozšířená synonyma) ---
        # Geberit používá "Discharge capacity", TECE "Drainage capacity"
        flow_keywords = r"(flow rate|drainage capacity|discharge capacity|ablaufleistung|schluckvermögen|discharge rate|capacity)"
        
        # Hledáme: keyword ... číslo ... l/s
        match_ls = re.search(flow_keywords + r".{0,100}?(\d+[.,]\d+)\s*l/s", text_lower)
        if match_ls:
            specs["Flow_Rate"] = f"{match_ls.group(2).replace(',', '.')} l/s"
        else:
            # Hledáme: keyword ... číslo ... l/min (převod)
            match_min = re.search(flow_keywords + r".{0,100}?(\d+[.,]\d+)\s*l/min", text_lower)
            if match_min:
                try:
                    val = float(match_min.group(2).replace(",", "."))
                    specs["Flow_Rate"] = f"{round(val/60, 2)} l/s"
                except: pass

        # --- 3. Material V4A ---
        if any(x in text_lower for x in ["1.4404", "316l", "v4a", "marine grade", "high-quality stainless"]):
            specs["Material_V4A"] = "YES (V4A / 1.4404)"

        # --- 4. Certs ---
        if "1253" in text_lower: specs["Cert_EN1253"] = "YES"
        if "18534" in text_lower: specs["Cert_EN18534"] = "YES"

        # --- 5. Height (Rozšířená synonyma) ---
        # Geberit: "H=" or "Installation height"
        height_keywords = r"(height|bauhöhe|installation depth|einbauhöhe|montagehöhe|construction height)"
        
        # Range (XX-YY mm)
        h_range = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*mm', text_lower)
        if h_range:
            specs["Height_Adjustability"] = f"{h_range.group(1)}-{h_range.group(2)}"
        else:
            # Single value close to keyword
            h_single = re.search(height_keywords + r".{0,50}?(\d{2,3})\s*mm", text_lower)
            if h_single: specs["Height_Adjustability"] = f"Min {h_single.group(2)}"

        # --- 6. Colors ---
        if any(x in text_lower for x in ["surface", "finish", "color", "colour", "oberfläche", "farb"]):
             matches = re.findall(r'(\d+)\s*(?:surfaces|finishes|colors|farben)', text_lower)
             if matches: specs["Colors_Available"] = matches[0]

        # --- 7. Fleece ---
        if any(x in text_lower for x in ["dichtvlies", "sealing fleece", "membrane", "factory-mounted", "werkseitig"]):
            specs["Sealing_Fleece"] = "YES (Likely)"

        # --- 8. Outlet ---
        if "vertical" in text_lower or "senkrecht" in text_lower: 
            specs["Outlet_Direction"] = "Vertical"
        elif "horizontal" in text_lower or "waagerecht" in text_lower: 
            specs["Outlet_Direction"] = "Horizontal"
            
        return specs

    def extract_from_table(self, page, sku):
        """Pokusí se najít řádek tabulky s daným SKU a extrahovat text jen z něj."""
        # TECE často používá mezery v SKU (600 120)
        sku_variants = [sku, sku.replace(" ", ""), sku[:3] + " " + sku[3:] if len(sku)==6 else sku]
        
        best_text = ""
        
        for s in sku_variants:
            # Hledáme řádek (tr), který obsahuje SKU
            try:
                row = page.locator(f"tr:has-text('{s}')").first
                if row.count() > 0:
                    print(f"      🎯 Nalezen řádek v tabulce pro SKU: {s}")
                    # Získáme text celého řádku + hlavičky tabulky pro kontext
                    best_text = row.inner_text()
                    # Zkusíme získat i text celé tabulky pro kontext, ale prioritizujeme řádek
                    parent_table = row.locator("xpath=..")
                    return best_text + " " + parent_table.inner_text()[:500] # + kousek kontextu
            except: pass
            
        return None

    def run(self):
        self.check_excel_access()
        tasks = self.get_pending_tasks()
        print(f"🚀 Start: {len(tasks)} produktů (V3 - Table Logic).")
        
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()

            for task in tasks:
                sku = task['sku']
                brand = task['brand']
                domain = self.brand_domains.get(brand, "")
                
                # V3: Hledáme SKU v uvozovkách pro přesnou shodu
                search_query = f"site:{domain} \"{sku}\""
                ddg_url = f"https://duckduckgo.com/?q={search_query.replace(' ', '+')}"
                
                print(f"🔍 {brand} {sku}: Hledám...")
                
                try:
                    page.goto(ddg_url, timeout=30000)
                    
                    try: page.wait_for_selector("[data-testid='result-title-a']", timeout=5000)
                    except: 
                        print("   ⚠️ Žádné výsledky na DDG.")
                        # Fallback: Zkusíme bez uvozovek
                        page.goto(f"https://duckduckgo.com/?q=site:{domain}+{sku}", timeout=15000)
                        try: page.wait_for_selector("[data-testid='result-title-a']", timeout=5000)
                        except: continue

                    # Vezmeme první relevantní odkaz
                    links = page.locator("[data-testid='result-title-a']").all()[:3]
                    target_url = None
                    for link in links:
                        href = link.get_attribute("href")
                        if href and href.startswith("http") and "duckduckgo" not in href and not href.endswith(".pdf"):
                            target_url = href
                            break
                    
                    if target_url:
                        print(f"   👉 Jdu na: {target_url}")
                        page.goto(target_url, timeout=60000)
                        
                        # Cookies
                        try: page.locator("button").filter(has_text=re.compile("Accept|Alle|Souhlas|Zustimmen|OK", re.IGNORECASE)).first.click(timeout=2000)
                        except: pass
                        
                        # Rozbalení detailů
                        try: page.get_by_text(re.compile("Techni|Data|Daten|Details|Produktdaten", re.IGNORECASE)).first.click(timeout=1000)
                        except: pass
                        time.sleep(1)

                        # A. Zkusíme extrahovat data specificky z tabulky (pro TECE)
                        table_text = self.extract_from_table(page, sku)
                        
                        # B. Získáme text celé stránky
                        full_text = page.locator("body").inner_text()
                        
                        # Pokud jsme našli řádek v tabulce, analyzujeme ho prioritně
                        analysis_text = table_text if table_text else full_text
                        
                        specs = self.clean_specs(analysis_text, sku)
                        specs["Component_SKU"] = sku
                        specs["Manufacturer"] = brand
                        specs["Tech_Source_URL"] = page.url
                        
                        # Cena
                        try:
                            price = page.locator(".price, .product-price").first.text_content().strip()
                            specs["Sales_Price_UVP"] = price
                        except: pass

                        print(f"   ✅ Data: {specs}")
                        results.append(specs)
                    else:
                        print("   ❌ Odkaz nenalezen.")

                except Exception as e:
                    print(f"   🔥 Chyba: {e}")
                
                time.sleep(1.5)

            browser.close()

        if results:
            df = pd.DataFrame(results)
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                try: start = writer.sheets['Products_Tech'].max_row
                except: start = 0
                header = True if start == 0 else False
                df.to_excel(writer, sheet_name="Products_Tech", index=False, header=header, startrow=start)
            print("✅ Hotovo.")

if __name__ == "__main__":
    agent = UniversalTechAgentV3()
    agent.run()