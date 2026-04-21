import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import sys
import os

class ViegaDynamicMaster:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        self.model_queries = [
            # Cleviva
            "4981.10", "4981.11", "4981.30", "4981.31", "4981.32", "4981.50", "4981.60",
            # Vario
            "4965.10", "4966.10", "4965.30", "4965.31", "4965.32",
            # Advantix Standard
            "4982.10", "4982.20", "4982.50", "4982.51", "4982.60", "4982.61", "4982.70", "4982.71", "4982.80",
            # Tempoplex
            "6961", "6962", "6963", "Tempoplex" 
        ]

    def search_and_get_links(self, page, model_query):
        """Nasimuluje lidské vyhledávání na webu Viegy."""
        print(f"\n🔍 Vyhledávám model: {model_query}", file=sys.stderr)
        page.goto("https://www.viega.de/de.html", timeout=60000)
        time.sleep(2)
        
        page.evaluate("try{document.querySelector('#uc-btn-accept-banner').click()}catch(e){}")
        
        success = page.evaluate(f"""(q) => {{
            let inputs = Array.from(document.querySelectorAll('input'));
            let searchInput = inputs.find(i => i.type === 'search' || i.name === 'q' || (i.placeholder && i.placeholder.toLowerCase().includes('such')));
            if(searchInput) {{
                searchInput.value = q;
                let form = searchInput.closest('form');
                if(form) {{ form.submit(); return true; }}
                else {{
                    searchInput.dispatchEvent(new KeyboardEvent('keydown', {{'key': 'Enter'}}));
                    return true;
                }}
            }}
            return false;
        }}""", model_query)
        
        if not success:
            page.goto(f"https://www.viega.de/de/suche.html?q={model_query}")
            
        time.sleep(3)
        
        print("   ⏬ Scrolluji výsledky hledání...", file=sys.stderr)
        # Zvýšeno scrollování, aby to bezpečně načetlo i více než 20 výsledků
        for i in range(1, 8):
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * ({i}/7))")
            time.sleep(1)
            
        links = page.locator("a[href*='/Katalog/']").all()
        found_urls = []
        
        base_query = model_query.split('.')[0] 
        
        for l in links:
            href = l.get_attribute("href")
            if href and ".html" in href and (base_query.lower() in href.lower() or model_query.lower() == "tempoplex"):
                full_url = "https://www.viega.de" + href if href.startswith("/") else href
                found_urls.append(full_url)
                
        unique_urls = list(set(found_urls))
        print(f"   🎯 Nalezeno {len(unique_urls)} produktových stránek k prozkoumání.", file=sys.stderr)
        return unique_urls

    def extract_rich_data(self, page, url):
        """Čteč tabulek."""
        try:
            h1_text = page.locator("h1").first.inner_text().strip()
        except:
            h1_text = "Viega Produkt"

        page.evaluate("""() => {
            document.querySelectorAll('button, a, li, div').forEach(el => {
                let t = (el.innerText || "").toLowerCase();
                if(t.includes('artikel') || t.includes('modell')) el.click();
            });
        }""")
        time.sleep(2)

        pdf_link = ""
        try:
            pdf_el = page.locator("a[href*='.pdf']").first
            if pdf_el.count() > 0: pdf_link = "https://www.viega.de" + pdf_el.get_attribute("href")
        except: pass

        body_text = page.locator("body").inner_text()
        global_flow = ""
        m_flow = re.search(r'(\d+(?:,\d+)?)\s*l/s', body_text)
        if m_flow: global_flow = m_flow.group(1).replace(',', '.')

        table_data = page.evaluate("""() => {
            let results = [];
            document.querySelectorAll('table').forEach(table => {
                let ths = table.querySelectorAll('th');
                if (ths.length === 0) ths = table.querySelectorAll('tr:first-child td');
                let headers = [];
                ths.forEach(th => headers.push(th.innerText.toLowerCase().trim()));
                
                let colSku = headers.findIndex(h => h.includes('artikel') || h.includes('art.-nr'));
                let colLen = headers.findIndex(h => h === 'l' || h.includes('länge') || h.includes('abmessung'));
                let colColor = headers.findIndex(h => h.includes('ausführung') || h.includes('farbe') || h.includes('modell'));
                let colFlow = headers.findIndex(h => h.includes('ablaufleistung'));
                
                if (colSku !== -1) {
                    let rows = table.querySelectorAll('tr');
                    for(let i = 1; i < rows.length; i++) {
                        let cells = rows[i].querySelectorAll('td');
                        if (cells.length > colSku) {
                            let skuRaw = cells[colSku].innerText;
                            let length = (colLen !== -1 && cells.length > colLen) ? cells[colLen].innerText : "";
                            let color = (colColor !== -1 && cells.length > colColor) ? cells[colColor].innerText : "";
                            let flow = (colFlow !== -1 && cells.length > colFlow) ? cells[colFlow].innerText : "";
                            results.push({sku: skuRaw, length: length, color: color, flow: flow, row_full: rows[i].innerText});
                        }
                    }
                }
            });
            return results;
        }""")

        items = []
        found_skus = set()

        for item in table_data:
            sku_match = re.search(r'([1-9]\d{2}[ \u00A0]?\d{3})', item['sku'])
            if not sku_match: continue
            
            sku = sku_match.group(1).replace(" ", "").replace("\u00A0", "")
            
            if sku not in found_skus:
                found_skus.add(sku)
                
                length = item['length'].strip()
                if not length:
                    m_len = re.search(r'\b(750|800|900|1000|1200)\b', item['row_full'])
                    if m_len: length = m_len.group(1)
                if not length and "Vario" in h1_text: length = "300 - 1200"

                color = item['color'].strip().replace("\n", " ")
                if not color:
                    if "Tempoplex" in h1_text: color = "Chrom"
                    else: color = "Standard Edelstahl"
                
                flow = item['flow'].strip() if item['flow'] else global_flow
                material = "Edelstahl V4A" if "v4a" in color.lower() or "1.4404" in color.lower() or "v4a" in item['row_full'].lower() else "Edelstahl V2A"

                items.append({
                    "Component_SKU": sku, "Manufacturer": "Viega", "Product_Name": h1_text,
                    "Tech_Source_URL": url, "Datasheet_URL": pdf_link, "Flow_Rate_l_s": flow,
                    "Length_mm": length, "Color": color, "Material_V4A": material,
                    "Cert_EN1253": "Yes", "Cert_EN18534": "Yes", 
                    "Is_Cuttable": "Yes" if "Vario" in h1_text or "Cleviva" in h1_text else "No"
                })
                print(f"      ✅ [SKU: {sku}] L: {length or '--'} | Barva: {color} | Flow: {flow}", file=sys.stderr)
        
        return items

    def run(self):
        print("\n" + "="*60)
        print("🕵️ KROK 1: Viega Dynamic Master (Vždy čerstvá data bez 'duchů')")
        print("="*60 + "\n", file=sys.stderr)

        all_collected = []
        visited_urls = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for query in self.model_queries:
                urls = self.search_and_get_links(page, query)
                
                # ZRUŠEN LIMIT - Projdeme naprosto všechny nalezené URL k danému hledání
                for url in urls: 
                    if url in visited_urls: continue
                    visited_urls.add(url)
                    
                    print(f"\n   👉 Otevírám nalezený detail: {url.split('/')[-1]}", file=sys.stderr)
                    try:
                        page.goto(url, timeout=40000)
                        time.sleep(1.5)
                        found = self.extract_rich_data(page, url)
                        all_collected.extend(found)
                    except Exception as e:
                        print(f"      ❌ Chyba čtení: {e}", file=sys.stderr)
            
            browser.close()

        if all_collected:
            df_new = pd.DataFrame(all_collected)
            
            if os.path.exists(self.excel_path):
                df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                df_tech['Component_SKU'] = df_tech['Component_SKU'].astype(str).str.replace('.0', '', regex=False).str.strip()
                
                # CHYTRÉ PŘEMAZÁNÍ: Ponecháme ostatní výrobce (Geberit atd.), ale Viegu smažeme
                df_tech_other = df_tech[df_tech['Manufacturer'] != 'Viega']
                
                # A napojíme na ně ty zbrusu nové, aktuální záznamy z Viegy
                df_combined = pd.concat([df_tech_other, df_new], ignore_index=True)
                df_combined.drop_duplicates(subset=['Component_SKU', 'Manufacturer'], keep='last', inplace=True)
            else:
                df_combined = df_new

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ HOTOVO! Stará data Viega smazána. Vloženo {len(df_new['Component_SKU'].unique())} aktuálních položek.")
        else:
            print("\n❌ Nenalezena žádná data.")

if __name__ == "__main__":
    ViegaDynamicMaster().run()