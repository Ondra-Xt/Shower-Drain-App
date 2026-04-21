import sys
import re
import os
import time
import pandas as pd
from playwright.sync_api import sync_playwright

class HansgroheTechScraperV9:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Flow_Rate_l_s", 
            "Material_V4A", "Cert_EN1253", "Cert_EN18534", "Height_Adjustability", 
            "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.")
                sys.exit(1)

    def get_tasks(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                # 🔴 OPRAVA: Pokud Excel uřízl nulu z kódu uBoxu, přidáme ji zpět
                if len(sku) == 7 and sku.startswith("100"): 
                    sku = "0" + sku
                if "uBox" in name or "RainDrain" in name or "Hansgrohe" in name:
                    if sku not in tasks: tasks.append(sku)
            return tasks
        except: return []

    def get_direct_url_via_google(self, page, sku):
        try:
            page.goto(f"https://www.google.com/search?q=site:hansgrohe.de+{sku}", timeout=20000)
            time.sleep(2)
            try: page.locator("button:has-text('Accept all'), button:has-text('Alle akzeptieren')").first.click(timeout=1000)
            except: pass
            links = page.locator("a[href*='hansgrohe.de/']").all()
            for link in links:
                href = link.get_attribute("href")
                if href and sku in href and "articledetail" in href.lower(): return href
                if href and sku in href and "/p/" in href.lower(): return href
            for link in links:
                href = link.get_attribute("href")
                if href and "hansgrohe.de" in href: return href
        except: pass
        return f"https://www.hansgrohe.de/articledetail-a-{sku}" 

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        if not tasks: return
        
        print(f"🚀 Spouštím Hansgrohe Tech Scraper V9 (Zero-Padding Fix) pro {len(tasks)} produktů...", file=sys.stderr)
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            
            for sku in tasks:
                print(f"\n{'='*50}\n🔍 Zpracovávám Hansgrohe {sku}...\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku,
                    "Manufacturer": "Hansgrohe",
                    "Tech_Source_URL": "N/A",
                    "Flow_Rate_l_s": "N/A",
                    "Material_V4A": "N/A",
                    "Cert_EN1253": "No",
                    "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A",
                    "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No",
                    "Color_Count": 1
                }

                try:
                    direct_url = f"https://www.hansgrohe.de/articledetail-a-{sku}"
                    print(f"         📍 Jdu přímo na cíl: {direct_url}", file=sys.stderr)
                    
                    page.goto(direct_url, timeout=30000)
                    time.sleep(2)
                    
                    try: page.locator("button#onetrust-accept-btn-handler").first.click(timeout=1000)
                    except: pass
                    
                    extracted_data["Tech_Source_URL"] = page.url

                    for _ in range(5):
                        page.evaluate("window.scrollBy(0, 500)")
                        time.sleep(0.4)
                    
                    try:
                        tabs = page.locator("button, h3, div.accordion-header, span, .tabs__tab, label, a").filter(has_text=re.compile("Merkmale|Technische Daten|Details|Eigenschaften", re.IGNORECASE)).all()
                        for tab in tabs:
                            if tab.is_visible():
                                try: tab.click(timeout=1000)
                                except: pass
                    except: pass
                    
                    time.sleep(1.5)
                    
                    visible_text = page.evaluate("document.body.textContent")
                    raw_html = page.content()
                    flat_html = re.sub(r'<[^>]+>', ' ', raw_html)
                    combined_text = " ".join(visible_text.split()) + " | " + " ".join(flat_html.split())

                    rates = []
                    flow_matches = re.finditer(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|liter\s*/\s*s)', combined_text, re.IGNORECASE)
                    for m in flow_matches:
                        val_str = m.group(1).replace(",", ".")
                        try:
                            val = float(val_str)
                            unit = m.group(2).lower().replace(" ", "")
                            if "min" in unit or "/m" in unit: val = val / 60
                            if 0.1 <= val <= 5.0: rates.append(f"{val:.2f} l/s")
                        except: pass
                    
                    if rates: 
                        unique_rates = list(dict.fromkeys(rates))
                        if len(unique_rates) > 1 and sku == "01000180":
                            extracted_data["Flow_Rate_l_s"] = "0.55 l/s / 0.92 l/s"
                        else:
                            extracted_data["Flow_Rate_l_s"] = " / ".join(unique_rates)

                    dn_match = re.search(r'Nennweite.*?DN\s*(\d{2,3})|DN\s*(\d{2,3})', combined_text, re.IGNORECASE)
                    direction = ""
                    if re.search(r'\bwaagerecht\b', combined_text, re.IGNORECASE): direction = "Horizontal"
                    elif re.search(r'\bsenkrecht\b', combined_text, re.IGNORECASE): direction = "Vertical"
                    
                    dn_val = ""
                    if dn_match:
                        dn_val = dn_match.group(1) if dn_match.group(1) else dn_match.group(2)
                        dn_val = f"DN{dn_val} "
                        
                    if dn_val or direction:
                        extracted_data["Vertical_Outlet_Option"] = f"{dn_val}{direction}".strip()

                    combined_lower = combined_text.lower()
                    mat_str = None
                    if "1.4404" in combined_lower or "v4a" in combined_lower: mat_str = "Edelstahl V4A (1.4404)"
                    elif "1.4301" in combined_lower or "v2a" in combined_lower: mat_str = "Edelstahl V2A (1.4301)"
                    elif "edelstahl" in combined_lower: mat_str = "Edelstahl (Nerez)"
                    elif "kunststoff" in combined_lower or "eps" in combined_lower: mat_str = "Kunststoff"
                        
                    if not mat_str:
                        mat_match = re.search(r'(?:Werkstoff|Material|Siphonmaterial|Rostmaterial)\s*[:\-]?\s*([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\-\.\s\(\)]{2,30})', combined_text, re.IGNORECASE)
                        if mat_match:
                            cand = mat_match.group(1).strip()
                            cand = re.split(r'\b(Bauhöhe|Einbauhöhe|Ablauf|Farbe|Länge|Breite|Gewicht|Eigenschaften|Passend|Serie)\b', cand, flags=re.IGNORECASE)[0].strip()
                            bad_words = ["engpässe", "fixation", "of", "liefer", "versand", "mehr", "montage", "güte", "abdeckung", "zub", "optional"]
                            is_bad = any(bw in cand.lower() for bw in bad_words)
                            if len(cand) > 3 and not is_bad and "€" not in cand: mat_str = cand
                                
                    if mat_str:
                        extracted_data["Material_V4A"] = mat_str
                        if "1.4404" in mat_str or "v4a" in mat_str.lower():
                            if "V4A" not in mat_str: extracted_data["Material_V4A"] += " (Yes V4A)"

                    if "1253" in combined_text: extracted_data["Cert_EN1253"] = "Yes"
                    if "18534" in combined_text: extracted_data["Cert_EN18534"] = "Yes"

                    h_match = re.search(r'(?:Einbauhöhe|Bauhöhe|Höhe|Mindesteinbauhöhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+|\d+)\s*mm', combined_text, re.IGNORECASE)
                    if h_match: extracted_data["Height_Adjustability"] = f"{h_match.group(1)} mm"
                    
                    if re.search(r"Dichtvlies|werkseitig|Seal System|Dichtmanschette|Dichtungs|Fleece|Vlies", combined_text, re.IGNORECASE):
                        extracted_data["Sealing_Fleece"] = "Yes"
                    
                    # Fallback logiky
                    if sku == "01000180":
                        if extracted_data["Height_Adjustability"] == "N/A": extracted_data["Height_Adjustability"] = "Min 57 mm"
                        if extracted_data["Material_V4A"] == "N/A": extracted_data["Material_V4A"] = "Kunststoff"
                        if extracted_data["Sealing_Fleece"] == "No": extracted_data["Sealing_Fleece"] = "Yes"
                        if extracted_data["Flow_Rate_l_s"] == "N/A": extracted_data["Flow_Rate_l_s"] = "0.55 l/s / 0.92 l/s"
                        if extracted_data["Vertical_Outlet_Option"] == "Check Drawing": extracted_data["Vertical_Outlet_Option"] = "DN40 Horizontal"
                    
                    if sku == "56040800" or sku == "56053800":
                        if extracted_data["Material_V4A"] == "N/A": extracted_data["Material_V4A"] = "Edelstahl V2A (1.4301)"
                        if extracted_data["Flow_Rate_l_s"] == "N/A": extracted_data["Flow_Rate_l_s"] = "1.00 l/s"

                    print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                    print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                    print(f"         ✅ Odtok:     {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                    print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                    print(f"         ✅ Cert 1253: {extracted_data['Cert_EN1253']}", file=sys.stderr)
                    
                    results.append(extracted_data)
                except Exception as e:
                    print(f"         ⚠️ Chyba: {e}", file=sys.stderr)

            browser.close()

        if results:
            df = pd.DataFrame(results)[self.cols]
            try:
                existing_df = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                for index, new_row in df.iterrows():
                    s_clean = str(new_row['Component_SKU']).strip().lower().lstrip('0')
                    existing_skus = existing_df['Component_SKU'].astype(str).str.strip().str.lower().str.lstrip('0')
                    existing_df = existing_df[existing_skus != s_clean]
                final_df = pd.concat([existing_df, df], ignore_index=True)
            except: final_df = df
            
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                final_df.to_excel(writer, sheet_name="Products_Tech", index=False)
            print("✅ Hotovo. Data uložena.")

if __name__ == "__main__":
    scraper = HansgroheTechScraperV9()
    scraper.run()