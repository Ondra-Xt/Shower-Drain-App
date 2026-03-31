import pandas as pd
import re
import sys
import time
import os
import urllib.parse
from playwright.sync_api import sync_playwright

class DallmerTechScraperV1:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.")
                sys.exit(1)

    def get_tasks(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            seen = set()
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                # Hledáme vše co je Dallmer
                if "dallmer" in name.lower():
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except: return []

    def extract_flow_rate(self, text):
        # Hledá 0,5 l/s, 0.8 l/s atd.
        matches = re.finditer(r"(\d+(?:[.,]\d+)?)\s*(l/s|l/min|l\s*/\s*sek)", text, re.IGNORECASE)
        max_flow = 0.0
        for m in matches:
            val_str = m.group(1).replace(",", ".")
            try:
                val = float(val_str)
                if "min" in m.group(2).lower(): val = val / 60.0
                # Dallmer mívá vyšší průtoky (až 1.0 l/s), upravíme range
                if 0.3 <= val <= 3.5 and val > max_flow: max_flow = val
            except: pass
        return f"{max_flow:.2f} l/s" if max_flow > 0 else "N/A"

    def extract_material(self, text):
        text_lower = text.lower()
        if "v4a" in text_lower or "1.4404" in text_lower or "316l" in text_lower: return "Edelstahl V4A (1.4404) (Yes V4A)"
        elif "v2a" in text_lower or "1.4301" in text_lower or "edelstahl" in text_lower: return "Edelstahl V2A (1.4301)"
        elif "polypropylen" in text_lower or "kunststoff" in text_lower or "pp" in text_lower: return "Kunststoff (Polypropylen)"
        return "N/A"

    def extract_height(self, text):
        # Bauhöhe, Einbauhöhe
        range_match = re.search(r"(?:Bauhöhe|Einbauhöhe|Höhe)[^\d]{0,20}?(\d{2,3})\s*(?:-|–|\s+bis\s+)\s*(\d{2,3})\s*mm", text, re.IGNORECASE)
        if range_match: return f"{range_match.group(1)}-{range_match.group(2)} mm"
        
        single_matches = re.finditer(r"(?:Bauhöhe|Einbauhöhe|Höhe)[^\d]{0,20}?(\d+(?:[.,]\d+)?)\s*mm", text, re.IGNORECASE)
        for sm in single_matches:
            val = float(sm.group(1).replace(",", "."))
            if val > 40: return f"{sm.group(1)} mm" # Dallmer tělesa jsou vyšší (cca 60-90mm)
        return "N/A"

    def search_shops_stealth(self, page, sku, raw_name):
        # Dallmer má číselné SKU, zkusíme hledat jen to číslo
        clean_sku = re.sub(r'[^0-9]', '', sku) 
        if len(clean_sku) < 4: clean_sku = sku # Pokud to není číslo, necháme původní
        
        shops = [
            {
                "name": "Megabad.com",
                "url": "https://www.megabad.com/",
                "cookie_sel": ".cmpboxbtnyes, #cmpbntyestxt, button:has-text('Alle')",
                "search_input": "input#search, input[name='q'], input[type='search']",
                "link_sel": ".product-box a, .product-list a, .search-result a",
                "tab_sel": "button:has-text('Technische Daten'), a:has-text('Details')"
            },
            {
                "name": "Bausep.de",
                "url": "https://www.bausep.de/",
                "cookie_sel": "button#btn-cookie-allow, button:has-text('Alle akzeptieren')",
                "search_input": "input[id='search']",
                "link_sel": "a.product-item-link",
                "tab_sel": "div.data.item.title, a.data.switch"
            }
        ]
        
        for shop in shops:
            print(f"         🛒 Jdu do e-shopu: {shop['name']}...", file=sys.stderr)
            try:
                page.goto(shop["url"], timeout=30000)
                try: page.locator(shop["cookie_sel"]).first.click(timeout=2000)
                except: pass
                time.sleep(1.5)

                # 1. Fyzické psaní do vyhledávání
                inp = page.locator(shop["search_input"]).first
                if inp.is_visible():
                    inp.click(force=True)
                    inp.fill(clean_sku)
                    page.keyboard.press("Enter")
                else:
                    # Zkusíme kliknout na lupu, pokud input není vidět
                    try: 
                        page.locator(".search-toggle, .header-search-icon").first.click()
                        time.sleep(1)
                        page.locator(shop["search_input"]).first.fill(clean_sku)
                        page.keyboard.press("Enter")
                    except:
                        print(f"         ⚠️ {shop['name']}: Nenašel jsem vyhledávání.", file=sys.stderr)
                        continue

                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)

                # 2. Detekce výsledků nebo detailu
                is_detail = False
                if shop["name"] == "Megabad.com":
                    is_detail = page.locator(".product-detail-price").count() > 0
                elif shop["name"] == "Bausep.de":
                    is_detail = page.locator("button.tocart").count() > 0

                if not is_detail:
                    # Klikneme na první výsledek
                    links = page.locator(shop["link_sel"]).all()
                    target_link = None
                    for l in links:
                        if l.is_visible() and "bewertung" not in l.get_attribute("href", ""):
                            target_link = l
                            break
                    
                    if target_link:
                        print(f"         🖱️ Klikám na nalezený produkt...", file=sys.stderr)
                        target_link.click(timeout=5000)
                        page.wait_for_load_state("domcontentloaded")
                        time.sleep(2)
                    else:
                        print(f"         ⚠️ {shop['name']}: Žádný produkt nenalezen.", file=sys.stderr)
                        continue
                else:
                    print(f"         🚀 {shop['name']}: Přesměrováno rovnou do detailu!", file=sys.stderr)

                # 3. Čtení dat
                if shop["tab_sel"]:
                    try: page.locator(shop["tab_sel"]).first.click(timeout=1000)
                    except: pass
                    time.sleep(1)

                content = page.evaluate("document.body.innerText")
                f_rate = self.extract_flow_rate(content)
                h_adj = self.extract_height(content)
                mat = self.extract_material(content)

                if f_rate != "N/A" or h_adj != "N/A":
                    return content, page.url
                else:
                    print(f"         ⚠️ Data nenalezena v popisu.", file=sys.stderr)

            except Exception as e:
                print(f"         ⚠️ Chyba {shop['name']}: {e}", file=sys.stderr)
        
        return "", "N/A"

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        if not tasks: return
            
        print(f"🚀 Spouštím Dallmer Tech Scraper V1 (Stealth)...", file=sys.stderr)
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám: {sku}\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku,
                    "Manufacturer": "Dallmer",
                    "Tech_Source_URL": "N/A",
                    "Datasheet_URL": "N/A",
                    "Flow_Rate_l_s": "N/A",
                    "Material_V4A": "N/A",
                    "Cert_EN1253": "No",
                    "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A",
                    "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No",
                    "Color_Count": 1
                }

                content, url = self.search_shops_stealth(page, sku, raw_name)
                
                if content:
                    extracted_data["Tech_Source_URL"] = url
                    extracted_data["Flow_Rate_l_s"] = self.extract_flow_rate(content)
                    extracted_data["Height_Adjustability"] = self.extract_height(content)
                    extracted_data["Material_V4A"] = self.extract_material(content)
                    
                    if "EN 1253" in content or "DIN 1253" in content: extracted_data["Cert_EN1253"] = "Yes"
                    if "18534" in content: extracted_data["Cert_EN18534"] = "Yes"
                    if "manschette" in content.lower() or "vlies" in content.lower(): extracted_data["Sealing_Fleece"] = "Yes"

                # Logika pro Dallmer (CeraLine vs CeraDrain)
                if "CeraLine" in raw_name:
                    if "Plan" in raw_name: 
                        if extracted_data["Height_Adjustability"] == "N/A": extracted_data["Height_Adjustability"] = "90 mm"
                    else:
                        if extracted_data["Height_Adjustability"] == "N/A": extracted_data["Height_Adjustability"] = "110 mm"
                
                # Odtok
                if "senkrecht" in content.lower() or "vertical" in content.lower(): extracted_data["Vertical_Outlet_Option"] = "Vertical"
                else: extracted_data["Vertical_Outlet_Option"] = "Horizontal"

                print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                
                results.append(extracted_data)

            browser.close()

        if results:
            df = pd.DataFrame(results)[self.cols]
            try:
                existing_df = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                for _, new_row in df.iterrows():
                    s = str(new_row['Component_SKU']).strip().lower()
                    existing_df = existing_df[existing_df['Component_SKU'].astype(str).str.strip().str.lower() != s]
                final_df = pd.concat([existing_df, df], ignore_index=True)
            except:
                final_df = df
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                final_df.to_excel(writer, sheet_name="Products_Tech", index=False)
            print("\n✅ Hotovo! Dallmer uložen.", file=sys.stderr)

if __name__ == "__main__":
    scraper = DallmerTechScraperV1()
    scraper.run()