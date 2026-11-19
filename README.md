# Apple Refurbished Store Tracker

Track Apple Refurbished deals across multiple countries and browse them in one simple HTML page.

### [https://gelosi.github.io/refub-shop](https://gelosi.github.io/refub-shop)

The scraper collects refurbished Apple products from supported country stores, converts prices to EUR for easier comparison, and generates a standalone `index.html` dashboard with filters and sorting.

## What It Covers

The scraper currently supports these stores:

- Germany (`DE`)
- Ireland (`IE`)
- Netherlands (`NL`)
- France (`FR`)
- Poland (`PL`)
- Austria (`AT`)
- Spain (`ES`)
- Switzerland (`CH`)
- Italy (`IT`)
- Belgium (`BE`)
- United Kingdom (`UK`)

## What You Get

- A single generated `index.html` file
- Browsing by country, category, device, RAM, and storage
- Prices normalized to EUR
- "Overview" landing view: the cheapest iPhone, iPad, Watch, MacBook, MacBook Pro, iMac, Mac mini, Mac Studio and external display across all countries
- "Best prices" view (`#best`): the country where each device is cheapest
- "Country review" view (`#countries`): the cheapest offer per device in each country, grouped by category
- Direct links to the Apple product pages

## Running It

Run everything:

```bash
./run_scraper.sh
```

Run only specific countries:

```bash
./run_scraper.sh --countries UK CH BE IE
```

Run the verifier only:

```bash
python3 scraper/verify_data.py
```

## Where To Look Next

- Human-facing output: [index.html](index.html)
- Main scraper: [scraper.py](scraper/scraper.py)
- Verifier: [verify_data.py](scraper/verify_data.py)
- More technical project guidance: [AGENTS.md](AGENTS.md)

If you just want the results, use the GitHub Pages link above or open the generated `index.html`.
