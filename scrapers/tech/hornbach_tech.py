import sys
import re
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

class HornbachTechScraper:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_tech"): os.makedirs("debug_tech")

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.")
                sys.exit(1)

    def get_tasks(self):
        if not os.path.exists(self.excel_path): return []
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                # Bereme jen Geberit a TECE
                if "Geberit" in name or "TECE" in name:
                    tasks.append({"sku": sku, "brand": "Geberit" if "Geberit" in name else "TECE"})
            
            seen = set()
            unique_tasks = []
            for t in tasks:
                if t['sku'] not in seen:
                    unique_tasks.append(t)
                    seen.add(t['sku'])
            return unique_tasks
        except: return []

    def process_product(self, page, task):
        sku = task['sku']
        brand = task['brand']
        print(f"\n{'='*50}\n🔍 Zpracovávám {brand} SKU: {sku} na Hornbach.de...\n{'='*50}", file=sys.stderr)
        
        extracted_data = {
            "Component_SKU": sku,
            "Tech_Source_URL": "N/A",
            "Flow_Rate_l_s": "N/A",
            "Material_V4A": "No (Standard)",
            "Cert_EN1253": "No",
            "Cert_EN18534": "No",
            "Height_Adjustability": "N/A",
            "Vertical_Outlet_Option": "Check Drawing",
            "Sealing_Fleece": "No",
            "Colors_Count": 1
        }

        try:
            # 1. Vyhledání na Hornbachu
            search_url = f"https://www.hornbach.de/s/{sku}"
            page.goto(search_url, timeout=60000)
            
            # Cookies
            try: page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            except: pass
            
            # Kontrola, jestli jsme na seznamu nebo přímo na produktu
            if "/s/" in page.url or page.locator("[data-testid='product-list-item']").count() > 0:
                print("   👉 Jsem na stránce vyhledávání, hledám správný produkt...", file=sys.stderr)
                # Klikne na první produkt, který vypadá relevantně
                first_product = page.locator("a[data-testid='product-list-item-link']").first
                if first_product.is_visible():
                    first_product.click()
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)
                else:
                    print("   ❌ Produkt nenalezen ve výsledcích vyhledávání.", file=sys.stderr)
                    return extracted_data
            else:
                print("   👉 Přímé přesměrování na detail produktu.", file=sys.stderr)

            extracted_data["Tech_Source_URL"] = page.url

            # 2. Otevření tabulky "Artikeldetails"
            try: 
                # Hornbach má často tlačítko "Mehr anzeigen" pro rozbalení specifikací
                page.locator("button").filter(has_text=re.compile("Mehr anzeigen|Alle Details", re.IGNORECASE)).first.click(timeout=2000)
                time.sleep(1)
            except: pass

            # 3. Těžba z tabulky (Hornbach používá element <dl> nebo tabulku)
            print("   Těžím strukturovaná data z tabulky...", file=sys.stderr)
            full_text = page.locator("body").inner_text()
            
            # Extrakce z tabulky
            # Najdeme kontejnery s klíči a hodnotami
            keys = page.locator("dt, th").all()
            values = page.locator("dd, td").all()
            
            table_data = {}
            for k, v in zip(keys, values):
                try: table_data[k.inner_text().strip().lower()] = v.inner_text().strip()
                except: pass

            # MATERIÁL
            mat = table_data.get("material", table_data.get("werkstoff", ""))
            if mat:
                extracted_data["Material_V4A"] = mat[:50]
                if "1.4404" in mat or "v4a" in mat.lower(): extracted_data["Material_V4A"] += " (Yes V4A)"
            else:
                if "1.4404" in full_text: extracted_data["Material_V4A"] = "Edelstahl (V4A)"
                elif "1.4301" in full_text: extracted_data["Material_V4A"] = "Edelstahl (V2A)"
                elif "Kunststoff" in full_text: extracted_data["Material_V4A"] = "Kunststoff"

            # PRŮTOK
            flow = table_data.get("ablaufleistung", table_data.get("abflusswert", ""))
            if flow:
                # Očistíme číslo
                flow_match = re.search(r"([\d.,]+)", flow)
                if flow_match:
                    val = float(flow_match.group(1).replace(",", "."))
                    if "l/min" in flow: val = val / 60
                    extracted_data["Flow_Rate_l_s"] = f"{val:.2f} l/s"
            else:
                # Fallback z textu
                flow_match = re.search(r"(?:Ablauf|Flow|Schluckvermögen).*?([\d.,]+)\s*(l/s|l/min)", full_text, re.IGNORECASE)
                if flow_match:
                    val = float(flow_match.group(1).replace(",", "."))
                    if flow_match.group(2).lower() == "l/min": val = val / 60
                    extracted_data["Flow_Rate_l_s"] = f"{val:.2f} l/s"

            # VÝŠKA
            height = table_data.get("bauhöhe", table_data.get("höhe", ""))
            if height: extracted_data["Height_Adjustability"] = height
            else:
                h_match = re.search(r"(?:Bauhöhe|Einbauhöhe).*?(\d+\s*[-–]\s*\d+)\s*mm", full_text, re.IGNORECASE)
                if h_match: extracted_data["Height_Adjustability"] = f"{h_match.group(1)} mm"

            # OSTATNÍ
            extracted_data["Cert_EN1253"] = "Yes" if "1253" in full_text else "No"
            extracted_data["Cert_EN18534"] = "Yes" if "18534" in full_text else "No"
            if re.search(r"Dichtvlies|werkseitig|Vlies", full_text, re.IGNORECASE):
                extracted_data["Sealing_Fleece"] = "Yes"

            print(f"   ✅ Materiál: {extracted_data['Material_V4A']}", file=sys.stderr)
            print(f"   ✅ Průtok:   {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
            print(f"   ✅ Výška:    {extracted_data['Height_Adjustability']}", file=sys.stderr)

        except Exception as e:
            print(f"   🔥 Chyba: {e}", file=sys.stderr)

        return extracted_data

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks:
            print("🚀 Žádné Geberit nebo TECE produkty nenalezeny v BOM_Definitions.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím Hornbach Scraper pro {len(tasks)} Geberit/TECE produktů...", file=sys.stderr)
        
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                data = self.process_product(page, task)
                results.append(data)
                time.sleep(1)

            browser.close()

        if results:
            df = pd.DataFrame(results)
            print("💾 Ukládám do Excelu...", file=sys.stderr)
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                try: start = writer.sheets['Products_Tech'].max_row
                except: start = 0
                header = True if start == 0 else False
                df.to_excel(writer, sheet_name="Products_Tech", index=False, header=header, startrow=start)
            print("✅ Hotovo. Data uložena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = HornbachTechScraper()
    scraper.run()