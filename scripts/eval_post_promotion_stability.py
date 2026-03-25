#!/usr/bin/env python3
"""
Evaluate post-promotion stability for promoted scenarios.

Usage:
    python scripts/eval_post_promotion_stability.py --scenario complex_semantic_reasoning

v6h: Post-Promotion Observation
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.production_whitelist import ProductionWhitelistRegistry
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard, GuardAction


def generate_sample_observations(count: int = 20, inject_issues: bool = False) -> list:
    """Generate sample observations for testing."""
    observations = []

    for i in range(count):
        obs = {
            "success": True,
            "latency_ms": random.uniform(50, 100),
            "fallback": False,
            "wrong_user_guard": False,
            "provider_health": True,
            "quality_signal": random.uniform(0.2, 0.6),
        }

        # Inject some issues if requested
        if inject_issues and i > count * 0.8:
            obs["fallback"] = random.random() > 0.7
            obs["latency_ms"] = random.uniform(100, 200)

        observations.append(obs)

    return observations


def main():
    parser = argparse.ArgumentParser(description="Evaluate post-promotion stability")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario to evaluate",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=5,
        help="Number of observation rounds (default: 5)",
    )
    parser.add_argument(
        "--samples-per-round",
        type=int,
        default=20,
        help="Samples per round (default: 20)",
    )
    parser.add_argument(
        "--inject-issues",
        action="store_true",
        help="Inject simulated issues for testing",
    )

    args = parser.parse_args()

    # Create registry and guard
    registry = ProductionWhitelistRegistry()
    guard = PostPromotionGuard(registry)

    # Check if scenario is promoted
    if not registry.is_in_production_whitelist(args.scenario):
        print(f"ERROR: {args.scenario} is not in production whitelist")
        print(f"Promoted scenarios: {registry.get_production_whitelist()}")
        sys.exit(1)

    print(f"=== Post-Promotion Observation for {args.scenario} ===")
    print(f"Rounds: {args.rounds}")
    print(f"Samples per round: {args.samples_per_round}")
    print()

    all_decisions = []

    for round_num in range(1, args.rounds + 1):
        print(f"--- Round {round_num}/{args.rounds} ---")

        # Generate observations
        observations = generate_sample_observations(
            count=args.samples_per_round,
            inject_issues=args.inject_issues,
        )

        # Run observation round
        decision = guard.run_observation_round(args.scenario, observations)
        all_decisions.append(decision)

        # Get current report
        report = registry.get_observation_report(args.scenario)

        print(f"  request_count: {report.get('request_count', 0)}")
        print(f"  fallback_rate: {report.get('fallback_rate', 0):.1%}")
        print(f"  p95_latency_ms: {report.get('p95_latency_ms', 0):.1f}")
        print(f"  wrong_user_guard: {report.get('wrong_user_guard_trigger_count', 0)}")
        print(f"  provider_health_rate: {report.get('provider_health_rate', 0):.1%}")
        print(f"  avg_quality_signal: {report.get('avg_quality_signal', 0):.2f}")
        print(f"  guard_action: {decision.action.value}")

        if decision.reason:
            print(f"  GUARD REASON: {decision.reason}")

        if decision.action in (GuardAction.DEMOTE, GuardAction.ROLLBACK):
            print()
            print(f"!!! SCENARIO {decision.action.value.upper()}D !!!")
            break

        print()

    # Generate final report
    final_report = guard.get_guard_report()

    report_path = Path("artifacts/eval/v6h/post_promotion_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(final_report, indent=2))

    print(f"=== Final Report ===")
    print(f"Total requests: {final_report['scenario_reports'].get(args.scenario, {}).get('request_count', 0)}")
    print(f"Observation rounds: {final_report['scenario_reports'].get(args.scenario, {}).get('observation_rounds', 0)}")
    print(f"Report saved to: {report_path}")

    # Check final status
    scenario_report = final_report['scenario_reports'].get(args.scenario, {})
    rollback_needed = scenario_report.get('rollback_needed')

    if rollback_needed:
        print()
        print(f"WARNING: Rollback needed: {rollback_needed}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
