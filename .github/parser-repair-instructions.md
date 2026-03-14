# Parser Repair Instructions

Read `AGENTS.md` first. It contains the repo-specific operating rules and definition of done.

For scraper or data-quality work:

- Use `./run_scraper.sh` for full scrape runs. It bootstraps the virtualenv, runs the scraper, and then runs verification.
- Use `python3 scraper/verify_data.py` to report exact totals from the current `index.html`.
- If you change `scraper/scraper.py`, regenerate `index.html` in the same branch before opening a PR.
- When running through automation, keep Gemini CLI edits limited to `scraper/scraper.py`; the workflow regenerates `index.html` afterward.
- Keep parser changes narrow. Prefer improving `parse_specs` or detail enrichment before adding SKU-specific overrides.
- Only keep scraper/index changes when they do not reduce `Total Products`, do not worsen `Missing RAM` or `Missing SSD`, and do not introduce more implausible RAM values.
- Run `python3 -m py_compile scraper/scraper.py scraper/verify_data.py scripts/metrics_gate.py scripts/parser_repair.py` before finishing.
- Do not change unrelated files.
