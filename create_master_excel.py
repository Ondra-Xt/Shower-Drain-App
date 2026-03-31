import pandas as pd
import os

# 1. Definice struktury (Sloupce pro každý list)

# A. Řídící panel - Co hledáme
cols_control = [
    "Reference_Brand", "Reference_Product", "Target_Length_mm", "Length_Tolerance_mm",
    "Target_Flow_Rate_ls", "Competitor_Brands_List"
]

# B. Technická data - KOMPLETNÍ SEZNAM
cols_tech = [
    # -- Identifikace --
    "Brand", 
    "Product_Name", 
    "Article_Number_SKU", 
    "Product_URL",           # Odkaz na produkt
    
    # -- Rozměry --
    "Length_mm", 
    "Is_Cuttable",           # Zkracovatelné?
    
    # -- Výkon a Odtok --
    "Flow_Rate_ls",          # Průtok (l/s)
    "Outlet_Type",           # Vertical / Horizontal / Both
    "Is_Outlet_Selectable",  # Jde měnit směr odtoku? (Selectable)
    "Height_Min_mm",         # Min. stavební výška
    "Height_Max_mm",         # Max. stavební výška (rozsah)
    
    # -- Materiál a Kvalita --
    "Material_Body",         # Např. Stainless Steel 1.4301
    "Is_V4A",                # Je to kvalitnější ocel V4A? (Ano/Ne)
    "Fleece_Preassembled",   # Těsnící manžeta z výroby? (Ano/Ne)
    
    # -- Normy --
    "Cert_DIN_EN1253",       # Norma pro vpusti
    "Cert_DIN_18534",        # Norma pro izolace
    
    # -- Design a Instalace --
    "Colors_Count",          # Počet barev
    "Tile_In_Possible",      # Možnost vložení dlažby (Tile-in)? (Chybělo)
    "Wall_Installation",     # Instalace ke stěně? (Chybělo)
    
    # -- Struktura a Cena --
    "Completeness_Type",     # Set / Modular (BOM)
    "Ref_Price_Estimate_EUR", # Orientační cena (pro rychlý přehled)
    
    # -- Důkazy --
    "Datasheet_URL", 
    "Evidence_Text"          # Kde jsme to v textu našli
]

# C. Definice složení (Bill of Materials)
cols_bom = [
    "Parent_Product_SKU", "Component_Type", "Component_Name", "Component_SKU", "Quantity"
]

# D. Ceny z trhu (Pricing Scraper)
cols_prices = [
    "Component_SKU", "Eshop_Source", "Found_Price_EUR", "Price_Breakdown", "Product_URL", "Timestamp"
]

# E. Finální report
cols_report = [
    "Brand", "Product_Name", 
    "Tech_Match_Score", 
    "Total_Price_EUR", 
    "Price_vs_Reference_Perc", 
    "Missing_Features"
]

# 2. Vytvoření DataFramů (s příkladem)
df_control = pd.DataFrame([{
    "Reference_Brand": "Kaldewei",
    "Reference_Product": "FlowLine Zero",
    "Target_Length_mm": 1200,
    "Length_Tolerance_mm": 100,
    "Target_Flow_Rate_ls": 0.8,
    "Competitor_Brands_List": "Hansgrohe, Geberit, Tece, Alca, Schlüter"
}], columns=cols_control)

df_tech = pd.DataFrame(columns=cols_tech)
df_bom = pd.DataFrame(columns=cols_bom)
df_prices = pd.DataFrame(columns=cols_prices)
df_report = pd.DataFrame(columns=cols_report)

# 3. Uložení
filename = "benchmark_master_v3_fixed.xlsx"

try:
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df_control.to_excel(writer, sheet_name='Control_Panel', index=False)
        df_tech.to_excel(writer, sheet_name='Products_Tech', index=False)
        df_bom.to_excel(writer, sheet_name='BOM_Definitions', index=False)
        df_prices.to_excel(writer, sheet_name='Market_Prices', index=False)
        df_report.to_excel(writer, sheet_name='Comparison_Report', index=False)
        
    print(f"✅ Opraveno! Soubor '{filename}' obsahuje všechny parametry včetně Tile-in a Wall Install.")
    print(f"📂 Uloženo v: {os.getcwd()}")

except Exception as e:
    print(f"❌ Chyba: {e}")