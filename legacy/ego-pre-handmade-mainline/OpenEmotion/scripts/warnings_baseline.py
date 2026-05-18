#!/usr/bin/env python3
"""Warnings baseline collector for CI gate."""
import subprocess
import json
import re
from pathlib import Path
from datetime import datetime

def collect_warnings(test_paths: list[str] = None) -> dict:
    """Run pytest and collect warnings count and details."""
    if test_paths is None:
        test_paths = ["tests/"]
    
    cmd = ["uv", "run", "pytest", *test_paths, "-q", "--tb=no", "-W", "default"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    output = result.stdout + result.stderr
    
    # Parse warnings count
    match = re.search(r"(\d+) warnings?", output)
    warnings_count = int(match.group(1)) if match else 0
    
    # Parse passed/failed/skipped
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    skipped_match = re.search(r"(\d+) skipped", output)
    
    # Extract warning categories
    warning_types = {}
    for line in output.split('\n'):
        if 'Warning' in line or 'warning' in line.lower():
            for wtype in ['DeprecationWarning', 'UserWarning', 'FutureWarning', 'RuntimeWarning']:
                if wtype in line:
                    warning_types[wtype] = warning_types.get(wtype, 0) + 1
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_warnings": warnings_count,
        "passed": int(passed_match.group(1)) if passed_match else 0,
        "failed": int(failed_match.group(1)) if failed_match else 0,
        "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        "warning_types": warning_types,
        "test_paths": test_paths,
        "exit_code": result.returncode
    }

def main():
    import sys
    test_paths = sys.argv[1:] if len(sys.argv) > 1 else ["tests/"]
    
    print(f"Collecting warnings baseline for: {test_paths}")
    baseline = collect_warnings(test_paths)
    
    baseline_path = Path(__file__).parent.parent / "reports" / "warnings_baseline.json"
    baseline_path.parent.mkdir(exist_ok=True)
    
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)
    
    print(f"Baseline: {baseline['total_warnings']} warnings")
    print(f"Passed: {baseline['passed']}, Failed: {baseline['failed']}, Skipped: {baseline['skipped']}")
    print(f"Saved to: {baseline_path}")

if __name__ == "__main__":
    main()
