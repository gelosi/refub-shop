import argparse
import json
from pathlib import Path


def load_metrics(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_metrics(before, after):
    reasons = []

    total_products_ok = after["total_products"] >= before["total_products"]
    missing_ram_ok = after["missing_ram"] <= before["missing_ram"]
    missing_ssd_ok = after["missing_ssd"] <= before["missing_ssd"]
    implausible_ram_ok = after["implausible_ram"] <= before["implausible_ram"]

    if not total_products_ok:
        reasons.append(
            "Total products dropped "
            f"({before['total_products']} -> {after['total_products']})."
        )
    if not missing_ram_ok:
        reasons.append(
            "Missing RAM increased "
            f"({before['missing_ram']} -> {after['missing_ram']})."
        )
    if not missing_ssd_ok:
        reasons.append(
            "Missing SSD increased "
            f"({before['missing_ssd']} -> {after['missing_ssd']})."
        )
    if not implausible_ram_ok:
        reasons.append(
            "Implausible RAM entries increased "
            f"({before['implausible_ram']} -> {after['implausible_ram']})."
        )

    improved = (
        after["total_products"] > before["total_products"]
        or after["missing_ram"] < before["missing_ram"]
        or after["missing_ssd"] < before["missing_ssd"]
        or after["implausible_ram"] < before["implausible_ram"]
    )

    should_commit = (
        total_products_ok
        and missing_ram_ok
        and missing_ssd_ok
        and implausible_ram_ok
    )
    decision = "pass" if should_commit else "regression"

    return {
        "before": before,
        "after": after,
        "decision": decision,
        "should_commit": should_commit,
        "improved": improved,
        "total_products_ok": total_products_ok,
        "missing_ram_ok": missing_ram_ok,
        "missing_ssd_ok": missing_ssd_ok,
        "implausible_ram_ok": implausible_ram_ok,
        "reasons": reasons,
    }


def format_markdown(comparison):
    before = comparison["before"]
    after = comparison["after"]
    lines = [
        "# Scrape Metrics",
        "",
        "| Metric | Last committed | Latest scrape |",
        "| --- | ---: | ---: |",
        f"| Total products | {before['total_products']} | {after['total_products']} |",
        f"| Missing RAM (mac only) | {before['missing_ram']} | {after['missing_ram']} |",
        f"| Missing SSD (mac/ipad/iphone/appletv) | {before['missing_ssd']} | {after['missing_ssd']} |",
        f"| Implausible RAM (>512 GB) | {before['implausible_ram']} | {after['implausible_ram']} |",
        "",
        f"Decision: **{comparison['decision'].upper()}**",
    ]

    if comparison["reasons"]:
        lines.extend(["", "Reasons:"])
        lines.extend(f"- {reason}" for reason in comparison["reasons"])
    else:
        lines.extend(["", "- Latest scrape passed the non-regression gate."])

    return "\n".join(lines) + "\n"


def write_github_outputs(path, comparison):
    output_path = Path(path)
    reasons = comparison["reasons"]
    summary = "; ".join(reasons) if reasons else "Latest scrape passed the non-regression gate."

    with output_path.open("a", encoding="utf-8") as handle:
        scalar_outputs = {
            "decision": comparison["decision"],
            "should_commit": str(comparison["should_commit"]).lower(),
            "improved": str(comparison["improved"]).lower(),
            "total_products_ok": str(comparison["total_products_ok"]).lower(),
            "missing_ram_ok": str(comparison["missing_ram_ok"]).lower(),
            "missing_ssd_ok": str(comparison["missing_ssd_ok"]).lower(),
            "implausible_ram_ok": str(comparison["implausible_ram_ok"]).lower(),
        }
        for key, value in scalar_outputs.items():
            handle.write(f"{key}={value}\n")

        handle.write("summary<<EOF\n")
        handle.write(summary + "\n")
        handle.write("EOF\n")


def main():
    parser = argparse.ArgumentParser(description="Compare two scrape metric snapshots.")
    parser.add_argument("before", help="Path to the baseline metrics JSON file.")
    parser.add_argument("after", help="Path to the candidate metrics JSON file.")
    parser.add_argument(
        "--github-output",
        help="Optional path to $GITHUB_OUTPUT for exporting gate results.",
    )
    parser.add_argument(
        "--markdown-out",
        help="Optional path to write a markdown summary of the comparison.",
    )
    args = parser.parse_args()

    comparison = compare_metrics(load_metrics(args.before), load_metrics(args.after))

    if args.github_output:
        write_github_outputs(args.github_output, comparison)

    summary_markdown = format_markdown(comparison)
    if args.markdown_out:
        Path(args.markdown_out).write_text(summary_markdown, encoding="utf-8")

    print(summary_markdown, end="")


if __name__ == "__main__":
    main()
