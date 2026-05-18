#!/usr/bin/env python3
"""
MVP12 T03.2: Replay Consistency Verification

Runs same cycles twice with same seed and verifies replay_consistency >= 0.99
Outputs to artifacts/mvp12/replay_consistency_report.json
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from emotiond.developmental_core import (
    CycleEngine,
    HypothesisGenerator,
    CycleTrigger,
)


def run_cycles_with_seed(seed: int, num_cycles: int = 50) -> List[Dict[str, Any]]:
    """Run cycles with a specific seed and return trace hashes."""
    engine = CycleEngine(seed=seed)
    gen = HypothesisGenerator(seed=seed)
    
    traces = []
    
    for i in range(num_cycles):
        # Start cycle
        ctx = engine.start_cycle(CycleTrigger.IDLE)
        
        # Generate candidates
        candidates = gen.generate(ctx)
        
        # Store trace info
        trace_info = {
            "cycle_index": i,
            "cycle_id": ctx.cycle_id,
            "seed": ctx.seed,
            "trigger": ctx.trigger.value,
            "trace_hash": ctx.trace_hash,
            "num_candidates": len(candidates),
            "candidate_hashes": [c.compute_hash() for c in candidates]
        }
        traces.append(trace_info)
        
        # Complete cycle
        engine.complete_cycle(ctx, candidates)
    
    return traces


def verify_replay_consistency():
    """Verify replay consistency by running same cycles twice."""
    print("Starting MVP12 T03.2: Replay Consistency Verification")
    print("=" * 60)
    
    seed = 12345
    num_cycles = 50
    
    print(f"Configuration: seed={seed}, cycles={num_cycles}")
    print("\nRunning first batch...")
    traces1 = run_cycles_with_seed(seed, num_cycles)
    
    print("Running second batch (replay)...")
    traces2 = run_cycles_with_seed(seed, num_cycles)
    
    print("\nComparing traces...")
    
    # Compare trace hashes
    matching_hashes = 0
    mismatch_details = []
    
    for i, (t1, t2) in enumerate(zip(traces1, traces2)):
        if t1['trace_hash'] == t2['trace_hash']:
            matching_hashes += 1
        else:
            mismatch_details.append({
                "cycle_index": i,
                "trace1_hash": t1['trace_hash'],
                "trace2_hash": t2['trace_hash']
            })
        
        # Also verify candidate hashes match
        if t1['candidate_hashes'] != t2['candidate_hashes']:
            print(f"  Warning: Candidate hash mismatch at cycle {i}")
    
    replay_consistency = matching_hashes / num_cycles if num_cycles > 0 else 0.0
    
    print("\n" + "=" * 60)
    print("Replay Consistency Results:")
    print(f"  Total Cycles: {num_cycles}")
    print(f"  Matching Trace Hashes: {matching_hashes}")
    print(f"  Replay Consistency: {replay_consistency:.2%}")
    print(f"  Mismatches: {num_cycles - matching_hashes}")
    
    if mismatch_details:
        print(f"\n  First few mismatches:")
        for detail in mismatch_details[:3]:
            print(f"    Cycle {detail['cycle_index']}: {detail['trace1_hash']} != {detail['trace2_hash']}")
    
    # Create report
    report = {
        "test_name": "MVP12 T03.2: Replay Consistency Verification",
        "timestamp": traces1[-1]['cycle_id'] if traces1 else "",
        "configuration": {
            "seed": seed,
            "num_cycles": num_cycles
        },
        "results": {
            "total_cycles": num_cycles,
            "matching_trace_hashes": matching_hashes,
            "replay_consistency": replay_consistency,
            "mismatches": num_cycles - matching_hashes
        },
        "assertions": {
            "replay_consistency_threshold": 0.99,
            "replay_consistency_actual": replay_consistency,
            "replay_consistency_passed": replay_consistency >= 0.99
        },
        "trace_samples": {
            "batch1_sample": traces1[:5],
            "batch2_sample": traces2[:5]
        },
        "mismatch_details": mismatch_details[:10] if mismatch_details else []
    }
    
    # Save report
    output_path = project_root / "artifacts" / "mvp12" / "replay_consistency_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"\nReport saved to: {output_path}")
    
    # Verify assertion
    if replay_consistency >= 0.99:
        print("\n✅ PASS: replay_consistency >= 0.99")
        return True
    else:
        print(f"\n❌ FAIL: replay_consistency {replay_consistency:.2%} < 0.99")
        return False


if __name__ == "__main__":
    success = verify_replay_consistency()
    sys.exit(0 if success else 1)
