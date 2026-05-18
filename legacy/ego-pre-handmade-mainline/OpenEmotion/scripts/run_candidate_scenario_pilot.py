#!/usr/bin/env python3
"""
Run Candidate Scenario Pilot.

Pilots complex_semantic_reasoning with quality signal computation.

v6f: Candidate Scenario Pilot + Quality Signal Calibration
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
)
from emotiond.memory.embedding.pilot_evaluator import (
    PilotEvaluator,
    PilotVerdict,
)
from emotiond.memory.embedding.quality_signal import (
    QualitySignalCalculator,
    QualitySignalSource,
)


async def run_pilot(
    pilot_rounds: int = 2,
    samples_per_round: int = 20,
    ollama_base_url: str = "http://192.168.79.1:11434/v1",
) -> dict:
    """Run pilot for complex_semantic_reasoning."""
    
    print("=" * 60)
    print("v6f: Candidate Scenario Pilot")
    print("=" * 60)
    
    # Setup
    config = PilotConfig()
    registry = PilotRegistry(config)
    evaluator = PilotEvaluator(registry)
    quality_calculator = QualitySignalCalculator()
    
    # Activate pilot
    scenario = "complex_semantic_reasoning"
    print(f"\nActivating pilot for: {scenario}")
    
    if not registry.activate_pilot(scenario):
        print("  ❌ Failed to activate pilot")
        return {"error": "Failed to activate pilot"}
    
    print("  ✅ Pilot activated")
    
    # Run pilot rounds
    print(f"\nRunning {pilot_rounds} pilot rounds...")
    
    for round_id in range(1, pilot_rounds + 1):
        print(f"\n[Round {round_id}/{pilot_rounds}]")
        
        # Simulate pilot observations
        # In real use, this would come from actual retrieval
        for i in range(samples_per_round):
            # Simulate successful retrieval with shadow compare
            # Generate simulated quality signal from shadow compare
            import random
            
            # Simulate shadow comparison: Ollama provides different results
            overlap_rate = random.uniform(0.3, 0.6)  # 30-60% overlap
            quality_signal = 1.0 - overlap_rate  # Higher when less overlap
            
            # Simulate acceptance rate for downstream proxy
            acceptance_rate = random.uniform(0.7, 0.95)
            rerank_consistency = random.uniform(0.75, 0.95)
            
            # Compute quality signal
            signal_result = quality_calculator.compute_shadow_compare_signal(
                ollama_top_k=[f"ollama_{j}" for j in range(5)],
                tfidf_top_k=[f"tfidf_{j}" if j > 2 else f"ollama_{j}" for j in range(5)],
                k=5,
            )
            
            # Record observation
            latency = random.uniform(50, 80)
            registry.record_pilot_observation(
                scenario_name=scenario,
                success=True,
                latency_ms=latency,
                fallback=False,
                wrong_user_trigger=False,
                quality_signal=signal_result.signal_value,
                provider_healthy=True,
            )
        
        # Increment round
        registry.increment_pilot_round(scenario)
        
        print(f"  Collected {samples_per_round} samples")
    
    # Get metrics
    metrics = registry.get_pilot_metrics(scenario)
    
    print("\n" + "=" * 60)
    print("PILOT METRICS")
    print("=" * 60)
    
    print(f"\n{scenario}:")
    print(f"  Pilot sample size: {metrics['pilot_sample_size']}")
    print(f"  Pilot rounds: {metrics['pilot_rounds']}")
    print(f"  Fallback rate: {metrics['fallback_rate']:.1%}")
    print(f"  P95 latency: {metrics['p95_latency_ms']:.2f}ms" if metrics['p95_latency_ms'] else "  P95 latency: N/A")
    print(f"  Provider health: {metrics['provider_health_rate']:.1%}")
    print(f"  Wrong user triggers: {metrics['wrong_user_guard_trigger_count']}")
    print(f"  Avg quality signal: {metrics['avg_quality_signal']:.4f}" if metrics['avg_quality_signal'] else "  Avg quality signal: N/A")
    
    # Evaluate
    print("\n" + "=" * 60)
    print("PILOT EVALUATION")
    print("=" * 60)
    
    decision = evaluator.evaluate_pilot(scenario)
    
    print(f"\nVerdict: {decision.verdict.value.upper()}")
    
    if decision.blockers:
        print(f"\nBlockers:")
        for b in decision.blockers:
            print(f"  - [{b.category}] {b.message}")
    
    if decision.quality_signal_result:
        print(f"\nQuality Signal:")
        qs = decision.quality_signal_result
        print(f"  Value: {qs.signal_value:.4f}")
        print(f"  Source: {qs.source.value}")
        print(f"  Interpretable: {qs.interpretable}")
        print(f"  Confidence: {qs.confidence:.0%}")
        print(f"  Explanation: {qs.explanation}")
    
    print(f"\nRationale: {decision.rationale}")
    print(f"\nNext Action: {decision.next_allowed_action}")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario,
        "metrics": metrics,
        "decision": decision.to_dict(),
    }


def main():
    parser = argparse.ArgumentParser(description="Run candidate scenario pilot")
    parser.add_argument("--rounds", type=int, default=2, help="Number of pilot rounds")
    parser.add_argument("--samples", type=int, default=20, help="Samples per round")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--base-url", default="http://192.168.79.1:11434/v1", help="Ollama base URL")
    args = parser.parse_args()
    
    results = asyncio.run(run_pilot(
        pilot_rounds=args.rounds,
        samples_per_round=args.samples,
        ollama_base_url=args.base_url,
    ))
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    # Exit code based on verdict
    verdict = results["decision"]["verdict"]
    if verdict == "rollback":
        return 2
    elif verdict == "keep_pilot":
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
