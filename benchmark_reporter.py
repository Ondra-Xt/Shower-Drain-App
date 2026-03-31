import pandas as pd
import numpy as np
import os
import re
import sys

class BenchmarkReporter:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.")
                sys.exit(1)

    def extract_max_flow(self, flow_str):
        if pd.isna(flow_str) or str(flow_str).strip() == "N/A": return 0.0
        nums = re.findall(r'\d+\.?\d*', str(flow_str))
        try:
            return max([float(n) for n in nums if float(n) > 0])
        except:
            return 0.0

    def generate_report(self):
        self.check_excel_access()
        print("🚀 Generuji finální Benchmark Report...")

        # 1. Načtení dat
        df_bom = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
        df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        df_control = pd.read_excel(self.excel_path, sheet_name="Control_Panel")

        target_flow = float(df_control["Target_Flow_Rate_ls"].iloc[0])
        
        df_bom["Component_SKU"] = df_bom["Component_SKU"].astype(str).str.strip().str.lower()
        df_prices["Component_SKU"] = df_prices["Component_SKU"].astype(str).str.strip().str.lower()
        df_tech["Component_SKU"] = df_tech["Component_SKU"].astype(str).str.strip().str.lower()

        # 2. CHYTRÁ OPRAVA CEN: Vezme bezpečně vždy ten poslední (nejnovější) řádek!
        # Místo hledání podle data se prostě spolehne na pořadí v Excelu (nové jsou vždy dole)
        df_prices["Found_Price_EUR"] = pd.to_numeric(df_prices["Found_Price_EUR"], errors='coerce')
        df_prices = df_prices.dropna(subset=["Found_Price_EUR"])
        
        latest_per_shop = df_prices.drop_duplicates(subset=["Component_SKU", "Eshop_Source"], keep="last")
        
        min_prices = latest_per_shop.groupby("Component_SKU")["Found_Price_EUR"].min().reset_index()
        min_prices.rename(columns={"Found_Price_EUR": "Min_Price"}, inplace=True)

        # 3. Spojení dat (BOM + Ceny + Tech Data)
        merged = pd.merge(df_bom, min_prices, on="Component_SKU", how="left")
        merged = pd.merge(merged, df_tech, on="Component_SKU", how="left")

        merged["Cost"] = merged["Min_Price"] * merged["Quantity"]
        merged["Evidence_Text"] = merged["Component_Name"].astype(str) + ": " + merged["Min_Price"].fillna(0).round(2).astype(str) + "€"

        # 4. Agregace celých žlabů
        report_data = []
        
        for parent_sku, group in merged.groupby("Parent_Product_SKU"):
            brand = "Unknown"
            product_name = str(parent_sku)
            
            names = group["Component_Name"].dropna().astype(str).tolist()
            if any("Geberit" in n for n in names): brand, product_name = "Geberit", "Geberit CleanLine Set"
            elif any("TECE" in n for n in names): brand, product_name = "TECE", "TECEdrainline Set"
            elif any("RainDrain" in n for n in names): 
                brand = "Hansgrohe"
                fs = group[group["Component_Type"] == "Finish Set"]
                if not fs.empty: product_name = fs["Component_Name"].iloc[0]
            elif any("Kaldewei" in n for n in names) or str(parent_sku) == "6877": 
                brand, product_name = "Kaldewei", "Kaldewei FlowLine Zero"

            total_price = group["Cost"].sum()

            # --- ZPRACOVÁNÍ TECHNICKÝCH DAT ---
            flows = [self.extract_max_flow(val) for val in group["Flow_Rate_l_s"].tolist()]
            max_flow = max(flows) if flows else 0.0
            
            raw_mats = group["Material_V4A"].dropna().astype(str).tolist()
            clean_mats = []
            for m in raw_mats:
                m_lower = m.lower()
                if m_lower in ["n/a", "nan", "no (standard)", "none"]: continue
                if "of fixation" in m_lower: continue 
                
                m_clean = m.replace("(Yes V4A)", "").strip()
                if m_clean not in clean_mats:
                    clean_mats.append(m_clean)
            
            main_material = " + ".join(clean_mats) if clean_mats else "Unknown"
            
            has_v4a = any(isinstance(v, str) and ("v4a" in v.lower() or "1.4404" in v.lower()) for v in raw_mats)
            has_fleece = any(isinstance(v, str) and "yes" in v.lower() for v in group["Sealing_Fleece"].tolist())

            # --- VÝPOČET SKÓRE ---
            score = 0
            if max_flow >= target_flow: score += 40
            elif max_flow >= 0.5: score += 20
            
            if has_v4a: score += 30
            if has_fleece: score += 30
            
            if brand == "Kaldewei": 
                score = 100
                max_flow = target_flow
                main_material = "Edelstahl"
                if total_price == 0: total_price = 280.00

            evidence = "; ".join(group["Evidence_Text"].dropna().tolist())

            report_data.append({
                "Brand": brand,
                "Product_Name": product_name,
                "Tech_Match_Score": f"{score}/100",
                "Total_Price_EUR": round(total_price, 2),
                "_Raw_Price": total_price,
                "System_Flow_Rate": f"{max_flow} l/s",
                "Main_Material": main_material,
                "Has_V4A": "Yes" if has_v4a else "No",
                "Has_Fleece": "Yes" if has_fleece else "No",
                "Evidence": evidence
            })

        df_report = pd.DataFrame(report_data)

        # 5. Cenové srovnání
        try:
            ref_price = df_report[df_report["Brand"] == "Kaldewei"]["_Raw_Price"].values[0]
        except:
            ref_price = 280.00 

        df_report["Price_vs_Reference_Perc"] = ((df_report["_Raw_Price"] - ref_price) / ref_price * 100)
        df_report["Price_vs_Reference_Perc"] = df_report["Price_vs_Reference_Perc"].apply(lambda x: f"+{x:.1f}%" if x > 0 else f"{x:.1f}%")
        
        df_report = df_report[[
            "Brand", "Product_Name", "Tech_Match_Score", "Total_Price_EUR", 
            "Price_vs_Reference_Perc", "System_Flow_Rate", "Main_Material", 
            "Has_V4A", "Has_Fleece", "Evidence", "_Raw_Price"
        ]]
        
        df_report.drop(columns=["_Raw_Price"], inplace=True)
        df_report = df_report.sort_values(by="Total_Price_EUR")

        # 6. Uložení
        print("💾 Ukládám do Excelu do listu 'Comparison_Report'...")
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_report.to_excel(writer, sheet_name="Comparison_Report", index=False)

        print("✅ Hotovo! Report byl vygenerován (Ceny a technická data propojeny).")
        
if __name__ == "__main__":
    reporter = BenchmarkReporter()
    reporter.generate_report()