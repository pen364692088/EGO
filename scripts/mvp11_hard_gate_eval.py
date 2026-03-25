#!/usr/bin/env python3
"""MVP11 Hard Gate Evaluator - Two-Phase Deployment.

Phase 1 (Shadow): Calculate should_fail, write report, but don't fail CI.
Phase 2 (Enforced): Exit with non-zero when should_fail=true.

Hard Gate Conditions:
- replay hash_match_rate < 1.0 → FAIL (immediate)
- sanity != OK for 2+ consecutive days → FAIL
- phi_top1_share > 0.55 for 2+ consecutive days → FAIL
- bias_p95 > 0.8*MAX_BIAS for 2+ consecutive days → FAIL

MVP11.4.6 P2: Supports calibrated thresholds from calibrate_mvp11_thresholds.py.
Thresholds can be loaded from JSON with --thresholds parameter.

MVP11.4.8 P1: Enhanced for Shadow Mode
- --out: Write simplified summary JSON (gate status only)
- --shadow-soft-fail: In shadow mode, exit 0 even if should_fail=true
- Enhanced stdout output with gate-level details

MVP11.4.9: One-liner output for CI/monitoring
- --out-one-liner: Write single-line summary in key=value format

Usage:
    # Shadow mode (default) with summary JSON
    python scripts/mvp11_hard_gate_eval.py \
        --trend-dir artifacts/mvp11/trends \
        --window-days 7 \
        --out artifacts/mvp11/profiles/hard_gate_summary.json

    # Shadow mode with soft-fail (monitoring without blocking CI)
    python scripts/mvp11_hard_gate_eval.py \
        --trend-dir artifacts/mvp11/trends \
        --out artifacts/mvp11/profiles/hard_gate_summary.json \
        --shadow-soft-fail

    # With calibrated thresholds
    python scripts/mvp11_hard_gate_eval.py \
        --thresholds reports/mvp11_threshold_calibration.json \
        --trend-dir artifacts/mvp11/trends

    # Enforced mode (Phase 2)
    HARD_GATE_ENFORCE=1 python scripts/mvp11_hard_gate_eval.py ...
    # Or:
    python scripts/mvp11_hard_gate_eval.py --enforce ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# Default hardcoded thresholds (fallback when --thresholds not provided or missing keys)
DEFAULT_THRESHOLDS = {
    "replay_hash_match_rate": 1.0,
    "sanity_consecutive_days": 2,
    "concentration_top1_threshold": 0.55,
    "concentration_consecutive_days": 2,
    "bias_p95_threshold": 0.12,  # 0.8 * MAX_BIAS (0.15)
    "bias_consecutive_days": 2,
}

MAX_BIAS = 0.15

# Default testbot thresholds (Shadow mode)
DEFAULT_TESTBOT_THRESHOLDS = {
    "phi_top1_share_max": 0.6,
    "unique_signatures_min": 5,
}


def load_testbot_metrics(
    report_path: str = "artifacts/testbot/concentration_report.json",
) -> Dict[str, Any]:
    """Load concentration_report.json and extract key metrics.
    
    Args:
        report_path: Path to testbot concentration report JSON
        
    Returns:
        Dict with:
        - loaded: bool (whether report was found and parsed)
        - tape_hash_match: bool (True if all scenarios have replay_hash_match=True)
        - phi_top1_share: float (average top1 share across scenarios)
        - unique_signatures: int (total unique signatures)
        - scenarios_count: int (number of scenarios)
        - scenarios_failed: int (number of failed scenarios)
        - scenarios: List of scenario results (name, status, hash_match)
        - error: str (error message if load failed)
    """
    result = {
        "loaded": False,
        "tape_hash_match": True,
        "phi_top1_share": None,
        "unique_signatures": None,
        "scenarios_count": 0,
        "scenarios_failed": 0,
        "scenarios": [],
        "error": None,
    }
    
    path = Path(report_path)
    if not path.exists():
        result["error"] = f"Report not found: {report_path}"
        return result
    
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        result["error"] = f"Failed to parse report: {e}"
        return result
    
    # Extract metrics
    results = data.get("results", [])
    result["scenarios_count"] = len(results)
    
    # Check tape hash match for all scenarios
    all_hash_match = True
    failed_count = 0
    scenarios_list = []
    for r in results:
        scenario_name = r.get("scenario", r.get("name", "unknown"))
        scenario_status = r.get("status", "unknown")
        hash_match = r.get("replay_hash_match", True)
        
        if not hash_match:
            all_hash_match = False
        if scenario_status != "success":
            failed_count += 1
        
        scenarios_list.append({
            "name": scenario_name,
            "status": "PASS" if scenario_status == "success" else "FAIL",
            "hash_match": hash_match,
        })
    
    result["tape_hash_match"] = all_hash_match
    result["scenarios_failed"] = failed_count
    result["scenarios"] = scenarios_list
    
    # Get concentration metrics
    concentration = data.get("concentration", {})
    result["phi_top1_share"] = concentration.get("avg_top1_share")
    result["unique_signatures"] = concentration.get("total_unique_signatures")
    
    result["loaded"] = True
    return result


def evaluate_testbot_gate(
    metrics: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate testbot gate conditions (Shadow mode).
    
    Gate conditions:
    - tape_hash_match: ERROR if False (shadow: log, no block)
    - phi_top1_share: WARN if > threshold
    - unique_signatures: WARN if < floor
    
    Args:
        metrics: Dict from load_testbot_metrics()
        thresholds: Optional dict with phi_top1_share_max and unique_signatures_min
        
    Returns:
        Dict with:
        - loaded: bool
        - overall_status: "PASS" | "WARN" | "ERROR"
        - gates: Dict with individual gate results
        - metrics: Original metrics dict
    """
    if thresholds is None:
        thresholds = DEFAULT_TESTBOT_THRESHOLDS
    
    result = {
        "loaded": metrics.get("loaded", False),
        "overall_status": "PASS",
        "gates": {},
        "metrics": metrics,
        "thresholds_used": thresholds,
    }
    
    if not metrics.get("loaded"):
        result["overall_status"] = "SKIP"
        result["gates"] = {
            "testbot_metrics": {
                "status": "SKIP",
                "reason": metrics.get("error", "Report not loaded"),
            }
        }
        return result
    
    # Gate 1: tape_hash_match (ERROR if False)
    tape_match = metrics.get("tape_hash_match", True)
    result["gates"]["tape_hash_match"] = {
        "status": "PASS" if tape_match else "ERROR",
        "value": tape_match,
        "reason": "All scenarios replay hash matched" if tape_match else "One or more scenarios have hash mismatch",
    }
    if not tape_match:
        result["overall_status"] = "ERROR"
    
    # Gate 2: phi_top1_share (WARN if > threshold)
    phi_top1 = metrics.get("phi_top1_share")
    phi_threshold = thresholds.get("phi_top1_share_max", 0.6)
    if phi_top1 is not None:
        phi_exceeded = phi_top1 > phi_threshold
        result["gates"]["phi_top1_share"] = {
            "status": "WARN" if phi_exceeded else "PASS",
            "value": phi_top1,
            "threshold": phi_threshold,
            "reason": f"phi_top1_share={phi_top1:.3f} {'>' if phi_exceeded else '<='} threshold={phi_threshold:.3f}",
        }
        if phi_exceeded and result["overall_status"] == "PASS":
            result["overall_status"] = "WARN"
    else:
        result["gates"]["phi_top1_share"] = {
            "status": "SKIP",
            "reason": "phi_top1_share not available",
        }
    
    # Gate 3: unique_signatures (WARN if < floor)
    unique_sigs = metrics.get("unique_signatures")
    unique_floor = thresholds.get("unique_signatures_min", 5)
    if unique_sigs is not None:
        unique_below = unique_sigs < unique_floor
        result["gates"]["unique_signatures"] = {
            "status": "WARN" if unique_below else "PASS",
            "value": unique_sigs,
            "threshold": unique_floor,
            "reason": f"unique_signatures={unique_sigs} {'<' if unique_below else '>='} floor={unique_floor}",
        }
        if unique_below and result["overall_status"] == "PASS":
            result["overall_status"] = "WARN"
    else:
        result["gates"]["unique_signatures"] = {
            "status": "SKIP",
            "reason": "unique_signatures not available",
        }
    
    return result


def load_thresholds(thresholds_path: Optional[Path]) -> Dict[str, Any]:
    """Load calibrated thresholds from JSON file with fallback to defaults.
    
    Args:
        thresholds_path: Path to calibration JSON (from calibrate_mvp11_thresholds.py)
        
    Returns:
        Dict with:
        - thresholds: Dict of threshold_name -> value
        - source: "calibrated" or "default"
        - calibration_info: Optional metadata from calibration file
    """
    result = {
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "source": "default",
        "calibration_info": None,
        "loaded_keys": [],
        "missing_keys": [],
    }
    
    if thresholds_path is None or not thresholds_path.exists():
        return result
    
    try:
        data = json.loads(thresholds_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(f"[WARN] Failed to load thresholds from {thresholds_path}: {e}", file=sys.stderr, flush=True)
        return result
    
    # Extract calibrations from expected structure
    calibrations = data.get("calibrations", {})
    hard_gates = calibrations.get("hard_gates", {})
    
    # Mapping from calibration key to our internal key
    key_mapping = {
        "replay_hash_match_rate": "replay_hash_match_rate",
        "sanity_consecutive_days": "sanity_consecutive_days",
        "concentration_top1_threshold": "concentration_top1_threshold",
        "concentration_consecutive_days": "concentration_consecutive_days",
        "bias_p95_threshold": "bias_p95_threshold",
        "bias_consecutive_days": "bias_consecutive_days",
    }
    
    loaded_count = 0
    for cal_key, internal_key in key_mapping.items():
        if cal_key in hard_gates:
            item = hard_gates[cal_key]
            recommended = item.get("recommended")
            if recommended is not None:
                result["thresholds"][internal_key] = recommended
                result["loaded_keys"].append({
                    "key": internal_key,
                    "value": recommended,
                    "confidence": item.get("confidence", "unknown"),
                    "rationale": item.get("rationale", ""),
                })
                loaded_count += 1
            else:
                result["missing_keys"].append(internal_key)
        else:
            result["missing_keys"].append(internal_key)
    
    if loaded_count > 0:
        result["source"] = "calibrated"
        result["calibration_info"] = {
            "path": str(thresholds_path),
            "generated_at": data.get("generated_at"),
            "sample_counts": data.get("sample_counts", {}),
        }
    
    return result


def load_trend_entries(trend_dir: Path, window_days: int = 7) -> List[Dict[str, Any]]:
    """Load recent trend entries."""
    entries = []
    
    current = trend_dir / "trend_entry.json"
    if current.exists():
        try:
            data = json.loads(current.read_text(encoding="utf-8"))
            entries.append(data)
        except (json.JSONDecodeError, IOError):
            pass
    
    trend_7d = trend_dir / "trend_7d.json"
    if trend_7d.exists():
        try:
            data = json.loads(trend_7d.read_text(encoding="utf-8"))
            if isinstance(data.get("entries"), list):
                entries.extend(data["entries"])
        except (json.JSONDecodeError, IOError):
            pass
    
    for f in sorted(trend_dir.glob("trend_entry_*.json"))[-window_days:]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entries.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: x.get("date_utc", ""), reverse=True):
        date = e.get("date_utc")
        if date and date not in seen:
            seen.add(date)
            unique.append(e)
    
    return unique[:window_days]


def check_replay_hash_match(
    entries: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Check replay hash_match_rate against threshold."""
    threshold = thresholds.get("replay_hash_match_rate", 1.0)
    
    for e in entries:
        replay = e.get("metrics", {}).get("replay", {})
        if isinstance(replay, dict):
            rate = replay.get("hash_match_rate")
        else:
            rate = e.get("replay", {}).get("hash_match_rate")
        
        if rate is not None and float(rate) < threshold:
            return {
                "gate": "replay_hash_match",
                "status": "FAIL",
                "reason": f"hash_match_rate={rate:.3f} < threshold={threshold:.3f}",
                "should_fail": True,
                "threshold": threshold,
                "observed": float(rate),
                "threshold_source": "calibrated" if threshold != DEFAULT_THRESHOLDS["replay_hash_match_rate"] else "default",
            }
    
    return {
        "gate": "replay_hash_match",
        "status": "PASS",
        "reason": f"hash_match_rate >= {threshold:.3f} for all entries",
        "should_fail": False,
        "threshold": threshold,
        "threshold_source": "calibrated" if threshold != DEFAULT_THRESHOLDS["replay_hash_match_rate"] else "default",
    }


def check_sanity_consecutive(
    entries: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Check sanity for consecutive days against threshold."""
    threshold_days = thresholds.get("sanity_consecutive_days", 2)
    
    if not entries:
        return {
            "gate": "sanity_consecutive",
            "status": "UNKNOWN",
            "should_fail": False,
            "reason": "No entries",
            "threshold": threshold_days,
            "threshold_source": "default",
        }
    
    sanity_values = []
    for e in entries:
        metrics = e.get("metrics", {})
        sanity = metrics.get("sanity_ok_coverage")
        if sanity is not None:
            sanity_values.append(float(sanity) >= 0.99)
        else:
            gate = e.get("gate", {})
            overall = gate.get("overall")
            sanity_values.append(overall == "PASS" if overall else None)
    
    consecutive_fail = 0
    max_consecutive = 0
    
    for v in sanity_values:
        if v is False:
            consecutive_fail += 1
            max_consecutive = max(max_consecutive, consecutive_fail)
        else:
            consecutive_fail = 0
    
    if max_consecutive >= threshold_days:
        return {
            "gate": "sanity_consecutive",
            "status": "FAIL",
            "reason": f"sanity != OK for {max_consecutive} consecutive days (threshold: {threshold_days})",
            "should_fail": True,
            "consecutive_days": max_consecutive,
            "threshold": threshold_days,
            "threshold_source": "calibrated" if threshold_days != DEFAULT_THRESHOLDS["sanity_consecutive_days"] else "default",
        }
    
    return {
        "gate": "sanity_consecutive",
        "status": "PASS",
        "reason": f"max consecutive fail = {max_consecutive} (threshold: {threshold_days})",
        "should_fail": False,
        "consecutive_days": max_consecutive,
        "threshold": threshold_days,
        "threshold_source": "calibrated" if threshold_days != DEFAULT_THRESHOLDS["sanity_consecutive_days"] else "default",
    }


def check_concentration_consecutive(
    entries: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Check signature concentration for consecutive days against thresholds."""
    top1_threshold = thresholds.get("concentration_top1_threshold", 0.55)
    threshold_days = thresholds.get("concentration_consecutive_days", 2)
    
    if not entries:
        return {
            "gate": "concentration_consecutive",
            "status": "UNKNOWN",
            "should_fail": False,
            "reason": "No entries",
            "top1_threshold": top1_threshold,
            "consecutive_threshold": threshold_days,
        }
    
    top1_values = []
    for e in entries:
        conc = e.get("concentration", {})
        top1 = conc.get("phi_top1_share")
        if top1 is not None:
            top1_values.append(float(top1))
    
    if not top1_values:
        return {
            "gate": "concentration_consecutive",
            "status": "UNKNOWN",
            "reason": "No concentration data",
            "should_fail": False,
            "top1_threshold": top1_threshold,
            "consecutive_threshold": threshold_days,
        }
    
    consecutive_violate = 0
    max_consecutive = 0
    
    for v in top1_values:
        if v > top1_threshold:
            consecutive_violate += 1
            max_consecutive = max(max_consecutive, consecutive_violate)
        else:
            consecutive_violate = 0
    
    # Determine threshold source
    top1_is_calibrated = top1_threshold != DEFAULT_THRESHOLDS["concentration_top1_threshold"]
    days_is_calibrated = threshold_days != DEFAULT_THRESHOLDS["concentration_consecutive_days"]
    threshold_source = "calibrated" if (top1_is_calibrated or days_is_calibrated) else "default"
    
    if max_consecutive >= threshold_days:
        return {
            "gate": "concentration_consecutive",
            "status": "FAIL",
            "reason": f"phi_top1_share > {top1_threshold:.3f} for {max_consecutive} consecutive days (threshold: {threshold_days})",
            "should_fail": True,
            "max_top1": max(top1_values),
            "top1_threshold": top1_threshold,
            "consecutive_threshold": threshold_days,
            "threshold_source": threshold_source,
        }
    
    return {
        "gate": "concentration_consecutive",
        "status": "PASS",
        "reason": f"max consecutive violation = {max_consecutive} (threshold: {threshold_days})",
        "should_fail": False,
        "max_top1": max(top1_values) if top1_values else None,
        "top1_threshold": top1_threshold,
        "consecutive_threshold": threshold_days,
        "threshold_source": threshold_source,
    }


def check_bias_consecutive(
    entries: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Check bias strength for consecutive days against thresholds."""
    bias_threshold = thresholds.get("bias_p95_threshold", 0.8 * MAX_BIAS)
    threshold_days = thresholds.get("bias_consecutive_days", 2)
    
    if not entries:
        return {
            "gate": "bias_consecutive",
            "status": "UNKNOWN",
            "should_fail": False,
            "reason": "No entries",
            "bias_threshold": bias_threshold,
            "consecutive_threshold": threshold_days,
        }
    
    bias_values = []
    for e in entries:
        prior = e.get("prior", {})
        bias_p95 = prior.get("bias_p95")
        if bias_p95 is not None:
            bias_values.append(float(bias_p95))
    
    if not bias_values:
        return {
            "gate": "bias_consecutive",
            "status": "SKIP",
            "reason": "Prior not enabled",
            "should_fail": False,
            "bias_threshold": bias_threshold,
            "consecutive_threshold": threshold_days,
        }
    
    consecutive_violate = 0
    max_consecutive = 0
    
    for v in bias_values:
        if v > bias_threshold:
            consecutive_violate += 1
            max_consecutive = max(max_consecutive, consecutive_violate)
        else:
            consecutive_violate = 0
    
    # Determine threshold source
    bias_is_calibrated = bias_threshold != DEFAULT_THRESHOLDS["bias_p95_threshold"]
    days_is_calibrated = threshold_days != DEFAULT_THRESHOLDS["bias_consecutive_days"]
    threshold_source = "calibrated" if (bias_is_calibrated or days_is_calibrated) else "default"
    
    if max_consecutive >= threshold_days:
        return {
            "gate": "bias_consecutive",
            "status": "FAIL",
            "reason": f"bias_p95 > {bias_threshold:.3f} for {max_consecutive} consecutive days (threshold: {threshold_days})",
            "should_fail": True,
            "max_bias_p95": max(bias_values),
            "bias_threshold": bias_threshold,
            "consecutive_threshold": threshold_days,
            "threshold_source": threshold_source,
        }
    
    return {
        "gate": "bias_consecutive",
        "status": "PASS",
        "reason": f"max consecutive violation = {max_consecutive} (threshold: {threshold_days})",
        "should_fail": False,
        "max_bias_p95": max(bias_values) if bias_values else None,
        "bias_threshold": bias_threshold,
        "consecutive_threshold": threshold_days,
        "threshold_source": threshold_source,
    }


def evaluate_hard_gates(
    entries: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
    enforce: bool = False,
    testbot_metrics: Optional[Dict[str, Any]] = None,
    testbot_thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate all hard gates using the provided thresholds.
    
    Args:
        entries: Trend entries to evaluate
        thresholds: Thresholds for main gates
        enforce: Whether to enforce hard gates
        testbot_metrics: Optional testbot metrics from load_testbot_metrics()
        testbot_thresholds: Optional thresholds for testbot gates
    """
    gates = [
        check_replay_hash_match(entries, thresholds),
        check_sanity_consecutive(entries, thresholds),
        check_concentration_consecutive(entries, thresholds),
        check_bias_consecutive(entries, thresholds),
    ]
    
    should_fail = any(g.get("should_fail", False) for g in gates)
    
    # Evaluate testbot gate (Shadow mode - does not affect should_fail)
    testbot_eval = None
    if testbot_metrics is not None:
        testbot_eval = evaluate_testbot_gate(testbot_metrics, testbot_thresholds)
    
    date_range = None
    if entries:
        date_range = {
            "start": entries[-1].get("date_utc"),
            "end": entries[0].get("date_utc"),
        }
    
    result = {
        "schema_version": "mvp11.hard_gate.v2",
        "ts": time.time(),
        "mode": "enforced" if enforce else "shadow",
        "entries_analyzed": len(entries),
        "date_range": date_range,
        "overall_status": "FAIL" if should_fail else "PASS",
        "should_fail": should_fail,
        "gates": gates,
    }
    
    # Add testbot section (Shadow mode)
    if testbot_eval is not None:
        result["testbot"] = testbot_eval
    
    return result


def render_report_md(
    report: Dict[str, Any],
    threshold_info: Dict[str, Any],
) -> str:
    """Render hard gate report as markdown with threshold comparison."""
    date_range = report.get("date_range") or {}
    
    lines = [
        "# MVP11 Hard Gate Report",
        "",
        f"**Mode**: `{report.get('mode', 'shadow')}`",
        f"**Overall Status**: `{'🚨 FAIL' if report.get('should_fail') else '✅ PASS'}`",
        f"**Entries Analyzed**: `{report.get('entries_analyzed', 0)}`",
        f"**Date Range**: `{date_range.get('start', 'N/A')}` to `{date_range.get('end', 'N/A')}`",
        f"**Threshold Source**: `{threshold_info.get('source', 'default')}`",
        "",
    ]
    
    # Threshold calibration info
    cal_info = threshold_info.get("calibration_info")
    if cal_info:
        lines.extend([
            "## Threshold Calibration",
            "",
            f"- **Path**: `{cal_info.get('path', 'N/A')}`",
            f"- **Generated**: `{cal_info.get('generated_at', 'N/A')}`",
        ])
        sample_counts = cal_info.get("sample_counts", {})
        if sample_counts:
            lines.append(f"- **Samples**: {sample_counts.get('total_entries', 0)} entries")
        lines.append("")
    
    # Gate Results table with threshold comparison
    lines.extend([
        "## Gate Results",
        "",
        "| Gate | Status | Threshold | Observed | Reason |",
        "|------|--------|-----------|----------|--------|",
    ])
    
    for g in report.get("gates", []):
        status = "🚨 FAIL" if g.get("should_fail") else "✅ PASS" if g.get("status") == "PASS" else "⚠️ " + g.get("status", "UNKNOWN")
        reason = g.get("reason", "")
        
        # Extract threshold info for comparison
        threshold_str = "-"
        observed_str = "-"
        
        if g.get("gate") == "replay_hash_match":
            threshold_str = f"{g.get('threshold', 1.0):.3f}"
            if g.get("observed") is not None:
                observed_str = f"{g.get('observed'):.3f}"
        elif g.get("gate") == "sanity_consecutive":
            threshold_str = f"{g.get('threshold', 2)} days"
            if g.get("consecutive_days") is not None:
                observed_str = f"{g.get('consecutive_days')} days"
        elif g.get("gate") == "concentration_consecutive":
            top1_t = g.get("top1_threshold", 0.55)
            days_t = g.get("consecutive_threshold", 2)
            threshold_str = f"{top1_t:.3f} / {days_t}d"
            if g.get("max_top1") is not None:
                observed_str = f"{g.get('max_top1'):.3f} / {g.get('consecutive_days', 0)}d"
        elif g.get("gate") == "bias_consecutive":
            bias_t = g.get("bias_threshold", 0.12)
            days_t = g.get("consecutive_threshold", 2)
            threshold_str = f"{bias_t:.3f} / {days_t}d"
            if g.get("max_bias_p95") is not None:
                observed_str = f"{g.get('max_bias_p95'):.3f} / {g.get('consecutive_days', 0)}d"
        
        lines.append(f"| {g.get('gate', 'unknown')} | {status} | {threshold_str} | {observed_str} | {reason} |")
    
    # Thresholds used section
    lines.extend([
        "",
        "## Thresholds Used",
        "",
        "| Threshold | Value | Source |",
        "|-----------|-------|--------|",
    ])
    
    thresholds = threshold_info.get("thresholds", DEFAULT_THRESHOLDS)
    loaded_keys = threshold_info.get("loaded_keys", [])
    loaded_map = {k["key"]: k for k in loaded_keys}
    
    for key, value in thresholds.items():
        if key in loaded_map:
            source = f"calibrated ({loaded_map[key].get('confidence', 'unknown')})"
        else:
            source = "default"
        
        if isinstance(value, float):
            lines.append(f"| {key} | {value:.4f} | {source} |")
        else:
            lines.append(f"| {key} | {value} | {source} |")
    
    # Testbot section (if present)
    testbot = report.get("testbot")
    if testbot:
        lines.extend([
            "",
            "## Testbot E2E Gates (Shadow Mode)",
            "",
            f"**Overall Status**: `{testbot.get('overall_status', 'SKIP')}`",
            "",
        ])
        
        testbot_metrics = testbot.get("metrics", {})
        if testbot_metrics.get("loaded"):
            lines.extend([
                f"- **Scenarios**: {testbot_metrics.get('scenarios_count', 0)} total, {testbot_metrics.get('scenarios_failed', 0)} failed",
                f"- **Tape Hash Match**: `{testbot_metrics.get('tape_hash_match', 'N/A')}`",
                f"- **Phi Top1 Share**: `{testbot_metrics.get('phi_top1_share', 'N/A'):.3f}`" if testbot_metrics.get('phi_top1_share') is not None else f"- **Phi Top1 Share**: `N/A`",
                f"- **Unique Signatures**: `{testbot_metrics.get('unique_signatures', 'N/A')}`",
                "",
            ])
        
        testbot_gates = testbot.get("gates", {})
        if testbot_gates:
            lines.extend([
                "| Gate | Status | Value | Threshold | Reason |",
                "|------|--------|-------|-----------|--------|",
            ])
            for gate_name, gate_info in testbot_gates.items():
                status = gate_info.get("status", "UNKNOWN")
                status_icon = "✅" if status == "PASS" else "⚠️" if status == "WARN" else "🚨" if status == "ERROR" else "➖"
                value = gate_info.get("value", "-")
                threshold = gate_info.get("threshold", "-")
                reason = gate_info.get("reason", "")
                
                if isinstance(value, float):
                    value_str = f"{value:.3f}"
                else:
                    value_str = str(value)
                
                if isinstance(threshold, float):
                    threshold_str = f"{threshold:.3f}"
                else:
                    threshold_str = str(threshold)
                
                lines.append(f"| {gate_name} | {status_icon} {status} | {value_str} | {threshold_str} | {reason} |")
    
    if report.get("should_fail"):
        lines.extend([
            "",
            "## ⚠️ Action Required",
            "",
            "One or more hard gates failed. Review the failures above.",
        ])
    
    return "\n".join(lines)


def build_summary_json(report: Dict[str, Any]) -> Dict[str, Any]:
    """Build a simplified summary JSON with gate status only.
    
    MVP11.4.8 P1: Summary JSON is a lightweight output for CI/monitoring pipelines.
    """
    gates_summary = []
    for g in report.get("gates", []):
        gates_summary.append({
            "gate": g.get("gate"),
            "status": g.get("status"),
            "should_fail": g.get("should_fail", False),
            "reason": g.get("reason"),
        })
    
    result = {
        "schema": "mvp11.hard_gate.summary.v1",
        "ts": report.get("ts"),
        "mode": report.get("mode"),
        "overall_status": report.get("overall_status"),
        "should_fail": report.get("should_fail"),
        "entries_analyzed": report.get("entries_analyzed"),
        "gates": gates_summary,
    }
    
    # Add testbot summary (if present)
    testbot = report.get("testbot")
    if testbot:
        testbot_gates = []
        for gate_name, gate_info in testbot.get("gates", {}).items():
            testbot_gates.append({
                "gate": gate_name,
                "status": gate_info.get("status"),
                "value": gate_info.get("value"),
                "threshold": gate_info.get("threshold"),
            })
        
        result["testbot"] = {
            "loaded": testbot.get("loaded", False),
            "overall_status": testbot.get("overall_status", "SKIP"),
            "gates": testbot_gates,
        }
    
    return result


def build_one_liner(report: Dict[str, Any]) -> str:
    """Build a single-line summary in key=value format.
    
    MVP11.4.9: One-liner output for CI/monitoring pipelines.
    
    Format:
        STATUS=PASS|WARN|ERROR
        ERRORS=<n>
        WARNS=<n>
        SCENARIOS=<scenario>:<status>,...
        TOP1=<value>/<thr> UNIQUE=<value>/<thr>
    
    Returns:
        Multi-line string with key=value pairs (parseable by simple parsers).
    """
    # Determine overall status
    # Priority: ERROR > FAIL > WARN > PASS
    overall_status = "PASS"
    error_count = 0
    warn_count = 0
    
    # Count errors/warns from main gates
    for g in report.get("gates", []):
        status = g.get("status", "UNKNOWN")
        if status == "FAIL":
            error_count += 1
            overall_status = "ERROR"
        elif status == "WARN":
            warn_count += 1
            if overall_status == "PASS":
                overall_status = "WARN"
    
    # Check testbot gates
    testbot = report.get("testbot")
    if testbot:
        for gate_name, gate_info in testbot.get("gates", {}).items():
            status = gate_info.get("status", "UNKNOWN")
            if status == "ERROR":
                error_count += 1
                overall_status = "ERROR"
            elif status == "WARN":
                warn_count += 1
                if overall_status == "PASS":
                    overall_status = "WARN"
    
    # Build SCENARIOS line from testbot
    scenarios_parts = []
    if testbot and testbot.get("metrics", {}).get("loaded"):
        for scenario in testbot.get("metrics", {}).get("scenarios", []):
            name = scenario.get("name", "unknown")
            status = scenario.get("status", "UNKNOWN")
            scenarios_parts.append(f"{name}:{status}")
    
    # If no testbot scenarios, use main gate names
    if not scenarios_parts:
        for g in report.get("gates", []):
            gate_name = g.get("gate", "unknown")
            status = "PASS" if g.get("status") == "PASS" else "FAIL"
            scenarios_parts.append(f"{gate_name}:{status}")
    
    scenarios_str = ",".join(scenarios_parts) if scenarios_parts else "N/A"
    
    # Build metrics line
    metrics_parts = []
    
    # TOP1 (phi_top1_share)
    if testbot and testbot.get("metrics", {}).get("phi_top1_share") is not None:
        top1_val = testbot["metrics"]["phi_top1_share"]
        top1_thr = testbot.get("thresholds_used", {}).get("phi_top1_share_max", 0.6)
        metrics_parts.append(f"TOP1={top1_val:.3f}/{top1_thr:.3f}")
    else:
        metrics_parts.append("TOP1=N/A/N/A")
    
    # UNIQUE (unique_signatures)
    if testbot and testbot.get("metrics", {}).get("unique_signatures") is not None:
        unique_val = testbot["metrics"]["unique_signatures"]
        unique_thr = testbot.get("thresholds_used", {}).get("unique_signatures_min", 5)
        metrics_parts.append(f"UNIQUE={unique_val}/{unique_thr}")
    else:
        metrics_parts.append("UNIQUE=N/A/N/A")
    
    metrics_str = " ".join(metrics_parts)
    
    # Build output lines
    lines = [
        f"STATUS={overall_status}",
        f"ERRORS={error_count}",
        f"WARNS={warn_count}",
        f"SCENARIOS={scenarios_str}",
        metrics_str,
    ]
    
    return "\n".join(lines)


def print_enhanced_stdout(report: Dict[str, Any], threshold_info: Dict[str, Any]) -> None:
    """MVP11.4.8 P1: Enhanced stdout output with gate-level details."""
    mode = report.get("mode", "shadow")
    overall = report.get("overall_status", "UNKNOWN")
    should_fail = report.get("should_fail", False)
    
    # Header
    print("\n" + "=" * 60, flush=True)
    print(f"MVP11 Hard Gate Evaluation", flush=True)
    print("=" * 60, flush=True)
    print(f"Mode:              {mode}", flush=True)
    print(f"Overall Status:    {overall}", flush=True)
    print(f"Should Fail:       {should_fail}", flush=True)
    print(f"Entries Analyzed:  {report.get('entries_analyzed', 0)}", flush=True)
    print(f"Threshold Source:  {threshold_info.get('source', 'default')}", flush=True)
    
    # Date range
    date_range = report.get("date_range") or {}
    if date_range:
        print(f"Date Range:        {date_range.get('start', 'N/A')} to {date_range.get('end', 'N/A')}", flush=True)
    
    # Gate details
    print("\n" + "-" * 60, flush=True)
    print("Gate Results:", flush=True)
    print("-" * 60, flush=True)
    
    for g in report.get("gates", []):
        gate_name = g.get("gate", "unknown")
        status = g.get("status", "UNKNOWN")
        should = g.get("should_fail", False)
        reason = g.get("reason", "")
        
        # Status icon
        if should:
            icon = "🚨"
        elif status == "PASS":
            icon = "✅"
        else:
            icon = "⚠️"
        
        print(f"\n  {icon} {gate_name}", flush=True)
        print(f"     Status:     {status}", flush=True)
        print(f"     ShouldFail: {should}", flush=True)
        print(f"     Reason:     {reason}", flush=True)
        
        # Show threshold comparison if available
        if g.get("threshold") is not None:
            print(f"     Threshold:  {g.get('threshold')}", flush=True)
        if g.get("observed") is not None:
            print(f"     Observed:   {g.get('observed')}", flush=True)
    
    # Testbot section (if present)
    testbot = report.get("testbot")
    if testbot:
        print("\n" + "-" * 60, flush=True)
        print("Testbot E2E Gates (Shadow Mode):", flush=True)
        print("-" * 60, flush=True)
        
        overall = testbot.get("overall_status", "SKIP")
        icon = "✅" if overall == "PASS" else "⚠️" if overall == "WARN" else "🚨" if overall == "ERROR" else "➖"
        print(f"\n  {icon} Testbot Overall: {overall}", flush=True)
        
        testbot_metrics = testbot.get("metrics", {})
        if testbot_metrics.get("loaded"):
            print(f"     Scenarios:    {testbot_metrics.get('scenarios_count', 0)} total, {testbot_metrics.get('scenarios_failed', 0)} failed", flush=True)
            print(f"     Unique Sigs:  {testbot_metrics.get('unique_signatures', 'N/A')}", flush=True)
            if testbot_metrics.get("phi_top1_share") is not None:
                print(f"     Phi Top1:     {testbot_metrics.get('phi_top1_share'):.3f}", flush=True)
        
        for gate_name, gate_info in testbot.get("gates", {}).items():
            status = gate_info.get("status", "UNKNOWN")
            gate_icon = "✅" if status == "PASS" else "⚠️" if status == "WARN" else "🚨" if status == "ERROR" else "➖"
            print(f"\n  {gate_icon} {gate_name}: {status}", flush=True)
            if gate_info.get("value") is not None:
                print(f"     Value:       {gate_info.get('value')}", flush=True)
            if gate_info.get("threshold") is not None:
                print(f"     Threshold:   {gate_info.get('threshold')}", flush=True)
    
    print("\n" + "=" * 60, flush=True)
    
    # Final status line
    if should_fail:
        print(f"❌ HARD GATE FAILURE DETECTED", flush=True)
    else:
        print(f"✅ ALL HARD GATES PASSED", flush=True)
    print("=" * 60 + "\n", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="MVP11 Hard Gate Evaluator with Calibrated Thresholds")
    ap.add_argument("--trend-dir", default="artifacts/mvp11/trends")
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument(
        "--out",
        default=None,
        help="Path to write summary JSON (simplified output with gate status only). "
             "If not specified, no summary JSON is written.",
    )
    ap.add_argument(
        "--out-report",
        default="artifacts/mvp11/profiles/hard_gate_report.json",
        help="Path to write full report JSON (default: artifacts/mvp11/profiles/hard_gate_report.json)",
    )
    ap.add_argument(
        "--out-md",
        default="artifacts/mvp11/profiles/hard_gate_report.md",
        help="Path to write markdown report (default: artifacts/mvp11/profiles/hard_gate_report.md)",
    )
    ap.add_argument(
        "--enforce",
        action="store_true",
        help="Exit with non-zero on failure (Phase 2 enforced mode)",
    )
    ap.add_argument(
        "--shadow-soft-fail",
        action="store_true",
        help="In shadow mode (non-enforce), exit 0 even if should_fail=true. "
             "Prints warning but does not fail CI. Useful for monitoring without blocking.",
    )
    ap.add_argument(
        "--thresholds",
        default="reports/mvp11_threshold_calibration.json",
        help="Path to calibrated thresholds JSON (from calibrate_mvp11_thresholds.py). "
             "Set to empty string to disable.",
    )
    ap.add_argument(
        "--testbot-report",
        default="artifacts/testbot/concentration_report.json",
        help="Path to testbot concentration report JSON. "
             "Set to empty string to disable testbot evaluation.",
    )
    ap.add_argument(
        "--testbot-phi-threshold",
        type=float,
        default=0.6,
        help="Maximum allowed phi_top1_share for testbot gate (default: 0.6, WARN if exceeded)",
    )
    ap.add_argument(
        "--testbot-unique-min",
        type=int,
        default=5,
        help="Minimum unique signatures for testbot gate (default: 5, WARN if below)",
    )
    ap.add_argument(
        "--out-one-liner",
        default=None,
        help="Path to write one-liner summary in key=value format. "
             "Output file is parseable with simple key=value parsing. "
             "Format: STATUS=PASS|WARN|ERROR, ERRORS=<n>, WARNS=<n>, "
             "SCENARIOS=<name>:<status>,..., TOP1=<val>/<thr> UNIQUE=<val>/<thr>",
    )
    args = ap.parse_args()
    
    enforce = args.enforce or os.environ.get("HARD_GATE_ENFORCE", "0") == "1"
    shadow_soft_fail = args.shadow_soft_fail and not enforce
    
    # Load thresholds
    thresholds_path = Path(args.thresholds) if args.thresholds else None
    threshold_info = load_thresholds(thresholds_path)
    thresholds = threshold_info["thresholds"]
    
    print(f"[INFO] Threshold source: {threshold_info['source']}", flush=True)
    if threshold_info.get("loaded_keys"):
        for k in threshold_info["loaded_keys"]:
            print(f"[INFO] Loaded calibrated threshold: {k['key']} = {k['value']} (confidence: {k['confidence']})", flush=True)
    
    # Load trend entries
    trend_dir = Path(args.trend_dir)
    entries = load_trend_entries(trend_dir, args.window_days)
    
    print(f"[INFO] Loaded {len(entries)} trend entries", flush=True)
    
    # Load testbot metrics (optional)
    testbot_metrics = None
    testbot_thresholds = {
        "phi_top1_share_max": args.testbot_phi_threshold,
        "unique_signatures_min": args.testbot_unique_min,
    }
    if args.testbot_report:
        testbot_metrics = load_testbot_metrics(args.testbot_report)
        if testbot_metrics.get("loaded"):
            print(f"[INFO] Loaded testbot metrics: {testbot_metrics.get('scenarios_count', 0)} scenarios", flush=True)
        else:
            print(f"[INFO] Testbot metrics not available: {testbot_metrics.get('error', 'unknown')}", flush=True)
            testbot_metrics = None  # Clear to skip evaluation
    
    # Evaluate hard gates
    report = evaluate_hard_gates(
        entries, 
        thresholds, 
        enforce=enforce,
        testbot_metrics=testbot_metrics,
        testbot_thresholds=testbot_thresholds,
    )
    
    # Add threshold info to report
    report["threshold_info"] = {
        "source": threshold_info["source"],
        "calibration_path": str(thresholds_path) if thresholds_path else None,
        "loaded_keys": threshold_info.get("loaded_keys", []),
    }
    
    # MVP11.4.8 P1: Write summary JSON if --out specified
    if args.out:
        out_summary = Path(args.out)
        out_summary.parent.mkdir(parents=True, exist_ok=True)
        summary = build_summary_json(report)
        out_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] Summary JSON written to: {out_summary}", flush=True)
    
    # MVP11.4.9: Write one-liner summary if --out-one-liner specified
    if args.out_one_liner:
        out_one_liner = Path(args.out_one_liner)
        out_one_liner.parent.mkdir(parents=True, exist_ok=True)
        one_liner = build_one_liner(report)
        out_one_liner.write_text(one_liner + "\n", encoding="utf-8")
        print(f"[INFO] One-liner summary written to: {out_one_liner}", flush=True)
    
    # Write full report JSON
    out_report = Path(args.out_report)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] Full report JSON written to: {out_report}", flush=True)
    
    # Write markdown report
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_report_md(report, threshold_info), encoding="utf-8")
    print(f"[INFO] Markdown report written to: {out_md}", flush=True)
    
    # MVP11.4.8 P1: Enhanced stdout output
    print_enhanced_stdout(report, threshold_info)
    
    # Exit logic with shadow-soft-fail support
    if report["should_fail"]:
        if enforce:
            # Phase 2: Enforced mode - must fail CI
            print("[ERROR] Hard gate failure in ENFORCED mode - exiting with non-zero", file=sys.stderr, flush=True)
            sys.exit(1)
        elif shadow_soft_fail:
            # MVP11.4.8 P1: Shadow mode with soft-fail - warn but exit 0
            print("[WARN] Hard gate failure in SHADOW mode with --shadow-soft-fail", file=sys.stderr, flush=True)
            print("[WARN] CI will pass, but failures detected. Review reports.", file=sys.stderr, flush=True)
            sys.exit(0)
        else:
            # Shadow mode without soft-fail - still fail (for backward compatibility)
            print("[WARN] Hard gate failure in SHADOW mode - exiting with non-zero", file=sys.stderr, flush=True)
            print("[WARN] Use --shadow-soft-fail to allow CI pass in shadow mode.", file=sys.stderr, flush=True)
            sys.exit(1)
    else:
        print("[INFO] All hard gates passed - exiting cleanly", flush=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
