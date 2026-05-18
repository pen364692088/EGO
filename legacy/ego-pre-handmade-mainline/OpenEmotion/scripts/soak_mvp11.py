#!/usr/bin/env python3
"""
MVP11 Soak Runner + Metrics Summary + Cycle Evidence

Goal:
- Long-run stability check (10k/100k ticks)
- Output drift/behavior metrics and cycle-closure metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics, render_cycle_markdown
from scripts.replay_mvp11 import load_run


def _safe_get(d: Dict[str, Any], path: str, default=None):
    cur = d
    for k in path.split('.'):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def compute_soak_metrics(events: List[Dict[str, Any]], log_file: Path) -> Dict[str, Any]:
    n = len(events)
    if n == 0:
        return {
            "events": 0,
            "focus_switch_rate": 0.0,
            "replan_rate": 0.0,
            "governor_block_rate": 0.0,
            "homeostasis_drift_mean": 0.0,
            "homeostasis_drift_max": 0.0,
            "log_bytes": log_file.stat().st_size if log_file.exists() else 0,
            "bytes_per_event": 0.0,
        }

    focus_switches = 0
    replan_ticks = 0
    governor_blocks = 0
    drift_vals: List[float] = []

    last_focus = None
    for e in events:
        focus = e.get("chosen_focus")
        if last_focus is not None and focus != last_focus:
            focus_switches += 1
        last_focus = focus

        replan_count = _safe_get(e, "validation.replan_count", 0) or _safe_get(e, "plan.replan_count", 0) or 0
        if replan_count > 0:
            replan_ticks += 1

        decision = _safe_get(e, "governor_decision.decision", "")
        if decision in {"DENY", "REQUIRE_APPROVAL"}:
            governor_blocks += 1

        hs = e.get("homeostasis_state") or {}
        if hs:
            vals = [
                float(hs.get("energy", 1.0)),
                float(hs.get("safety", 1.0)),
                float(hs.get("affiliation", 1.0)),
                float(hs.get("certainty", 1.0)),
                float(hs.get("autonomy", 1.0)),
                float(hs.get("fairness", 1.0)),
            ]
            drift = sum(abs(v - 0.75) for v in vals) / len(vals)
            drift_vals.append(drift)

    log_bytes = log_file.stat().st_size if log_file.exists() else 0

    return {
        "events": n,
        "focus_switch_rate": round(focus_switches / max(1, n - 1), 6),
        "replan_rate": round(replan_ticks / n, 6),
        "governor_block_rate": round(governor_blocks / n, 6),
        "homeostasis_drift_mean": round((sum(drift_vals) / len(drift_vals)) if drift_vals else 0.0, 6),
        "homeostasis_drift_max": round(max(drift_vals) if drift_vals else 0.0, 6),
        "log_bytes": log_bytes,
        "bytes_per_event": round(log_bytes / n, 6),
    }


def write_cycle_report(run_id: str, artifacts: Path, cycle_metrics: Dict[str, Any]) -> Dict[str, str]:
    run_dir = artifacts / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "cycle_report.json"
    md_path = run_dir / "cycle_report.md"

    payload = {
        "run_id": run_id,
        "metrics": cycle_metrics,
        "sanity": cycle_metrics.get("sanity", {}),
        "cycle_candidates_topK": cycle_metrics.get("cycle_candidates_topK", []),
        "ts": time.time(),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_cycle_markdown(run_id, cycle_metrics), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--artifacts", default="artifacts/mvp11")
    ap.add_argument("--out", default="artifacts/mvp11/soak_report.json")
    ap.add_argument("--intervention", default=None)
    args = ap.parse_args()

    artifacts = Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    loop = LoopMVP10(
        seed=args.seed,
        artifacts_dir=str(artifacts),
        use_mock_planner=True,
        intervention=args.intervention,
    )

    goals = [f"soak_goal_{i}" for i in range(args.ticks + 10)]
    loop.start(goals=goals)
    ticks_executed = 0
    for _ in range(args.ticks):
        try:
            loop.tick()
            ticks_executed += 1
        except Exception:
            break
    summary = loop.stop()
    summary["ticks_executed"] = ticks_executed

    run_id = summary.get("run_id") or loop.ledger.run_id
    events = load_run(run_id, artifacts_dir=str(artifacts))
    log_file = artifacts / f"{run_id}.jsonl"

    metrics = compute_soak_metrics(events, log_file)
    cycle_metrics = compute_cycle_metrics(events)
    cycle_metrics["cycle_candidates_topK"] = compute_cycle_candidates(events, top_k=10)
    cycle_paths = write_cycle_report(run_id, artifacts, cycle_metrics)

    report = {
        "run_id": run_id,
        "seed": args.seed,
        "ticks_requested": args.ticks,
        "duration_sec": round(time.time() - t0, 6),
        "summary": summary,
        "metrics": metrics,
        "cycle_metrics": cycle_metrics,
        "paths": {
            "log": str(log_file),
            "cycle_report_json": cycle_paths["json"],
            "cycle_report_md": cycle_paths["md"],
        },
        "ts": time.time(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
