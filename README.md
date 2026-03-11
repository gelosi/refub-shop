# 🍎 Apple Refurbished Store Tracker

> ⚠️ *Note: This is a "vibecoded" product. No responsibility is taken for missed deals using this software.*

### [https://gelosi.github.io/refub-shop](https://gelosi.github.io/refub-shop)

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

## 🤖 Automated Copilot Repair Loop
This repository now includes a gated automation flow for GitHub Actions plus GitHub Copilot coding agent:

- `.github/workflows/scrape.yml`
  - runs the daily scrape
  - captures verifier metrics before and after the run
  - commits `index.html` only when `Total Products` does not decrease, missing RAM/SSD do not regress, and implausible RAM values do not regress
  - opens or updates a Copilot-assigned issue when the latest scrape regresses
- `.github/workflows/validate-generated-data.yml`
  - validates pull requests against the current `main` branch metrics
  - requires regenerated `index.html` when scraper code changes
  - blocks scraper/index PRs that do not produce a measurable improvement
- `.github/workflows/copilot-setup-steps.yml`
  - bootstraps Python dependencies and Playwright for GitHub Copilot coding agent

### One-Time GitHub Setup
The repository files alone are not enough. You still need to configure GitHub:

1. Enable GitHub Copilot coding agent for the repository.
2. Add a repository secret named `COPILOT_ASSIGNMENT_TOKEN`.
3. Use a token that can create issues and assign them in this repository.
4. Optionally protect `main` and require the `Validate Generated Data` workflow before merge.

### Copilot Issue Flow
When the scheduled scrape regresses:

1. The workflow does not commit the new `index.html`.
2. It creates or updates a `Daily scrape regression` issue.
3. The issue is assigned to Copilot and includes the baseline and latest verifier totals.
4. Copilot is expected to open a PR with both the scraper fix and regenerated `index.html`.

## ⚠️ Disclaimer
This tool is not affiliated with, endorsed by, or connected to Apple Inc. It is a hobbyist project ("vibecoded") provided for educational and personal tracking purposes only.

## 📄 License
This project is released under the **Vibecoded Copyleft License**.
See the [LICENSE](LICENSE) file for details.
