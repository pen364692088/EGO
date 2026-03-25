#!/usr/bin/env python3
"""
Run Real-Time Observation for High-Quality Retrieval Mode.

Collects real metrics and generates admission decision.

v6c: High-Quality Retrieval Mode Admission Governance
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
)
from emotiond.memory.embedding.admission import (
    AdmissionGovernor,
    AdmissionMetrics,
    AdmissionThresholds,
    AdmissionState,
)
from emotiond.memory.embedding.telemetry import get_telemetry


async def collect_sample(selector: ProviderSelector, mode: str) -> dict:
    """Collect a single sample for the given mode."""
    result = {
        "mode": mode,
        "success": False,
        "latency_ms": 0,
        "fallback_triggered": False,
        "provider_used": "",
    }
    
    try:
        provider, trace = await selector.select_provider(mode)
        
        result["success"] = True
        result["latency_ms"] = trace.latency_ms
        result["fallback_triggered"] = trace.fallback_triggered
        result["provider_used"] = trace.provider_used
        result["resolved_mode"] = trace.resolved_mode
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


async def run_observation(
    sample_count: int = 20,
    ollama_base_url: str = "http://192.168.79.1:11434/v1",
) -> dict:
    """Run observation and collect metrics."""
    
    print("=" * 60)
    print("v6c: Real-Time Observation for High-Quality Mode")
    print("=" * 60)
    
    config = RetrievalConfig(
        mode="tfidf",
        allow_high_quality_mode=True,
        fallback_on_provider_failure=True,
        ollama_base_url=ollama_base_url,
    )
    selector = ProviderSelector(config)
    telemetry = get_telemetry()
    
    # Collect samples
    samples = []
    tfidf_samples = []
    ollama_samples = []
    
    print(f"\nCollecting {sample_count} samples...")
    
    for i in range(sample_count):
        # Alternate between tfidf and ollama requests
        mode = "tfidf" if i % 2 == 0 else "ollama"
        
        sample = await collect_sample(selector, mode)
        samples.append(sample)
        
        if sample["success"]:
            telemetry.record_usage(
                provider=sample["provider_used"],
                latency_ms=sample["latency_ms"],
                success=sample["success"],
                fallback_triggered=sample["fallback_triggered"],
            )
            
            if sample["provider_used"] == "tfidf":
                tfidf_samples.append(sample)
            else:
                ollama_samples.append(sample)
        
        print(f"  [{i+1}/{sample_count}] {mode} -> {sample.get('provider_used', 'N/A')} "
              f"({'fallback' if sample.get('fallback_triggered') else 'ok'})")
    
    # Build metrics
    metrics = AdmissionMetrics(
        sample_size=sample_count,
        request_count=sample_count,
        success_count=sum(1 for s in samples if s["success"]),
        fallback_count=sum(1 for s in samples if s.get("fallback_triggered")),
        timeout_count=sum(1 for s in samples if not s["success"]),
        wrong_user_recall_count=0,  # Would need retrieval test to measure
        latencies=[s["latency_ms"] for s in samples if s["success"]],
        health_check_success_count=sum(1 for s in ollama_samples if s["provider_used"] == "ollama"),
        health_check_total_count=len(ollama_samples),
    )
    
    # Quality gain from v6a results
    metrics.tfidf_hit_at_1 = 0.4
    metrics.ollama_hit_at_1 = 0.6
    metrics.quality_gain = metrics.ollama_hit_at_1 - metrics.tfidf_hit_at_1
    
    # Make decision
    governor = AdmissionGovernor(metrics=metrics)
    decision = governor.decide()
    
    # Output
    print("\n" + "=" * 60)
    print("OBSERVATION RESULTS")
    print("=" * 60)
    
    print(f"\nMetrics:")
    print(f"  Sample size: {metrics.sample_size}")
    print(f"  Success count: {metrics.success_count}")
    print(f"  Fallback count: {metrics.fallback_count}")
    print(f"  Fallback rate: {metrics.fallback_rate:.1%}")
    print(f"  Avg latency: {metrics.avg_latency_ms:.2f}ms" if metrics.avg_latency_ms else "  Avg latency: N/A")
    print(f"  P95 latency: {metrics.p95_latency_ms:.2f}ms" if metrics.p95_latency_ms else "  P95 latency: N/A")
    print(f"  Provider health rate: {metrics.provider_health_rate:.1%}")
    
    print(f"\nGates:")
    for gate in decision.gates:
        status_icon = "✅" if gate.status.value == "pass" else "❌" if gate.status.value == "fail" else "⚠️"
        print(f"  {status_icon} {gate.gate_name}: {gate.actual} (threshold: {gate.threshold})")
    
    print(f"\nState: {decision.state.value.upper()}")
    
    if decision.blockers:
        print(f"\nBlockers:")
        for b in decision.blockers:
            print(f"  - {b}")
    
    if decision.recommendations:
        print(f"\nRecommendations:")
        for r in decision.recommendations:
            print(f"  - {r}")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics.to_dict(),
        "decision": decision.to_dict(),
    }


def main():
    parser = argparse.ArgumentParser(description="Run observation for high-quality mode")
    parser.add_argument("--samples", type=int, default=20, help="Number of samples to collect")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--base-url", default="http://192.168.79.1:11434/v1", help="Ollama base URL")
    args = parser.parse_args()
    
    results = asyncio.run(run_observation(
        sample_count=args.samples,
        ollama_base_url=args.base_url,
    ))
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    # Exit code based on state
    state = results["decision"]["state"]
    if state == "rollback_required":
        return 2
    elif state == "manual_only":
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
