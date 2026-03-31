import pandas as pd
from scrapers.megabad_scraper import MegabadScraper
from scrapers.hornbach_scraper import HornbachScraper
from scrapers.reuter_scraper import ReuterScraper
import time
from datetime import datetime

def run_benchmark():
    print("🚀 SPOUŠTÍM BENCHMARK AGENTA (Verze: Detailní kontrola)")
    print("=" * 60)

    targets = [
        {
            "shop": "Megabad",
            "scraper": MegabadScraper(),
            "url": "https://www.megabad.com/kaldewei-duschrinnen-flowline-zero-900-cm-a-2273697.htm"
        },
        {
            "shop": "Hornbach",
            "scraper": HornbachScraper(),
            "url": "https://www.hornbach.de/p/duschrinnerost-kaldewei-flowline-zero-2400-900-mm-schwarz-matt-940000010676/12028764/"
        },
        {
            "shop": "Reuter",
            "scraper": ReuterScraper(),
            # Pokud Reuter zlobí, zkus sem dát obecný link na kategorii, robot si to najde
            "url": "https://www.reuter.de/kaldewei-flowline-zero-abdeckung-fuer-duschrinne-a1183307.php" 
        }
    ]

    results_data = []

    for target in targets:
        shop_name = target["shop"]
        url = target["url"]
        scraper = target["scraper"]

        print(f"\n🔄 Zpracovávám: {shop_name}...")
        
        try:
            products = scraper.scrape(url)
            
            if products:
                product = products[0]
                print(f"   ✅ Cena: {product.price} EUR")
                if product.price_breakdown:
                    print(f"   🔍 Složení: {product.price_breakdown}")
                
                sleva_proc = 0
                if product.original_price and product.price and product.original_price > product.price:
                    sleva_proc = round((1 - product.price / product.original_price) * 100)

                results_data.append({
                    "E-shop": shop_name,
                    "Produkt": product.name,
                    "Cena (EUR)": product.price,
                    # Nový sloupec pro kontrolu
                    "Složení ceny": product.price_breakdown if product.price_breakdown else "Pouze hlavní produkt",
                    "Původní cena (EUR)": product.original_price if product.original_price else "-",
                    "Sleva (%)": f"{sleva_proc}%" if sleva_proc > 0 else "-",
                    "URL": url,
                    "Datum": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
            else:
                print(f"   ❌ {shop_name}: Nic nenalezeno.")
                
        except Exception as e:
            print(f"   💥 Chyba u {shop_name}: {e}")

    print("\n" + "=" * 60)
    
    if results_data:
        df = pd.DataFrame(results_data)
        df = df.sort_values(by="Cena (EUR)")
        
        print("📊 VÝSLEDNÁ TABULKA:")
        # Přidáme zobrazení sloupce 'Složení ceny'
        print(df[["E-shop", "Cena (EUR)", "Složení ceny", "Produkt"]].to_string(index=False))
        
        filename = f"benchmark_detail_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n💾 Uloženo do souboru: {filename}")
    else:
        print("😞 Žádná data.")

if __name__ == "__main__":
    run_benchmark()