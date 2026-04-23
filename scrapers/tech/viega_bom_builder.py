import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import sys
import os

class ViegaBOMBuilder:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.cols_tech = [
            "Article_Number_SKU", "Brand", "Product_URL", "Datasheet_URL", 
            "Flow_Rate_ls", "Is_V4A", "Color", "Cert_DIN_EN1253", "Cert_DIN_18534", 
            "Height_Min_mm", "Height_Max_mm", "Is_Cuttable", "Product_Name", "Evidence_Text"
        ]

    def extract_bom_details(self, url):
        """Vytáhne technické detaily pomocí BeautifulSoup (bez prohlížeče)."""
        print(f"   🔍 Analyzuji detaily (BS4): {url}", file=sys.stderr)
        try:
            r = requests.get(url, headers=self.headers, timeout=20)
            if r.status_code != 200:
                return None
            
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Základní metadata
            h1 = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Neznámý produkt"
            body_text = soup.get_text()
            
            # Detekce průtoku (l/s)
            flow = ""
            m_flow = re.search(r'(\d+(?:,\d+)?)\s*l/s', body_text)
            if m_flow: 
                flow = m_flow.group(1).replace(',', '.')

            # Detekce materiálu V4A
            is_v4a = "No"
            if any(x in body_text.lower() for x in ["v4a", "1.4404", "edelstahl 1.4404"]):
                is_v4a = "Yes"

            # Detekce certifikace
            cert_1253 = "Yes" if "1253" in body_text else "No"
            cert_18534 = "Yes" if "18534" in body_text else "No"

            # Hledání SKU
            found_sku = ""
            sku_match = re.search(r'Artikel\s*([1-9]\d{2}[ \u00A0]?\d{3})', body_text)
            if sku_match:
                found_sku = sku_match.group(1).replace(" ", "").replace("\u00A0", "")

            return {
                "Article_Number_SKU": found_sku,
                "Brand": "Viega",
                "Product_Name": h1,
                "Product_URL": url,
                "Flow_Rate_ls": flow,
                "Is_V4A": is_v4a,
                "Cert_DIN_EN1253": cert_1253,
                "Cert_DIN_18534": cert_18534,
                "Evidence_Text": f"Stabilně vytaženo přes BS4 z {url}"
            }
        except Exception as e:
            print(f"   ⚠️ Chyba při BS4 extrakci {url}: {e}", file=sys.stderr)
            return None

    def run(self, specific_urls=None):
        print("\n" + "="*60)
        print("🏗️ KROK 2: Viega BOM Builder (Stabilní verze)")
        print("="*60 + "\n", file=sys.stderr)

        if not specific_urls:
            print("❌ Žádné URL k analýze nebyly předány.", file=sys.stderr)
            return

        all_collected = []
        for url in specific_urls:
            data = self.extract_bom_details(url)
            if data:
                all_collected.append(data)
            time.sleep(1) # Malá pauza šetřící server

        if all_collected:
            df_new = pd.DataFrame(all_collected)
            
            if os.path.exists(self.excel_path):
                try:
                    # Načtení stávajících dat
                    with pd.ExcelFile(self.excel_path) as xls:
                        if "Products_Tech" in xls.sheet_names:
                            df_tech = pd.read_excel(xls, "Products_Tech")
                        else:
                            df_tech = pd.DataFrame(columns=self.cols_tech)
                    
                    # Sjednocení a promazání duplicit podle SKU
                    df_combined = pd.concat([df_tech, df_new], ignore_index=True)
                    df_combined.drop_duplicates(subset=['Article_Number_SKU'], keep='last', inplace=True)
                except Exception as e:
                    print(f"⚠️ Problém s Excel listem: {e}", file=sys.stderr)
                    df_combined = df_new
            else:
                df_combined = df_new

            # Zápis do Excelu
            try:
                with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
                print(f"✅ BOM Builder HOTOVO: Data uložena.")
            except Exception:
                df_combined.to_excel(self.excel_path, sheet_name="Products_Tech", index=False)
                print(f"✅ BOM Builder HOTOVO: Soubor vytvořen.")
        else:
            print("\n❌ Nebyla získána žádná nová data.")