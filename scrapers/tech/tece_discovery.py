import os
import re
import time
import requests
import pandas as pd
from playwright.sync_api import sync_playwright

try:
    import pdfplumber
except ImportError:
    print("⚠️ Knihovna pdfplumber nenalezena. (Nainstalujte ji pomocí: python -m pip install pdfplumber)")

class TeceDiscovery:
    def __init__(self, excel_path="benchmark_master_v3_fixed.xlsx"):
        self.excel_path = excel_path
        self.base_url = "https://www.tece.com"
        self.pdf_dir = "tece_pdfs"

        if not os.path.exists(self.pdf_dir):
            os.makedirs(self.pdf_dir)

        self.category_urls = [
            "https://www.tece.com/de/entwaesserungstechnik/duschrinne-tecedrainline",
            "https://www.tece.com/de/entwaesserungstechnik/duschrinne-tecedrainprofile",
            "https://www.tece.com/de/entwaesserungstechnik/punktablauf-tecedrainpoint-s",
            "https://www.tece.com/de/entwaesserungstechnik/tecedrainway"
        ]

        self.cols_tech = [
            "Brand", "Product_Name", "Article_Number_SKU", "Product_URL",
            "Length_mm", "Is_Cuttable", "Flow_Rate_ls", "Outlet_Type",
            "Is_Outlet_Selectable", "Height_Min_mm", "Height_Max_mm",
            "Material_Body", "Is_V4A", "Fleece_Preassembled",
            "Cert_DIN_EN1253", "Cert_DIN_18534", "Colors_Count",
            "Tile_In_Possible", "Wall_Installation", "Completeness_Type",
            "Ref_Price_Estimate_EUR", "Datasheet_URL", "Evidence_Text"
        ]

    def ensure_excel_exists(self):
        if not os.path.exists(self.excel_path):
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                pd.DataFrame(columns=self.cols_tech).to_excel(writer, sheet_name='Products_Tech', index=False)

    def handle_cookies(self, page):
        try:
            page.locator("button:has-text('Alle akzeptieren'), a:has-text('Alle akzeptieren')").click(timeout=2000)
        except: pass

    def run(self):
        self.ensure_excel_exists()
        print("🕵️‍♂️ Spouštím TECE PDF Discovery & Mining (Chytré čtení po řádcích)...")
        all_data = []

        try:
            import pdfplumber
        except ImportError:
            print("❌ Zastavuji: Nemáte nainstalovaný pdfplumber.")
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for cat_url in self.category_urls:
                download_url = f"{cat_url}/downloads"
                print(f"\n📂 Prohledávám sekci: {download_url.split('/')[-2]}/downloads")
                
                try:
                    page.goto(download_url, timeout=60000)
                    self.handle_cookies(page)
                    time.sleep(3) 

                    links = page.locator("a").all()
                    detail_pages = set()

                    for link in links:
                        href = link.get_attribute("href")
                        if href and "/service/" in href.lower():
                            full_url = self.base_url + href if href.startswith("/") else href
                            detail_pages.add(full_url)

                    print(f"   🔍 Nalezeno {len(detail_pages)} podstránek. Prohledávám...")
                    found_pdfs = set()

                    for detail_url in detail_pages:
                        try:
                            page.goto(detail_url, timeout=30000)
                            time.sleep(1.5)
                            pdf_links = page.locator("a[href*='.pdf']").all()
                            for pdf_link in pdf_links:
                                pdf_href = pdf_link.get_attribute("href")
                                if pdf_href:
                                    final_pdf_url = self.base_url + pdf_href if pdf_href.startswith("/") else pdf_href
                                    found_pdfs.add(final_pdf_url)
                        except: pass

                    print(f"✅ Extrahováno {len(found_pdfs)} PDF odkazů.")

                    for pdf_url in found_pdfs:
                        local_path = self.download_pdf(pdf_url)
                        if local_path:
                            extracted = self.extract_data_from_pdf(local_path, pdf_url)
                            if extracted:
                                all_data.extend(extracted)
                except Exception as e:
                    print(f"❌ Chyba u kategorie {cat_url}: {e}")

            browser.close()

        if all_data:
            self.save_to_excel(all_data)
        else:
            print("❌ Nepodařilo se vytěžit žádná data z PDF.")

    def download_pdf(self, url):
        try:
            filename = url.split("/")[-1].split("?")[0]
            path = os.path.join(self.pdf_dir, filename)
            
            if os.path.exists(path):
                return path 
            
            print(f"   ⬇️ Stahuji: {filename[:30]}...")
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                with open(path, "wb") as f:
                    f.write(response.content)
                return path
            return None
        except: return None

    def extract_data_from_pdf(self, pdf_path, source_url):
        results = []
        filename = os.path.basename(pdf_path)
        print(f"   📖 Čtu tabulky a řádky: {filename[:30]}...")
        
        import pdfplumber
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # 1. Zkusíme najít globální průtok v úvodu dokumentu
                doc_flow_rate = "TBD"
                intro_text = ""
                for page in pdf.pages[:3]:
                    txt = page.extract_text()
                    if txt: intro_text += txt
                flow_match = re.search(r'(\d[.,]\d+)\s*l/s', intro_text)
                if flow_match:
                    doc_flow_rate = flow_match.group(1).replace(",", ".")

                found_skus = set()

                # 2. Čtení stránku po stránce (po řádcích)
                for i, page in enumerate(pdf.pages):
                    if i > 25: break # Ochrana před 200stránkovými katalogy
                    
                    text = page.extract_text()
                    if not text: continue
                    
                    lines = text.split('\n')
                    for line in lines:
                        # Najdeme SKU (Přesně 6 čísel začínajících 6kou)
                        sku_match = re.search(r'\b(6[0-9]{5})\b', line)
                        if sku_match:
                            sku = sku_match.group(1)
                            if sku in found_skus: continue # Už jsme ho našli v tomto PDF
                            
                            # Hledáme délku JEN na tom samém řádku jako je SKU
                            len_match = re.search(r'(\d{3,4})\s*mm', line)
                            length = len_match.group(1) if len_match else "TBD"
                            
                            # Název: Zkusíme vzít zbytek řádku bez čísla SKU
                            name_clean = re.sub(r'\b6[0-9]{5}\b', '', line).strip()
                            name_clean = re.sub(r'[^a-zA-ZäöüßÄÖÜ \-"]', '', name_clean) # Vyčistíme podivné znaky
                            name_clean = re.sub(r'\s+', ' ', name_clean).strip()[:60]
                            
                            if len(name_clean) < 3:
                                name_clean = f"TECE Komponent ({sku})"

                            results.append({
                                "Brand": "TECE",
                                "Product_Name": name_clean,
                                "Article_Number_SKU": sku,
                                "Product_URL": source_url,
                                "Length_mm": length,
                                "Is_Cuttable": "TBD",
                                "Flow_Rate_ls": doc_flow_rate,
                                "Outlet_Type": "TBD",
                                "Is_Outlet_Selectable": "TBD",
                                "Height_Min_mm": "",
                                "Height_Max_mm": "",
                                "Material_Body": "TBD",
                                "Is_V4A": "TBD",
                                "Fleece_Preassembled": "TBD",
                                "Cert_DIN_EN1253": "TBD",
                                "Cert_DIN_18534": "TBD",
                                "Colors_Count": 1,
                                "Tile_In_Possible": "TBD",
                                "Wall_Installation": "TBD",
                                "Completeness_Type": "Modular",
                                "Ref_Price_Estimate_EUR": 0,
                                "Datasheet_URL": source_url,
                                "Evidence_Text": f"PDF Řádek: {filename}"
                            })
                            found_skus.add(sku)
                            
        except Exception as e:
            print(f"      ⚠️ Chyba při čtení PDF: {e}")
        
        return results

    def save_to_excel(self, data):
        if not data: return
        df = pd.DataFrame(data)
        
        for col in self.cols_tech:
            if col not in df.columns:
                df[col] = ""
                
        df = df[self.cols_tech]
        
        print(f"💾 Ukládám {len(df)} preciznějších záznamů do Excelu...")
        with pd.ExcelWriter(self.excel_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
            try: start_row = writer.sheets['Products_Tech'].max_row
            except: start_row = 0
            df.to_excel(writer, sheet_name="Products_Tech", index=False, header=False, startrow=start_row)
        print("✅ TECE PDF Těžba úspěšně dokončena.")

if __name__ == "__main__":
    # --- OPRAVA: SPOLUHRÁT S HLAVNÍM EXCELEM ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
    MASTER_EXCEL = os.path.join(base_dir, "benchmark_master_v3_fixed.xlsx")
    
    bot = TeceDiscovery(excel_path=MASTER_EXCEL)
    bot.run()