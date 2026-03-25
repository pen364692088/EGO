#!/usr/bin/env python3
"""
Run post-promotion observation for a promoted scenario.

Usage:
    python scripts/run_post_promotion_observation.py --scenario complex_semantic_reasoning --rounds 3 --samples 50

v6i: Post-Promotion Observation
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
from emotiond.memory.embedding.post_promotion_guard import PostPromotionGuard
from emotiond.memory.embedding.post_promotion_stability import (
    PostPromotionStabilityEvaluator,
    StabilityVerdict,
)


def generate_realistic_observations(count: int, inject_issues: bool = False) -> list:
    """Generate realistic observation samples."""
    observations = []

    for i in range(count):
        obs = {
            "success": True,
            "latency_ms": random.gauss(65, 15),  # Realistic latency distribution
            "fallback": False,
            "wrong_user_guard": False,
            "provider_health": True,
            "quality_signal": random.uniform(0.3, 0.5),
        }

        # Inject occasional issues if requested
        if inject_issues and random.random() < 0.05:
            obs["fallback"] = True

        observations.append(obs)

    return observations


def main():
    parser = argparse.ArgumentParser(description="Run post-promotion observation")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario to observe (e.g., complex_semantic_reasoning)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Number of observation rounds (default: 3)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=50,
        help="Samples per round (default: 50)",
    )
    parser.add_argument(
        "--inject-issues",
        action="store_true",
        help="Inject occasional issues for testing",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Only evaluate stability, don't run observations",
    )

    args = parser.parse_args()

    # Create registry and evaluator
    registry = ProductionWhitelistRegistry()
    guard = PostPromotionGuard(registry)
    evaluator = PostPromotionStabilityEvaluator(registry, guard)

    # Check if scenario is promoted
    if not registry.is_in_production_whitelist(args.scenario):
        print(f"ERROR: {args.scenario} is not in production whitelist")
        print(f"Promoted scenarios: {registry.get_production_whitelist()}")
        sys.exit(1)

    print(f"=== Post-Promotion Observation for {args.scenario} ===")
    print(f"Rounds: {args.rounds}")
    print(f"Samples per round: {args.samples}")
    print()

    if not args.eval_only:
        # Run observation rounds
        for round_num in range(1, args.rounds + 1):
            print(f"--- Round {round_num}/{args.rounds} ---")

            # Generate observations
            observations = generate_realistic_observations(
                count=args.samples,
                inject_issues=args.inject_issues,
            )

            # Record round
            receipt = evaluator.record_observation_round(args.scenario, observations)

            print(f"  sample_count: {receipt.sample_count}")
            print(f"  fallback_rate: {receipt.fallback_rate:.1%}")
            print(f"  p95_latency_ms: {receipt.p95_latency_ms:.1f}")
            print(f"  wrong_user_guard: {receipt.wrong_user_guard_trigger_count}")
            print(f"  provider_health_rate: {receipt.provider_health_rate:.1%}")
            print(f"  quality_gain_signal: {receipt.quality_gain_signal:.2f}")
            print(f"  guard_status: {receipt.guard_status}")
            print()

    # Evaluate stability
    print("=== Stability Evaluation ===")
    evaluation = evaluator.evaluate_stability(args.scenario)

    print(f"Verdict: {evaluation.verdict.value}")
    print(f"Observation rounds: {evaluation.observation_rounds}")
    print(f"Request count: {evaluation.metrics_summary.get('request_count', 0)}")

    if evaluation.blockers:
        print(f"Blockers: {evaluation.blockers}")

    print(f"Rationale: {evaluation.rationale}")
    print(f"Next action: {evaluation.next_allowed_action}")

    # Save report
    report_path = evaluator.save_stability_report(args.scenario)
    print()
    print(f"Report saved to: {report_path}")

    # Return code based on verdict
    if evaluation.verdict == StabilityVerdict.STABLE_KEEP_PROMOTED:
        return 0
    elif evaluation.verdict == StabilityVerdict.KEEP_UNDER_OBSERVATION:
        return 1
    else:
        return 2


if __name__ == "__main__":
    sys.exit(main())
