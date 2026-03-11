import argparse
import json
import re
import sys
from pathlib import Path


PRODUCTS_PATTERN = re.compile(r"const products = (\[.*?\]);", re.DOTALL)


def load_products(index_path):
    content = Path(index_path).read_text(encoding="utf-8")
    match = PRODUCTS_PATTERN.search(content)
    if not match:
        raise ValueError(f"Could not find products JSON in {index_path}")
    return json.loads(match.group(1))


def collect_metrics(products, sample_limit=25):
    total = len(products)
    ram_applicable_categories = {"mac"}
    ssd_applicable_categories = {"mac", "ipad", "iphone", "appletv"}

    ram_applicable = [p for p in products if p["category"] in ram_applicable_categories]
    ssd_applicable = [p for p in products if p["category"] in ssd_applicable_categories]

    missing_ram_products = [p for p in ram_applicable if p["specs"]["ram"] is None]
    missing_ssd_products = [p for p in ssd_applicable if p["specs"]["ssd"] is None]
    implausible_ram_products = [
        p
        for p in ram_applicable
        if isinstance(p["specs"]["ram"], int) and p["specs"]["ram"] > 512
    ]

    return {
        "total_products": total,
        "ram_applicable_total": len(ram_applicable),
        "ssd_applicable_total": len(ssd_applicable),
        "missing_ram": len(missing_ram_products),
        "missing_ram_pct": (
            round(len(missing_ram_products) / len(ram_applicable) * 100, 1)
            if ram_applicable
            else 0.0
        ),
        "missing_ssd": len(missing_ssd_products),
        "missing_ssd_pct": (
            round(len(missing_ssd_products) / len(ssd_applicable) * 100, 1)
            if ssd_applicable
            else 0.0
        ),
        "implausible_ram": len(implausible_ram_products),
        "sample_missing_ram": [
            {"name": p["name"], "country": p["country"]}
            for p in missing_ram_products[:sample_limit]
        ],
        "sample_missing_ssd": [
            {"name": p["name"], "country": p["country"]}
            for p in missing_ssd_products[:sample_limit]
        ],
        "sample_implausible_ram": [
            {
                "name": p["name"],
                "country": p["country"],
                "ram": p["specs"]["ram"],
            }
            for p in implausible_ram_products[:sample_limit]
        ],
    }


def print_report(metrics):
    print(f"Total Products: {metrics['total_products']}")
    if metrics["ram_applicable_total"]:
        print(
            "Missing RAM (mac only): "
            f"{metrics['missing_ram']} ({metrics['missing_ram_pct']:.1f}%)"
        )
    else:
        print("Missing RAM (mac only): 0")

    if metrics["ssd_applicable_total"]:
        print(
            "Missing SSD (mac/ipad/iphone/appletv): "
            f"{metrics['missing_ssd']} ({metrics['missing_ssd_pct']:.1f}%)"
        )
    else:
        print("Missing SSD (mac/ipad/iphone/appletv): 0")

    print(f"Implausible RAM values (>512 GB): {metrics['implausible_ram']}")

    print("\nSample Missing RAM (max 25):")
    for product in metrics["sample_missing_ram"]:
        print(f"- {product['name']} ({product['country']})")

    print("\nSample Missing SSD (max 25):")
    for product in metrics["sample_missing_ssd"]:
        print(f"- {product['name']} ({product['country']})")

    if metrics["sample_implausible_ram"]:
        print("\nImplausible RAM entries:")
        for product in metrics["sample_implausible_ram"]:
            print(
                f"- {product['ram']} GB | {product['name']} ({product['country']})"
            )


def verify(index_path="index.html", as_json=False):
    products = load_products(index_path)
    metrics = collect_metrics(products)
    if as_json:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        print_report(metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Verify generated Apple scrape data.")
    parser.add_argument(
        "--index",
        default="index.html",
        help="Path to the generated index.html file. Default: index.html",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON metrics instead of the human-readable report.",
    )
    args = parser.parse_args()

    try:
        verify(index_path=args.index, as_json=args.json)
    except Exception as exc:
        print(f"Verification failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
