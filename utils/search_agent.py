from playwright.sync_api import sync_playwright
import time
import urllib.parse

class SearchAgent:
    def __init__(self):
        pass

    def find_url(self, site_domain, query):
        """
        Najde URL produktu pomocí DuckDuckGo.
        Příklad: site_domain="reuter.de", query="Kaldewei FlowLine Zero 900"
        """
        full_query = f"site:{site_domain} {query}"
        print(f"🕵️‍♂️ PÁTRAČ: Jdu na DuckDuckGo hledat: '{full_query}'...")
        
        found_url = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Pátrač může pracovat skrytě
            page = browser.new_page()
            
            try:
                # Jdeme na DuckDuckGo (je friendly k botům)
                # Použijeme HTML verzi, která je rychlejší a bez složitého JS
                encoded_query = urllib.parse.quote(full_query)
                ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
                
                page.goto(ddg_url, timeout=30000)
                
                # Hledáme první výsledek
                # Selektor pro odkaz ve výsledcích
                result_link = page.locator(".result__a").first
                
                if result_link.count() > 0:
                    found_url = result_link.get_attribute("href")
                    print(f"   🎯 Mám to! Nalezena URL: {found_url}")
                else:
                    print("   ❌ Pátrač nenašel žádný výsledek.")

            except Exception as e:
                print(f"   💥 Chyba při hledání: {e}")
            finally:
                browser.close()
        
        return found_url