from scrapers.reuter_scraper import ReuterScraper

def main():
    # SEM VLOŽ TU URL Z REUTER.DE:
    url = "https://www.reuter.de/p/kaldewei-flowline-zero-abdeckung-fuer-duschrinne/1579540182670668/1187791" # <-- Přepiš toto!
    
    print(f"Spouštím test Reuter...")
    scraper = ReuterScraper()
    results = scraper.scrape(url)
    
    if results:
        p = results[0]
        print("\n" + "="*30)
        print(f"🎉 VÝSLEDEK REUTER")
        print("="*30)
        print(f"Produkt:       {p.title}")
        print(f"Aktuální cena: {p.price} €")
        
        if p.original_price:
            diff = p.original_price - p.price
            sleva = round((1 - p.price / p.original_price) * 100)
            print(f"Původní cena:  {p.original_price} €")
            print(f"Sleva:         {sleva} % (-{diff:.2f} €)")
            
        print("="*30)
    else:
        print("\n😞 Nic jsem nenašel.")

if __name__ == "__main__":
    main()