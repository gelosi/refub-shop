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

## 🤖 Automated Parser Repair Loop
This repository now includes a three-stage automation flow for GitHub Actions plus Gemini CLI-based parser repair:

- `.github/workflows/scrape.yml`
  - runs the daily scrape
  - captures verifier metrics before and after the run for artifacts
  - commits the refreshed `index.html`
- `.github/workflows/validate-generated-data.yml`
  - validates pull requests against the current `main` branch metrics
  - requires regenerated `index.html` when scraper code changes
  - blocks scraper/index PRs that do not produce a measurable improvement
  - also runs after `Daily Scrape` finishes on `main`
  - checks the configured missing-RAM error-rate threshold
  - dispatches parser repair only when the threshold is exceeded
- `.github/workflows/parser-fix.yml`
  - opens or updates a parser repair issue
  - uses the official Gemini CLI GitHub Action to make a narrow edit to `scraper/scraper.py`
  - reruns `./run_scraper.sh`, validates the before/after verifier totals, and rejects non-helpful repairs
  - pushes successful repairs to `automation/parser-repair` and opens or updates a PR
  - fails with a clear message when `GEMINI_API_KEY` is missing or Gemini CLI hits quota/rate limits

### One-Time GitHub Setup
The repository files alone are not enough. You still need to configure GitHub:

1. Add a repository secret named `GEMINI_API_KEY`.
2. Optionally adjust `MISSING_RAM_TRIGGER_RATE_THRESHOLD` in `.github/workflows/validate-generated-data.yml`.
3. Ensure the default `GITHUB_TOKEN` can create issues, push branches, and open pull requests in this repository.
4. Optionally protect `main` and require the `Validate Generated Data` workflow before merge.

### Parser Repair Flow
When post-scrape validation exceeds the configured missing-RAM error-rate threshold:

1. `Daily Scrape` finishes independently and commits the latest `index.html`.
2. `Validate Generated Data` runs afterward and checks the current error rate on `main`.
3. If the threshold is exceeded, it dispatches `Parser Repair`.
4. `Parser Repair` creates or updates the `Daily scrape parser repair` issue, runs Gemini CLI headlessly for a bounded parser fix, reruns the scraper, and compares before/after verifier totals.
5. If the candidate repair is helpful, the workflow commits `scraper/scraper.py` plus regenerated `index.html` to `automation/parser-repair` and opens or updates a PR.
6. If the repair is not helpful, if `GEMINI_API_KEY` is missing, or if Gemini quota is exhausted, the repair workflow fails without affecting the scrape workflow and posts the failure reason to the issue.

## ⚠️ Disclaimer
This tool is not affiliated with, endorsed by, or connected to Apple Inc. It is a hobbyist project ("vibecoded") provided for educational and personal tracking purposes only.

## 📄 License
This project is released under the **Vibecoded Copyleft License**.
See the [LICENSE](LICENSE) file for details.
