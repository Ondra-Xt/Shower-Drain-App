import pandas as pd
from playwright.sync_api import sync_playwright
import re
import time
import os
import random

class TechSpecsAgent:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_tech"): os.makedirs("debug_tech")

    def load_tasks(self):
        """Načte SKU z BOM_Definitions, která ještě nemají technická data."""
        if not os.path.exists(self.excel_path): return []
        
        # Načteme definice produktů
        df_bom = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
        tasks = []
        
        # Definice domovských stránek výrobců
        domains = {
            "Hansgrohe": "https://www.hansgrohe.com", # Nebo .de pro více detailů
            "Geberit": "https://www.geberit.com",
            "TECE": "https://www.tece.com",
            "Alca": "https://www.alcadrain.com",
            "Dallmer": "https://www.dallmer.com",
            "Viega": "https://www.viega.com",
            "ESS": "https://www.easydrain.com",
            "Schlueter": "https://www.schluter.com",
            "Schuette": "https://fjschuette.com"
        }

        for _, row in df_bom.iterrows():
            sku = str(row["Component_SKU"]).strip()
            name = str(row["Component_Name"])
            
            # Detekce značky
            brand = "Unknown"
            start_url = ""
            
            if "Geberit" in name: brand = "Geberit"
            elif "TECE" in name: brand = "TECE"
            elif "Hansgrohe" in name or "RainDrain" in name: brand = "Hansgrohe"
            elif "Alca" in name: brand = "Alca"
            elif "Dallmer" in name: brand = "Dallmer"
            elif "Viega" in name: brand = "Viega"
            elif "Easy Drain" in name or "ESS" in name: brand = "ESS"
            
            # Jungborn a Form & Style řeší Hornbach scraper, zde přeskakujeme
            if "Jungborn" in name or "Form" in name: continue

            if brand in domains:
                tasks.append({
                    "sku": sku,
                    "brand": brand,
                    "base_url": domains[brand]
                })
        
        return tasks

    def analyze_text_for_specs(self, text):
        """Univerzální analyzátor textu hledající klíčová slova."""
        specs = {
            "Flow_Rate_l_s": None,
            "Material_V4A": False,
            "Cert_EN1253": False,
            "Cert_EN18534": False,
            "Height_Adjustability": None,
            "Vertical_Outlet_Option": False,
            "Sealing_Fleece": False,
            "Color_Count": 1 # Default
        }
        
        text_lower = text.lower()

        # 1. Flow Rate (0.8 l/s)
        # Hledáme vzory jako "0,8 l/s", "0.8l/s", "capacity 1.2 l/s"
        flow_match = re.search(r'(\d+[.,]\d+)\s*l/s', text_lower)
        if flow_match:
            specs["Flow_Rate_l_s"] = flow_match.group(1).replace(",", ".")

        # 2. Material V4A (High quality stainless)
        if any(x in text_lower for x in ["v4a", "1.4404", "316l", "marine grade"]):
            specs["Material_V4A"] = True

        # 3. Certifikace
        if "en 1253" in text_lower or "en1253" in text_lower:
            specs["Cert_EN1253"] = True
        if "en 18534" in text_lower or "18534" in text_lower:
            specs["Cert_EN18534"] = True

        # 4. Height Adjustability
        # Hledáme "height adjustment", "verstellbereich", a čísla mm
        if "adjust" in text_lower or "verstell" in text_lower:
            h_match = re.search(r'(\d+)\s*-\s*(\d+)\s*mm', text_lower)
            if h_match:
                specs["Height_Adjustability"] = f"{h_match.group(1)}-{h_match.group(2)}"

        # 5. Vertical Outlet
        if any(x in text_lower for x in ["vertical outlet", "senkrecht", "vertical drain"]):
            specs["Vertical_Outlet_Option"] = True

        # 6. Sealing Fleece (Pre-assembled)
        if any(x in text_lower for x in ["sealing fleece", "dichtvlies", "waterproofing membrane", "factory-mounted"]):
            specs["Sealing_Fleece"] = True

        # 7. Colors (Hrubý odhad - hledání klíčových slov barev)
        colors = ["chrome", "black", "matt", "white", "gold", "bronze", "steel", "brushed"]
        found_colors = sum(1 for c in colors if c in text_lower)
        if found_colors > 1:
            specs["Color_Count"] = found_colors

        return specs

    def search_and_analyze(self, page, task):
        """Vyhledá produkt na webu výrobce a stáhne data."""
        sku = task['sku']
        brand = task['brand']
        base_url = task['base_url']
        
        print(f"🔍 {brand}: Hledám technická data pro '{sku}'...")
        
        try:
            # 1. Jdi na domovskou stránku / vyhledávání
            # Většina webů má strukturu /search?q=SKU
            search_url = f"{base_url}/search?q={sku}" # Generický pokus
            if brand == "Hansgrohe":
                search_url = f"https://www.hansgrohe.com/articledetail-{sku}" # Hansgrohe direct link trick
            elif brand == "Geberit":
                search_url = f"{base_url}/en/search/?q={sku}"
            
            page.goto(search_url, timeout=30000)
            
            # Hansgrohe direct link fallback
            if brand == "Hansgrohe" and page.title().startswith("Error"):
                 page.goto(f"https://www.hansgrohe.de/articledetail-{sku}") # Zkusíme DE verzi

            time.sleep(3)
            
            # Pokud jsme na vyhledávání a vidíme výsledky, klikneme na první
            if "search" in page.url:
                first_result = page.locator("a[href*='product'], a[href*='detail'], h3 a").first
                if first_result.is_visible():
                    print("   👉 Klikám na první výsledek vyhledávání...")
                    first_result.click()
                    time.sleep(3)

            # 2. Extrahuj text z produktové stránky
            # Otevřeme taby "Technical data" pokud existují
            try:
                page.get_by_text(re.compile("Technical|Technisch|Details", re.IGNORECASE)).click(timeout=1000)
            except: pass
            
            full_text = page.locator("body").inner_text()
            
            # 3. Analýza
            specs = self.analyze_text_for_specs(full_text)
            
            # Kontrola úspěšnosti - pokud jsme nenašli nic, možná jsme na špatné stránce
            if not specs["Flow_Rate_l_s"] and not specs["Cert_EN1253"]:
                 print("   ⚠️ Málo dat nalezeno. Možná špatná stránka?")
            else:
                 print(f"   ✅ Data nalezena: {specs}")
            
            return specs, page.url

        except Exception as e:
            print(f"   ❌ Chyba: {e}")
            return None, None

    def run(self):
        tasks = self.load_tasks()
        print(f"🚀 Nalezeno {len(tasks)} produktů k analýze.")
        
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless=False pro ladění
            page = browser.new_page()
            
            for task in tasks:
                specs, url = self.search_and_analyze(page, task)
                if specs:
                    row = {
                        "Component_SKU": task['sku'],
                        "Manufacturer": task['brand'],
                        "Tech_Source_URL": url,
                        **specs
                    }
                    results.append(row)
                time.sleep(1) # Politeness delay
                
            browser.close()

        if results:
            self.save_results(results)

    def save_results(self, results):
        df_new = pd.DataFrame(results)
        
        # Načteme existující nebo vytvoříme nový
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                # Zapíšeme do listu Products_Tech
                df_new.to_excel(writer, sheet_name="Products_Tech", index=False)
            print("✅ Technická data uložena do listu 'Products_Tech'.")
        except Exception as e:
            print(f"⚠️ Chyba při ukládání: {e}")
            # Fallback na CSV
            df_new.to_csv("tech_data_backup.csv", index=False)
            print("💾 Data uložena do tech_data_backup.csv")

if __name__ == "__main__":
    agent = TechSpecsAgent()
    agent.run()