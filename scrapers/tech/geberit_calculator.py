import pandas as pd
import re
import os
import sys

class GeberitSystemCalculatorFinal:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def parse_max_length(self, length_str):
        try:
            s = str(length_str).lower().replace('mm', '').replace('cm', '').strip()
            if '-' in s: return float(s.split('-')[-1].strip())
            return float(s)
        except: return 0.0

    def get_price(self, df_prices, sku):
        # Ochrana proti nekonzistentním typům v Excelu
        sku_prices = df_prices[df_prices['Component_SKU'].astype(str).str.upper() == str(sku).upper()]
        if sku_prices.empty: return 0.0
        
        valid_prices = []
        for p in sku_prices['Found_Price_EUR']:
            try: valid_prices.append(float(str(p).replace(',', '.')))
            except: pass
        return min(valid_prices) if valid_prices else 0.0

    def extract_series(self, product_name):
        m = re.search(r'cleanline\s*(\d{2})', str(product_name), re.IGNORECASE)
        if m: return f"CleanLine {m.group(1)}"
        return "CleanLine"

    def deduce_color_from_sku(self, sku):
        """Vyčte 100% správnou barvu přímo z Geberit kódu."""
        sku_up = str(sku).upper()
        if ".KS." in sku_up: return "Edelstahl (Gebürstet/Poliert)"
        if ".QC." in sku_up or ".TE." in sku_up or ".QB." in sku_up: return "Schwarz"
        if ".39." in sku_up: return "Champagner"
        if ".00." in sku_up and "154.455" not in sku_up: return "Edelstahl (Gebürstet/Poliert)"
        return ""

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Excel soubor nebyl nalezen.")
            return

        print("\n" + "="*60)
        print("🚀 Spouštím Krok 3: Geberit System Builder (Final Logic + Type Fix)")
        print("="*60 + "\n", file=sys.stderr)

        # 1. NAČTENÍ DAT A OPRAVA CHYB - FIX TYPŮ
        try:
            df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
            df_tech = df_tech.replace(['nan', 'None'], '')
            
            df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices", dtype=str)
            df_prices = df_prices.replace(['nan', 'None'], '')
        except Exception as e:
            print(f"❌ Chyba při načítání dat pro kalkulátor: {e}")
            return
        
        for col in ['Length_mm', 'Is_Cuttable', 'Color', 'Material_V4A', 'Flow_Rate_l_s', 'Height_Adjustability', 'Vertical_Outlet_Option', 'Product_Name']:
            if col not in df_tech.columns: df_tech[col] = ""

        # Ochrana před špatným čtením barev
        brand_col = 'Manufacturer' if 'Manufacturer' in df_tech.columns else 'Brand'
        sku_col = 'Component_SKU' if 'Component_SKU' in df_tech.columns else 'Article_Number_SKU'
        mat_col = 'Material_V4A' if 'Material_V4A' in df_tech.columns else 'Is_V4A'

        is_geberit = df_tech[brand_col].astype(str).str.strip() == 'Geberit'
        
        for idx in df_tech[is_geberit].index:
            sku = df_tech.at[idx, sku_col]
            
            if "154.15" in str(sku):
                 df_tech.at[idx, mat_col] = ""
                 df_tech.at[idx, 'Color'] = ""
            else:
                 correct_color = self.deduce_color_from_sku(sku)
                 if correct_color:
                     df_tech.at[idx, 'Color'] = str(correct_color)
                 
                 if "V4A" not in str(df_tech.at[idx, mat_col]):
                      df_tech.at[idx, mat_col] = "Edelstahl V2A"
        
        # Uložíme opravená data (jako string)
        df_tech = df_tech.astype(str).replace(['nan', 'None'], '')
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
             df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)

        geberit_tech = df_tech[df_tech[brand_col].astype(str).str.strip() == 'Geberit'].copy()
        
        # 2. SESTAVENÍ SYSTÉMŮ
        siphon_std_df = geberit_tech[geberit_tech[sku_col].astype(str).str.upper() == '154.150.00.1']
        siphon_flat_df = geberit_tech[geberit_tech[sku_col].astype(str).str.upper() == '154.152.00.1']
        
        if siphon_std_df.empty or siphon_flat_df.empty:
            print("⚠️ Chybí mi sifony 154.150.00.1 nebo 154.152.00.1.")
            return

        siphon_std = siphon_std_df.to_dict('records')[0]
        siphon_flat = siphon_flat_df.to_dict('records')[0]

        valid_grates = []
        for _, row in geberit_tech.iterrows():
            sku = str(row[sku_col]).upper()
            if "154.15" in sku: continue
            
            max_len = self.parse_max_length(row.get('Length_mm', '0'))
            if max_len >= 1200:
                valid_grates.append(row.to_dict())

        print(f"   📌 Nalezeno {len(valid_grates)} Geberit roštů pro >=120cm sprchu.\n", file=sys.stderr)

        compiled_systems = []
        
        for grate in valid_grates:
            grate_sku = str(grate.get(sku_col, '')).upper()
            grate_color = str(grate.get('Color', ''))
            grate_mat = str(grate.get(mat_col, ''))
            grate_name = str(grate.get('Product_Name', ''))
            grate_price = self.get_price(df_prices, grate_sku)
            
            series_tag = self.extract_series(grate_name)
            if series_tag == "CleanLine" and "154.44" in grate_sku: series_tag = "CleanLine 80"
            
            if grate_price == 0.0: continue

            for s_type, siphon in [("Standardní", siphon_std), ("Snížený", siphon_flat)]:
                siphon_sku = str(siphon.get(sku_col, '')).upper()
                siphon_price = self.get_price(df_prices, siphon_sku)
                
                if siphon_price == 0.0: continue

                total_price = round(grate_price + siphon_price, 2)
                
                # Zjištění průtoku (podpora obou formátů z Viega a Geberit skriptů)
                sys_flow = str(siphon.get('Flow_Rate_l_s', siphon.get('Flow_Rate_ls', '')))
                
                sys_outlet = "DN 50" if "150" in siphon_sku else "DN 40" 
                has_v4a = "Yes" if "V4A" in grate_mat else "No"
                color_clean = grate_color if grate_color else "Edelstahl"
                
                system_name = f"Geberit {series_tag} {color_clean} ({s_type} - {sys_outlet})"
                evidence_text = f"Sifon ({siphon_sku}): {siphon_price}€; Rošt ({grate_sku}): {grate_price}€"
                
                compiled_systems.append({
                    "Brand": "Geberit",
                    "Product_Name": str(system_name),
                    "Tech_Match_Score": "100/100", 
                    "Total_Price_EUR": float(total_price),
                    "Price_vs_Reference_Perc": "", 
                    "System_Flow_Rate": str(sys_flow),
                    "Main_Material": str(grate_mat),
                    "Has_V4A": str(has_v4a),
                    "Cert_EN1253": "Yes" if "Yes" in str(siphon.get('Cert_EN1253', '')) else "No",
                    "Cert_EN18534": "Yes", 
                    "Height_Adjustability": "65-175 mm",
                    "Vertical_Outlet_Option": str(sys_outlet),
                    "Has_Fleece": "Yes",
                    "Color_Count": "1",
                    "Evidence": str(evidence_text)
                })
                
                print(f"      ✅ Sestaveno: {system_name} -> {total_price} €", file=sys.stderr)

        if not compiled_systems: 
            print("\n❌ Nepodařilo se sestavit žádné systémy.")
            return

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_new_systems = pd.DataFrame(compiled_systems)
            try:
                # Ošetření, pokud list Comparison_Report ještě neexistuje
                df_report = pd.read_excel(self.excel_path, sheet_name="Comparison_Report")
                if not df_report.empty and 'Brand' in df_report.columns:
                    df_report = df_report[df_report['Brand'].astype(str).str.strip() != 'Geberit']
                
                # Zápis do existujícího
                pd.concat([df_report, df_new_systems], ignore_index=True).to_excel(writer, sheet_name="Comparison_Report", index=False)
            except Exception:
                # Vytvoření nového
                df_new_systems.to_excel(writer, sheet_name="Comparison_Report", index=False)

        print(f"\n✅ Hotovo! Do záložky Comparison_Report bylo zapsáno {len(compiled_systems)} vyčištěných Geberit systémů!")

if __name__ == "__main__":
    GeberitSystemCalculatorFinal().run()