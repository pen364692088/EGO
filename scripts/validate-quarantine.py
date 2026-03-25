#!/usr/bin/env python3
"""
Validate quarantine.yml according to governance policies.
"""

import yaml
import sys
from pathlib import Path

def validate_quarantine():
    """Validate quarantine.yml against governance policies."""
    quarantine_file = Path("tests/quarantine.yml")
    
    if not quarantine_file.exists():
        print("ERROR: quarantine.yml not found")
        return False
    
    with open(quarantine_file) as f:
        data = yaml.safe_load(f)
    
    # Check required metadata
    required_metadata = ["total_skipped", "policy", "approval_required_for_new"]
    for field in required_metadata:
        if field not in data.get("metadata", {}):
            print(f"ERROR: Missing required metadata field: {field}")
            return False
    
    # Check policy enforcement
    if data["metadata"]["policy"] != "quarantine count can only decrease":
        print("ERROR: Policy string mismatch")
        return False
    
    # Check test entries have required fields
    required_fields = ["test_id", "reason", "owner", "target_unblock_version", "category"]
    for test in data.get("skipped_tests", []):
        for field in required_fields:
            if field not in test:
                print(f"ERROR: Test {test.get('test_id', 'unknown')} missing field: {field}")
                return False
    
    # Verify count matches actual entries
    actual_count = len(data.get("skipped_tests", []))
    declared_count = data["metadata"]["total_skipped"]
    if actual_count != declared_count:
        print(f"ERROR: Declared count ({declared_count}) != actual count ({actual_count})")
        return False
    
    # Check CI gate
    ci_gate = data.get("ci_gate", {})
    if ci_gate.get("max_allowed") != declared_count:
        print("ERROR: CI gate max_allowed != total_skipped")
        return False
    
    print(f"✅ Quarantine validation passed: {actual_count} tests")
    return True

if __name__ == "__main__":
    success = validate_quarantine()
    sys.exit(0 if success else 1)
