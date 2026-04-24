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
        
        self.search_queries = [
            "CleanLine20", "CleanLine30", "CleanLine50", 
            "CleanLine60", "CleanLine80", "Rohbauset CleanLine"
        ]

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Excel soubor {self.excel_path} nebyl nalezen.")
            return

        print("\n" + "="*60)
        print("🕵️ Goro: Spouštím KROK 1: Geberit Master Catalog Discovery (BS4)")
        print("="*60 + "\n", file=sys.stderr)

        # Načtení dat a oprava typů (vakcína)
        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
            df_tech = df_tech.replace(['nan', 'None'], '')
        except Exception:
            df_tech = pd.DataFrame(columns=self.cols_tech)

        for col in self.cols_tech:
            if col not in df_tech.columns: df_tech[col] = ""

        existing_skus = set(df_tech['Component_SKU'].astype(str).str.upper().tolist())
        new_skus_found = []

        for query in self.search_queries:
            print(f"\n🔎 Hledám v oficiálním katalogu Geberit: {query}", file=sys.stderr)
            search_url = f"https://catalog.geberit.de/de-DE/search?q={query.replace(' ', '+')}"
            
            try:
                r = requests.get(search_url, headers=self.headers, timeout=30)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Posbíráme odkazy na produkty
                target_links = []
                for a in soup.find_all('a', href=re.compile(r'/product/')):
                    href = a['href']
                    full_link = "https://catalog.geberit.de" + href if href.startswith("/") else href
                    if full_link not in target_links: target_links.append(full_link)
                
                # Omezíme to na max 8 produktů, jak jsi to měl v Playwrightu
                for url in list(set(target_links))[:8]:
                    try:
                        res_prod = requests.get(url, headers=self.headers, timeout=20)
                        p_soup = BeautifulSoup(res_prod.text, 'html.parser')
                        
                        h1_tag = p_soup.find('h1')
                        h1_text = h1_tag.get_text(strip=True) if h1_tag else f"Geberit {query}"
                        
                        # TRIK: Získáme text z HTML elementů + z Javascriptových dat v kódu stránky
                        page_text = p_soup.get_text() + str(p_soup) 
                        
                        # Nekompromisní hledání SKU formátu (154.xxx.xx.x)
                        found_skus = re.findall(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', page_text)
                        
                        for sku in set(found_skus):
                            sku_upper = sku.upper()
                            if sku_upper not in existing_skus and sku_upper not in [s['Component_SKU'] for s in new_skus_found]:
                                new_row = {col: "" for col in self.cols_tech}
                                new_row.update({
                                    "Component_SKU": str(sku_upper),
                                    "Manufacturer": "Geberit",
                                    "Product_Name": str(h1_text),
                                    "Tech_Source_URL": str(url),
                                    "Evidence_Text": f"Stabilní BS4 extrakce: {time.strftime('%d.%m.%Y')}"
                                })
                                new_skus_found.append(new_row)
                                print(f"   🌟 Nalezeno SKU: {sku_upper} ({h1_text})", file=sys.stderr)
                                
                    except Exception as e: pass
                    time.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Chyba vyhledávání {query}: {e}", file=sys.stderr)

        # INJEKCE SIFONŮ (Tohle tam prostě musíme mít jako pojistku pro kalkulátor)
        essential_siphons = [
            {"Component_SKU": "154.150.00.1", "Manufacturer": "Geberit", "Product_Name": "Rohbauset Duschrinnen H90", "Tech_Source_URL": "https://catalog.geberit.de/de-DE/product/PRO_100918", "Flow_Rate_l_s": "0.8"},
            {"Component_SKU": "154.152.00.1", "Manufacturer": "Geberit", "Product_Name": "Rohbauset Duschrinnen H65", "Tech_Source_URL": "https://catalog.geberit.de/de-DE/product/PRO_100919", "Flow_Rate_l_s": "0.4"}
        ]
        for s in essential_siphons:
            if s["Component_SKU"] not in existing_skus and s["Component_SKU"] not in [x['Component_SKU'] for x in new_skus_found]:
                new_row = {col: "" for col in self.cols_tech}
                new_row.update(s)
                new_skus_found.append(new_row)
                print(f"   💉 INJEKCE SIFONU: {s['Component_SKU']} - Pojistka pro kalkulátor", file=sys.stderr)


        if new_skus_found:
            print("\n💾 Ukládám oficiální Geberit SKU kódy do Excelu...", file=sys.stderr)
            
            df_new = pd.DataFrame(new_skus_found).astype(str).replace(['nan', 'None'], '')
            df_combined = pd.concat([df_tech, df_new], ignore_index=True)
            df_combined = df_combined.astype(str).replace(['nan', 'None'], '')

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            print(f"✅ Úspěšně zaneseno {len(new_skus_found)} nových variant žlabů!")
        else:
            print("\n✅ Všechny varianty z oficiálního katalogu už v Excelu máme.")

if __name__ == "__main__":
    GeberitMasterDiscovery().run()