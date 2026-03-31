import pandas as pd
import numpy as np
import os
import sys

class BenchmarkAnalytics:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def load_data(self):
        """Načte všechny potřebné listy z Excelu."""
        if not os.path.exists(self.excel_path):
            print(f"❌ Soubor {self.excel_path} nenalezen.")
            sys.exit(1)
            
        try:
            self.df_bom = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            self.df_prices = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
            self.df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
            self.df_control = pd.read_excel(self.excel_path, sheet_name="Control_Panel")
            print("✅ Data úspěšně načtena.")
        except Exception as e:
            print(f"❌ Chyba při načítání dat: {e}")
            sys.exit(1)

    def get_best_price_for_sku(self, sku):
        """Najde nejnižší nalezenou cenu pro dané SKU napříč e-shopy."""
        sku = str(sku).strip()
        # Filtrujeme ceny pro dané SKU
        matches = self.df_prices[self.df_prices['Component_SKU'].astype(str).str.strip() == sku]
        
        if matches.empty:
            return None, "Price not found"
        
        # Očistíme ceny od nul a NaN
        valid_prices = matches[matches['Found_Price_EUR'] > 0]
        if valid_prices.empty:
            return None, "Valid price not found"
            
        # Vybereme minimum
        best_row = valid_prices.loc[valid_prices['Found_Price_EUR'].idxmin()]
        return best_row['Found_Price_EUR'], best_row['Eshop_Source']

    def calculate_tech_score(self, sku):
        """Jednoduché skóre technické shody (zatím placeholder)."""
        # Zde bychom mohli porovnávat parametry vůči Kaldewei
        # Pro teď vrátíme 100% pokud máme data, 0% pokud ne
        match = self.df_tech[self.df_tech['Component_SKU'].astype(str).str.strip() == str(sku)]
        if not match.empty:
            row = match.iloc[0]
            # Pokud chybí klíčová data, sniž skóre
            if str(row.get('Flow_Rate_l_s')) == "N/A": return 50
            return 100
        return 0

    def run_analysis(self):
        print("🚀 Spouštím výpočet benchmarku...")
        self.load_data()
        
        report_data = []
        
        # 1. Získáme unikátní Rodičovské produkty (Parent Products)
        parents = self.df_bom['Parent_Product_SKU'].unique()
        
        # Referenční cena Kaldewei (pro porovnání)
        ref_price = 0
        try:
            # Zkusíme najít cenu FlowLine v Control Panelu nebo ji zadáme fixně
            # Pro účely dema předpokládejme cenu 280 EUR (MOC)
            ref_price = 280.0 
        except: pass

        for parent_sku in parents:
            parent_sku = str(parent_sku)
            # Získáme komponenty pro tento produkt
            components = self.df_bom[self.df_bom['Parent_Product_SKU'].astype(str) == parent_sku]
            
            product_name = components.iloc[0]['Parent_Product_SKU'] # Fallback name
            # Zkusíme najít hezčí název z tech listu
            tech_info = self.df_tech[self.df_tech['Component_SKU'].astype(str) == parent_sku]
            brand = "Unknown"
            
            if not tech_info.empty:
                brand = tech_info.iloc[0].get('Manufacturer', 'Unknown')
            else:
                # Zkusíme odhadnout značku z názvu komponenty
                first_comp_name = components.iloc[0]['Component_Name']
                if "Hansgrohe" in str(first_comp_name): brand = "Hansgrohe"
                elif "Geberit" in str(first_comp_name): brand = "Geberit"
                elif "TECE" in str(first_comp_name): brand = "TECE"

            total_system_price = 0
            is_complete = True
            evidence = []
            
            # Sčítání cen komponent (BOM)
            for _, comp in components.iterrows():
                comp_sku = str(comp['Component_SKU'])
                qty = comp['Quantity']
                
                price, source = self.get_best_price_for_sku(comp_sku)
                
                if price:
                    total_system_price += (price * qty)
                    evidence.append(f"{comp['Component_Name']}: {price}€ ({source})")
                else:
                    is_complete = False
                    evidence.append(f"{comp['Component_Name']}: CENU NEMÁME")

            # Výpočet delta vůči Kaldewei
            price_delta = 0
            if is_complete and ref_price > 0:
                price_delta = ((total_system_price - ref_price) / ref_price) * 100

            report_data.append({
                "Brand": brand,
                "Product_SKU": parent_sku,
                "Is_Complete_System": "YES" if is_complete else "PARTIAL",
                "Total_Market_Price_EUR": round(total_system_price, 2),
                "Kaldewei_Ref_Price": ref_price,
                "Price_Difference_%": round(price_delta, 1) if is_complete else "N/A",
                "Price_Breakdown": "; ".join(evidence)
            })

        # Uložení reportu
        if report_data:
            df_report = pd.DataFrame(report_data)
            print("\n📊 VÝSLEDEK ANALÝZY:")
            print(df_report[["Brand", "Total_Market_Price_EUR", "Price_Difference_%"]])
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_report.to_excel(writer, sheet_name="Comparison_Report", index=False)
            print(f"✅ Report uložen do listu 'Comparison_Report' v {self.excel_path}")

if __name__ == "__main__":
    analyst = BenchmarkAnalytics()
    analyst.run_analysis()