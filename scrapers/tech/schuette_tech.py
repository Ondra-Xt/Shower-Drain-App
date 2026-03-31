import pandas as pd
import re
import sys
import time
import os
import urllib.parse
import datetime
from playwright.sync_api import sync_playwright

class SchuetteTechScraperV8:
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
                if "schütte" in name.lower() or "schuette" in name.lower():
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except Exception as e:
            print(f"⚠️ Chyba při čtení Excelu: {e}", file=sys.stderr)
            return []

    def extract_best_height(self, text):
        best_val = None
        matches = re.finditer(r'(?:Einbautiefe|Einbauhöhe|Bauhöhe|Höhe|Installation height|Stavební výška)[^\d]{0,30}?(\d+\s*[-– ]\s*\d+|\d+)\s*mm', text, re.IGNORECASE)
        for m in matches:
            val = m.group(1).replace(" ", "-").replace("–", "-")
            val = re.sub(r'-+', '-', val)
            if "-" in val:
                best_val = val 
                break
            elif not best_val:
                best_val = val 
        return f"{best_val} mm" if best_val else "N/A"

    def extract_flow_rate(self, text):
        matches = re.finditer(r'(\d+(?:[.,]\d+)?)\s*(l/s|l/min|ltr/min|liter/min|l\s*/\s*sek|l/m)', text, re.IGNORECASE)
        max_flow = 0.0
        for m in matches:
            val_str = m.group(1).replace(",", ".")
            try:
                val = float(val_str)
                unit = m.group(2).lower()
                if "min" in unit or "m" in unit: val = val / 60.0
                if 0.2 <= val <= 3.5 and val > max_flow: max_flow = val
            except: pass
        return f"{max_flow:.2f} l/s" if max_flow > 0 else "N/A"

    def extract_material(self, text):
        lower_text = text.lower()
        if "1.4404" in lower_text or "v4a" in lower_text or "316l" in lower_text: return "Edelstahl V4A (1.4404) (Yes V4A)"
        elif "1.4301" in lower_text or "v2a" in lower_text or "304" in lower_text or "edelstahl" in lower_text or "stainless steel" in lower_text: return "Edelstahl V2A (1.4301)"
        elif "polypropylen" in lower_text or "kunststoff" in lower_text or "plastic" in lower_text or "plast" in lower_text or "pp" in lower_text: return "Kunststoff (Polypropylen)"
        return "N/A"

    def extract_price(self, page):
        """Zcela nová agresivní detekce ceny v EUR"""
        # 1. Čistá meta data (pro Google)
        try:
            price_content = page.locator('meta[itemprop="price"]').first.get_attribute('content', timeout=1000)
            if price_content:
                return float(price_content.replace(',', '.'))
        except: pass
        
        # 2. Hledání v typických CSS třídách e-shopů
        try:
            texts = page.locator('.product-detail-price, .product-price, .price--content, [itemprop="price"], .price, .current-price').all_inner_texts()
            for text in texts:
                clean_text = text.replace('\n', ' ').strip()
                match = re.search(r'(\d{1,3}(?:\.\d{3})*)[,.](\d{2})', clean_text)
                if match:
                    main_part = match.group(1).replace('.', '')
                    return float(f"{main_part}.{match.group(2)}")
        except: pass
        
        # 3. Hrubá síla: Přečte celý web a najde první číslo u znaku €
        try:
            body_text = page.evaluate("document.body.innerText")
            # Hledá např. 149,99 € nebo 1.299,00 EUR
            matches = re.findall(r'(\d{1,3}(?:\.\d{3})*)[,.](\d{2})\s*(?:€|EUR)', body_text)
            if matches:
                main_part = matches[0][0].replace('.', '')
                return float(f"{main_part}.{matches[0][1]}")
            
            # Hledá např. € 149.99
            matches2 = re.findall(r'(?:€|EUR)\s*(\d{1,3}(?:\.\d{3})*)[,.](\d{2})', body_text)
            if matches2:
                main_part = matches2[0][0].replace('.', '')
                return float(f"{main_part}.{matches2[0][1]}")
        except: pass
        
        return "N/A"

    def destroy_cookie_banners(self, page):
        try:
            page.evaluate("""
                const banners = document.querySelectorAll('#cc--main, #c-s-in, .cookiebot, #cookiebanner, .cc-window, .cookie-consent, #cmpbox');
                banners.forEach(el => el.remove());
                document.body.style.overflow = 'auto';
            """)
        except: pass

    def search_shops_stealth(self, page, sku, raw_name):
        clean_name = re.sub(r'Schütte|Schuette|fjschuette', '', raw_name, flags=re.IGNORECASE).strip()
        queries = list(dict.fromkeys([sku, clean_name]))
        queries = [q for q in queries if len(q) > 2]
        
        shops = [
            {
                "name": "Schuette.com",
                "url_template": "https://fjschuette.com/de/suche?s={}",
                "cookie_sel": "button:has-text('Akzeptieren'), button:has-text('Zustimmen'), button:has-text('Alle akzeptieren')"
            },
            {
                "name": "Megabad.com",
                "url_template": "https://www.megabad.com/suche?q={}",
                "cookie_sel": ".cmpboxbtnyes, #cmpbntyestxt, button:has-text('Alle')"
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

                    time.sleep(2.5)
                    try: page.locator(shop["cookie_sel"]).first.click(timeout=1500, force=True)
                    except: pass
                    
                    self.destroy_cookie_banners(page)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)

                    is_detail = False
                    if "schuette" in shop["name"].lower() and ("/produkte/" in page.url or "/detail" in page.url):
                        if "duschrinne" in page.url.lower():
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
                                
                                if any(x in href for x in ["bewertung", "img", "basket", "cart", "login", "suche", "search", "account", "checkout", "tel:", "mailto:"]):
                                    continue
                                
                                if "schuette" in shop["name"].lower():
                                    if "/produkte/" in href and not href.endswith("/produkte/"):
                                        parts = href.split("/produkte/")
                                        if len(parts) > 1 and len(parts[1]) > 5:
                                            target_href = raw_href
                                            break
                                            
                                elif "megabad" in shop["name"].lower():
                                    if "/produkt" in href or "-a-" in href or "-p-" in href:
                                        target_href = raw_href
                                        break

                        if target_href:
                            print(f"         🚀 Odkaz na produkt nalezen! Přecházím přímo na URL...", file=sys.stderr)
                            if not target_href.startswith("http"):
                                domain = "https://fjschuette.com" if "schuette" in shop["name"].lower() else "https://www.megabad.com"
                                target_href = domain.rstrip("/") + "/" + target_href.lstrip("/")
                            
                            page.goto(target_href, timeout=20000)
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(2.5)
                        else:
                            print(f"         ⚠️ Žádný produktový odkaz nenalezen ve výsledcích.", file=sys.stderr)
                            continue
                    else:
                        print(f"         🚀 E-shop nás po hledání přesměroval rovnou do detailu!", file=sys.stderr)

                    self.destroy_cookie_banners(page)

                    # 🔴 EXTARAKCE CENY POMOCÍ NOVÉ FUNKCE
                    found_price = self.extract_price(page)

                    print(f"         🔍 Prohledávám roletky a záložky s textem...", file=sys.stderr)
                    buttons = page.locator("button, .accordion-button, .nav-link, .tab-pane, h3, h4, .toggle").all()
                    for b in buttons:
                        try:
                            if b.is_visible():
                                b_text = b.inner_text().lower()
                                if any(x in b_text for x in ["eigenschaft", "technisch", "detail", "beschreibung", "lieferumfang", "daten", "mass", "mehr"]):
                                    b.click(timeout=1000, force=True)
                                    time.sleep(0.3)
                        except: pass

                    combined_text = page.evaluate("document.body.innerText")

                    f_rate = self.extract_flow_rate(combined_text)
                    h_adj = self.extract_best_height(combined_text)
                    
                    if f_rate != "N/A" or h_adj != "N/A" or "schuette" in shop["name"].lower():
                        return combined_text, page.url, shop["name"], found_price
                    else:
                        print(f"         ⚠️ Produkt otevřen, ale chybí v něm data. Zkouším další dotaz/eshop...", file=sys.stderr)

                except Exception as e:
                    print(f"         ⚠️ Chyba: {e}", file=sys.stderr)
                    
        return "", "N/A", "N/A", "N/A"

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks: 
            print("⚠️ POZOR: V Excelu jsem nenašel žádné produkty Schütte.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím Schuette Tech & Price Scraper V8 pro {len(tasks)} produktů...", file=sys.stderr)
        tech_results = []
        price_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()

            for task in tasks:
                sku = task["sku"]
                raw_name = task["name"]
                
                print(f"\n{'='*50}\n🔍 Zpracovávám: {sku}\n{'='*50}", file=sys.stderr)
                
                extracted_data = {
                    "Component_SKU": sku,
                    "Manufacturer": "Schütte",
                    "Tech_Source_URL": "N/A",
                    "Datasheet_URL": "N/A",
                    "Flow_Rate_l_s": "N/A",
                    "Material_V4A": "N/A",
                    "Cert_EN1253": "No",
                    "Cert_EN18534": "No",
                    "Height_Adjustability": "N/A",
                    "Vertical_Outlet_Option": "Check Drawing",
                    "Sealing_Fleece": "No",
                    "Color_Count": 1
                }

                content, source_url, source_eshop, price = self.search_shops_stealth(page, sku, raw_name)
                
                if content:
                    extracted_data["Tech_Source_URL"] = source_url
                    extracted_data["Flow_Rate_l_s"] = self.extract_flow_rate(content)
                    extracted_data["Height_Adjustability"] = self.extract_best_height(content)
                    extracted_data["Material_V4A"] = self.extract_material(content)
                    
                    if "1253" in content: extracted_data["Cert_EN1253"] = "Yes"
                    if "18534" in content: extracted_data["Cert_EN18534"] = "Yes"
                    
                    lower_content = content.lower()
                    fleece_keywords = ["tape", "band", "fleece", "páska", "vlies", "manschette", "dichtband", "dichtvlies", "abdichtvlies"]
                    if any(word in lower_content for word in fleece_keywords):
                        extracted_data["Sealing_Fleece"] = "Yes"

                    dn_match = re.search(r'(?:Abflussrohrdurchmesser|Rohranschluss|DN|Adapter)\s*[:\-]?\s*(\d{2,3})', content, re.IGNORECASE)
                    direction = ""
                    if re.search(r'\bsenkrecht', content, re.IGNORECASE): direction = " Vertical"
                    elif re.search(r'\bwaagerecht', content, re.IGNORECASE): direction = " Horizontal"
                        
                    if dn_match:
                        if "40" in dn_match.group(1) and "50" in content:
                            extracted_data["Vertical_Outlet_Option"] = f"DN40/DN50{direction}".strip()
                        else:
                            extracted_data["Vertical_Outlet_Option"] = f"DN{dn_match.group(1)}{direction}".strip()
                    elif direction:
                        extracted_data["Vertical_Outlet_Option"] = direction.strip()
                        
                    if "schuette" in source_url.lower():
                        try:
                            pdf_links = page.locator("a[href$='.pdf']").all()
                            for link in pdf_links:
                                raw_pdf_href = link.get_attribute("href")
                                if raw_pdf_href:
                                    href = raw_pdf_href.lower()
                                    if "sicherheit" in href: continue
                                    if "montage" in href or "anleitung" in href or "datenblatt" in href or "zeichnung" in href:
                                        if not raw_pdf_href.startswith("http"): 
                                            raw_pdf_href = "https://fjschuette.com" + raw_pdf_href
                                        extracted_data["Datasheet_URL"] = raw_pdf_href
                                        break
                        except: pass

                    if price != "N/A":
                        price_results.append({
                            "Component_SKU": sku,
                            "Eshop_Source": source_eshop,
                            "Found_Price_EUR": price,
                            "Price_Breakdown": "Single",
                            "Product_URL": source_url,
                            "Timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        })

                print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Odtok:     {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                print(f"         ✅ Fleece:    {extracted_data['Sealing_Fleece']}", file=sys.stderr)
                print(f"         ✅ Cena EUR:  {price} (Eshop: {source_eshop})", file=sys.stderr)
                
                tech_results.append(extracted_data)

            browser.close()

        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            if tech_results:
                df_tech = pd.DataFrame(tech_results)[self.tech_cols]
                try:
                    existing_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                    for _, new_row in df_tech.iterrows():
                        s = str(new_row['Component_SKU']).strip().lower()
                        existing_tech = existing_tech[existing_tech['Component_SKU'].astype(str).str.strip().str.lower() != s]
                    final_tech = pd.concat([existing_tech, df_tech], ignore_index=True)
                except:
                    final_tech = df_tech
                final_tech.to_excel(writer, sheet_name="Products_Tech", index=False)
                
            if price_results:
                df_price = pd.DataFrame(price_results)[self.price_cols]
                try:
                    existing_price = pd.read_excel(self.excel_path, sheet_name="Market_Prices")
                    for _, new_row in df_price.iterrows():
                        s = str(new_row['Component_SKU']).strip().lower()
                        e = str(new_row['Eshop_Source']).strip().lower()
                        existing_price = existing_price[
                            ~((existing_price['Component_SKU'].astype(str).str.strip().str.lower() == s) & 
                              (existing_price['Eshop_Source'].astype(str).str.strip().str.lower() == e))
                        ]
                    final_price = pd.concat([existing_price, df_price], ignore_index=True)
                except:
                    final_price = df_price
                final_price.to_excel(writer, sheet_name="Market_Prices", index=False)

        print("\n✅ Hotovo! Technická data i ceny byly uloženy.", file=sys.stderr)

if __name__ == "__main__":
    scraper = SchuetteTechScraperV8()
    scraper.run()