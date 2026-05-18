#!/usr/bin/env python3
"""
Run whitelist governance automation.

Usage:
    python scripts/run_whitelist_governance_auto.py --run-all

v6k.1: Periodic Receipts Automation
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.whitelist_governance import WhitelistGovernanceEvaluator
from emotiond.memory.embedding.periodic_receipts import (
    PeriodicReceiptGenerator,
    ReceiptMode,
)


def run_daily_receipt(storage_path: Path) -> dict:
    """Generate daily receipt."""
    registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
    governance = WhitelistGovernanceEvaluator(registry, storage_path=storage_path)
    generator = PeriodicReceiptGenerator(registry, governance, storage_path=storage_path)

    receipt = generator.generate_daily_receipt()

    return {
        "receipt_id": receipt.receipt_id,
        "mode": receipt.mode.value,
        "generated_at": receipt.generated_at,
        "artifact_path": receipt.artifact_refs.get("daily_receipt", ""),
        "status": "generated",
    }


def run_round_receipt(round_id: int, storage_path: Path) -> dict:
    """Generate round-based receipt."""
    registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
    governance = WhitelistGovernanceEvaluator(registry, storage_path=storage_path)
    generator = PeriodicReceiptGenerator(registry, governance, storage_path=storage_path)

    receipt = generator.generate_round_receipt(round_id)

    return {
        "receipt_id": receipt.receipt_id,
        "mode": receipt.mode.value,
        "generated_at": receipt.generated_at,
        "round_id": round_id,
        "artifact_path": receipt.artifact_refs.get("round_receipt", ""),
        "status": "generated",
    }


def run_all_automations(storage_path: Path) -> dict:
    """Run all automated receipt generation."""
    results = {
        "generated_at": datetime.now().isoformat(),
        "storage_path": str(storage_path),
        "daily_receipt": None,
        "round_receipt": None,
    }

    # Daily receipt
    try:
        results["daily_receipt"] = run_daily_receipt(storage_path)
    except Exception as e:
        results["daily_receipt"] = {"status": "failed", "error": str(e)}

    # Round receipt (round 1)
    try:
        results["round_receipt"] = run_round_receipt(1, storage_path)
    except Exception as e:
        results["round_receipt"] = {"status": "failed", "error": str(e)}

    # Summary
    results["summary"] = {
        "daily_receipt_generated": results["daily_receipt"].get("status") == "generated",
        "round_receipt_generated": results["round_receipt"].get("status") == "generated",
        "all_passed": (
            results["daily_receipt"].get("status") == "generated" and
            results["round_receipt"].get("status") == "generated"
        ),
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Run whitelist governance automation")
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Run all automated receipt generation",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Generate daily receipt only",
    )
    parser.add_argument(
        "--round",
        type=int,
        help="Generate round receipt with specified round ID",
    )
    parser.add_argument(
        "--storage",
        default="artifacts/eval/v6k_1",
        help="Storage path for receipts",
    )

    args = parser.parse_args()

    storage_path = Path(args.storage)
    storage_path.mkdir(parents=True, exist_ok=True)

    print(f"=== Whitelist Governance Automation ===")
    print(f"Storage: {storage_path}")
    print()

    if args.run_all:
        results = run_all_automations(storage_path)

        print(f"Daily receipt: {results['daily_receipt'].get('status', 'N/A')}")
        if results['daily_receipt'].get('artifact_path'):
            print(f"  Path: {results['daily_receipt']['artifact_path']}")

        print(f"Round receipt: {results['round_receipt'].get('status', 'N/A')}")
        if results['round_receipt'].get('artifact_path'):
            print(f"  Path: {results['round_receipt']['artifact_path']}")

        print()
        print(f"All passed: {results['summary']['all_passed']}")

        # Save automation log
        log_file = storage_path / "automation_log.json"
        log_file.write_text(json.dumps(results, indent=2))
        print(f"Automation log: {log_file}")

        return 0 if results["summary"]["all_passed"] else 1

    elif args.daily:
        result = run_daily_receipt(storage_path)
        print(f"Daily receipt: {result['status']}")
        print(f"  ID: {result['receipt_id']}")
        print(f"  Path: {result['artifact_path']}")
        return 0 if result["status"] == "generated" else 1

    elif args.round:
        result = run_round_receipt(args.round, storage_path)
        print(f"Round receipt: {result['status']}")
        print(f"  ID: {result['receipt_id']}")
        print(f"  Path: {result['artifact_path']}")
        return 0 if result["status"] == "generated" else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
