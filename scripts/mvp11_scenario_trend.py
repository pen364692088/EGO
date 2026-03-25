#!/usr/bin/env python3
"""MVP11 Scenario-Stratified 7-Day Trend.

Eliminates sentinel rotation noise by grouping trends by scenario.

Key insight: Mixed baseline/focused/wide trends cause false drift alerts.
Stratifying by scenario provides cleaner signals for Hard Gate.

Usage:
    python scripts/mvp11_scenario_trend.py \
        --trend-dir artifacts/mvp11/trends \
        --out-dir artifacts/mvp11/trends/scenario_stratified
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_all_trend_entries(trend_dir: Path) -> List[Dict[str, Any]]:
    """Load all available trend entries."""
    entries = []
    
    # Load current entry
    current = trend_dir / "trend_entry.json"
    if current.exists():
        try:
            entries.append(json.loads(current.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IOError):
            pass
    
    # Load 7-day trend
    trend_7d = trend_dir / "trend_7d.json"
    if trend_7d.exists():
        try:
            data = json.loads(trend_7d.read_text(encoding="utf-8"))
            if isinstance(data.get("entries"), list):
                entries.extend(data["entries"])
        except (json.JSONDecodeError, IOError):
            pass
    
    # Dedupe by date
    seen = set()
    unique = []
    for e in sorted(entries, key=lambda x: x.get("date_utc", ""), reverse=True):
        date = e.get("date_utc")
        if date and date not in seen:
            seen.add(date)
            unique.append(e)
    
    return unique


def extract_scenario_from_entry(entry: Dict[str, Any]) -> str:
    """Extract scenario from trend entry."""
    # Try sentinel scenario first
    sentinel = entry.get("sentinel", {})
    scenario = sentinel.get("scenario")
    if scenario:
        return scenario
    
    # Fallback to extracting from metrics
    metrics = entry.get("metrics", {})
    # Could have per-scenario breakdown
    
    return "unknown"


def stratify_by_scenario(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group entries by scenario."""
    stratified = defaultdict(list)
    
    for e in entries:
        scenario = extract_scenario_from_entry(e)
        stratified[scenario].append(e)
    
    return dict(stratified)


def compute_scenario_metrics(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics for a scenario."""
    if not entries:
        return {}
    
    # Extract metrics over time
    cycle_persistence = []
    dot_ratio = []
    novelty_ratio = []
    top1_share = []
    
    for e in entries:
        metrics = e.get("metrics", {})
        
        cp = metrics.get("cycle_persistence_score", {})
        if isinstance(cp, dict) and "p50" in cp:
            cycle_persistence.append(cp["p50"])
        
        dr = metrics.get("dot_ratio", {})
        if isinstance(dr, dict) and "p50" in dr:
            dot_ratio.append(dr["p50"])
        
        conc = e.get("concentration", {})
        if conc.get("phi_top1_share") is not None:
            top1_share.append(conc["phi_top1_share"])
    
    def trend(vals: List[float]) -> str:
        if len(vals) < 2:
            return "insufficient_data"
        if vals[-1] > vals[0] * 1.05:
            return "increasing"
        if vals[-1] < vals[0] * 0.95:
            return "decreasing"
        return "stable"
    
    return {
        "entries": len(entries),
        "date_range": {
            "start": entries[-1].get("date_utc") if entries else None,
            "end": entries[0].get("date_utc") if entries else None,
        },
        "cycle_persistence_score": {
            "values": cycle_persistence,
            "trend": trend(cycle_persistence),
            "mean": sum(cycle_persistence) / len(cycle_persistence) if cycle_persistence else None,
        },
        "dot_ratio": {
            "values": dot_ratio,
            "trend": trend(dot_ratio),
            "mean": sum(dot_ratio) / len(dot_ratio) if dot_ratio else None,
        },
        "concentration_top1": {
            "values": top1_share,
            "trend": trend(top1_share),
            "mean": sum(top1_share) / len(top1_share) if top1_share else None,
        },
    }


def render_scenario_trend_md(report: Dict[str, Any]) -> str:
    """Render scenario-stratified trend as markdown."""
    lines = [
        "# MVP11 Scenario-Stratified 7-Day Trend",
        "",
        f"**Generated**: `{report.get('ts_iso', 'unknown')}`",
        f"**Total Entries**: `{report.get('total_entries', 0)}`",
        "",
        "## Scenario Breakdown",
        "",
    ]
    
    for scenario, data in sorted(report.get("scenarios", {}).items()):
        lines.extend([
            f"### {scenario}",
            "",
            f"- **Entries**: `{data.get('entries', 0)}`",
            f"- **Date Range**: `{data.get('date_range', {}).get('start', 'N/A')}` to `{data.get('date_range', {}).get('end', 'N/A')}`",
            "",
        ])
        
        metrics = data.get("metrics", {})
        
        for mk in ["cycle_persistence_score", "dot_ratio", "concentration_top1"]:
            m = metrics.get(mk, {})
            if m.get("mean") is not None:
                trend_emoji = "📈" if m.get("trend") == "increasing" else "📉" if m.get("trend") == "decreasing" else "➡️"
                lines.append(f"- **{mk}**: `{m['mean']:.4f}` {trend_emoji} ({m.get('trend', 'unknown')})")
        
        lines.append("")
    
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trend-dir", default="artifacts/mvp11/trends")
    ap.add_argument("--out-dir", default="artifacts/mvp11/trends/scenario_stratified")
    args = ap.parse_args()
    
    trend_dir = Path(args.trend_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    entries = load_all_trend_entries(trend_dir)
    print(f"[INFO] Loaded {len(entries)} total entries", flush=True)
    
    stratified = stratify_by_scenario(entries)
    print(f"[INFO] Stratified into {len(stratified)} scenarios", flush=True)
    
    # Compute metrics per scenario
    scenario_metrics = {}
    for scenario, scenario_entries in stratified.items():
        scenario_metrics[scenario] = {
            "entries": len(scenario_entries),
            "date_range": {
                "start": scenario_entries[-1].get("date_utc") if scenario_entries else None,
                "end": scenario_entries[0].get("date_utc") if scenario_entries else None,
            },
            "metrics": compute_scenario_metrics(scenario_entries),
        }
    
    report = {
        "schema_version": "mvp11.scenario_trend.v1",
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_entries": len(entries),
        "scenarios": scenario_metrics,
    }
    
    # Write outputs
    out_json = out_dir / "scenario_trend.json"
    out_md = out_dir / "scenario_trend.md"
    
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_scenario_trend_md(report), encoding="utf-8")
    
    print(json.dumps({
        "output_json": str(out_json),
        "output_md": str(out_md),
        "scenarios": list(stratified.keys()),
        "total_entries": len(entries),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
