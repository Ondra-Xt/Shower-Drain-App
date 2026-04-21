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

class KaldeweiTechScraperV13:
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
        except Exception as e:
            print(f"⚠️ Chyba při čtení Excelu: {e}", file=sys.stderr)
            return []

    # === IMPLANTOVÁNO Z VAŠEHO KÓDU ===
    def clean_price(self, text):
        if not text: return None
        clean_text = text.lower()
        if "spar" in clean_text or "sie sparen" in clean_text: return None
        if "monat" in clean_text or "rate" in clean_text: return None 
        
        clean_text = clean_text.replace("ihr preis", "").replace("preis", "").replace("stückpreis", "")
        clean_text = clean_text.replace("€", "").replace("eur", "").replace("ab", "").replace("von", "").replace("*", "").strip()
        
        clean_text = clean_text.replace("uvp", "").replace("statt", "").replace("doporučená", "")

        if re.search(r'\d+,\d{2}', clean_text): 
            clean_text = clean_text.replace(".", "").replace(",", ".")
        match = re.search(r'(\d+\.?\d*)', clean_text)
        if match:
            try: return float(match.group(1))
            except: return None
        return None

    def extract_price_ultimate(self, page):
        try:
            meta_price = page.locator("meta[itemprop='price']").get_attribute("content")
            if meta_price:
                val = float(meta_price.replace(",", "."))
                if val > 400: return val 
        except: pass

        try:
            scripts = page.locator("script[type='application/ld+json']").all()
            for s in scripts:
                content = s.text_content()
                if '"price":' in content:
                    match = re.search(r'"price":\s*"?(\d+\.?\d*)"?', content)
                    if match:
                        val = float(match.group(1))
                        if val > 400: return val
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
                if val and val > 1: return val
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

        try:
            text = main_area.inner_text()
            patterns = [
                r'UVP.*?(\d{1,5}[.,]\d{2})', r'statt.*?(\d{1,5}[.,]\d{2})',
                r'Doporučená.*?(\d{1,5}[.,]\d{2})', r'Bisher.*?(\d{1,5}[.,]\d{2})'
            ]
            for pat in patterns:
                matches = re.findall(pat, text, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    val = self.clean_price(m)
                    if val and val > selling_price + 2: return val
        except: pass
        return None
    # =================================================

    def analyze_text_data(self, text):
        data = {}
        clean_text = text.replace('\n', ' ').replace('\r', ' ')
        clean_text = re.sub(r'\s+', ' ', clean_text)
        lower_text = clean_text.lower()

        match_flow_min = re.search(r'(\d+(?:[.,]\d+)?)\s*l/min', clean_text, re.IGNORECASE)
        match_flow_sec = re.search(r'(\d+(?:[.,]\d+)?)\s*l/s', clean_text, re.IGNORECASE)
        if match_flow_sec:
            val = float(match_flow_sec.group(1).replace(',', '.'))
            if 0.2 <= val <= 2.5: data["Flow_Rate_l_s"] = f"{val} l/s"
        elif match_flow_min:
            val = float(match_flow_min.group(1).replace(',', '.'))
            val_sec = round(val / 60.0, 2)
            if 0.2 <= val_sec <= 2.5: data["Flow_Rate_l_s"] = f"{val_sec} l/s"

        h_text = re.sub(r'Sperrwasserhöhe.{0,20}\d+\s*(?:mm)?', '', clean_text, flags=re.IGNORECASE)
        match_range = re.search(r'(?:Einbautiefe|Bauhöhe|Einbauhöhe|Gesamthöhe)[^\d]{0,40}?(\d+\s*[-–]\s*\d+)\s*mm', h_text, re.IGNORECASE)
        if match_range:
             data["Height_Adjustability"] = f"{match_range.group(1).replace(' ', '')} mm"
        else:
            match_single = re.search(r'(?:Einbautiefe|Bauhöhe|Einbauhöhe|Gesamthöhe)[^\d]{0,30}?(\d{2,3})\s*mm', h_text, re.IGNORECASE)
            if match_single:
                val = int(match_single.group(1))
                if val > 40: data["Height_Adjustability"] = f"{val} mm"

        match_dn = re.search(r'DN\s*(\d+(?:\s*/\s*\d+)?)', clean_text)
        if match_dn: data["Vertical_Outlet_Option"] = f"DN {match_dn.group(1).replace(' ', '')}"

        if "1.4404" in lower_text or "v4a" in lower_text or "316" in lower_text: data["Material_V4A"] = "Edelstahl V4A (1.4404)"
        elif "1.4301" in lower_text or "v2a" in lower_text or "304" in lower_text: data["Material_V4A"] = "Edelstahl V2A (1.4301)"
        elif "stahlemail" in lower_text or "kaldewei stahl" in lower_text: data["Material_V4A"] = "Stahlemail"
        elif "edelstahl" in lower_text: data["Material_V4A"] = "Edelstahl (Typ nezjištěn)"

        if "1253" in lower_text and "din" in lower_text: data["Cert_EN1253"] = "Yes"
        
        # 🔴 ZMĚNA: Agresivnější hledání těsnění
        fleece_keywords = [
            "dichtmanschette", "dichtband", "abdichtungsset", "dichtvlies", 
            "werkseitig angebracht", "werkseitig integriert", "abdichtung", 
            "dichtelement", "wps", "sealing", "dichtsystem", "dicht-manschette", "dicht-band"
        ]
        if any(x in lower_text for x in fleece_keywords) or ("dicht" in lower_text and "werkseitig" in lower_text):
            data["Sealing_Fleece"] = "Yes"
        
        return data

    def download_and_read_pdf(self, pdf_url):
        print(f"         📥 Stahuji PDF: {pdf_url} ...", file=sys.stderr)
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
            return ""
        except Exception as e:
            return ""

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks: 
            print("⚠️ POZOR: V Excelu nejsou žádné produkty Kaldewei.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím Kaldewei Tech Scraper V13 (The Final Polish)...", file=sys.stderr)
        tech_results = []
        price_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1080})
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám (Zlatý Standard): {sku} - {raw_name}\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku, "Manufacturer": "Kaldewei",
                    "Tech_Source_URL": "N/A", "Datasheet_URL": "N/A",
                    "Flow_Rate_l_s": "N/A", "Material_V4A": "N/A",
                    "Cert_EN1253": "No", "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A", "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No", "Color_Count": 1
                }

                # --- 1. KALDEWEI.DE ---
                print(f"         🛒 Kaldewei.de: Otevírám produktovou rodinu...", file=sys.stderr)
                pdf_url = "N/A"
                full_text = ""
                target_url = "https://www.kaldewei.de/produkte/kaldewei-flow/" if "flow" in raw_name.lower() else f"https://www.kaldewei.de/suche/?q={sku}"
                
                try:
                    page.goto(target_url, timeout=30000)
                    time.sleep(2)
                    try: page.locator("button:has-text('Alle akzeptieren'), button:has-text('Zustimmen')").click(timeout=1500)
                    except: pass
                    
                    extracted_data["Tech_Source_URL"] = target_url
                    
                    for i in range(1, 6):
                        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {i/5});")
                        time.sleep(0.3)
                    
                    buttons = page.locator("button:has-text('Technische'), button:has-text('Download'), .accordion__button, .tab__title").all()
                    for b in buttons:
                        try: b.click(force=True, timeout=500); time.sleep(0.2)
                        except: pass
                    
                    web_text = page.evaluate("document.body.innerText")
                    
                    pdf_links = page.locator("a[href$='.pdf']").all()
                    for link in pdf_links:
                        href = link.get_attribute("href")
                        text = link.inner_text().lower()
                        if href and ("datenblatt" in text or "techni" in text or "montage" in text or "produktblatt" in text):
                            pdf_url = href
                            if not pdf_url.startswith("http"): pdf_url = "https://www.kaldewei.de" + pdf_url
                            pdf_text = self.download_and_read_pdf(pdf_url)
                            full_text = web_text + " " + pdf_text
                            break
                    
                    if not full_text: full_text = web_text
                    
                    analyzed = self.analyze_text_data(full_text)
                    extracted_data.update({k: v for k, v in analyzed.items() if v})

                except Exception as e:
                    print(f"         ⚠️ Chyba na Kaldewei.de: {e}", file=sys.stderr)

                # --- 2. MEGABAD.COM ---
                print(f"         🛒 Megabad.com: Načítám cenu z konfigurátoru...", file=sys.stderr)
                selling_price = "N/A"
                original_price = "N/A"
                mb_url = "N/A"
                
                try:
                    if "flowline" in raw_name.lower():
                        mb_url = "https://www.megabad.com/kaldewei-duschrinnen-und-duschablaeufe-flowline-zero-a-2358939.htm"
                    else:
                        mb_url = f"https://www.megabad.com/suche?q={urllib.parse.quote('Kaldewei ' + raw_name.replace('Kaldewei', ''))}"
                    
                    page.goto(mb_url, timeout=30000)
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)
                    
                    try:
                        page.locator(".cmpboxbtnyes, button:has-text('Zustimmen')").first.click(timeout=1000)
                        time.sleep(1)
                    except: pass
                    
                    try:
                        page.locator("label:has-text('Edelstahl')").first.click(timeout=1000)
                        time.sleep(1)
                    except: pass
                    try:
                        page.locator("label:has-text('FlowDrain')").first.click(timeout=1000)
                        time.sleep(1.5)
                    except: pass

                    print(f"         🔎 Nasazuji Váš PricingAgent čtecí mechanismus...", file=sys.stderr)
                    
                    p_val = self.extract_price_ultimate(page)
                    
                    if p_val:
                        selling_price = p_val
                        print(f"         💰 Prodejní cena: {selling_price} EUR", file=sys.stderr)
                        
                        o_val = self.extract_original_price(page, selling_price)
                        if o_val:
                            original_price = o_val
                            print(f"         🏷️ Původní cena (UVP): {original_price} EUR", file=sys.stderr)
                            
                    else:
                        print(f"         ⚠️ Nepodařilo se přečíst koncovou cenu.", file=sys.stderr)

                except Exception as e:
                    print(f"         ⚠️ Chyba na Megabad.com: {e}", file=sys.stderr)

                # --- UKLÁDÁNÍ VÝSLEDKŮ ---
                if selling_price != "N/A":
                    price_results.append({
                        "Component_SKU": sku, "Eshop_Source": "Megabad.com",
                        "Found_Price_EUR": selling_price, "Original_Price_EUR": original_price if original_price != "N/A" else None,
                        "Price_Breakdown": "Base Model (Configured)",
                        "Product_URL": mb_url, "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    })

                print(f"         ✅ Materiál:     {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:       {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Výška:        {extracted_data['Height_Adjustability']}", file=sys.stderr)
                print(f"         ✅ Odtok:        {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                print(f"         ✅ Fleece:       {extracted_data['Sealing_Fleece']}", file=sys.stderr)
                print(f"         ✅ EN 1253:      {extracted_data['Cert_EN1253']}", file=sys.stderr)
                print(f"         💰 Systém EUR:   {selling_price} (UVP: {original_price})", file=sys.stderr)
                
                tech_results.append(extracted_data)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if tech_results:
                df = pd.DataFrame(tech_results)[self.tech_cols]
                try: 
                    old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    for sku in df['Component_SKU']: old = old[old['Component_SKU'].astype(str) != str(sku)]
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

        print("\n✅ Hotovo! Kaldewei Master Data uložena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = KaldeweiTechScraperV13()
    scraper.run()