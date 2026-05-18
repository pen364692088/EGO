#!/usr/bin/env python3
"""
Run guard drills to test demotion/rollback mechanisms.

Usage:
    python scripts/run_guard_drill.py --scenario complex_semantic_reasoning

v6i: Post-Promotion Guard Drill
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard
from emotiond.memory.embedding.guard_drill import (
    GuardDrillRunner,
    DrillType,
    DrillResult,
)


def main():
    parser = argparse.ArgumentParser(description="Run guard drills")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario to drill (e.g., complex_semantic_reasoning)",
    )
    parser.add_argument(
        "--drill-type",
        choices=["all", "fallback", "wrong_user", "provider", "latency", "quality"],
        default="all",
        help="Specific drill to run (default: all)",
    )
    parser.add_argument(
        "--no-simulate",
        action="store_true",
        help="Actually change state (default: simulate only)",
    )

    args = parser.parse_args()

    # Create registry and drill runner
    registry = ProductionWhitelistRegistry()
    guard = PostPromotionGuard(registry)
    drill_runner = GuardDrillRunner(registry, guard)

    print(f"=== Guard Drill for {args.scenario} ===")
    print(f"Mode: {'LIVE' if not args.no_simulate else 'SIMULATE'}")
    print()

    simulate_only = not args.no_simulate

    if args.drill_type == "all":
        # Run all drills
        summary = drill_runner.run_all_drills(args.scenario, simulate_only)

        print("=== Drill Summary ===")
        print(f"Total: {summary['summary']['total']}")
        print(f"Passed: {summary['summary']['passed']}")
        print(f"Failed: {summary['summary']['failed']}")
        print(f"Skipped: {summary['summary']['skipped']}")
        print()
        print(f"Demotion Drill: {summary['demotion_drill']}")
        print(f"Rollback Drill: {summary['rollback_drill']}")
        print()

        # Detailed results
        for drill_name, result in summary["drills"].items():
            status = "✓" if result["result"] == "pass" else "✗"
            print(f"  {status} {drill_name}: {result['result']}")

    else:
        # Run specific drill
        drill_map = {
            "fallback": DrillType.FALLBACK_RATE_OVERFLOW,
            "wrong_user": DrillType.WRONG_USER_GUARD_TRIGGER,
            "provider": DrillType.PROVIDER_HEALTH_DEGRADATION,
            "latency": DrillType.LATENCY_SPIKE,
            "quality": DrillType.QUALITY_SIGNAL_NEGATIVE,
        }

        drill_type = drill_map[args.drill_type]
        report = drill_runner.run_drill(drill_type, args.scenario, simulate_only)

        print(f"=== {drill_type.value} Drill ===")
        print(f"Result: {report.result.value}")
        print(f"Expected action: {report.expected_action.value}")
        print(f"Actual action: {report.actual_action.value}")
        print(f"Expected status: {report.expected_status.value}")
        print(f"Actual status: {report.actual_status.value}")
        print()

        if report.details:
            print("Details:")
            for key, value in report.details.items():
                print(f"  {key}: {value}")

    # Save report
    report_file = drill_runner.storage_path / "guard_drill_report.json"
    print()
    print(f"Report saved to: {report_file}")

    # Return code based on results
    if args.drill_type == "all":
        passed = summary["summary"]["passed"]
        total = summary["summary"]["total"]
        return 0 if passed == total else 1
    else:
        return 0 if report.result == DrillResult.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
