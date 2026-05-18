#!/usr/bin/env python3
"""
Run whitelist scheduler once.

Usage:
    python scripts/run_whitelist_scheduler_once.py --daily
    python scripts/run_whitelist_scheduler_once.py --round --round-id 1
    python scripts/run_whitelist_scheduler_once.py --manual --reason "Ad-hoc check"

v6k.2: Whitelist Scheduler
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.whitelist_scheduler import WhitelistScheduler


def main():
    parser = argparse.ArgumentParser(description="Run whitelist scheduler once")
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Run daily governance",
    )
    parser.add_argument(
        "--round",
        action="store_true",
        help="Run round-based governance",
    )
    parser.add_argument(
        "--round-id",
        type=int,
        default=1,
        help="Round ID for round-based governance",
    )
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Run manual governance",
    )
    parser.add_argument(
        "--reason",
        default="Manual trigger",
        help="Reason for manual run",
    )
    parser.add_argument(
        "--storage",
        default="artifacts/eval/v6k_2",
        help="Storage path for scheduler",
    )
    parser.add_argument(
        "--registry-storage",
        default="artifacts/eval/v6h",
        help="Storage path for whitelist registry",
    )

    args = parser.parse_args()

    storage_path = Path(args.storage)
    registry_storage = Path(args.registry_storage)

    scheduler = WhitelistScheduler(storage_path=storage_path)

    print("=== Whitelist Scheduler ===")
    print(f"Storage: {storage_path}")
    print(f"Registry: {registry_storage}")
    print()

    if args.daily:
        print("Running daily governance...")
        run = scheduler.run_daily(registry_storage)

    elif args.round:
        print(f"Running round {args.round_id} governance...")
        run = scheduler.run_round(args.round_id, registry_storage)

    elif args.manual:
        print(f"Running manual governance: {args.reason}")
        run = scheduler.run_manual(args.reason, registry_storage)

    else:
        print("ERROR: Specify --daily, --round, or --manual")
        parser.print_help()
        return 1

    # Print results
    print(f"\nRun ID: {run.run_id}")
    print(f"Triggered at: {run.triggered_at}")
    print(f"Success: {run.success}")

    if run.receipt_id:
        print(f"Receipt: {run.receipt_id}")

    print(f"Alerts generated: {run.alerts_generated}")
    print(f"Governance verdict: {run.governance_verdict}")

    if run.details:
        print(f"Details: {json.dumps(run.details, indent=2)}")

    return 0 if run.success else 1


if __name__ == "__main__":
    sys.exit(main())
