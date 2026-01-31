from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
import time
import argparse

# Configuration
# Configuration
STORES = {
    "DE": {
        "base_url": "https://www.apple.com/de/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "IE": {
        "base_url": "https://www.apple.com/ie/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "NL": {
        "base_url": "https://www.apple.com/nl/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "FR": {
        "base_url": "https://www.apple.com/fr/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "PL": {
        "base_url": "https://www.apple.com/pl/shop/refurbished",
        "currency_symbol": "zł",
        "currency_label": "PLN",
        "rate_to_eur": 0.23, # Approx
    },
    "AT": {
        "base_url": "https://www.apple.com/at/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "ES": {
        "base_url": "https://www.apple.com/es/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },

    "CH": { # Swiss German
        "base_url": "https://www.apple.com/ch-de/shop/refurbished",
        "currency_symbol": "CHF",
        "currency_label": "CHF",
        "rate_to_eur": 1.07, # Approx
    },
    # Nordic/Baltic/Central EU stores often don't exist (404), so we exclude them to prevent errors.
    # Confirmed 404: SE, DK, NO, FI, CZ, SI, HU, LU, PT
    "IT": {
        "base_url": "https://www.apple.com/it/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "BE": { # Belgium (French)
        "base_url": "https://www.apple.com/be-fr/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "UK": {
        "base_url": "https://www.apple.com/uk/shop/refurbished",
        "currency_symbol": "£",
        "currency_label": "GBP",
        "rate_to_eur": 1.17, # Approx
    }
}

CATEGORIES = ['mac', 'ipad', 'iphone', 'watch', 'appletv', 'accessories']

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
OUTPUT_FILE = "index.html"

def fetch_store_data(playwright, country_code, config):
    print(f"Fetching data for {country_code}...")
    browser = playwright.chromium.launch(headless=True)
    
    all_category_items = []
    
    for category in CATEGORIES:
        url = f"{config['base_url']}/{category}"
        print(f"  Scanning {category} at {url}...")
        
        page = browser.new_page()
        items = []
        
        try:
            page.goto(url, timeout=60000)
            
            # Check if 404 or redirect to home (some categories might be missing in some countries)
            if "as-refurbished" not in page.url and category not in page.url:
                pass

            # Incremental scroll to trigger lazy loading
            for _ in range(5): 
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
                    item_url = "https://www.apple.com" + title_elem['href']
                    
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
                        
                        # Decimal Separator Logic (reused)
                        is_comma_decimal_country = country_code in ['DE', 'FR', 'PL', 'NL', 'ES', 'PT', 'AT', 'CZ', 'SE', 'DK', 'SI', 'CH']
                        
                        if ',' in clean_price and '.' in clean_price:
                            last_comma = clean_price.rfind(',')
                            last_dot = clean_price.rfind('.')
                            if last_comma > last_dot: clean_price = clean_price.replace('.', '').replace(',', '.')
                            else: clean_price = clean_price.replace(',', '')
                        elif ',' in clean_price:
                            if is_comma_decimal_country: clean_price = clean_price.replace(',', '.')
                            else: clean_price = clean_price.replace(',', '')
                        
                        try:
                            price = float(clean_price)
                        except:
                            price = 0
    
                    # Specs
                    raw_text = tile.get_text(" ", strip=True)
                    specs, _ = parse_specs(raw_text, category)
                    
                    # Fallback visit logic
                    # Only check RAM missing for Macs.
                    # Check SSD for Mac, iPad, iPhone, AppleTV (AppleTV has capacity).
                    # Watch and Accessories might not clearly state capacity in title or use different format, so skip forced check.
        
                    check_ram = (category == 'mac') 
                    check_ssd = (category in ['mac', 'ipad', 'iphone', 'appletv'])
                    
                    # Strictness check
                    missing_important = False
                    if check_ram and specs['ram'] is None: missing_important = True
                    if check_ssd and specs['ssd'] is None: missing_important = True
                    
                    if missing_important and specs['device_type'] not in ['Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'Accessory']:
                         print(f"    Missing specs ({category}) for '{name[:30]}...' -> visiting page...")
                         try:
                             page_prod = browser.new_page()
                             page_prod.goto(item_url, timeout=30000)
                             prod_content = page_prod.content()
                             
                             soup_prod = BeautifulSoup(prod_content, 'html.parser')
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
    
                             specs_new, _ = parse_specs(full_page_text, category)
                             
                             if specs['ram'] is None: specs['ram'] = specs_new['ram']
                             if specs['ssd'] is None: specs['ssd'] = specs_new['ssd']
                             if specs['chip'] is None: specs['chip'] = specs_new['chip']
                             if specs['screen'] is None: specs['screen'] = specs_new['screen']
                             if specs_new['device_type'] != 'Device': specs['device_type'] = specs_new['device_type']
                             
                             page_prod.close()
                         except Exception as e:
                             print(f"    Failed to visit page: {e}")
    
                    # Recategorize accessories found in other sections (e.g. Pencil in iPad section)
                    final_category = category
                    if specs['device_type'] in ['Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod', 'Accessory']:
                        final_category = 'accessories'

                    prod = {
                        "country": country_code,
                        "category": final_category,
                        "name": name,
                        "price": price,
                        "currency": config['currency_label'],
                        "price_eur": round(price * config['rate_to_eur'], 2),
                        "image": image,
                        "url": item_url,
                        "specs": specs
                    }
                    items.append(prod)
                    
                except Exception as e:
                     continue
                     
        except Exception as e:
            print(f"Error processing {country_code} {category}: {e}")
            
        page.close()
        all_category_items.extend(items)

    browser.close()
    return all_category_items

def parse_specs(text, category='mac'):
    # Normalize unicode spaces (NBSP)
    text = text.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    text = text.lower()
    specs = {
        "ram": None,
        "ssd": None,
        "chip": None,
        "screen": None,
        "device_type": "Device"
    }
    
    # Global Accessory Detection (Prioritized)
    # Detect Pencils, Keyboards, etc. regardless of category context
    if 'pencil' in text: # "Apple Pencil" usually
        specs['device_type'] = 'Apple Pencil'
    elif 'mouse' in text or 'souris' in text or 'maus' in text or 'ratón' in text:
        specs['device_type'] = 'Mouse'
    elif 'trackpad' in text:
        specs['device_type'] = 'Trackpad'
    elif 'keyboard' in text or 'clavier' in text or 'tastatur' in text or 'teclado' in text:
        specs['device_type'] = 'Keyboard'
    elif 'homepod' in text:
        specs['device_type'] = 'HomePod'
    
    # If identified as accessory, we can skip other checks or be careful not to overwrite
    is_accessory = specs['device_type'] in ['Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod']

    # RAM (Mostly for Mac)
    if not is_accessory and category == 'mac':
        ram_patterns = [
            r'(\d+)\s*(?:gb|go)\s*(?:de\s+)?(?:unified memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|zunifikowanej\s*pamięci|pamięć\s*ram|centraal\s*geheugen|geheugen|memoria\s*unificada|memoria\s*unificata)',
            r'(\d+)\s*(?:gb|go)\s*(?:ram|memory|arbeitsspeicher|mémoire|pamięć|geheugen|memoria)',
            r'(\d+)\s*(?:gb|go)', # Fallback
        ]
        
        for pattern in ram_patterns[:2]:
             ram_match = re.search(pattern, text)
             if ram_match:
                 specs['ram'] = int(ram_match.group(1))
                 break
        
        if specs['ram'] is None:
            pass

    # SSD
    if not is_accessory:
        ssd_match = re.search(r'ssd\s+(\d+)\s*(?:gb|go|tb|to)', text)
    
        if not ssd_match:
            ssd_match = re.search(r'(?:ssd|opslag|stockage)\s*(?:van|de|von|z)\s*(\d+)\s*(?:gb|go|tb|to)', text)
            
        if not ssd_match:
            # Fallback
            ssd_match = re.search(r'(\d+)\s*(?:gb|go|tb|to)\s*(?:ssd|stockage|opslag|almacenamiento|lagring|úložiště|pamięci masowej)', text)
            
        if ssd_match:
            val = int(ssd_match.group(1))
            full_match = ssd_match.group(0)
            if 'tb' in full_match or 'to' in full_match:
                val *= 1024
            specs['ssd'] = val
        
        # Allow simple GB search for iPad/iPhone/AppleTV if no "SSD" keyword found
        if specs['ssd'] is None and category in ['ipad', 'iphone', 'appletv']:
             simple_gb = re.search(r'(\d+)\s*(?:gb|go|tb|to)', text)
             if simple_gb:
                 val = int(simple_gb.group(1))
                 if 'tb' in simple_gb.group(0) or 'to' in simple_gb.group(0): val *= 1024
                 specs['ssd'] = val


    # Chip
    # M-series
    chip_match = re.search(r'\b(m[1-4])\s*(pro|max|ultra)?\b', text)
    if chip_match:
        base_chip = chip_match.group(1).upper() 
        suffix = chip_match.group(2) 
        if suffix: specs['chip'] = f"{base_chip} {suffix.capitalize()}"
        else: specs['chip'] = base_chip
    
    # A-series (for iPad/iPhone/TV)
    if specs['chip'] is None:
        a_chip = re.search(r'\b(a\d{2}[zx]?)\b', text) # A12, A12Z, A14...
        if a_chip:
            specs['chip'] = a_chip.group(1).upper()

    # Screen Size (Watch size / Screen)
    screen_match = re.search(r'(\d+[,.]\d+)["”]', text)
    if screen_match:
        specs['screen'] = float(screen_match.group(1).replace(',', '.'))
    elif category == 'watch':
        # Watch Case Size (mm)
        mm_match = re.search(r'(\d+)\s*mm', text)
        if mm_match:
             specs['screen'] = int(mm_match.group(1)) # Treat 'screen' field as size for watch
    
    # Device Type refine
    if specs['device_type'] == 'Device': # Only if not already identified as accessory
        if category == 'mac':
            specs['device_type'] = 'Mac'
            if 'macbook air' in text: specs['device_type'] = 'MacBook Air'
            elif 'macbook pro' in text: specs['device_type'] = 'MacBook Pro'
            elif 'mini' in text: specs['device_type'] = 'Mac mini'
            elif 'imac' in text: specs['device_type'] = 'iMac'
            elif 'studio' in text: specs['device_type'] = 'Mac Studio'
            elif 'pro' in text and 'mac' in text: specs['device_type'] = 'Mac Pro'
        elif category == 'ipad':
            specs['device_type'] = 'iPad'
            if 'ipad pro' in text: specs['device_type'] = 'iPad Pro'
            elif 'ipad air' in text: specs['device_type'] = 'iPad Air'
            elif 'ipad mini' in text: specs['device_type'] = 'iPad mini'
        elif category == 'iphone':
            specs['device_type'] = 'iPhone'
            model_match = re.search(r'iphone\s+(\d+\s*(?:pro|max|plus|mini)?)', text)
            if model_match:
                specs['device_type'] = f"iPhone {model_match.group(1).title()}"
        elif category == 'watch':
            specs['device_type'] = 'Apple Watch'
            if 'ultra' in text: specs['device_type'] = 'Apple Watch Ultra'
            elif 'se' in text: specs['device_type'] = 'Apple Watch SE'
            else:
                series = re.search(r'series\s+(\d+)', text)
                if series: specs['device_type'] = f"Apple Watch Series {series.group(1)}"
        elif category == 'appletv':
            specs['device_type'] = 'Apple TV'
            if '4k' in text: specs['device_type'] = 'Apple TV 4K'
            if 'hd' in text: specs['device_type'] = 'Apple TV HD'
        elif category == 'accessories':
            specs['device_type'] = 'Accessory'

    return specs, text 

def generate_html(all_products):
    # Determine unique filter values
    countries = sorted(list(set(p['country'] for p in all_products)))
    categories = sorted(list(set(p['category'] for p in all_products)))
    device_types = sorted(list(set(p['specs']['device_type'] for p in all_products)))
    # For filters, maybe we should separate by category or just list all
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
        .header h1 {{ margin-bottom: 10px; }}
        .controls {{ display: flex; gap: 15px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
        select {{ padding: 8px; border-radius: 8px; border: 1px solid #d2d2d7; font-size: 14px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 18px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s; display: flex; flex-direction: column; }}
        .card:hover {{ transform: translateY(-4px); box-shadow: 0 10px 15px rgba(0,0,0,0.1); }}
        .image-container {{ height: 200px; display: flex; align-items: center; justify-content: center; padding: 20px; background: white; }}
        .image-container img {{ max-height: 100%; max-width: 100%; object-fit: contain; }}
        .content {{ padding: 20px; flex-grow: 1; display: flex; flex-direction: column; }}
        .category-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: #86868b; margin-bottom: 4px; font-weight: 600; }}
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
        <select id="categoryFilter" onchange="renderGrid()">
            <option value="All">All Categories</option>
            {''.join(f'<option value="{cat}">{cat.title()}</option>' for cat in categories)}
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
            const category = document.getElementById('categoryFilter').value;
            const device = document.getElementById('deviceFilter').value;
            const ram = document.getElementById('ramFilter').value;
            const ssd = document.getElementById('ssdFilter').value;
            const sort = document.getElementById('sortFilter').value;
            
            const container = document.getElementById('grid');
            container.innerHTML = '';

            let filtered = products.filter(p => {{
                return (country === 'All' || p.country === country) &&
                       (category === 'All' || p.category === category) &&
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
                            <span class="category-label">${{p.category.toUpperCase()}}</span>
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
            print(f"Processing store: {country} ({config['base_url']})")
            items = fetch_store_data(p, country, config)
            print(f"Found {len(items)} items in {country}")
            all_items.extend(items)
    
    generate_html(all_items)

if __name__ == "__main__":
    main()
