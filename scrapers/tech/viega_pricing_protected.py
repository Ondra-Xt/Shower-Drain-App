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

    def get_price_from_megabad(self, sku):
        """Získá cenu z Megabadu pomocí přímého vyhledávání (rychlá BS4 verze)."""
        search_url = f"https://www.megabad.com/shop-search.php?query=Viega+{sku}"
        try:
            r = requests.get(search_url, headers=self.headers, timeout=20)
            if r.status_code != 200:
                return None, None, None
            
            soup = BeautifulSoup(r.text, 'html.parser')
            page_text = soup.get_text()
            
            # Kontrola, zda je SKU opravdu na stránce (ochrana proti falešným výsledkům)
            if sku.replace(" ", "") not in page_text.replace(" ", ""):
                return None, None, None

            # Extrakce ceny pomocí regulárního výrazu (hledá formát 123,45 €)
            price = None
            uvp = None
            
            # Hledáme hlavní cenu
            price_match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
            if price_match:
                price = float(price_match.group(1).replace('.', '').replace(',', '.'))
            
            # Hledáme UVP (původní cenu), pokud existuje
            uvp_match = re.search(r'UVP:\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*€', page_text)
            if uvp_match:
                uvp = float(uvp_match.group(1).replace('.', '').replace(',', '.'))
                
            return price, uvp, search_url
        except Exception as e:
            print(f"      ❌ Chyba při spojení pro SKU {sku}: {e}", file=sys.stderr)
            return None, None, None

    def run(self):
        if not os.path.exists(self.excel_path):
            print("❌ Excel nenalezen!", file=sys.stderr)
            return

        print("\n" + "="*60)
        print("🚀 Viega Pricing Bot (Stabilní BS4 Cloud Verze)")
        print("="*60 + "\n", file=sys.stderr)

        # Načtení dat striktně jako stringy (prevence float64 chyby)
        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
        df_tech = df_tech.replace(['nan', 'None'], '')

        # Filtrace Viega produktů
        mask = df_tech['Brand'].astype(str).str.contains('Viega', case=False, na=False)
        skus_to_search = df_tech[mask]['Article_Number_SKU'].unique()

        market_prices = []
        prices_found = 0

        for target_sku in skus_to_search:
            if not target_sku or target_sku == '': continue
            
            print(f"   ➡️ SKU {target_sku}: Hledám cenu...", file=sys.stderr)
            price, uvp, url = self.get_price_from_megabad(target_sku)

            if price:
                market_prices.append({
                    "Component_SKU": str(target_sku),
                    "Eshop_Source": "Megabad",
                    "Found_Price_EUR": price,
                    "Original_Price_EUR": uvp,
                    "Product_URL": url,
                    "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                prices_found += 1
                print(f"      ✅ Cena: {price} €", file=sys.stderr)
            else:
                print(f"      ⚠️ Cena nenalezena.", file=sys.stderr)
            
            time.sleep(0.5) # Respekt k serveru

        # Uložení výsledků
        if market_prices:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                # Zápis cenového listu
                try:
                    # Pokus o načtení starých cen (opět striktně stringy)
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
                    df_new_prices = pd.DataFrame(market_prices).astype(str)
                    
                    # Sjednocení a odstranění duplicit
                    df_combined = pd.concat([df_old_prices, df_new_prices], ignore_index=True)
                    df_combined.drop_duplicates(subset=['Component_SKU', 'Eshop_Source'], keep='last', inplace=True)
                    df_combined.to_excel(writer, sheet_name="Market_Prices", index=False)
                except:
                    # Pokud list neexistuje, vytvoříme ho
                    pd.DataFrame(market_prices).astype(str).to_excel(writer, sheet_name="Market_Prices", index=False)
            
            print(f"\n✅ Hotovo! Nalezeno {prices_found} cen.")

if __name__ == "__main__":
    ViegaPricingBotProtected().run()