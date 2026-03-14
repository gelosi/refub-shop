import argparse
import json
import subprocess
import sys
from pathlib import Path

from metrics_gate import compare_metrics


ALLOWED_TRACKED_CHANGES = {"scraper/scraper.py", "index.html"}
IGNORED_STATUS_PATHS = {
    "current-metrics.json",
    "current-report.txt",
    "repaired-metrics.json",
    "parser-repair-comment.md",
    "parser-repair-result.json",
    "parser-repair-pr-body.md",
}
IGNORED_STATUS_PREFIXES = (".gemini/", "gha-creds-")


class RepairError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_text(path, content):
    Path(path).write_text(content.rstrip() + "\n", encoding="utf-8")


def write_result(path, payload):
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def format_metrics(metrics):
    return (
        f"Total products: {metrics['total_products']}\n"
        f"Missing RAM (mac only): {metrics['missing_ram']} ({metrics['missing_ram_pct']}%)\n"
        f"Missing SSD (mac/ipad/iphone/appletv): {metrics['missing_ssd']} ({metrics['missing_ssd_pct']}%)\n"
        f"Implausible RAM (>512 GB): {metrics['implausible_ram']}"
    )


def normalize_summary(value):
    return " ".join((value or "").split()).strip()


def sanitize_commit_message(summary):
    normalized = normalize_summary(summary)
    if not normalized:
        return "Parser repair: improve spec extraction"

    normalized = normalized.removeprefix("Summary:").strip()
    prefix = "Parser repair: "
    if normalized.lower().startswith(prefix.lower()):
        text = normalized
    else:
        text = prefix + normalized
    return text[:72]


def should_ignore_status_path(path):
    if path in IGNORED_STATUS_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in IGNORED_STATUS_PREFIXES)


def parse_status_path(raw_path):
    if " -> " in raw_path:
        return raw_path.split(" -> ", 1)[1]
    return raw_path


def collect_git_status():
    result = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        check=True,
        text=True,
        capture_output=True,
    )
    tracked = set()
    untracked = set()

    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2]
        path = parse_status_path(line[3:])
        if should_ignore_status_path(path):
            continue
        if status == "??":
            untracked.add(path)
        else:
            tracked.add(path)

    return tracked, untracked


def build_success_comment(summary, before_metrics, after_metrics, comparison, changed_files):
    normalized = normalize_summary(summary) or "Gemini CLI produced a repair candidate."
    reasons = comparison["reasons"] or ["Latest run passed the non-regression gate."]
    reasons_block = "\n".join(f"- {reason}" for reason in reasons)
    changed_block = "\n".join(f"- {path}" for path in changed_files)

    return (
        "## Repair Result\n"
        f"- Gemini CLI summary: {normalized}\n"
        "- Decision: helpful parser repair generated and validated locally.\n\n"
        "## Before\n"
        f"{format_metrics(before_metrics)}\n\n"
        "## After\n"
        f"{format_metrics(after_metrics)}\n\n"
        "## Changed Files\n"
        f"{changed_block}\n\n"
        "## Validation\n"
        f"{reasons_block}\n"
    )


def build_failure_comment(message, summary="", before_metrics=None, after_metrics=None, comparison=None):
    sections = ["## Repair Failure", f"- {message}"]

    normalized = normalize_summary(summary)
    if normalized:
        sections.extend(["", "## Gemini CLI Summary", f"- {normalized}"])
    if before_metrics:
        sections.extend(["", "## Baseline", format_metrics(before_metrics)])
    if after_metrics:
        sections.extend(["", "## Candidate Result", format_metrics(after_metrics)])
    if comparison and comparison.get("reasons"):
        sections.extend(["", "## Why It Was Rejected"])
        sections.extend(f"- {reason}" for reason in comparison["reasons"])

    return "\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description="Validate a Gemini CLI parser repair candidate.")
    parser.add_argument("--before-json", required=True)
    parser.add_argument("--after-json", required=True)
    parser.add_argument("--summary-file", default="")
    parser.add_argument("--comment-out", default="parser-repair-comment.md")
    parser.add_argument("--result-json-out", default="parser-repair-result.json")
    args = parser.parse_args()

    before_metrics = None
    after_metrics = None
    comparison = None
    summary = ""

    try:
        before_metrics = load_json(args.before_json)
        after_metrics = load_json(args.after_json)
        if args.summary_file:
            summary = Path(args.summary_file).read_text(encoding="utf-8").strip()

        comparison = compare_metrics(before_metrics, after_metrics)
        tracked_changes, untracked_changes = collect_git_status()

        if untracked_changes:
            raise RepairError(
                "Gemini CLI repair left unexpected untracked files: "
                + ", ".join(sorted(untracked_changes))
            )

        unexpected_tracked = sorted(tracked_changes - ALLOWED_TRACKED_CHANGES)
        if unexpected_tracked:
            raise RepairError(
                "Gemini CLI repair changed unexpected tracked files: "
                + ", ".join(unexpected_tracked)
            )

        missing_required = sorted(ALLOWED_TRACKED_CHANGES - tracked_changes)
        if missing_required:
            raise RepairError(
                "Gemini CLI repair did not produce the expected tracked changes: "
                + ", ".join(missing_required)
            )

        if not comparison["should_commit"]:
            raise RepairError("Candidate repair regressed the generated data.")
        if not comparison["improved"]:
            raise RepairError("Candidate repair was not helpful; no tracked metric improved.")

        changed_files = sorted(tracked_changes)
        comment = build_success_comment(summary, before_metrics, after_metrics, comparison, changed_files)
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "success",
                "summary": normalize_summary(summary),
                "commit_message": sanitize_commit_message(summary),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
                "changed_files": changed_files,
            },
        )
        return 0
    except RepairError as exc:
        comment = build_failure_comment(
            message=str(exc),
            summary=summary,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            comparison=comparison,
        )
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "failure",
                "message": str(exc),
                "summary": normalize_summary(summary),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
            },
        )
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        message = f"Unexpected parser repair validation failure: {exc}"
        comment = build_failure_comment(
            message=message,
            summary=summary,
            before_metrics=before_metrics,
            after_metrics=after_metrics,
            comparison=comparison,
        )
        write_text(args.comment_out, comment)
        write_result(
            args.result_json_out,
            {
                "status": "failure",
                "message": message,
                "summary": normalize_summary(summary),
                "before_metrics": before_metrics,
                "after_metrics": after_metrics,
                "comparison": comparison,
            },
        )
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
