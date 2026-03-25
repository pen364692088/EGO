#!/usr/bin/env python3
"""Export MVP11.4 trend entry with cycle_graph, prior, and concentration metrics.

Extends the base trend entry with:
- cycle_candidates_count
- cycle_store_count  
- cycle_graph_nodes / cycle_graph_edges
- prior_bias_p95 (when prior enabled)
- signature_concentration (MVP11.4.2)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import datetime, timezone
from math import log2
from pathlib import Path
from typing import Any, Dict, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None


def get_cycle_graph_metrics(artifacts_dir: Path) -> Dict[str, Any]:
    """Extract cycle graph metrics."""
    graph_path = artifacts_dir / "cycle_graph.json"
    data = load_json(graph_path)
    if not data:
        return {"nodes": 0, "edges": 0, "top_transitions": []}
    
    nodes = len(data.get("nodes", []))
    edges = len(data.get("edges", []))
    transitions = data.get("transitions", [])
    
    return {
        "nodes": nodes,
        "edges": edges,
        "top_transitions": sorted(transitions, key=lambda x: x.get("count", 0), reverse=True)[:5] if transitions else [],
    }


def get_cycle_store_metrics(artifacts_dir: Path) -> Dict[str, Any]:
    """Extract cycle store metrics."""
    memory_path = artifacts_dir / "cycle_memory.json"
    data = load_json(memory_path)
    if not data:
        return {"count": 0, "candidates": 0}
    
    cycles = data.get("cycles", [])
    return {
        "count": len(cycles),
        "candidates": sum(len(c.get("candidates", [])) for c in cycles),
    }


def get_prior_metrics(ab_report_path: Optional[Path]) -> Dict[str, Any]:
    """Extract prior metrics from A/B report."""
    data = load_json(ab_report_path)
    if not data:
        return {
            "enabled": False,
            "bias_p95": None,
            "near_cap_rate": None,
            "nightly_gate_ready": None,
        }
    
    agg = data.get("aggregate", {})
    bias = agg.get("bias_strength", {})
    rec = agg.get("recommendation", {})
    
    return {
        "enabled": True,
        "bias_p95": bias.get("p95"),
        "near_cap_rate": bias.get("near_cap_rate_mean"),
        "nightly_gate_ready": rec.get("nightly_gate_ready"),
        "pairs": data.get("summary", {}).get("pairs", 0),
    }


def get_concentration_metrics(artifacts_dir: Path) -> Dict[str, Any]:
    """Compute signature concentration from latest run."""
    events_files = list(artifacts_dir.glob("mvp11_*.jsonl"))
    if not events_files:
        return {"phi_top1_share": None, "phi_top3_share": None, "phi_hhi": None}
    
    latest = max(events_files, key=lambda p: p.stat().st_mtime)
    
    signatures = []
    try:
        with open(latest, "r", encoding="utf-8") as f:
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
        return {"phi_top1_share": None, "phi_top3_share": None, "phi_hhi": None}
    
    if not signatures:
        return {"phi_top1_share": 0.0, "phi_top3_share": 0.0, "phi_hhi": 0.0}
    
    counts = Counter(signatures)
    total = len(signatures)
    sorted_counts = sorted(counts.values(), reverse=True)
    
    top1_share = sorted_counts[0] / total if sorted_counts else 0.0
    top3_share = sum(sorted_counts[:3]) / total if len(sorted_counts) >= 3 else sum(sorted_counts) / total
    hhi = sum((c / total) ** 2 for c in counts.values())
    
    return {
        "phi_top1_share": round(top1_share, 6),
        "phi_top3_share": round(top3_share, 6),
        "phi_hhi": round(hhi, 6),
    }


def export_trend_entry(
    dashboard: Dict[str, Any],
    profile: Dict[str, Any],
    gate: Dict[str, Any],
    effects: Optional[Dict[str, Any]] = None,
    *,
    artifacts_dir: Path,
    ab_report_path: Optional[Path] = None,
    commit: str,
    date_utc: str,
) -> Dict[str, Any]:
    effects = effects or {}
    
    gate_rows = gate.get("gates") or []
    g1 = gate_rows[0] if len(gate_rows) > 0 else {}
    g2 = gate_rows[1] if len(gate_rows) > 1 else {}
    g3 = gate_rows[2] if len(gate_rows) > 2 else {}

    config = profile.get("config") or {}
    sentinel_selected = config.get("sentinel_scenarios_selected") or []
    
    def gate_state(row: Dict[str, Any]) -> str:
        if not row:
            return "UNKNOWN"
        if row.get("skipped") or row.get("observed") == "SKIPPED_C3_OFF":
            return "SKIPPED_C3_OFF"
        return "PASS" if bool(row.get("pass")) else "FAIL"
    
    def metric_dist(key: str) -> Dict[str, float]:
        node = (((profile.get("profile") or {}).get("distribution") or {}).get(key) or {})
        return {
            "p50": float(node.get("p50", 0.0) or 0.0),
            "p95": float(node.get("p95", 0.0) or 0.0),
        }
    
    def effects_status() -> Dict[str, str]:
        status = {
            "open_loop": "UNKNOWN",
            "remove_self_state": "UNKNOWN",
            "disable_homeostasis": "UNKNOWN",
            "disable_broadcast": "UNKNOWN",
        }
        
        assertions = effects.get("structural_assertions") or []
        for row in assertions:
            name = str(row.get("name", "")).lower()
            st = "PASS" if bool(row.get("pass")) else "FAIL"
            if "open_loop" in name:
                status["open_loop"] = st
            elif "remove_self_state" in name:
                status["remove_self_state"] = st
            elif "disable_homeostasis" in name:
                status["disable_homeostasis"] = st
            elif "disable_broadcast" in name:
                status["disable_broadcast"] = st
        
        matrix = effects.get("effects") or {}
        if status["disable_broadcast"] == "UNKNOWN" and "P1" in matrix:
            status["disable_broadcast"] = "PASS"
        
        return status

    out = {
        "date_utc": date_utc,
        "commit": commit,
        "sentinel": {
            "scenario": sentinel_selected[0] if sentinel_selected else "unknown",
            "rotation_mode": config.get("sentinel_rotation_mode", "unknown"),
        },
        "gate": {
            "overall": "PASS" if bool(gate.get("overall_pass")) else "FAIL",
            "gate1": gate_state(g1),
            "gate2": gate_state(g2),
            "gate3": gate_state(g3),
        },
        "metrics": {
            "cycle_persistence_score": metric_dist("cycle_persistence_score"),
            "dot_ratio": metric_dist("dot_ratio"),
            "return_time_p95": float(metric_dist("return_time_p95").get("p95", 0.0)),
            "order_invariance": {
                "score": metric_dist("order_invariance_score"),
                "action_multiset": metric_dist("order_invariance_action_multiset"),
                "goal_closure": metric_dist("order_invariance_goal_closure"),
            },
            "sanity_ok_coverage": float(((profile.get("profile") or {}).get("sanity_ok_coverage", 0.0) or 0.0)),
        },
        "cycle_store": {
            "entries": int(((dashboard.get("cycle_store") or {}).get("entries", 0) or 0)),
            "evicted_entries": int(((dashboard.get("cycle_store") or {}).get("evicted_entries", 0) or 0)),
            "dedupe_rate": float(((dashboard.get("cycle_store") or {}).get("dedupe_rate", 0.0) or 0.0)),
        },
        # MVP11.4: Cycle graph and memory
        "cycle_graph": get_cycle_graph_metrics(artifacts_dir),
        "cycle_memory": get_cycle_store_metrics(artifacts_dir),
        # MVP11.4: Prior metrics
        "prior": get_prior_metrics(ab_report_path),
        # MVP11.4.2: Concentration metrics
        "concentration": get_concentration_metrics(artifacts_dir),
        "effects": effects_status(),
        "threshold_recommendations": ((profile.get("profile") or {}).get("threshold_recommendations") or {}),
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dashboard", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--gate", required=True)
    ap.add_argument("--effects", default="")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--ab-report", default="")
    ap.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--date-utc", default="")
    ap.add_argument("--out", default="artifacts/mvp11/trends/trend_entry.json")
    args = ap.parse_args()

    dashboard_path = Path(args.dashboard)
    profile_path = Path(args.profile)
    gate_path = Path(args.gate)
    effects_path = Path(args.effects) if args.effects else None
    artifacts_dir = Path(args.artifacts_dir)
    ab_report_path = Path(args.ab_report) if args.ab_report else None

    dashboard = load_json(dashboard_path) or {}
    profile = load_json(profile_path) or {}
    gate = load_json(gate_path) or {}
    effects = load_json(effects_path) if effects_path else {}

    date_utc = args.date_utc or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit = args.commit or "unknown"

    payload = export_trend_entry(
        dashboard, profile, gate, effects,
        artifacts_dir=artifacts_dir,
        ab_report_path=ab_report_path,
        commit=commit,
        date_utc=date_utc,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "output": str(out),
        "date_utc": payload["date_utc"],
        "cycle_graph_nodes": payload["cycle_graph"]["nodes"],
        "prior_enabled": payload["prior"]["enabled"],
        "phi_top1_share": payload["concentration"].get("phi_top1_share"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
