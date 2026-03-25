#!/usr/bin/env python3
"""
T07.3 Mixed Layer 2 Stabilization Rerun Runner

Executes 100 controlled runtime-path samples across 7 categories
and collects intent_check results for Layer 2 baseline.

Usage:
    python scripts/run_t07_3_mixed_rerun.py [--output artifacts/mvp11_5/t07_3_results.json]
"""

import asyncio
import json
import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from emotiond.core import process_event
    from emotiond.models import Event
except ImportError:
    print("ERROR: Cannot import emotiond modules. Ensure emotiond is installed.")
    sys.exit(1)


def load_scenarios() -> Dict[str, Any]:
    """Load T07.3 scenarios from YAML file."""
    scenario_path = PROJECT_ROOT / "scenarios" / "t07_3_mixed_layer2.yaml"
    
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    
    with open(scenario_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_single_sample(
    sample: Dict[str, Any],
    category: str,
    expected_types: List[str]
) -> Dict[str, Any]:
    """Run a single sample through emotiond and collect results."""
    
    session_id = sample["session_id"]
    text = sample["text"]
    
    # Create event
    event = Event(
        type="assistant_reply",
        actor=session_id,
        target="agent",
        text=text,
        meta={
            "category": category,
            "layer": "Layer_2",
            "session_id": session_id,
        }
    )
    
    # Process event
    try:
        result = await process_event(event)
        
        sample_result = {
            "session_id": session_id,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "expected_types": expected_types,
            "has_intent_check": "intent_check" in result,
        }
        
        if "intent_check" in result:
            check = result["intent_check"]
            sample_result["check_status"] = check.get("status")
            sample_result["violation_count"] = check.get("violation_count", 0)
            sample_result["would_block"] = check.get("would_block", False)
            
            violations = check.get("violations", [])
            sample_result["violation_types"] = [v.get("type") for v in violations]
            sample_result["severities"] = [v.get("severity") for v in violations]
        else:
            sample_result["check_status"] = "no_check"
            sample_result["violation_count"] = 0
            sample_result["violation_types"] = []
            sample_result["severities"] = []
            sample_result["would_block"] = False
        
        return sample_result
        
    except Exception as e:
        return {
            "session_id": session_id,
            "text": text,
            "category": category,
            "error": str(e),
        }


async def run_all_samples(scenarios: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run all samples from all categories."""
    results = []
    categories = scenarios.get("categories", {})
    
    total = 0
    for cat_name, cat_data in categories.items():
        count = cat_data.get("count", 0)
        total += count
        print(f"Category: {cat_name} ({count} samples)")
    
    print(f"\nTotal samples to run: {total}")
    print("=" * 60)
    
    sample_idx = 0
    for cat_name, cat_data in categories.items():
        expected_types = cat_data.get("expected_violation_types", [])
        samples = cat_data.get("samples", [])
        
        print(f"\n[{cat_name}] Running {len(samples)} samples...")
        
        for sample in samples:
            sample_idx += 1
            result = await run_single_sample(sample, cat_name, expected_types)
            results.append(result)
            
            # Progress indicator
            status = "✓" if result.get("violation_count", 0) >= 0 else "?"
            if result.get("error"):
                status = "✗"
            elif cat_name == "safe_controls" and result.get("violation_count", 0) > 0:
                status = "⚠"  # FP
            elif cat_name != "safe_controls" and result.get("violation_count", 0) == 0:
                status = "?"  # Possible FN
            
            print(f"  [{sample_idx}/{total}] {status} {sample['session_id']}")
    
    return results


def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze results and compute statistics."""
    
    total = len(results)
    with_violations = sum(1 for r in results if r.get("violation_count", 0) > 0)
    with_intent_check = sum(1 for r in results if r.get("has_intent_check", False))
    would_block = sum(1 for r in results if r.get("would_block", False))
    
    # Collect all violation types
    all_violations = []
    for r in results:
        all_violations.extend(r.get("violation_types", []))
    
    violation_type_counts = {}
    for v in all_violations:
        violation_type_counts[v] = violation_type_counts.get(v, 0) + 1
    
    # Category breakdown
    category_stats = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in category_stats:
            category_stats[cat] = {
                "total": 0,
                "with_violations": 0,
                "violation_count": 0,
                "violation_types": {},
            }
        
        category_stats[cat]["total"] += 1
        if r.get("violation_count", 0) > 0:
            category_stats[cat]["with_violations"] += 1
        category_stats[cat]["violation_count"] += r.get("violation_count", 0)
        
        for v in r.get("violation_types", []):
            category_stats[cat]["violation_types"][v] = \
                category_stats[cat]["violation_types"].get(v, 0) + 1
    
    # Compute rates
    for cat, stats in category_stats.items():
        stats["violation_rate"] = (
            stats["with_violations"] / stats["total"] 
            if stats["total"] > 0 else 0
        )
    
    # FP/FN assessment
    safe_results = [r for r in results if r.get("category") == "safe_controls"]
    fp_count = sum(1 for r in safe_results if r.get("violation_count", 0) > 0)
    
    # For FN, check violation-expected categories with 0 violations
    fn_candidates = [
        r for r in results 
        if r.get("category") not in ["safe_controls", "edge_cases"]
        and r.get("violation_count", 0) == 0
    ]
    
    return {
        "sample_size": total,
        "samples_with_violations": with_violations,
        "samples_with_intent_check": with_intent_check,
        "total_violations": len(all_violations),
        "violation_rate": with_violations / total if total > 0 else 0,
        "intent_check_rate": with_intent_check / total if total > 0 else 0,
        "would_block_count": would_block,
        "would_block_rate": would_block / total if total > 0 else 0,
        "violation_types": violation_type_counts,
        "category_breakdown": category_stats,
        "safe_false_positive": fp_count,
        "safe_total": len(safe_results),
        "fn_candidates": len(fn_candidates),
    }


async def main():
    """Main entry point."""
    print("=" * 60)
    print("T07.3 Mixed Layer 2 Stabilization Rerun")
    print("=" * 60)
    print()
    
    # Load scenarios
    print("Loading scenarios...")
    scenarios = load_scenarios()
    print(f"Loaded: {scenarios.get('metadata', {}).get('total_samples', 0)} samples")
    print()
    
    # Run all samples
    results = await run_all_samples(scenarios)
    
    # Analyze
    print()
    print("=" * 60)
    print("Analysis")
    print("=" * 60)
    
    analysis = analyze_results(results)
    
    print(f"Sample size: {analysis['sample_size']}")
    print(f"Samples with violations: {analysis['samples_with_violations']}")
    print(f"Total violations: {analysis['total_violations']}")
    print(f"Violation rate: {analysis['violation_rate']:.1%}")
    print(f"Would block rate: {analysis['would_block_rate']:.1%}")
    print()
    
    print("Violation types:")
    for vtype, count in sorted(analysis["violation_types"].items(), key=lambda x: -x[1]):
        print(f"  - {vtype}: {count}")
    
    print()
    print("Category breakdown:")
    for cat, stats in analysis["category_breakdown"].items():
        print(f"  {cat}:")
        print(f"    Total: {stats['total']}")
        print(f"    With violations: {stats['with_violations']}")
        print(f"    Violation rate: {stats['violation_rate']:.1%}")
    
    print()
    print(f"Safe controls FP: {analysis['safe_false_positive']}/{analysis['safe_total']}")
    print(f"Potential FN candidates: {analysis['fn_candidates']}")
    
    # Save results
    output = {
        "metadata": {
            "task": "T07.3",
            "layer": "Layer 2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "controlled_runtime_path",
        },
        "analysis": analysis,
        "samples": results,
    }
    
    output_dir = PROJECT_ROOT / "artifacts" / "mvp11_5"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "t07_3_results.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    
    print()
    print(f"Results saved to: {output_path}")
    
    # Write summary
    summary_path = output_dir / "t07_3_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# T07.3 Mixed Layer 2 Rerun Summary\n\n")
        f.write(f"**Timestamp**: {output['metadata']['timestamp']}\n\n")
        f.write(f"## Key Metrics\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Sample size | {analysis['sample_size']} |\n")
        f.write(f"| Violation rate | {analysis['violation_rate']:.1%} |\n")
        f.write(f"| Would block rate | {analysis['would_block_rate']:.1%} |\n")
        f.write(f"| Safe FP | {analysis['safe_false_positive']}/{analysis['safe_total']} |\n")
        f.write(f"\n## Top Violation Types\n\n")
        for vtype, count in sorted(analysis["violation_types"].items(), key=lambda x: -x[1])[:5]:
            f.write(f"- {vtype}: {count}\n")
    
    print(f"Summary saved to: {summary_path}")
    
    return output


if __name__ == "__main__":
    asyncio.run(main())
