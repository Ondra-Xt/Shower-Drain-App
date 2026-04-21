import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import sys
import os

class ViegaUltraDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        # Spojení Vašich přesných URL a mých širokých kategorií
        self.target_urls = [
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-30.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-31.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-32.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-50.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Advantix-Cleviva-Duschrinnen-Zubehoer/Advantix-Cleviva-Duschrinnen-4981-60.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-70-mm/Advantix-Cleviva-Duschrinne-4981-11.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-30.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-31.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Advantix-Vario-Duschrinnen-Zubehoer/Advantix-Vario-Duschrinnen-4965-32.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Vario-Duschrinnen-4965-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Vario-Duschrinnen/Einbauhoehe-ab-70-mm/Advantix-Vario-Duschrinnen-4966-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Grundkoerper/Einbauhoehe-ab-95-mm/Advantix-Duschrinnen-Grundkoerper-4982-10.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Grundkoerper/Einbauhoehe-ab-70-mm/Advantix-Duschrinnen-Grundkoerper-4982-20.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-50.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-51.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-60.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-61.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-70.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-71.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Duschrinnen/Advantix-Duschrinnen-Zubehoer/Advantix-Duschrinnen-Rost-4982-80.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Ablaeufe-fuer-Bade--und-Duschwannen/Tempoplex.html",
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Zubehoer-und-Ersatzteile-fuer-Ablaeufe.html"
        ]

    def extract_rich_data(self, page, url, h1_text):
        # VAŠE MAGICKÉ KLIKÁNÍ NA ARTIKEL/MODELL
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

        # EXTRAKCE Z TABULEK
        table_data = page.evaluate("""() => {
            let results = [];
            document.querySelectorAll('table').forEach(table => {
                let ths = table.querySelectorAll('th');
                if (ths.length === 0) ths = table.querySelectorAll('tr:first-child td');
                let headers = Array.from(ths).map(th => th.innerText.toLowerCase().trim());
                
                let colSku = headers.findIndex(h => h.includes('artikel') || h.includes('art.-nr'));
                let colLen = headers.findIndex(h => h === 'l' || h.includes('länge') || h.includes('abmessung'));
                let colColor = headers.findIndex(h => h.includes('ausführung') || h.includes('farbe') || h.includes('modell'));
                let colFlow = headers.findIndex(h => h.includes('ablaufleistung'));
                
                if (colSku !== -1) {
                    let rows = table.querySelectorAll('tr');
                    for(let i = 1; i < rows.length; i++) {
                        let cells = rows[i].querySelectorAll('td');
                        if (cells.length > colSku) {
                            results.push({
                                sku: cells[colSku].innerText,
                                length: (colLen !== -1 && cells.length > colLen) ? cells[colLen].innerText : "",
                                color: (colColor !== -1 && cells.length > colColor) ? cells[colColor].innerText : "",
                                flow: (colFlow !== -1 && cells.length > colFlow) ? cells[colFlow].innerText : "",
                                row_full: rows[i].innerText
                            });
                        }
                    }
                }
            });
            return results;
        }""")

        items = []
        for item in table_data:
            sku_match = re.search(r'(\d{3}[ \u00A0]?\d{3})', item['sku'])
            if not sku_match: continue
            sku = sku_match.group(1).replace(" ", "").replace("\u00A0", "")
            
            # URČENÍ PARAMETRŮ
            length = item['length'].strip()
            if not length:
                m_len = re.search(r'\b(750|800|900|1000|1200)\b', item['row_full'])
                if m_len: length = m_len.group(1)
            
            color = item['color'].strip().replace("\n", " ")
            material = "Edelstahl V4A" if "v4a" in color.lower() or "1.4404" in color.lower() or "v4a" in item['row_full'].lower() else "Edelstahl V2A"
            flow = item['flow'].strip() if item['flow'] else global_flow

            items.append({
                "Component_SKU": sku, "Manufacturer": "Viega", "Product_Name": h1_text,
                "Tech_Source_URL": url, "Datasheet_URL": pdf_link, "Flow_Rate_l_s": flow,
                "Length_mm": length, "Color": color, "Material_V4A": material,
                "Cert_EN1253": "Yes", "Cert_EN18534": "Yes", 
                "Is_Cuttable": "Yes" if any(x in h1_text for x in ["Vario", "Cleviva"]) else "No"
            })
            print(f"      ✅ [SKU: {sku}] L: {length or '--'} | Barva: {color}", file=sys.stderr)
        return items

    def run(self):
        print("\n" + "="*60)
        print("🕵️ KROK 1: Viega Ultra Discovery (Motor Greedy + Cleanup)")
        print("="*60 + "\n", file=sys.stderr)

        all_collected = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for start_url in self.target_urls:
                print(f"\n📂 Otevírám: {start_url.split('/')[-1]}", file=sys.stderr)
                try:
                    page.goto(start_url, timeout=60000)
                    time.sleep(2)
                    
                    # SCROLL PRO LAZY LOAD
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)

                    # ROZCESTNÍK LOGIKA
                    is_rozcestnik = any(rozc in start_url for rozc in ["Tempoplex.html", "4982-10", "4982-20", "Zubehoer"])
                    if is_rozcestnik:
                        links = page.locator("a[href*='/Katalog/']").all()
                        model_urls = []
                        for l in links:
                            href = l.get_attribute("href")
                            if href and ".html" in href:
                                full_url = "https://www.viega.de" + href if href.startswith("/") else href
                                if full_url != start_url: model_urls.append(full_url)
                        
                        for m_url in list(set(model_urls))[:15]: # Proklid až 15 podmodelů
                            try:
                                page.goto(m_url)
                                time.sleep(1.5)
                                h1 = page.locator("h1").first.inner_text().strip()
                                all_collected.extend(self.extract_rich_data(page, m_url, h1))
                            except: pass
                    else:
                        h1 = page.locator("h1").first.inner_text().strip()
                        all_collected.extend(self.extract_rich_data(page, start_url, h1))
                except Exception as e:
                    print(f"   ❌ Chyba: {e}", file=sys.stderr)
            browser.close()

        if all_collected:
            df_new = pd.DataFrame(all_collected).drop_duplicates(subset=['Component_SKU'])
            if os.path.exists(self.excel_path):
                # KLÍČOVÉ: Nejdřív načteme vše, pak vymažeme jen Viegu
                df_old = pd.read_excel(self.excel_path, sheet_name="Products_Tech")
                df_others = df_old[df_old['Manufacturer'].astype(str).str.strip() != 'Viega']
                df_final = pd.concat([df_others, df_new], ignore_index=True)
            else:
                df_final = df_new

            with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df_final.to_excel(writer, sheet_name="Products_Tech", index=False)
            print(f"\n✅ HOTOVO! Nalezeno {len(df_new)} unikátních Viega kódů.")
        else:
            print("\n❌ Žádná data nenalezena.")

if __name__ == "__main__":
    ViegaUltraDiscovery().run()