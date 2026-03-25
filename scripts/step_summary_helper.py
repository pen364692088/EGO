#!/usr/bin/env python3
"""Helper for GitHub Actions step summary."""
import json
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: step_summary_helper.py <report.json>", file=sys.stderr)
        sys.exit(1)

    report_path = sys.argv[1]

    try:
        with open(report_path) as f:
            d = json.load(f)
    except FileNotFoundError:
        print(f"Report not found: {report_path}", file=sys.stderr)
        sys.exit(0)

    passed = d.get("passed", 0)
    total = d.get("total_scenarios", 0)
    failed = d.get("failed", 0)
    errors = d.get("errors", 0)

    print(f"- Passed: {passed}/{total}")
    print(f"- Failed: {failed}")
    print(f"- Errors: {errors}")

    # For nightly report, also print time
    if "total_elapsed_seconds" in d:
        print(f"- Time: {d['total_elapsed_seconds']:.2f}s")

if __name__ == "__main__":
    main()
