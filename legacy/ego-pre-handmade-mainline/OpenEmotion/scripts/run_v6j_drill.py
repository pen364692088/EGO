#!/usr/bin/env python3
"""
Run v6j guard drill completion.

Usage:
    python scripts/run_v6j_drill.py --scenario complex_semantic_reasoning

v6j: Demotion/Rollback Guard Drill Completion
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import (
    ProductionWhitelistRegistry,
    WhitelistStatus,
)
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard
from emotiond.memory.embedding.guard_drill import (
    GuardDrillRunner,
    DrillType,
    DrillResult,
)


def run_demotion_drill(scenario_name: str, storage_path: Path) -> dict:
    """Run demotion drill specifically."""
    # Use v6h storage to inherit promotion receipt
    registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
    guard = PostPromotionGuard(registry)
    drill_runner = GuardDrillRunner(registry, guard, storage_path=storage_path)

    # Ensure scenario is promoted
    if not registry.is_in_production_whitelist(scenario_name):
        registry.promote_scenario(scenario_name, "Drill setup", "v6j-drill")

    # Reset state
    registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
    registry.scenarios[scenario_name].request_count = 0
    registry.scenarios[scenario_name].fallback_count = 0
    registry._save_state()

    # Run fallback overflow drill
    report = drill_runner.run_drill(
        DrillType.FALLBACK_RATE_OVERFLOW,
        scenario_name,
        simulate_only=False,
    )

    return {
        "drill_type": "demotion",
        "scenario_name": scenario_name,
        "trigger": "fallback_rate > 10%",
        "result": report.result.value,
        "expected_action": report.expected_action.value,
        "actual_action": report.actual_action.value,
        "expected_status": report.expected_status.value,
        "actual_status": report.actual_status.value,
        "details": report.details,
        "timestamp": datetime.now().isoformat(),
    }


def run_rollback_drill(scenario_name: str, storage_path: Path) -> dict:
    """Run rollback drill specifically."""
    # Use v6h storage to inherit promotion receipt
    registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
    guard = PostPromotionGuard(registry)
    drill_runner = GuardDrillRunner(registry, guard, storage_path=storage_path)

    # Ensure scenario is promoted
    if not registry.is_in_production_whitelist(scenario_name):
        registry.promote_scenario(scenario_name, "Drill setup", "v6j-drill")

    # Reset state
    registry.scenarios[scenario_name].status = WhitelistStatus.PROMOTED
    registry.scenarios[scenario_name].wrong_user_guard_trigger_count = 0
    registry._save_state()

    # Run wrong_user_guard drill
    report = drill_runner.run_drill(
        DrillType.WRONG_USER_GUARD_TRIGGER,
        scenario_name,
        simulate_only=False,
    )

    return {
        "drill_type": "rollback",
        "scenario_name": scenario_name,
        "trigger": "wrong_user_guard_trigger_count > 0",
        "result": report.result.value,
        "expected_action": report.expected_action.value,
        "actual_action": report.actual_action.value,
        "expected_status": report.expected_status.value,
        "actual_status": report.actual_status.value,
        "details": report.details,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Run v6j guard drill")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario to drill (e.g., complex_semantic_reasoning)",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore scenario to promoted state after drill",
    )

    args = parser.parse_args()

    storage_path = Path("artifacts/eval/v6j")
    storage_path.mkdir(parents=True, exist_ok=True)

    print(f"=== v6j Guard Drill for {args.scenario} ===\n")

    # Run demotion drill
    print("--- Demotion Drill (fallback_rate > 10%) ---")
    demotion_result = run_demotion_drill(args.scenario, storage_path)
    print(f"  Result: {demotion_result['result']}")
    print(f"  Trigger: {demotion_result['trigger']}")
    print(f"  Action: {demotion_result['actual_action']}")
    print(f"  Status: {demotion_result['actual_status']}")
    print(f"  Fallback rate: {demotion_result['details'].get('fallback_rate', 0):.1%}")
    print()

    # Save demotion report
    demotion_file = storage_path / "demotion_drill_report.json"
    demotion_file.write_text(json.dumps(demotion_result, indent=2))

    # Run rollback drill
    print("--- Rollback Drill (wrong_user_guard > 0) ---")
    rollback_result = run_rollback_drill(args.scenario, storage_path)
    print(f"  Result: {rollback_result['result']}")
    print(f"  Trigger: {rollback_result['trigger']}")
    print(f"  Action: {rollback_result['actual_action']}")
    print(f"  Status: {rollback_result['actual_status']}")
    print()

    # Save rollback report
    rollback_file = storage_path / "rollback_drill_report.json"
    rollback_file.write_text(json.dumps(rollback_result, indent=2))

    # Summary
    demotion_pass = demotion_result["result"] == "pass"
    rollback_pass = rollback_result["result"] == "pass"

    summary = {
        "scenario_name": args.scenario,
        "demotion_drill": "PASS" if demotion_pass else "FAIL",
        "rollback_drill": "PASS" if rollback_pass else "FAIL",
        "all_passed": demotion_pass and rollback_pass,
        "demotion_details": demotion_result,
        "rollback_details": rollback_result,
        "generated_at": datetime.now().isoformat(),
    }

    summary_file = storage_path / "guard_drill_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))

    print("=== Summary ===")
    print(f"  Demotion drill: {summary['demotion_drill']}")
    print(f"  Rollback drill: {summary['rollback_drill']}")
    print(f"  All passed: {summary['all_passed']}")
    print()
    print(f"Reports saved to: {storage_path}")

    # Restore if requested
    if args.restore:
        registry = ProductionWhitelistRegistry(storage_path=Path("artifacts/eval/v6h"))
        registry.scenarios[args.scenario].status = WhitelistStatus.PROMOTED
        registry.scenarios[args.scenario].wrong_user_guard_trigger_count = 0
        registry.scenarios[args.scenario].fallback_count = 0
        registry.scenarios[args.scenario].request_count = 0
        registry._save_state()
        print(f"\nRestored {args.scenario} to promoted state")

    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
