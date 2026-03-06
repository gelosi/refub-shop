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
        ram_applicable_categories = {'mac'}
        ssd_applicable_categories = {'mac', 'ipad', 'iphone', 'appletv'}

        ram_applicable = [p for p in products if p['category'] in ram_applicable_categories]
        ssd_applicable = [p for p in products if p['category'] in ssd_applicable_categories]

        missing_ram = sum(1 for p in ram_applicable if p['specs']['ram'] is None)
        missing_ssd = sum(1 for p in ssd_applicable if p['specs']['ssd'] is None)

        print(f"Total Products: {total}")
        if ram_applicable:
            print(f"Missing RAM (mac only): {missing_ram} ({missing_ram/len(ram_applicable)*100:.1f}%)")
        else:
            print("Missing RAM (mac only): 0")
        if ssd_applicable:
            print(f"Missing SSD (mac/ipad/iphone/appletv): {missing_ssd} ({missing_ssd/len(ssd_applicable)*100:.1f}%)")
        else:
            print("Missing SSD (mac/ipad/iphone/appletv): 0")

        print("\nSample Missing RAM (max 25):")
        shown = 0
        for p in ram_applicable:
            if p['specs']['ram'] is None:
                print(f"- {p['name']} ({p['country']})")
                shown += 1
                if shown >= 25:
                    break

        print("\nSample Missing SSD (max 25):")
        shown = 0
        for p in ssd_applicable:
            if p['specs']['ssd'] is None:
                print(f"- {p['name']} ({p['country']})")
                shown += 1
                if shown >= 25:
                    break
        
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify()
