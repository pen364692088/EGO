#!/usr/bin/env python3
"""Check for P0 failures and write to GITHUB_OUTPUT."""
import json
import os
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: check_failures.py <report.json>", file=sys.stderr)
        sys.exit(1)

    report_path = sys.argv[1]

    try:
        with open(report_path) as f:
            d = json.load(f)
    except FileNotFoundError:
        print(f"Report not found: {report_path}", file=sys.stderr)
        sys.exit(0)

    failed = d.get("failed", 0)
    errors = d.get("errors", 0)
    results = d.get("results", [])

    # Find P0 failures
    p0_failures = []
    for r in results:
        if r.get("status") != "pass" or r.get("p0_risk", False):
            name = r.get("name", "unknown")
            # Check if it's a P0 scenario
            if (
                "governor" in name.lower()
                or "replay" in name.lower()
                or "nondeterminism" in name.lower()
                or r.get("p0_risk", False)
            ):
                p0_failures.append(name)

    # Write to temp file for step summary
    with open("/tmp/nightly_status.txt", "w") as f:
        f.write(f"FAILED={failed}\n")
        f.write(f"ERRORS={errors}\n")
        f.write(f"P0_COUNT={len(p0_failures)}\n")
        f.write(f"P0_SCENARIOS={','.join(p0_failures)}\n")

    # Write to GITHUB_OUTPUT
    output_file = os.environ.get("GITHUB_OUTPUT", "/dev/null")
    with open(output_file, "a") as f:
        f.write(f"failed={failed}\n")
        f.write(f"errors={errors}\n")
        f.write(f"p0_count={len(p0_failures)}\n")

    print(f"Failed: {failed}, Errors: {errors}, P0: {len(p0_failures)}")

if __name__ == "__main__":
    main()
