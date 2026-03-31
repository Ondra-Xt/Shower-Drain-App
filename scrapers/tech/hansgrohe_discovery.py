from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import os

class HansgroheDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.base_url = "https://www.hansgrohe.de"
        
        # Definice sloupců
        self.cols_tech = [
            "Brand", "Product_Name", "Article_Number_SKU", "Product_URL",
            "Length_mm", "Is_Cuttable", "Flow_Rate_ls", "Outlet_Type",
            "Is_Outlet_Selectable", "Height_Min_mm", "Height_Max_mm",
            "Material_Body", "Is_V4A", "Fleece_Preassembled",
            "Cert_DIN_EN1253", "Cert_DIN_18534", "Colors_Count",
            "Tile_In_Possible", "Wall_Installation", "Completeness_Type",
            "Ref_Price_Estimate_EUR", "Datasheet_URL", "Evidence_Text"
        ]
        self.cols_bom = [
            "Parent_Product_SKU", "Component_Type", "Component_Name", "Component_SKU", "Quantity"
        ]

    def ensure_excel_exists(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Vytvářím nový Excel: {self.excel_path}")
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                pd.DataFrame(columns=self.cols_tech).to_excel(writer, sheet_name='Products_Tech', index=False)
                pd.DataFrame(columns=self.cols_bom).to_excel(writer, sheet_name='BOM_Definitions', index=False)

    def discover(self, search_query="56053800"):
        self.ensure_excel_exists()
        print(f"🕵️‍♂️ Hansgrohe Discovery: Cíl '{search_query}'...")
        
        discovered_products = []
        bom_items = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            try:
                # 1. Vyhledání produktu
                search_url = f"{self.base_url}/suche?q={search_query}"
                print(f"🌍 Jdu na: {search_url}")
                page.goto(search_url, timeout=60000)
                
                # 2. Cookies (Zkusíme více selektorů)
                try:
                    time.sleep(2)
                    page.locator("button#onetrust-accept-btn-handler, .uc-list-button__accept-all").first.click(timeout=3000)
                    print("🍪 Cookies potvrzeny.")
                    time.sleep(1)
                except: pass

                # 3. Proklik na detail (AGRESIVNÍ METODA)
                if "articledetail" not in page.url:
                    print("🔎 Hledám odkaz na produkt...")
                    page.wait_for_load_state("networkidle") # Počkáme na dotáhnutí JS
                    
                    found = False
                    # Strategie A: Najdi jakýkoliv odkaz, který obsahuje 'articledetail'
                    # Bez ohledu na to, v jakém divu je schovaný
                    try:
                        link = page.locator("a[href*='articledetail']").first
                        if link.is_visible():
                            print("👉 Klikám na nalezený odkaz (Strategie A)...")
                            link.click()
                            found = True
                    except: pass
                    
                    # Strategie B: Fallback - Přímá navigace, pokud klikání selže
                    if not found and search_query == "56053800":
                        print("⚠️ Klikání selhalo. Používám ZÁLOŽNÍ PŘÍMÝ ODKAZ...")
                        direct_url = "https://www.hansgrohe.de/articledetail-raindrain-flex-fertigset-duschrinne-1000-fuer-wandmontage-kuerzbar-56053800"
                        page.goto(direct_url)
                        found = True

                    if not found:
                        print("❌ Nepodařilo se najít ani kliknout na produkt.")
                        # Uděláme screenshot, ať víme, co robot viděl
                        page.screenshot(path="debug_click_fail.png")
                        return

                # Čekáme na načtení detailu
                page.wait_for_load_state("domcontentloaded")
                target_url = page.url
                print(f"✅ Jsem na detailu: {target_url}")

                # --- 4. TĚŽBA DAT ---
                print("⛏️ Těžím data...")
                # Scroll pro načtení dynamických tabulek
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(2)
                
                body_text = page.locator("body").inner_text()
                h1_text = page.locator("h1").first.inner_text().strip()

                # A. SKU
                sku = search_query 
                
                # B. Průtok
                flow_rate = None
                flow_matches = re.findall(r'(\d+[.,]?\d*)\s*(l/min|l/s)', body_text, re.IGNORECASE)
                for val_str, unit in flow_matches:
                    val = float(val_str.replace(',', '.'))
                    if unit.lower() == "l/min":
                        flow_rate = round(val / 60, 2)
                    else:
                        flow_rate = val
                    if flow_rate > 0: break
                print(f"💧 Průtok: {flow_rate} l/s")

                # C. Výška
                h_min, h_max = 0, 0
                height_matches = re.findall(r'(\d+)\s*-\s*(\d+)\s*mm', body_text)
                if height_matches:
                    h_min = int(height_matches[0][0])
                    h_max = int(height_matches[0][1])
                else:
                    h_single = re.search(r'(?:ab|min\.)\s*(\d+)\s*mm', body_text)
                    if h_single:
                        h_min = int(h_single.group(1))
                print(f"📏 Výška: {h_min} - {h_max} mm")

                # D. Datasheet
                datasheet_url = target_url
                try:
                    pdf_link = page.locator("a[href*='.pdf']").first
                    if pdf_link.count() > 0:
                        href = pdf_link.get_attribute("href")
                        datasheet_url = href if href.startswith("http") else self.base_url + href
                except: pass

                # E. BOM Logika
                completeness = "Modular (BOM)" 
                if "uBox" not in body_text and "Grundkörper" not in body_text:
                     if "Flex" in h1_text: completeness = "Modular (BOM)"

                product_data = {
                    "Brand": "Hansgrohe",
                    "Product_Name": h1_text,
                    "Article_Number_SKU": sku,
                    "Product_URL": target_url,
                    "Length_mm": 1000, 
                    "Is_Cuttable": "ANO",
                    "Flow_Rate_ls": flow_rate,
                    "Outlet_Type": "Horizontal/Vertical",
                    "Is_Outlet_Selectable": "ANO",
                    "Height_Min_mm": h_min,
                    "Height_Max_mm": h_max,
                    "Material_Body": "Nerez V4A (1.4404)" if ("1.4404" in body_text or "V4A" in body_text) else "Nerez (Standard)",
                    "Is_V4A": "ANO" if ("1.4404" in body_text or "V4A" in body_text) else "NE",
                    "Fleece_Preassembled": "ANO" if "Dichtvlies" in body_text else "NE",
                    "Cert_DIN_EN1253": "ANO" if "1253" in body_text else "NE",
                    "Cert_DIN_18534": "ANO" if "18534" in body_text else "NE",
                    "Colors_Count": 1,
                    "Tile_In_Possible": "NE",
                    "Wall_Installation": "ANO",
                    "Completeness_Type": completeness,
                    "Ref_Price_Estimate_EUR": 0,
                    "Datasheet_URL": datasheet_url,
                    "Evidence_Text": f"Deep Scan SKU {sku}. Flow: {flow_rate}, Height: {h_min}-{h_max}"
                }
                
                discovered_products.append(product_data)

                if completeness == "Modular (BOM)":
                    bom_items.append({"Parent_Product_SKU": sku, "Component_Type": "Base Set", "Component_Name": "uBox universal", "Component_SKU": "01000180", "Quantity": 1})
                    bom_items.append({"Parent_Product_SKU": sku, "Component_Type": "Finish Set", "Component_Name": h1_text, "Component_SKU": sku, "Quantity": 1})

            except Exception as e:
                print(f"❌ Kritická chyba: {e}")
                page.screenshot(path="debug_critical_fail.png")
            finally:
                browser.close()
        
        self.save_to_excel(discovered_products, bom_items)

    def save_to_excel(self, products, bom_items):
        if not products:
            print("⚠️ Žádná data nebyla získána.")
            return
        
        print(f"💾 Ukládám do Excelu...")
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            try: start_row = writer.sheets['Products_Tech'].max_row
            except: start_row = 0
            pd.DataFrame(products).to_excel(writer, sheet_name="Products_Tech", index=False, header=False, startrow=start_row)
            
            if bom_items:
                try: start_row_bom = writer.sheets['BOM_Definitions'].max_row
                except: start_row_bom = 0
                pd.DataFrame(bom_items).to_excel(writer, sheet_name="BOM_Definitions", index=False, header=False, startrow=start_row_bom)
        print("✅ Hotovo.")

if __name__ == "__main__":
    bot = HansgroheDiscovery()
    bot.discover("56053800")