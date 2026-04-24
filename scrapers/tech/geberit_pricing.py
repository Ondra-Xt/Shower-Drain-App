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

    def extract_tech_details(self, text_lower):
        """Pomocná funkcia na vytiahnutie materiálu a farby z textu Megabadu."""
        color, material = "", ""
        if "v4a" in text_lower or "1.4404" in text_lower: material = "Edelstahl V4A"
        elif "edelstahl" in text_lower or "1.4301" in text_lower: material = "Edelstahl V2A"
        
        if "schwarz" in text_lower: color = "Schwarz"
        elif "champagner" in text_lower: color = "Champagner"
        elif "gold" in text_lower: color = "Gold"
        elif "matt" in text_lower: color = "Edelstahl (Matt)"
        return color, material

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"❌ Súbor {self.excel_path} neexistuje.")
            return

        print("\n" + "="*60)
        print("💰 Goro Master Bot: Geberit Pricing + Tech (Agresívny Playwright)")
        print("="*60 + "\n", file=sys.stderr)

        # 1. Načítanie dát s vakcínou proti float64
        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str).replace(['nan', 'None'], '')
        except Exception as e:
            print(f"❌ Chyba načítania: {e}")
            return

        # Určenie SKU stĺpca (univerzálne pre Geberit aj Viega riadky)
        sku_col = 'Component_SKU' if 'Component_SKU' in df_tech.columns else 'Article_Number_SKU'
        brand_col = 'Manufacturer' if 'Manufacturer' in df_tech.columns else 'Brand'

        # Vyberieme len Geberit položky
        mask_geberit = df_tech[brand_col].astype(str).str.contains('Geberit', case=False, na=False)
        skus_to_search = df_tech[mask_geberit][sku_col].unique()

        market_prices = []
        updates_count = 0

        with sync_playwright() as p:
            # Neviditeľný Chrome
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()

            for target_sku in skus_to_search:
                target_sku = str(target_sku).strip()
                if not target_sku or target_sku == "": continue

                print(f"   ➡️ SKU {target_sku}: Hľadám cenu a tech detaily...", file=sys.stderr)
                search_url = f"https://www.megabad.com/shop-search.php?query={target_sku}"
                
                try:
                    page.goto(search_url, timeout=45000)
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    
                    page_text = page.locator("body").inner_text()
                    page_text_l = page_text.lower()
                    
                    # --- EXTRAKCIA CENY ---
                    price = None
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
                        
                        # --- EXTRAKCIA TECH DETAILOV (ak v tabuľke chýbajú) ---
                        color, mat = self.extract_tech_details(page_text_l)
                        row_idx = df_tech.index[df_tech[sku_col] == target_sku].tolist()[0]
                        
                        # Zápis do stĺpcov (podpora pre rôzne názvy)
                        m_col = 'Material_V4A' if 'Material_V4A' in df_tech.columns else 'Is_V4A'
                        if mat and (not df_tech.at[row_idx, m_col]):
                            df_tech.at[row_idx, m_col] = mat
                        if color and (not df_tech.at[row_idx, 'Color']):
                            df_tech.at[row_idx, 'Color'] = color
                            
                        updates_count += 1
                    else:
                        print(f"      ⚠️ Cena nenájdená.", file=sys.stderr)

                except Exception as e:
                    print(f"      ❌ Chyba: {e}", file=sys.stderr)
            
            browser.close()

        # 3. Uloženie s totálnou konverziou na stringy
        if updates_count > 0 or market_prices:
            df_tech = df_tech.astype(str).replace(['nan', 'None'], '')
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                
                # Uloženie cien (Market_Prices)
                try:
                    df_old_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
                    df_new_prices = pd.DataFrame(market_prices).astype(str)
                    # Odstránenie starých Megabad cien pre tieto SKU
                    df_old_prices = df_old_prices[~((df_old_prices['Component_SKU'].isin(skus_to_search)) & (df_old_prices['Eshop_Source'] == 'Megabad'))]
                    pd.concat([df_old_prices, df_new_prices], ignore_index=True).to_excel(writer, sheet_name="Market_Prices", index=False)
                except:
                    pd.DataFrame(market_prices).astype(str).to_excel(writer, sheet_name="Market_Prices", index=False)
            
            print(f"\n✅ Master Bot hotový! Aktualizovaných {updates_count} položiek.")

if __name__ == "__main__":
    GeberitPricingV11_EdgeCase().run()