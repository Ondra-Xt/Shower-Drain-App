import pandas as pd
import time
import re
import sys
import os
import requests
from bs4 import BeautifulSoup

class ViegaGreedyMaster:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        # Kompletní seznam URL přesně podle vašeho originálu
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
            "https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Ablaeufe-fuer-Bade--und-Duschwannen/Tempoplex.html"
        ]

    def extract_rich_data(self, url):
        """Čtení tabulek bez prohlížeče pomocí BeautifulSoup."""
        try:
            r = requests.get(url, headers=self.headers, timeout=20)
            if r.status_code != 200: return []
            
            soup = BeautifulSoup(r.text, 'html.parser')
            h1_text = soup.find('h1').text.strip() if soup.find('h1') else "Neznámý produkt"
            
            pdf_link = ""
            pdf_tag = soup.find('a', href=re.compile(r'\.pdf'))
            if pdf_tag: pdf_link = "https://www.viega.de" + pdf_tag['href']

            body_text = soup.get_text()
            global_flow = ""
            m_flow = re.search(r'(\d+(?:,\d+)?)\s*l/s', body_text)
            if m_flow: global_flow = m_flow.group(1).replace(',', '.')

            items = []
            found_skus = set()
            
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if not rows: continue
                
                headers = [th.text.lower().strip() for th in rows[0].find_all(['th', 'td'])]
                col_sku = next((i for i, h in enumerate(headers) if any(x in h for x in ['artikel', 'art.-nr'])), -1)
                col_len = next((i for i, h in enumerate(headers) if any(x in h for x in ['länge', 'abmessung', ' l '])), -1)
                col_color = next((i for i, h in enumerate(headers) if any(x in h for x in ['ausführung', 'farbe', 'modell'])), -1)
                col_flow = next((i for i, h in enumerate(headers) if 'ablaufleistung' in h), -1)

                if col_sku == -1: continue

                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) <= col_sku: continue
                    
                    sku_raw = cells[col_sku].text.strip()
                    sku_match = re.search(r'([1-9]\d{2}[ \u00A0]?\d{3})', sku_raw)
                    if not sku_match: continue
                    
                    sku = sku_match.group(1).replace(" ", "").replace("\u00A0", "")
                    if sku in found_skus: continue
                    found_skus.add(sku)
                    
                    length = cells[col_len].text.strip() if col_len != -1 else ""
                    if not length:
                        m_len = re.search(r'\b(750|800|900|1000|1200)\b', row.get_text())
                        if m_len: length = m_len.group(1)
                    
                    color = cells[col_color].text.strip().replace("\n", " ") if col_color != -1 else ""
                    if not color:
                        if "4981-31" in url or "4965-32" in url: color = "Schwarz Matt"
                        elif "4981-32" in url: color = "Kupfer PVD"
                        elif "4981-50" in url: color = "Gold PVD"
                        elif "4981-60" in url: color = "Champagner PVD"
                        elif "4965-30" in url: color = "Edelstahl matt"
                        elif "4965-31" in url: color = "Edelstahl glänzend"
                        elif "Tempoplex" in h1_text: color = "Chrom"
                        else: color = "Standard Edelstahl"
                    
                    flow = cells[col_flow].text.strip() if col_flow != -1 else global_flow
                    material = "Edelstahl V4A" if any(x in color.lower() or x in row.get_text().lower() for x in ["v4a", "1.4404"]) else "Edelstahl V2A"

                    items.append({
                        "Article_Number_SKU": str(sku), "Brand": "Viega", "Product_Name": str(h1_text),
                        "Product_URL": str(url), "Datasheet_URL": str(pdf_link), "Flow_Rate_ls": str(flow),
                        "Length_mm": str(length), "Color": str(color), "Is_V4A": str(material),
                        "Cert_DIN_EN1253": "Yes", "Cert_DIN_18534": "Yes", 
                        "Is_Cuttable": "Yes" if any(x in h1_text for x in ["Vario", "Cleviva"]) else "No"
                    })
                    print(f"      ✅ SKU: {sku} | L: {length or '--'} | Barva: {color}", file=sys.stderr)
            return items
        except Exception as e:
            print(f"   ⚠️ Chyba extrakce: {e}", file=sys.stderr)
            return []

    def handle_rozcestnik(self, url):
        """Analyzuje pod-produkty v rozcestnících."""
        try:
            r = requests.get(url, headers=self.headers, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'/Katalog/'))
            sub_urls = []
            for a in links:
                href = a['href']
                full = "https://www.viega.de" + href if href.startswith("/") else href
                if ".html" in full and full != url:
                    if any(x in url for x in ["Tempoplex", "4982-10", "4982-20"]):
                        sub_urls.append(full)
            return list(set(sub_urls))[:20]
        except: return []

    def run(self):
        print("\n" + "="*60)
        print("🕵️ Viega Discovery - STABILNÍ CLOUD VERZE")
        print("="*60 + "\n", file=sys.stderr)

        all_collected = []
        for start_url in self.target_urls:
            print(f"📂 Zpracovávám: {start_url.split('/')[-1]}", file=sys.stderr)
            if any(x in start_url for x in ["Tempoplex.html", "4982-10.html", "4982-20.html"]):
                for s_url in self.handle_rozcestnik(start_url):
                    all_collected.extend(self.extract_rich_data(s_url))
            else:
                all_collected.extend(self.extract_rich_data(start_url))
            time.sleep(1)

        if all_collected:
            df_new = pd.DataFrame(all_collected)
            
            # --- FIX TYPŮ: Převod všeho na string dřív, než dojde ke spojení ---
            df_new = df_new.astype(str).replace(['nan', 'None'], '')

            if os.path.exists(self.excel_path):
                try:
                    # Načítáme existující soubor také striktně jako string
                    df_old = pd.read_excel(self.excel_path, sheet_name="Products_Tech", dtype=str)
                    df_old = df_old.replace(['nan', 'None'], '')
                    
                    df_final = pd.concat([df_old, df_new], ignore_index=True)
                    df_final.drop_duplicates(subset=['Article_Number_SKU'], keep='last', inplace=True)
                except Exception as e: 
                    print(f"⚠️ Problém s připojením starých dat: {e}", file=sys.stderr)
                    df_final = df_new
            else: 
                df_final = df_new

            # Finální pojistka před zápisem
            df_final = df_final.astype(str).replace(['nan', 'None'], '')

            # Zápis do Excelu
            # Pokud soubor neexistuje, 'mode' musí být 'w' (zajištěno v app.py, ale tady raději ošetříme)
            try:
                with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df_final.to_excel(writer, sheet_name="Products_Tech", index=False)
            except (FileNotFoundError, ValueError):
                with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                    df_final.to_excel(writer, sheet_name="Products_Tech", index=False)

            print(f"✅ HOTOVO! Uloženo {len(df_final)} celkových položek.")

if __name__ == "__main__":
    ViegaGreedyMaster().run()