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
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        # Klíčové designové řady Geberit
        self.search_queries = [
            "CleanLine20",
            "CleanLine30",
            "CleanLine50",
            "CleanLine60",
            "CleanLine80",
            "Rohbauset CleanLine"
        ]

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Excel soubor {self.excel_path} nebyl nalezen. Vytvářím nový...", file=sys.stderr)
            df_tech = pd.DataFrame(columns=self.cols_tech)
        else:
            try:
                df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
            except Exception:
                df_tech = pd.DataFrame(columns=self.cols_tech)

        existing_skus = set(df_tech['Component_SKU'].astype(str).str.upper().tolist())
        new_skus_found = []

        print("\n" + "="*60)
        print("🕵️ Goro: Spouštím Geberit Discovery (Stabilní BS4 verze)")
        print("="*60 + "\n", file=sys.stderr)

        for query in self.search_queries:
            print(f"🔎 Hledám v katalogu Geberit: {query}", file=sys.stderr)
            search_url = f"https://catalog.geberit.de/de-DE/search?q={query.replace(' ', '+')}"
            
            try:
                response = requests.get(search_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Najdeme všechny odkazy na produkty (/product/)
                target_links = []
                for a in soup.find_all('a', href=re.compile(r'/product/')):
                    href = a['href']
                    full_link = "https://catalog.geberit.de" + href if href.startswith("/") else href
                    if full_link not in target_links:
                        target_links.append(full_link)
                
                # Limitujeme na prvních 10 unikátních výsledků pro stabilitu
                target_links = list(set(target_links))[:10]
                
                for url in target_links:
                    try:
                        res_prod = requests.get(url, headers=self.headers, timeout=20)
                        if res_prod.status_code != 200:
                            continue
                            
                        p_soup = BeautifulSoup(res_prod.text, 'html.parser')
                        
                        # Získání názvu produktu (H1)
                        h1_tag = p_soup.find('h1')
                        h1_text = h1_tag.get_text(strip=True) if h1_tag else f"Geberit {query}"
                        
                        # Extrakce SKU kódů (formát 154.xxx.xx.x) z celého textu stránky
                        page_text = p_soup.get_text()
                        found_skus = re.findall(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', page_text)
                        found_skus = list(set([s.upper() for s in found_skus]))

                        for sku in found_skus:
                            if sku not in existing_skus and sku not in [s['Component_SKU'] for s in new_skus_found]:
                                new_row = {col: "" for col in self.cols_tech}
                                new_row.update({
                                    "Component_SKU": sku,
                                    "Manufacturer": "Geberit",
                                    "Product_Name": h1_text,
                                    "Tech_Source_URL": url,
                                    "Evidence_Text": f"Získáno z oficiálního katalogu BS4 dne {time.strftime('%d.%m.%Y')}"
                                })
                                new_skus_found.append(new_row)
                                print(f"   🌟 Nalezeno SKU: {sku} ({h1_text})", file=sys.stderr)
                        
                        time.sleep(0.5) # Rychlá, ale bezpečná prodleva
                        
                    except Exception:
                        continue

            except Exception as e:
                print(f"   ❌ Chyba při hledání {query}: {e}", file=sys.stderr)

        if new_skus_found:
            print("\n💾 Ukládám Geberit SKU kódy do Excelu...", file=sys.stderr)
            df_new = pd.DataFrame(new_skus_found)
            df_combined = pd.concat([df_tech, df_new], ignore_index=True)
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            print(f"✅ Úspěšně zaneseno {len(new_skus_found)} nových variant žlabů!")
        else:
            print("\n✅ Žádné nové varianty nebyly nalezeny.", file=sys.stderr)

if __name__ == "__main__":
    GeberitMasterDiscovery().run()