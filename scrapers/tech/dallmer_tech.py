import sys
import re
import os
import time
import io
import urllib.request
import pandas as pd
from playwright.sync_api import sync_playwright
from PyPDF2 import PdfReader

class DallmerTechScraperV4:
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
                name = str(row["Component_Name"]).lower()
                sku = str(row["Component_SKU"]).strip()
                if "dallmer" in name or "cerawall" in name or "cerafloor" in name or "dallflex" in name or "ceraline" in name:
                    if sku not in tasks: tasks.append(sku)
            return tasks
        except: return []

    def extract_best_height(self, text):
        """Projdi VŠECHNY výšky v textu a vyber tu, co má rozsah (pomlčku)"""
        best_val = None
        matches = re.finditer(r'(?:Höheneinstellung|height adjustment|Einbauhöhe|Bauhöhe|Höhe)\s*[^\d]{0,30}?\s*(\d+\s*[-– ]\s*\d+|\d+)\s*mm', text, re.IGNORECASE)
        for m in matches:
            val = m.group(1).replace(" ", "-").replace("–", "-")
            val = re.sub(r'-+', '-', val) # Ošetření, aby nevzniklo 90--238
            if "-" in val:
                best_val = val # Našel rozsah (90-238), to je náš absolutní vítěz!
                break
            elif not best_val:
                best_val = val # Zatím si uloží 90, kdyby náhodou rozsah neexistoval
                
        return f"{best_val} mm" if best_val else "N/A"

    def read_pdf_for_data(self, pdf_url):
        try:
            req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
            remote_file = urllib.request.urlopen(req).read()
            remote_file_bytes = io.BytesIO(remote_file)
            pdf = PdfReader(remote_file_bytes)
            pdf_text = "".join([page.extract_text() + " " for page in pdf.pages])
            flat_pdf = re.sub(r'\s+', ' ', pdf_text)
            
            flow = "N/A"
            rates = []
            flow_match = re.finditer(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|I/s)', flat_pdf, re.IGNORECASE)
            for m in flow_match:
                val = float(m.group(1).replace(",", "."))
                unit = m.group(2).lower()
                if "min" in unit or "/ m" in unit: val = val / 60
                if 0.1 <= val <= 5.0: rates.append(val)
                
            if rates:
                flow = f"{max(rates):.2f} l/s"
                
            # 🔴 Použití chytré logiky pro výšku
            height = self.extract_best_height(flat_pdf)

            return flow, height
        except Exception:
            return "N/A", "N/A"

    def extract_material(self, text):
        mat_str = None
        lower_text = text.lower()
        if "1.4404" in lower_text or "v4a" in lower_text or "316l" in lower_text: 
            mat_str = "Edelstahl V4A (1.4404)"
        elif "1.4301" in lower_text or "v2a" in lower_text or "304" in lower_text: 
            mat_str = "Edelstahl V2A (1.4301)"
        elif "edelstahl" in lower_text or "stainless steel" in lower_text: 
            mat_str = "Edelstahl (Nerez)"
        elif "polypropylen" in lower_text or "kunststoff" in lower_text or "eps" in lower_text: 
            mat_str = "Kunststoff (Polypropylen/EPS)"
            
        if mat_str and ("1.4404" in mat_str or "v4a" in mat_str.lower()):
            mat_str += " (Yes V4A)"
        return mat_str

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        if not tasks: return
            
        print(f"🚀 Spouštím Dallmer Tech Scraper V4 (Smart Height) pro {len(tasks)} produktů...", file=sys.stderr)
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()
            
            for sku in tasks:
                print(f"\n{'='*50}\n🔍 Zpracovávám Dallmer {sku}...\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku,
                    "Manufacturer": "Dallmer",
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
                    search_url = f"https://www.dallmer.de/de/search/index.php?searchTerm={sku}"
                    page.goto(search_url, timeout=30000)
                    time.sleep(2)
                    
                    try: page.locator("button:has-text('Alle akzeptieren'), button:has-text('Zustimmen')").first.click(timeout=1000)
                    except: pass
                    
                    try:
                        page.locator(f"a[href*='{sku}']").first.click(timeout=5000)
                        time.sleep(2)
                    except: pass
                    
                    extracted_data["Tech_Source_URL"] = page.url

                    print("         Rozbaluji technická data...", file=sys.stderr)
                    try:
                        tabs = page.locator("button, a, span, h3, h2").filter(has_text=re.compile("Technische Daten|Details|Ausführung|Material|Downloads|Specification", re.IGNORECASE)).all()
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

                    # PRŮTOK z webu
                    rates = []
                    flow_matches = re.finditer(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m)', combined_text, re.IGNORECASE)
                    for m in flow_matches:
                        val = float(m.group(1).replace(",", "."))
                        unit = m.group(2).lower().replace(" ", "")
                        if "min" in unit or "/m" in unit: val = val / 60
                        if 0.1 <= val <= 5.0: rates.append(val)
                    if rates: extracted_data["Flow_Rate_l_s"] = f"{max(rates):.2f} l/s"

                    # DN POTRUBÍ
                    dn_match = re.search(r'DN\s*(\d{2,3})', combined_text, re.IGNORECASE)
                    direction = ""
                    if re.search(r'\bwaagerecht\b|\bhorizontal\b', combined_text, re.IGNORECASE): direction = "Horizontal"
                    elif re.search(r'\bsenkrecht\b|\bvertical\b', combined_text, re.IGNORECASE): direction = "Vertical"
                    if dn_match or direction:
                        dn_val = f"DN{dn_match.group(1)} " if dn_match else ""
                        extracted_data["Vertical_Outlet_Option"] = f"{dn_val}{direction}".strip()

                    # 🔴 Použití chytré logiky pro výšku z WEBU
                    extracted_data["Height_Adjustability"] = self.extract_best_height(combined_text)

                    # 🔴 STAHOVÁNÍ PDF (Dallmer Datasheet)
                    if extracted_data["Flow_Rate_l_s"] == "N/A" or extracted_data["Height_Adjustability"] == "N/A" or "-" not in extracted_data["Height_Adjustability"]:
                        print("         Hledám doplňující data v PDF...", file=sys.stderr)
                        base_url = "https://www.dallmer.de"
                        pdf_links = []
                        for link in page.locator("a[href$='.pdf']").all():
                            try:
                                href = link.get_attribute("href")
                                if href and not any(x in href.lower() for x in ["agb", "datenschutz", "garantie", "katalog", "montage"]):
                                    if href.startswith("/"): href = base_url + href
                                    pdf_links.append(href)
                            except: pass
                        
                        for pdf_url in list(dict.fromkeys(pdf_links)):
                            print(f"         📄 Analyzuji PDF: {pdf_url.split('/')[-1]}", file=sys.stderr)
                            pdf_flow, pdf_height = self.read_pdf_for_data(pdf_url)
                            if pdf_flow != "N/A" and extracted_data["Flow_Rate_l_s"] == "N/A": 
                                extracted_data["Flow_Rate_l_s"] = pdf_flow
                            
                            # Pokud PDF našlo lepší výšku (s pomlčkou), nahradí tu z webu
                            if pdf_height != "N/A" and "-" in pdf_height:
                                extracted_data["Height_Adjustability"] = pdf_height
                            elif pdf_height != "N/A" and extracted_data["Height_Adjustability"] == "N/A":
                                extracted_data["Height_Adjustability"] = pdf_height
                                
                            # Můžeme skončit s hledáním v PDF?
                            if extracted_data["Flow_Rate_l_s"] != "N/A" and "-" in extracted_data["Height_Adjustability"]: 
                                break

                    # MATERIÁL
                    extracted_data["Material_V4A"] = self.extract_material(combined_text) or "N/A"

                    # CERTIFIKACE A LÍMEC
                    if "1253" in combined_text: extracted_data["Cert_EN1253"] = "Yes"
                    if "18534" in combined_text: extracted_data["Cert_EN18534"] = "Yes"
                    if re.search(r"Dichtmanschette|Dichtvlies|sealing collar|sealing sleeve|Verbundabdichtung", combined_text, re.IGNORECASE):
                        extracted_data["Sealing_Fleece"] = "Yes"

                    # DALLMER - SPECIFICKÁ LOGIKA
                    if sku == "570000":
                        extracted_data["Sealing_Fleece"] = "Yes"
                        if extracted_data["Material_V4A"] == "N/A": extracted_data["Material_V4A"] = "Kunststoff (Polypropylen/EPS)"
                    
                    if sku == "535139":
                        extracted_data["Sealing_Fleece"] = "No"
                        extracted_data["Flow_Rate_l_s"] = "N/A"
                        extracted_data["Cert_EN1253"] = "N/A"
                        extracted_data["Height_Adjustability"] = "N/A" 

                    print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                    print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                    print(f"         ✅ Odtok:     {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                    print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                    print(f"         ✅ Cert 1253: {extracted_data['Cert_EN1253']}", file=sys.stderr)
                    print(f"         ✅ Fleece:    {extracted_data['Sealing_Fleece']}", file=sys.stderr)
                    
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
    scraper = DallmerTechScraperV4()
    scraper.run()