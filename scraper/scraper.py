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
LISTING_TILE_SELECTOR = ".rf-refurb-producttile"
TECH_SPECS_SELECTOR = ".rf-pdp-techspecssection, .TechSpecs-panel"

ACCESSORY_TYPES = {'Apple Pencil', 'Keyboard', 'Mouse', 'Trackpad', 'HomePod', 'AirPods', 'Display', 'Accessory'}
MAC_DEVICE_TYPES = {'Mac', 'MacBook Air', 'MacBook Pro', 'Mac mini', 'iMac', 'Mac Studio', 'Mac Pro'}
MACBOOK_TYPES = {'MacBook Air', 'MacBook Pro'}
SCREEN_BUCKET_DEVICE_TYPES = {'MacBook Air', 'MacBook Pro', 'iMac', 'iPad', 'iPad Pro', 'iPad Air', 'iPad mini'}
GENERIC_DEVICE_TYPES = {'Mac', 'iPad', 'iPhone', 'Apple Watch', 'Apple TV', 'Accessory'}
NUMBER_UNIT_SEP = r'\s*(?:-\s*)?'
FOOTNOTE_SUFFIX = r'(?:[0-9¹²³⁴⁵⁶⁷⁸⁹]+)?'
RAM_UNIT_PATTERN = rf'(?:gb|go){FOOTNOTE_SUFFIX}(?![a-z])'
STORAGE_UNIT_PATTERN = rf'(gb|go|tb|to){FOOTNOTE_SUFFIX}(?![a-z])'
DETAIL_SPEC_SECTION_WINDOW = 1800
DETAIL_FETCH_RETRIES = 3
DETAIL_FETCH_BACKOFF_SECONDS = 0.75
DETAIL_FETCH_THROTTLE_SECONDS = 0.35
LISTING_SCROLL_STEPS = 6
LISTING_SCROLL_DELAY_SECONDS = 0.65
LISTING_SETTLE_SECONDS = 0.8
DETAIL_SCROLL_STEPS = 4
DETAIL_SCROLL_DELAY_SECONDS = 0.25
DETAIL_SETTLE_SECONDS = 0.8
MAX_COUNTRY_WORKERS = 4
MIN_TECH_SPECS_SECTIONS = 4
MIN_TECH_SPECS_ITEMS = 8
MAX_REASONABLE_STORAGE_GB = 16384
DETAIL_SPEC_SECTION_MARKERS = [
    "product information overview",
    "product information",
    "tech specs",
    "produktinformationen überblick",
    "produktinformationen",
    "technische daten",
    "informations produit présentation",
    "informations produit",
    "caractéristiques techniques",
    "productinformatie overzicht",
    "productinformatie",
    "technische specificaties",
    "informazioni sul prodotto panoramica",
    "informazioni sul prodotto",
    "specifiche tecniche",
    "información del producto descripción",
    "información del producto",
    "especificaciones técnicas",
    "informacje o produkcie omówienie",
    "informacje o produkcie",
    "dane techniczne",
    "specyfikacja techniczna",
]
DISPLAY_SECTION_MARKERS = [
    "display",
    "bildschirm",
    "écran",
    "scherm",
    "pantalla",
    "schermo",
    "wyświetlacz",
]
MEMORY_SECTION_MARKERS = [
    "memory",
    "arbeitsspeicher",
    "mémoire",
    "geheugen",
    "memoria",
    "pamięć operacyjna",
]
STORAGE_SECTION_MARKERS = [
    "storage",
    "massenspeicher",
    "stockage",
    "opslag",
    "almacenamiento",
    "archiviazione",
    "pamięć masowa",
]
CHIP_SECTION_MARKERS = [
    "chip",
    "puce",
    "czip",
]
KNOWN_SSD_OVERRIDES_BY_PRODUCT_CODE = {
    # iMac M4 8-core CPU / 8-core GPU listings where storage is intermittently absent in localized detail text.
    "fwue3ze": 256,
    "fwug3ze": 256,
    "g1e20ze": 256,
    "g1e50n": 256,
}


def normalize_text(text):
    text = unescape(text or "")
    text = text.replace('\u00a0', ' ').replace('\u2009', ' ').replace('\u202f', ' ')
    text = text.replace('\u00ad', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
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


def dedupe_text_parts(parts):
    deduped = []
    seen = set()

    for part in parts:
        normalized = normalize_text(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    return deduped


def wait_for_page_settle(page, selector=None, timeout=15000, settle_seconds=0):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass

    if selector:
        try:
            page.wait_for_selector(selector, timeout=timeout)
        except Exception:
            pass

    if settle_seconds:
        time.sleep(settle_seconds)


def extract_prioritized_detail_sections(body_text):
    normalized_body = normalize_text(body_text)
    lowered = normalized_body.lower()
    sections = []
    seen_ranges = set()

    for marker in DETAIL_SPEC_SECTION_MARKERS:
        start = 0
        while True:
            idx = lowered.find(marker, start)
            if idx == -1:
                break

            window_start = idx
            window_end = min(len(normalized_body), idx + DETAIL_SPEC_SECTION_WINDOW)
            window_key = (window_start, window_end)
            if window_key not in seen_ranges:
                seen_ranges.add(window_key)
                sections.append(normalized_body[window_start:window_end])

            start = idx + len(marker)

    return dedupe_text_parts(sections)


def storage_value_in_gb(raw_value, raw_unit):
    value = int(raw_value)
    unit = raw_unit.lower()
    if unit in {'tb', 'to'}:
        value *= 1024
    return value


def is_reasonable_storage_value(value):
    return isinstance(value, int) and 0 < value <= MAX_REASONABLE_STORAGE_GB


def first_valid_ram_value(text):
    ram_patterns = [
        rf'(?<!\d)(?:20\d{{2}}[\s-]*)?(\d{{1,3}}){NUMBER_UNIT_SEP}{RAM_UNIT_PATTERN}[\s,;:()/-]*(?:(?:de|di|del|della|z|van)\s+)?(?:unified\s*memory|gemeinsamer\s*arbeitsspeicher|mémoire\s*unifiée|mémoire|zunifikowanej\s*pamięci|pamięci\s*ram|pamięć\s*ram|centraal\s*geheugen|geheugen|memoria\s*unificada|memoria\s*unificata|ram|memory|arbeitsspeicher)',
        rf'(?:(?:ram|memory|arbeitsspeicher|mémoire|pamięć|pamięci|geheugen|memoria)\s*)[:\-]\s*(?<!\d)(\d{{1,4}}){NUMBER_UNIT_SEP}{RAM_UNIT_PATTERN}',
    ]

    candidates = []
    for pattern in ram_patterns:
        for match in re.finditer(pattern, text):
            ram_value = sanitize_ram_value(int(match.group(1)))
            if ram_value is not None:
                candidates.append((match.start(), ram_value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def first_valid_storage_value(text, category, device_type):
    ssd_keywords = r'(?:ssd(?:\s*-\s*opslag)?|flash\s*storage|massenspeicher|stockage|opslag|almacenamiento|archiviazione|lagring|úložiště|pamięci\s*masowej|pamięć\s*masowa|pamięci\s*ssd|storage|speicherplatz)'
    ssd_patterns = [
        rf'{ssd_keywords}[\s,;:()/-]*(?:von|de|del|di|z|da|van)?\s*(\d+){NUMBER_UNIT_SEP}{STORAGE_UNIT_PATTERN}',
        rf'(\d+){NUMBER_UNIT_SEP}{STORAGE_UNIT_PATTERN}\b[\s,;:()/-]*{ssd_keywords}',
    ]
    candidates = []

    for pattern in ssd_patterns:
        for match in re.finditer(pattern, text):
            storage_value = storage_value_in_gb(match.group(1), match.group(2))
            if is_reasonable_storage_value(storage_value):
                candidates.append((match.start(), storage_value))

    is_mac = category == 'mac' or device_type in MAC_DEVICE_TYPES
    if not candidates and is_mac:
        storage_capacity_pattern = (
            rf'(?:storage|opslag|stockage|massenspeicher|speicherplatz|almacenamiento|archiviazione|pamięci\s*masowej|pamięć\s*masowa|pojemno(?:ść|sci)|capacity|capacità|capaciteit|kapazität|capacité)'
            rf'[\s,;:()/-]*(?:von|de|del|di|z|da|van|o)?[\s,;:()/-]*(\d+){NUMBER_UNIT_SEP}{STORAGE_UNIT_PATTERN}'
        )
        for match in re.finditer(storage_capacity_pattern, text):
            storage_value = storage_value_in_gb(match.group(1), match.group(2))
            if is_reasonable_storage_value(storage_value):
                candidates.append((match.start(), storage_value))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def merge_specs(base, updates, prefer_updates=False):
    merged = dict(base)
    for key in ['ram', 'ssd', 'chip', 'screen']:
        update_value = updates.get(key)
        if update_value is None:
            continue

        current_value = merged.get(key)
        if prefer_updates or current_value is None:
            merged[key] = update_value
    # Only replace generic type names
    if prefer_updates:
        update_type = updates.get('device_type')
        current_type = merged.get('device_type')
        if update_type and update_type != 'Device':
            # Keep a specific listing type when detail parsing only falls back to a generic category label.
            if not (update_type in GENERIC_DEVICE_TYPES and current_type not in GENERIC_DEVICE_TYPES):
                merged['device_type'] = update_type
    elif merged.get('device_type') in [None, 'Device', *GENERIC_DEVICE_TYPES]:
        if updates.get('device_type') and updates['device_type'] != 'Device':
            merged['device_type'] = updates['device_type']
    return merged


def apply_known_overrides(product):
    url = product.get('url', '')
    match = re.search(r'/product/([^/]+)/', url)
    if not match:
        return product

    code = match.group(1).lower()
    specs = product.get('specs', {})

    if specs.get('ssd') is None and code in KNOWN_SSD_OVERRIDES_BY_PRODUCT_CODE:
        specs['ssd'] = KNOWN_SSD_OVERRIDES_BY_PRODUCT_CODE[code]

    return product


def extract_detail_text_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    parts = []
    if soup.title and soup.title.get_text(strip=True):
        parts.append(soup.title.get_text(" ", strip=True))

    tech_specs_parts = extract_tech_specs_text_from_html(html, soup)
    if tech_specs_parts:
        parts.extend(tech_specs_parts)
        return normalize_text(" ".join(dedupe_text_parts(parts)))

    if soup.body:
        body_text = soup.body.get_text(" ", strip=True)
        if body_text:
            parts.extend(extract_prioritized_detail_sections(body_text))
            parts.append(body_text[:20000])

    # Structured data can include storage fields that are not visible in normal copy.
    for script in soup.select('script[type="application/ld+json"]'):
        script_text = normalize_text(script.get_text(" ", strip=True))
        if script_text:
            parts.append(script_text[:12000])

    desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_meta and desc_meta.get('content'):
        parts.append(desc_meta.get('content').replace('|', ' '))

    return normalize_text(" ".join(dedupe_text_parts(parts)))


def extract_json_object_after_marker(text, marker):
    marker_index = text.find(marker)
    if marker_index == -1:
        return None

    start = text.find('{', marker_index + len(marker))
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for idx in range(start, len(text)):
        char = text[idx]

        if in_string:
            if escape_next:
                escape_next = False
            elif char == '\\':
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:idx + 1]

    return None


def html_fragment_to_text(fragment):
    if not fragment:
        return ""
    return normalize_text(BeautifulSoup(fragment, 'html.parser').get_text(" ", strip=True))


def heading_matches(heading, markers):
    lowered = normalize_text(heading).lower()
    return lowered in markers


class TechSpecsStructureError(ValueError):
    pass


def has_meaningful_tech_specs_sections(sections):
    if len(sections) < MIN_TECH_SPECS_SECTIONS:
        return False

    item_count = sum(len(section.get('items', [])) for section in sections)
    return item_count >= MIN_TECH_SPECS_ITEMS


def extract_tech_specs_sections_from_dom(soup):
    panel = soup.select_one('.TechSpecs-panel')
    if not panel:
        return []

    main_panel = panel.select_one('.rc-pdsection-mainpanel') or panel
    sections = []
    current_heading = None
    current_items = []

    for child in main_panel.children:
        if not getattr(child, 'name', None):
            continue

        child_classes = set(child.get('class', []))
        if child.name == 'h4' and 'h4-para-title' in child_classes:
            if current_heading:
                sections.append({
                    'heading': current_heading,
                    'items': dedupe_text_parts(current_items),
                })
            current_heading = normalize_text(child.get_text(" ", strip=True))
            current_items = []
            continue

        if not current_heading:
            continue

        text = normalize_text(child.get_text(" ", strip=True))
        if text:
            current_items.append(text)

    if current_heading:
        sections.append({
            'heading': current_heading,
            'items': dedupe_text_parts(current_items),
        })

    return [section for section in sections if section['heading'] and section['items']]


def flatten_tech_specs_sections(sections):
    parts = []
    for section in sections:
        parts.append(section['heading'])
        parts.extend(section['items'])
    return dedupe_text_parts(parts)


def extract_nested_tech_specs_text(node):
    parts = []

    if isinstance(node, str):
        text = html_fragment_to_text(node)
        if text:
            parts.append(text)
        return parts

    if isinstance(node, list):
        for item in node:
            parts.extend(extract_nested_tech_specs_text(item))
        return parts

    if not isinstance(node, dict):
        return parts

    for key in (
        'groupTitleFromAsset',
        'groupTitleFromAttribute',
        'paragraphText',
        'value',
        'text',
        'title',
    ):
        if node.get(key):
            parts.extend(extract_nested_tech_specs_text(node[key]))

    for key in ('attributeList', 'imageValue', 'imageValueList', 'items'):
        if node.get(key):
            parts.extend(extract_nested_tech_specs_text(node[key]))

    return parts


def extract_page_level_section_text(html, section_name):
    payload = extract_json_object_after_marker(html, f"window.pageLevelData.{section_name} =")
    if not payload:
        return []

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    parts = []
    section_title = data.get('sectionTitle')
    if section_title:
        parts.append(section_title)

    groups = (((data.get('tiles') or {}).get('groups') or {}).get('items') or [])
    for group_entry in groups:
        value = group_entry.get('value') or {}

        for key in ('mutiValueAttributeSelector', 'multiValueAttributeSelector', 'listOfAttributes'):
            selector = value.get(key)
            if not selector:
                continue

            parts.extend(extract_nested_tech_specs_text(selector))

    return dedupe_text_parts(parts)


def extract_tech_specs_dom_text(soup):
    sections = extract_tech_specs_sections_from_dom(soup)
    return flatten_tech_specs_sections(sections)


def extract_tech_specs_text_from_html(html, soup):
    return extract_tech_specs_dom_text(soup)


def extract_detail_specs_from_html(html, category='mac'):
    soup = BeautifulSoup(html, 'html.parser')
    title_text = normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    title_specs, _ = parse_specs(title_text, category)
    specs = merge_specs({
        "ram": None,
        "ssd": None,
        "chip": None,
        "screen": None,
        "device_type": "Device"
    }, title_specs, prefer_updates=True)

    sections = extract_tech_specs_sections_from_dom(soup)
    if not has_meaningful_tech_specs_sections(sections):
        raise TechSpecsStructureError(
            "Detailed Tech Specs DOM block missing or incomplete; site structure likely changed and the whole page needs re-analysis."
        )

    for section in sections:
        section_text = normalize_text(" ".join([section['heading'], *section['items']]))
        section_first_text = normalize_text(f"{section_text} {title_text}")
        parsed_section_specs, _ = parse_specs(section_first_text, category)

        if heading_matches(section['heading'], CHIP_SECTION_MARKERS) and parsed_section_specs.get('chip') is not None:
            specs['chip'] = parsed_section_specs['chip']
        elif heading_matches(section['heading'], MEMORY_SECTION_MARKERS) and parsed_section_specs.get('ram') is not None:
            specs['ram'] = parsed_section_specs['ram']
        elif heading_matches(section['heading'], STORAGE_SECTION_MARKERS) and parsed_section_specs.get('ssd') is not None:
            specs['ssd'] = parsed_section_specs['ssd']
        elif heading_matches(section['heading'], DISPLAY_SECTION_MARKERS) and parsed_section_specs.get('screen') is not None:
            specs['screen'] = parsed_section_specs['screen']

    detail_text = normalize_text(" ".join(dedupe_text_parts([title_text, *flatten_tech_specs_sections(sections)])))
    fallback_specs, _ = parse_specs(detail_text, category)
    specs = merge_specs(specs, fallback_specs, prefer_updates=False)
    return specs, detail_text


def fetch_detail_html(product_url):
    last_error = None
    for attempt in range(DETAIL_FETCH_RETRIES):
        try:
            req = urllib.request.Request(product_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as exc:
            last_error = exc
            if attempt + 1 < DETAIL_FETCH_RETRIES:
                time.sleep(DETAIL_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise last_error


def fetch_detail_html_playwright(page, product_url):
    last_error = None
    for attempt in range(DETAIL_FETCH_RETRIES):
        try:
            page.goto(product_url, timeout=60000, wait_until="domcontentloaded")
            wait_for_page_settle(page, selector=TECH_SPECS_SELECTOR, timeout=15000, settle_seconds=DETAIL_SETTLE_SECONDS)
            for _ in range(DETAIL_SCROLL_STEPS):
                page.evaluate("window.scrollBy(0, 1200)")
                time.sleep(DETAIL_SCROLL_DELAY_SECONDS)
            wait_for_page_settle(page, selector=TECH_SPECS_SELECTOR, timeout=10000, settle_seconds=DETAIL_SETTLE_SECONDS)
            return page.content()
        except Exception as exc:
            last_error = exc
            try:
                page.goto("about:blank", timeout=10000, wait_until="domcontentloaded")
            except Exception:
                pass
            if attempt + 1 < DETAIL_FETCH_RETRIES:
                time.sleep(DETAIL_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise last_error


def extract_detail_text(product_url):
    last_error = None
    for attempt in range(DETAIL_FETCH_RETRIES):
        try:
            req = urllib.request.Request(product_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
            return extract_detail_text_from_html(html)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < DETAIL_FETCH_RETRIES:
                time.sleep(DETAIL_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise last_error


def extract_detail_text_playwright(page, product_url):
    last_error = None
    for attempt in range(DETAIL_FETCH_RETRIES):
        try:
            page.goto(product_url, timeout=60000, wait_until="domcontentloaded")
            wait_for_page_settle(page, selector=TECH_SPECS_SELECTOR, timeout=15000, settle_seconds=DETAIL_SETTLE_SECONDS)
            for _ in range(DETAIL_SCROLL_STEPS):
                page.evaluate("window.scrollBy(0, 1200)")
                time.sleep(DETAIL_SCROLL_DELAY_SECONDS)
            wait_for_page_settle(page, selector=TECH_SPECS_SELECTOR, timeout=10000, settle_seconds=DETAIL_SETTLE_SECONDS)
            return extract_detail_text_from_html(page.content())
        except Exception as exc:
            last_error = exc
            try:
                page.goto("about:blank", timeout=10000, wait_until="domcontentloaded")
            except Exception:
                pass
            if attempt + 1 < DETAIL_FETCH_RETRIES:
                time.sleep(DETAIL_FETCH_BACKOFF_SECONDS * (attempt + 1))
    raise last_error


def needs_detail_enrichment(product):
    specs = product.get('specs', {})
    category = product.get('category')
    device_type = specs.get('device_type')

    if category == 'mac':
        if specs.get('ram') is None or specs.get('ssd') is None:
            return True
        return supports_screen_buckets(device_type) and specs.get('screen') is None

    if category in ['ipad', 'iphone', 'appletv'] and specs.get('ssd') is None:
        return True

    # Accessories and watches should not force RAM/SSD enrichment.
    if category in ['watch', 'accessories'] or device_type in ACCESSORY_TYPES:
        return False
    return False


def needs_retry_detail_enrichment(product):
    specs = product.get('specs', {})
    category = product.get('category')

    if category == 'mac':
        return specs.get('ram') is None or specs.get('ssd') is None

    if category in ['ipad', 'iphone', 'appletv']:
        return specs.get('ssd') is None

    return False


def enrich_products_with_detail_specs(products, country_code, browser=None):
    cache = {}
    enriched = 0
    errors = []
    detail_page = browser.new_page() if browser else None

    try:
        for product in products:
            if not needs_detail_enrichment(product):
                continue

            url = product.get('url')
            if not url:
                continue

            try:
                if url not in cache:
                    detail_texts = []

                    # Keep urllib as a stable baseline.
                    try:
                        urllib_html = fetch_detail_html(url)
                        if urllib_html:
                            detail_texts.append(urllib_html)
                    except Exception as e:
                        errors.append(f"urllib detail fetch failed ({country_code}): {url} -> {e}")

                    # Rendered page can expose extra localized/spec data.
                    if detail_page is not None:
                        try:
                            playwright_html = fetch_detail_html_playwright(detail_page, url)
                            if playwright_html:
                                detail_texts.append(playwright_html)
                        except Exception as e:
                            errors.append(f"Playwright detail fetch failed ({country_code}): {url} -> {e}")

                    cache[url] = detail_texts
                    time.sleep(DETAIL_FETCH_THROTTLE_SECONDS)

                detail_texts = cache[url]
                if detail_texts:
                    merged_specs = dict(product['specs'])
                    for detail_html in detail_texts:
                        detail_specs, _ = extract_detail_specs_from_html(detail_html, product.get('category', 'mac'))
                        merged_specs = merge_specs(merged_specs, detail_specs, prefer_updates=True)
                    if merged_specs != product['specs']:
                        product['specs'] = merged_specs
                        enriched += 1
            except Exception as e:
                errors.append(f"Detail enrichment failed ({country_code}): {url} -> {e}")
    finally:
        if detail_page is not None:
            detail_page.close()

    print(f"  Detail enrichment ({country_code}): updated {enriched} products")
    return errors


def retry_unresolved_detail_specs(products):
    unresolved = [p for p in products if needs_retry_detail_enrichment(p)]
    if not unresolved:
        return []

    print(f"Running sequential retry enrichment for {len(unresolved)} unresolved products...")
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)

    try:
        return enrich_products_with_detail_specs(unresolved, "RETRY", browser)
    finally:
        browser.close()
        playwright.stop()


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
    if 23.0 <= value < 25.0:
        return 24
    if value < 20:
        return int(value)
    return None


def supports_screen_buckets(device_type):
    if not isinstance(device_type, str):
        return False
    if device_type in SCREEN_BUCKET_DEVICE_TYPES:
        return True
    return device_type.startswith('iPhone')


def device_filter_label(product):
    specs = product.get('specs', {})
    device_type = specs.get('device_type', 'Device')
    screen = specs.get('screen')

    inch_bucket = bucket_screen_inches(screen)
    if inch_bucket is not None and supports_screen_buckets(device_type):
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
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            wait_for_page_settle(page, selector=LISTING_TILE_SELECTOR, timeout=15000, settle_seconds=LISTING_SETTLE_SECONDS)
            
            # Check if 404 or redirect to home (some categories might be missing in some countries)
            if "as-refurbished" not in page.url and f"/{category}" not in page.url:
                print(f"  Skipping {category} in {country_code}: redirected to {page.url}")
                page.close()
                continue

            # Incremental scroll to trigger lazy loading
            for _ in range(LISTING_SCROLL_STEPS): 
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(LISTING_SCROLL_DELAY_SECONDS)
            wait_for_page_settle(page, selector=LISTING_TILE_SELECTOR, timeout=10000, settle_seconds=LISTING_SETTLE_SECONDS)
                
            content = page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Select product tiles
            tiles = soup.select(LISTING_TILE_SELECTOR)
            
            for tile in tiles:
                try:
                    title_elem = tile.select_one('h3 a')
                    if not title_elem:
                        continue
                        
                    name = normalize_text(title_elem.get_text(strip=True))
                    item_url = urljoin(config['base_url'], title_elem['href'])
                    
                    # Image
                    img_elem = tile.select_one('img')
                    image = ""
                    if img_elem:
                        image = (
                            img_elem.get('src')
                            or img_elem.get('data-src')
                            or img_elem.get('data-image-src')
                            or ""
                        )
                        if not image:
                            srcset = img_elem.get('srcset') or img_elem.get('data-srcset') or ""
                            if srcset:
                                image = srcset.split(",")[0].strip().split(" ")[0]
                    
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
                    prod = apply_known_overrides(prod)
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

    country_errors.extend(enrich_products_with_detail_specs(all_category_items, country_code, browser))
    all_category_items = [apply_known_overrides(p) for p in all_category_items]
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
        specs['ram'] = first_valid_ram_value(text)

    # SSD
    if not is_accessory:
        specs['ssd'] = first_valid_storage_value(text, category, specs['device_type'])
        
        # Allow simple GB search for iPad/iPhone/AppleTV if no "SSD" keyword found
        if specs['ssd'] is None and category in ['ipad', 'iphone', 'appletv']:
            simple_gb = re.search(rf'(\d+){NUMBER_UNIT_SEP}{STORAGE_UNIT_PATTERN}', text)
            if simple_gb:
                specs['ssd'] = storage_value_in_gb(simple_gb.group(1), simple_gb.group(2))

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
    if supports_screen_buckets(specs['device_type']):
        display_heading_pattern = r'(?:' + '|'.join(re.escape(marker) for marker in DISPLAY_SECTION_MARKERS) + r')'
        screen_patterns = [
            rf'{display_heading_pattern}.{{0,260}}?(\d{{1,2}}[.,]\d)\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))',
            rf'{display_heading_pattern}.{{0,260}}?(\d{{1,2}})\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))',
            r'(\d{1,2}[.,]\d)\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))',
            r'(\d{1,2})\s*(?:["”]|-?\s*(?:inch|inches|cal(?:i|owy|owe)?|zoll|pouces|pulgadas|pollici))',
        ]
        screen_match = None
        for pattern in screen_patterns:
            screen_match = re.search(pattern, text)
            if screen_match:
                break
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

    issue_lines = []

    macs = [p for p in all_products if p.get('category') == 'mac']
    if macs:
        missing_mac_ram = sum(1 for p in macs if p.get('specs', {}).get('ram') is None)
        missing_mac_ssd = sum(1 for p in macs if p.get('specs', {}).get('ssd') is None)
        if missing_mac_ram:
            issue_lines.append(f"Mac missing RAM: {missing_mac_ram / len(macs) * 100:.1f}%")
        if missing_mac_ssd:
            issue_lines.append(f"Mac missing SSD: {missing_mac_ssd / len(macs) * 100:.1f}%")

    iphones = [p for p in all_products if p.get('category') == 'iphone']
    if iphones:
        missing_iphone_storage = sum(1 for p in iphones if p.get('specs', {}).get('ssd') is None)
        if missing_iphone_storage:
            issue_lines.append(f"iPhone missing storage: {missing_iphone_storage / len(iphones) * 100:.1f}%")

    ipads = [p for p in all_products if p.get('category') == 'ipad']
    if ipads:
        missing_ipad_storage = sum(1 for p in ipads if p.get('specs', {}).get('ssd') is None)
        if missing_ipad_storage:
            issue_lines.append(f"iPad missing storage: {missing_ipad_storage / len(ipads) * 100:.1f}%")

    other_devices = [p for p in all_products if p.get('category') not in {'mac', 'iphone', 'ipad'}]
    if other_devices:
        missing_other_prices = sum(
            1 for p in other_devices
            if not isinstance(p.get('price'), (int, float)) or p.get('price') <= 0
        )
        if missing_other_prices:
            issue_lines.append(f"Other devices missing price: {missing_other_prices / len(other_devices) * 100:.1f}%")

    issue_stats_html = ""
    if issue_lines:
        issue_stats_html = '<div class="issue-stats">Issues: ' + ' · '.join(escape(line) for line in issue_lines) + '</div>'

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
            --frame-accent: #c5d0e5;
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
            --bg-0: #0e100f;
            --bg-1: #181b19;
            --panel: #1d211f;
            --panel-border: #303934;
            --frame-accent: #567160;
            --text: #edf1ed;
            --muted: #a2aca5;
            --accent: #9fc6aa;
            --price: #bff0cb;
            --card-grad-1: #252927;
            --card-grad-2: #181b1a;
            --img-grad-1: #2d3430;
            --img-grad-2: #181b1a;
            --img-shadow: rgba(0,0,0,0.45);
            --img-blend: multiply;
            --img-filter: drop-shadow(0 14px 18px var(--img-shadow)) contrast(1.03);
            --img-overlay: rgba(14,16,15,0.22);
            --bg-glow-1: rgba(92, 98, 94, 0.34);
            --bg-glow-2: rgba(52, 78, 63, 0.28);
        }}
        @media (prefers-color-scheme: dark) {{
            :root:not([data-theme='light']) {{
                --bg-0: #0e100f;
                --bg-1: #181b19;
                --panel: #1d211f;
                --panel-border: #303934;
                --frame-accent: #567160;
                --text: #edf1ed;
                --muted: #a2aca5;
                --accent: #9fc6aa;
                --price: #bff0cb;
                --card-grad-1: #252927;
                --card-grad-2: #181b1a;
                --img-grad-1: #2d3430;
                --img-grad-2: #181b1a;
                --img-shadow: rgba(0,0,0,0.45);
                --img-blend: multiply;
                --img-filter: drop-shadow(0 14px 18px var(--img-shadow)) contrast(1.03);
                --img-overlay: rgba(14,16,15,0.22);
                --bg-glow-1: rgba(92, 98, 94, 0.34);
                --bg-glow-2: rgba(52, 78, 63, 0.28);
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
        .theme-control {{ margin-top: 12px; }}
        .controls {{ display: flex; gap: 15px; justify-content: center; margin-bottom: 20px; flex-wrap: wrap; }}
        select {{ padding: 8px; border-radius: 8px; border: 1px solid var(--panel-border); font-size: 14px; background: var(--panel); color: var(--text); }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
        .card {{ background: linear-gradient(180deg, var(--card-grad-1), var(--card-grad-2)); border: 1px solid var(--panel-border); border-radius: 18px; overflow: hidden; box-shadow: 0 8px 26px rgba(0,0,0,0.18); transition: transform 0.2s, border-color 0.2s; display: flex; flex-direction: column; }}
        .card:hover {{ transform: translateY(-4px); border-color: var(--frame-accent); }}
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
        .issue-stats {{
            position: absolute;
            top: 20px;
            left: 20px;
            max-width: 420px;
            font-size: 12px;
            line-height: 1.35;
            color: var(--muted);
        }}
        a {{ text-decoration: none; color: inherit; }}
    </style>
</head>
<body>
    {issue_stats_html}
    <div class="attribution">
        made by <a href="https://gelosi.github.io" target="_blank">gelosi</a><br>
        get notifications via <a href="https://refurb-tracker.com" target="_blank">refurb-tracker</a>
    </div>
    <div class="header">
        <h1>Apple Refurbished Tracker</h1>
        <p>Tracking {len(all_products)} items across {len(countries)} countries</p>
        <p style="font-size: 14px; color: var(--muted); margin-top: 5px;">Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <div class="theme-control">
            <select id="themeFilter" onchange="setTheme(this.value)">
                <option value="system">Theme: System</option>
                <option value="light">Theme: Light</option>
                <option value="dark">Theme: Dark</option>
            </select>
        </div>
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

        function supportsScreenBucket(deviceType) {{
            return [
                'MacBook Air',
                'MacBook Pro',
                'iMac',
                'iPad',
                'iPad Pro',
                'iPad Air',
                'iPad mini',
            ].includes(deviceType) || deviceType.startsWith('iPhone');
        }}

        function getDeviceFilterValue(p) {{
            const bucket = bucketScreen(p.specs.screen);
            if (bucket && supportsScreenBucket(p.specs.device_type)) {{
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
    with ProcessPoolExecutor(max_workers=min(MAX_COUNTRY_WORKERS, len(valid_countries))) as executor:
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

    master_errors.extend(retry_unresolved_detail_specs(all_items))
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
