import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import sys
import os

class ViegaBOMBuilder:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        # Sjednocené hlavičky podle vašeho Excelu
        self.cols_tech = [
            "Article_Number_SKU", "Brand", "Product_URL", "Datasheet_URL", 
            "Flow_Rate_ls", "Is_V4A", "Color", "Cert_DIN_EN1253", "Cert_DIN_18534", 
            "Height_Min_mm", "Height_Max_mm", "Is_Cuttable", "Product_Name", "Evidence_Text"
        ]

    def extract_bom_details(self, page, url):
        """Vytáhne technické detaily z konkrétní produktové stránky Viega."""
        print(f"   🔍 Analyzuji detaily: {url}", file=sys.stderr)
        try:
            page.goto(url, timeout=60000)
            time.sleep(1.5)
            
            h1 = page.locator("h1").first.inner_text().strip()
            body_text = page.locator("body").inner_text()
            
            # Detekce průtoku
            flow = ""
            m_flow = re.search(r'(\d+(?:,\d+)?)\s*l/s', body_text)
            if m_flow: flow = m_flow.group(1).replace(',', '.')

            # Detekce materiálu
            is_v4a = "No"
            if any(x in body_text.lower() for x in ["v4a", "1.4404", "edelstahl 1.4404"]):
                is_v4a = "Yes"

            # Detekce certifikace
            cert_1253 = "Yes" if "1253" in body_text else "No"
            cert_18534 = "Yes" if "18534" in body_text else "No"

            # Hledání SKU přímo na stránce (pokud tam je tabulka)
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
                "Evidence_Text": f"Automaticky vytaženo z {url}"
            }
        except Exception as e:
            print(f"   ⚠️ Chyba při extrakci {url}: {e}", file=sys.stderr)
            return None

    def run(self, specific_urls=None):
        print("\n" + "="*60)
        print("🏗️ KROK 2: Viega BOM Builder (Stavba technických listů)")
        print("="*60 + "\n", file=sys.stderr)

        if not specific_urls:
            print("❌ Žádné URL k analýze nebyly předány.", file=sys.stderr)
            return

        all_collected = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for url in specific_urls:
                data = self.extract_bom_details(page, url)
                if data:
                    all_collected.append(data)
            
            browser.close()

        if all_collected:
            df_new = pd.DataFrame(all_collected)
            
            # --- MAPOVÁNÍ PRO BOM BUILDER (Pojistka pro konzistenci) ---
            rename_map = {
                "Component_SKU": "Article_Number_SKU",
                "Manufacturer": "Brand",
                "Tech_Source_URL": "Product_URL",
                "Flow_Rate_l_s": "Flow_Rate_ls",
                "Material_V4A": "Is_V4A"
            }
            df_new.rename(columns=rename_map, inplace=True)

            if os.path.exists(self.excel_path):
                # Načtení stávajícího listu
                try:
                    df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    
                    # Dynamické určení SKU sloupce
                    sku_col = 'Article_Number_SKU' if 'Article_Number_SKU' in df_tech.columns else 'Component_SKU'
                    
                    if sku_col in df_tech.columns:
                        df_tech[sku_col] = df_tech[sku_col].astype(str).str.replace('.0', '', regex=False).str.strip()
                    
                    # Spojení a odstranění duplicit
                    df_combined = pd.concat([df_tech, df_new], ignore_index=True)
                    if sku_col in df_combined.columns:
                        df_combined.drop_duplicates(subset=[sku_col], keep='last', inplace=True)
                except Exception as e:
                    print(f"⚠️ Nepodařilo se načíst stávající list: {e}. Vytvářím nový.", file=sys.stderr)
                    df_combined = df_new
            else:
                df_combined = df_new

            # Zápis do Excelu
            try:
                with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
                print(f"\n✅ BOM Builder HOTOVO: Data uložena do {self.excel_path}")
            except Exception as e:
                print(f"❌ Chyba při zápisu do Excelu: {e}", file=sys.stderr)
        else:
            print("\n❌ Nebyla získána žádná nová technická data.")

if __name__ == "__main__":
    # Testovací spuštění s jednou URL
    test_url = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
    ViegaBOMBuilder().run(test_url)