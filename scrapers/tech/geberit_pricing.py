import pandas as pd
from playwright.sync_api import sync_playwright
import datetime
import os
import re
import time
import sys

class GeberitPricingV11_EdgeCase:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def run(self):
        if not os.path.exists(self.excel_path): return

        print("\n" + "="*60)
        print("💰 Goro: Spouštím Geberit Pricing (PLAYWRIGHT)")
        print("="*60 + "\n", file=sys.stderr)

        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str).replace(['nan', 'None'], '')
        except Exception: return

        skus = df_tech[df_tech['Manufacturer'].astype(str).str.contains('Geberit')]['Component_SKU'].dropna().unique()
        market_prices = []
        updates_made = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for sku in skus:
                target_sku = str(sku).strip()
                search_url = f"https://www.megabad.com/shop-search.php?query={target_sku}"
                print(f"   ➡️ SKU {target_sku}: Hledám cenu...", file=sys.stderr)
                
                try:
                    page.goto(search_url, timeout=40000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1.5)
                    
                    page_text = page.locator("body").inner_text()
                    
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
                    else:
                        print(f"      ⚠️ Cena nenalezena.", file=sys.stderr)
                except Exception as e:
                    print(f"      ❌ Chyba u {target_sku}: {e}", file=sys.stderr)
            
            browser.close()

        if updates_made > 0 or market_prices:
            df_tech = df_tech.astype(str).replace(['nan', 'None'], '')
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                try:
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str).replace(['nan', 'None'], '')
                    df_new_prices = pd.DataFrame(market_prices).astype(str)
                    df_old_prices = df_old_prices[~((df_old_prices['Component_SKU'].isin(skus)) & (df_old_prices['Eshop_Source'] == 'Megabad'))]
                    pd.concat([df_old_prices, df_new_prices], ignore_index=True).to_excel(writer, sheet_name="Market_Prices", index=False)
                except Exception:
                    pd.DataFrame(market_prices).astype(str).to_excel(writer, sheet_name="Market_Prices", index=False)
            
            print(f"\n✅ Pricing hotovo! Aktualizováno {updates_made} položek.")

if __name__ == "__main__":
    GeberitPricingV11_EdgeCase().run()