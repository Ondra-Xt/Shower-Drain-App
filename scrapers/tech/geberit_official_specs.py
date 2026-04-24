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
        m_color = re.search(r'(?:farbe|oberfläche)[^\:]*:\s*(.{5,40})', text_lower)
        if m_color:
            val = m_color.group(1).split('\n')[0].strip()
            if "schwarz" in val: return "Schwarz"
            if "champagner" in val: return "Champagner"
            if "gebürstet" in val or "poliert" in val or "edelstahl" in val: return "Edelstahl (Gebürstet/Poliert)"
        if "schwarz" in text_lower: return "Schwarz"
        if "champagner" in text_lower: return "Champagner"
        if "gebürstet" in text_lower or "poliert" in text_lower: return "Edelstahl (Gebürstet/Poliert)"
        return ""

    def run(self):
        if not os.path.exists(self.excel_path): return
        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str).replace(['nan', 'None'], '')
        except: return

        print("\n" + "="*60)
        print("🛠️ Goro: Spouštím Geberit Specs (PLAYWRIGHT)")
        print("="*60 + "\n", file=sys.stderr)

        for col in ['Length_mm', 'Color', 'Material_V4A', 'Is_Cuttable']:
            if col not in df_tech.columns: df_tech[col] = ""

        is_geberit = df_tech['Manufacturer'].astype(str).str.contains('Geberit', case=False)
        needs_update = is_geberit & ((df_tech['Length_mm'] == "") | (df_tech['Color'] == ""))
        skus_to_process = df_tech[needs_update]['Component_SKU'].tolist()

        if not skus_to_process:
            print("✅ Geberit detaily jsou kompletní.")
            return

        updates = 0
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for sku in skus_to_process:
                idx = df_tech.index[df_tech['Component_SKU'] == sku].tolist()[0]
                url = df_tech.at[idx, 'Tech_Source_URL']
                if not url or url == "": continue

                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1)
                    
                    page_text_lower = page.locator("body").inner_text().lower()

                    length = ""
                    is_cuttable = "No"
                    m_len = re.search(r'(?:l\s*=|länge|l)[\s:]*(\d{2,3})\s*cm', page_text_lower)
                    if m_len:
                        val = int(m_len.group(1))
                        if val in [90, 130, 160]:
                            length = f"300 - {val * 10}"
                            is_cuttable = "Yes"
                        else: length = str(val * 10)
                                
                    if sku == "154.455.00.1":
                        length = "188"
                        is_cuttable = "No"

                    color = self.extract_color(page_text_lower)
                    material = ""
                    if "v4a" in page_text_lower or "1.4404" in page_text_lower: material = "Edelstahl V4A"
                    elif any(x in page_text_lower for x in ["crni-stahl", "edelstahl", "1.4301"]): material = "Edelstahl V2A"

                    changed = False
                    if length:
                        df_tech.at[idx, 'Length_mm'] = str(length)
                        df_tech.at[idx, 'Is_Cuttable'] = str(is_cuttable)
                        changed = True
                    if color:
                        df_tech.at[idx, 'Color'] = str(color)
                        changed = True
                    if material:
                        df_tech.at[idx, 'Material_V4A'] = str(material)
                        changed = True

                    if changed:
                        updates += 1
                        print(f"   ✅ {sku}: Detaily načteny", file=sys.stderr)

                except Exception as e: pass
            browser.close()

        if updates > 0:
            df_tech = df_tech.astype(str).replace(['nan', 'None'], '')
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ Hotovo! Doplněno {updates} produktů.")
        else:
            print("\n✅ Žádná nová data k uložení.")

if __name__ == "__main__":
    GeberitOfficialSpecsBot().run()