import pandas as pd
import re
import sys
import time
import os
import urllib.parse
import datetime
import requests
import io
from playwright.sync_api import sync_playwright

try:
    import pdfplumber
except ImportError:
    print("❌ CHYBA: Chybí knihovna 'pdfplumber'.", file=sys.stderr)
    sys.exit(1)

class KaldeweiTechScraperV38:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.tech_cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]
        self.price_cols = [
            "Component_SKU", "Eshop_Source", "Found_Price_EUR", "Original_Price_EUR",
            "Price_Breakdown", "Product_URL", "Timestamp"
        ]

    def check_excel_access(self):
        if os.path.exists(self.excel_path):
            try:
                with open(self.excel_path, "a+"): pass
            except PermissionError:
                print(f"❌ ERROR: Excel '{self.excel_path}' je otevřený! Prosím zavřete ho.", file=sys.stderr)
                sys.exit(1)

    def get_tasks(self):
        try:
            df = pd.read_excel(self.excel_path, sheet_name="BOM_Definitions")
            tasks = []
            seen = set()
            for _, row in df.iterrows():
                name = str(row["Component_Name"]).strip()
                sku = str(row["Component_SKU"]).strip()
                if "kaldewei" in name.lower():
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except: return []

    # === OPRAVENÝ ČTECÍ MECHANISMUS CEN Z V34 ===
    def clean_price(self, text):
        if not text: return None
        clean_text = str(text).lower()
        if "spar" in clean_text or "sie sparen" in clean_text: return None
        if "monat" in clean_text or "rate" in clean_text or "mtl" in clean_text: return None 
        if "%" in clean_text or "rabatt" in clean_text: return None
        
        clean_text = clean_text.replace("ihr preis", "").replace("preis", "").replace("stückpreis", "")
        clean_text = clean_text.replace("€", "").replace("eur", "").replace("ab", "").replace("von", "").replace("*", "").strip()
        clean_text = clean_text.replace("uvp", "").replace("statt", "").replace("doporučená", "")

        # Podpora pro formát 1.115,03 i 285,60
        if re.search(r'\d{1,3}\.\d{3},\d{2}', clean_text): 
            clean_text = clean_text.replace(".", "").replace(",", ".")
        elif re.search(r'\d+,\d{2}', clean_text): 
            clean_text = clean_text.replace(".", "").replace(",", ".")
            
        match = re.search(r'(\d+\.?\d*)', clean_text)
        if match:
            try: return float(match.group(1))
            except: return None
        return None

    def extract_price_ultimate(self, page):
        try:
            meta_price = page.locator("meta[itemprop='price']").first.get_attribute("content")
            if meta_price:
                val = float(meta_price.replace(",", "."))
                if val > 10: return val 
        except: pass

        try:
            scripts = page.locator("script[type='application/ld+json']").all()
            for s in scripts:
                content = s.text_content()
                if '"price":' in content:
                    match = re.search(r'"price":\s*"?(\d+\.?\d*)"?', content)
                    if match:
                        val = float(match.group(1))
                        if val > 10: return val
        except: pass

        selectors = [
            "[data-testid='price-main']", ".price-large", ".product-detail-price__price", 
            ".current-price-container", ".price--content", ".price__amount", "#product-price", ".final-price",
            "div.product-detail-price-container span.current-price" 
        ]
        
        main_area = page.locator("main, .product-detail, #content").first
        if main_area.count() == 0: main_area = page.locator("body")

        for sel in selectors:
            if main_area.locator(sel).count() > 0:
                txt = main_area.locator(sel).first.text_content()
                val = self.clean_price(txt)
                if val and val > 10: return val
        return None

    def extract_original_price(self, page, selling_price):
        if not selling_price: return None
        
        old_price_selectors = [
            ".old-price", ".price-strike", ".price--line-through", 
            ".product-price--crossed", ".uvp-price", ".regular-price"
        ]
        
        main_area = page.locator("main, .product-detail, #content").first
        if main_area.count() == 0: main_area = page.locator("body")

        for sel in old_price_selectors:
            if main_area.locator(sel).count() > 0:
                txt = main_area.locator(sel).first.text_content()
                val = self.clean_price(txt)
                if val and val > selling_price: return val

        # BEZPEČNÝ REGEX PRO UVP Z V34
        try:
            text = main_area.inner_text()
            patterns = [
                r'UVP.*?(\d{1,3}[.,]?\d{0,3}[.,]\d{2})', 
                r'statt.*?(\d{1,3}[.,]?\d{0,3}[.,]\d{2})', 
                r'Bisher.*?(\d{1,3}[.,]?\d{0,3}[.,]\d{2})'
            ]
            for pat in patterns:
                matches = re.findall(pat, text, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    val = self.clean_price(m)
                    if val and val > selling_price + 2: return val
        except: pass
        return None

    def analyze_text_data(self, text, variant="regular"):
        data = {}
        clean_text = text.replace('\n', ' ').replace('\r', ' ')
        clean_text = re.sub(r'\s+', ' ', clean_text)
        lower_text = clean_text.lower()

        if variant == "flat":
            data["Vertical_Outlet_Option"] = "DN 40"
            data["Cert_EN1253"] = "No (low height)"
        else:
            data["Vertical_Outlet_Option"] = "DN 50"
            if "1253" in lower_text and "din" in lower_text: data["Cert_EN1253"] = "Yes"

        match_flow_min = re.search(r'(\d+(?:[.,]\d+)?)\s*l/min', clean_text, re.IGNORECASE)
        match_flow_sec = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', clean_text, re.IGNORECASE)
        if match_flow_sec:
            val = float(match_flow_sec.group(1).replace(',', '.'))
            if 0.2 <= val <= 2.5: data["Flow_Rate_l_s"] = f"{val} l/s"

        h_text = re.sub(r'Sperrwasserhöhe.{0,20}\d+\s*(?:mm)?', '', clean_text, flags=re.IGNORECASE)
        match_range = re.search(r'(?:Einbautiefe|Bauhöhe|Einbauhöhe|Gesamthöhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+)\s*mm', h_text, re.IGNORECASE)
        if match_range: data["Height_Adjustability"] = f"{match_range.group(1).replace(' ', '')} mm"

        if "1.4404" in lower_text or "v4a" in lower_text or "316" in lower_text: data["Material_V4A"] = "Edelstahl V4A (1.4404)"
        elif "1.4301" in lower_text or "v2a" in lower_text or "304" in lower_text: data["Material_V4A"] = "Edelstahl V2A (1.4301)"
        elif "stahlemail" in lower_text or "kaldewei stahl" in lower_text: data["Material_V4A"] = "Stahlemail"

        fleece_keywords = ["dichtmanschette", "dichtband", "abdichtungsset", "dichtvlies", "werkseitig angebracht", "abdichtung", "wps", "dichtsystem"]
        if any(x in lower_text for x in fleece_keywords) or ("dicht" in lower_text and "werkseitig" in lower_text):
            data["Sealing_Fleece"] = "Yes"
        
        return data

    def download_and_read_pdf(self, pdf_url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(pdf_url, headers=headers, timeout=15)
            if response.status_code == 200:
                full_text = ""
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    for page in pdf.pages[:3]:
                        txt = page.extract_text()
                        if txt: full_text += txt + " "
                return full_text
        except: pass
        return ""

    # --- SIFONY ---
    def get_megabad_component_price(self, page, query, must_have_in_url=None, must_not_have_in_url=None):
        print(f"         🔍 Hledám SIFON: '{query}'", file=sys.stderr)
        try:
            page.goto("https://www.megabad.com/", timeout=30000)
            time.sleep(2)
            try: page.locator(".cmpboxbtnyes, button:has-text('Zustimmen')").first.click(timeout=1000)
            except: pass
            
            inputs = page.locator("input#search, input[name='q'], input[type='search']").all()
            if not inputs:
                try: page.locator(".search-toggle, .header-search-icon").first.click(timeout=1000); time.sleep(1)
                except: pass
                inputs = page.locator("input[type='text']").all()
            
            for inp in inputs:
                if inp.is_visible():
                    inp.click(force=True)
                    inp.fill(query)
                    page.keyboard.press("Enter")
                    break

            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            links = page.locator("a").all()
            target_href = None
            
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and ("-a-" in href or "/product/" in href) and "-k-" not in href:
                        href_lower = href.lower()
                        if "kaldewei" in href_lower:
                            if must_not_have_in_url:
                                skip = False
                                for bad_word in must_not_have_in_url:
                                    if bad_word.lower() in href_lower: skip = True
                                if skip: continue
                            if must_have_in_url:
                                skip = False
                                for good_word in must_have_in_url:
                                    if good_word.lower() not in href_lower: skip = True
                                if skip: continue

                            target_href = href
                            break
                except: pass

            if target_href:
                if target_href.startswith("/"): target_href = "https://www.megabad.com" + target_href
                print(f"            🚀 Přecházím na detail: {target_href.split('/')[-1]}", file=sys.stderr)
                page.goto(target_href, timeout=30000)
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                
                p_val = self.extract_price_ultimate(page)
                o_val = self.extract_original_price(page, p_val)
                return p_val, o_val
        except: pass
        return None, None

    # 🔴 FINÁLNÍ TOP-DOWN SBĚRAČ KRYTŮ (Kombinace V34 sběru a neprůstřelného JS)
    def scrape_all_covers_forcefully(self, page):
        cover_prices = {}
        cover_uvp = {}
        colors_to_find = ["Edelstahl", "Alpinweiß", "Schwarz", "Champagner", "Graphit"]
        
        query = "Kaldewei FlowLine Zero 1200 Duschrinne 120 cm"
        print(f"\n         🔍 Hromadné hledání krytů: '{query}'", file=sys.stderr)
        
        page.goto("https://www.megabad.com/", timeout=30000)
        time.sleep(2)
        try: page.locator(".cmpboxbtnyes, button:has-text('Zustimmen')").first.click(timeout=1000)
        except: pass
        
        inputs = page.locator("input#search, input[name='q'], input[type='search']").all()
        if not inputs:
            try: page.locator(".search-toggle, .header-search-icon").first.click(timeout=1000); time.sleep(1)
            except: pass
            inputs = page.locator("input[type='text']").all()
        
        for inp in inputs:
            if inp.is_visible():
                inp.click(force=True)
                inp.fill(query)
                page.keyboard.press("Enter")
                break
                
        page.wait_for_load_state("domcontentloaded")
        time.sleep(3)
        
        links = page.locator("a").all()
        target_hrefs = []
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and ("-a-" in href or "/product/" in href) and "-k-" not in href:
                    if "flowline" in href.lower() and "set" not in href.lower():
                        if href not in target_hrefs:
                            target_hrefs.append(href)
            except: pass
            
        print(f"            🔎 Nalezeno {len(target_hrefs)} odkazů na kryty. Jdu je otevřít...", file=sys.stderr)
        
        for href in target_hrefs[:30]:
            if not colors_to_find: break
            
            full_url = href if href.startswith("http") else "https://www.megabad.com" + href
            try:
                page.goto(full_url, timeout=30000)
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)
                
                try: h1 = page.locator("h1").first.inner_text().lower()
                except: h1 = ""
                
                if "set" in h1:
                    print(f"            ⏭️ Přeskakuji SET: {h1.strip()}", file=sys.stderr)
                    continue
                if not ("1200" in h1 or "120" in h1):
                    print(f"            ⏭️ Špatná délka (není 1200mm): {h1.strip()}", file=sys.stderr)
                    continue
                
                p_val = self.extract_price_ultimate(page)
                o_val = self.extract_original_price(page, p_val)
                if not p_val: 
                    print(f"            ⚠️ Stránka načtena, ale CENU SE NEPODAŘILO PŘEČÍST.", file=sys.stderr)
                    continue
                
                # 🔴 JAVASCRIPT PRO BEZPEČNOU EXTRAKCI BARVY (Nečte Related Products!)
                js_code = """() => {
                    let texts = [];
                    // 1. Meta Title
                    let t = document.querySelector('title'); if(t) texts.push(t.innerText);
                    // 2. H1 a Breadcrumb
                    let h1 = document.querySelector('h1'); if(h1) texts.push(h1.innerText);
                    let bc = document.querySelector('.breadcrumb'); if(bc) texts.push(bc.innerText);
                    // 3. Aktivní tlačítka z konfigurátoru
                    let active = document.querySelector('input[type="radio"]:checked + label, .product-detail-configurator-option-label.is-display-text, .is-active');
                    if(active) texts.push(active.innerText);
                    // 4. Tabulka specifikací
                    let props = document.querySelectorAll('.product-detail-properties-table tr, .product-detail-properties tr, dl.properties, .product-attributes');
                    props.forEach(p => texts.push(p.innerText));
                    // 5. JSON-LD Backend data
                    let scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    scripts.forEach(s => {
                        try {
                            let data = JSON.parse(s.innerText);
                            if (data.name) texts.push(data.name);
                            if (data.color) texts.push(data.color);
                        } catch(e) {}
                    });
                    return texts.join(' ').toLowerCase();
                }"""
                
                try: text_to_check = page.evaluate(js_code)
                except: text_to_check = h1
                
                found_col = None
                
                if "schwarz" in text_to_check and "Schwarz" in colors_to_find: found_col = "Schwarz"
                elif "alpin" in text_to_check and "Alpinweiß" in colors_to_find: found_col = "Alpinweiß"
                elif "champag" in text_to_check and "Champagner" in colors_to_find: found_col = "Champagner"
                elif "graphit" in text_to_check and "Graphit" in colors_to_find: found_col = "Graphit"
                elif ("edelstahl" in text_to_check or "nerez" in text_to_check or "gebürstet" in text_to_check) and "Edelstahl" in colors_to_find: 
                    found_col = "Edelstahl"
                    
                # Extrémní pojistka: Nerez dáme, jen pokud jsme si 100% jistí, že tam není jiná barva
                if not found_col and "Edelstahl" in colors_to_find and not any(c in text_to_check for c in ["schwarz", "alpin", "champag", "graphit"]):
                    found_col = "Edelstahl"

                if found_col:
                    cover_prices[found_col] = p_val
                    cover_uvp[found_col] = o_val if o_val else p_val
                    colors_to_find.remove(found_col)
                    print(f"            🚀 BINGO! Načten kryt {found_col}: {p_val} € (UVP: {o_val})", file=sys.stderr)
                else:
                    print(f"            ⏭️ Toto je jiná barva, nebo už ji máme (Nadpis: {h1[:40]}...). Jdu na další...", file=sys.stderr)
                    
            except Exception as e:
                print(f"            ⚠️ Chyba při načítání odkazu: {e}", file=sys.stderr)
            
        for c in colors_to_find:
            print(f"            ⚠️ Barva '{c}' nebyla nalezena ve výsledcích.", file=sys.stderr)

        return cover_prices, cover_uvp

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        if not tasks: return
            
        print(f"🚀 Spouštím Kaldewei Tech Scraper V38 (The Golden Mean)...", file=sys.stderr)
        tech_results = []
        price_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám: {sku} - {raw_name} (Délka: 1200mm)\n{'='*50}", file=sys.stderr)

                # --- 1. KALDEWEI.DE (Stahování tech dat) ---
                print(f"         🛒 Kaldewei.de: Analyzuji technická data...", file=sys.stderr)
                pdf_url, full_text = "N/A", ""
                target_url = "https://www.kaldewei.de/produkte/kaldewei-flow/" if "flow" in raw_name.lower() else f"https://www.kaldewei.de/suche/?q={sku}"
                
                try:
                    page.goto(target_url, timeout=30000)
                    time.sleep(2)
                    try: page.locator("button:has-text('Alle akzeptieren')").click(timeout=1000)
                    except: pass
                    
                    web_text = page.evaluate("document.body.innerText")
                    pdf_links = page.locator("a[href$='.pdf']").all()
                    for link in pdf_links:
                        href = link.get_attribute("href")
                        if href and ("datenblatt" in href.lower() or "montage" in href.lower()):
                            pdf_url = href if href.startswith("http") else "https://www.kaldewei.de" + href
                            full_text = web_text + " " + self.download_and_read_pdf(pdf_url)
                            break
                    if not full_text: full_text = web_text
                except: pass

                for variant in ["regular", "flat"]:
                    extracted_data = {
                        "Component_SKU": f"{sku}_{variant.upper()}",
                        "Manufacturer": "Kaldewei", "Tech_Source_URL": target_url, "Datasheet_URL": pdf_url,
                        "Flow_Rate_l_s": "N/A", "Material_V4A": "N/A", "Cert_EN1253": "No", "Cert_EN18534": "No",
                        "Height_Adjustability": "N/A", "Vertical_Outlet_Option": "N/A", "Sealing_Fleece": "No", "Color_Count": 5
                    }
                    analyzed = self.analyze_text_data(full_text, variant=variant)
                    extracted_data.update({k: v for k, v in analyzed.items() if v})
                    tech_results.append(extracted_data)

                # --- 2. MEGABAD.COM ---
                print(f"         🛒 Megabad.com: Získávám ceny odtoků...", file=sys.stderr)
                
                base_prices = {}
                base_uvp = {}
                
                drains = {
                    "Regular": {"q": "Kaldewei FlowDrain horizontal regular", "must": ["flowdrain", "regular"], "excl": ["point", "flat"]},
                    "Flat": {"q": "Kaldewei Ablaufgarnitur FlowDrain flat", "must": ["flowdrain", "flat"], "excl": ["point", "regular"]}
                }
                
                for key, config in drains.items():
                    p_val, o_val = self.get_megabad_component_price(page, config["q"], must_have_in_url=config["must"], must_not_have_in_url=config["excl"])
                    if p_val:
                        base_prices[key] = p_val
                        base_uvp[key] = o_val if o_val else p_val
                        print(f"            ✅ Sifon {key}: {p_val} € (UVP: {o_val})", file=sys.stderr)
                    else:
                        print(f"            ⚠️ Sifon {key} nenalezen.", file=sys.stderr)

                cover_prices, cover_uvp = self.scrape_all_covers_forcefully(page)

                # --- 3. MATEMATIKA ---
                print(f"\n         🧮 Skládám kompletní sety...", file=sys.stderr)
                for drain_key in drains.keys():
                    if drain_key not in base_prices: continue
                    
                    for color in ["Edelstahl", "Alpinweiß", "Schwarz", "Champagner", "Graphit"]:
                        if color not in cover_prices: continue
                        
                        total_price = round(base_prices[drain_key] + cover_prices[color], 2)
                        
                        total_uvp = None
                        if base_uvp.get(drain_key) and cover_uvp.get(color):
                            total_uvp = round(base_uvp[drain_key] + cover_uvp[color], 2)

                        breakdown_label = f"System (FlowDrain {drain_key} + {color})"
                        print(f"            💰 {breakdown_label}: {total_price} € (UVP: {total_uvp})", file=sys.stderr)

                        price_results.append({
                            "Component_SKU": sku, 
                            "Eshop_Source": "Megabad.com",
                            "Found_Price_EUR": total_price, 
                            "Original_Price_EUR": total_uvp,
                            "Price_Breakdown": breakdown_label,
                            "Product_URL": "Combined Calculation", 
                            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        })

            browser.close()

        # Uložení
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if tech_results:
                df = pd.DataFrame(tech_results)[self.tech_cols]
                try: 
                    old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    for s in df['Component_SKU'].str.split('_').str[0].unique():
                        old = old[~old['Component_SKU'].astype(str).str.startswith(s)]
                    df = pd.concat([old, df], ignore_index=True)
                except: pass
                df.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if price_results:
                df_p = pd.DataFrame(price_results)[self.price_cols]
                try:
                    old_p = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    for _, row in df_p.iterrows():
                        mask = (old_p['Component_SKU'].astype(str) == str(row['Component_SKU'])) & \
                               (old_p['Eshop_Source'] == row['Eshop_Source']) & \
                               (old_p['Price_Breakdown'] == row['Price_Breakdown'])
                        old_p = old_p[~mask]
                    df_p = pd.concat([old_p, df_p], ignore_index=True)
                except: pass
                df_p.to_excel(writer, sheet_name="Market_Prices", index=False)

        print("\n✅ Hotovo! Kaldewei Master Data uložena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = KaldeweiTechScraperV38()
    scraper.run()