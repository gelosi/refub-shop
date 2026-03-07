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
from html import unescape, escape
from urllib.parse import urljoin

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

ACCESSORY_TYPES = {'Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod', 'AirPods', 'Display', 'Accessory'}
MAC_DEVICE_TYPES = {'Mac', 'MacBook Air', 'MacBook Pro', 'Mac mini', 'iMac', 'Mac Studio', 'Mac Pro'}
MACBOOK_TYPES = {'MacBook Air', 'MacBook Pro'}


def normalize_text(text):
    text = unescape(text or "")
    text = text.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    text = re.sub(r'[\u2010-\u2015\u2212]', '-', text)  # normalize dash variants
    text = re.sub(r'\s+', ' ', text).strip()
    return text


VALID_RAM_GB_VALUES = {4, 8, 12, 16, 18, 24, 32, 36, 48, 64, 96, 128, 192, 256, 512}


def sanitize_ram_value(raw_value):
    """Normalize RAM values and recover known year+RAM concatenation glitches (e.g. 202416 -> 16)."""
    if raw_value in VALID_RAM_GB_VALUES:
        return raw_value

    digits = str(raw_value)
    if len(digits) >= 6:
        for suffix_len in (3, 2, 1):
            if len(digits) <= suffix_len:
                continue
            suffix = int(digits[-suffix_len:])
            prefix = digits[:-suffix_len]
            if suffix in VALID_RAM_GB_VALUES and re.fullmatch(r'20\d{2}', prefix):
                return suffix

    # Drop obviously implausible values to avoid polluting filters/output.
    return None


def merge_specs(base, updates):
    merged = dict(base)
    for key in ['ram', 'ssd', 'chip', 'screen']:
        if merged.get(key) is None and updates.get(key) is not None:
            merged[key] = updates[key]
    # Only replace generic type names
    if merged.get('device_type') in [None, 'Device', 'Mac', 'iPad', 'iPhone', 'Apple Watch', 'Apple TV', 'Accessory']:
        if updates.get('device_type') and updates['device_type'] != 'Device':
            merged['device_type'] = updates['device_type']
    return merged


def extract_detail_text(product_url):
    req = urllib.request.Request(product_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        html = response.read().decode('utf-8', errors='ignore')

    soup = BeautifulSoup(html, 'html.parser')
    parts = []
    if soup.title and soup.title.get_text(strip=True):
        parts.append(soup.title.get_text(" ", strip=True))

    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_meta and desc_meta.get('content'):
        parts.append(desc_meta.get('content').replace('|', ' '))

    # Meta description is often generic; include visible body text to capture localized RAM/SSD lines.
    if soup.body:
        body_text = soup.body.get_text(" ", strip=True)
        if body_text:
            parts.append(body_text[:20000])

    return normalize_text(" ".join(parts))


def needs_detail_enrichment(product):
    specs = product.get('specs', {})
    category = product.get('category')
    device_type = specs.get('device_type')

    if category == 'mac':
        return specs.get('ram') is None or specs.get('ssd') is None or specs.get('screen') is None

    if category in ['ipad', 'iphone', 'appletv'] and specs.get('ssd') is None:
        return True

    # Accessories and watches should not force RAM/SSD enrichment.
    if category in ['watch', 'accessories'] or device_type in ACCESSORY_TYPES:
        return False
    return False


def enrich_products_with_detail_specs(products, country_code):
    cache = {}
    enriched = 0
    errors = []

    for product in products:
        if not needs_detail_enrichment(product):
            continue

        url = product.get('url')
        if not url:
            continue

        try:
            if url not in cache:
                cache[url] = extract_detail_text(url)
                time.sleep(0.12)  # small throttle to reduce bursty requests

            detail_text = cache[url]
            if detail_text:
                detail_specs, _ = parse_specs(detail_text, product.get('category', 'mac'))
                merged_specs = merge_specs(product['specs'], detail_specs)
                if merged_specs != product['specs']:
                    product['specs'] = merged_specs
                    enriched += 1
        except Exception as e:
            errors.append(f"Detail enrichment failed ({country_code}): {url} -> {e}")

    print(f"  Detail enrichment ({country_code}): updated {enriched} products")
    return errors


def format_screen_value(screen):
    if screen is None:
        return None
    if isinstance(screen, int) or float(screen).is_integer():
        return str(int(screen))
    return f"{screen:.1f}".rstrip('0').rstrip('.')


def html_option(value, label=None):
    if label is None:
        label = value
    safe_value = escape(str(value), quote=True)
    safe_label = escape(str(label), quote=False)
    return f'<option value="{safe_value}">{safe_label}</option>'


def bucket_screen_inches(screen):
    if screen is None:
        return None
    value = float(screen)
    # Keep all common "13-inch class" screens in one bucket (13.0 / 13.3 / 13.6).
    if 12.7 <= value < 14.0:
        return 13
    if value < 20:
        return int(value)
    return None


def device_filter_label(product):
    specs = product.get('specs', {})
    device_type = specs.get('device_type', 'Device')
    screen = specs.get('screen')

    inch_bucket = bucket_screen_inches(screen)
    if inch_bucket is not None and device_type not in ['Apple Watch', 'Display']:
        return f"{device_type} {inch_bucket}\""
    return device_type


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
                        
                    name = normalize_text(title_elem.get_text(strip=True))
                    item_url = urljoin(config['base_url'], title_elem['href'])
                    
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
                    raw_text = normalize_text(f"{name} {tile.get_text(' ', strip=True)}")
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

    country_errors.extend(enrich_products_with_detail_specs(all_category_items, country_code))
    browser.close()
    playwright.stop()
    return all_category_items, country_errors

def parse_specs(text, category='mac'):
    text = normalize_text(text)
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

    is_accessory = specs['device_type'] in ACCESSORY_TYPES

    # RAM (Mostly for Mac)
    if not is_accessory and (category == 'mac' or specs['device_type'] in MAC_DEVICE_TYPES):
        ram_patterns = [
            r'(?<!\d)(?:20\d{2}[\s-]*)?(\d{1,3})\s*(?:gb|go)\s*(?:(?:de|di|del|della|z)\s+)?(?:unified\s*memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|mémoire|zunifikowanej\s*pamięci|pamięci\s*ram|pamięć\s*ram|centraal\s*geheugen|geheugen|memoria\s*unificada|memoria\s*unificata|ram|memory|arbeitsspeicher)',
            r'(?:(?:ram|memory|arbeitsspeicher|mémoire|pamięć|pamięci|geheugen|memoria)\s*)[:\-]\s*(?<!\d)(\d{1,4})\s*(?:gb|go)',
        ]

        for pattern in ram_patterns:
            ram_match = re.search(pattern, text)
            if ram_match:
                specs['ram'] = sanitize_ram_value(int(ram_match.group(1)))
                break

    # SSD
    if not is_accessory:
        ssd_match = re.search(r'(?:ssd|flash\s*storage|massenspeicher|stockage|opslag|almacenamiento|archiviazione|storage)\s*(?:von|de|del|di|z|da)?\s*(\d+)\s*(?:gb|go|tb|to)', text)
        if not ssd_match:
            ssd_match = re.search(r'(\d+)\s*(?:gb|go|tb|to)\s*(?:ssd|flash\s*storage|massenspeicher|stockage|opslag|almacenamiento|archiviazione|lagring|úložiště|pamięci\s*masowej|storage|speicherplatz)', text)
            
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
                if 'tb' in simple_gb.group(0) or 'to' in simple_gb.group(0):
                    val *= 1024
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

    # Screen size (inch- or locale-word based) and watch size (mm)
    # Prefer decimal measurements (e.g. 13.6) over integer mentions (e.g. "13-inch").
    screen_match = re.search(r'(\d{1,2}[.,]\d)\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))', text)
    if not screen_match:
        screen_match = re.search(r'(\d{1,2})\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))', text)
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
    device_types = sorted(list(set(device_filter_label(p) for p in all_products)))
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
        :root {{
            --bg-0: #f3f6fc;
            --bg-1: #ffffff;
            --panel: #ffffff;
            --panel-border: #d6ddef;
            --text: #111827;
            --muted: #5a667f;
            --accent: #2563eb;
            --price: #0a7f46;
            --card-grad-1: #ffffff;
            --card-grad-2: #f6f8ff;
            --img-grad-1: #ffffff;
            --img-grad-2: #ffffff;
            --img-shadow: rgba(0, 0, 0, 0);
            --img-blend: normal;
            --img-filter: none;
            --img-overlay: transparent;
            --bg-glow-1: rgba(118, 156, 255, 0.25);
            --bg-glow-2: rgba(133, 182, 255, 0.22);
        }}
        :root[data-theme='dark'] {{
            --bg-0: #090c14;
            --bg-1: #121829;
            --panel: #171f33;
            --panel-border: #2a3554;
            --text: #ecf1ff;
            --muted: #95a3c8;
            --accent: #8ec5ff;
            --price: #b9f8d3;
            --card-grad-1: #1f2a45;
            --card-grad-2: #141c2f;
            --img-grad-1: #2a3554;
            --img-grad-2: #141c2f;
            --img-shadow: rgba(0,0,0,0.45);
            --img-blend: multiply;
            --img-filter: drop-shadow(0 14px 18px var(--img-shadow)) contrast(1.03);
            --img-overlay: rgba(9,12,20,0.20);
            --bg-glow-1: rgba(38, 53, 91, 0.60);
            --bg-glow-2: rgba(30, 65, 120, 0.45);
        }}
        @media (prefers-color-scheme: dark) {{
            :root:not([data-theme='light']) {{
                --bg-0: #090c14;
                --bg-1: #121829;
                --panel: #171f33;
                --panel-border: #2a3554;
                --text: #ecf1ff;
                --muted: #95a3c8;
                --accent: #8ec5ff;
                --price: #b9f8d3;
                --card-grad-1: #1f2a45;
                --card-grad-2: #141c2f;
                --img-grad-1: #2a3554;
                --img-grad-2: #141c2f;
                --img-shadow: rgba(0,0,0,0.45);
                --img-blend: multiply;
                --img-filter: drop-shadow(0 14px 18px var(--img-shadow)) contrast(1.03);
                --img-overlay: rgba(9,12,20,0.20);
                --bg-glow-1: rgba(38, 53, 91, 0.60);
                --bg-glow-2: rgba(30, 65, 120, 0.45);
            }}
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(1300px 500px at 10% -10%, var(--bg-glow-1) 0%, transparent 65%), radial-gradient(1000px 400px at 90% -20%, var(--bg-glow-2) 0%, transparent 70%), linear-gradient(180deg, var(--bg-1), var(--bg-0));
            color: var(--text);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ margin-bottom: 10px; }}
        .controls {{ display: flex; gap: 15px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
        select {{ padding: 8px; border-radius: 8px; border: 1px solid var(--panel-border); font-size: 14px; background: var(--panel); color: var(--text); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: linear-gradient(180deg, var(--card-grad-1), var(--card-grad-2)); border: 1px solid var(--panel-border); border-radius: 18px; overflow: hidden; box-shadow: 0 8px 26px rgba(0,0,0,0.18); transition: transform 0.2s, border-color 0.2s; display: flex; flex-direction: column; }}
        .card:hover {{ transform: translateY(-4px); border-color: #3a4d79; }}
        .image-container {{ height: 200px; display: flex; align-items: center; justify-content: center; padding: 20px; background: radial-gradient(circle at 50% 30%, var(--img-grad-1), var(--img-grad-2) 75%); position: relative; overflow: hidden; }}
        .image-container::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(circle at 50% 50%, transparent 40%, var(--img-overlay) 100%); pointer-events: none; }}
        .image-container img {{ max-height: 100%; max-width: 100%; object-fit: contain; filter: var(--img-filter); mix-blend-mode: var(--img-blend); border-radius: 14px; }}
        .content {{ padding: 20px; flex-grow: 1; display: flex; flex-direction: column; }}
        .category-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }}
        .title {{ font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text); line-height: 1.4; }}
        .specs {{ font-size: 12px; color: var(--muted); margin-bottom: 12px; flex-grow: 1; }}
        .price-row {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 10px; }}
        .price {{ font-size: 18px; font-weight: 700; color: var(--price); }}
        .price-eur {{ font-size: 13px; color: var(--muted); }}
        .attribution {{ position: absolute; top: 20px; right: 20px; font-size: 12px; color: var(--muted); }}
        .attribution a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
        .attribution a:hover {{ text-decoration: underline; }}
        a {{ text-decoration: none; color: inherit; }}
    </style>
</head>
<body>
    <div class="attribution">
        made by <a href="https://gelosi.github.io" target="_blank">gelosi</a><br>
        get notifications via <a href="https://refurb-tracker.com" target="_blank">refurb-tracker</a>
    </div>
    <div class="header">
        <h1>Apple Refurbished Tracker</h1>
        <p>Tracking {len(all_products)} items across {len(countries)} countries</p>
        <p style="font-size: 14px; color: var(--muted); margin-top: 5px;">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="controls">
        <select id="countryFilter" onchange="renderGrid()">
            <option value="All">All Countries</option>
            {''.join(html_option(c) for c in countries)}
        </select>
        <select id="categoryFilter" onchange="renderGrid()">
            <option value="All">All Categories</option>
            {''.join(html_option(cat, cat.title()) for cat in categories)}
        </select>
        <select id="deviceFilter" onchange="renderGrid()">
            <option value="All">All Devices</option>
            {''.join(html_option(d) for d in device_types)}
        </select>
        <select id="ramFilter" onchange="renderGrid()">
            <option value="All">All RAM</option>
            {''.join(html_option(r, f"{r} GB") for r in ram_options)}
        </select>
        <select id="ssdFilter" onchange="renderGrid()">
            <option value="All">All SSD</option>
            {''.join(html_option(s, f"{s if s < 1024 else s/1024} {'GB' if s < 1024 else 'TB'}") for s in ssd_options)}
        </select>
        <select id="sortFilter" onchange="renderGrid()">
            <option value="price_asc">Price: Low to High</option>
            <option value="price_desc">Price: High to Low</option>
        </select>
        <select id="themeFilter" onchange="setTheme(this.value)">
            <option value="system">Theme: System</option>
            <option value="light">Theme: Light</option>
            <option value="dark">Theme: Dark</option>
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

        function formatScreen(screen) {{
            if (!screen) return '';
            const s = Number.isInteger(screen) ? screen.toString() : screen.toFixed(1).replace(/\\.0$/, '');
            return s + '"';
        }}

        function bucketScreen(screen) {{
            if (!screen) return null;
            const value = Number(screen);
            if (value >= 12.7 && value < 14) return 13;
            if (value < 20) return Math.floor(value);
            return null;
        }}

        function getDeviceFilterValue(p) {{
            const bucket = bucketScreen(p.specs.screen);
            if (bucket && p.specs.device_type !== 'Apple Watch' && p.specs.device_type !== 'Display') {{
                return `${{p.specs.device_type}} ${{bucket}}"`;
            }}
            return p.specs.device_type;
        }}

        function setTheme(theme) {{
            const root = document.documentElement;
            if (theme === 'light' || theme === 'dark') {{
                root.setAttribute('data-theme', theme);
            }} else {{
                root.removeAttribute('data-theme');
            }}
            localStorage.setItem('theme-preference', theme);
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
                       (device === 'All' || getDeviceFilterValue(p) === device) &&
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
                if (p.specs.screen && (p.specs.device_type === 'MacBook Air' || p.specs.device_type === 'MacBook Pro' || p.specs.device_type === 'iMac' || p.specs.device_type === 'Display')) specList.push(formatScreen(p.specs.screen) + ' Display');
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
        const savedTheme = localStorage.getItem('theme-preference') || 'system';
        document.getElementById('themeFilter').value = savedTheme;
        setTheme(savedTheme);
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
