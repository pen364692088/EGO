#!/usr/bin/env python3
"""MVP11.4.7 P1: Threshold Calibration with Versioning and Freeze.

Analyzes historical nightly summary data to recommend calibrated thresholds
for MVP11 hard gates and soft warnings.

Features:
- Default output to artifacts/mvp11/gates/thresholds.latest.json
- --freeze: Create timestamped frozen copy for archival
- --refresh: Force regeneration even if frozen exists
- Metadata: commit, confidence, source_window_days

Calibrates:
- Hard gates: replay_hash_match, sanity_consecutive, concentration_consecutive, bias_consecutive
- Soft thresholds: sanity_ok_rate_min, concentration thresholds, bias thresholds
- Gate parameters: max_governor_delta, max_drift_delta, consecutive_days

Usage:
    # Normal run - creates thresholds.latest.json
    python scripts/calibrate_mvp11_thresholds.py

    # Freeze current thresholds
    python scripts/calibrate_mvp11_thresholds.py --freeze

    # Force refresh
    python scripts/calibrate_mvp11_thresholds.py --refresh

    # Custom paths
    python scripts/calibrate_mvp11_thresholds.py \
        --nightly-dir artifacts/mvp11/nightly \
        --trends-dir artifacts/mvp11/trends \
        --out artifacts/mvp11/gates/thresholds.latest.json

Output:
    - thresholds.latest.json: Current active thresholds (with metadata)
    - thresholds.YYYYMMDDTHHMMSSZ.json: Frozen snapshots (when --freeze)
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Current hardcoded thresholds (from mvp11_hard_gate_eval.py, cycle_gate_mvp11.py, etc.)
CURRENT_THRESHOLDS = {
    "hard_gates": {
        "replay_hash_match_rate": {"current": 1.0, "description": "Replay hash match must be 100%"},
        "sanity_consecutive_days": {"current": 2, "description": "Max consecutive days with sanity != OK"},
        "concentration_top1_threshold": {"current": 0.55, "description": "phi_top1_share warning threshold"},
        "concentration_consecutive_days": {"current": 2, "description": "Max consecutive days with high concentration"},
        "bias_p95_threshold": {"current": 0.12, "description": "0.8 * MAX_BIAS (0.15)"},
        "bias_consecutive_days": {"current": 2, "description": "Max consecutive days with high bias"},
    },
    "soft_thresholds": {
        "sanity_ok_rate_min": {"current": 0.99, "description": "Minimum sanity OK coverage rate"},
        "concentration_hhi_threshold": {"current": 0.25, "description": "HHI warning threshold"},
        "concentration_top1_warn": {"current": 0.55, "description": "Top1 share warning (light mode)"},
        "bias_max": {"current": 0.15, "description": "MAX_BIAS for cycle prior"},
        "bias_near_cap_rate": {"current": 0.05, "description": "Near cap rate warning"},
        "drift_alert_threshold": {"current": 0.2, "description": "Drift score alert threshold"},
    },
    "gate_params": {
        "max_governor_delta": {"current": 0.01, "description": "Gate-3 max governor block rate delta"},
        "max_drift_delta": {"current": 0.01, "description": "Gate-3 max homeostasis drift delta"},
        "min_sanity_ok_rate": {"current": 0.99, "description": "Gate-1 minimum sanity OK rate"},
    },
    "cycle_graph": {
        "max_nodes": {"current": 10000, "description": "Max cycle graph nodes"},
        "max_edges": {"current": 50000, "description": "Max cycle graph edges"},
    },
}

# Minimum samples for calibration confidence
MIN_SAMPLES_LOW = 3
MIN_SAMPLES_MEDIUM = 7
MIN_SAMPLES_HIGH = 14


def get_git_commit(repo_path: Path) -> Optional[str]:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass
    return None


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file if exists."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def load_nightly_summaries(nightly_dir: Path) -> List[Dict[str, Any]]:
    """Load all nightly summary JSON files."""
    summaries = []
    for p in nightly_dir.rglob("nightly_summary.json"):
        data = load_json(p)
        if data:
            data["_source"] = str(p)
            summaries.append(data)
    summaries.sort(key=lambda x: x.get("date", ""), reverse=True)
    return summaries


def load_trend_entries(trends_dir: Path) -> List[Dict[str, Any]]:
    """Load trend entries from trends directory."""
    entries = []
    trend_7d = load_json(trends_dir / "trend_7d.json")
    if trend_7d and trend_7d.get("entries"):
        entries.extend(trend_7d["entries"])
    for p in trends_dir.glob("trend_entry_*.json"):
        data = load_json(p)
        if data:
            entries.append(data)
    current = load_json(trends_dir / "trend_entry.json")
    if current:
        entries.append(current)
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: x.get("date_utc", ""), reverse=True):
        date = e.get("date_utc")
        if date and date not in seen:
            seen.add(date)
            unique.append(e)
    return unique


def extract_metrics_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant metrics from a nightly summary."""
    metrics = {}
    eval_data = summary.get("eval", {})
    quick = eval_data.get("quick", {})
    science = eval_data.get("science", {})
    replay = eval_data.get("replay", {})
    sanity_ok = quick.get("sanity")
    metrics["sanity_ok_coverage"] = 1.0 if sanity_ok == "OK" else (0.0 if sanity_ok else None)
    metrics["science_sanity"] = 1.0 if science.get("sanity") == "OK" else (0.0 if science.get("sanity") else None)
    metrics["replay_hash_match_rate"] = replay.get("hash_match_rate")
    prior = summary.get("prior", {})
    metrics["bias_p95"] = prior.get("bias_strength_p95")
    metrics["bias_mean"] = prior.get("bias_strength_mean")
    metrics["near_cap_rate"] = prior.get("near_cap_rate")
    metrics["prior_enabled"] = prior.get("enabled", False)
    conc = summary.get("concentration", {})
    metrics["phi_top1_share"] = conc.get("phi_top1_share")
    metrics["phi_top3_share"] = conc.get("phi_top3_share")
    metrics["phi_hhi"] = conc.get("phi_hhi")
    cycle_graph = summary.get("cycle_graph", {})
    metrics["cycle_graph_nodes"] = cycle_graph.get("nodes")
    metrics["cycle_graph_edges"] = cycle_graph.get("edges")
    cycle = summary.get("cycle", {})
    metrics["cycle_store_count"] = cycle.get("cycle_store_count")
    metrics["date"] = summary.get("date")
    return metrics


def extract_metrics_from_trend(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant metrics from a trend entry."""
    metrics = {}
    metrics["date"] = entry.get("date_utc")
    gate = entry.get("gate", {})
    metrics["gate_overall"] = gate.get("overall")
    metrics["gate1"] = gate.get("gate1")
    metrics["gate2"] = gate.get("gate2")
    metrics["gate3"] = gate.get("gate3")
    m = entry.get("metrics", {})
    metrics["sanity_ok_coverage"] = m.get("sanity_ok_coverage")
    cps = m.get("cycle_persistence_score", {})
    metrics["cycle_persistence_p50"] = cps.get("p50")
    metrics["cycle_persistence_p95"] = cps.get("p95")
    dot = m.get("dot_ratio", {})
    metrics["dot_ratio_p50"] = dot.get("p50")
    metrics["dot_ratio_p95"] = dot.get("p95")
    metrics["return_time_p95"] = m.get("return_time_p95")
    prior = entry.get("prior", {})
    metrics["bias_p95"] = prior.get("bias_p95")
    metrics["bias_mean"] = prior.get("bias_mean") if "bias_mean" in prior else prior.get("bias_p95")
    metrics["near_cap_rate"] = prior.get("near_cap_rate")
    metrics["prior_enabled"] = prior.get("enabled", False)
    conc = entry.get("concentration", {})
    metrics["phi_top1_share"] = conc.get("phi_top1_share")
    metrics["phi_top3_share"] = conc.get("phi_top3_share")
    metrics["phi_hhi"] = conc.get("phi_hhi")
    cg = entry.get("cycle_graph", {})
    metrics["cycle_graph_nodes"] = cg.get("nodes")
    metrics["cycle_graph_edges"] = cg.get("edges")
    cm = entry.get("cycle_memory", {})
    metrics["cycle_store_count"] = cm.get("count")
    return metrics


def compute_stats(values: List[float]) -> Dict[str, float]:
    """Compute basic statistics for a list of values."""
    if not values:
        return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "p5": 0.0, "p50": 0.0, "p95": 0.0}
    n = len(values)
    sorted_vals = sorted(values)
    mean = sum(values) / n
    if n > 1:
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    else:
        std = 0.0
    def percentile(p: float) -> float:
        if n == 1:
            return values[0]
        idx = (n - 1) * p / 100.0
        lower = int(idx)
        upper = lower + 1
        if upper >= n:
            return sorted_vals[-1]
        weight = idx - lower
        return sorted_vals[lower] * (1 - weight) + sorted_vals[upper] * weight
    return {
        "count": n,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "min": sorted_vals[0],
        "max": sorted_vals[-1],
        "p5": round(percentile(5), 6),
        "p50": round(percentile(50), 6),
        "p95": round(percentile(95), 6),
        "p99": round(percentile(99), 6),
    }


def compute_consecutive_pattern(values: List[Optional[bool]], threshold_days: int = 2) -> Dict[str, Any]:
    """Analyze consecutive pattern for binary values."""
    if not values:
        return {"max_consecutive_true": 0, "max_consecutive_false": 0, "violation_count": 0, "total_days": 0}
    max_true = 0
    max_false = 0
    current_true = 0
    current_false = 0
    violations = 0
    for v in values:
        if v is None:
            current_true = 0
            current_false = 0
        elif v:
            current_true += 1
            current_false = 0
            max_true = max(max_true, current_true)
        else:
            current_false += 1
            current_true = 0
            max_false = max(max_false, current_false)
            if current_false == threshold_days:
                violations += 1
    return {
        "max_consecutive_true": max_true,
        "max_consecutive_false": max_false,
        "violation_count": violations,
        "total_days": len([v for v in values if v is not None]),
    }


def calibrate_threshold_from_distribution(
    stats: Dict[str, float],
    current: float,
    threshold_type: str = "upper",
    safety_margin: float = 0.1,
) -> Dict[str, Any]:
    """Calibrate a threshold based on distribution statistics."""
    n = stats["count"]
    if n < MIN_SAMPLES_LOW:
        confidence = "insufficient"
    elif n < MIN_SAMPLES_MEDIUM:
        confidence = "low"
    elif n < MIN_SAMPLES_HIGH:
        confidence = "medium"
    else:
        confidence = "high"
    if confidence == "insufficient":
        return {
            "recommended": current,
            "rationale": f"Insufficient data ({n} samples), keeping current threshold",
            "confidence": confidence,
            "sample_count": n,
        }
    mean = stats["mean"]
    std = stats["std"]
    p5 = stats["p5"]
    p95 = stats["p95"]
    if threshold_type == "upper":
        if std > 0 and abs(mean - stats["p50"]) < std:
            candidate = mean + 2 * std
        else:
            candidate = p95
        margin = safety_margin * abs(candidate) if candidate != 0 else safety_margin
        recommended = round(candidate + margin, 6)
        if recommended > current and current > p95:
            recommended = current
            rationale = f"Current threshold ({current}) already covers p95 ({p95}), no change needed"
        else:
            rationale = f"Based on mean={mean:.4f}, std={std:.4f}, p95={p95:.4f}; added {safety_margin*100}% margin"
    elif threshold_type == "lower":
        if std > 0 and abs(mean - stats["p50"]) < std:
            candidate = mean - 2 * std
        else:
            candidate = p5
        margin = safety_margin * abs(candidate) if candidate != 0 else safety_margin
        recommended = round(candidate - margin, 6)
        if recommended < current and current < p5:
            recommended = current
            rationale = f"Current threshold ({current}) already covers p5 ({p5}), no change needed"
        else:
            rationale = f"Based on mean={mean:.4f}, std={std:.4f}, p5={p5:.4f}; added {safety_margin*100}% margin"
    else:
        recommended = current
        rationale = "Exact threshold, calibration not applicable"
    return {
        "recommended": recommended,
        "rationale": rationale,
        "confidence": confidence,
        "sample_count": n,
        "stats": stats,
    }


def calibrate_consecutive_days(
    pattern: Dict[str, Any],
    current: int,
    min_days: int = 2,
    max_days: int = 5,
) -> Dict[str, Any]:
    """Calibrate consecutive days threshold based on observed pattern."""
    total_days = pattern["total_days"]
    max_consecutive = pattern["max_consecutive_false"]
    violations = pattern["violation_count"]
    if total_days < MIN_SAMPLES_LOW:
        return {
            "recommended": current,
            "rationale": f"Insufficient data ({total_days} days)",
            "confidence": "insufficient",
        }
    if violations == 0 and max_consecutive < current:
        confidence = "medium" if total_days >= MIN_SAMPLES_MEDIUM else "low"
        return {
            "recommended": current,
            "rationale": f"No violations observed (max consecutive = {max_consecutive}), threshold is safe",
            "confidence": confidence,
        }
    if violations > 0:
        recommended = min(current + 1, max_days)
        confidence = "medium" if total_days >= MIN_SAMPLES_MEDIUM else "low"
        return {
            "recommended": recommended,
            "rationale": f"{violations} violation(s) observed with threshold={current}; consider increasing",
            "confidence": confidence,
        }
    if max_consecutive >= current - 1:
        confidence = "medium" if total_days >= MIN_SAMPLES_MEDIUM else "low"
        return {
            "recommended": current,
            "rationale": f"Max consecutive failures ({max_consecutive}) close to threshold ({current})",
            "confidence": confidence,
        }
    return {
        "recommended": current,
        "rationale": "Threshold is appropriate",
        "confidence": "high",
    }


def analyze_all_metrics(
    summaries: List[Dict[str, Any]],
    trend_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze all metrics from loaded data."""
    all_metrics: List[Dict[str, Any]] = []
    for s in summaries:
        m = extract_metrics_from_summary(s)
        m["_source_type"] = "nightly_summary"
        all_metrics.append(m)
    for e in trend_entries:
        m = extract_metrics_from_trend(e)
        m["_source_type"] = "trend_entry"
        all_metrics.append(m)
    numeric_values: Dict[str, List[float]] = defaultdict(list)
    binary_values: Dict[str, List[Optional[bool]]] = defaultdict(list)
    for m in all_metrics:
        for key in [
            "sanity_ok_coverage",
            "replay_hash_match_rate",
            "bias_p95", "bias_mean", "near_cap_rate",
            "phi_top1_share", "phi_top3_share", "phi_hhi",
            "cycle_graph_nodes", "cycle_graph_edges",
            "cycle_store_count",
            "cycle_persistence_p50", "cycle_persistence_p95",
            "dot_ratio_p50", "dot_ratio_p95",
            "return_time_p95",
        ]:
            val = m.get(key)
            if val is not None and isinstance(val, (int, float)):
                numeric_values[key].append(float(val))
        for key in ["gate_overall", "gate1", "gate2", "gate3"]:
            val = m.get(key)
            if val is not None:
                binary_values[key].append(val == "PASS")
        if m.get("sanity_ok_coverage") is not None:
            binary_values["sanity_ok"].append(m["sanity_ok_coverage"] >= 0.99)
    analysis = {
        "numeric_stats": {},
        "binary_patterns": {},
        "sample_counts": {
            "total_entries": len(all_metrics),
            "nightly_summaries": len(summaries),
            "trend_entries": len(trend_entries),
        },
    }
    for key, values in numeric_values.items():
        analysis["numeric_stats"][key] = compute_stats(values)
    for key, values in binary_values.items():
        analysis["binary_patterns"][key] = compute_consecutive_pattern(values)
    return analysis


def generate_calibrations(
    analysis: Dict[str, Any],
    current_thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate calibration recommendations."""
    calibrations = {
        "hard_gates": {},
        "soft_thresholds": {},
        "gate_params": {},
        "cycle_graph": {},
    }
    numeric_stats = analysis["numeric_stats"]
    binary_patterns = analysis["binary_patterns"]
    
    # Hard gates
    if "replay_hash_match_rate" in numeric_stats:
        stats = numeric_stats["replay_hash_match_rate"]
        current = current_thresholds["hard_gates"]["replay_hash_match_rate"]["current"]
        if stats["min"] < 1.0:
            calibrations["hard_gates"]["replay_hash_match_rate"] = {
                "current": current,
                "recommended": 1.0,
                "rationale": f"Observed values < 1.0 (min={stats['min']}), threshold must remain 1.0",
                "confidence": "high",
                "status": "CRITICAL",
            }
        else:
            calibrations["hard_gates"]["replay_hash_match_rate"] = {
                "current": current,
                "recommended": current,
                "rationale": "All observed values = 1.0, threshold is correct",
                "confidence": "high",
                "status": "OK",
            }
    
    if "sanity_ok" in binary_patterns:
        pattern = binary_patterns["sanity_ok"]
        current = current_thresholds["hard_gates"]["sanity_consecutive_days"]["current"]
        cal = calibrate_consecutive_days(pattern, current)
        calibrations["hard_gates"]["sanity_consecutive_days"] = {
            "current": current,
            "recommended": cal["recommended"],
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
        }
    
    if "phi_top1_share" in numeric_stats:
        stats = numeric_stats["phi_top1_share"]
        current = current_thresholds["hard_gates"]["concentration_top1_threshold"]["current"]
        cal = calibrate_threshold_from_distribution(stats, current, threshold_type="upper")
        calibrations["hard_gates"]["concentration_top1_threshold"] = {
            "current": current,
            "recommended": cal["recommended"],
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
            "stats": stats,
        }
    
    if "bias_p95" in numeric_stats:
        stats = numeric_stats["bias_p95"]
        current = current_thresholds["hard_gates"]["bias_p95_threshold"]["current"]
        cal = calibrate_threshold_from_distribution(stats, current, threshold_type="upper")
        max_safe = current_thresholds["soft_thresholds"]["bias_max"]["current"] * 0.8
        if cal["recommended"] > max_safe:
            cal["recommended"] = round(max_safe, 6)
            cal["rationale"] += f" (capped at 0.8 * MAX_BIAS = {max_safe})"
        calibrations["hard_gates"]["bias_p95_threshold"] = {
            "current": current,
            "recommended": cal["recommended"],
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
            "stats": stats,
        }
    
    # Soft thresholds
    if "phi_hhi" in numeric_stats:
        stats = numeric_stats["phi_hhi"]
        current = current_thresholds["soft_thresholds"]["concentration_hhi_threshold"]["current"]
        cal = calibrate_threshold_from_distribution(stats, current, threshold_type="upper")
        calibrations["soft_thresholds"]["concentration_hhi_threshold"] = {
            "current": current,
            "recommended": cal["recommended"],
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
            "stats": stats,
        }
    
    # Default for missing data
    for key in ["sanity_ok_rate_min", "drift_alert_threshold", "bias_near_cap_rate"]:
        if key not in calibrations["soft_thresholds"]:
            calibrations["soft_thresholds"][key] = {
                "current": current_thresholds["soft_thresholds"][key]["current"],
                "recommended": current_thresholds["soft_thresholds"][key]["current"],
                "rationale": "Insufficient data for calibration",
                "confidence": "insufficient",
                "status": "NO_DATA",
            }
    
    # Gate params - require A/B data
    for key in ["max_governor_delta", "max_drift_delta", "min_sanity_ok_rate"]:
        calibrations["gate_params"][key] = {
            "current": current_thresholds["gate_params"][key]["current"],
            "recommended": current_thresholds["gate_params"][key]["current"],
            "rationale": "A/B report data required for calibration",
            "confidence": "insufficient",
            "status": "NO_DATA",
        }
    
    # Cycle graph
    if "cycle_graph_nodes" in numeric_stats:
        stats = numeric_stats["cycle_graph_nodes"]
        current = current_thresholds["cycle_graph"]["max_nodes"]["current"]
        cal = calibrate_threshold_from_distribution(stats, current, threshold_type="upper")
        calibrations["cycle_graph"]["max_nodes"] = {
            "current": current,
            "recommended": int(cal["recommended"]) if cal["recommended"] != current else current,
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
            "stats": stats,
        }
    
    if "cycle_graph_edges" in numeric_stats:
        stats = numeric_stats["cycle_graph_edges"]
        current = current_thresholds["cycle_graph"]["max_edges"]["current"]
        cal = calibrate_threshold_from_distribution(stats, current, threshold_type="upper")
        calibrations["cycle_graph"]["max_edges"] = {
            "current": current,
            "recommended": int(cal["recommended"]) if cal["recommended"] != current else current,
            "rationale": cal["rationale"],
            "confidence": cal["confidence"],
            "status": "OK" if cal["recommended"] == current else "REVIEW",
            "stats": stats,
        }
    
    return calibrations


def compute_overall_confidence(calibrations: Dict[str, Any]) -> str:
    """Compute overall confidence from calibration results."""
    confidence_counts = {"high": 0, "medium": 0, "low": 0, "insufficient": 0}
    for category in calibrations.values():
        for item in category.values():
            conf = item.get("confidence", "insufficient")
            if conf in confidence_counts:
                confidence_counts[conf] += 1
    total = sum(confidence_counts.values())
    if total == 0:
        return "insufficient"
    score = (
        confidence_counts["high"] * 3 +
        confidence_counts["medium"] * 2 +
        confidence_counts["low"] * 1
    ) / total
    if score >= 2.5:
        return "high"
    elif score >= 1.5:
        return "medium"
    elif score >= 0.5:
        return "low"
    else:
        return "insufficient"


def render_markdown_report(
    calibrations: Dict[str, Any],
    analysis: Dict[str, Any],
    current_thresholds: Dict[str, Any],
    metadata: Dict[str, Any],
) -> str:
    """Render calibration report as markdown."""
    lines = [
        "# MVP11.4.7 Threshold Calibration Report",
        "",
        f"**Generated**: {metadata.get('generated_at', 'N/A')}",
        f"**Commit**: {metadata.get('commit', 'N/A')}",
        f"**Confidence**: {metadata.get('confidence', 'N/A')}",
        f"**Source Window**: {metadata.get('source_window_days', 'N/A')} days",
        f"**Frozen**: {metadata.get('frozen_at', 'No')}",
        "",
        f"**Total Entries Analyzed**: {analysis['sample_counts']['total_entries']}",
        f"**Nightly Summaries**: {analysis['sample_counts']['nightly_summaries']}",
        f"**Trend Entries**: {analysis['sample_counts']['trend_entries']}",
        "",
    ]
    
    review_count = sum(
        1 for cat in calibrations.values()
        for item in cat.values()
        if item.get("status") == "REVIEW"
    )
    no_data_count = sum(
        1 for cat in calibrations.values()
        for item in cat.values()
        if item.get("status") == "NO_DATA"
    )
    
    lines.extend([
        "## Summary",
        "",
        f"- **Thresholds to Review**: {review_count}",
        f"- **Insufficient Data**: {no_data_count}",
        "",
    ])
    
    # Hard Gates table
    lines.extend([
        "## Hard Gates",
        "",
        "| Threshold | Current | Recommended | Status | Confidence |",
        "|-----------|---------|-------------|--------|------------|",
    ])
    for key, item in calibrations.get("hard_gates", {}).items():
        status_icon = "OK" if item.get("status") == "OK" else ("REVIEW" if item.get("status") == "REVIEW" else "CRITICAL")
        lines.append(f"| {key} | {item.get('current')} | {item.get('recommended')} | {status_icon} | {item.get('confidence', 'unknown')} |")
    lines.append("")
    
    # Soft Thresholds table
    lines.extend([
        "## Soft Thresholds",
        "",
        "| Threshold | Current | Recommended | Status | Confidence |",
        "|-----------|---------|-------------|--------|------------|",
    ])
    for key, item in calibrations.get("soft_thresholds", {}).items():
        status_icon = "OK" if item.get("status") == "OK" else ("REVIEW" if item.get("status") == "REVIEW" else "NO_DATA")
        lines.append(f"| {key} | {item.get('current')} | {item.get('recommended')} | {status_icon} | {item.get('confidence', 'unknown')} |")
    lines.append("")
    
    # Gate Parameters table
    lines.extend([
        "## Gate Parameters",
        "",
        "| Parameter | Current | Recommended | Status |",
        "|-----------|---------|-------------|--------|",
    ])
    for key, item in calibrations.get("gate_params", {}).items():
        lines.append(f"| {key} | {item.get('current')} | {item.get('recommended')} | {item.get('status', 'unknown')} |")
    lines.append("")
    
    # Cycle Graph table
    lines.extend([
        "## Cycle Graph Limits",
        "",
        "| Limit | Current | Recommended | Status |",
        "|-------|---------|-------------|--------|",
    ])
    for key, item in calibrations.get("cycle_graph", {}).items():
        lines.append(f"| {key} | {item.get('current')} | {item.get('recommended')} | {item.get('status', 'unknown')} |")
    lines.append("")
    
    # Rationale for REVIEW items
    lines.extend(["## Rationale for Reviews", ""])
    for category in ["hard_gates", "soft_thresholds", "cycle_graph"]:
        for key, item in calibrations.get(category, {}).items():
            if item.get("status") == "REVIEW":
                lines.append(f"### {key}")
                lines.append("")
                lines.append(f"- **Current**: `{item.get('current')}`")
                lines.append(f"- **Recommended**: `{item.get('recommended')}`")
                lines.append(f"- **Rationale**: {item.get('rationale', 'N/A')}")
                if item.get("stats"):
                    stats = item["stats"]
                    lines.append(f"- **Stats**: mean={stats.get('mean'):.4f}, std={stats.get('std'):.4f}, p95={stats.get('p95'):.4f}, n={stats.get('count')}")
                lines.append("")
    
    # Observed Statistics
    lines.extend(["## Observed Statistics", ""])
    for key, stats in analysis.get("numeric_stats", {}).items():
        if stats.get("count", 0) > 0:
            lines.append(f"### {key}")
            lines.append("")
            lines.append(f"- n: {stats['count']}, mean: {stats['mean']:.4f}, std: {stats['std']:.4f}")
            lines.append(f"- min: {stats['min']:.4f}, max: {stats['max']:.4f}")
            lines.append(f"- p5: {stats['p5']:.4f}, p50: {stats['p50']:.4f}, p95: {stats['p95']:.4f}")
            lines.append("")
    
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="MVP11.4.7 P1: Threshold Calibration with Versioning")
    ap.add_argument("--nightly-dir", default="artifacts/mvp11/nightly", help="Directory containing nightly summaries")
    ap.add_argument("--trends-dir", default="artifacts/mvp11/trends", help="Directory containing trend entries")
    ap.add_argument("--out", default="artifacts/mvp11/gates/thresholds.latest.json", help="Output JSON path (default: artifacts/mvp11/gates/thresholds.latest.json)")
    ap.add_argument("--out-md", default=None, help="Output markdown path (default: same dir as --out with .md extension)")
    ap.add_argument("--window-days", type=int, default=30, help="Max days to analyze")
    ap.add_argument("--freeze", action="store_true", help="Create a frozen timestamped copy alongside the latest")
    ap.add_argument("--refresh", action="store_true", help="Force regeneration even if frozen exists")
    args = ap.parse_args()
    
    # Determine project root (assumed to be parent of scripts/)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    
    nightly_dir = project_root / args.nightly_dir
    trends_dir = project_root / args.trends_dir
    
    # Default output paths
    out_json = project_root / args.out
    if args.out_md:
        out_md = project_root / args.out_md
    else:
        out_md = out_json.with_suffix(".md")
    
    # Check if frozen file exists and --refresh not set
    if args.freeze and not args.refresh:
        gates_dir = out_json.parent
        frozen_pattern = "thresholds.*Z.json"
        existing_frozen = list(gates_dir.glob(frozen_pattern)) if gates_dir.exists() else []
        if existing_frozen:
            latest_frozen = sorted(existing_frozen)[-1]
            print(f"[INFO] Frozen threshold file exists: {latest_frozen}", flush=True)
            print(f"[INFO] Use --refresh to regenerate", flush=True)
    
    print(f"[INFO] Loading nightly summaries from {nightly_dir}", flush=True)
    summaries = load_nightly_summaries(nightly_dir)
    print(f"[INFO] Loaded {len(summaries)} nightly summaries", flush=True)
    
    print(f"[INFO] Loading trend entries from {trends_dir}", flush=True)
    trend_entries = load_trend_entries(trends_dir)
    print(f"[INFO] Loaded {len(trend_entries)} trend entries", flush=True)
    
    # Limit to window
    actual_window = min(len(summaries), args.window_days) if args.window_days > 0 else len(summaries)
    if args.window_days > 0:
        summaries = summaries[:args.window_days]
        trend_entries = trend_entries[:args.window_days]
    
    print("[INFO] Analyzing metrics...", flush=True)
    analysis = analyze_all_metrics(summaries, trend_entries)
    
    print("[INFO] Generating calibrations...", flush=True)
    calibrations = generate_calibrations(analysis, CURRENT_THRESHOLDS)
    
    # Compute overall confidence
    overall_confidence = compute_overall_confidence(calibrations)
    
    # Get git commit
    commit = get_git_commit(project_root)
    
    # Build metadata
    now_utc = datetime.now(timezone.utc)
    metadata = {
        "schema_version": "mvp11.threshold_calibration.v2",
        "generated_at": now_utc.isoformat(),
        "commit": commit,
        "confidence": overall_confidence,
        "source_window_days": actual_window,
        "frozen_at": None,
    }
    
    # Build output
    output = {
        "metadata": metadata,
        "sample_counts": analysis["sample_counts"],
        "current_thresholds": CURRENT_THRESHOLDS,
        "calibrations": calibrations,
        "numeric_stats": analysis["numeric_stats"],
        "binary_patterns": analysis["binary_patterns"],
    }
    
    # Ensure output directory exists
    out_json.parent.mkdir(parents=True, exist_ok=True)
    
    # Write main output (thresholds.latest.json)
    out_json.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] JSON output: {out_json}", flush=True)
    
    # Handle --freeze flag
    frozen_path = None
    if args.freeze:
        frozen_ts = now_utc.strftime("%Y%m%dT%H%M%SZ")
        frozen_filename = f"thresholds.{frozen_ts}.json"
        frozen_path = out_json.parent / frozen_filename
        
        # Update metadata for frozen copy
        frozen_metadata = metadata.copy()
        frozen_metadata["frozen_at"] = now_utc.isoformat()
        
        frozen_output = output.copy()
        frozen_output["metadata"] = frozen_metadata
        
        frozen_path.write_text(json.dumps(frozen_output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] Frozen output: {frozen_path}", flush=True)
    
    # Write Markdown
    md_metadata = metadata.copy()
    if frozen_path:
        md_metadata["frozen_at"] = frozen_path.name
    md_content = render_markdown_report(calibrations, analysis, CURRENT_THRESHOLDS, md_metadata)
    out_md.write_text(md_content, encoding="utf-8")
    print(f"[INFO] Markdown output: {out_md}", flush=True)
    
    # Print summary
    review_count = sum(1 for cat in calibrations.values() for item in cat.values() if item.get("status") == "REVIEW")
    result = {
        "output_json": str(out_json),
        "output_md": str(out_md),
        "total_entries": analysis["sample_counts"]["total_entries"],
        "thresholds_to_review": review_count,
        "confidence": overall_confidence,
        "commit": commit,
        "source_window_days": actual_window,
    }
    if frozen_path:
        result["frozen_json"] = str(frozen_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
