import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import sys
import os

class GeberitMasterDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        # Půjdeme přímo po konkrétních designových řadách Geberitu
        self.search_queries = [
            "CleanLine20",
            "CleanLine30",
            "CleanLine50",
            "CleanLine60",
            "CleanLine80",
            "Rohbauset CleanLine"
        ]

    def run(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Excel soubor {self.excel_path} nebyl nalezen.")
            return

        print("\n" + "="*60)
        print("🕵️ Spouštím KROK 1: Geberit Master Catalog Discovery")
        print("="*60 + "\n", file=sys.stderr)

        # Načtení stávajících dat, ať nepřidáváme duplicity
        df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        existing_skus = set(df_tech['Component_SKU'].astype(str).str.upper().tolist())
        new_skus_found = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for query in self.search_queries:
                print(f"\n🔎 Hledám v oficiálním katalogu Geberit: {query}", file=sys.stderr)
                try:
                    # Jdeme přímo do srdce německého Geberit katalogu
                    search_url = f"https://catalog.geberit.de/de-DE/search?q={query.replace(' ', '+')}"
                    page.goto(search_url, timeout=40000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(3)

                    # Odkliknutí cookies, pokud tam jsou
                    try: page.locator('button:has-text("Akzeptieren")').first.click(timeout=2000)
                    except: pass

                    # Posbíráme všechny odkazy na produkty ve výsledcích
                    links = page.locator("a").all()
                    target_links = []
                    for link in links:
                        try:
                            href = link.get_attribute("href")
                            if href and "/product/" in href:
                                full_link = "https://catalog.geberit.de" + href if href.startswith("/") else href
                                if full_link not in target_links: target_links.append(full_link)
                        except: pass
                    
                    target_links = list(set(target_links))[:8] # Vezmeme max 8 hlavních produktů z řady
                    
                    for url in target_links:
                        try:
                            page.goto(url, timeout=30000)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(1)
                            
                            # H1 = Název řady (např. Geberit CleanLine80 Duschrinne)
                            try: h1_text = page.locator("h1").first.inner_text().strip()
                            except: h1_text = f"Geberit {query}"

                            # Vytáhneme z celé stránky absolutně všechny SKU kódy (Geberit je má v tabulkách variant)
                            page_text = page.locator("body").inner_text()
                            found_skus = re.findall(r'(154\.\d{3}\.[A-Za-z0-9]{2,3}\.\d)', page_text)
                            found_skus = list(set([s.upper() for s in found_skus]))

                            for sku in found_skus:
                                if sku not in existing_skus and sku not in [s['Component_SKU'] for s in new_skus_found]:
                                    
                                    new_row = {col: "" for col in self.cols_tech}
                                    new_row.update({
                                        "Component_SKU": sku,
                                        "Manufacturer": "Geberit",
                                        "Product_Name": h1_text, # Uložíme si oficiální název pro Kalkulátor!
                                        "Tech_Source_URL": url
                                    })
                                    new_skus_found.append(new_row)
                                    print(f"   🌟 Nalezeno SKU: {sku} ({h1_text})", file=sys.stderr)
                                    
                        except Exception as e: pass

                except Exception as e:
                    print(f"   ❌ Chyba při hledání {query}: {e}", file=sys.stderr)

            browser.close()

        if new_skus_found:
            print("\n💾 Ukládám oficiální Geberit SKU kódy do Excelu...", file=sys.stderr)
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_new = pd.DataFrame(new_skus_found)
                df_combined = pd.concat([df_tech, df_new], ignore_index=True)
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"✅ Úspěšně zaneseno {len(new_skus_found)} nových variant žlabů!")
            print("➡️ NYNÍ SPUSŤTE 'KROK 2' (geberit_pricing.py - Verze 11.4), aby robot k těmto kódům stáhl ceny a PDF z Megabadu.")
        else:
            print("\n✅ Všechny varianty z oficiálního katalogu už v Excelu máme.")

if __name__ == "__main__":
    GeberitMasterDiscovery().run()