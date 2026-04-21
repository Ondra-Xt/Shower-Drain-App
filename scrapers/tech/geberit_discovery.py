from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import os
import sys

class GeberitDiscoveryV19_1:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.target_url = "https://catalog.geberit.de/de-DE/systems/CH3_3294141/products" 
        
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]

    def ensure_excel_exists(self):
        if not os.path.exists(self.excel_path):
            print(f"⚠️ Excel soubor {self.excel_path} nebyl nalezen.", file=sys.stderr)

    def run(self):
        self.ensure_excel_exists()
        discovered_products = []

        print("\n" + "="*60)
        print("🚀 Spouštím Geberit Discovery V19.1 (The Syntax Fix)")
        print("="*60 + "\n", file=sys.stderr)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            print(f"⏳ Otevírám katalog Geberit...", file=sys.stderr)
            page.goto(self.target_url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

            # --- TVRDÝ COOKIE BUSTER ---
            print("🍪 Odstraňuji Cookies...", file=sys.stderr)
            try:
                page.mouse.wheel(0, 300)
                time.sleep(1)
                cookie_selectors = [
                    "button:has-text('Alle Einwilligungen erteilen')",
                    "button:has-text('Alle akzeptieren')",
                    "button#cmpbntyestxt"
                ]
                for sel in cookie_selectors:
                    if page.locator(sel).is_visible():
                        page.locator(sel).first.click(timeout=2000)
                        break
            except: pass

            print("🔎 Sbírám odkazy na produkty...", file=sys.stderr)
            js_code_links = "() => [...new Set(Array.from(document.querySelectorAll('a')).map(a => a.href).filter(href => href.includes('/product/PRO_')))]"
            product_urls = page.evaluate(js_code_links)
            
            if not product_urls:
                print("   ❌ Žádné odkazy nebyly nalezeny.", file=sys.stderr)
                browser.close(); return
                
            print(f"   📌 Nalezeno {len(product_urls)} odkazů. Jdeme na detaily!\n")

            for url in product_urls: 
                print(f"   ➡️ Otevírám: {url.split('/')[-1]}", file=sys.stderr)
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)
                    
                    # Scroll dolů
                    for _ in range(3): page.mouse.wheel(0, 800); time.sleep(0.3)
                    
                    # OPRAVA CHYBY: Rozkliknutí "harmonik" (Technické údaje) pomocí oddělených try/except bloků
                    try:
                        if page.locator(".accordion-header").count() > 0:
                            for header in page.locator(".accordion-header").all():
                                if header.is_visible(): header.click(timeout=500)
                    except: pass
                    
                    try:
                        if page.locator("text='Technische Daten'").count() > 0:
                            page.locator("text='Technische Daten'").first.click(timeout=500)
                    except: pass

                    try:
                        if page.locator("text='Eigenschaften'").count() > 0:
                            page.locator("text='Eigenschaften'").first.click(timeout=500)
                    except: pass
                    
                    time.sleep(0.5)

                    # NAČTENÍ TABULEK (<dl>, <tr>, atd.) A TEXTU PŘES JS
                    js_extractor = """() => {
                        let result = { h1: "", sku: "", fullText: document.body.innerText.toLowerCase(), properties: {} };
                        
                        let h1 = document.querySelector('h1');
                        if (h1) result.h1 = h1.innerText.trim();

                        let skuMatch = document.body.innerText.match(/(\\d{3}\\.\\d{3}\\.[a-zA-Z0-9]{2,3}\\.\\d|\\d{3}\\.\\d{3}\\.\\d{2}\\.\\d)/);
                        if (skuMatch) result.sku = skuMatch[1];

                        // Hlavní lovec tabulek Vlastností/Technických dat
                        let items = document.querySelectorAll('dl > div, dl > dt, tr, .feature, .attribute');
                        
                        let currentKey = "";
                        for(let item of items) {
                            let text = item.innerText.trim().toLowerCase();
                            
                            let cells = item.querySelectorAll('td, th, dd, dt, div');
                            if(cells.length === 2) {
                                result.properties[cells[0].innerText.trim().toLowerCase()] = cells[1].innerText.trim().toLowerCase();
                            } else if (item.tagName === 'DT') {
                                currentKey = text;
                            } else if (item.tagName === 'DD' && currentKey) {
                                result.properties[currentKey] = text;
                                currentKey = "";
                            } else if (text.includes(':')) {
                                let parts = text.split(':');
                                result.properties[parts[0].trim()] = parts.slice(1).join(':').trim();
                            } else if (text.includes('\\n')) {
                                let parts = text.split('\\n');
                                if (parts.length >= 2) result.properties[parts[0].trim()] = parts.slice(1).join(' ').trim();
                            }
                        }
                        return result;
                    }"""
                    
                    extracted = page.evaluate(js_extractor)
                    
                    h1_text = extracted.get("h1", "Geberit Produkt")
                    sku = extracted.get("sku", "")
                    full_text = extracted.get("fullText", "")
                    properties = extracted.get("properties", {})

                    if not sku: continue

                    is_siphon = "rohbauset" in h1_text.lower() or "154.15" in sku
                    typ_produktu = "Sifon (Rohbauset)" if is_siphon else "Kryt (Rošt)"

                    print(f"      ✅ Načteno: {h1_text[:40]}... (SKU: {sku}) - [{typ_produktu}]", file=sys.stderr)

                    record = {
                        "Component_SKU": sku, "Manufacturer": "Geberit", "Product_Name": h1_text,
                        "Tech_Source_URL": url, "Datasheet_URL": "", "Flow_Rate_l_s": "",
                        "Material_V4A": "", "Color": "", "Cert_EN1253": "No", "Cert_EN18534": "No",
                        "Height_Adjustability": "", "Vertical_Outlet_Option": "", "Sealing_Fleece": "No",
                        "Color_Count": "1", "Length_mm": "", "Is_Cuttable": "No",
                        "Evidence_Text": full_text[:150].replace('\n', ' ')
                    }

                    # =========================================================
                    # 1. SIFONY (ROHBAUSETS)
                    # =========================================================
                    if is_siphon:
                        # PRŮTOK
                        for k, v in properties.items():
                            if "ablauf" in k:
                                m_flow = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', v)
                                if m_flow: record["Flow_Rate_l_s"] = f"{m_flow.group(1).replace(',', '.')} l/s"
                        
                        if not record["Flow_Rate_l_s"]:
                            m_flow_raw = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', full_text)
                            if m_flow_raw:
                                val = float(m_flow_raw.group(1).replace(',', '.'))
                                if 0.2 < val < 2.0: record["Flow_Rate_l_s"] = f"{val} l/s"

                        # TRUBKA (DN)
                        for k, v in properties.items():
                            if "d, " in k or "ø" in k or k == "d":
                                m_dn = re.search(r'(\d{2})', v)
                                if m_dn: record["Vertical_Outlet_Option"] = f"DN {m_dn.group(1)}"
                        
                        if not record["Vertical_Outlet_Option"]:
                            if "dn 50" in full_text or "d=50" in full_text or "d=50mm" in full_text: record["Vertical_Outlet_Option"] = "DN 50"
                            elif "dn 40" in full_text or "d=40" in full_text or "d=40mm" in full_text: record["Vertical_Outlet_Option"] = "DN 40"

                        # VÝŠKA
                        for k, v in properties.items():
                            if "estrich" in k or "bauhöhe" in k or k == "h":
                                m_h = re.search(r'(\d{2,3})', v)
                                if m_h: record["Height_Adjustability"] = f"{m_h.group(1)} mm"
                        if not record["Height_Adjustability"]:
                            m_h_raw = re.search(r'(?:estrichhöhe|bauhöhe|h\s*=).*?(\d{2,3})\s*mm', full_text)
                            if m_h_raw: record["Height_Adjustability"] = f"{m_h_raw.group(1)} mm"

                    # =========================================================
                    # 2. KRYTY (ROŠTY)
                    # =========================================================
                    else:
                        # DÉLKA a IS_CUTTABLE
                        for k, v in properties.items():
                            if "länge" in k or "l " in k or k == "l":
                                m_range = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})', v)
                                if m_range:
                                    record["Length_mm"] = str(int(m_range.group(2)) * 10)
                                    record["Is_Cuttable"] = "Yes"
                                else:
                                    m_single = re.search(r'(\d{2,3})', v)
                                    if m_single: 
                                        record["Length_mm"] = str(int(m_single.group(1)) * 10)
                                        record["Is_Cuttable"] = "No"
                        
                        if not record["Length_mm"]: 
                            m_len_text = re.search(r'(\d{2,3})\s*[-–]\s*(\d{2,3})\s*cm', full_text)
                            if m_len_text:
                                record["Length_mm"] = str(int(m_len_text.group(2)) * 10)
                                record["Is_Cuttable"] = "Yes"
                            else:
                                m_h1 = re.search(r'(\d{2,3})\s*cm', h1_text.lower())
                                if m_h1: record["Length_mm"] = str(int(m_h1.group(1)) * 10)

                        # BARVA A MATERIÁL (Základní tabulka Farbe / Oberfläche)
                        farbe_text = ""
                        for k, v in properties.items():
                            if "farbe" in k or "oberfläche" in k:
                                farbe_text = v
                                break
                        
                        if farbe_text:
                            if "schwarz" in farbe_text: record["Color"] = "Schwarz"
                            elif "champagner" in farbe_text: record["Color"] = "Champagner"
                            elif "gebürstet" in farbe_text or "poliert" in farbe_text or "edelstahl" in farbe_text: 
                                record["Color"] = "Edelstahl (Gebürstet/Poliert)"
                        else:
                            if "schwarz chromiert" in full_text: record["Color"] = "Schwarz"
                            elif "champagner" in full_text: record["Color"] = "Champagner"
                            else: record["Color"] = "Edelstahl (Gebürstet/Poliert)" # Default

                        # Materiál (V4A)
                        if "v4a" in full_text or "1.4404" in full_text: record["Material_V4A"] = "Edelstahl V4A"
                        elif "edelstahl" in full_text or "nerez" in full_text: record["Material_V4A"] = "Edelstahl V2A"

                    # =========================================================
                    # SPOLEČNÉ (Certifikáty, Rouno)
                    # ==========================================
                    if "en 1253" in full_text: record["Cert_EN1253"] = "Yes"
                    if "dichtvlies" in full_text or "werkseitig" in full_text: record["Sealing_Fleece"] = "Yes"

                    # VÝPIS DO TERMINÁLU
                    found = []
                    if record["Flow_Rate_l_s"]: found.append(f"Průtok: {record['Flow_Rate_l_s']}")
                    if record["Height_Adjustability"]: found.append(f"Výška: {record['Height_Adjustability']}")
                    if record["Vertical_Outlet_Option"]: found.append(f"Trubka: {record['Vertical_Outlet_Option']}")
                    if record["Length_mm"]: found.append(f"Délka: {record['Length_mm']} mm (Řez: {record['Is_Cuttable']})")
                    if record["Material_V4A"]: found.append(f"Mat: {record['Material_V4A']}")
                    if record["Color"]: found.append(f"Barva: {record['Color']}")
                    
                    if found: print(f"         ⚙️ Získáno: {', '.join(found)}", file=sys.stderr)
                    else: print(f"         ⚠️ Data nenalezena.", file=sys.stderr)
                    
                    discovered_products.append(record)
                    
                except Exception as e:
                    print(f"      ❌ Chyba: {e}", file=sys.stderr)

            browser.close()
        
        print("\n" + "="*60)
        print(f"✅ Dokončeno. Zpracováno {len(discovered_products)} produktů.")
        print("="*60 + "\n", file=sys.stderr)
        self.save_to_excel(discovered_products)

    def save_to_excel(self, products):
        if not products: return
        print(f"💾 Ukládám do Excelu...", file=sys.stderr)
        
        df_old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
        if 'Color' not in df_old.columns: df_old['Color'] = ""
            
        df_new = pd.DataFrame(products)
        if not df_old.empty and 'Manufacturer' in df_old.columns:
            df_old = df_old[df_old['Manufacturer'] != 'Geberit']
            
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            
        print("✅ Hotovo!", file=sys.stderr)

if __name__ == "__main__":
    scraper = GeberitDiscoveryV19_1()
    scraper.run()