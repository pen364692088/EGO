#!/usr/bin/env python3
"""
Collect and analyze pytest warnings for baseline tracking
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

def run_pytest_collect_warnings():
    """Run pytest and capture warnings output"""
    try:
        # Run pytest with warnings captured
        result = subprocess.run(
            ["uv", "run", "pytest", "--tb=no", "-q", "-W", "error::DeprecationWarning", "--disable-warnings"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        # Run with warnings to stderr
        result_warn = subprocess.run(
            ["uv", "run", "pytest", "--tb=no", "-q"],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
        )
        
        return result_warn.stderr
        
    except Exception as e:
        print(f"Error running pytest: {e}")
        return ""

def parse_warnings(warnings_output):
    """Parse warnings output into structured data"""
    warnings_list = []
    current_warning = {}
    
    for line in warnings_output.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('/home/moonlight') or line.startswith('.'):
            # File path line
            if current_warning:
                warnings_list.append(current_warning)
            current_warning = {'file': line, 'message': '', 'category': ''}
        elif ':' in line and current_warning:
            # Line number and message
            parts = line.split(':', 2)
            if len(parts) >= 2:
                current_warning['line'] = parts[1]
                if len(parts) > 2:
                    current_warning['message'] = parts[2].strip()
        elif 'Warning:' in line and current_warning:
            # Warning category
            current_warning['category'] = line
        elif current_warning and line:
            # Additional message content
            current_warning['message'] += ' ' + line
    
    if current_warning:
        warnings_list.append(current_warning)
    
    return warnings_list

def generate_baseline(warnings_list):
    """Generate baseline report"""
    baseline = {
        "timestamp": datetime.now().isoformat(),
        "total_warnings": len(warnings_list),
        "by_file": defaultdict(int),
        "by_category": Counter(),
        "details": warnings_list
    }
    
    for warning in warnings_list:
        file_path = warning.get('file', 'unknown')
        # Group by base filename for readability
        file_name = Path(file_path).name if file_path != 'unknown' else 'unknown'
        baseline["by_file"][file_name] += 1
        
        category = warning.get('category', 'unknown')
        baseline["by_category"][category] += 1
    
    # Convert defaultdict to regular dict for JSON serialization
    baseline["by_file"] = dict(baseline["by_file"])
    
    return baseline

def main():
    """Main collection script"""
    print("Collecting pytest warnings for baseline...")
    
    # Capture warnings
    warnings_output = run_pytest_collect_warnings()
    
    if not warnings_output:
        print("No warnings captured or pytest failed")
        return 1
    
    # Parse warnings
    warnings_list = parse_warnings(warnings_output)
    
    if not warnings_list:
        print("No warnings found in output")
        return 0
    
    # Generate baseline
    baseline = generate_baseline(warnings_list)
    
    # Save baseline
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    
    baseline_file = reports_dir / "warnings_baseline.json"
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)
    
    # Print summary
    print(f"\nWarnings Baseline Generated:")
    print(f"  Total warnings: {baseline['total_warnings']}")
    print(f"  Files affected: {len(baseline['by_file'])}")
    print(f"  Categories: {len(baseline['by_category'])}")
    print(f"  Baseline saved to: {baseline_file}")
    
    # Show top files
    print(f"\nTop 5 files with warnings:")
    for file_name, count in sorted(baseline['by_file'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {file_name}: {count}")
    
    # Show top categories
    print(f"\nWarning categories:")
    for category, count in baseline['by_category'].most_common():
        print(f"  {category}: {count}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
