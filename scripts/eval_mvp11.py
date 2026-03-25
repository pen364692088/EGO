#!/usr/bin/env python3
"""MVP11 evaluator: quick/science/replay (+ cycle evidence)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics, render_cycle_markdown
from scripts.replay_mvp11 import load_run, replay_run


MODE_DEFAULT_TICKS = {
    "quick": 120,
    "science": 600,
}


def compute_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(events)
    if n == 0:
        return {
            "events": 0,
            "focus_switch_rate": 0.0,
            "replan_rate": 0.0,
            "governor_block_rate": 0.0,
            "homeostasis_drift_mean": 0.0,
        }

    switch = sum(1 for e in events if e.get("focus_switch"))
    replan = sum(1 for e in events if (e.get("validation") or {}).get("replan_count", 0) > 0)
    blocks = sum(1 for e in events if (e.get("governor_decision") or {}).get("decision") in {"DENY", "REQUIRE_APPROVAL"})

    drifts: List[float] = []
    for e in events:
        hs = e.get("homeostasis_state") or {}
        if hs:
            vals = [float(v) for v in hs.values()]
            drifts.append(sum(abs(v - 0.75) for v in vals) / max(1, len(vals)))

    return {
        "events": n,
        "focus_switch_rate": round(switch / max(1, n - 1), 6),
        "replan_rate": round(replan / n, 6),
        "governor_block_rate": round(blocks / n, 6),
        "homeostasis_drift_mean": round((sum(drifts) / len(drifts)) if drifts else 0.0, 6),
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


def _write_summary_md(path: Path, lines: List[str]) -> None:
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    path.write_text((existing + "\n" + "\n".join(lines) + "\n").strip() + "\n", encoding="utf-8")


def eval_quick_or_science(mode: str, artifacts_dir: str, seed: int, ticks: int) -> Dict[str, Any]:
    artifacts = Path(artifacts_dir)
    loop = LoopMVP10(seed=seed, artifacts_dir=artifacts_dir, use_mock_planner=True)
    goals = [f"goal_{i}" for i in range(max(16, ticks // 4))]
    loop.start(goals=goals)
    for _ in range(ticks):
        loop.tick()
    summary = loop.stop()

    run_id = summary["run_id"]
    events = load_run(run_id, artifacts_dir=artifacts_dir)
    metrics = compute_metrics(events)
    cycle_metrics = compute_cycle_metrics(events)
    cycle_metrics["cycle_candidates_topK"] = compute_cycle_candidates(events, top_k=10)
    cycle_paths = write_cycle_report(run_id, artifacts, cycle_metrics)

    report = {
        "mode": mode,
        "pass": metrics["events"] == ticks,
        "run_id": run_id,
        "seed": seed,
        "ticks": ticks,
        "artifacts_dir": artifacts_dir,
        "metrics": metrics,
        "cycle_metrics": cycle_metrics,
        "paths": {
            "log": f"{artifacts_dir}/{run_id}.jsonl",
            "summary": f"{artifacts_dir}/summary_{run_id}.json",
            "cycle_report_json": cycle_paths["json"],
            "cycle_report_md": cycle_paths["md"],
        },
        "ts": time.time(),
    }
    return report


def eval_replay(run_id: str, artifacts_dir: str) -> Dict[str, Any]:
    result = replay_run(run_id, artifacts_dir=artifacts_dir)
    return {
        "mode": "replay",
        "pass": ("error" not in result) and result.get("hash_match_rate", 0.0) >= 0.95,
        "run_id": run_id,
        "artifacts_dir": artifacts_dir,
        "replay": result,
        "ts": time.time(),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["quick", "science", "replay"], default="quick")
    ap.add_argument("--run-id", default=None, help="Required for replay mode")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ticks", type=int, default=None)
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    args = ap.parse_args()

    artifacts = Path(args.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    if args.mode == "replay":
        if not args.run_id:
            raise SystemExit("--run-id is required for replay mode")
        report = eval_replay(args.run_id, args.artifacts_dir)
        out_path = artifacts / f"eval_replay_{args.run_id}.json"
    else:
        ticks = args.ticks if args.ticks is not None else MODE_DEFAULT_TICKS[args.mode]
        report = eval_quick_or_science(args.mode, args.artifacts_dir, seed=args.seed, ticks=ticks)
        out_path = artifacts / f"eval_{args.mode}_{report['run_id']}.json"

    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_md = artifacts / "summary.md"
    _write_summary_md(
        summary_md,
        [
            f"## eval {args.mode}",
            f"- pass: {report.get('pass')}",
            f"- run_id: {report.get('run_id')}",
            f"- output: {out_path}",
        ],
    )

    print(json.dumps({"report": report, "output": str(out_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
