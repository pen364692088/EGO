#!/usr/bin/env python3
"""
Generate whitelist governance receipt.

Usage:
    python scripts/generate_whitelist_receipt.py --mode daily
    python scripts/generate_whitelist_receipt.py --mode round --round-id 1
    python scripts/generate_whitelist_receipt.py --mode manual --reason "Ad-hoc check"

v6k: Whitelist Governance Receipts
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.whitelist_governance import WhitelistGovernanceEvaluator
from emotiond.memory.embedding.periodic_receipts import (
    PeriodicReceiptGenerator,
    ReceiptMode,
)


def main():
    parser = argparse.ArgumentParser(description="Generate whitelist receipt")
    parser.add_argument(
        "--mode",
        choices=["daily", "round", "manual"],
        required=True,
        help="Receipt generation mode",
    )
    parser.add_argument(
        "--round-id",
        type=int,
        help="Round ID for round-based receipt",
    )
    parser.add_argument(
        "--reason",
        default="",
        help="Reason for manual receipt",
    )
    parser.add_argument(
        "--storage",
        default="artifacts/eval/v6k",
        help="Storage path for receipts",
    )

    args = parser.parse_args()

    storage_path = Path(args.storage)
    storage_path.mkdir(parents=True, exist_ok=True)

    # Use v6h storage to inherit whitelist state
    registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
    governance = WhitelistGovernanceEvaluator(registry, storage_path=storage_path)
    generator = PeriodicReceiptGenerator(registry, governance, storage_path=storage_path)

    print(f"=== Whitelist Receipt ({args.mode}) ===\n")

    # Generate receipt based on mode
    if args.mode == "daily":
        receipt = generator.generate_daily_receipt()
    elif args.mode == "round":
        if args.round_id is None:
            print("ERROR: --round-id required for round mode")
            sys.exit(1)
        receipt = generator.generate_round_receipt(args.round_id)
    else:  # manual
        receipt = generator.generate_manual_receipt(args.reason)

    # Print receipt
    print(f"Receipt ID: {receipt.receipt_id}")
    print(f"Generated: {receipt.generated_at}")
    print(f"Mode: {receipt.mode.value}")
    print()

    print(f"Active scenarios: {receipt.active_scenario_count}")
    print(f"  Healthy: {receipt.healthy_scenario_count}")
    print(f"  Observe: {receipt.observe_scenario_count}")
    print(f"  Demote candidate: {receipt.demote_candidate_count}")
    print(f"  Rollback candidate: {receipt.rollback_candidate_count}")
    print()

    print(f"Whitelist verdict: {receipt.whitelist_verdict}")
    print(f"Expansion readiness: {receipt.expansion_readiness}")

    if receipt.blockers:
        print(f"Blockers: {receipt.blockers}")

    print()
    print("=== Scenario Metrics ===")
    for metric in receipt.scenario_metrics:
        print(f"\n  {metric['scenario_name']}:")
        print(f"    Request count: {metric['request_count']}")
        print(f"    Fallback rate: {metric['fallback_rate']:.1%}")
        print(f"    P95 latency: {metric['p95_latency_ms']:.0f}ms")
        print(f"    Provider health: {metric['provider_health_rate']:.1%}")
        print(f"    Verdict: {metric['scenario_verdict']}")

    print()
    print(f"Artifact: {receipt.artifact_refs.get(f'{args.mode}_receipt', 'N/A')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
