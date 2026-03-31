from playwright.sync_api import sync_playwright
from models.product import Product
import re

class MegabadScraper:
    def __init__(self):
        pass

    def scrape(self, url: str):
        print(f"🔄 Zpracovávám: Megabad...")
        print(f"🕵️‍♂️ Startuji misi na: {url}")
        
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(url, timeout=60000)
                
                # 1. Název
                title = "Neznámý produkt"
                if page.locator("h1").count() > 0:
                    title = page.locator("h1").first.text_content().strip()
                print(f"📦 Název: {title}")

                # 2. Cena
                price_element = page.locator(".price-container .price").first
                price_text = ""
                
                if price_element.count() > 0:
                    price_text = price_element.text_content()
                else:
                    body_text = page.locator("body").inner_text()
                    match = re.search(r'(\d{1,4}[.,]\d{2})\s*€', body_text)
                    if match:
                        price_text = match.group(1)

                clean_price = price_text.replace("€", "").replace("*", "").strip()
                clean_price = clean_price.replace(".", "").replace(",", ".")
                
                try:
                    final_price = float(clean_price)
                    print(f"✅ Cena po slevě: {final_price} EUR")
                except:
                    final_price = 0.0

                # 3. Původní cena
                original_price = None
                try:
                    uvp_el = page.locator(".old-price").first
                    if uvp_el.count() > 0:
                        uvp_text = uvp_el.text_content().replace("€", "").replace("UVP", "").strip()
                        uvp_clean = uvp_text.replace(".", "").replace(",", ".")
                        original_price = float(uvp_clean)
                except:
                    pass

                if final_price > 0:
                    # Explicitně uvedeme složení
                    breakdown = "Jednotná cena (Kompletní produkt)"
                    
                    product = Product(
                        name=title,
                        price=final_price,
                        original_price=original_price if original_price and original_price > final_price else None,
                        url=url,
                        price_breakdown=breakdown  # Zde to doplňujeme
                    )
                    results.append(product)

            except Exception as e:
                print(f"💥 Chyba: {e}")
            finally:
                browser.close()
        
        return results