from scrapers.megabad_scraper import MegabadScraper

def main():
    # Tady je ta SPRÁVNÁ, FUNKČNÍ URL, kterou jsi našel:
    url = "https://www.megabad.com/kaldewei-duschrinnen-flowline-zero-900-cm-a-2273697.htm"
    
    print(f"Spouštím test...")
    scraper = MegabadScraper()
    results = scraper.scrape(url)
    
    if results:
        p = results[0]
        print("\n" + "="*30)
        print(f"🎉 VÝSLEDEK BENCHMARKU")
        print("="*30)
        print(f"Produkt:       {p.title}")
        print(f"Aktuální cena: {p.price} €")
        
        if p.original_price:
            print(f"Původní cena:  {p.original_price} €")
            diff = p.original_price - p.price
            print(f"Ušetříte:      {diff:.2f} €")
            sleva = round((1 - p.price / p.original_price) * 100)
            print(f"Sleva:         {sleva} %")
        else:
            print("Původní cena:  Nenalezena (asi není v akci)")
            
        print("="*30)
    else:
        print("\n😞 Nic jsem nenašel (zkontroluj URL nebo Cookies).")

if __name__ == "__main__":
    main()