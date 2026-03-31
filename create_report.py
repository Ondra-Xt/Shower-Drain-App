import pandas as pd
import os

def generate_benchmark_report(excel_path="benchmark_master_v3_fixed.xlsx"):
    print("📊 Generuji finální Benchmark Report...")
    
    # 1. Načtení dat
    xls = pd.ExcelFile(excel_path)
    df_tech = pd.read_excel(xls, "Products_Tech")
    df_bom = pd.read_excel(xls, "BOM_Definitions")
    df_prices = pd.read_excel(xls, "Market_Prices")
    df_control = pd.read_excel(xls, "Control_Panel")
    
    # Nastavení referenční ceny pro Kaldewei (pokud ji nemáš v tabulce, dosadíme odhad)
    # FlowLine Zero 1200mm set (např. 280 EUR)
    REF_PRICE_KALDEWEI = 280.0 

    # 2. Přidání Kaldewei reference (pokud chybí)
    if not any(df_tech['Brand'] == 'Kaldewei'):
        print("ℹ️ Přidávám referenční produkt Kaldewei...")
        kaldewei_ref = {
            "Brand": "Kaldewei",
            "Product_Name": "FlowLine Zero",
            "Article_Number_SKU": "Reference",
            "Length_mm": 1200,
            "Flow_Rate_ls": 0.8,
            "Completeness_Type": "Set",
            "Ref_Price_Estimate_EUR": REF_PRICE_KALDEWEI
        }
        df_tech = pd.concat([df_tech, pd.DataFrame([kaldewei_ref])], ignore_index=True)

    report_data = []

    # 3. Výpočet pro každou značku v technické tabulce
    for _, product in df_tech.iterrows():
        brand = product['Brand']
        sku = product['Article_Number_SKU']
        name = product['Product_Name']
        
        total_price = 0
        evidence = ""

        if brand == "Kaldewei":
            total_price = REF_PRICE_KALDEWEI
            evidence = "Referenční cena (Kaldewei)"
        else:
            # A) Pokud je to MODULÁRNÍ (BOM)
            if product['Completeness_Type'] == "Modular (BOM)":
                # Najdi všechny komponenty pro toto SKU
                components = df_bom[df_bom['Parent_Product_SKU'] == sku]
                for _, comp in components.iterrows():
                    comp_sku = comp['Component_SKU']
                    # Najdi nejnižší cenu pro tento komponent
                    comp_prices = df_prices[df_prices['Component_SKU'].astype(str) == str(comp_sku)]
                    if not comp_prices.empty:
                        min_price = comp_prices['Found_Price_EUR'].min()
                        total_price += min_price * comp['Quantity']
                        evidence += f"{comp['Component_Name']}: {min_price}€; "
                    else:
                        evidence += f"Missing price for {comp_sku}; "
            else:
                # B) Pokud je to jako SET
                product_prices = df_prices[df_prices['Component_SKU'].astype(str) == str(sku)]
                if not product_prices.empty:
                    total_price = product_prices['Found_Price_EUR'].min()
                    evidence = "Cena za kompletní set"

        # 4. Výpočet skóre (shoda s cílem 1200mm a 0.8 l/s)
        score = 0
        if product['Length_mm'] == 1200: score += 50
        elif abs(product['Length_mm'] - 1200) <= 300: score += 30 # Srážka za jinou délku
        
        if product['Flow_Rate_ls'] >= 0.8: score += 50
        elif product['Flow_Rate_ls'] > 0: score += 20

        # 5. Výpočet rozdílu oproti Kaldewei
        price_vs_ref = 0
        if REF_PRICE_KALDEWEI > 0 and total_price > 0:
            price_vs_ref = round(((total_price / REF_PRICE_KALDEWEI) - 1) * 100, 1)

        report_data.append({
            "Brand": brand,
            "Product_Name": name,
            "Tech_Match_Score": f"{score}/100",
            "Total_Price_EUR": round(total_price, 2),
            "Price_vs_Reference_Perc": f"{price_vs_ref}%",
            "Evidence": evidence
        })

    # 6. Uložení reportu
    df_report = pd.DataFrame(report_data)
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_report.to_excel(writer, sheet_name="Comparison_Report", index=False)
    
    print("✅ Report byl vytvořen v listu 'Comparison_Report'!")
    print(df_report[['Brand', 'Total_Price_EUR', 'Price_vs_Reference_Perc']])

if __name__ == "__main__":
    generate_benchmark_report()