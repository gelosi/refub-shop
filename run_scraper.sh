#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python3"
PIP_BIN="$VENV_DIR/bin/pip3"
REQ_FILE="$ROOT_DIR/requirements.txt"

ensure_venv() {
    if [[ -x "$PYTHON_BIN" ]]; then
        return
    fi

    if [[ -d "$VENV_DIR" ]]; then
        echo "Repairing virtual environment at $VENV_DIR..."
        python3 -m venv --clear "$VENV_DIR"
    else
        echo "Creating virtual environment at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi

    if [[ ! -x "$PYTHON_BIN" ]]; then
        echo "Failed to create a working virtual environment at $VENV_DIR"
        exit 1
    fi
}

ensure_python_deps() {
    if [[ ! -f "$REQ_FILE" ]]; then
        echo "Missing requirements file: $REQ_FILE"
        exit 1
    fi

    local -a missing_packages=()
    while IFS= read -r requirement || [[ -n "$requirement" ]]; do
        requirement="${requirement%%#*}"
        requirement="$(echo "$requirement" | tr -d '[:space:]')"
        [[ -z "$requirement" ]] && continue

        package_name="$(echo "$requirement" | sed -E 's/[<>=!~].*$//')"
        if ! "$PIP_BIN" show "$package_name" >/dev/null 2>&1; then
            missing_packages+=("$package_name")
        fi
    done < "$REQ_FILE"

    if (( ${#missing_packages[@]} > 0 )); then
        echo "Installing missing Python dependencies: ${missing_packages[*]}"
        "$PIP_BIN" install -r "$REQ_FILE"
    else
        echo "Python dependencies already installed."
    fi
}

ensure_playwright_browser() {
    if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
PY
    then
        echo "Installing Playwright Chromium browser..."
        "$PYTHON_BIN" -m playwright install chromium
    else
        echo "Playwright Chromium browser already available."
    fi
}

ensure_venv
ensure_python_deps
ensure_playwright_browser

echo "Starting daily scrape..."
"$PYTHON_BIN" scraper/scraper.py "$@"

echo "Verifying data..."
"$PYTHON_BIN" scraper/verify_data.py

# Optional: git commit and push if running in a repo
# git add index.html
# git commit -m "Daily update: $(date)"
# git push

echo "Done!"
