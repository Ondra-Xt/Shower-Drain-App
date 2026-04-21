from playwright.sync_api import sync_playwright
import time
import re
import os

def debug_run():
    sku = "56040800" # Testovací SKU
    if not os.path.exists("debug_tech"): os.makedirs("debug_tech")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Nastavíme viewport na Full HD, aby web vypadal jako na PC
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        print(f"🔍 DIAGNOSTIKA v2 pro SKU: {sku}")
        print("   Jdu na Hansgrohe.de...")
        page.goto("https://www.hansgrohe.de/")
        
        # Cookies
        try: 
            page.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            print("   Cookies potvrzeny.")
        except: pass
        
        # Hledání
        print("   Otevírám hledání...")
        page.locator("header .icon-search, header button[title='Suche']").first.click(force=True)
        time.sleep(1) # Čekání na animaci
        
        print(f"   Píšu SKU {sku}...")
        inp = page.locator("input.js-searchbar-input, input[type='search']").first
        inp.fill(sku)
        inp.press("Enter")
        
        print("   Čekám na výsledky...")
        page.wait_for_load_state("networkidle") # Čekáme, až se dotahají data
        time.sleep(3)
        
        # Screenshot výsledků (PRO KONTROLU)
        page.screenshot(path="debug_tech/search_results.png")
        print("   📸 Screenshot výsledků uložen do 'debug_tech/search_results.png'")
        
        # Hledání odkazu - VELMI VOLNÝ SELEKTOR
        # Hledáme jakýkoliv odkaz, který má v adrese 'articledetail'
        links = page.locator("main a[href*='articledetail']").all()
        
        print(f"   ℹ️ Na stránce nalezeno {len(links)} odkazů na produkty.")
        
        target_link = None
        # Zkusíme najít ten nejlepší
        for link in links:
            url = link.get_attribute("href")
            text = link.inner_text().strip()
            print(f"      Nalezeno: {text[:30]}... -> {url}")
            
            # Pokud odkaz obsahuje SKU nebo je to první relevantní, bereme ho
            if sku in url or sku in text:
                target_link = link
                break
        
        # Pokud jsme nenašli podle SKU, vezmeme první, co není PDF
        if not target_link and links:
            for link in links:
                if not link.get_attribute("href").endswith(".pdf"):
                    target_link = link
                    break
        
        if target_link:
            url = target_link.get_attribute("href")
            print(f"   👉 KLIKÁM NA: {url}")
            target_link.click(force=True)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(3)
            
            # Jsme na detailu. Teď zkusíme najít Technická data.
            # Hledáme tlačítko pro rozbalení
            print("   Hledám sekci 'Technische Daten'...")
            
            # Zkusíme najít text v obsahu
            tech_text_loc = page.get_by_text(re.compile("Technische Daten|Product attributes", re.IGNORECASE))
            
            if tech_text_loc.count() > 0:
                print("   Sekce nalezena. Zkouším rozkliknout (pokud je to tlačítko)...")
                try:
                    tech_text_loc.first.click(force=True, timeout=2000)
                    time.sleep(1)
                except: 
                    print("   (Možná to není tlačítko nebo už je otevřeno)")
            
            # Screenshot detailu
            page.screenshot(path="debug_tech/product_detail.png")
            
            # Vytáhneme text celé stránky a hledáme klíčová slova
            body_text = page.locator("body").inner_text()
            
            print("\n--- TEST REGEXU (Co vidí robot?) ---")
            
            # Hledáme Werkstoff
            m_mat = re.search(r"(?:Werkstoff|Material)[\s:]*([^\n\r]+)", body_text, re.IGNORECASE)
            if m_mat: print(f"   [MATERIÁL] Regex našel: '{m_mat.group(1).strip()}'")
            else: print("   [MATERIÁL] Regex nenašel nic.")
            
            # Hledáme Ablaufleistung
            m_flow = re.search(r"(?:Ablauf|Flow).*?([\d.,]+)\s*(l/s|l/min)", body_text, re.IGNORECASE)
            if m_flow: print(f"   [PRŮTOK] Regex našel: '{m_flow.group(1)} {m_flow.group(2)}'")
            else: print("   [PRŮTOK] Regex nenašel nic.")

            # Uložíme HTML pro analýzu (pokud regex selhal)
            with open("debug_tech/product_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("\n✅ HTML stránky uloženo do 'debug_tech/product_page.html' pro analýzu.")

        else:
            print("❌ Žádný použitelný odkaz na produkt nebyl nalezen.")

        browser.close()

if __name__ == "__main__":
    debug_run()