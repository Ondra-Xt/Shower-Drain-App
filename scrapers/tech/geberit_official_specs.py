import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import os
import sys
import time

class GeberitOfficialSpecsBot:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def extract_color(self, text_lower):
        """Vyhledá informaci o barvě v textu stránky."""
        # Geberit katalog často používá tvary "Farbe / Oberfläche: champagner" atd.
        m_color = re.search(r'(?:farbe|oberfläche)[^\:]*:\s*(.{5,40})', text_lower)
        if m_color:
            val = m_color.group(1).split('\n')[0].strip()
            if "schwarz" in val: return "Schwarz"
            elif "champagner" in val: return "Champagner"
            elif "gebürstet" in val or "poliert" in val or "edelstahl" in val: return "Edelstahl (Gebürstet/Poliert)"
            
        if "schwarz" in text_lower: return "Schwarz"
        if "champagner" in text_lower: return "Champagner"
        if "gebürstet" in text_lower or "poliert" in text_lower: return "Edelstahl (Gebürstet/Poliert)"
        
        return ""

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Soubor {self.excel_path} nenalezen.", file=sys.stderr)
            return

        print("\n" + "="*60)
        print("🛠️ Goro: Spouštím Geberit Official Specs (Stabilní BS4)")
        print("="*60 + "\n", file=sys.stderr)

        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        except Exception as e:
            print(f"❌ Chyba při čtení Excelu: {e}", file=sys.stderr)
            return

        # Filtrace produktů k aktualizaci
        is_geberit = df_tech['Manufacturer'].astype(str).str.strip() == 'Geberit'
        has_url = df_tech['Tech_Source_URL'].astype(str).str.contains('catalog.geberit')
        
        for col in ['Length_mm', 'Color', 'Material_V4A', 'Is_Cuttable']:
            if col not in df_tech.columns: df_tech[col] = ""
            df_tech[col] = df_tech[col].astype(str).replace('nan', '').strip()

        needs_update = is_geberit & has_url & ((df_tech['Length_mm'] == "") | (df_tech['Color'] == ""))
        skus_to_process = df_tech[needs_update]['Component_SKU'].tolist()

        if not skus_to_process:
            print("✅ Všechna Geberit data jsou již kompletní.")
            return

        print(f"📌 Chybějící data u {len(skus_to_process)} položek. Stahuji...", file=sys.stderr)
        updates = 0

        for sku in skus_to_process:
            idx = df_tech.index[df_tech['Component_SKU'] == sku].tolist()[0]
            url = df_tech.at[idx, 'Tech_Source_URL']

            try:
                r = requests.get(url, headers=self.headers, timeout=20)
                if r.status_code != 200: continue
                
                soup = BeautifulSoup(r.text, 'html.parser')
                page_text_lower = soup.get_text().lower()

                # Extrakce délky
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
                            
                if sku == "154.455.00.1":
                    length = "188"
                    is_cuttable = "No"

                color = self.extract_color(page_text_lower)

                # Extrakce materiálu
                material = ""
                if "v4a" in page_text_lower or "1.4404" in page_text_lower: 
                    material = "Edelstahl V4A"
                elif any(x in page_text_lower for x in ["crni-stahl", "edelstahl", "1.4301"]): 
                    material = "Edelstahl V2A"

                # Zápis změn
                changes = []
                if length and not df_tech.at[idx, 'Length_mm']:
                    df_tech.at[idx, 'Length_mm'] = length
                    df_tech.at[idx, 'Is_Cuttable'] = is_cuttable
                    changes.append("Délka")
                if color and not df_tech.at[idx, 'Color']:
                    df_tech.at[idx, 'Color'] = color
                    changes.append("Barva")
                if material and not df_tech.at[idx, 'Material_V4A']:
                    df_tech.at[idx, 'Material_V4A'] = material
                    changes.append("Materiál")

                if changes:
                    updates += 1
                    print(f"   ✅ {sku}: Doplněno ({', '.join(changes)})", file=sys.stderr)
                
                time.sleep(0.5)

            except Exception as e:
                print(f"   ❌ Chyba u SKU {sku}: {e}", file=sys.stderr)

        if updates > 0:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ Hotovo! Aktualizováno {updates} produktů.")
        else:
            print("\n✅ Žádná nová data k uložení.")

if __name__ == "__main__":
    GeberitOfficialSpecsBot().run()