import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import sys
import os

class ViegaGreedyMaster:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.cols_tech = [
            "Component_SKU", "Manufacturer", "Tech_Source_URL", "Datasheet_URL", 
            "Flow_Rate_l_s", "Material_V4A", "Color", "Cert_EN1253", "Cert_EN18534", 
            "Height_Adjustability", "Vertical_Outlet_Option", "Sealing_Fleece", "Color_Count",
            "Product_Name", "Length_mm", "Is_Cuttable", "Evidence_Text"
        ]
        
        self.target_urls = [
            # 🟦 CLEVIVA
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-30.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-31.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-32.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-50.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-60.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-70-mm/Advantix-Cleviva-Duschrinne-4981-11.html",
            
            # 🟩 VARIO
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-30.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-31.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-32.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Vario-Duschrinnen-4965-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Einbauhoehe-ab-70-mm/Advantix-Vario-Duschrinnen-4966-10.html",
            
            # 🟨 ADVANTIX STANDARD (Rozcestníky a rošty)
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Grundkoerper/Einbauhoehe-ab-95-mm/Advantix-Duschrinnen-Grundkoerper-4982-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Grundkoerper/Einbauhoehe-ab-70-mm/Advantix-Duschrinnen-Grundkoerper-4982-20.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-50.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-51.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-60.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-61.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-70.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-71.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-80.html",

            # 🟧 TEMPOPLEX (Dynamický rozcestník)
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Ablaeufe-fuer-Bade--und-Duschwannen/Tempoplex.html"
        ]

    def extract_rich_data(self, page, url, h1_text):
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
                    if "4981-31" in url or "4965-32" in url: color = "Schwarz Matt"
                    elif "4981-32" in url: color = "Kupfer PVD"
                    elif "4981-50" in url: color = "Gold PVD"
                    elif "4981-60" in url: color = "Champagner PVD"
                    elif "4965-30" in url: color = "Edelstahl matt"
                    elif "4965-31" in url: color = "Edelstahl glänzend"
                    elif "Tempoplex" in h1_text: color = "Chrom"
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
        print("🕵️ KROK 1: Viega Greedy Master (Chytá rozcestníky s posunem!)")
        print("="*60 + "\n", file=sys.stderr)

        all_collected = []
        with sync_playwright() as p:
            # KLÍČOVÁ OPRAVA PRO CLOUD: --disable-dev-shm-usage a --no-sandbox
            browser = p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()

            for start_url in self.target_urls:
                print(f"\n📂 Otevírám: {start_url.split('/')[-1]}", file=sys.stderr)
                try:
                    page.goto(start_url, timeout=60000)
                    time.sleep(2)

                    is_rozcestnik = any(rozc in start_url for rozc in ["Tempoplex.html", "4982-10.html", "4982-20.html"])
                    
                    if is_rozcestnik:
                        # === MAGICKÝ SCROLL PRO VYNUCNÍ LAZY LOADU ===
                        print("   ⏬ Scroluji pro probuzení dlaždic...", file=sys.stderr)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
                        time.sleep(1)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight/1.5)")
                        time.sleep(1)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1.5)

                        links = page.locator("a[href*='/Katalog/']").all()
                        model_urls = []
                        for l in links:
                            href = l.get_attribute("href")
                            if href and ".html" in href:
                                full_url = "https://www.viega.de" + href if href.startswith("/") else href
                                if full_url == start_url: continue 
                                
                                if "Tempoplex" in start_url and "Tempoplex" in full_url:
                                    model_urls.append(full_url)
                                elif "4982-10" in start_url and "4982" in full_url:
                                    model_urls.append(full_url)
                                elif "4982-20" in start_url and "4982" in full_url:
                                    model_urls.append(full_url)
                        
                        model_urls = list(set(model_urls))
                        print(f"   🧩 Nalezeno pod-modelů k prokliku: {len(model_urls)}", file=sys.stderr)
                        for m_url in model_urls[:10]:
                            try:
                                page.goto(m_url, timeout=45000)
                                time.sleep(1.5)
                                h1 = page.locator("h1").first.inner_text().strip()
                                found = self.extract_rich_data(page, m_url, h1)
                                all_collected.extend(found)
                            except: pass
                    else:
                        h1 = page.locator("h1").first.inner_text().strip()
                        found = self.extract_rich_data(page, start_url, h1)
                        all_collected.extend(found)
                except Exception as e:
                    print(f"   ❌ Chyba u {start_url}: {e}", file=sys.stderr)
            
            browser.close()

        if all_collected:
            df_new = pd.DataFrame(all_collected)
            
            rename_map = {
                "Component_SKU": "Article_Number_SKU",
                "Manufacturer": "Brand",
                "Tech_Source_URL": "Product_URL",
                "Flow_Rate_l_s": "Flow_Rate_ls",
                "Material_V4A": "Is_V4A"
            }
            df_new.rename(columns=rename_map, inplace=True)

            if os.path.exists(self.excel_path):
                df_tech = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                sku_col = 'Article_Number_SKU' if 'Article_Number_SKU' in df_tech.columns else 'Component_SKU'
                
                if sku_col in df_tech.columns:
                    df_tech[sku_col] = df_tech[sku_col].astype(str).str.replace('.0', '', regex=False).str.strip()
                
                df_combined = pd.concat([df_tech, df_new], ignore_index=True)
                if sku_col in df_combined.columns:
                    df_combined.drop_duplicates(subset=[sku_col], keep='last', inplace=True)
            else:
                df_combined = df_new

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_combined.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ HOTOVO! Excel aktualizován.")
        else:
            print("\n❌ Nenalezena žádná data.")

if __name__ == "__main__":
    ViegaGreedyMaster().run()