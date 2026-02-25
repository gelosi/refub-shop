from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime
import time
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import urllib.request

def fetch_exchange_rates():
    try:
        url = "https://open.er-api.com/v6/latest/EUR"
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            return data.get('rates', {})
    except Exception as e:
        print(f"Warning: Failed to fetch exchange rates ({e}). Using hardcoded fallbacks.")
        return {}

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
        "rate_to_eur": 0.23,
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
    "CH": {
        "base_url": "https://www.apple.com/ch-de/shop/refurbished",
        "currency_symbol": "CHF",
        "currency_label": "CHF",
        "rate_to_eur": 1.07,
    },
    "IT": {
        "base_url": "https://www.apple.com/it/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "BE": {
        "base_url": "https://www.apple.com/be-fr/shop/refurbished",
        "currency_symbol": "€",
        "currency_label": "EUR",
        "rate_to_eur": 1.0,
    },
    "UK": {
        "base_url": "https://www.apple.com/uk/shop/refurbished",
        "currency_symbol": "£",
        "currency_label": "GBP",
        "rate_to_eur": 1.17,
    }
}

CATEGORIES = ['mac', 'ipad', 'iphone', 'watch', 'appletv', 'accessories']

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
OUTPUT_FILE = "index.html"

def fetch_store_data(country_code, config):
    print(f"Fetching data for {country_code}...")
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    
    all_category_items = []
    country_errors = []
    
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
                        is_comma_decimal_country = country_code in ['DE', 'FR', 'PL', 'NL', 'ES', 'AT', 'CH', 'IT', 'BE']
                        
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
                    
    
                    # Recategorize accessories found in other sections (e.g. Pencil in iPad section)
                    final_category = category
                    if specs['device_type'] in ['Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod', 'AirPods', 'Display', 'Accessory']:
                        final_category = 'accessories'

                    # Calculate EUR price
                    price_eur = round(price * config['rate_to_eur'], 2)
                    
                    prod = {
                        "country": country_code,
                        "category": final_category,
                        "name": name,
                        "price": price_eur, # Main price is now always EUR
                        "currency": "EUR",
                        "original_price": price if config['currency_label'] != 'EUR' else None,
                        "original_currency": config['currency_label'],
                        "image": image,
                        "url": item_url,
                        "specs": specs
                    }
                    items.append(prod)
                    
                except Exception as e:
                     err_msg = f"Item processing error: {e}"
                     country_errors.append(err_msg)
                     continue
                     
        except Exception as e:
            err_msg = f"Error processing {country_code} {category}: {e}"
            print(err_msg)
            country_errors.append(err_msg)
            
        page.close()
        all_category_items.extend(items)

    browser.close()
    playwright.stop()
    return all_category_items, country_errors

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

    # 1. Main Device Type Detection (Priority 1)
    # Detect Macs first as they often contain accessory names in their specs
    if 'macbook air' in text: specs['device_type'] = 'MacBook Air'
    elif 'macbook pro' in text: specs['device_type'] = 'MacBook Pro'
    elif 'mac mini' in text: specs['device_type'] = 'Mac mini'
    elif 'imac' in text: specs['device_type'] = 'iMac'
    elif 'mac studio' in text: specs['device_type'] = 'Mac Studio'
    elif 'mac pro' in text: specs['device_type'] = 'Mac Pro'
    elif 'ipad' in text:
        specs['device_type'] = 'iPad'
        if 'ipad pro' in text: specs['device_type'] = 'iPad Pro'
        elif 'ipad air' in text: specs['device_type'] = 'iPad Air'
        elif 'ipad mini' in text: specs['device_type'] = 'iPad mini'
    elif 'iphone' in text:
        specs['device_type'] = 'iPhone'
        model_match = re.search(r'iphone\s+(\d+(?:\s*(?:pro\s*max|pro|max|plus|mini))?)', text)
        if model_match:
            device_model = re.sub(r'\s+', ' ', model_match.group(1).strip().title())
            specs['device_type'] = f"iPhone {device_model}"
    elif 'watch' in text:
        specs['device_type'] = 'Apple Watch'
    elif 'apple tv' in text:
        specs['device_type'] = 'Apple TV'

    # 2. Accessory Detection (Priority 2 - Only if not already identified as a main device)
    # Or specifically for Pencil which can be in iPad section names
    if specs['device_type'] == 'Device':
        if 'pencil' in text: specs['device_type'] = 'Apple Pencil'
        elif 'magic mouse' in text: specs['device_type'] = 'Mouse'
        elif 'magic trackpad' in text: specs['device_type'] = 'Trackpad'
        elif 'magic keyboard' in text: specs['device_type'] = 'Keyboard'
        elif 'homepod' in text: specs['device_type'] = 'HomePod'
        elif 'airpods' in text: specs['device_type'] = 'AirPods'
        elif 'studio display' in text or 'pro display' in text: specs['device_type'] = 'Display'
    
    # Special case: Apple Pencil overrides because it's often in title "Pencil for iPad"
    if 'pencil' in text:
        specs['device_type'] = 'Apple Pencil'

    # 3. Final Category Fallbacks
    if specs['device_type'] == 'Device':
        if category == 'mac': specs['device_type'] = 'Mac'
        elif category == 'ipad': specs['device_type'] = 'iPad'
        elif category == 'iphone': specs['device_type'] = 'iPhone'
        elif category == 'watch': specs['device_type'] = 'Apple Watch'
        elif category == 'appletv': specs['device_type'] = 'Apple TV'
        elif category == 'accessories': specs['device_type'] = 'Accessory'

    is_accessory = specs['device_type'] in ['Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod', 'AirPods', 'Display', 'Accessory']

    # RAM (Mostly for Mac)
    if not is_accessory and (category == 'mac' or specs['device_type'] in ['Mac', 'MacBook Air', 'MacBook Pro', 'Mac mini', 'iMac', 'Mac Studio', 'Mac Pro']):
        ram_patterns = [
            r'(\d+)\s*(?:gb|go)\s*(?:(?:de|di)\s+)?(?:unified memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|zunifikowanej\s*pamięci|pamięć\s*ram|centraal\s*geheugen|geheugen|memoria\s*unificada|memoria\s*unificata)',
            r'(\d+)\s*(?:gb|go)\s*(?:ram|memory|arbeitsspeicher|mémoire|pamięć|geheugen|memoria)',
            r'(\d+)\s*(?:gb|go)', # Fallback
        ]
        
        for pattern in ram_patterns[:2]:
             ram_match = re.search(pattern, text)
             if ram_match:
                 specs['ram'] = int(ram_match.group(1))
                 break

    # SSD
    if not is_accessory:
        ssd_match = re.search(r'ssd\s+(\d+)\s*(?:gb|go|tb|to)', text)
        if not ssd_match:
            ssd_match = re.search(r'(?:ssd|opslag|stockage)\s*(?:van|de|von|z|da)\s*(\d+)\s*(?:gb|go|tb|to)', text)
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
    elif category == 'watch' or specs['device_type'] == 'Apple Watch':
        # Watch Case Size (mm)
        mm_match = re.search(r'(\d+)\s*mm', text)
        if mm_match:
             specs['screen'] = int(mm_match.group(1)) # Treat 'screen' field as size for watch
    elif specs['device_type'] == 'Display':
        # Studio Display is 27", Pro Display XDR is 32"
        if '27' in text: specs['screen'] = 27
        elif '32' in text: specs['screen'] = 32

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
        .attribution {{ position: absolute; top: 20px; right: 20px; font-size: 12px; color: #86868b; }}
        .attribution a {{ color: #0066cc; text-decoration: none; font-weight: 600; }}
        .attribution a:hover {{ text-decoration: underline; }}
        a {{ text-decoration: none; color: inherit; }}
    </style>
</head>
<body>
    <div class="attribution">
        made by <a href="https://gelosi.github.io" target="_blank">gelosi</a>
    </div>
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

        // Explicit Lazy Loading to avoid rate limits
        const lazyObserver = new IntersectionObserver((entries, observer) => {{
            entries.forEach(entry => {{
                if (entry.isIntersecting) {{
                    const img = entry.target;
                    // Throttle loading to only when user stops scrolling past
                    setTimeout(() => {{
                        const rect = img.getBoundingClientRect();
                        if (rect.top < window.innerHeight + 100 && rect.bottom > -100) {{
                            img.src = img.getAttribute('data-src');
                            img.classList.remove('lazy-image');
                            observer.unobserve(img);
                        }}
                    }}, 150);
                }}
            }});
        }}, {{ rootMargin: "200px 0px" }});

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
                filtered.sort((a, b) => a.price - b.price);
            }} else {{
                filtered.sort((a, b) => b.price - a.price);
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
                
                const showOriginal = p.original_price != null;
                
                card.innerHTML = `
                    <div class="image-container">
                        <img class="lazy-image" data-src="${{p.image}}" src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1 1'%3E%3C/svg%3E" alt="${{p.name}}">
                    </div>
                    <div class="content">
                        <div>
                            <span class="country-tag">${{p.country}}</span>
                            <span class="category-label">${{p.category.toUpperCase()}}</span>
                        </div>
                        <div class="title">${{p.name}}</div>
                        <div class="specs">${{specList.join(' • ')}}</div>
                        <div class="price-row">
                            <div class="price">€${{p.price.toFixed(2)}}</div>
                            ${{showOriginal ? `<div class="price-eur">${{p.original_price.toFixed(2)}} ${{p.original_currency}}</div>` : ''}}
                        </div>
                    </div>
                `;
                container.appendChild(card);
            }});

            document.querySelectorAll('.lazy-image').forEach(img => lazyObserver.observe(img));
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

    # Fetch and update exchange rates
    rates = fetch_exchange_rates()
    if rates:
        print("Updating exchange rates...")
        for country, config in STORES.items():
            currency = config['currency_label']
            if currency == 'EUR':
                config['rate_to_eur'] = 1.0
            elif currency in rates and rates[currency] > 0:
                # API gives X Currency per 1 EUR. We want EUR per 1 Currency.
                # So rate_to_eur = 1 / rate
                new_rate = 1.0 / rates[currency]
                print(f"  {country} ({currency}): {config['rate_to_eur']} -> {new_rate:.4f}")
                config['rate_to_eur'] = new_rate
    
    jobs = {}
    master_errors = []
    with ProcessPoolExecutor(max_workers=len(valid_countries)) as executor:
        for country in valid_countries:
            config = STORES[country]
            if 'base_url' not in config:
                print(f"Skipping {country}: Missing base_url")
                continue
            print(f"Queuing store: {country} ({config['base_url']})")
            future = executor.submit(fetch_store_data, country, config)
            jobs[future] = country

        for future in as_completed(jobs):
            country = jobs[future]
            try:
                items, c_errors = future.result()
                print(f"Found {len(items)} items in {country}")
                all_items.extend(items)
                master_errors.extend(c_errors)
            except Exception as e:
                print(f"Failed to fetch {country}: {e}")
                master_errors.append(f"CRITICAL: Failed to fetch {country}: {e}")
                
    generate_html(all_items)
    
    # --- Statistics Output ---
    print("\n" + "="*40)
    print("SCRAPING STATISTICS")
    print("="*40)
    print(f"Total Products Found: {len(all_items)}")
    
    if not all_items:
        print("WARNING: No products were scraped at all. Check connection or selectors.")
        return
        
    stats = {}
    for item in all_items:
        c = item['country']
        cat = item['category']
        if c not in stats:
            stats[c] = {category: 0 for category in CATEGORIES}
            stats[c]['_total'] = 0
        
        # In case a custom category slipped in
        if cat not in stats[c]:
            stats[c][cat] = 0
            
        stats[c][cat] += 1
        stats[c]['_total'] += 1

    for country in valid_countries:
        if country not in stats:
            print(f"\n[{country}] - 0 items (FAILED OR EMPTY)")
            continue
            
        c_stats = stats[country]
        print(f"\n[{country}] Total: {c_stats['_total']}")
        
        for cat in CATEGORIES:
            count = c_stats.get(cat, 0)
            if count == 0:
                # Flag missing categories, which might indicate a changed page structure or real lack of stock
                print(f"  - {cat.ljust(12)}: {count}  <-- EMPTY")
            else:
                print(f"  - {cat.ljust(12)}: {count}")
                
    if master_errors:
        print("\n" + "="*40)
        print("ERRORS ENCOUNTERED")
        print("="*40)
        for err in master_errors:
            print(f" - {err}")
            
    print("\n" + "="*40 + "\n")

if __name__ == "__main__":
    main()
