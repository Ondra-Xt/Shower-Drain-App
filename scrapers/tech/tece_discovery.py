from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import os

class TeceDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.base_url = "https://www.tece.com/de"
        
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
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                pd.DataFrame(columns=self.cols_tech).to_excel(writer, sheet_name='Products_Tech', index=False)
                pd.DataFrame(columns=self.cols_bom).to_excel(writer, sheet_name='BOM_Definitions', index=False)

    def handle_cookies(self, page):
        try:
            # TECE cookie banner
            page.locator("button:has-text('Alle akzeptieren'), a:has-text('Alle akzeptieren')").click(timeout=2000)
            print("🍪 Cookies potvrzeny.")
        except: pass

    def discover(self, search_sku="601200"): 
        self.ensure_excel_exists()
        print(f"🕵️‍♂️ TECE Discovery: Hledám žlab SKU '{search_sku}'...")
        
        discovered_products = []
        bom_items = []
        
        # Defaultní hodnoty (Fallback), kdyby web selhal
        fallback_data = {
            "Product_Name": "TECEdrainline Duschrinne gerade",
            "Length_mm": 1200,
            "Flow_Rate_ls": 0.8,
            "Target_Url": f"https://www.tece.com/de/search?search_api_fulltext={search_sku}"
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            try:
                # 1. Vyhledávání
                search_url = f"{self.base_url}/search?search_api_fulltext={search_sku}"
                print(f"🌍 Jdu na: {search_url}")
                page.goto(search_url, timeout=60000)
                self.handle_cookies(page)

                # 2. Klik na produkt (Agresivní textové hledání)
                print("🔎 Hledám odkaz na produkt...")
                target_url = None
                
                try:
                    # Hledáme odkaz, který obsahuje SKU a je viditelný
                    link = page.locator(f"a").filter(has_text=search_sku).first
                    if link.is_visible():
                        link.click()
                        page.wait_for_load_state("domcontentloaded")
                        target_url = page.url
                    else:
                        raise Exception("Odkaz nenalezen")
                except:
                    print("⚠️ Klikání selhalo. Používám Fallback data.")
                    target_url = fallback_data["Target_Url"]

                print(f"✅ Detail produktu: {target_url}")

                # --- 3. TĚŽBA DAT ---
                print("⛏️ Těžím technická data...")
                
                # Pokud jsme na detailu, zkusíme vytáhnout data
                if target_url != fallback_data["Target_Url"]:
                    body_text = page.locator("body").inner_text()
                    h1_text = page.locator("h1").first.inner_text().strip()
                    
                    # SKU
                    sku_match = re.search(r'Bestell-Nr\.:\s*(\d+)', body_text)
                    sku = sku_match.group(1) if sku_match else search_sku
                    
                    # Délka
                    len_match = re.search(r'Nennlänge:\s*(\d+)\s*mm', body_text)
                    length = int(len_match.group(1)) if len_match else 1200
                    
                    # Průtok
                    flow_match = re.search(r'(\d+[.,]\d+)\s*l/s', body_text)
                    flow_rate = float(flow_match.group(1).replace(',', '.')) if flow_match else 0.8
                else:
                    # Použijeme Fallback data
                    sku = search_sku
                    h1_text = fallback_data["Product_Name"]
                    length = fallback_data["Length_mm"]
                    flow_rate = fallback_data["Flow_Rate_ls"]

                # Sestavení dat
                product_data = {
                    "Brand": "TECE",
                    "Product_Name": h1_text,
                    "Article_Number_SKU": sku,
                    "Product_URL": target_url,
                    "Length_mm": length,
                    "Is_Cuttable": "NE",
                    "Flow_Rate_ls": flow_rate,
                    "Outlet_Type": "Horizontal/Vertical",
                    "Is_Outlet_Selectable": "ANO",
                    "Height_Min_mm": 95,
                    "Height_Max_mm": 150,
                    "Material_Body": "Nerez (Edelstahl)",
                    "Is_V4A": "NE", 
                    "Fleece_Preassembled": "ANO", # Seal System
                    "Cert_DIN_EN1253": "ANO",
                    "Cert_DIN_18534": "ANO",
                    "Colors_Count": 1,
                    "Tile_In_Possible": "ANO",
                    "Wall_Installation": "ANO",
                    "Completeness_Type": "Modular (BOM)",
                    "Ref_Price_Estimate_EUR": 0,
                    "Datasheet_URL": target_url,
                    "Evidence_Text": f"TECE Scan (Fallback: {target_url == fallback_data['Target_Url']})"
                }
                
                discovered_products.append(product_data)

                # --- 4. BOM (Klíčová část) ---
                # 1. Těleso
                bom_items.append({"Parent_Product_SKU": sku, "Component_Type": "Channel Body", "Component_Name": h1_text, "Component_SKU": sku, "Quantity": 1})
                # 2. Sifon
                bom_items.append({"Parent_Product_SKU": sku, "Component_Type": "Drain/Trap", "Component_Name": "TECEdrainline Ablauf DN 50 waagerecht", "Component_SKU": "650000", "Quantity": 1})
                # 3. Rošt Basic
                bom_items.append({"Parent_Product_SKU": sku, "Component_Type": "Grate/Cover", "Component_Name": "TECEdrainline Designrost 'basic'", "Component_SKU": "601210", "Quantity": 1})

            except Exception as e:
                print(f"❌ Kritická chyba: {e}")
            finally:
                browser.close()
        
        self.save_to_excel(discovered_products, bom_items)

    def save_to_excel(self, products, bom_items):
        if not products: return
        print(f"💾 Ukládám do Excelu...")
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            try: start_row = writer.sheets['Products_Tech'].max_row
            except: start_row = 0
            pd.DataFrame(products).to_excel(writer, sheet_name="Products_Tech", index=False, header=False, startrow=start_row)
            if bom_items:
                try: start_row_bom = writer.sheets['BOM_Definitions'].max_row
                except: start_row_bom = 0
                pd.DataFrame(bom_items).to_excel(writer, sheet_name="BOM_Definitions", index=False, header=False, startrow=start_row_bom)
        print("✅ TECE úspěšně přidáno.")

if __name__ == "__main__":
    bot = TeceDiscovery()
    bot.discover("601200")