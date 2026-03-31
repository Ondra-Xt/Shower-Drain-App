import sys
import json
import re
from playwright.sync_api import sync_playwright

def run():
    extracted_data = {}
    
    with sync_playwright() as p:
        # Browser Setup
        # Headless=False as requested
        # Try Firefox to bypass potential Chromium-specific issues
        browser = p.firefox.launch(headless=False)
        # CRITICAL: Viewport setup 1920x1080
        # Set a real user agent to avoid potential bot detection/JS errors
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Set cookies to avoid location/language issues
            context.add_cookies([
                {"name": "siterecom", "value": "de", "domain": ".hansgrohe.de", "path": "/"},
                {"name": "isSitechosen", "value": "true", "domain": ".hansgrohe.de", "path": "/"}
            ])

            print("Navigating to https://www.hansgrohe.de/...", file=sys.stderr)
            page.goto("https://www.hansgrohe.de/")

            # Cookie Consent
            print("Handling cookie consent...", file=sys.stderr)
            try:
                # Wait for banner. User provided ID.
                # Also try finding by text "Alle akzeptieren" which is more robust if ID changes
                accept_btn = page.locator("#onetrust-accept-btn-handler").or_(page.get_by_role("button", name="Alle akzeptieren")).first
                if accept_btn.is_visible():
                    accept_btn.click()
                    print("Cookie consent accepted.", file=sys.stderr)
                else:
                    print("Cookie banner not visible or not found.", file=sys.stderr)
            except Exception as e:
                print(f"Cookie consent warning (might be absent or different): {e}", file=sys.stderr)

            # Search Interaction
            print("Starting search interaction...", file=sys.stderr)
            try:
                print(f"Current URL: {page.url}", file=sys.stderr)
                # Attempt to find the search icon/button in the header
                # Strategy:
                # 1. Avoid "Partner" or "Händler"
                # 2. Look for "Suche" or icon
                
                search_clicked = False
                
                # Helper to check if button is valid
                def is_valid_search_btn(loc):
                    if not loc.is_visible(): return False
                    txt = (loc.text_content() or "").lower()
                    title = (loc.get_attribute("title") or "").lower()
                    aria = (loc.get_attribute("aria-label") or "").lower()
                    combined = txt + title + aria
                    if "partner" in combined or "händler" in combined:
                        return False
                    return True

                # Potential selectors
                potential_selectors = [
                    "header button.search-toggle",
                    "header .icon-search", 
                    "header .icon-magnifier",
                    "header [data-icon='search']",
                    "header button[title='Suche']",
                    "header a[title='Suche']", # Might be dealer search, checked by is_valid
                    "header button"
                ]

                found_btn = None
                for sel in potential_selectors:
                    locs = page.locator(sel).all()
                    for loc in locs:
                        if is_valid_search_btn(loc):
                            found_btn = loc
                            print(f"Found search button: {sel}", file=sys.stderr)
                            break
                    if found_btn: break
                
                if found_btn:
                    found_btn.click()
                    search_clicked = True
                else:
                    print("Could not find a specific search button. Trying generic fallback.", file=sys.stderr)
                
                if not search_clicked:
                    # Last resort: Try to find the magnifying glass icon specifically if possible, 
                    # usually it's a pseudo element or background, or an svg.
                    # Let's assume one of the above worked. If not, we might error out on the wait_for_selector below.
                    print("Warning: Could not definitively identify search button. Trying generic click if visible.", file=sys.stderr)

                # CRITICAL: Explicitly wait for input[type='search']
                print("Waiting for search input...", file=sys.stderr)
                search_input_selector = "input[type='search']"
                
                # Verify if click caused navigation
                page.wait_for_timeout(1000)
                if page.url != "https://www.hansgrohe.de/":
                     print(f"Navigated to: {page.url}", file=sys.stderr)
                
                # Wait for it to be visible
                try:
                    # Try generic input if specific type='search' fails
                    # Exclude partnerfinder
                    # Found input in debug: <input type="text" class="js-searchbar-input" name="text">
                    search_input = page.locator("input.js-searchbar-input").or_(page.locator("input[name='text']")).or_(page.locator("input[type='search']:not([id*='partner'])")).first
                    search_input.wait_for(state="visible", timeout=10000)
                    search_input_selector = search_input # Use the locator directly
                except:
                     print("Search input not visible. Dumping all inputs...", file=sys.stderr)
                     inputs = page.locator("input").all()
                     for inp in inputs:
                         if inp.is_visible():
                             print(f"Visible Input: HTML={inp.evaluate('el => el.outerHTML')}", file=sys.stderr)
                     print("Dumping body start...", file=sys.stderr)
                     print(page.locator("body").inner_html()[:500], file=sys.stderr)
                     raise

                # Type SKU and Enter
                target_sku = "56034000"
                product_name = "RainDrain Rock"
                
                print(f"Typing SKU {target_sku}...", file=sys.stderr)
                search_input_selector.fill(target_sku)
                page.wait_for_timeout(500)
                search_input_selector.press("Enter")
                
                # Wait for navigation or results
                print("Waiting for search results...", file=sys.stderr)
                try:
                    # Wait for URL to contain "search" or "suche" or "find"?
                    # Or wait for a result item.
                    # Hansgrohe search URL usually contains query.
                    page.wait_for_url(lambda u: "56034000" in u or "search" in u or "suche" in u, timeout=10000)
                except:
                    print("URL did not change to search results. Trying to click submit button if available.", file=sys.stderr)
                    # Try to find submit button near input
                    # Input is inside a form?
                    # Let's try to find a button type=submit
                    search_input_selector.locator("xpath=..").locator("button[type='submit'], .search-submit").click()
                    page.wait_for_timeout(2000)

                print(f"Current URL after search: {page.url}", file=sys.stderr)

            except Exception as e:
                print(f"Error during search interaction: {e}", file=sys.stderr)
                # Dump header HTML for debugging if search failed
                try:
                    print(f"Header HTML dump: {page.locator('header').inner_html()[:500]}", file=sys.stderr)
                except:
                    pass
                raise e

            # Results Page
            print("Processing results...", file=sys.stderr)
            page.wait_for_load_state("domcontentloaded")
            
            # Find first valid product link (ignore PDF)
            # We want a link that is likely a product page.
            # Strategy: Get all links in main content area.
            
            # Wait for results to appear
            print("Waiting for results...", file=sys.stderr)
            try:
                # Wait for something that looks like a result
                # Try common selectors
                page.wait_for_selector(".result-list, .product-list, .search-results, .c-product-tile", timeout=10000)
            except:
                print("Timeout waiting for specific results container. Checking page content...", file=sys.stderr)
                if "56034000" in page.content():
                    print("SKU found in page content!", file=sys.stderr)
                else:
                    print("SKU NOT found in page content. Search might have failed.", file=sys.stderr)

            valid_link_selector = None
            
            # We iterate through links in the main content
            # Strategy: look for SKU in text first, then generic product link
            # Hansgrohe search results usually have a class for results items
            
            # Try to find specific result items first
            potential_result_containers = [
                ".search-results .result-item a",
                ".product-list .product-item a",
                ".results-list li a",
                "main .teaser a" # Common for product teasers
            ]

            found_links = []
            
            # First pass: Look for SKU in any link in main or results container
            # Try to find the results container
            results_container = page.locator(".result-list").or_(page.locator(".product-list")).or_(page.locator(".search-results")).or_(page.locator("main")).first
            
            main_links = results_container.locator("a").all()
            print(f"Found {len(main_links)} links in results container. Scanning...", file=sys.stderr)
            
            if len(main_links) < 5:
                # Try clicking "Suchen" button on the search page if present
                search_btn_on_page = page.locator(".search-field__btn").first
                if search_btn_on_page.is_visible():
                     print("Clicking 'Suchen' button on search page...", file=sys.stderr)
                     search_btn_on_page.click()
                     page.wait_for_timeout(3000)
                     # Re-scan
                     main_links = results_container.locator("a").all()
                     print(f"Found {len(main_links)} links after clicking Suchen.", file=sys.stderr)

            # Check for SKU link
            sku_link = None
            def find_sku_link(links):
                for link in links:
                    if not link.is_visible(): continue
                    href = link.get_attribute("href")
                    txt = (link.text_content() or "").strip()
                    if not href: continue
                    if href.lower().endswith(".pdf"): continue
                    
                    if "56034000" in txt or "56034000" in href:
                        print(f"Found SKU match: {txt} -> {href}", file=sys.stderr)
                        return link
                return None

            sku_link = find_sku_link(main_links)

            # Fallback search if SKU not found
            if not sku_link:
                print("SKU not found with initial search. Trying generic search term 'RainDrain Rock'...", file=sys.stderr)
                # Find input on results page (likely .js-searchbar-input)
                fallback_input = page.locator("input.js-searchbar-input").first
                if fallback_input.is_visible():
                    fallback_input.fill("RainDrain Rock")
                    fallback_input.press("Enter")
                    page.wait_for_timeout(3000) # Wait for new results
                    
                    # Re-scan
                    main_links = results_container.locator("a").all()
                    print(f"Found {len(main_links)} links after fallback search.", file=sys.stderr)
                    sku_link = find_sku_link(main_links)
                else:
                    print("Could not find search input for fallback.", file=sys.stderr)
            
            if sku_link:
                valid_link_selector = sku_link
            else:
                 # Second pass: Look for specific result containers
                 for sel in potential_result_containers:
                     items = page.locator(sel).all()
                     for link in items:
                         if not link.is_visible(): continue
                         href = link.get_attribute("href")
                         if href and not href.lower().endswith(".pdf"):
                             valid_link_selector = link
                             print(f"Found result via container '{sel}': {link.get_attribute('href')}", file=sys.stderr)
                             break
                     if valid_link_selector: break
            
            # Third pass: Just the first reasonable link in main that isn't navigation?
            if not valid_link_selector:
                # Filter out obvious navigation links (e.g. "Home", "Kueche", "Bad")
                # This is hard without knowing structure.
                # Let's use the first link that contains "produkt" in href or is deep
                for link in main_links:
                    if not link.is_visible(): continue
                    href = link.get_attribute("href")
                    txt = (link.text_content() or "").strip()
                    if not href or href.lower().endswith(".pdf"): continue
                    
                    # Heuristics
                    if "/articledetail-" in href or "/produkt/" in href or "raindrain" in txt.lower():
                        valid_link_selector = link
                        print(f"Found result via heuristic: {txt} -> {href}", file=sys.stderr)
                        break

            # Fallback: Original logic (first visible link in main)
            if not valid_link_selector:
                 print("Using fallback (first link in main)...", file=sys.stderr)
                 for link in main_links:
                     href = link.get_attribute("href")
                     if href and not href.lower().endswith(".pdf") and link.is_visible():
                          if len((link.text_content() or "").strip()) > 5: # Avoid tiny links
                              valid_link_selector = link
                              break
            
            if not valid_link_selector:
                print("No valid product link found in results.", file=sys.stderr)
                # Dump links found for debugging
                for l in main_links[:5]:
                    print(f"Link: {l.get_attribute('href')}", file=sys.stderr)
                raise Exception("No product link found")

            print(f"Clicking result: {valid_link_selector.get_attribute('href')}", file=sys.stderr)
            valid_link_selector.click()
            
            # Product Page
            print("Loaded product page. Extracting data...", file=sys.stderr)
            page.wait_for_load_state("domcontentloaded")
            
            # Expand "Technische Daten"
            # Try to find a button or section with "Technische Daten"
            try:
                # Look for a button or summary that contains "Technische Daten"
                tech_label = page.get_by_text("Technische Daten", exact=False)
                if tech_label.count() > 0:
                    # It might be a button or inside a button
                    target = tech_label.first
                    # Walk up to find clickable if needed, or just click.
                    # Often accordion headers are clickable.
                    if target.is_visible():
                        target.click()
                        page.wait_for_timeout(500) # Wait for expansion
            except Exception as e:
                print(f"Info: Could not click 'Technische Daten' (might be open or not found): {e}", file=sys.stderr)
            
            # Get Full Text
            full_text = page.locator("body").text_content()
            # Normalize whitespace
            full_text = re.sub(r'\s+', ' ', full_text)

            # --- Data Extraction ---
            
            # 1. Color Count
            # "Prioritize counting actual interactive color elements"
            # Look for common selectors for color swatches
            color_count = 0
            # Selectors for swatches
            swatch_selectors = [
                ".product-detail-page__swatches input", 
                ".swatches__option", 
                "[class*='color-selector']", 
                "[class*='surface-selector']",
                ".variants input[type='radio']"
            ]
            
            found_swatches = False
            for sel in swatch_selectors:
                elements = page.locator(sel)
                count = elements.count()
                if count > 0:
                    color_count = count
                    found_swatches = True
                    print(f"Found {count} colors using selector '{sel}'", file=sys.stderr)
                    break
            
            if not found_swatches:
                # Fallback: Regex for "X Oberflächen"
                match = re.search(r"(\d+)\s*Oberflächen", full_text, re.IGNORECASE)
                if match:
                    color_count = int(match.group(1))
                    print(f"Found {color_count} colors using regex", file=sys.stderr)

            extracted_data["color_count"] = color_count

            # 2. Flow Rate
            # "Ablaufleistung", "l/s", or "l/min"
            # Need to capture value and unit.
            # Example text: "Ablaufleistung 0,8 l/s" or "up to 48 l/min"
            # Regex to find number near keywords
            # Allowing for comma or dot decimal
            flow_regex = re.compile(r"(?:Ablaufleistung|Flow rate).*?([\d.,]+)\s*(l/s|l/min)", re.IGNORECASE)
            match = flow_regex.search(full_text)
            
            if match:
                val_str = match.group(1).replace(",", ".")
                unit = match.group(2).lower()
                try:
                    val = float(val_str)
                    if unit == "l/min":
                        val = val / 60.0
                    extracted_data["flow_rate"] = f"{val:.2f}"
                except ValueError:
                    extracted_data["flow_rate"] = None
            else:
                # Try simpler search just for l/s or l/min if specific keyword missing?
                # Risk of capturing wrong thing. 
                # Let's try searching for l/s or l/min with a number preceding
                match_generic = re.search(r"([\d.,]+)\s*(l/s|l/min)", full_text, re.IGNORECASE)
                if match_generic:
                     val_str = match_generic.group(1).replace(",", ".")
                     unit = match_generic.group(2).lower()
                     try:
                        val = float(val_str)
                        if unit == "l/min":
                            val = val / 60.0
                        extracted_data["flow_rate"] = f"{val:.2f}"
                     except:
                        extracted_data["flow_rate"] = None
                else:
                    extracted_data["flow_rate"] = None

            # 3. material_v4a
            # "1.4404" or "V4A" -> Yes, else No (Standard)
            if re.search(r"1\.4404|V4A", full_text, re.IGNORECASE):
                extracted_data["material_v4a"] = "Yes"
            else:
                extracted_data["material_v4a"] = "No (Standard)"

            # 4. cert_en1253
            extracted_data["cert_en1253"] = "Yes" if "EN 1253" in full_text else "No"

            # 5. cert_en18534
            extracted_data["cert_en18534"] = "Yes" if "18534" in full_text else "No"

            # 6. height_adjustability
            # "Bauhöhe", "Einbauhöhe" ... range in mm
            # Example: "Bauhöhe: 70 - 120 mm"
            height_match = re.search(r"(?:Bauhöhe|Einbauhöhe|Height).*?(\d+\s*-\s*\d+)\s*mm", full_text, re.IGNORECASE)
            if height_match:
                extracted_data["height_adjustability"] = f"{height_match.group(1)} mm"
            else:
                 extracted_data["height_adjustability"] = None

            # 7. outlet_direction
            # "waagerecht" or "senkrecht"
            dirs = []
            if "waagerecht" in full_text.lower():
                dirs.append("waagerecht")
            if "senkrecht" in full_text.lower():
                dirs.append("senkrecht")
            
            if dirs:
                extracted_data["outlet_direction"] = "/".join(dirs)
            else:
                extracted_data["outlet_direction"] = None

            # 8. sealing_fleece
            # "Dichtvlies" or "werkseitig"
            # Debug: check if text exists
            if re.search(r"Dichtvlies|werkseitig|pre-mounted sealing membrane", full_text, re.IGNORECASE):
                extracted_data["sealing_fleece"] = "Yes"
            else:
                extracted_data["sealing_fleece"] = "No"

            # Print ONLY JSON to stdout
            print(json.dumps(extracted_data, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    run()
