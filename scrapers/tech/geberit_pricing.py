import pandas as pd
import datetime
import os
import re
import time
import sys
import requests
from bs4 import BeautifulSoup

class GeberitPricingV11_EdgeCase:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Soubor {self.excel_path} nenalezen.", file=sys.stderr)
            return

        print("\n" + "="*60)
        print("💰 Goro: Spouštím Geberit Pricing (Agresivní BS4)")
        print("="*60 + "\n", file=sys.stderr)

        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
            df_tech = df_tech.replace(['nan', 'None'], '')
        except Exception as e:
            print(f"❌ Chyba: {e}", file=sys.stderr)
            return

        sku_col = 'Component_SKU' if 'Component_SKU' in df_tech.columns else 'Article_Number_SKU'
        brand_col = 'Manufacturer' if 'Manufacturer' in df_tech.columns else 'Brand'

        is_geberit = df_tech[brand_col].astype(str).str.contains('Geberit', case=False, na=False)
        skus = df_tech[is_geberit][sku_col].dropna().unique()
        
        market_prices = []
        updates_made = 0

        for sku in skus:
            target_sku = str(sku).strip()
            if not target_sku: continue

            # Hledání na Megabad - odesíláme čistý kód bez teček i s tečkami
            search_url = f"https://www.megabad.com/shop-search.php?query={target_sku}"
            print(f"   ➡️ SKU {target_sku}: Hledám cenu...", file=sys.stderr)
            
            try:
                r = requests.get(search_url, headers=self.headers, timeout=20)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Zrušili jsme blokaci, pokud SKU není přesně v textu! Spoléháme na to, že search Megabadu vrací relevantní výsledek.
                
                price = None
                # Pokus 1: Speciální CSS třída
                price_el = soup.select_one('.product-detail-price, .price-gross, [itemprop="price"]')
                if price_el:
                    val = price_el.get_text(strip=True).replace('€', '').replace('*', '').strip()
                    val = re.sub(r'[^\d,.-]', '', val)
                    if ',' in val and '.' in val: val = val.replace('.', '').replace(',', '.')
                    elif ',' in val: val = val.replace(',', '.')
                    if val: price = float(val)

                # Pokus 2: Regulární výraz z celého textu (Fallback)
                if not price:
                    page_text = soup.get_text()
                    price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
                    if price_match:
                        price = float(price_match.group(1).replace('.', '').replace(',', '.'))

                if price:
                    market_prices.append({
                        "Component_SKU": target_sku, 
                        "Eshop_Source": "Megabad",
                        "Found_Price_EUR": price,
                        "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    print(f"      ✅ Cena: {price} €", file=sys.stderr)
                    updates_made += 1
                else:
                    print(f"      ⚠️ Cena nenalezena na stránce.", file=sys.stderr)

                time.sleep(0.5)

            except Exception as e:
                print(f"      ❌ Chyba u {target_sku}: {e}", file=sys.stderr)

        if updates_made > 0 or market_prices:
            df_tech = df_tech.astype(str).replace(['nan', 'None'], '')
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                try:
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
                    df_old_prices = df_old_prices.replace(['nan', 'None'], '')
                    df_new_prices = pd.DataFrame(market_prices).astype(str)
                    df_old_prices = df_old_prices[~((df_old_prices['Component_SKU'].isin(skus)) & (df_old_prices['Eshop_Source'] == 'Megabad'))]
                    df_final_prices = pd.concat([df_old_prices, df_new_prices], ignore_index=True)
                    df_final_prices.to_excel(writer, sheet_name="Market_Prices", index=False)
                except Exception:
                    pd.DataFrame(market_prices).astype(str).to_excel(writer, sheet_name="Market_Prices", index=False)
            print(f"\n✅ Pricing hotovo! Uloženo {updates_made} cen Geberit.")
        else:
            print("\n⚠️ Žádné nové ceny nebyly nalezeny.")

if __name__ == "__main__":
    GeberitPricingV11_EdgeCase().run()