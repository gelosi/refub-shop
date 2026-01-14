# 🍎 Apple Refurbished Store Tracker

> ⚠️ *Note: This is a "vibecoded" product. No responsibility is taken for missed deals using this software.*

A "vibecoded" automation tool that scrapes Apple's Refurbished Store across varying countries and currencies to find the best deals on Macs. It generates a static standalone HTML dashboard for easy browsing and filtering.

## 🚀 Features

*   **Multi-Region Support**: Tracks 10+ countries including Germany (DE), Poland (PL), Sweden (SE), Netherlands (NL), Ireland (IE), France (FR), Austria (AT), Spain (ES), and more.
*   **Intelligent Parsing**:
    *   **Multilingual**: Understands specs in English, German, Polish, Dutch, French, Spanish, etc.
    *   **Currency Normalization**: Converts prices (PLN, SEK, CHF, etc.) to formatted EUR for easy comparison.
    *   **Spec Extraction**: Regex-based extraction for M-series chips (M1, M2, M3, M4), RAM, and SSD storage.
*   **Static Dashboard**: Generates a zero-dependency `index.html` with:
    *   Instant filtering by Country, Device Model, RAM, and SSD.
    *   Client-side sorting (Price Low/High).
    *   Lazy-loading grid layout.
*   **Automation Ready**:
    *   Includes GitHub Actions workflow for daily scraping.
    *   Shell script for local execution.

## 🛠️ Usage

### Prerequisites
*   Python 3.9+
*   Playwright

### Installation
```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

### Running the Scraper
You can run the scraper for all configured countries or specific ones.

**Scrape All:**
```bash
python3 scraper/scraper.py
```

**Scrape Specific Countries:**
```bash
python3 scraper/scraper.py --countries DE PL SE NL
```

**Using the Shell Script:**
```bash
./run_scraper.sh --countries DE
```

### Viewing Results
Open `index.html` in your browser.

## ⚙️ Configuration
The scraper behavior is defined in `scraper/scraper.py`. You can adjust:
*   `STORES`: Dictionary mapping country codes to Apple Refurbished URLs.
*   `CURRENCY_RATES`: Fixed exchange rates for normalization (defaults provided).

## 🤖 GitHub Action
A `.github/workflows/scrape.yml` file is included to run the scraper daily (at 08:00 UTC) and commit the updated `index.html` back to the repository.

## ⚠️ Disclaimer
This tool is not affiliated with, endorsed by, or connected to Apple Inc. It is a hobbyist project ("vibecoded") provided for educational and personal tracking purposes only.

## 📄 License
This project is released under the **Vibecoded Copyleft License**.
See the [LICENSE](LICENSE) file for details.
