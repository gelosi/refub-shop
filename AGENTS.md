# AI Working Guide

This guide defines expected assistant behavior and quality targets for this repository.

## Project Snapshot
- Goal: scrape Apple Refurbished listings by country and generate `index.html`.
- Core logic: `scraper/scraper.py`.
- Validation: `scraper/verify_data.py`.
- Preferred entrypoint: `run_scraper.sh` (env bootstrap + scrape + verify).

## User-Expected Assistant Behavior
- Execute requested checks yourself. Do not stop at suggestions when the task is executable locally.
- If user says "run verifier", run `python3 scraper/verify_data.py` and report exact numbers.
- If user says "just run scraper", use `./run_scraper.sh` (it already runs verification).
- If command cannot complete due environment/network restrictions, say that clearly and provide the best local fallback evidence.
- Follow commit scope exactly (example: "commit all but index.html" means do not include `index.html`).
- When fixing parser bugs, report before and after counts, not only code changes.

## Quality Targets (Expected Results)
- For normal runs, `mac` RAM completeness should be 100% (`Missing RAM (mac only): 0`).
- `Implausible RAM values (>512 GB)` should be `0`.
- SSD completeness should not regress; if a localized edge case remains, list affected SKUs/countries explicitly.
- Device labels must avoid incorrect screen suffixes on desktop Macs (no "Mac Studio 7 inch" style outputs).
- The issue box in generated HTML must describe problems accurately (no misleading combined labels).

## Known Historical Issues and Fix Patterns
1. RAM mis-parse from concatenated year+RAM tokens (example: `202416GB`).
Fix pattern: sanitize values against valid RAM set and recover suffix only when prefix is year-like.

2. SSD missing on localized pages with weak meta descriptions.
Fix pattern: enrich from multiple detail sources and parse body/structured data; add narrow fallbacks before broad regex.

3. Device filter regressions from screen bucketing.
Fix pattern: apply screen buckets only to display-bearing device families.

4. Runner failures from environment drift (`ModuleNotFoundError: playwright`).
Fix pattern: use `run_scraper.sh` bootstrap path and run scraper/verify with venv Python.

5. Persistent SKU-level data gaps (specific iMac M4 locale variants).
Fix pattern: allow tightly scoped SKU overrides with clear comments and periodic revalidation.

## Debug Workflow
1. Baseline current output:
```bash
python3 scraper/verify_data.py
```
2. Reproduce with country scope:
```bash
./run_scraper.sh --countries PL NL
```
3. If missing specs remain:
Capture exact products/SKUs from verifier output, patch `parse_specs` and/or enrichment conservatively, and add SKU overrides only when parser/enrichment cannot reliably recover source data.
4. Re-run and compare counts.

## Definition of Done for Parsing Changes
- `python3 -m py_compile scraper/scraper.py scraper/verify_data.py` passes.
- `python3 scraper/verify_data.py` shows intended improvement with no obvious collateral regression.
- If HTML regenerated, issue stats reflect current truth.
- Final report includes exact verifier totals.
- Final report includes changed files.
- Final report includes remaining known edge cases (if any).
