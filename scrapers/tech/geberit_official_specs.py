import pandas as pd
from playwright.sync_api import sync_playwright
import re
import os
import sys
import time

class GeberitOfficialSpecsBot:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def extract_color(self, text_lower):
        # Geberit katalog často používá tvary "Farbe / Oberfläche: champagner" atd.
        m_color = re.search(r'(?:farbe|oberfläche)[^\:]*:\s*(.{5,40})', text_lower)
        if m_color:
            val = m_color.group(1).split('\n')[0].strip() # Vezmeme jen první řádek po dvojtečce
            if "schwarz" in val: return "Schwarz"
            elif "champagner" in val: return "Champagner"
            elif "gebürstet" in val or "poliert" in val or "edelstahl" in val: return "Edelstahl (Gebürstet/Poliert)"
            
        # Záchytná síť, pokud by to v tabulce nenašel, hledáme klíčová slova v celém textu
        if "schwarz" in text_lower: return "Schwarz"
        if "champagner" in text_lower: return "Champagner"
        if "gebürstet" in text_lower or "poliert" in text_lower: return "Edelstahl (Gebürstet/Poliert)"
        
        return ""

    def run(self):
        if not os.path.exists(self.excel_path): return

        print("\n" + "="*60)
        print("🛠️ Spouštím Krok 1.5: Geberit Official Specs Extractor")
        print("="*60 + "\n", file=sys.stderr)

        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        
        # Filtrujeme Geberit produkty, které MAJÍ oficiální link, ale CHYBÍ jim délka nebo barva
        is_geberit = df_tech['Manufacturer'].astype(str).str.strip() == 'Geberit'
        has_geberit_url = df_tech['Tech_Source_URL'].astype(str).str.contains('catalog.geberit')
        
        # Pojistíme si sloupce
        for col in ['Length_mm', 'Color', 'Material_V4A', 'Is_Cuttable']:
            if col not in df_tech.columns: df_tech[col] = ""
            df_tech[col] = df_tech[col].astype(str).replace('nan', '')

        needs_update = is_geberit & has_geberit_url & ((df_tech['Length_mm'] == "") | (df_tech['Color'] == ""))
        skus_to_process = df_tech[needs_update]['Component_SKU'].tolist()

        if not skus_to_process:
            print("✅ Všechny Geberit rošty už mají délku i barvu, není co doplňovat.")
            return

        print(f"📌 Nalezeno {len(skus_to_process)} roštů bez dat. Jdu je stáhnout z Geberit.de...\n", file=sys.stderr)
        updates = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for sku in skus_to_process:
                # Najdeme řádek a URL
                idx = df_tech.index[df_tech['Component_SKU'] == sku].tolist()[0]
                url = df_tech.at[idx, 'Tech_Source_URL']

                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1.5) # Necháme chvíli načíst Geberit tabulky

                    page_text = page.locator("body").inner_text()
                    page_text_lower = page_text.lower()

                    # Zkusíme najít délku (L / Länge)
                    length = ""
                    is_cuttable = "No"
                    m_len = re.search(r'(?:l\s*=|länge|l)[\s:]*(\d{2,3})\s*cm', page_text_lower)
                    if m_len:
                        val = int(m_len.group(1))
                        if val in [90, 130, 160]:
                            length = f"300 - {val * 10}"
                            is_cuttable = "Yes"
                        else:
                            length = str(val * 10)
                            
                    # Pokud je to zrovna ten krátký 154.455.00.1, přepíšeme ho natvrdo
                    if sku == "154.455.00.1":
                        length = "188"
                        is_cuttable = "No"

                    # Zkusíme najít barvu
                    color = self.extract_color(page_text_lower)

                    # Zkusíme najít materiál
                    material = ""
                    if "v4a" in page_text_lower or "1.4404" in page_text_lower: material = "Edelstahl V4A"
                    elif "crni-stahl" in page_text_lower or "edelstahl" in page_text_lower or "1.4301" in page_text_lower: material = "Edelstahl V2A"

                    info = []
                    if length and not df_tech.at[idx, 'Length_mm']:
                        df_tech.at[idx, 'Length_mm'] = length
                        df_tech.at[idx, 'Is_Cuttable'] = is_cuttable
                        info.append(f"Délka: {length} mm")
                    if color and not df_tech.at[idx, 'Color']:
                        df_tech.at[idx, 'Color'] = color
                        info.append(f"Barva: {color}")
                    if material and not df_tech.at[idx, 'Material_V4A']:
                        df_tech.at[idx, 'Material_V4A'] = material
                        info.append(f"Mat: {material}")

                    if info:
                        updates += 1
                        print(f"   ✅ {sku}: Dočteno z Geberitu -> {', '.join(info)}", file=sys.stderr)
                    else:
                        print(f"   ⚠️ {sku}: Stránka prohledána, ale nenašel jsem nová data.", file=sys.stderr)

                except Exception as e:
                    print(f"   ❌ Chyba u {sku}: {e}", file=sys.stderr)

            browser.close()

        if updates > 0:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ Hotovo! Doplněno {updates} profilů přímo od výrobce.")
        else:
            print("\n✅ Skript doběhl, ale žádná nová data k doplnění se nenašla.")

if __name__ == "__main__":
    GeberitOfficialSpecsBot().run()