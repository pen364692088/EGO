#!/usr/bin/env python
"""
MVP14 Runtime Diff Statistics

Collects real-time diff statistics between legacy DriveState and new DriveManager.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.drive_homeostasis import DriveState, get_drive_modulation_params, drive_error
from emotiond.drives import get_drive_manager
from emotiond.drives.schema import DriveType
import json
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, field, asdict


@dataclass
class DiffSample:
    """Single diff sample."""
    timestamp: str
    legacy_values: Dict[str, float]
    new_values: Dict[str, float]
    field_diffs: Dict[str, float]
    params_legacy: Dict[str, float]
    params_new: Dict[str, float]
    param_diffs: Dict[str, float]
    rank_change: bool
    top_pattern: str


@dataclass
class DiffStats:
    """Aggregated diff statistics."""
    total_samples: int = 0
    field_diff_rates: Dict[str, float] = field(default_factory=dict)
    avg_field_diffs: Dict[str, float] = field(default_factory=dict)
    param_diff_rates: Dict[str, float] = field(default_factory=dict)
    avg_param_diffs: Dict[str, float] = field(default_factory=dict)
    rank_change_rate: float = 0.0
    top_patterns: List[Dict[str, Any]] = field(default_factory=list)
    samples: List[DiffSample] = field(default_factory=list)
    # MVP14: New metrics for decision drift
    top1_agreement_rate: float = 0.0
    high_risk_avg_diff: float = 0.0
    high_risk_fields: List[str] = field(default_factory=list)


def collect_diff_sample(event_type: str = "test") -> DiffSample:
    """Collect a single diff sample."""
    # Reset DriveManager to ensure clean state
    from emotiond.drives.manager import DriveManager
    DriveManager.reset()
    
    # Legacy
    legacy_state = DriveState()
    legacy_params = get_drive_modulation_params(legacy_state)
    legacy_error = drive_error(legacy_state)
    
    # New
    new_manager = get_drive_manager()
    new_state = new_manager.get_state()
    
    # Field mapping
    field_mapping = {
        "energy": "stability",
        "uncertainty": "coherence",
        "social": "completion",
        "safety": "verification",
        "fatigue": "repair",
    }
    
    # Calculate field diffs
    legacy_values = {}
    new_values = {}
    field_diffs = {}
    
    for legacy_name, new_name in field_mapping.items():
        legacy_val = legacy_state.setpoints.get(legacy_name, 0.5)
        new_drive = new_state.active_drives.get(new_name)
        new_val = new_drive.intensity if new_drive else 0.0
        
        legacy_values[legacy_name] = legacy_val
        new_values[new_name] = new_val
        field_diffs[f"{legacy_name}->{new_name}"] = abs(legacy_val - new_val)
    
    # Param diffs (placeholder - new API doesn't have equivalent)
    param_diffs = {}
    for key in ["risk_aversion", "initiative_level"]:
        param_diffs[key] = 0.0  # Same for now
    
    # Rank change (check if priority order changed for common fields only)
    # Only compare fields that exist in both systems
    common_legacy_fields = ['energy', 'uncertainty', 'social', 'safety', 'fatigue']
    legacy_common = {k: legacy_values[k] for k in common_legacy_fields if k in legacy_values}
    
    mapping = {
        "energy": "stability",
        "uncertainty": "coherence",
        "social": "completion",
        "safety": "verification",
        "fatigue": "repair",
    }
    new_common = {}
    for legacy_name, new_name in mapping.items():
        if new_name in new_values:
            new_common[new_name] = new_values[new_name]
    
    legacy_sorted = sorted(legacy_common.items(), key=lambda x: x[1], reverse=True)
    new_sorted = sorted(new_common.items(), key=lambda x: x[1], reverse=True)
    
    # Compare rankings
    legacy_ranking = [x[0] for x in legacy_sorted]
    new_ranking = [x[0] for x in new_sorted]
    # Map legacy ranking to new field names
    mapped_legacy_ranking = [mapping.get(k, k) for k in legacy_ranking]
    
    rank_change = mapped_legacy_ranking != new_ranking
    
    # Top pattern
    max_diff_field = max(field_diffs.items(), key=lambda x: x[1])
    top_pattern = f"{max_diff_field[0]}: {max_diff_field[1]:.3f}"
    
    return DiffSample(
        timestamp=datetime.now().isoformat(),
        legacy_values=legacy_values,
        new_values=new_values,
        field_diffs=field_diffs,
        params_legacy=legacy_params,
        params_new={},  # Placeholder
        param_diffs=param_diffs,
        rank_change=rank_change,
        top_pattern=top_pattern,
    )


def compute_diff_stats(samples: List[DiffSample]) -> DiffStats:
    """Compute aggregated statistics from samples."""
    if not samples:
        return DiffStats()
    
    stats = DiffStats(total_samples=len(samples))
    
    # Field diff rates (threshold: 0.1)
    field_names = list(samples[0].field_diffs.keys())
    for field in field_names:
        diffs = [s.field_diffs[field] for s in samples]
        stats.field_diff_rates[field] = sum(1 for d in diffs if d > 0.1) / len(diffs)
        stats.avg_field_diffs[field] = sum(diffs) / len(diffs)
    
    # Param diff rates
    param_names = list(samples[0].param_diffs.keys())
    for param in param_names:
        diffs = [s.param_diffs[param] for s in samples]
        stats.param_diff_rates[param] = sum(1 for d in diffs if d > 0.01) / len(diffs)
        stats.avg_param_diffs[param] = sum(diffs) / len(diffs)
    
    # Rank change rate
    stats.rank_change_rate = sum(1 for s in samples if s.rank_change) / len(samples)
    
    # Top patterns
    pattern_counts = {}
    for s in samples:
        pattern = s.top_pattern
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    stats.top_patterns = [
        {"pattern": k, "count": v, "rate": v / len(samples)}
        for k, v in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    
    stats.samples = samples
    
    # MVP14: New metrics for decision drift
    # Top-1 agreement rate (check if the highest priority field is the same)
    top1_matches = 0
    for s in samples:
        # Get top-1 from legacy
        legacy_sorted = sorted(s.legacy_values.items(), key=lambda x: x[1], reverse=True)
        legacy_top1 = legacy_sorted[0][0] if legacy_sorted else None
        
        # Get top-1 from new
        new_sorted = sorted(s.new_values.items(), key=lambda x: x[1], reverse=True)
        new_top1 = new_sorted[0][0] if new_sorted else None
        
        # Map legacy to new
        mapping = {
            "energy": "stability",
            "uncertainty": "coherence",
            "social": "completion",
            "safety": "verification",
            "fatigue": "repair",
        }
        
        if legacy_top1 and new_top1:
            expected_new = mapping.get(legacy_top1, legacy_top1)
            if expected_new == new_top1:
                top1_matches += 1
    
    stats.top1_agreement_rate = top1_matches / len(samples)
    
    # High-risk fields average diff
    stats.high_risk_fields = ["energy->stability", "safety->verification"]
    high_risk_diffs = []
    for field in stats.high_risk_fields:
        if field in stats.avg_field_diffs:
            high_risk_diffs.append(stats.avg_field_diffs[field])
    stats.high_risk_avg_diff = sum(high_risk_diffs) / len(high_risk_diffs) if high_risk_diffs else 0.0
    
    return stats


def run_diff_analysis(num_samples: int = 100) -> DiffStats:
    """Run diff analysis with specified number of samples."""
    print(f"=== MVP14 Runtime Diff Analysis ===")
    print(f"Collecting {num_samples} samples...")
    
    samples = []
    for i in range(num_samples):
        sample = collect_diff_sample()
        samples.append(sample)
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{num_samples}")
    
    stats = compute_diff_stats(samples)
    
    print(f"\n=== Results ===")
    print(f"Total samples: {stats.total_samples}")
    print(f"\nField Diff Rates (>0.1):")
    for field, rate in stats.field_diff_rates.items():
        status = "⚠️ HIGH" if rate > 0.5 else "✅ OK"
        print(f"  {field}: {rate:.2%} {status}")
    
    print(f"\nAvg Field Diffs:")
    for field, diff in stats.avg_field_diffs.items():
        print(f"  {field}: {diff:.3f}")
    
    print(f"\n=== Decision Drift Metrics ===")
    print(f"Rank Change Rate: {stats.rank_change_rate:.2%}")
    print(f"Top-1 Agreement Rate: {stats.top1_agreement_rate:.2%}")
    print(f"High-Risk Avg Diff: {stats.high_risk_avg_diff:.3f}")
    
    print(f"\nTop Diff Patterns:")
    for p in stats.top_patterns:
        print(f"  {p['pattern']}: {p['count']} ({p['rate']:.2%})")
    
    # Cutover readiness assessment
    print(f"\n=== Cutover Readiness ===")
    ready = True
    if stats.rank_change_rate > 0.1:
        print(f"  ❌ Rank Change Rate: {stats.rank_change_rate:.2%} > 10% threshold")
        ready = False
    else:
        print(f"  ✅ Rank Change Rate: {stats.rank_change_rate:.2%} <= 10% threshold")
    
    if stats.top1_agreement_rate < 0.9:
        print(f"  ❌ Top-1 Agreement: {stats.top1_agreement_rate:.2%} < 90% threshold")
        ready = False
    else:
        print(f"  ✅ Top-1 Agreement: {stats.top1_agreement_rate:.2%} >= 90% threshold")
    
    if stats.high_risk_avg_diff > 0.05:
        print(f"  ❌ High-Risk Diff: {stats.high_risk_avg_diff:.3f} > 0.05 threshold")
        ready = False
    else:
        print(f"  ✅ High-Risk Diff: {stats.high_risk_avg_diff:.3f} <= 0.05 threshold")
    
    if ready:
        print(f"\n✅ CUTOVER READY")
    else:
        print(f"\n❌ CUTOVER NOT READY")
    
    return stats


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--output", type=str, default="artifacts/mvp14/runtime_diff_stats.json")
    args = parser.parse_args()
    
    stats = run_diff_analysis(args.samples)
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump({
            "total_samples": stats.total_samples,
            "field_diff_rates": stats.field_diff_rates,
            "avg_field_diffs": stats.avg_field_diffs,
            "param_diff_rates": stats.param_diff_rates,
            "avg_param_diffs": stats.avg_param_diffs,
            "rank_change_rate": stats.rank_change_rate,
            "top_patterns": stats.top_patterns,
        }, f, indent=2)
    
    print(f"\nResults saved to {output_path}")
