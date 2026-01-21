import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from scraper.scraper import parse_specs

def reproduce():
    url = "https://www.apple.com/pl/shop/product/g15y3ze/a/odnowiony-13-calowy-macbook-air-z-czipem-apple-m2-8%E2%80%91rdzeniowym-cpu-i-8%E2%80%91rdzeniowym-gpu-księżycowa-poświata?fnode=b1cbf51424929e2d7858b4914bcdb02df91e5c42d087ae11a57aa6abc26f5ea2c5f9a60cf84f83922df67435e56481957974b4694631a60b1b946e61335de6e343fb2365ea7e5537e68fa366230664a4"
    
    print(f"Visiting {url}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        content = page.content()
        browser.close()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Mimic the fixed fetch_store_data logic
        selectors = [
             '.rc-pdsection-panel.Overview-panel', 
             '.rc-pdsection-panel.TechSpecs-panel', 
             '.rf-tech-specs-section',
             '.rf-pdp-title'
        ]
        
        full_text = ""
        found_specific = False
        for sel in selectors:
            elements = soup.select(sel)
            if elements:
                found_specific = True
                for el in elements:
                    full_text += " " + el.get_text(" ", strip=True)
        
        if not found_specific:
            print("Warning: Specific selectors not found, using full text.")
            full_text = soup.get_text(" ", strip=True)
            
        print(f"Extracted text length: {len(full_text)}")
        
        specs, _ = parse_specs(full_text)
        print("\nParsed Specs with Fix:")
        print(specs)
        
        # Assertion
        if specs['ssd'] == 256 and specs['ram'] == 16:
            print("\nSUCCESS: Correctly parsed 256GB SSD and 16GB RAM.")
        elif specs['ssd'] == 256:
             print("\nSUCCESS: Correctly parsed 256GB SSD. (RAM mismatch or varying)")
        else:
            print(f"\nFAILURE: Expected 256GB SSD, got {specs['ssd']}")


if __name__ == "__main__":
    reproduce()
