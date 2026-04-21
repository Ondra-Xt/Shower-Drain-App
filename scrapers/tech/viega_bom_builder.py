import pandas as pd
import os

class ViegaBOMBuilder:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path

    def run(self):
        if not os.path.exists(self.excel_path):
            print("❌ Excel nenalezen!")
            return

        print("\n" + "="*60)
        print("🏗️ KROK 3: Viega BOM Builder (Skládání setů)")
        print("="*60)

        # Načtení dat
        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        df_tech['Component_SKU'] = df_tech['Component_SKU'].astype(str).str.strip()
        
        # Filtrujeme Viegu
        viega_items = df_tech[df_tech['Manufacturer'] == 'Viega']
        
        bom_entries = []

        # --- LOGIKA 1: CLEVIVA SETY ---
        # Sifony pro Clevivu (základní kameny)
        cleviva_bases = {
            "794101": "Standard (95mm)",
            "794118": "Snížený (70mm)",
            "794163": "Vertikální"
        }
        
        # Profily pro Clevivu (to barevné nahoře)
        # Hledáme podle jména produktu nebo délky
        cleviva_profiles = viega_items[viega_items['Product_Name'].str.contains("Cleviva", na=False) & 
                                      viega_items['Component_SKU'].str.match(r'^(794|736|737)')]

        for _, profile in cleviva_profiles.iterrows():
            p_sku = profile['Component_SKU']
            p_name = f"Viega Cleviva {profile['Color']} {profile['Length_mm']}mm"
            
            # Pro každý profil vytvoříme set se standardním sifonem
            for b_sku, b_desc in cleviva_bases.items():
                parent_sku = f"CLEVIVA_{p_sku}_{b_sku}"
                
                # Zápis komponent do BOM
                bom_entries.append({
                    "Parent_Product_SKU": parent_sku,
                    "Component_Type": "Base Set",
                    "Component_Name": f"Cleviva Sifon {b_desc}",
                    "Component_SKU": b_sku,
                    "Quantity": 1
                })
                bom_entries.append({
                    "Parent_Product_SKU": parent_sku,
                    "Component_Type": "Finish Set",
                    "Component_Name": p_name,
                    "Component_SKU": p_sku,
                    "Quantity": 1
                })

        # --- LOGIKA 2: VARIO SETY ---
        vario_bases = viega_items[viega_items['Product_Name'].str.contains("Vario", na=False) & 
                                 viega_items['Product_Name'].str.contains("Grundkörper", na=False)]
        vario_grates = viega_items[viega_items['Product_Name'].str.contains("Vario", na=False) & 
                                  viega_items['Product_Name'].str.contains("Stegrost", na=False)]

        for _, base in vario_bases.iterrows():
            for _, grate in vario_grates.iterrows():
                parent_sku = f"VARIO_{base['Component_SKU']}_{grate['Component_SKU']}"
                bom_entries.append({
                    "Parent_Product_SKU": parent_sku, "Component_Type": "Base Set",
                    "Component_Name": "Vario Těleso", "Component_SKU": base['Component_SKU'], "Quantity": 1
                })
                bom_entries.append({
                    "Parent_Product_SKU": parent_sku, "Component_Type": "Finish Set",
                    "Component_Name": f"Vario Rošt {grate['Color']}", "Component_SKU": grate['Component_SKU'], "Quantity": 1
                })

        if not bom_entries:
            print("⚠️ Nepodařilo se logicky spárovat žádné sety. Zkontrolujte názvy produktů.")
            return

        # Uložení do BOM_Definitions
        df_bom_new = pd.DataFrame(bom_entries)
        
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                # Načteme stávající BOM a přidáme nové (Viega nahradíme)
                try:
                    df_bom_old = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
                    # Smažeme starou Viegu z BOM
                    df_bom_others = df_bom_old[~df_bom_old['Parent_Product_SKU'].str.contains("CLEVIVA|VARIO|TEMPOPLEX", na=False)]
                    df_bom_final = pd.concat([df_bom_others, df_bom_new], ignore_index=True)
                except:
                    df_bom_final = df_bom_new
                
                df_bom_final.to_excel(writer, sheet_name="BOM_Definitions", index=False)
        except Exception as e:
            print(f"❌ Chyba při zápisu: {e}")
            return

        print(f"✅ HOTOVO! Vytvořeno {len(df_bom_new) // 2} kompletních Viega setů v 'BOM_Definitions'.")
        print("Nyní můžete spustit hlavní Comparison Report.")

if __name__ == "__main__":
    ViegaBOMBuilder().run()