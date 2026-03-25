#!/usr/bin/env python3
"""
Run Limited Rollout Observation.

Tests rollout policy with whitelist scenarios.

v6d: Limited Rollout for High-Quality Retrieval Mode
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.scenario_router import (
    RolloutConfig,
    ScenarioContext,
    RetrievalScenario,
)
from emotiond.memory.embedding.rollout import (
    RolloutPolicy,
    RolloutVerdict,
)


# Test cases for different scenarios
TEST_CASES = [
    # Whitelist scenarios
    {
        "query": "I remember something about a project we discussed",
        "action_type": "memory_search",
        "expected_scenario": RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value,
        "expected_rollout": True,
    },
    {
        "query": "I think there was something like a meeting last week",
        "action_type": "narrative_recall",
        "expected_scenario": RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value,
        "expected_rollout": True,
    },
    {
        "query": "Find the conversation where we discussed the long-term roadmap and quarterly planning for the project milestone review",
        "action_type": "semantic_lookup",
        "expected_scenario": RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value,
        "expected_rollout": True,
    },
    # Non-whitelist scenarios
    {
        "query": '"exact keyword search"',
        "action_type": "search",
        "expected_scenario": RetrievalScenario.KEYWORD_EXACT_MATCH.value,
        "expected_rollout": False,
    },
    {
        "query": "quick search",
        "action_type": "real-time",
        "expected_scenario": RetrievalScenario.LOW_LATENCY_PATH.value,
        "expected_rollout": False,
    },
    {
        "query": "hello world",
        "action_type": "default",
        "expected_scenario": RetrievalScenario.DEFAULT.value,
        "expected_rollout": False,
    },
]


async def run_rollout_observation(
    sample_count: int = 20,
    ollama_base_url: str = "http://192.168.79.1:11434/v1",
) -> dict:
    """Run rollout observation."""
    
    print("=" * 60)
    print("v6d: Limited Rollout Observation")
    print("=" * 60)
    
    # Configure rollout
    rollout_config = RolloutConfig(
        enabled=True,
        default_mode="tfidf",
        allowed_scenarios=[
            RetrievalScenario.MEMORY_SEARCH_HARD_QUERY.value,
            RetrievalScenario.NARRATIVE_RECALL_AMBIGUOUS_QUERY.value,
            RetrievalScenario.LONG_CONTEXT_SEMANTIC_LOOKUP.value,
        ],
        rollout_percentage=100,
        fallback_to_tfidf=True,
        shadow_compare_enabled=False,
    )
    
    from emotiond.memory.embedding.selector import RetrievalConfig
    retrieval_config = RetrievalConfig(
        mode="tfidf",
        allow_high_quality_mode=True,
        fallback_on_provider_failure=True,
        ollama_base_url=ollama_base_url,
    )
    
    policy = RolloutPolicy(rollout_config, retrieval_config)
    
    print(f"\nRollout Config:")
    print(f"  Enabled: {rollout_config.enabled}")
    print(f"  Default mode: {rollout_config.default_mode}")
    print(f"  Allowed scenarios: {rollout_config.allowed_scenarios}")
    
    # Run tests
    results = []
    print(f"\nRunning {sample_count} samples...")
    
    for i in range(sample_count):
        test_case = TEST_CASES[i % len(TEST_CASES)]
        
        context = ScenarioContext(
            query=test_case["query"],
            action_type=test_case["action_type"],
        )
        
        try:
            provider, trace = await policy.execute_retrieval(context)
            
            results.append({
                "query": test_case["query"][:40] + "..." if len(test_case["query"]) > 40 else test_case["query"],
                "expected_scenario": test_case["expected_scenario"],
                "actual_scenario": trace.scenario_name,
                "expected_rollout": test_case["expected_rollout"],
                "actual_rollout": trace.rollout_applied,
                "provider": trace.provider_used,
                "fallback": trace.fallback_triggered,
                "latency_ms": round(trace.latency_ms, 2),
            })
            
            status = "✅" if trace.rollout_applied == test_case["expected_rollout"] else "⚠️"
            print(f"  [{i+1}/{sample_count}] {status} {trace.scenario_name[:25]:<25} -> {trace.provider_used:<7} (rollout={trace.rollout_applied})")
            
        except Exception as e:
            print(f"  [{i+1}/{sample_count}] ❌ Error: {str(e)[:50]}")
            results.append({
                "error": str(e),
            })
    
    # Get metrics
    metrics = policy.get_metrics()
    verdict = policy.get_verdict()
    
    # Output
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    print(f"\nMetrics:")
    print(f"  Whitelist requests: {metrics.whitelist_requests}")
    print(f"  Non-whitelist requests: {metrics.non_whitelist_requests}")
    print(f"  Ollama success: {metrics.ollama_success_count}")
    print(f"  Fallback count: {metrics.ollama_fallback_count}")
    print(f"  TF-IDF count: {metrics.tfidf_count}")
    print(f"  P95 latency: {metrics.p95_latency_ms:.2f}ms")
    print(f"  Fallback rate: {metrics.fallback_rate:.1%}")
    
    print(f"\nVerdict: {verdict.value}")
    
    # Verify whitelist behavior
    print("\n" + "=" * 60)
    print("WHITELIST VERIFICATION")
    print("=" * 60)
    
    whitelist_correct = 0
    non_whitelist_correct = 0
    
    for r in results:
        if "error" not in r:
            if r["expected_rollout"]:
                if r["actual_rollout"]:
                    whitelist_correct += 1
            else:
                if not r["actual_rollout"]:
                    non_whitelist_correct += 1
    
    total_whitelist = sum(1 for r in results if "expected_rollout" in r and r["expected_rollout"])
    total_non_whitelist = sum(1 for r in results if "expected_rollout" in r and not r["expected_rollout"])
    
    print(f"  Whitelist scenarios -> Ollama: {whitelist_correct}/{total_whitelist}")
    print(f"  Non-whitelist scenarios -> TF-IDF: {non_whitelist_correct}/{total_non_whitelist}")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "config": rollout_config.to_dict(),
        "metrics": metrics.to_dict(),
        "verdict": verdict.value,
        "whitelist_verification": {
            "whitelist_correct": whitelist_correct,
            "whitelist_total": total_whitelist,
            "non_whitelist_correct": non_whitelist_correct,
            "non_whitelist_total": total_non_whitelist,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run limited rollout observation")
    parser.add_argument("--samples", type=int, default=20, help="Number of samples")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--base-url", default="http://192.168.79.1:11434/v1", help="Ollama base URL")
    args = parser.parse_args()
    
    results = asyncio.run(run_rollout_observation(
        sample_count=args.samples,
        ollama_base_url=args.base_url,
    ))
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    # Exit code based on whitelist correctness
    whitelist_rate = results["whitelist_verification"]["whitelist_correct"] / max(results["whitelist_verification"]["whitelist_total"], 1)
    non_whitelist_rate = results["whitelist_verification"]["non_whitelist_correct"] / max(results["whitelist_verification"]["non_whitelist_total"], 1)
    
    if whitelist_rate >= 0.8 and non_whitelist_rate >= 0.8:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
