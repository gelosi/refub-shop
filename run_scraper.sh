#!/bin/bash


# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run scraper
echo "Starting daily scrape..."
python3 scraper/scraper.py "$@"

# Verify data
echo "Verifying data..."
python3 scraper/verify_data.py

# Optional: git commit and push if running in a repo
# git add index.html
# git commit -m "Daily update: $(date)"
# git push

echo "Done!"
