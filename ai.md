# AI Prompts & Vibecoding Guide

This file contains prompts and context for working on the Apple Refurbished Scraper with an AI assistant.

## 🧠 Context
This is a "vibecoded" project—prioritizing speed, aesthetics, and functionality. It supports 10+ European countries and uses Playwright for scraping.

## 🤖 Useful Prompts

### Adding a New Country
```text
I want to add support for [Country Name] ([Country Code]).
The URL is: [Apple Refurb URL]
Currency: [Currency Symbol] (Rate to EUR: [Rate])
Please:
1. Update STORES in scraper/scraper.py
2. Update parse_specs regex if the language is new (examples of RAM/SSD text: [...])
3. Update README.md
```

### Debugging Regex
```text
The scraper isn't picking up SSD storage for [Country].
Here is the raw HTML/text from the product tile:
[Insert Text]
Please update the regex in `parse_specs` to handle this variation.
```

### Updating Exchange Rates
```text
The exchange rates in `scraper.py` are outdated.
Please update the `rate_to_eur` values for SE, PL, DK, CZ, etc. based on current market rates.
```

### Enhancing the Dashboard
```text
I want to make the index.html look more "premium".
- Add a dark mode toggle
- Use a glassmorphism effect for the cards
- Add a price history chart (if we start saving history)
```

## 📝 Vibecoding Philosophy
- **Ship it**: Better to have a working scraper than perfect code.
- **Fail gracefully**: If a spec parses wrong, default to 0 rather than crashing.
- **Look good**: The output `index.html` should be a joy to browse.
