#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
GEMINI_BIN="${GEMINI_BIN:-gemini}"
ALLOW_DIRTY="false"

usage() {
  cat <<'EOF'
Usage: scripts/test_parser_repair_local.sh [--model MODEL] [--gemini-bin PATH] [--allow-dirty]

Runs the local Gemini CLI parser repair loop:
1. Captures baseline verifier metrics
2. Invokes Gemini CLI headlessly against scraper/scraper.py
3. Re-runs the scraper
4. Validates the resulting metrics with scripts/parser_repair.py

Environment:
  GEMINI_API_KEY   Required Gemini API key
  GEMINI_MODEL     Optional model override (default: gemini-2.5-flash)
  GEMINI_BIN       Optional Gemini CLI binary path (default: gemini)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      MODEL="${2:?missing model value}"
      shift 2
      ;;
    --gemini-bin)
      GEMINI_BIN="${2:?missing gemini binary path}"
      shift 2
      ;;
    --allow-dirty)
      ALLOW_DIRTY="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "GEMINI_API_KEY is not set." >&2
  exit 1
fi

if ! command -v "$GEMINI_BIN" >/dev/null 2>&1; then
  echo "Gemini CLI not found: $GEMINI_BIN" >&2
  exit 1
fi

if [[ "$ALLOW_DIRTY" != "true" ]] && [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit/stash changes first, or rerun with --allow-dirty." >&2
  exit 1
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/parser-repair-local.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT

BASELINE_JSON="$WORK_DIR/current-metrics.json"
BASELINE_REPORT="$WORK_DIR/current-report.txt"
REPAIRED_JSON="$WORK_DIR/repaired-metrics.json"
SUMMARY_FILE="$WORK_DIR/gemini-summary.txt"
OUTPUT_JSON="$WORK_DIR/gemini-output.json"
PROMPT_FILE="$WORK_DIR/gemini-prompt.txt"
COMMENT_OUT="$WORK_DIR/parser-repair-comment.md"
RESULT_JSON="$WORK_DIR/parser-repair-result.json"

python3 scraper/verify_data.py --json > "$BASELINE_JSON"
python3 scraper/verify_data.py > "$BASELINE_REPORT"

cat > "$PROMPT_FILE" <<EOF
You are fixing a Python parser regression in this repository.

Read \`AGENTS.md\` and \`.github/parser-repair-instructions.md\` first.

Current verifier metrics are:
$(cat "$BASELINE_JSON")

Current verifier report is:
$(cat "$BASELINE_REPORT")

Edit only \`scraper/scraper.py\`.
Do not modify \`index.html\`, workflow files, docs, issue text files, git metadata, or branches.
Do not commit or push.

Make the narrowest safe parser or detail-enrichment fix that can improve missing RAM and/or missing SSD without reducing total products or increasing implausible RAM.

Leave the repository ready for these exact commands to be run after you finish:
- \`python3 -m py_compile scraper/scraper.py scraper/verify_data.py scripts/metrics_gate.py scripts/parser_repair.py\`
- \`./run_scraper.sh\`
- \`python3 scraper/verify_data.py --json > repaired-metrics.json\`

If no safe fix is clear, make no code changes and say that explicitly.
EOF

echo "Running Gemini CLI with model: $MODEL"
"$GEMINI_BIN" \
  -p "$(cat "$PROMPT_FILE")" \
  --model "$MODEL" \
  --output-format json \
  --yolo \
  > "$OUTPUT_JSON"

python3 - <<'PY' "$OUTPUT_JSON" "$SUMMARY_FILE"
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
error = payload.get("error")
if error:
    raise SystemExit(f"Gemini CLI returned an error payload: {error}")
response = payload.get("response", "").strip()
if not response:
    raise SystemExit(f"Gemini CLI returned no response. Error: {error}")
Path(sys.argv[2]).write_text(response + "\n", encoding="utf-8")
PY

python3 -m py_compile scraper/scraper.py scraper/verify_data.py scripts/metrics_gate.py scripts/parser_repair.py
./run_scraper.sh
python3 scraper/verify_data.py --json > "$REPAIRED_JSON"

python3 scripts/parser_repair.py \
  --before-json "$BASELINE_JSON" \
  --after-json "$REPAIRED_JSON" \
  --summary-file "$SUMMARY_FILE" \
  --comment-out "$COMMENT_OUT" \
  --result-json-out "$RESULT_JSON"

echo "Local parser repair validation passed."
echo "Summary: $(cat "$SUMMARY_FILE")"
echo "Comment report: $COMMENT_OUT"
echo "Result JSON: $RESULT_JSON"
