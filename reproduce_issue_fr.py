from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import time

# Regex from scraper.py
def parse_specs(text):
    # Normalize unicode spaces (NBSP)
    text = text.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    text = text.lower()
    specs = {
        "ram": None,
        "ssd": None,
        "chip": None,
        "screen": None,
        "device_type": "Mac"
    }
    
    # RAM
    ram_patterns = [
        # Added (?:de\s+)? to handle "16 Go de mémoire unifiée"
        r'(\d+)\s*(?:gb|go)\s*(?:de\s+)?(?:unified memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|zunifikowanej\s*pamięci|pamięć\s*ram|centraal\s*geheugen|geheugen)',
        r'(\d+)\s*(?:gb|go)\s*(?:ram|memory|arbeitsspeicher|mémoire|pamięć|geheugen)',
        r'(\d+)\s*(?:gb|go)', # Fallback
    ]
    
    for pattern in ram_patterns[:2]:
         ram_match = re.search(pattern, text)
         if ram_match:
             specs['ram'] = int(ram_match.group(1))
             break
    
    if specs['ram'] is None:
        pass # Fallback logic in scraper.py was empty/pass

    # SSD
    # Try specific Polish/Short format "SSD 256 GB" FIRST
    ssd_match = re.search(r'ssd\s+(\d+)\s*(?:gb|go|tb|to)', text)

    if not ssd_match:
        # Dutch/Reverse style: "SSD van 256 GB" -> Now handles "SSD de 256 Go"
        ssd_match = re.search(r'(?:ssd|opslag|stockage)\s*(?:van|de|von|z)\s*(\d+)\s*(?:gb|go|tb|to)', text)
        
    if not ssd_match:
        # Fallback to generic "NUM GB ... SSD"
        ssd_match = re.search(r'(\d+)\s*(?:gb|go|tb|to)\s*(?:ssd|stockage|opslag|almacenamiento|lagring|úložiště|pamięci masowej)', text)
        
    if ssd_match:
        val = int(ssd_match.group(1))
        full_match = ssd_match.group(0)
        if 'tb' in full_match or 'to' in full_match:
            val *= 1024
        specs['ssd'] = val
        
    return specs, text

def debug_fr():
    url = "https://www.apple.com/fr/shop/refurbished/mac"
    print(f"Connecting to {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        
        # Scroll a bit
        page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(1)
        
        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')
        tiles = soup.select('.rf-refurb-producttile')
        
        print(f"Found {len(tiles)} tiles.")
        
        # Check first 5 tiles
        for i, tile in enumerate(tiles[:5]):
            title_elem = tile.select_one('h3 a')
            if not title_elem: continue
            
            name = title_elem.get_text(strip=True)
            print(f"\n--- Product {i+1}: {name} ---")
            
            raw_text = tile.get_text(" ", strip=True)
            specs, _ = parse_specs(raw_text)
            print(f"Tile Search: RAM={specs['ram']}, SSD={specs['ssd']}")
            
            if specs['ram'] is None or specs['ssd'] is None:
                print("  -> Missing info, visiting page...")
                url_prod = "https://www.apple.com" + title_elem['href']
                
                try:
                    page_prod = browser.new_page()
                    page_prod.goto(url_prod)
                    prod_content = page_prod.content()
                    soup_prod = BeautifulSoup(prod_content, 'html.parser')
                    
                    # Selectors from scraper.py
                    selectors = [
                         '.rc-pdsection-panel.Overview-panel', 
                         '.rc-pdsection-panel.TechSpecs-panel', 
                         '.rf-tech-specs-section',
                         '.rf-pdp-title'
                    ]
                    
                    full_page_text = ""
                    for sel in selectors:
                        elements = soup_prod.select(sel)
                        for el in elements:
                            full_page_text += " " + el.get_text(" ", strip=True)
                    
                    if not full_page_text.strip():
                        full_page_text = soup_prod.get_text(" ", strip=True)
                        
                    print(f"  Page Text Sample (len={len(full_page_text)}): {full_page_text[:200]}...")
                    specs_new, _ = parse_specs(full_page_text)
                    print(f"  Page Search: RAM={specs_new['ram']}, SSD={specs_new['ssd']}")
                    
                    page_prod.close()
                    
                except Exception as e:
                    print(f"Error visiting page: {e}")
            
        browser.close()

if __name__ == "__main__":
    debug_fr()
