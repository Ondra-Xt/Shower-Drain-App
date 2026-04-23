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
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        self.overrides = {
            "154.455.00.1": {"Length_mm": "188", "Is_Cuttable": "No", "Color": "Edelstahl (Gebürstet/Poliert)"}
        }

    def extract_data_from_pdf(self, pdf_url):
        """Stáhne a prohledá PDF bez potřeby prohlížeče."""
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
        if not os.path.exists(self.excel_path): return

        print("\n" + "="*60)
        print("💰 Goro: Spouštím Geberit Pricing (Stabilní BS4)")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        skus = df_tech[df_tech['Manufacturer'] == 'Geberit']['Component_SKU'].dropna().unique()
        
        market_prices = []
        updates_made = 0

        for sku in skus:
            # Megabad vyhledávání přes URL (mnohem stabilnější než klikání)
            search_url = f"https://www.megabad.com/shop-search.php?query={sku}"
            print(f"   ➡️ SKU {sku}: Hledám cenu...", file=sys.stderr)
            
            try:
                r = requests.get(search_url, headers=self.headers, timeout=20)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                page_text = soup.get_text().lower()

                # Hledání ceny v HTML
                # Megabad často používá meta tagy nebo specifické třídy pro cenu
                price = ""
                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', soup.get_text())
                if price_match:
                    price = price_match.group(1).replace('.', '').replace(',', '.')

                if price:
                    market_prices.append({
                        "Component_SKU": sku, "Eshop_Source": "Megabad",
                        "Found_Price_EUR": float(price),
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    print(f"      ✅ Cena nalezena: {price} €", file=sys.stderr)
                    updates_made += 1

                # Pokud chybí PDF datasheet v Excelu, zkusíme ho najít
                idx = df_tech.index[df_tech['Component_SKU'] == sku].tolist()[0]
                if not str(df_tech.at[idx, 'Datasheet_URL']).startswith('http'):
                    pdf_tag = soup.find('a', href=re.compile(r'\.pdf'))
                    if pdf_tag:
                        pdf_url = pdf_tag['href']
                        if not pdf_url.startswith('http'): pdf_url = "https://www.megabad.com" + pdf_url
                        df_tech.at[idx, 'Datasheet_URL'] = pdf_url

                time.sleep(1) # Prevence blokování

            except Exception as e:
                print(f"      ❌ Chyba u {sku}: {e}", file=sys.stderr)

        # Zápis výsledků
        if updates_made > 0:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                
                # Aktualizace cen
                try:
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    df_new_prices = pd.DataFrame(market_prices)
                    # Odstraníme staré ceny z Megabadu pro tato SKU
                    df_old_prices = df_old_prices[~((df_old_prices['Component_SKU'].isin(skus)) & (df_old_prices['Eshop_Source'] == 'Megabad'))]
                    pd.concat([df_old_prices, df_new_prices], ignore_index=True).to_excel(writer, sheet_name="Market_Prices", index=False)
                except:
                    pd.DataFrame(market_prices).to_excel(writer, sheet_name="Market_Prices", index=False)
            
            print(f"\n✅ Hotovo! Aktualizováno {updates_made} cen.")