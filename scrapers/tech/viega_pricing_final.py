import pandas as pd
import datetime
import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup

class ViegaPricingBotProtected:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def get_color_and_material(self, text, h1):
        text_l, h1_l = text.lower(), h1.lower()
        color, material = "", ""
        if "v4a" in text_l or "1.4404" in text_l: material = "Edelstahl V4A"
        elif "kunststoff" in text_l: material = "Kunststoff"
        
        if "schwarz" in h1_l or "schwarz" in text_l: color = "Schwarz"
        elif "champagner" in h1_l or "champagner" in text_l: color = "Champagner"
        elif "vergoldet" in h1_l or "gold" in text_l: color = "Gold"
        elif "kupfer" in h1_l or "kupfer" in text_l: color = "Kupfer"
        elif "matt" in h1_l or "gebürstet" in h1_l: color = "Edelstahl (Matt)"
        elif "glänzend" in h1_l or "poliert" in h1_l: color = "Edelstahl (Glänzend)"
        return color, material

    def is_empty(self, val):
        v = str(val).strip().lower()
        return v in ['nan', 'none', '', '--', 'nat']

    def run(self):
        if not os.path.exists(self.excel_path): 
            print("❌ Excel nenalezen!", file=sys.stderr)
            return

        print("\n" + "="*60)
        print("🚀 Viega Pricing Bot (STABILNÍ BS4 + PŘÍSNÉ SKU)")
        print("="*60 + "\n", file=sys.stderr)

        # Načtení dat striktně jako string (vakcína proti float64)
        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
        df_tech = df_tech.replace(['nan', 'None'], '')
        
        # Sjednocení názvů sloupců (podpora obou verzí)
        sku_col = 'Component_SKU' if 'Component_SKU' in df_tech.columns else 'Article_Number_SKU'
        brand_col = 'Manufacturer' if 'Manufacturer' in df_tech.columns else 'Brand'

        is_viega = df_tech[brand_col].astype(str).str.contains('Viega', case=False, na=False)
        skus_to_search = df_tech[is_viega][sku_col].dropna().unique()
        
        market_prices = []
        prices_found = 0

        for target_sku in skus_to_search:
            target_sku = str(target_sku).strip()
            print(f"   ➡️ SKU {target_sku}: Hledám...", file=sys.stderr)
            
            search_url = f"https://www.megabad.com/shop-search.php?query=Viega+{target_sku}"
            try:
                r = requests.get(search_url, headers=self.headers, timeout=20)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                page_text = soup.get_text()
                h1_text = soup.find('h1').text.strip() if soup.find('h1') else "Neznámý produkt"

                # --- PŘÍSNÁ KONTROLA SKU ---
                clean_sku = target_sku.replace(" ", "")
                clean_page_text = page_text.replace(" ", "").lower()
                
                if clean_sku not in clean_page_text:
                    print(f"      ⚠️ Přeskakuji: Falešný výsledek.", file=sys.stderr)
                    continue

                # --- EXTRAKCE CENY ---
                price, uvp = None, None
                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
                if price_match:
                    price = float(price_match.group(1).replace('.', '').replace(',', '.'))
                
                uvp_match = re.search(r'UVP:\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
                if uvp_match:
                    uvp = float(uvp_match.group(1).replace('.', '').replace(',', '.'))

                if price:
                    market_prices.append({
                        "Component_SKU": target_sku, "Eshop_Source": "Megabad",
                        "Found_Price_EUR": price, "Original_Price_EUR": uvp,
                        "Product_URL": search_url, "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    prices_found += 1
                    
                    # Doplňková technická data (pokud chybí)
                    color, material = self.get_color_and_material(page_text, h1_text)
                    row_idx = df_tech.index[df_tech[sku_col] == target_sku].tolist()[0]
                    
                    if material and self.is_empty(df_tech.at[row_idx, 'Material_V4A' if 'Material_V4A' in df_tech.columns else 'Is_V4A']):
                        col_m = 'Material_V4A' if 'Material_V4A' in df_tech.columns else 'Is_V4A'
                        df_tech.at[row_idx, col_m] = material
                    if color and self.is_empty(df_tech.at[row_idx, 'Color']):
                        df_tech.at[row_idx, 'Color'] = color

                    print(f"      ✅ Nalezeno: {price} €", file=sys.stderr)

            except Exception as e:
                print(f"      ❌ Chyba u {target_sku}: {e}", file=sys.stderr)
            
            time.sleep(0.5)

        # --- ZÁPIS ---
        # Před zápisem vše na string (kompletní imunizace proti float64)
        df_tech = df_tech.astype(str).replace(['nan', 'None'], '')

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            if market_prices:
                df_new_p = pd.DataFrame(market_prices).astype(str)
                try:
                    df_old_p = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
                    df_res_p = pd.concat([df_old_p, df_new_p], ignore_index=True).drop_duplicates(subset=['Component_SKU', 'Eshop_Source'], keep='last')
                    df_res_p.to_excel(writer, sheet_name="Market_Prices", index=False)
                except:
                    df_new_p.to_excel(writer, sheet_name="Market_Prices", index=False)

        print(f"\n✅ Hotovo! Nalezeno {prices_found} cen.")

if __name__ == "__main__":
    ViegaPricingBotProtected().run()