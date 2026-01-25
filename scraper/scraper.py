from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
import time
import argparse

# Configuration
STORES = {
    "DE": {
        "url": "https://www.apple.com/de/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "IE": {
        "url": "https://www.apple.com/ie/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "NL": {
        "url": "https://www.apple.com/nl/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "FR": {
        "url": "https://www.apple.com/fr/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "PL": {
        "url": "https://www.apple.com/pl/shop/refurbished/mac",
        "currency_symbol": "zł",
        "currency_label": "PLN",
        "rate_to_eur": 0.23, # Approx
    },
    "AT": {
        "url": "https://www.apple.com/at/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "ES": {
        "url": "https://www.apple.com/es/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "PT": {
        "url": "https://www.apple.com/pt/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "CH": { # Swiss German
        "url": "https://www.apple.com/ch-de/shop/refurbished/mac",
        "currency_symbol": "CHF",
        "currency_label": "CHF",
        "rate_to_eur": 1.07, # Approx
    },
    "SE": {
        "url": "https://www.apple.com/se/shop/refurbished/mac",
        "currency_symbol": "kr",
        "currency_label": "SEK",
        "rate_to_eur": 0.088, # Approx
    },
    "DK": {
        "url": "https://www.apple.com/dk/shop/refurbished/mac",
        "currency_symbol": "kr.",
        "currency_label": "DKK",
        "rate_to_eur": 0.13, # Approx
    },
    "CZ": {
        "url": "https://www.apple.com/cz/shop/refurbished/mac",
        "currency_symbol": "Kč",
        "currency_label": "CZK",
        "rate_to_eur": 0.040, # Approx
    },
    "SI": { # Use standard EU structure, check validity later
        "url": "https://www.apple.com/si/shop/refurbished/mac",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    }
}

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
OUTPUT_FILE = "index.html"

def fetch_store_data(playwright, country_code, config):
    print(f"Fetching data for {country_code}...")
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    
    items = []
    
    try:
        page.goto(config['url'], timeout=60000)
        
        # Incremental scroll to trigger lazy loading
        for _ in range(10): 
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(0.5)
            
        content = page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Select product tiles
        tiles = soup.select('.rf-refurb-producttile')
        
        for tile in tiles:
            try:
                title_elem = tile.select_one('h3 a')
                if not title_elem:
                    continue
                    
                name = title_elem.get_text(strip=True)
                url = "https://www.apple.com" + title_elem['href']
                
                # Image
                img_elem = tile.select_one('img')
                image = img_elem['src'] if img_elem else ""
                
                # Price Parsing
                price = 0
                price_text = ""
                price_elem = tile.select_one('span.rf-refurb-producttile-currentprice')
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Clean price
                    clean_price = re.sub(r'[^\d.,]', '', price_text)
                    
                    # Decimal Separator Logic for EU/Different formats
                    # Countries using comma decimal: DE, FR, PL, CH (mostly), NL, ES, PT, AT, CZ, SE, DK, SI
                    # Actually:
                    # UK/IE/US: dot decimal, comma thousands (1,234.56)
                    # EU (most): comma decimal, dot thousands (1.234,56)
                    # CH: dot decimal usually for currency? 'CHF 1’234.56' or comma. 
                    
                    is_comma_decimal_country = country_code in ['DE', 'FR', 'PL', 'NL', 'ES', 'PT', 'AT', 'CZ', 'SE', 'DK', 'SI', 'CH']
                    
                    if ',' in clean_price and '.' in clean_price:
                        # Ambiguous: detect by position
                        last_comma = clean_price.rfind(',')
                        last_dot = clean_price.rfind('.')
                        if last_comma > last_dot: # 1.234,56
                             clean_price = clean_price.replace('.', '').replace(',', '.')
                        else: # 1,234.56
                             clean_price = clean_price.replace(',', '')
                    elif ',' in clean_price:
                        if is_comma_decimal_country:
                             clean_price = clean_price.replace(',', '.')
                        else:
                             clean_price = clean_price.replace(',', '')
                    # else: only dots or plain number, python float handles it (if dot)
                    
                    try:
                        price = float(clean_price)
                        # Correct currency conversion would happen here if we used rate_to_eur
                    except:
                        price = 0

                # Specs Fallback
                raw_text = tile.get_text(" ", strip=True)
                specs, _ = parse_specs(raw_text)
                
                # Fallback to visiting product page if specs missing
                if specs['ram'] is None or specs['ssd'] is None:
                     print(f"  Missing specs for '{name[:40]}...' -> visiting product page...")
                     try:
                         page_prod = browser.new_page()
                         page_prod.goto(url, timeout=30000)
                         prod_content = page_prod.content()
                         
                         # Parse description from page
                         soup_prod = BeautifulSoup(prod_content, 'html.parser')
                         # Try specific selectors first to avoid marketing/footer noise
                         selectors = [
                             '.rc-pdsection-panel.Overview-panel', 
                             '.rc-pdsection-panel.TechSpecs-panel', 
                             '.rf-tech-specs-section',
                             '.rf-pdp-title'
                         ]
                         
                         full_page_text = ""
                         found_specific = False
                         for sel in selectors:
                             elements = soup_prod.select(sel)
                             if elements:
                                 found_specific = True
                                 for el in elements:
                                     full_page_text += " " + el.get_text(" ", strip=True)
                         
                         if not found_specific:
                             # Fallback to full page text
                             full_page_text = soup_prod.get_text(" ", strip=True)

                         specs_new, _ = parse_specs(full_page_text)
                         
                         if specs['ram'] is None: specs['ram'] = specs_new['ram']
                         if specs['ssd'] is None: specs['ssd'] = specs_new['ssd']
                         if specs['chip'] is None: specs['chip'] = specs_new['chip']
                         if specs['screen'] is None: specs['screen'] = specs_new['screen']
                         
                         page_prod.close()
                     except Exception as e:
                         print(f"  Failed to visit product page: {e}")

                prod = {
                    "country": country_code,
                    "name": name,
                    "price": price,
                    "currency": config['currency_label'],
                    "price_eur": round(price * config['rate_to_eur'], 2),
                    "image": image,
                    "url": url,
                    "specs": specs
                }
                items.append(prod)
                
            except Exception as e:
                 print(f"Error parsing tile: {e}")
                 continue
                 
    except Exception as e:
        print(f"Error processing {country_code}: {e}")

    return items

def parse_specs(text):
    # Normalize unicode spaces (NBSP)
    text = text.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    text = text.lower()
    specs = {
        "ram": None,
        "ssd": None,
        "chip": None,
        "screen": None,
        "device_type": "Mac" # Default since we are scraping /mac
    }
    
    # RAM
    ram_patterns = [
        r'(\d+)\s*(?:gb|go)\s*(?:unified memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|zunifikowanej\s*pamięci|pamięć\s*ram|centraal\s*geheugen|geheugen)',
        r'(\d+)\s*(?:gb|go)\s*(?:ram|memory|arbeitsspeicher|mémoire|pamięć|geheugen)',
        r'(\d+)\s*(?:gb|go)', # Fallback
    ]
    
    # Refined RAM: look for number + GB/Go followed by known RAM keywords within N characters
    # Or number + GB/Go if it doesn't match SSD pattern.
    
    # Let's stick to the safer patterns first
    for pattern in ram_patterns[:2]:
         ram_match = re.search(pattern, text)
         if ram_match:
             specs['ram'] = int(ram_match.group(1))
             break
    
    if specs['ram'] is None:
        # Try finding just number + GB but ensure it's not SSD
        # This is hard without lookaheads/behinds or complex logic.
        # Simple fallback for now: if we see "8GB" and haven't matched SSD yet, maybe it's RAM? 
        # But usually SSD is larger.
        pass

    # SSD
    # Try specific Polish/Short format "SSD 256 GB" FIRST
    ssd_match = re.search(r'ssd\s+(\d+)\s*(?:gb|go|tb|to)', text)

    if not ssd_match:
        # Dutch/Reverse style: "SSD van 256 GB"
        ssd_match = re.search(r'(?:ssd|opslag|stockage)\s*(?:van|de|von|z)\s*(\d+)\s*(?:gb|tb)', text)
        
    if not ssd_match:
        # Fallback to generic "NUM GB ... SSD"
        # Warning: This picks up "512 GB ... SSD" if it appears first
        ssd_match = re.search(r'(\d+)\s*(?:gb|go|tb|to)\s*(?:ssd|stockage|opslag|almacenamiento|lagring|úložiště|pamięci masowej)', text)
        
    if ssd_match:
        val = int(ssd_match.group(1))
        # Check for TB/To unit
        full_match = ssd_match.group(0)
        if 'tb' in full_match or 'to' in full_match:
            val *= 1024
        specs['ssd'] = val
        
    # If generic 16 GB regex matched but we are unsure if it's RAM or SSD:
    if specs['ram'] is None:
         # Find all "XX GB"
         matches = re.findall(r'(\d+)\s*(?:gb|go)', text)
         # Heuristic: usually smaller number is RAM, larger is SSD.
         # But M4 max can have 128GB RAM.
         # This is risky. 
         # Let's try to see if the text near "16 GB" contains "memory" or "arbeitsspeicher" even if unrelated characters in between.
         pass


    # Chip
    # Search for "M1/M2/M3/M4" optionally followed by "Pro", "Max", "Ultra" directly
    chip_match = re.search(r'\b(m[1-4])\s*(pro|max|ultra)?\b', text)
    if chip_match:
        base_chip = chip_match.group(1).upper() # e.g. M2
        suffix = chip_match.group(2) # e.g. Pro
        if suffix:
            specs['chip'] = f"{base_chip} {suffix.capitalize()}"
        else:
            specs['chip'] = base_chip
    
    # Screen Size
    screen_match = re.search(r'(\d+[,.]\d+)["”]', text)
    if screen_match:
        specs['screen'] = float(screen_match.group(1).replace(',', '.'))
    
    # Device Type refine
    if 'macbook air' in text: specs['device_type'] = 'MacBook Air'
    elif 'macbook pro' in text: specs['device_type'] = 'MacBook Pro'
    elif 'mini' in text: specs['device_type'] = 'Mac mini'
    elif 'imac' in text: specs['device_type'] = 'iMac'
    elif 'studio' in text: specs['device_type'] = 'Mac Studio'
    elif 'pro' in text and 'mac' in text: specs['device_type'] = 'Mac Pro'

    return specs, text 

def generate_html(all_products):
    # Determine unique filter values
    countries = sorted(list(set(p['country'] for p in all_products)))
    device_types = sorted(list(set(p['specs']['device_type'] for p in all_products)))
    ram_options = sorted(list(set(p['specs']['ram'] for p in all_products if p['specs']['ram'] is not None)))
    ssd_options = sorted(list(set(p['specs']['ssd'] for p in all_products if p['specs']['ssd'] is not None)))

    json_data = json.dumps(all_products)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apple Refurbished Tracker</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f5f5f7; margin: 0; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .controls {{ display: flex; gap: 15px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
        select {{ padding: 8px; border-radius: 8px; border: 1px solid #d2d2d7; font-size: 14px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 18px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s; display: flex; flex-direction: column; }}
        .card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); }}
        .image-container {{ height: 200px; display: flex; align-items: center; justify-content: center; padding: 20px; background: white; }}
        .image-container img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
        .content {{ padding: 20px; flex-grow: 1; display: flex; flex-direction: column; }}
        .title {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #1d1d1f; line-height: 1.4; }}
        .specs {{ font-size: 12px; color: #86868b; margin-bottom: 12px; flex-grow: 1; }}
        .price-row {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px; }}
        .price {{ font-size: 18px; font-weight: 700; color: #1d1d1f; }}
        .price-eur {{ font-size: 13px; color: #86868b; }}
        .country-tag {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; background: #e8e8ed; color: #1d1d1f; margin-bottom: 8px; }}
        a {{ text-decoration: none; color: inherit; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Apple Refurbished Tracker</h1>
        <p>Tracking {len(all_products)} items across {len(countries)} countries</p>
        <p style="font-size: 14px; color: #86868b; margin-top: 5px;">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="controls">
        <select id="countryFilter" onchange="renderGrid()">
            <option value="All">All Countries</option>
            {''.join(f'<option value="{c}">{c}</option>' for c in countries)}
        </select>
        <select id="deviceFilter" onchange="renderGrid()">
            <option value="All">All Devices</option>
            {''.join(f'<option value="{d}">{d}</option>' for d in device_types)}
        </select>
        <select id="ramFilter" onchange="renderGrid()">
            <option value="All">All RAM</option>
            {''.join(f'<option value="{r}">{r} GB</option>' for r in ram_options)}
        </select>
        <select id="ssdFilter" onchange="renderGrid()">
            <option value="All">All SSD</option>
            {''.join(f'<option value="{s}">{s if s < 1024 else s/1024} {"GB" if s < 1024 else "TB"}</option>' for s in ssd_options)}
        </select>
        <select id="sortFilter" onchange="renderGrid()">
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
        </select>
    </div>

    <div id="grid" class="grid"></div>

    <script>
        const products = {json_data};

        function formatSSD(gb) {{
            if (!gb) return '';
            return gb >= 1024 ? (gb/1024) + ' TB' : gb + ' GB';
        }}

        function renderGrid() {{
            const country = document.getElementById('countryFilter').value;
            const device = document.getElementById('deviceFilter').value;
            const ram = document.getElementById('ramFilter').value;
            const ssd = document.getElementById('ssdFilter').value;
            const sort = document.getElementById('sortFilter').value;
            
            const container = document.getElementById('grid');
            container.innerHTML = '';

            let filtered = products.filter(p => {{
                return (country === 'All' || p.country === country) &&
                       (device === 'All' || p.specs.device_type === device) &&
                       (ram === 'All' || (p.specs.ram && p.specs.ram.toString() === ram)) &&
                       (ssd === 'All' || (p.specs.ssd && p.specs.ssd.toString() === ssd));
            }});

            if (sort === 'price_asc') {{
                filtered.sort((a, b) => a.price_eur - b.price_eur);
            }} else {{
                filtered.sort((a, b) => b.price_eur - a.price_eur);
            }}

            filtered.forEach(p => {{
                const card = document.createElement('a');
                card.href = p.url;
                card.target = "_blank";
                card.className = 'card';
                
                let specList = [];
                if (p.specs.chip) specList.push(p.specs.chip);
                if (p.specs.ram) specList.push(p.specs.ram + ' GB RAM');
                if (p.specs.ssd) specList.push(formatSSD(p.specs.ssd) + ' SSD');
                
                const showEur = p.currency !== 'EUR';
                
                card.innerHTML = `
                    <div class="image-container">
                        <img src="${{p.image}}" alt="${{p.name}}" loading="lazy">
                    </div>
                    <div class="content">
                        <div>
                            <span class="country-tag">${{p.country}}</span>
                        </div>
                        <div class="title">${{p.name}}</div>
                        <div class="specs">${{specList.join(' • ')}}</div>
                        <div class="price-row">
                            <div class="price">${{p.price}} ${{p.currency}}</div>
                            ${{showEur ? `<div class="price-eur">~${{p.price_eur}} €</div>` : ''}}
                        </div>
                    </div>
                `;
                container.appendChild(card);
            }});
        }}
        
        // Initial render
        renderGrid();
    </script>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Generated index.html")

def main():
    parser = argparse.ArgumentParser(description="Apple Refurbished Store Scraper")
    parser.add_argument("--countries", nargs="+", help="List of country codes to scrape (e.g., DE NL PL). Default: ALL")
    args = parser.parse_args()

    target_countries = args.countries if args.countries else STORES.keys()
    
    # Validate country codes
    valid_countries = [c for c in target_countries if c in STORES]
    if not valid_countries:
        print(f"No valid countries found in selection. Available: {list(STORES.keys())}")
        return

    print("Starting Playwright Scraper...")
    all_items = []
    
    with sync_playwright() as p:
        for country in valid_countries:
            config = STORES[country]
            print(f"Processing store: {country} ({config['url']})")
            items = fetch_store_data(p, country, config)
            print(f"Found {len(items)} items in {country}")
            all_items.extend(items)
    
    generate_html(all_items)

if __name__ == "__main__":
    main()
