import sys
import re
import os
import time
import io
import urllib.request
import pandas as pd
from playwright.sync_api import sync_playwright
from PyPDF2 import PdfReader

class MegabadTechScraperV16:
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
            
            pdf_text = ""
            for page in pdf.pages:
                pdf_text += page.extract_text() + " "
                
            flat_pdf = re.sub(r'\s+', ' ', pdf_text)
            
            flow = "N/A"
            height = "N/A"
            
            # VYLEPŠENÝ REGEX i pro PDF (bere všechny zkratky)
            flow_match = re.search(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|liter\s*/\s*s|liter\s*/\s*m|liter\s*pro\s*sekunde)', flat_pdf, re.IGNORECASE)
            if flow_match:
                val = float(flow_match.group(1).replace(",", "."))
                unit = flow_match.group(2).lower()
                if "min" in unit or "/ m" in unit: val = val / 60
                flow = f"{val:.2f} l/s"
                
            h_match = re.search(r'(?:Bauhöhe|Einbauhöhe|Aufbauhöhe|Estrichhöhe|Systemmaß|Höhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+|\d+)\s*mm', flat_pdf, re.IGNORECASE)
            if h_match:
                height = f"{h_match.group(1)} mm"

            return flow, height
            
        except Exception as e:
            print(f"         ⚠️ Nepodařilo se přečíst PDF: {e}", file=sys.stderr)
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

        print("         Roluji dolů pro aktivaci dat...", file=sys.stderr)
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 600)")
            time.sleep(0.8)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        print("         Rozbaluji záložky...", file=sys.stderr)
        tabs = page.locator("button, div.tab-title, span, .accordion-header, label").filter(has_text=re.compile("Techni|Details|Eigenschaften|Daten|Merkmale|Zusatz|Mehr anzeigen", re.IGNORECASE)).all()
        for tab in tabs:
            if tab.is_visible():
                try: page.evaluate("(el) => el.click()", tab.element_handle())
                except: pass
        time.sleep(1.5)

        try: visible_text = page.locator("body").inner_text()
        except: visible_text = ""
        
        flat_visible = " ".join(visible_text.split())
        combined_text = flat_visible

        # 1. PRŮTOK Z WEBU (Ultimátní Regex pro TECE)
        rates = []
        flow_matches = re.finditer(r'([\d.,]+)\s*(l\s*/\s*s|l\s*/\s*sek|l\s*/\s*min|l\s*/\s*m|liter\s*/\s*s|liter\s*/\s*m|liter\s*pro\s*sekunde)', combined_text, re.IGNORECASE)
        for m in flow_matches:
            val_str = m.group(1).replace(",", ".")
            try:
                val = float(val_str)
                unit = m.group(2).lower().replace(" ", "")
                if "min" in unit or "/m" in unit: val = val / 60
                rates.append(f"{val:.2f} l/s")
            except: pass
        if rates: extracted_data["Flow_Rate_l_s"] = " / ".join(list(dict.fromkeys(rates)))

        # 2. VÝŠKA Z WEBU
        h_match = re.search(r'(?:Bauhöhe|Einbauhöhe|Aufbauhöhe|Estrichhöhe|Systemmaß|Höhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+|\d+)\s*mm', combined_text, re.IGNORECASE)
        if h_match: extracted_data["Height_Adjustability"] = f"{h_match.group(1)} mm"
        if extracted_data["Height_Adjustability"] == "N/A" and brand == "Geberit":
            if "H=90" in combined_text or "90 mm" in combined_text: extracted_data["Height_Adjustability"] = "90 mm"
            elif "H=65" in combined_text or "65 mm" in combined_text: extracted_data["Height_Adjustability"] = "65 mm"

        # 3. KONTROLA PDF (Záchrana - nyní ignoruje GDPR dokumenty)
        if extracted_data["Flow_Rate_l_s"] == "N/A":
            print("         Průtok na webu nenalezen, hledám PDF přílohy...", file=sys.stderr)
            pdf_links = page.locator("a[href$='.pdf']").all()
            for link in pdf_links:
                try:
                    pdf_url = link.get_attribute("href")
                    if pdf_url:
                        pdf_url_lower = pdf_url.lower()
                        # ZAKÁZÁNO číst GDPR a letáky
                        if any(x in pdf_url_lower for x in ["datenschutz", "garantie", "agb", "label", "anleitung", "katalog"]):
                            continue

                        if pdf_url.startswith("/"): pdf_url = "https://www.megabad.com" + pdf_url
                        print(f"         📄 Analyzuji technické PDF: {pdf_url.split('/')[-1]}", file=sys.stderr)
                        pdf_flow, pdf_height = self.read_pdf_for_data(pdf_url)
                        
                        if pdf_flow != "N/A": extracted_data["Flow_Rate_l_s"] = pdf_flow
                        if extracted_data["Height_Adjustability"] == "N/A" and pdf_height != "N/A": 
                            extracted_data["Height_Adjustability"] = pdf_height
                        
                        if extracted_data["Flow_Rate_l_s"] != "N/A": break
                except: pass

        # 4. MATERIÁL
        mat_str = None
        mat_match = re.search(r'(?:Werkstoff|Material|Siphonmaterial|Rostmaterial)\s*[:\-]?\s*([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\-\.\s\(\)]{2,30})', flat_visible, re.IGNORECASE)
        if mat_match:
            cand = mat_match.group(1).strip()
            cand = re.split(r'\b(Bauhöhe|Einbauhöhe|Ablauf|Farbe|Länge|Breite|Gewicht|Eigenschaften|Passend|Serie)\b', cand, flags=re.IGNORECASE)[0].strip()
            if len(cand) > 3 and "Maße" not in cand and "€" not in cand: mat_str = cand
        if not mat_str:
            if "1.4404" in combined_text or "v4a" in combined_text.lower(): mat_str = "Edelstahl V4A (1.4404)"
            elif "1.4301" in combined_text or "v2a" in combined_text.lower(): mat_str = "Edelstahl V2A (1.4301)"
            elif "edelstahl" in combined_text.lower(): mat_str = "Edelstahl (Nerez)"
            elif "kunststoff" in combined_text.lower() or "eps" in combined_text.lower(): mat_str = "Kunststoff"
        if mat_str:
            extracted_data["Material_V4A"] = mat_str
            if "1.4404" in mat_str or "v4a" in mat_str.lower():
                if "V4A" not in mat_str: extracted_data["Material_V4A"] += " (Yes V4A)"

        # 5. CERTIFIKACE A TĚSNĚNÍ
        if "1253" in combined_text: extracted_data["Cert_EN1253"] = "Yes"
        if "18534" in combined_text: extracted_data["Cert_EN18534"] = "Yes"
        if re.search(r"Dichtvlies|werkseitig|Seal System|Dichtmanschette|Dichtungs|Fleece|Vlies", combined_text, re.IGNORECASE):
            extracted_data["Sealing_Fleece"] = "Yes"

        print(f"         ✅ Materiál: {extracted_data['Material_V4A']}", file=sys.stderr)
        print(f"         ✅ Průtok:   {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
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
            
        print(f"🚀 Spouštím Megabad Scraper V16 pro {len(tasks)} produktů...", file=sys.stderr)
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
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                try: start = writer.sheets['Products_Tech'].max_row
                except: start = 0
                header = True if start == 0 else False
                df.to_excel(writer, sheet_name="Products_Tech", index=False, header=header, startrow=start)
            print("✅ Hotovo. Data uložena do Excelu.", file=sys.stderr)

if __name__ == "__main__":
    scraper = MegabadTechScraperV16()
    scraper.run()