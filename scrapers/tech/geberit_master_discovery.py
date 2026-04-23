import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import sys
import os

class GeberitMasterDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # Kompletní seznam sloupců pro Products_Tech
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        # Cílové produktové řady Geberit
        self.search_queries = [
            "CleanLine20", "CleanLine30", "CleanLine50", 
            "CleanLine60", "CleanLine80", "Rohbauset CleanLine"
        ]

    def run(self):
        print("\n" + "="*60)
        print("🕵️ Goro: Spouštím Geberit Discovery (Kompletní BS4 Fix)")
        print("="*60 + "\n", file=sys.stderr)

        # 1. NAČTENÍ NEBO VYTVOŘENÍ EXCELU S FIXEM TYPŮ
        if not os.path.exists(self.excel_path):
            df_tech = pd.DataFrame(columns=self.cols_tech)
        else:
            try:
                df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                # ZÁSADNÍ OPRAVA: Všechny sloupce hned po načtení převedeme na text
                for col in df_tech.columns:
                    df_tech[col] = df_tech[col].astype(str).replace(['nan', 'None'], '')
            except Exception:
                df_tech = pd.DataFrame(columns=self.cols_tech)

        existing_skus = set(df_tech['Component_SKU'].astype(str).str.upper().tolist())
        new_skus_found = []

        # 2. PROCHÁZENÍ KATALOGU
        for query in self.search_queries:
            print(f"🔎 Vyhledávám v Geberit katalogu: {query}", file=sys.stderr)
            search_url = f"https://catalog.geberit.de/de-DE/search?q={query.replace(' ', '+')}"
            
            try:
                r = requests.get(search_url, headers=self.headers, timeout=30)
                if r.status_code != 200:
                    continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Najdeme odkazy na produktové detaily
                target_links = []
                for a in soup.find_all('a', href=re.compile(r'/product/')):
                    href = a['href']
                    full_link = "https://catalog.geberit.de" + href if href.startswith("/") else href
                    if full_link not in target_links:
                        target_links.append(full_link)
                
                for url in list(set(target_links))[:10]: # Limit na 10 linků pro stabilitu
                    try:
                        res_prod = requests.get(url, headers=self.headers, timeout=20)
                        p_soup = BeautifulSoup(res_prod.text, 'html.parser')
                        
                        # Název produktu
                        h1_tag = p_soup.find('h1')
                        h1_text = h1_tag.get_text(strip=True) if h1_tag else f"Geberit {query}"
                        
                        # Hledání všech SKU (formát 154.xxx.xx.x)
                        page_text = p_soup.get_text()
                        found_skus = re.findall(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', page_text)
                        
                        for sku in set(found_skus):
                            sku_upper = sku.upper()
                            if sku_upper not in existing_skus and sku_upper not in [s['Component_SKU'] for s in new_skus_found]:
                                new_row = {col: "" for col in self.cols_tech}
                                new_row.update({
                                    "Component_SKU": sku_upper,
                                    "Manufacturer": "Geberit",
                                    "Product_Name": h1_text,
                                    "Tech_Source_URL": url,
                                    "Evidence_Text": f"Stabilní BS4 extrakce: {time.strftime('%d.%m.%Y')}"
                                })
                                new_skus_found.append(new_row)
                                print(f"   🌟 Nalezeno SKU: {sku_upper}", file=sys.stderr)
                        
                        time.sleep(0.5) 
                    except Exception:
                        continue

            except Exception as e:
                print(f"   ❌ Chyba vyhledávání {query}: {e}", file=sys.stderr)

        # 3. ZÁPIS DO EXCELU S FINÁLNÍM OŠETŘENÍM TYPŮ
        if new_skus_found:
            df_new = pd.DataFrame(new_skus_found)
            df_combined = pd.concat([df_tech, df_new], ignore_index=True)
            
            # Pojistka: Před zápisem vše na string (řeší chybu float64)
            for col in df_combined.columns:
                df_combined[col] = df_combined[col].astype(str).replace(['nan', 'None'], '')

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            print(f"\n✅ Discovery hotovo: Přidáno {len(new_skus_found)} nových SKU.")
        else:
            print("\n✅ Žádná nová SKU k přidání.")

if __name__ == "__main__":
    GeberitMasterDiscovery().run()