import pandas as pd
import re
import sys
import time
import os
import urllib.parse
from playwright.sync_api import sync_playwright

class AlcaTechScraperV8:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count"
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
                name = str(row["Component_Name"])
                sku = str(row["Component_SKU"]).strip()
                if "alca" in name.lower() or "alcadrain" in name.lower() or "alcaplast" in name.lower():
                    if sku not in seen:
                        seen.add(sku)
                        tasks.append({"sku": sku, "name": name})
            return tasks
        except Exception as e:
            return []

    def extract_best_height(self, text):
        best_val = None
        matches = re.finditer(r'(?:Installation height|Einbauhöhe|Bauhöhe|Stavební výška|Instalační výška|Höhe|Height)[^\d]{0,30}?(\d+\s*[-– ]\s*\d+|\d+)\s*mm', text, re.IGNORECASE)
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
        matches = re.finditer(r'(\d+(?:[.,]\d+)?)\s*(l/s|l/min|l\s*/\s*sek|l/m)', text, re.IGNORECASE)
        max_flow = 0.0
        for m in matches:
            val_str = m.group(1).replace(",", ".")
            try:
                val = float(val_str)
                unit = m.group(2).lower()
                if "min" in unit or "m" in unit: val = val / 60.0
                if 0.3 <= val <= 3.5 and val > max_flow: max_flow = val
            except: pass
        return f"{max_flow:.2f} l/s" if max_flow > 0 else "N/A"

    def extract_material(self, text):
        lower_text = text.lower()
        if "1.4404" in lower_text or "v4a" in lower_text or "316l" in lower_text: return "Edelstahl V4A (1.4404) (Yes V4A)"
        elif "1.4301" in lower_text or "v2a" in lower_text or "304" in lower_text or "edelstahl" in lower_text or "stainless steel" in lower_text or "nerez" in lower_text: return "Edelstahl V2A (1.4301)"
        elif "polypropylen" in lower_text or "kunststoff" in lower_text or "plastic" in lower_text or "plast" in lower_text or "pp" in lower_text: return "Kunststoff (Polypropylen)"
        return "N/A"

    def search_shops_stealth(self, page, sku, raw_name):
        base_sku = re.sub(r'-\d{3,4}M?$', '', sku).strip()
        core_sku = base_sku.split('-')[0].strip()
        queries = list(dict.fromkeys([sku, base_sku, core_sku]))
        
        shops = [
            {
                "name": "Alcadrain.com",
                "url_template": "https://www.alcadrain.com/vyhledavani?searchword={}&searchphrase=all",
                "cookie_sel": "button:has-text('Souhlasím'), button:has-text('Accept'), button:has-text('Alle akzeptieren'), #c-s-in button",
                "link_sel": ".products-list a, .search-results a, .product a, a.product-link, a.item-title, main a[href*='detail']"
            },
            {
                "name": "DEK.cz",
                "url_template": "https://www.dek.cz/produkty/vyhledavani?text={}",
                "cookie_sel": "button:has-text('Souhlasím')",
                "link_sel": "a.product-card__link, a[href*='/produkt/']"
            }
        ]

        for shop in shops:
            for query in queries:
                print(f"         🛒 {shop['name']}: Napřímo hledám výraz '{query}'...", file=sys.stderr)
                try:
                    search_url = shop["url_template"].format(urllib.parse.quote(query))
                    response = page.goto(search_url, timeout=30000)
                    
                    if response and response.status in [403, 429]:
                        print(f"         🛑 {shop['name']} zablokoval přístup.", file=sys.stderr)
                        break

                    # Delší čas na naskočení protivného cookie banneru
                    time.sleep(3)
                    try: page.locator(shop["cookie_sel"]).first.click(timeout=2000)
                    except: pass
                    
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)

                    is_detail = False
                    if "alcadrain" in shop["name"].lower() and ("/detail" in page.url or "/product/" in page.url):
                        is_detail = True
                    elif "dek" in shop["name"].lower() and ("/produkt/" in page.url):
                        is_detail = True

                    if not is_detail:
                        links = page.locator(shop["link_sel"]).all()
                        target_link = None
                        target_href = None
                        
                        for l in links:
                            if l.is_visible():
                                text = l.inner_text().upper()
                                raw_href = l.get_attribute("href")
                                href = raw_href.upper() if raw_href else ""
                                
                                if "BEWERTUNG" in href or "IMG" in href: continue

                                if base_sku.upper() in text or base_sku.upper() in href:
                                    target_link = l
                                    target_href = raw_href
                                    break
                                    
                        if not target_link and links:
                            for l in links:
                                if l.is_visible():
                                    raw_href = l.get_attribute("href")
                                    if raw_href and ("detail" in raw_href.lower() or "produkt" in raw_href.lower()):
                                        target_link = l
                                        target_href = raw_href
                                        break

                        if target_link:
                            print(f"         🖱️ Klikám na nalezený produkt s Force=True...", file=sys.stderr)
                            try:
                                # 🔴 FORCE CLICK - ignoruje, pokud něco překrývá obrazovku
                                target_link.click(timeout=5000, force=True)
                            except Exception as click_err:
                                print(f"         ⚠️ Kliknutí selhalo, zkouším záložní načtení URL...", file=sys.stderr)
                                if target_href:
                                    # Plán B - přímý přechod na zachycenou URL
                                    if not target_href.startswith("http"):
                                        domain = "https://www.alcadrain.com" if "alcadrain" in shop["name"].lower() else "https://www.dek.cz"
                                        target_href = domain + target_href
                                    page.goto(target_href, timeout=15000)
                                    
                            page.wait_for_load_state("domcontentloaded")
                            time.sleep(2)
                        else:
                            print(f"         ⚠️ Žádný produktový odkaz nenalezen ve výsledcích.", file=sys.stderr)
                            continue
                    else:
                        print(f"         🚀 E-shop nás přesměroval rovnou do detailu!", file=sys.stderr)

                    combined_text = ""
                    tabs_to_try = [
                        "Vlastnosti", "Features", "Eigenschaften", 
                        "Parametry", "Parameters", "Technické", "Technical", 
                        "Obsah balení", "Scope of supply", "Lieferumfang", "Balení",
                        "Ke stažení", "Downloads"
                    ]
                    
                    for t_name in tabs_to_try:
                        try:
                            # Tady taky dán Force click kvůli občasným bannerům
                            tab = page.locator(f"a:has-text('{t_name}'), li:has-text('{t_name}'), span:has-text('{t_name}')").first
                            if tab.is_visible():
                                tab.click(timeout=1000, force=True)
                                time.sleep(0.5)
                                combined_text += " " + page.evaluate("document.body.innerText")
                        except: pass

                    if not combined_text.strip():
                        combined_text = page.evaluate("document.body.innerText")

                    f_rate = self.extract_flow_rate(combined_text)
                    h_adj = self.extract_best_height(combined_text)
                    
                    if f_rate != "N/A" or h_adj != "N/A" or "alcadrain" in shop["name"].lower():
                        return combined_text, page.url
                    else:
                        print(f"         ⚠️ Produkt otevřen, ale chybí v něm data. Zkouším další dotaz...", file=sys.stderr)

                except Exception as e:
                    print(f"         ⚠️ Chyba: {e}", file=sys.stderr)
                    
        return "", "N/A"

    def run(self):
        self.check_excel_access()
        tasks = self.get_tasks()
        
        if not tasks: 
            print("⚠️ POZOR: V Excelu jsem nenašel žádné produkty Alca/Alcadrain.", file=sys.stderr)
            return
            
        print(f"🚀 Spouštím Alcadrain Tech Scraper V8 (Force Click Edition) pro {len(tasks)} produktů...", file=sys.stderr)
        results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
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
                    "Manufacturer": "Alcadrain",
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

                content, source_url = self.search_shops_stealth(page, sku, raw_name)
                
                if content:
                    extracted_data["Tech_Source_URL"] = source_url
                    extracted_data["Flow_Rate_l_s"] = self.extract_flow_rate(content)
                    extracted_data["Height_Adjustability"] = self.extract_best_height(content)
                    extracted_data["Material_V4A"] = self.extract_material(content)
                    
                    if "EN 1253" in content or "DIN 1253" in content or "EN1253" in content: extracted_data["Cert_EN1253"] = "Yes"
                    if "18534" in content: extracted_data["Cert_EN18534"] = "Yes"
                    
                    lower_content = content.lower()
                    fleece_keywords = ["tape", "band", "fleece", "páska", "vlies", "manschette", "hydroizolační", "waterproofing", "izolační límec", "dichtband"]
                    if any(word in lower_content for word in fleece_keywords):
                        extracted_data["Sealing_Fleece"] = "Yes"

                    dn_match = re.search(r'(?:Waste pipe diameter|Průměr odpadního potrubí|Abflussrohrdurchmesser|odpadní trubka|pipe diameter|DN)\s*[:\-]?\s*(\d{2,3})', content, re.IGNORECASE)
                    direction = ""
                    if re.search(r'\bsvisl|\bvertical|\bsenkrecht|\bspodní', content, re.IGNORECASE):
                        direction = " Vertical"
                    elif re.search(r'\bvodorov|\bhorizontal|\bwaagerecht|\bboční', content, re.IGNORECASE):
                        direction = " Horizontal"
                        
                    if dn_match:
                        extracted_data["Vertical_Outlet_Option"] = f"DN{dn_match.group(1)}{direction}".strip()
                    elif direction:
                        extracted_data["Vertical_Outlet_Option"] = direction.strip()
                        
                    if "alcadrain" in source_url.lower():
                        try:
                            pdf_links = page.locator("a[href$='.pdf']").all()
                            for link in pdf_links:
                                href = link.get_attribute("href")
                                if href and ("technic" in href.lower() or "datasheet" in href.lower() or "list" in href.lower() or "tl_" in href.lower()):
                                    if not href.startswith("http"): href = "https://www.alcadrain.com" + href
                                    extracted_data["Datasheet_URL"] = href
                                    break
                        except: pass

                print(f"         ✅ Materiál:  {extracted_data['Material_V4A']}", file=sys.stderr)
                print(f"         ✅ Průtok:    {extracted_data['Flow_Rate_l_s']}", file=sys.stderr)
                print(f"         ✅ Odtok:     {extracted_data['Vertical_Outlet_Option']}", file=sys.stderr)
                print(f"         ✅ Výška:     {extracted_data['Height_Adjustability']}", file=sys.stderr)
                print(f"         ✅ Fleece:    {extracted_data['Sealing_Fleece']}", file=sys.stderr)
                print(f"         ✅ PDF URL:   {extracted_data['Datasheet_URL']}", file=sys.stderr)
                
                results.append(extracted_data)

            browser.close()

        if results:
            df = pd.DataFrame(results)[self.cols]
            try:
                existing_df = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                for _, new_row in df.iterrows():
                    s = str(new_row['Component_SKU']).strip().lower()
                    existing_df = existing_df[existing_df['Component_SKU'].astype(str).str.strip().str.lower() != s]
                final_df = pd.concat([existing_df, df], ignore_index=True)
            except:
                final_df = df
                
            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                final_df.to_excel(writer, sheet_name="Products_Tech", index=False)
            print("\n✅ Hotovo! Alcadrain data uložena.", file=sys.stderr)

if __name__ == "__main__":
    scraper = AlcaTechScraperV8()
    scraper.run()