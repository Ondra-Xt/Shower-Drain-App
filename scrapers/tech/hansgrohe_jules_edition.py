import sys
import json
import re
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

class HansgroheJulesScraper:
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

    def get_hansgrohe_tasks(self):
        if not os.path.exists(self.excel_path): return []
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                if "Hansgrohe" in name or "RainDrain" in name or "uBox" in name:
                    tasks.append({"sku": sku, "name": name})
            
            # Unikátní podle SKU
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
        product_name_guess = task['name']
        print(f"🔍 Processing SKU: {sku}...", file=sys.stderr)
        
        extracted_data = {
            "Component_SKU": sku,
            "Tech_Source_URL": "",
            "Flow_Rate": "N/A", "Material_V4A": "No (Standard)", 
            "Cert_EN1253": "No", "Cert_EN18534": "No",
            "Height_Adjustability": "N/A", "Sales_Price_UVP": "N/A",
            "Outlet_Direction": "Check Drawing", "Sealing_Fleece": "No",
            "Colors_Available": 1
        }

        try:
            # 1. Jdi na domovskou stránku (pokud tam nejsme)
            if "hansgrohe.de" not in page.url:
                page.goto("https://www.hansgrohe.de/")
            
            # 2. Cookies (jen pro jistotu, kdyby vyskočily znovu)
            try:
                accept_btn = page.locator("#onetrust-accept-btn-handler").or_(page.get_by_role("button", name="Alle akzeptieren")).first
                if accept_btn.is_visible():
                    accept_btn.click()
                    time.sleep(1)
            except: pass

            # 3. Hledání (Search Interaction - Jules Logic)
            search_input = None
            
            # Zkusíme najít lupu a kliknout
            potential_selectors = [
                "header button.search-toggle", "header .icon-search", "header .icon-magnifier",
                "header [data-icon='search']", "header button[title='Suche']", "header button"
            ]
            
            search_btn = None
            for sel in potential_selectors:
                locs = page.locator(sel).all()
                for loc in locs:
                    if loc.is_visible():
                        txt = (loc.text_content() or "").lower()
                        if "partner" not in txt and "händler" not in txt:
                            search_btn = loc
                            break
                if search_btn: break
            
            if search_btn:
                search_btn.click()
            else:
                # Force click na oblast, kde bývá lupa
                page.mouse.click(1800, 50) # Hrubý odhad vpravo nahoře
            
            # Čekání na input
            try:
                # Julesova logika pro nalezení inputu
                search_input = page.locator("input.js-searchbar-input").or_(page.locator("input[name='text']")).or_(page.locator("input[type='search']:not([id*='partner'])")).first
                search_input.wait_for(state="visible", timeout=5000)
            except:
                print("   ⚠️ Search input not visible. Retrying generic search icon click...", file=sys.stderr)
                # Zkusíme znovu kliknout
                if search_btn: search_btn.click(force=True)
                time.sleep(1)
                search_input = page.locator("input[type='search'], input[name='text']").first

            # Zapsat SKU
            search_input.fill(sku)
            time.sleep(0.5)
            search_input.press("Enter")
            
            # 4. Výsledky (Processing Results)
            try:
                page.wait_for_load_state("domcontentloaded")
                time.sleep(2)
            except: pass
            
            # Hledání odkazu na produkt
            # Strategie: Najít odkaz, který obsahuje SKU nebo název produktu
            found_link = None
            
            # A. Přímá shoda SKU v odkazu
            links = page.locator("a[href*='articledetail'], a[href*='produktdetail']").all()
            for link in links:
                href = link.get_attribute("href")
                if href and sku in href and not href.endswith(".pdf"):
                    found_link = link
                    break
            
            # B. Fallback: Hledání podle textu odkazu (pokud SKU nenašel)
            if not found_link:
                print("   ⚠️ Direct SKU link not found. Checking text match...", file=sys.stderr)
                # Zkusíme hledat text RainDrain atd.
                for link in links:
                    txt = link.inner_text()
                    if "RainDrain" in txt or "uBox" in txt:
                        found_link = link
                        print(f"   👉 Found via heuristic: {txt}", file=sys.stderr)
                        break

            if found_link:
                found_link.click()
                page.wait_for_load_state("domcontentloaded")
                extracted_data["Tech_Source_URL"] = page.url
                
                # 5. Extrakce dat (Jules Regex Logic)
                # Rozbalit technická data
                try: page.get_by_text(re.compile("Techni|Data|Daten|Details", re.IGNORECASE)).first.click(timeout=1000)
                except: pass
                
                full_text = page.locator("body").inner_text()
                # Normalize
                full_text = re.sub(r'\s+', ' ', full_text)

                # Flow Rate
                flow_match = re.search(r"(?:Ablaufleistung|Flow rate).*?([\d.,]+)\s*(l/s|l/min)", full_text, re.IGNORECASE)
                if flow_match:
                    val = float(flow_match.group(1).replace(",", "."))
                    if flow_match.group(2).lower() == "l/min": val = val / 60.0
                    extracted_data["Flow_Rate"] = f"{val:.2f} l/s"
                
                # Material
                if re.search(r"1\.4404|V4A|316L", full_text, re.IGNORECASE):
                    extracted_data["Material_V4A"] = "Yes"
                
                # Certs
                extracted_data["Cert_EN1253"] = "Yes" if "1253" in full_text else "No"
                extracted_data["Cert_EN18534"] = "Yes" if "18534" in full_text else "No"
                
                # Height
                h_match = re.search(r"(?:Bauhöhe|Einbauhöhe|Height).*?(\d+\s*-\s*\d+)\s*mm", full_text, re.IGNORECASE)
                if h_match: extracted_data["Height_Adjustability"] = f"{h_match.group(1)} mm"
                
                # Outlet
                dirs = []
                if "waagerecht" in full_text.lower(): dirs.append("Horizontal")
                if "senkrecht" in full_text.lower(): dirs.append("Vertical")
                if dirs: extracted_data["Outlet_Direction"] = "/".join(dirs)

                # Fleece
                if re.search(r"Dichtvlies|werkseitig|pre-mounted", full_text, re.IGNORECASE):
                    extracted_data["Sealing_Fleece"] = "Yes"
                
                # Colors
                try:
                    count = page.locator(".color-switch__item, .variant-switch__item").count()
                    if count > 1: extracted_data["Colors_Available"] = count
                except: pass

                # Cena
                try:
                    price = page.locator(".price__value, .product-price").first.inner_text().strip()
                    extracted_data["Sales_Price_UVP"] = price
                except: pass

                print(f"   ✅ Data extracted: {extracted_data}", file=sys.stderr)
            else:
                print("   ❌ Product link not found in results.", file=sys.stderr)

        except Exception as e:
            print(f"   🔥 Error processing {sku}: {e}", file=sys.stderr)
            page.goto("https://www.hansgrohe.de/")
        
        return extracted_data

    def run(self):
        self.check_excel_access()
        tasks = self.get_hansgrohe_tasks()
        print(f"🚀 Starting Jules-Edition Scraper for {len(tasks)} products...", file=sys.stderr)
        
        results = []

        with sync_playwright() as p:
            # Setup podle Julese (Firefox/Chromium + Viewport)
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Pre-load home & cookies
            page.goto("https://www.hansgrohe.de/")
            try:
                page.locator("#onetrust-accept-btn-handler").or_(page.get_by_role("button", name="Alle akzeptieren")).first.click(timeout=3000)
            except: pass

            for task in tasks:
                data = self.process_product(page, task)
                results.append(data)
                time.sleep(1)

            browser.close()

        if results:
            df = pd.DataFrame(results)
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                try: start = writer.sheets['Products_Tech'].max_row
                except: start = 0
                header = True if start == 0 else False
                df.to_excel(writer, sheet_name="Products_Tech", index=False, header=header, startrow=start)
            print("✅ All data saved to Excel.", file=sys.stderr)

if __name__ == "__main__":
    scraper = HansgroheJulesScraper()
    scraper.run()