import json
import re

def verify():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extract the JSON object from the script tag
        match = re.search(r'const products = (\[.*?\]);', content, re.DOTALL)
        if not match:
            print("Could not find products JSON in index.html")
            return

        products = json.loads(match.group(1))
        
        total = len(products)
        missing_ram = sum(1 for p in products if p['specs']['ram'] is None)
        missing_ssd = sum(1 for p in products if p['specs']['ssd'] is None)
        
        print(f"Total Products: {total}")
        print(f"Missing RAM: {missing_ram} ({missing_ram/total*100:.1f}%)")
        print(f"Missing SSD: {missing_ssd} ({missing_ssd/total*100:.1f}%)")
        
        # Print a few examples
        total_items = 0 # Re-initialize for this section if needed, or use 'total'
        missing_ram = 0 # Re-initialize for this section
        missing_ssd = 0 # Re-initialize for this section

        for p in products: # Assuming 'products' is the intended list to iterate over
            total_items += 1
            
            # Check RAM
            if p['specs']['ram'] is None:
                missing_ram += 1
                print(f"Missing RAM: {p['name']} ({p['country']})")
            
            # Check SSD
            if p['specs']['ssd'] is None:
                missing_ssd += 1
                print(f"Missing SSD: {p['name']} ({p['country']})") # Added print for SSD as well
                # We can't access original description from index.html easily as it wasn't saved in the json.
                # Wait, I didn't save the description in the products list in scraper.py?
                # Let's check scraper.py.
                # break # Removed break as it would stop after the first missing SSD
        
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify()
