from scrapers.hornbach_scraper import HornbachScraper

def main():
    # URL z tvého obrázku (černý rošt 900mm)
    url = "https://www.hornbach.de/p/duschrinnerost-kaldewei-flowline-zero-2400-900-mm-schwarz-matt-940000010676/12028764/"
    
    print(f"Spouštím test Hornbach...")
    scraper = HornbachScraper()
    results = scraper.scrape(url)
    
    if results:
        p = results[0]
        print("\n" + "="*30)
        print(f"🎉 VÝSLEDEK HORBACH")
        print("="*30)
        print(f"Produkt: {p.title}")
        print(f"Cena:    {p.price} €")
        print("="*30)
    else:
        print("\n😞 Nic jsem nenašel.")

if __name__ == "__main__":
    main()