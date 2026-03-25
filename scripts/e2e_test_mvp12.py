#!/usr/bin/env python3
"""
MVP12 T03.1: Full E2E Cycle Test

Runs 100 cycles and verifies cycle_success_rate >= 0.95
Outputs to artifacts/mvp12/e2e_results.json
"""

import sys
import os
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from emotiond.developmental_core import (
    CycleEngine,
    CycleMemory,
    HypothesisGenerator,
    CandidateEvaluator,
    CycleMetricsCollector,
    CycleTrigger,
)


def run_e2e_test():
    """Run full E2E cycle test with 100 cycles."""
    print("Starting MVP12 T03.1: Full E2E Cycle Test")
    print("=" * 60)
    
    # Initialize components
    engine = CycleEngine(seed=42)
    memory = CycleMemory()
    gen = HypothesisGenerator(seed=42)
    evaluator = CandidateEvaluator()
    collector = CycleMetricsCollector()
    
    # Clear previous data
    memory.clear_pool()
    collector.reset()
    
    # Run 100 cycles
    total_cycles = 100
    successful = 0
    failed = 0
    
    for i in range(total_cycles):
        try:
            # Start cycle
            ctx = engine.start_cycle(CycleTrigger.IDLE)
            
            # Generate candidates
            candidates = gen.generate(ctx)
            
            # Evaluate candidates
            results = evaluator.evaluate_batch(candidates)
            
            # Get approved candidates
            approved_candidates = [
                c for c, r in zip(candidates, results) 
                if r.approved_for_pool
            ]
            
            # Complete cycle
            result = engine.complete_cycle(ctx, approved_candidates)
            
            # Store cycle
            memory.store_cycle(result)
            
            # Record metrics
            collector.record_cycle(
                cycle_id=ctx.cycle_id,
                success=True,
                trigger=ctx.trigger.value,
                candidates_generated=len(candidates),
                candidates_approved=len(approved_candidates),
                trace_hash=ctx.trace_hash
            )
            
            # Add approved candidates to pool
            for cand, eval_result in zip(candidates, results):
                if eval_result.approved_for_pool:
                    memory.add_to_pool(cand, eval_result.score)
            
            successful += 1
            
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{total_cycles} cycles completed")
                
        except Exception as e:
            failed += 1
            print(f"Cycle {i+1} failed: {e}")
            collector.record_sandbox_violation(
                cycle_id=f"cycle_{i}",
                violation_type="cycle_error",
                details={"error": str(e)}
            )
    
    # Get final metrics
    metrics = collector.get_aggregate_metrics()
    
    print("\n" + "=" * 60)
    print("E2E Test Results:")
    print(f"  Total Cycles: {metrics['total_cycles']}")
    print(f"  Successful: {metrics['successful_cycles']}")
    print(f"  Failed: {metrics['failed_cycles']}")
    print(f"  Success Rate: {metrics['cycle_success_rate']:.2%}")
    print(f"  Total Candidates Generated: {metrics['total_candidates_generated']}")
    print(f"  Total Candidates Approved: {metrics['total_candidates_approved']}")
    print(f"  Candidate Pool Size: {memory.get_pool_size()}")
    print(f"  Sandbox Violations: {metrics['sandbox_violations']}")
    
    # Create results output
    e2e_results = {
        "test_name": "MVP12 T03.1: Full E2E Cycle Test",
        "timestamp": metrics['last_updated'],
        "configuration": {
            "total_cycles": total_cycles,
            "seed": 42
        },
        "results": {
            "total_cycles": metrics['total_cycles'],
            "successful_cycles": metrics['successful_cycles'],
            "failed_cycles": metrics['failed_cycles'],
            "cycle_success_rate": metrics['cycle_success_rate'],
            "total_candidates_generated": metrics['total_candidates_generated'],
            "total_candidates_approved": metrics['total_candidates_approved'],
            "candidate_pool_size": memory.get_pool_size(),
            "sandbox_violations": metrics['sandbox_violations'],
            "trigger_breakdown": metrics['trigger_breakdown']
        },
        "assertions": {
            "cycle_success_rate_threshold": 0.95,
            "cycle_success_rate_actual": metrics['cycle_success_rate'],
            "cycle_success_rate_passed": metrics['cycle_success_rate'] >= 0.95
        },
        "evidence": {
            "cycles_file": "artifacts/mvp12/developmental_cycles.json",
            "pool_file": "artifacts/mvp12/candidate_pool.json",
            "traces_dir": "artifacts/mvp12/cycle_traces",
            "metrics_file": "artifacts/mvp12/sandbox_metrics.json"
        }
    }
    
    # Save results
    output_path = project_root / "artifacts" / "mvp12" / "e2e_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(e2e_results, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    # Verify assertion
    if metrics['cycle_success_rate'] >= 0.95:
        print("\n✅ PASS: cycle_success_rate >= 0.95")
        return True
    else:
        print(f"\n❌ FAIL: cycle_success_rate {metrics['cycle_success_rate']:.2%} < 0.95")
        return False


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)
