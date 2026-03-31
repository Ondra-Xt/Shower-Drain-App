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

# Kontrola instalace
try:
    import pdfplumber
except ImportError:
    print("❌ CHYBA: Chybí knihovna 'pdfplumber'. Nainstalujte ji příkazem: python -m pip install pdfplumber requests", file=sys.stderr)
    sys.exit(1)

class ViegaTechScraperV16:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.tech_cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
        ]
        self.price_cols = [
            "Component_SKU", "Eshop_Source", "Found_Price_EUR", 
            "Price_Breakdown", "Product_URL", "Timestamp"
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
            seen = set()
            for _, row in df.iterrows():
                name = str(row["Component_Name"]).strip()
                sku = str(row["Component_SKU"]).strip()
                if "viega" in name.lower():
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except Exception as e:
            print(f"⚠️ Chyba při čtení Excelu: {e}", file=sys.stderr)
            return []

    # --- MOZEK Z VERZE 15 (Chytrá analýza čísel) ---
    def analyze_text_data(self, text):
        """Vytáhne data z textu pomocí vylepšených regexů."""
        data = {}
        clean_text = text.replace('\n', ' ').replace('\r', ' ')
        clean_text = re.sub(r'\s+', ' ', clean_text)

        # 1. PRŮTOK (Hledá AL 10 / AL 20)
        match_al20 = re.search(r'(?:AL\s*20|Ablaufleistung.*?20\s*mm)[^\d]{0,60}?(\d+[,.]\d+)', clean_text, re.IGNORECASE)
        match_al10 = re.search(r'(?:AL\s*10|Ablaufleistung.*?10\s*mm)[^\d]{0,60}?(\d+[,.]\d+)', clean_text, re.IGNORECASE)
        
        if match_al20:
            data["Flow_Rate_l_s"] = f"{match_al20.group(1).replace(',', '.')} l/s (20mm)"
        elif match_al10:
            data["Flow_Rate_l_s"] = f"{match_al10.group(1).replace(',', '.')} l/s (10mm)"
        else:
            # Fallback
            matches = re.findall(r'(\d+[.,]\d+)\s*(?:l/s|l/min)', clean_text)
            valid = [float(m.replace(',', '.')) for m in matches if 0.3 <= float(m.replace(',', '.')) <= 2.5]
            if valid: data["Flow_Rate_l_s"] = f"{max(valid)} l/s"

        # 2. VÝŠKA (Hledá "von...bis" nebo rozsah)
        h_text = re.sub(r'Sperrwasserhöhe.{0,20}\d+\s*(?:mm)?', '', clean_text, flags=re.IGNORECASE)
        
        match_range = re.search(r'(?:Bauhöhe|Einbaumaß|Höhe)[^\d]{0,60}?(\d+\s*[-–]\s*\d+)', h_text, re.IGNORECASE)
        if match_range:
             data["Height_Adjustability"] = f"{match_range.group(1).replace(' ', '')} mm"
        else:
            match_von = re.search(r'(?:Bauhöhe|Einbaumaß).*?von\s*(\d{2,3})', h_text, re.IGNORECASE)
            match_bis = re.search(r'(?:Bauhöhe|Einbaumaß).*?bis\s*(\d{2,3})', h_text, re.IGNORECASE)
            if match_von and match_bis:
                data["Height_Adjustability"] = f"{match_von.group(1)}-{match_bis.group(1)} mm"

        # 3. ODTOK (DN)
        match_dn = re.search(r'DN\s*(\d+(?:\s*/\s*\d+)?)', clean_text)
        if match_dn:
            data["Vertical_Outlet_Option"] = f"DN {match_dn.group(1).replace(' ', '')}"

        # 4. MATERIÁL
        lower = clean_text.lower()
        if "1.4404" in lower or "v4a" in lower: data["Material_V4A"] = "Edelstahl V4A"
        elif "1.4301" in lower or "v2a" in lower: data["Material_V4A"] = "Edelstahl V2A"
        elif "polypropylen" in lower or "kunststoff" in lower: data["Material_V4A"] = "Kunststoff"

        return data

    def download_and_read_pdf(self, pdf_url):
        print(f"         📥 Stahuji a analyzuji PDF: {pdf_url} ...", file=sys.stderr)
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(pdf_url, headers=headers, timeout=15)
            if response.status_code == 200:
                full_text = ""
                with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                    # Čteme první 4 strany
                    for page in pdf.pages[:4]:
                        txt = page.extract_text()
                        if txt: full_text += txt + " "
                        # Extrakt tabulek (klíčové pro Viegu!)
                        tables = page.extract_tables()
                        for table in tables:
                            for row in table:
                                clean_row = [str(c) for c in row if c]
                                full_text += " | ".join(clean_row) + " "
                
                print(f"         📝 PDF úspěšně přečteno ({len(full_text)} znaků).", file=sys.stderr)
                return full_text
            return ""
        except Exception as e:
            print(f"         ⚠️ Chyba PDF: {e}", file=sys.stderr)
            return ""

    def extract_price(self, page):
        try:
            content = page.locator('meta[itemprop="price"]').first.get_attribute('content')
            if content: return float(content.replace(',', '.'))
        except: pass
        try:
            texts = page.locator('.product-detail-price, .price, .current-price').all_inner_texts()
            for t in texts:
                match = re.search(r'(\d{1,4}[.,]\d{2})', t)
                if match: return float(match.group(1).replace(',', '.'))
        except: pass
        return "N/A"

    def destroy_cookie_banners(self, page):
        try:
            page.evaluate("""
                const banners = document.querySelectorAll('#cc--main, .cookiebot, .cc-window, #cmpbox, #onetrust-consent-sdk');
                banners.forEach(el => el.remove());
            """)
        except: pass

    # --- MOTOR Z VERZE 13 (Spolehlivá navigace) ---
    def search_shops_stealth(self, page, sku, raw_name):
        clean_name = re.sub(r'Viega|Advantix|Vario', '', raw_name, flags=re.IGNORECASE).strip()
        sku_clean = sku.replace(' ', '')
        queries = list(dict.fromkeys([sku, sku_clean, clean_name]))
        queries = [q for q in queries if len(q) > 2]
        
        shops = [
            {
                "name": "Viega.de",
                "url_template": "https://www.viega.de/de/Suche.html?q={}",
                "cookie_sel": "button#onetrust-accept-btn-handler"
            },
            {
                "name": "Megabad.com",
                "url_template": "https://www.megabad.com/suche?q={}",
                "cookie_sel": ".cmpboxbtnyes"
            }
        ]

        for shop in shops:
            for query in queries:
                print(f"         🛒 {shop['name']}: Napřímo vyhledávám '{query}'...", file=sys.stderr)
                try:
                    search_url = shop["url_template"].format(urllib.parse.quote(query))
                    response = page.goto(search_url, timeout=30000)
                    
                    if response and response.status in [403, 429]:
                        print(f"         🛑 {shop['name']} zablokoval přístup.", file=sys.stderr)
                        break

                    time.sleep(2)
                    try: page.locator(shop["cookie_sel"]).first.click(timeout=1500, force=True)
                    except: pass
                    self.destroy_cookie_banners(page)
                    page.wait_for_load_state("domcontentloaded")

                    # Detekce detailu
                    is_detail = False
                    if "viega" in shop["name"].lower() and ("/produkte/Katalog/" in page.url or "/artikel/" in page.url) and query in page.url:
                        is_detail = True
                    elif "megabad" in shop["name"].lower() and page.locator(".product-detail-price").count() > 0:
                        is_detail = True

                    if not is_detail:
                        links = page.locator("a").all()
                        target_href = None
                        for l in links:
                            if l.is_visible():
                                raw_href = l.get_attribute("href")
                                if not raw_href: continue
                                href = raw_href.lower()
                                text = l.inner_text().upper()
                                if any(x in href for x in ["bewertung", "img", "basket", "login", "tel:"]): continue
                                
                                # Logika výběru odkazu
                                if "viega" in shop["name"].lower():
                                    if ("/produkte/katalog/" in href or "/artikel/" in href or "/produkte/" in href):
                                        if query in text.replace(' ', '') or query in href:
                                            target_href = raw_href
                                            break
                                elif "megabad" in shop["name"].lower():
                                    if "/produkt" in href or "-a-" in href or "-p-" in href:
                                        target_href = raw_href
                                        break

                        if target_href:
                            print(f"         🚀 Odkaz na produkt nalezen! Přecházím na detail...", file=sys.stderr)
                            if not target_href.startswith("http"):
                                domain = "https://www.viega.de" if "viega" in shop["name"].lower() else "https://www.megabad.com"
                                target_href = domain.rstrip("/") + "/" + target_href.lstrip("/")
                            page.goto(target_href, timeout=20000)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                        else:
                            print(f"         ⚠️ Žádný konkrétní produktový odkaz nenalezen.", file=sys.stderr)
                            continue

                    # --- JSME NA DETAILU ---
                    self.destroy_cookie_banners(page)
                    found_price = self.extract_price(page)

                    # 1. Zkusíme data z webu
                    web_text = page.evaluate("document.body.innerText")
                    
                    # 2. Hledáme PDF (Scroll & Click z V13)
                    pdf_href = "N/A"
                    pdf_text_content = ""
                    
                    if "viega" in shop["name"].lower():
                        print(f"         🖱️ Scrolluji a hledám sekci 'Downloads'...", file=sys.stderr)
                        for i in range(1, 6):
                            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/5});")
                            time.sleep(0.3)
                        
                        print(f"         📂 Otevírám záložky...", file=sys.stderr)
                        buttons = page.locator("button:has-text('Downloads'), button:has-text('Download'), h3:has-text('Download'), .accordion-button").all()
                        for b in buttons:
                            try: 
                                if b.is_visible(): b.click(force=True, timeout=500); time.sleep(0.2)
                            except: pass

                        # Hledáme PDF odkazy
                        pdf_links = page.locator("a[href*='.pdf'], a[href*='data-sheets'], a:has-text('Datenblatt')").all()
                        for link in pdf_links:
                            raw_href = link.get_attribute("href")
                            if raw_href and ("data-sheets" in raw_href or "datenblatt" in raw_href.lower()) and "sicherheit" not in raw_href.lower():
                                if not raw_href.startswith("http"):
                                    raw_href = "https://www.viega.de" + raw_href
                                pdf_href = raw_href
                                print(f"         📄 Nalezeno PDF: {pdf_href}", file=sys.stderr)
                                # Stáhneme text z PDF
                                pdf_text_content = self.download_and_read_pdf(pdf_href)
                                break
                    
                    # 3. Analýza a návrat
                    # Analyzujeme text z PDF (pokud je), jinak z webu
                    final_text_to_analyze = pdf_text_content if pdf_text_content else web_text
                    
                    # Pokud máme alespoň nějaká data (cena nebo text), vracíme výsledek
                    return final_text_to_analyze, page.url, shop["name"], found_price, pdf_href

                except Exception as e:
                    print(f"         ⚠️ Chyba: {e}", file=sys.stderr)
                    
        return "", "N/A", "N/A", "N/A", "N/A"

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks: 
            print("⚠️ POZOR: Žádné úkoly Viega.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím Viega Tech Scraper V16 (V13 Engine + V15 Brain)...", file=sys.stderr)
        tech_results = []
        price_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám: {sku}\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku, "Manufacturer": "Viega",
                    "Tech_Source_URL": "N/A", "Datasheet_URL": "N/A",
                    "Flow_Rate_l_s": "N/A", "Material_V4A": "N/A",
                    "Cert_EN1253": "No", "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A", "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No", "Color_Count": 1
                }

                # Získání surového textu (z webu nebo PDF) a metadat
                content, url, eshop, price, pdf_url = self.search_shops_stealth(page, sku, raw_name)
                
                if content:
                    extracted_data["Tech_Source_URL"] = url
                    extracted_data["Datasheet_URL"] = pdf_url
                    
                    # Použití chytrého mozku na získaný text
                    analyzed_data = self.analyze_text_data(content)
                    extracted_data.update({k: v for k, v in analyzed_data.items() if v})
                    
                    # Fleece check (jednoduchý)
                    if any(x in content.lower() for x in ["vlies", "dichtband", "abdichtungsflansch"]):
                        extracted_data["Sealing_Fleece"] = "Yes"

                    # Uložení ceny
                    if price != "N/A":
                        price_results.append({
                            "Component_SKU": sku, "Eshop_Source": eshop,
                            "Found_Price_EUR": price, "Price_Breakdown": "Single",
                            "Product_URL": url, "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        })

                # Výpis
                print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Odtok:     {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                print(f"         ✅ Cena EUR:  {price}", file=sys.stderr)
                
                tech_results.append(extracted_data)

            browser.close()

        # Ukládání
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if tech_results:
                df = pd.DataFrame(tech_results)[self.tech_cols]
                try: 
                    old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    for sku in df['Component_SKU']:
                        old = old[old['Component_SKU'].astype(str) != str(sku)]
                    df = pd.concat([old, df], ignore_index=True)
                except: pass
                df.to_excel(writer, sheet_name="Products_Tech", index=False)
            
            if price_results:
                df_p = pd.DataFrame(price_results)[self.price_cols]
                try:
                    old_p = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    for _, row in df_p.iterrows():
                        old_p = old_p[~((old_p['Component_SKU'].astype(str) == str(row['Component_SKU'])) & (old_p['Eshop_Source'] == row['Eshop_Source']))]
                    df_p = pd.concat([old_p, df_p], ignore_index=True)
                except: pass
                df_p.to_excel(writer, sheet_name="Market_Prices", index=False)

        print("\n✅ Hotovo! Viega V16 (Final Fix) dokončena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = ViegaTechScraperV16()
    scraper.run()