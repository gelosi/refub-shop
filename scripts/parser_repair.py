import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from metrics_gate import compare_metrics


ALLOWED_EDIT_FILES = {"scraper/scraper.py"}


class RepairError(Exception):
    pass


def run_command(args, capture_output=True):
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def write_text(path, content):
    Path(path).write_text(content.rstrip() + "\n", encoding="utf-8")


def load_verify_metrics():
    result = run_command(["python3", "scraper/verify_data.py", "--json"])
    return json.loads(result.stdout)


def load_verify_report():
    result = run_command(["python3", "scraper/verify_data.py"])
    return result.stdout.strip()


def format_metrics(metrics):
    return (
        f"Total products: {metrics['total_products']}\n"
        f"Missing RAM (mac only): {metrics['missing_ram']} ({metrics['missing_ram_pct']}%)\n"
        f"Missing SSD (mac/ipad/iphone/appletv): {metrics['missing_ssd']} ({metrics['missing_ssd_pct']}%)\n"
        f"Implausible RAM (>512 GB): {metrics['implausible_ram']}"
    )


def extract_text_parts(response_payload):
    parts = []
    for candidate in response_payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text.strip())
    return "\n".join(parts).strip()


def parse_json_response(raw_text):
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_gemini(api_key, model, prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "x-goog-api-client": "github-actions-parser-repair/2.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429 or "RESOURCE_EXHAUSTED" in body or "quota" in body.lower():
            raise RepairError(
                "Gemini quota exceeded or the request was rate-limited. "
                "Increase quota or retry later."
            ) from exc
        raise RepairError(f"Gemini request failed with HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RepairError(f"Gemini request failed: {exc}") from exc

    raw_text = extract_text_parts(response_payload)
    if not raw_text:
        raise RepairError("Gemini returned no usable response text.")

    try:
        return parse_json_response(raw_text)
    except json.JSONDecodeError as exc:
        raise RepairError(
            f"Gemini returned invalid JSON: {raw_text[:500]}"
        ) from exc


def build_prompt(metrics, report, scraper_source, instructions, source_urls):
    return f"""You are fixing a Python parser in an Apple refurbished scraper repository.

Target file:
- `scraper/scraper.py`

Repository instructions:
<INSTRUCTIONS>
{instructions}
</INSTRUCTIONS>

Current verifier metrics:
{json.dumps(metrics, indent=2, sort_keys=True)}

Current verifier report:
{report}

Source workflow URLs:
{json.dumps(source_urls, indent=2, sort_keys=True)}

Current `scraper/scraper.py`:
<SCRAPER_PY>
{scraper_source}
</SCRAPER_PY>

Return JSON only with this schema:
{{
  "summary": "short explanation",
  "commit_message": "short git commit message under 72 chars",
  "edits": [
    {{
      "file": "scraper/scraper.py",
      "find": "exact existing text",
      "replace": "replacement text"
    }}
  ]
}}

Rules:
- Only edit `scraper/scraper.py`.
- Focus on parser or detail-enrichment fixes that can reduce missing RAM or missing SSD.
- Keep changes narrow and conservative.
- `find` text must match exactly once in the current file.
- Do not return markdown fences.
- Do not propose broad rewrites, renames, or unrelated cleanup.
- If no safe fix is clear, return an empty `edits` list and explain why in `summary`.
"""


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise RepairError("Gemini did not return a JSON object.")

    edits = plan.get("edits")
    if not isinstance(edits, list):
        raise RepairError("Gemini response is missing an edits list.")
    if not edits:
        raise RepairError(
            f"Gemini did not produce a safe repair edit. Summary: {plan.get('summary', 'n/a')}"
        )

    for edit in edits:
        if not isinstance(edit, dict):
            raise RepairError("Every edit must be a JSON object.")
        if edit.get("file") not in ALLOWED_EDIT_FILES:
            raise RepairError(f"Gemini attempted to edit a disallowed file: {edit.get('file')}")
        if not isinstance(edit.get("find"), str) or not edit["find"]:
            raise RepairError("Every edit must include a non-empty find string.")
        if not isinstance(edit.get("replace"), str):
            raise RepairError("Every edit must include a replace string.")


def apply_edits(edits):
    file_contents = {
        path: Path(path).read_text(encoding="utf-8")
        for path in sorted({edit["file"] for edit in edits})
    }

    for edit in edits:
        path = edit["file"]
        current = file_contents[path]
        occurrences = current.count(edit["find"])
        if occurrences != 1:
            raise RepairError(
                f"Edit target in {path} matched {occurrences} times instead of exactly once."
            )
        file_contents[path] = current.replace(edit["find"], edit["replace"], 1)

    for path, content in file_contents.items():
        Path(path).write_text(content, encoding="utf-8")


def sanitize_commit_message(value):
    text = " ".join((value or "").split()).strip()
    if not text:
        return "Parser repair: improve spec extraction"
    return text[:72]


def build_success_comment(plan, before_metrics, after_metrics, comparison):
    reason_lines = comparison["reasons"] or ["Latest run passed the non-regression gate."]
    reasons = "\n".join(f"- {line}" for line in reason_lines)
    return (
        "## Repair Result\n"
        f"- Gemini summary: {plan.get('summary', 'n/a')}\n"
        "- Decision: helpful parser repair generated and validated locally.\n\n"
        "## Before\n"
        f"{format_metrics(before_metrics)}\n\n"
        "## After\n"
        f"{format_metrics(after_metrics)}\n\n"
        "## Validation\n"
        f"{reasons}\n"
    )


def build_failure_comment(message, before_metrics=None, after_metrics=None, comparison=None):
    sections = ["## Repair Failure", f"- {message}"]
    if before_metrics:
        sections.extend(["", "## Baseline", format_metrics(before_metrics)])
    if after_metrics:
        sections.extend(["", "## Candidate Result", format_metrics(after_metrics)])
    if comparison and comparison.get("reasons"):
        sections.extend(["", "## Why It Was Rejected"])
        sections.extend(f"- {reason}" for reason in comparison["reasons"])
    return "\n".join(sections)


def write_result(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate and validate a Gemini-driven parser repair.")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--api-key-env", default="GEMINI_API_KEY")
    parser.add_argument("--comment-out", default="parser-repair-comment.md")
    parser.add_argument("--result-json-out", default="parser-repair-result.json")
    parser.add_argument("--source-validation-run-url", default="")
    parser.add_argument("--source-scrape-run-url", default="")
    args = parser.parse_args()

    before_metrics = None
    after_metrics = None
    comparison = None

    try:
        api_key = os.environ.get(args.api_key_env, "").strip()
        if not api_key:
            raise RepairError("GEMINI_API_KEY is not configured. Parser repair cannot run.")

        before_metrics = load_verify_metrics()
        before_report = load_verify_report()
        instructions = Path("AGENTS.md").read_text(encoding="utf-8") + "\n\n" + Path(
            ".github/parser-repair-instructions.md"
        ).read_text(encoding="utf-8")
        scraper_source = Path("scraper/scraper.py").read_text(encoding="utf-8")
        source_urls = {
            "validation_run_url": args.source_validation_run_url or "unavailable",
            "scrape_run_url": args.source_scrape_run_url or "unavailable",
        }

        plan = call_gemini(
            api_key=api_key,
            model=args.model,
            prompt=build_prompt(
                metrics=before_metrics,
                report=before_report,
                scraper_source=scraper_source,
                instructions=instructions,
                source_urls=source_urls,
            ),
        )
        validate_plan(plan)
        apply_edits(plan["edits"])

        run_command(
            [
                "python3",
                "-m",
                "py_compile",
                "scraper/scraper.py",
                "scraper/verify_data.py",
                "scripts/metrics_gate.py",
                "scripts/parser_repair.py",
            ],
            capture_output=True,
        )
        run_command(["./run_scraper.sh"], capture_output=False)

        after_metrics = load_verify_metrics()
        comparison = compare_metrics(before_metrics, after_metrics)
        if not comparison["should_commit"]:
            raise RepairError("Candidate repair regressed the generated data.")
        if not comparison["improved"]:
            raise RepairError("Candidate repair was not helpful; no tracked metric improved.")

        changed_files = run_command(["git", "diff", "--name-only"], capture_output=True).stdout.splitlines()
        expected_changes = {"scraper/scraper.py", "index.html"}
        unexpected_changes = sorted(set(changed_files) - expected_changes)
        if unexpected_changes:
            raise RepairError(
                f"Repair workflow produced unexpected file changes: {', '.join(unexpected_changes)}"
            )

        if not any(path in changed_files for path in expected_changes):
            raise RepairError("Repair workflow produced no commit-worthy changes.")

        comment = build_success_comment(plan, before_metrics, after_metrics, comparison)
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "success",
                "commit_message": sanitize_commit_message(plan.get("commit_message")),
                "summary": plan.get("summary", ""),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
                "changed_files": changed_files,
            },
        )
        return 0
    except subprocess.CalledProcessError as exc:
        command = " ".join(exc.cmd) if isinstance(exc.cmd, (list, tuple)) else str(exc.cmd)
        message = f"Command failed during parser repair: `{command}` exited with status {exc.returncode}."
        comment = build_failure_comment(message, before_metrics, after_metrics, comparison)
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "failure",
                "message": message,
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
            },
        )
        print(message, file=sys.stderr)
        return 1
    except RepairError as exc:
        comment = build_failure_comment(str(exc), before_metrics, after_metrics, comparison)
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "failure",
                "message": str(exc),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
            },
        )
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        message = f"Unexpected parser repair failure: {exc}"
        comment = build_failure_comment(message, before_metrics, after_metrics, comparison)
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "failure",
                "message": message,
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
            },
        )
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
