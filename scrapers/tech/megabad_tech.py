import sys
import re
import os
import time
import io
import urllib.request
import pandas as pd
from playwright.sync_api import sync_playwright
from PyPDF2 import PdfReader

class MegabadTechScraperV21:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        if not os.path.exists("debug_tech"): os.makedirs("debug_tech")
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
        if not os.path.exists(self.excel_path): return []
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            for _, row in df.iterrows():
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                if "Geberit" in name or "TECE" in name:
                    tasks.append({"sku": sku, "brand": "Geberit" if "Geberit" in name else "TECE"})
            
            seen = set()
            unique_tasks = []
            for t in tasks:
                if t['sku'] not in seen:
                    unique_tasks.append(t)
                    seen.add(t['sku'])
            return unique_tasks
        except: return []

    def normalize_sku(self, sku):
        return str(sku).replace(".", "").replace("-", "").replace(" ", "").strip().lower()

    def handle_cookies(self, page):
        selectors = ["#onetrust-accept-btn-handler", "button:has-text('Alle akzeptieren')", "button:has-text('Zustimmen')"]
        for sel in selectors:
            try:
                if page.locator(sel).first.is_visible():
                    page.locator(sel).first.click(force=True, timeout=500)
                    time.sleep(0.5)
            except: pass

    def is_search_page(self, page):
        url = page.url.lower()
        if "/s/" in url or "suche" in url or "search" in url or "q=" in url: return True
        if page.locator(".search-result").count() > 0 or page.locator(".product-list-item").count() > 1: return True
        return False

    def validate_product_identity(self, page, target_sku, brand):
        if self.is_search_page(page): return False, "IsSearchPage"
        target_clean = self.normalize_sku(target_sku)
        try: h1 = page.locator("h1").first.inner_text().lower()
        except: h1 = ""
        body_text = page.evaluate("document.body.innerText").lower()
        if brand.lower() not in body_text: return False, "BrandMismatch"
        if target_clean in self.normalize_sku(page.url): return True, "OK_UrlMatch"
        if target_clean in self.normalize_sku(h1): return True, "OK_TitleMatch"
        if target_clean in self.normalize_sku(body_text): return True, "OK_LooseTextMatch"
        return False, f"SkuMismatch"

    def read_pdf_for_data(self, pdf_url):
        try:
            req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
            remote_file = urllib.request.urlopen(req).read()
            remote_file_bytes = io.BytesIO(remote_file)
            pdf = PdfReader(remote_file_bytes)
            pdf_text = "".join([page.extract_text() + " " for page in pdf.pages])
            flat_pdf = re.sub(r'\s+', ' ', pdf_text)
            
            flow, height = "N/A", "N/A"
            flow_match = re.search(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|liter\s*/\s*s|liter\s*/\s*m|liter\s*pro\s*sekunde)', flat_pdf, re.IGNORECASE)
            if flow_match:
                val = float(flow_match.group(1).replace(",", "."))
                unit = flow_match.group(2).lower()
                if "min" in unit or "/ m" in unit: val = val / 60
                if 0.1 <= val <= 5.0: flow = f"{val:.2f} l/s"
                
            h_match = re.search(r'(?:Bauhöhe|Einbauhöhe|Aufbauhöhe|Estrichhöhe|Systemmaß|Höhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+|\d+)\s*mm', flat_pdf, re.IGNORECASE)
            if h_match: height = f"{h_match.group(1)} mm"

            return flow, height
        except Exception:
            return "N/A", "N/A"

    def extract_technical_data(self, page, sku, brand):
        extracted_data = {
            "Component_SKU": sku,
            "Manufacturer": brand,
            "Tech_Source_URL": page.url,
            "Flow_Rate_l_s": "N/A",
            "Material_V4A": "N/A", 
            "Cert_EN1253": "No",
            "Cert_EN18534": "No",
            "Height_Adjustability": "N/A",
            "Vertical_Outlet_Option": "Check Drawing",
            "Sealing_Fleece": "No",
            "Color_Count": 1
        }

        print("         Aktivuji 3-Vrstvý skener vč. Anti-Nonsense filtru...", file=sys.stderr)
        
        for _ in range(8):
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(0.4)
        
        try:
            tabs = page.locator(".accordion-header, .tab-title, button, h3").filter(has_text=re.compile("Produktdetails|Techni|Details|Eigenschaften|Mehr anzeigen|mehr", re.IGNORECASE)).all()
            for tab in tabs:
                if tab.is_visible():
                    try: 
                        tab.click(timeout=1000)
                        time.sleep(0.5)
                    except: pass
        except: pass
        
        time.sleep(2)

        visible_text = page.locator("body").inner_text()
        raw_html = page.content()
        flat_html = re.sub(r'<[^>]+>', ' ', raw_html)
        
        combined_text = " ".join(visible_text.split()) + " | " + " ".join(flat_html.split())

        # PRŮTOK
        rates = []
        flow_matches = re.finditer(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|liter\s*/\s*s|liter\s*/\s*m|liter\s*pro\s*sekunde)', combined_text, re.IGNORECASE)
        for m in flow_matches:
            val_str = m.group(1).replace(",", ".")
            try:
                val = float(val_str)
                unit = m.group(2).lower().replace(" ", "")
                if "min" in unit or "/m" in unit: val = val / 60
                if 0.1 <= val <= 5.0: rates.append(f"{val:.2f} l/s")
            except: pass
        if rates: extracted_data["Flow_Rate_l_s"] = " / ".join(list(dict.fromkeys(rates)))

        # DN POTRUBÍ
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

        # VÝŠKA
        h_match = re.search(r'(?:Bauhöhe|Einbauhöhe|Aufbauhöhe|Estrichhöhe|Systemmaß|Höhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+|\d+)\s*mm', combined_text, re.IGNORECASE)
        if h_match: extracted_data["Height_Adjustability"] = f"{h_match.group(1)} mm"
        if extracted_data["Height_Adjustability"] == "N/A" and brand == "Geberit":
            if "H=90" in combined_text or "90 mm" in combined_text: extracted_data["Height_Adjustability"] = "90 mm"
            elif "H=65" in combined_text or "65 mm" in combined_text: extracted_data["Height_Adjustability"] = "65 mm"

        # KONTROLA PDF
        if extracted_data["Flow_Rate_l_s"] == "N/A" or extracted_data["Height_Adjustability"] == "N/A":
            print("         Záchranná síť: Hledám data v PDF...", file=sys.stderr)
            pdf_links = page.locator("a").all()
            for link in pdf_links:
                try:
                    href = link.get_attribute("href")
                    if href and ".pdf" in href.lower():
                        if any(x in href.lower() for x in ["datenschutz", "garantie", "agb", "katalog", "label"]): continue
                        if href.startswith("/"): href = "https://www.megabad.com" + href
                        print(f"         📄 Analyzuji PDF: {href.split('/')[-1].split('?')[0]}", file=sys.stderr)
                        pdf_flow, pdf_height = self.read_pdf_for_data(href)
                        if pdf_flow != "N/A" and extracted_data["Flow_Rate_l_s"] == "N/A": 
                            extracted_data["Flow_Rate_l_s"] = pdf_flow
                        if pdf_height != "N/A" and extracted_data["Height_Adjustability"] == "N/A": 
                            extracted_data["Height_Adjustability"] = pdf_height
                        if extracted_data["Flow_Rate_l_s"] != "N/A" and extracted_data["Height_Adjustability"] != "N/A": break
                except: pass

        # MATERIÁL - OPRAVA PROTI "OF FIXATION"
        mat_str = None
        mat_match = re.search(r'(?:Werkstoff|Material|Siphonmaterial|Rostmaterial)\s*[:\-]?\s*([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\-\.\s\(\)]{2,30})', combined_text, re.IGNORECASE)
        if mat_match:
            cand = mat_match.group(1).strip()
            cand = re.split(r'\b(Bauhöhe|Einbauhöhe|Ablauf|Farbe|Länge|Breite|Gewicht|Eigenschaften|Passend|Serie)\b', cand, flags=re.IGNORECASE)[0].strip()
            # Pokud do materiálu skočil nesmysl (fixation, of...), vůbec ho nevezme
            if len(cand) > 3 and "Maße" not in cand and "€" not in cand and "fixation" not in cand.lower() and "of " not in cand.lower(): 
                mat_str = cand
                
        # ZÁCHRANA MATERIÁLU
        if not mat_str:
            if "1.4404" in combined_text or "v4a" in combined_text.lower(): mat_str = "Edelstahl V4A (1.4404)"
            elif "1.4301" in combined_text or "v2a" in combined_text.lower(): mat_str = "Edelstahl V2A (1.4301)"
            elif "edelstahl" in combined_text.lower(): mat_str = "Edelstahl (Nerez)"
            elif "kunststoff" in combined_text.lower() or "eps" in combined_text.lower(): mat_str = "Kunststoff"
            
        if mat_str:
            extracted_data["Material_V4A"] = mat_str
            if "1.4404" in mat_str or "v4a" in mat_str.lower():
                if "V4A" not in mat_str: extracted_data["Material_V4A"] += " (Yes V4A)"

        # CERTIFIKACE A TĚSNĚNÍ
        if "1253" in combined_text: extracted_data["Cert_EN1253"] = "Yes"
        if "18534" in combined_text: extracted_data["Cert_EN18534"] = "Yes"
        if re.search(r"Dichtvlies|werkseitig|Seal System|Dichtmanschette|Dichtungs|Fleece|Vlies", combined_text, re.IGNORECASE):
            extracted_data["Sealing_Fleece"] = "Yes"

        print(f"         ✅ Materiál: {extracted_data['Material_V4A']}", file=sys.stderr)
        print(f"         ✅ Průtok:   {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
        print(f"         ✅ Odtok:    {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
        print(f"         ✅ Výška:    {extracted_data['Height_Adjustability']}", file=sys.stderr)
        print(f"         ✅ Fleece:   {extracted_data['Sealing_Fleece']}", file=sys.stderr)
        return extracted_data

    def search_manual(self, page, query):
        print(f"   Hledám '{query}'...", file=sys.stderr)
        try:
            page.goto("https://www.megabad.com/", timeout=60000)
            self.handle_cookies(page)
            time.sleep(2)
            found = False
            inputs = page.locator("input#search, input[name='q'], input[type='search']").all()
            if not inputs:
                try: page.locator(".search-toggle, .header-search-icon").first.click(timeout=1000)
                except: pass
                time.sleep(1)
                inputs = page.locator("input[type='text']").all()
            for inp in inputs:
                if inp.is_visible():
                    inp.click(force=True)
                    inp.fill(query)
                    page.keyboard.press("Enter")
                    found = True
                    break
            if not found: return False
            page.wait_for_load_state("domcontentloaded")
            time.sleep(4)
            return True
        except: return False

    def process_results(self, page, sku, brand):
        if not self.is_search_page(page):
            valid, status = self.validate_product_identity(page, sku, brand)
            if valid:
                print(f"      📍 Rovnou správný detail.", file=sys.stderr)
                return self.extract_technical_data(page, sku, brand)

        product_links = []
        try:
            all_links = page.locator("a").all()
            for link in all_links:
                href = link.get_attribute("href")
                if not href or len(href) < 5: continue
                if any(x in href for x in ["javascript", "#", "login", "cart", "wishlist", "bewertung"]): continue
                if ("-a-" in href or "/product/" in href) and "-k-" not in href: 
                    if href.startswith("/"): product_links.append("https://www.megabad.com" + href)
                    elif href.startswith("http"): product_links.append(href)
        except: pass

        product_links = list(dict.fromkeys(product_links))
        norm_sku = self.normalize_sku(sku)
        top = [l for l in product_links if norm_sku in l]
        rest = [l for l in product_links if l not in top]
        final_list = (top + rest)[:5] 

        for i, link in enumerate(final_list):
            try:
                page.goto(link, timeout=20000)
                time.sleep(2.5)
                self.handle_cookies(page)
                valid, status = self.validate_product_identity(page, sku, brand)
                if valid:
                    print(f"         ✅ SKU SHODA!", file=sys.stderr)
                    return self.extract_technical_data(page, sku, brand)
            except: pass
        return None

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        if not tasks: return
            
        print(f"🚀 Spouštím Megabad Scraper V21 pro {len(tasks)} produktů...", file=sys.stderr)
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                sku = task['sku']
                brand = task['brand']
                print(f"\n{'='*50}\n🔍 Zpracovávám {brand} {sku}...\n{'='*50}", file=sys.stderr)
                search_sku = sku
                if brand == "TECE" and len(sku) == 6 and sku.isdigit(): search_sku = f"{sku[:3]} {sku[3:]}"
                if self.search_manual(page, f"{brand} {search_sku}".strip()):
                    data = self.process_results(page, sku, brand)
                    if data: results.append(data)
            browser.close()

        if results:
            df = pd.DataFrame(results)[self.cols]
            try:
                existing_df = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                for index, new_row in df.iterrows():
                    sku = str(new_row['Component_SKU']).strip().lower()
                    existing_df = existing_df[existing_df['Component_SKU'].astype(str).str.strip().str.lower() != sku]
                final_df = pd.concat([existing_df, df], ignore_index=True)
            except:
                final_df = df
                
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                final_df.to_excel(writer, sheet_name="Products_Tech", index=False)
                
            print("✅ Hotovo. Nová data uložena do Excelu.", file=sys.stderr)

if __name__ == "__main__":
    scraper = MegabadTechScraperV21()
    scraper.run()