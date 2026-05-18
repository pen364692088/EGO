#!/usr/bin/env python3
"""
CLI wrapper for self_report_consistency_checker.

Usage:
    python3 emotiond/self_report_check.py "LLM response text"
    python3 emotiond/self_report_check.py "LLM response text" path/to/contract.json

Returns JSON to stdout with check result.
"""

import sys
import json
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from emotiond.self_report_consistency_checker import (
    SelfReportConsistencyChecker,
    check_consistency,
)


def generate_sample_contract():
    """Generate a sample contract for testing."""
    from emotiond.self_report_interpreter import interpret_to_contract
    
    # Sample raw state
    raw_state = {
        "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.05},
        "mood": {"joy": 0.0, "loneliness": 0.15},
        "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
    }
    
    return interpret_to_contract(raw_state, mode="interpreted")


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "status": "error",
            "error": "no_llm_response",
            "message": "Usage: self_report_check.py <llm_response> [contract_path]"
        }))
        sys.exit(1)
    
    llm_response = sys.argv[1]
    contract_path = sys.argv[2] if len(sys.argv) > 2 else None
    session_id = sys.argv[3] if len(sys.argv) > 3 else ""
    
    # Load or generate contract
    contract = None
    if contract_path and os.path.exists(contract_path):
        try:
            with open(contract_path, 'r', encoding='utf-8') as f:
                contract = json.load(f)
        except Exception as e:
            print(json.dumps({
                "status": "error",
                "error": "contract_load_error",
                "message": str(e)
            }))
            sys.exit(1)
    
    if contract is None:
        # Generate sample contract for testing
        contract = generate_sample_contract()
    
    # Run check
    try:
        result = check_consistency(llm_response, contract, session_id)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": "check_error",
            "message": str(e)
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
