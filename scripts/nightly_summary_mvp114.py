#!/usr/bin/env python3
"""MVP11.4 Nightly Summary - Light Observe Mode.

Collects all nightly outputs into a unified summary with OK/WARN/ERROR status.
Light mode: warnings/errors are logged but do NOT fail the job.

v11.4.2: Added signature concentration metrics for chronic degradation detection.

Usage:
    python scripts/nightly_summary_mvp114.py \
        --artifacts-dir artifacts/mvp11 \
        --profile artifacts/mvp11/profiles/nightly_soak_profile.json \
        --effects artifacts/mvp11/effects/nightly_cycle_effects.json \
        --gate artifacts/mvp11/profiles/nightly_cycle_gate_report.json \
        --out-dir artifacts/mvp11/nightly/$(date +%Y%m%d)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from math import log2
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def get_git_commit() -> str:
    """Get current git commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    """Load JSON file if exists."""
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def compute_signature_concentration_from_events(events_path: Path, window_size: int = 200) -> Dict[str, Any]:
    """Compute signature concentration from events file.
    
    Returns:
        - phi_top1_share: top-1 signature share
        - phi_top3_share: top-3 signature share
        - phi_hhi: Herfindahl index
        - unique_phi_per_1000: unique signatures per 1000 ticks
    """
    if not events_path.exists():
        return {"phi_top1_share": None, "phi_top3_share": None, "phi_hhi": None, "unique_phi_per_1000": None}
    
    signatures = []
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                    sig = event.get("cycle_signature")
                    if sig:
                        signatures.append(sig)
                except json.JSONDecodeError:
                    continue
    except IOError:
        return {"phi_top1_share": None, "phi_top3_share": None, "phi_hhi": None, "unique_phi_per_1000": None}
    
    if not signatures:
        return {"phi_top1_share": 0.0, "phi_top3_share": 0.0, "phi_hhi": 0.0, "unique_phi_per_1000": 0.0}
    
    counts = Counter(signatures)
    total = len(signatures)
    sorted_counts = sorted(counts.values(), reverse=True)
    
    top1_share = sorted_counts[0] / total if sorted_counts else 0.0
    top3_share = sum(sorted_counts[:3]) / total if len(sorted_counts) >= 3 else sum(sorted_counts) / total
    hhi = sum((c / total) ** 2 for c in counts.values())
    unique_per_1000 = (len(counts) / total) * 1000 if total > 0 else 0.0
    
    return {
        "phi_top1_share": round(top1_share, 6),
        "phi_top3_share": round(top3_share, 6),
        "phi_hhi": round(hhi, 6),
        "unique_phi_per_1000": round(unique_per_1000, 2),
    }


def check_eval_status(profile: Optional[Dict], effects: Optional[Dict]) -> Dict[str, Any]:
    """Check eval status from profile and effects."""
    result = {
        "quick": {"pass": None, "events": 0, "sanity": "UNKNOWN"},
        "science": {"pass": None, "events": 0, "sanity": "UNKNOWN", "cycle_candidates": 0},
        "replay": {"pass": None, "hash_match_rate": None},
    }
    
    if profile:
        sanity_ok_rate = profile.get("sanity_ok_rate", 0)
        result["quick"]["sanity"] = "OK" if sanity_ok_rate >= 0.99 else "WARN"
        result["quick"]["pass"] = sanity_ok_rate >= 0.99
        ticks = profile.get("config", {}).get("ticks", 0)
        scenarios = len(profile.get("config", {}).get("scenarios", []))
        seeds = len(profile.get("config", {}).get("seeds", []))
        result["quick"]["events"] = ticks * scenarios * seeds
    
    if effects:
        result["science"]["pass"] = effects.get("gate_passed", False)
        result["science"]["sanity"] = "OK" if effects.get("sanity_ok", True) else "WARN"
        result["science"]["cycle_candidates"] = effects.get("cycle_candidates_count", 0)
    
    return result


def check_cycle_status(artifacts_dir: Path) -> Dict[str, Any]:
    """Check cycle analysis status."""
    result = {
        "consolidated_written": False,
        "cycle_store_count": 0,
        "cycle_memory_exists": False,
    }
    
    cycle_memory = artifacts_dir / "cycle_memory.json"
    if cycle_memory.exists():
        result["cycle_memory_exists"] = True
        data = load_json(cycle_memory)
        if data:
            result["cycle_store_count"] = len(data.get("cycles", []))
            result["consolidated_written"] = True
    
    return result


def check_cycle_graph_status(artifacts_dir: Path) -> Dict[str, Any]:
    """Check cycle graph status."""
    result = {
        "nodes": 0,
        "edges": 0,
        "top_transitions": [],
    }
    
    cycle_graph = artifacts_dir / "cycle_graph.json"
    if cycle_graph.exists():
        data = load_json(cycle_graph)
        if data:
            result["nodes"] = len(data.get("nodes", []))
            result["edges"] = len(data.get("edges", []))
            transitions = data.get("transitions", [])
            result["top_transitions"] = sorted(
                transitions,
                key=lambda x: x.get("count", 0),
                reverse=True
            )[:5] if transitions else []
    
    return result


def check_prior_status(artifacts_dir: Path, ab_report: Optional[Dict]) -> Dict[str, Any]:
    """Check prior status from A/B report."""
    result = {
        "enabled": False,
        "bias_strength_mean": None,
        "bias_strength_p95": None,
        "near_cap_rate": None,
        "nightly_gate_ready": None,
    }
    
    if ab_report:
        agg = ab_report.get("aggregate", {})
        bias = agg.get("bias_strength", {})
        rec = agg.get("recommendation", {})
        
        result["enabled"] = True
        result["bias_strength_mean"] = bias.get("mean")
        result["bias_strength_p95"] = bias.get("p95")
        result["near_cap_rate"] = bias.get("near_cap_rate_mean")
        result["nightly_gate_ready"] = rec.get("nightly_gate_ready")
    
    return result


def check_concentration_status(artifacts_dir: Path) -> Dict[str, Any]:
    """Check signature concentration from latest run events."""
    result = {
        "phi_top1_share": None,
        "phi_top3_share": None,
        "phi_hhi": None,
        "unique_phi_per_1000": None,
    }
    
    # Find latest events file
    events_files = list(artifacts_dir.glob("mvp11_*.jsonl"))
    if not events_files:
        return result
    
    latest = max(events_files, key=lambda p: p.stat().st_mtime)
    return compute_signature_concentration_from_events(latest)


def apply_light_mode_gates(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Apply light mode gates - log warnings but don't fail.
    
    Light mode thresholds (WARN only, no fail):
    - replay: hash_match_rate < 1.0 -> ERROR (but job still passes)
    - cycle_analyze: sanity != OK -> WARN
    - cycle_graph: nodes/edges exceed limits -> WARN
    - prior: near_cap_rate > 0.05 -> WARN
    - prior: bias_p95 > 0.8*MAX_BIAS -> WARN
    - concentration: top1_share > 0.55 -> WARN (single-cycle collapse)
    """
    warnings = []
    errors = []
    
    # Eval checks
    eval_data = summary.get("eval", {})
    
    replay = eval_data.get("replay", {})
    if replay.get("hash_match_rate") is not None and replay["hash_match_rate"] < 1.0:
        errors.append(f"replay hash_match_rate={replay['hash_match_rate']:.3f} < 1.0")
    
    quick = eval_data.get("quick", {})
    if quick.get("sanity") != "OK":
        warnings.append(f"quick sanity={quick.get('sanity')}")
    
    science = eval_data.get("science", {})
    if science.get("sanity") != "OK":
        warnings.append(f"science sanity={science.get('sanity')}")
    
    # Cycle graph limits
    MAX_NODES = 10000
    MAX_EDGES = 50000
    
    cycle_graph = summary.get("cycle_graph", {})
    if cycle_graph.get("nodes", 0) > MAX_NODES:
        warnings.append(f"cycle_graph nodes={cycle_graph['nodes']} > {MAX_NODES}")
    if cycle_graph.get("edges", 0) > MAX_EDGES:
        warnings.append(f"cycle_graph edges={cycle_graph['edges']} > {MAX_EDGES}")
    
    # Prior checks
    prior = summary.get("prior", {})
    MAX_BIAS = 0.15
    
    if prior.get("near_cap_rate") is not None and prior["near_cap_rate"] > 0.05:
        warnings.append(f"prior near_cap_rate={prior['near_cap_rate']:.3f} > 0.05")
    
    if prior.get("bias_strength_p95") is not None and prior["bias_strength_p95"] > 0.8 * MAX_BIAS:
        warnings.append(f"prior bias_p95={prior['bias_strength_p95']:.3f} > {0.8 * MAX_BIAS:.3f}")
    
    # Concentration checks (MVP11.4.2)
    concentration = summary.get("concentration", {})
    
    if concentration.get("phi_top1_share") is not None and concentration["phi_top1_share"] > 0.55:
        warnings.append(f"concentration phi_top1_share={concentration['phi_top1_share']:.3f} > 0.55 (potential single-cycle collapse)")
    
    if concentration.get("phi_hhi") is not None and concentration["phi_hhi"] > 0.4:
        warnings.append(f"concentration phi_hhi={concentration['phi_hhi']:.3f} > 0.4 (high concentration)")
    
    # Determine status
    if errors:
        summary["status"] = "ERROR"
    elif warnings:
        summary["status"] = "WARN"
    else:
        summary["status"] = "OK"
    
    summary["warnings"] = warnings
    summary["errors"] = errors
    
    return summary


def render_summary_md(summary: Dict[str, Any]) -> str:
    """Render summary as markdown."""
    lines = [
        f"# MVP11.4 Nightly Summary",
        "",
        f"**Date**: {summary.get('date', 'unknown')}",
        f"**Commit**: `{summary.get('commit', 'unknown')}`",
        f"**Status**: `{summary.get('status', 'unknown')}`",
        "",
        "## Eval Status",
        "",
        "| Mode | Pass | Events | Sanity |",
        "|------|------|--------|--------|",
    ]
    
    eval_data = summary.get("eval", {})
    for mode in ["quick", "science"]:
        d = eval_data.get(mode, {})
        pass_str = "✅" if d.get("pass") else "❌" if d.get("pass") is False else "?"
        events = d.get("events", 0)
        sanity = d.get("sanity", "UNKNOWN")
        lines.append(f"| {mode} | {pass_str} | {events} | {sanity} |")
    
    replay = eval_data.get("replay", {})
    if replay.get("hash_match_rate") is not None:
        pass_str = "✅" if replay.get("pass") else "❌"
        lines.append(f"| replay | {pass_str} | hash_match={replay['hash_match_rate']:.3f} | - |")
    
    lines.extend([
        "",
        "## Cycle Status",
        "",
        f"- **Consolidated**: {'✅' if summary.get('cycle', {}).get('consolidated_written') else '❌'}",
        f"- **Store Count**: {summary.get('cycle', {}).get('cycle_store_count', 0)}",
        "",
        "## Cycle Graph",
        "",
        f"- **Nodes**: {summary.get('cycle_graph', {}).get('nodes', 0)}",
        f"- **Edges**: {summary.get('cycle_graph', {}).get('edges', 0)}",
    ])
    
    top_trans = summary.get("cycle_graph", {}).get("top_transitions", [])
    if top_trans:
        lines.extend([
            "",
            "### Top Transitions",
            "",
            "| From | To | Count |",
            "|------|-----|-------|",
        ])
        for t in top_trans[:5]:
            lines.append(f"| {t.get('from', '?')} | {t.get('to', '?')} | {t.get('count', 0)} |")
    
    # Prior status
    lines.extend([
        "",
        "## Prior Status",
        "",
    ])
    
    prior = summary.get("prior", {})
    if prior.get("enabled"):
        lines.extend([
            f"- **Enabled**: ✅",
            f"- **Bias Mean**: {prior.get('bias_strength_mean', 'N/A')}",
            f"- **Bias P95**: {prior.get('bias_strength_p95', 'N/A')}",
            f"- **Near Cap Rate**: {prior.get('near_cap_rate', 'N/A')}",
            f"- **Nightly Gate Ready**: {'✅' if prior.get('nightly_gate_ready') else '❌'}",
        ])
    else:
        lines.append("- **Enabled**: ❌ (A/B not run)")
    
    # Concentration status (MVP11.4.2)
    concentration = summary.get("concentration", {})
    if concentration.get("phi_top1_share") is not None:
        lines.extend([
            "",
            "## Signature Concentration (Chronic Degradation)",
            "",
            f"- **Top1 Share**: `{concentration.get('phi_top1_share', 'N/A')}`",
            f"- **Top3 Share**: `{concentration.get('phi_top3_share', 'N/A')}`",
            f"- **HHI**: `{concentration.get('phi_hhi', 'N/A')}`",
            f"- **Unique/1000**: `{concentration.get('unique_phi_per_1000', 'N/A')}`",
        ])
    
    # Warnings/Errors
    if summary.get("warnings"):
        lines.extend([
            "",
            "## ⚠️ Warnings",
            "",
        ])
        for w in summary["warnings"]:
            lines.append(f"- {w}")
    
    if summary.get("errors"):
        lines.extend([
            "",
            "## 🚨 Errors",
            "",
        ])
        for e in summary["errors"]:
            lines.append(f"- {e}")
    
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--effects", default=None)
    ap.add_argument("--gate", default=None)
    ap.add_argument("--ab-report", default=None)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()
    
    artifacts = Path(args.artifacts_dir)
    
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        date_str = datetime.now().strftime("%Y%m%d")
        out_dir = artifacts / "nightly" / date_str
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    profile = load_json(Path(args.profile) if args.profile else None)
    effects = load_json(Path(args.effects) if args.effects else None)
    gate = load_json(Path(args.gate) if args.gate else None)
    ab_report = load_json(Path(args.ab_report) if args.ab_report else None)
    
    summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "commit": get_git_commit(),
        "status": "OK",
        "eval": check_eval_status(profile, effects),
        "cycle": check_cycle_status(artifacts),
        "cycle_graph": check_cycle_graph_status(artifacts),
        "prior": check_prior_status(artifacts, ab_report),
        "concentration": check_concentration_status(artifacts),
        "warnings": [],
        "errors": [],
        "ts": time.time(),
    }
    
    summary = apply_light_mode_gates(summary)
    
    json_path = out_dir / "nightly_summary.json"
    md_path = out_dir / "nightly_summary.md"
    
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_summary_md(summary), encoding="utf-8")
    
    print(json.dumps({
        "output_json": str(json_path),
        "output_md": str(md_path),
        "status": summary["status"],
        "warnings": len(summary["warnings"]),
        "errors": len(summary["errors"]),
        "concentration": summary.get("concentration", {}),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
