import pandas as pd
import datetime
import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup
import io
import PyPDF2

class GeberitPricingV11_EdgeCase:
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

    def extract_data_from_pdf(self, pdf_url):
        """Stažení a analýza PDF bez prohlížeče."""
        data = {}
        try:
            response = requests.get(pdf_url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                with io.BytesIO(response.content) as open_pdf_file:
                    reader = PyPDF2.PdfReader(open_pdf_file)
                    pdf_text = " ".join([p.extract_text() for p in reader.pages if p.extract_text()]).lower()
                    
                    if "v4a" in pdf_text or "1.4404" in pdf_text: data['material'] = "Edelstahl V4A"
                    elif "edelstahl" in pdf_text: data['material'] = "Edelstahl V2A"
                    
                    m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', pdf_text)
                    if m_flow: data['flow_rate'] = f"{m_flow.group(1).replace(',', '.')} l/s"
        except: pass
        return data

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Soubor {self.excel_path} nenalezen.", file=sys.stderr)
            return

        print("\n" + "="*60)
        print("💰 Goro: Spouštím Geberit Pricing (Definitivní Fix Typů)")
        print("="*60 + "\n", file=sys.stderr)

        # 1. NAČTENÍ A FIXACE TYPŮ (Zabiják float64 chyby)
        try:
            # KLÍČ: dtype=str vynutí načtení všech prázdných i plných buněk jako text
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
            df_tech = df_tech.replace(['nan', 'None'], '')
        except Exception as e:
            print(f"❌ Chyba při čtení Products_Tech: {e}", file=sys.stderr)
            return

        # Podpora pro oba názvy sloupců (Viega/Geberit zvyklosti)
        sku_col = 'Component_SKU' if 'Component_SKU' in df_tech.columns else 'Article_Number_SKU'
        brand_col = 'Manufacturer' if 'Manufacturer' in df_tech.columns else 'Brand'

        is_geberit = df_tech[brand_col].astype(str).str.contains('Geberit', case=False, na=False)
        skus = df_tech[is_geberit][sku_col].dropna().unique()
        
        market_prices = []
        updates_made = 0

        # 2. VYHLEDÁVÁNÍ CEN
        for sku in skus:
            target_sku = str(sku).strip()
            if not target_sku: continue

            search_url = f"https://www.megabad.com/shop-search.php?query={target_sku}"
            print(f"   ➡️ SKU {target_sku}: Hledám cenu...", file=sys.stderr)
            
            try:
                r = requests.get(search_url, headers=self.headers, timeout=20)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                page_text = soup.get_text()

                # Extrakce ceny (hledáme formát 123,45 €)
                price = ""
                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
                if price_match:
                    price = price_match.group(1).replace('.', '').replace(',', '.')

                if price:
                    market_prices.append({
                        "Component_SKU": target_sku, 
                        "Eshop_Source": "Megabad",
                        "Found_Price_EUR": float(price),
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    print(f"      ✅ Cena: {price} €", file=sys.stderr)
                    updates_made += 1

                # Pokus o PDF Datasheet
                idx_list = df_tech.index[df_tech[sku_col] == target_sku].tolist()
                if idx_list:
                    idx = idx_list[0]
                    # Zjistíme správný název sloupce pro datasheet
                    ds_col = 'Datasheet_URL' if 'Datasheet_URL' in df_tech.columns else 'Product_URL'
                    if ds_col in df_tech.columns and not str(df_tech.at[idx, ds_col]).startswith('http'):
                        pdf_tag = soup.find('a', href=re.compile(r'\.pdf'))
                        if pdf_tag:
                            pdf_url = pdf_tag['href']
                            if not pdf_url.startswith('http'): pdf_url = "https://www.megabad.com" + pdf_url
                            df_tech.at[idx, ds_col] = str(pdf_url)

                time.sleep(0.3)

            except Exception as e:
                print(f"      ❌ Chyba u {target_sku}: {e}", file=sys.stderr)

        # 3. ZÁPIS DO EXCELU S EXTRÉMNÍ OPATRNOSTÍ NA TYPY
        if updates_made > 0 or market_prices:
            # Znovu vynutíme string u všeho v tech listu před uložením
            df_tech = df_tech.astype(str).replace(['nan', 'None'], '')

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                # Uložení tech listu
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                
                # Uložení cen
                try:
                    # I staré ceny načítáme jako string, aby se nerozbila SKU
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
                    df_old_prices = df_old_prices.replace(['nan', 'None'], '')
                    
                    df_new_prices = pd.DataFrame(market_prices).astype(str)
                    
                    # Odstranění starých duplicit
                    df_old_prices = df_old_prices[~((df_old_prices['Component_SKU'].isin(skus)) & (df_old_prices['Eshop_Source'] == 'Megabad'))]
                    
                    df_final_prices = pd.concat([df_old_prices, df_new_prices], ignore_index=True)
                    df_final_prices.to_excel(writer, sheet_name="Market_Prices", index=False)
                except Exception:
                    # Pokud list neexistuje, vytvoříme ho
                    pd.DataFrame(market_prices).astype(str).to_excel(writer, sheet_name="Market_Prices", index=False)
            
            print(f"\n✅ Pricing hotovo! Aktualizováno {updates_made} položek.")
        else:
            print("\n⚠️ Žádné nové ceny nebyly nalezeny.")

if __name__ == "__main__":
    GeberitPricingV11_EdgeCase().run()