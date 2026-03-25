#!/usr/bin/env python3
"""
Promote a candidate scenario to production whitelist.

Usage:
    python scripts/promote_candidate_scenario.py --scenario complex_semantic_reasoning --commit <git-commit>

v6h: Production Whitelist Promotion
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    PromotionReceipt,
)


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()[:8]
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Promote a candidate scenario to production whitelist")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario name to promote (e.g., complex_semantic_reasoning)",
    )
    parser.add_argument(
        "--commit",
        help="Git commit hash (default: current HEAD)",
    )
    parser.add_argument(
        "--observation-days",
        type=int,
        default=14,
        help="Observation window in days (default: 14)",
    )
    parser.add_argument(
        "--observation-rounds",
        type=int,
        default=10,
        help="Observation window in rounds (default: 10)",
    )
    parser.add_argument(
        "--approval-basis",
        help="Reason for promotion",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes",
    )

    args = parser.parse_args()

    # Get commit hash
    commit = args.commit or get_git_commit()

    # Check v6f pilot report exists
    pilot_report_path = Path("artifacts/eval/v6f/pilot_report.json")
    if not pilot_report_path.exists():
        print(f"ERROR: Pilot report not found at {pilot_report_path}")
        print("Run v6f evaluation first.")
        sys.exit(1)

    # Load pilot report
    pilot_report = json.loads(pilot_report_path.read_text())
    pilot_metrics = pilot_report.get("metrics", {})
    pilot_decision = pilot_report.get("decision", {})

    # Verify promotion verdict
    verdict = pilot_decision.get("verdict")
    if verdict != "promote":
        print(f"ERROR: Pilot verdict is '{verdict}', not 'promote'")
        print(f"Reason: {pilot_decision.get('rationale', 'Unknown')}")
        sys.exit(1)

    # Build approval basis
    approval_basis = args.approval_basis or (
        f"Pilot evaluation passed: {pilot_metrics.get('request_count', 0)} requests, "
        f"fallback_rate={pilot_metrics.get('fallback_rate', 0):.1%}, "
        f"p95_latency={pilot_metrics.get('p95_latency_ms', 0):.1f}ms, "
        f"wrong_user_guard={pilot_metrics.get('wrong_user_guard_trigger_count', 0)}, "
        f"provider_health={pilot_metrics.get('provider_health_rate', 0):.1%}, "
        f"quality_signal={pilot_metrics.get('avg_quality_signal', 0):.2f}"
    )

    if args.dry_run:
        print("=== DRY RUN - Promotion would proceed with: ===")
        print(f"  scenario: {args.scenario}")
        print(f"  commit: {commit}")
        print(f"  observation_days: {args.observation_days}")
        print(f"  observation_rounds: {args.observation_rounds}")
        print(f"  approval_basis: {approval_basis}")
        print()
        print("Pilot metrics:")
        for key, value in pilot_metrics.items():
            print(f"  {key}: {value}")
        return

    # Create registry and promote
    registry = ProductionWhitelistRegistry()

    receipt = registry.promote_scenario(
        scenario_name=args.scenario,
        approval_basis=approval_basis,
        promotion_commit=commit,
        observation_window_days=args.observation_days,
        observation_window_rounds=args.observation_rounds,
    )

    # Print receipt
    print("=== Promotion Receipt ===")
    print(json.dumps(receipt.to_dict(), indent=2))

    # Print updated whitelist
    print()
    print("=== Updated Production Whitelist ===")
    for scenario in registry.get_production_whitelist():
        print(f"  - {scenario}")

    # Save receipt to v6h artifacts
    artifacts_dir = Path("artifacts/eval/v6h")
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    receipt_file = artifacts_dir / "promotion_receipt.json"
    receipt_file.write_text(json.dumps(receipt.to_dict(), indent=2))
    print()
    print(f"Receipt saved to: {receipt_file}")


if __name__ == "__main__":
    main()
