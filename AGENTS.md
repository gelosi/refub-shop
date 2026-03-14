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

2. SSD missing on localized pages.
Fix pattern: enrich from the rendered detailed `Tech Specs` DOM, not from broad body/meta copy. Prefer section-local extraction from the storage block over whole-page regex fallback.

3. Detail-page spec extraction should prefer the full detailed Tech Specs DOM over compact or partial sources.
Fix pattern: on product pages, go straight to the expanded detailed tech specs block (`.TechSpecs-panel` / detailed tech specs accordion content), split it by section headings like `h4.h4-para-title`, and extract RAM/storage/display/chip from the rows that belong to that section. Do not prioritize `window.pageLevelData.TechSpecs` when the detailed DOM block is present; the DOM block carries richer fields such as wireless/audio/display details and is the preferred source for future parser work. If that detailed subtree is missing or clearly incomplete, treat it as a structure change and log the problem instead of falling back to broad whole-page regex parsing.

4. Tech Specs DOM extraction can fail even when `.TechSpecs-panel` exists.
Fix pattern: do not assume section `h4` nodes are direct children of `.rc-pdsection-mainpanel`. Walk the ordered `h4.h4-para-title` and `.para-list` nodes anywhere inside the Tech Specs subtree so wrapped section layouts still parse correctly.

5. Device filter regressions from screen bucketing.
Fix pattern: apply screen buckets only to display-bearing device families.

6. Runner failures from environment drift (`ModuleNotFoundError: playwright`).
Fix pattern: use `run_scraper.sh` bootstrap path and run scraper/verify with venv Python.

7. Persistent SKU-level data gaps (specific iMac M4 locale variants).
Fix pattern: allow tightly scoped SKU overrides with clear comments and periodic revalidation.

## Detail Parsing Priority
When working on product detail parsing, use this source order unless the user asks otherwise:
1. Detailed Tech Specs DOM block on the product page.
Identify `.TechSpecs-panel` or equivalent expanded detailed tech specs content, then treat each `h4.h4-para-title` heading plus its following `.para-list` rows as one semantic section. Do not assume the `h4` and `.para-list` nodes are direct children of `.rc-pdsection-mainpanel`; Apple can wrap each section in an extra container.
2. Targeted parsing from section-local text.
Parse RAM only from the memory section, storage only from the storage section, screen only from the display section, etc. This is preferred over whole-page regex scans.
3. If the detailed Tech Specs DOM block is missing or incomplete, log a structural parser problem.
Assume the HTML changed and the page needs re-analysis. Do not replace this with broad body/meta fallback parsing.

Avoid prioritizing `window.pageLevelData.TechSpecs` over the detailed DOM block. It can still exist on the page, but the detailed rendered section is the canonical source for future scraping improvements because it exposes the fullest per-product spec set.
Avoid using section order as the primary classifier. Section kind should come from heading text and section-local content, not a hardcoded section index.

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
When debugging detail enrichment, first confirm that `extract_tech_specs_sections_from_dom(...)` is returning real sections from the live `.TechSpecs-panel`; if it returns zero sections on a page that visibly has Tech Specs, inspect the subtree shape before changing regexes.
4. Re-run and compare counts.

## Definition of Done for Parsing Changes
- `python3 -m py_compile scraper/scraper.py scraper/verify_data.py` passes.
- `python3 scraper/verify_data.py` shows intended improvement with no obvious collateral regression.
- If HTML regenerated, issue stats reflect current truth.
- Final report includes exact verifier totals.
- Final report includes changed files.
- Final report includes remaining known edge cases (if any).
