import pandas as pd
import os
import sys
from datetime import datetime

class ViegaCalculator:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        # Mapování sloupců: podporuje staré i nové názvy napříč Viega i Geberit skripty
        self.internal_map = {
            'Article_Number_SKU': 'sku',
            'Component_SKU': 'sku',
            'Brand': 'brand',
            'Manufacturer': 'brand',
            'Flow_Rate_ls': 'flow',
            'Flow_Rate_l_s': 'flow',
            'Product_Name': 'name',
            'Is_V4A': 'v4a',
            'Material_V4A': 'v4a',
            'Product_URL': 'url',
            'Tech_Source_URL': 'url'
        }

    def load_tech_data(self):
        """Načte technická data z Excelu striktně jako stringy."""
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Soubor {self.excel_path} nebyl nalezen.", file=sys.stderr)
            return pd.DataFrame()

        try:
            # KLÍČOVÁ ZMĚNA: dtype=str zabrání chybě float64
            df = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
            df = df.replace(['nan', 'None'], '')

            # Najdeme sloupec se SKU (podporuje oba názvy)
            sku_col = next((c for c in ['Article_Number_SKU', 'Component_SKU'] if c in df.columns), None)
            
            if sku_col:
                # Vyčištění SKU: odstranění .0 u čísel, která se změnila na string, a ořezání mezer
                df[sku_col] = df[sku_col].str.replace('.0', '', regex=False).str.strip()
            
            # Přejmenování na interní názvy pro zbytek logiky
            return df.rename(columns=self.internal_map)
        except Exception as e:
            print(f"❌ Chyba při načítání dat pro kalkulátor: {e}", file=sys.stderr)
            return pd.DataFrame()

    def calculate_drainage_capacity(self, selected_skus):
        """Vypočítá celkovou kapacitu odtoku pro vybrané položky."""
        df = self.load_tech_data()
        if df.empty or 'sku' not in df.columns:
            return 0.0, []

        results = []
        total_flow = 0.0

        for sku in selected_skus:
            target_sku = str(sku).strip()
            match = df[df['sku'] == target_sku]
            
            if not match.empty:
                row = match.iloc[0]
                flow_val = row.get('flow', '0')
                
                try:
                    # Ošetření formátů (čárka vs tečka) a převod na float pro výpočet
                    clean_flow = str(flow_val).replace(',', '.').strip()
                    flow_num = float(clean_flow) if clean_flow else 0.0
                except:
                    flow_num = 0.0
                
                total_flow += flow_num
                results.append({
                    "sku": target_sku,
                    "name": row.get('name', 'Neznámý produkt'),
                    "brand": row.get('brand', 'Viega'),
                    "flow": flow_num,
                    "v4a": row.get('v4a', 'No'),
                    "url": row.get('url', '')
                })
        
        return round(total_flow, 2), results

    def generate_bom_from_selection(self, selected_skus):
        """Vytvoří DataFrame s přehledem materiálu pro export."""
        _, details = self.calculate_drainage_capacity(selected_skus)
        if not details:
            return pd.DataFrame()
            
        df_bom = pd.DataFrame(details)
        export_map = {
            "sku": "Objednací číslo",
            "name": "Název produktu",
            "brand": "Výrobce",
            "flow": "Průtok (l/s)",
            "v4a": "Materiál V4A",
            "url": "Odkaz na produkt"
        }
        return df_bom.rename(columns=export_map)

    def save_calculation(self, selected_skus, project_name="Projekt"):
        """Uloží výsledek kalkulace do nového listu v Excelu."""
        df_bom = self.generate_bom_from_selection(selected_skus)
        if df_bom.empty:
            return False

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            sheet_name = f"BOM_{timestamp}"[:31] 
            
            # Před zápisem vše na string (pro jistotu u výsledného Excelu)
            df_bom = df_bom.astype(str)

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_bom.to_excel(writer, sheet_name=sheet_name, index=False)
            return True
        except Exception as e:
            print(f"❌ Chyba při ukládání BOMu: {e}", file=sys.stderr)
            return False

if __name__ == "__main__":
    calc = ViegaCalculator()
    test_skus = ["750694", "4981.10"] 
    total, items = calc.calculate_drainage_capacity(test_skus)
    print(f"Celková kapacita: {total} l/s")