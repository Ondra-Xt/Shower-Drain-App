import pandas as pd
import os

def clean_excel_database(excel_path="benchmark_master_v3_fixed.xlsx"):
    print(f"🧹 Čistím databázi: {excel_path} ...")
    
    if not os.path.exists(excel_path):
        print("❌ Soubor neexistuje.")
        return

    # 1. Načtení listů
    try:
        xls = pd.ExcelFile(excel_path)
        df_tech = pd.read_excel(xls, "Products_Tech")
        df_bom = pd.read_excel(xls, "BOM_Definitions")
        df_prices = pd.read_excel(xls, "Market_Prices")
        
        # Načteme i Control_Panel, pokud existuje
        if "Control_Panel" in xls.sheet_names:
            df_control = pd.read_excel(xls, "Control_Panel")
        else:
            df_control = pd.DataFrame()
            
    except Exception as e:
        print(f"❌ Chyba při čtení: {e}")
        return

    # 2. Čištění Products_Tech
    print(f"  - Tech: Původně {len(df_tech)} řádků")
    # Odstraníme řádky bez SKU a ty s chybou "WURDE NICHT GEFUNDEN"
    df_tech = df_tech.dropna(subset=['Article_Number_SKU'])
    df_tech = df_tech[df_tech['Product_Name'] != "WURDE NICHT GEFUNDEN"]
    # Odstraníme duplicity podle SKU (necháme poslední nalezený = nejnovější)
    df_tech = df_tech.drop_duplicates(subset=['Article_Number_SKU'], keep='last')
    print(f"  -> Tech: Nyní {len(df_tech)} unikátních produktů")

    # 3. Čištění BOM_Definitions
    print(f"  - BOM: Původně {len(df_bom)} řádků")
    # Odstraníme řádky bez Parent SKU
    df_bom = df_bom.dropna(subset=['Parent_Product_SKU'])
    # Odstraníme duplicity (stejná komponenta pro stejný produkt by měla být jen jednou)
    df_bom = df_bom.drop_duplicates(subset=['Parent_Product_SKU', 'Component_SKU'], keep='last')
    print(f"  -> BOM: Nyní {len(df_bom)} položek")

    # 4. Čištění Market_Prices (volitelné, ale užitečné)
    # Tady je to složitější, chceme nechat historii, ale pro report je lepší mít pořádek.
    # Prozatím necháme vše, report si bere min(), ale můžeme smazat evidentní nesmysly (např. 0 EUR)
    df_prices = df_prices[df_prices['Found_Price_EUR'] > 0]
    
    # 5. Uložení zpět
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
        df_bom.to_excel(writer, sheet_name="BOM_Definitions", index=False)
        df_prices.to_excel(writer, sheet_name="Market_Prices", index=False)
        if not df_control.empty:
            df_control.to_excel(writer, sheet_name="Control_Panel", index=False)
            
    print("✅ Hotovo! Excel je vyčištěn.")

if __name__ == "__main__":
    clean_excel_database()