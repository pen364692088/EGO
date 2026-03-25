#!/usr/bin/env python3
"""Run baseline + P1..P4 intervention soak and emit standardized artifacts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.loop_mvp10 import LoopMVP10


INTERVENTIONS: List[Tuple[str, str]] = [
    ("P1", "disable_broadcast"),
    ("P2", "disable_homeostasis"),
    ("P3", "remove_self_state"),
    ("P4", "open_loop"),
]

PROFILE_TICKS = {
    "ci": 200,
    "full": 2000,
}


def _load_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _metrics(events: List[Dict[str, Any]], log_path: Path) -> Dict[str, Any]:
    n = len(events)
    if n == 0:
        return {
            "events": 0,
            "focus_switch_rate": 0.0,
            "replan_rate": 0.0,
            "governor_block_rate": 0.0,
            "homeostasis_drift_mean": 0.0,
            "homeostasis_drift_max": 0.0,
            "bytes_per_event": 0.0,
        }

    focus_switch = sum(1 for e in events if e.get("focus_switch"))
    replan = sum(1 for e in events if (e.get("validation") or {}).get("replan_count", 0) > 0)
    blocked = sum(1 for e in events if (e.get("governor_decision") or {}).get("decision") in {"DENY", "REQUIRE_APPROVAL"})

    drifts: List[float] = []
    for e in events:
        hs = e.get("homeostasis_state") or {}
        if hs:
            vals = [float(v) for v in hs.values()]
            drifts.append(sum(abs(v - 0.75) for v in vals) / max(1, len(vals)))

    log_bytes = log_path.stat().st_size if log_path.exists() else 0

    return {
        "events": n,
        "focus_switch_rate": round(focus_switch / max(1, n - 1), 6),
        "replan_rate": round(replan / n, 6),
        "governor_block_rate": round(blocked / n, 6),
        "homeostasis_drift_mean": round((sum(drifts) / len(drifts)) if drifts else 0.0, 6),
        "homeostasis_drift_max": round(max(drifts) if drifts else 0.0, 6),
        "bytes_per_event": round(log_bytes / n, 2),
    }


def _run_condition(artifacts_dir: str, ticks: int, seed: int, intervention: str | None) -> Dict[str, Any]:
    loop = LoopMVP10(seed=seed, artifacts_dir=artifacts_dir, intervention=intervention, use_mock_planner=True)
    goals = [f"goal_{i}" for i in range(max(16, ticks // 4))]
    loop.start(goals=goals)
    for _ in range(ticks):
        loop.tick()
    summary = loop.stop()

    run_id = summary["run_id"]
    log_path = Path(artifacts_dir) / f"{run_id}.jsonl"
    events = _load_events(log_path)
    return {
        "run_id": run_id,
        "seed": seed,
        "ticks": ticks,
        "intervention": intervention,
        "metrics": _metrics(events, log_path),
        "paths": {
            "log": str(log_path),
            "summary": str(Path(artifacts_dir) / f"summary_{run_id}.json"),
        },
    }


def _effect_sizes(baseline: Dict[str, Any], condition: Dict[str, Any]) -> Dict[str, float]:
    keys = [
        "focus_switch_rate",
        "replan_rate",
        "governor_block_rate",
        "homeostasis_drift_mean",
        "homeostasis_drift_max",
    ]
    out: Dict[str, float] = {}
    for k in keys:
        out[k] = round(float(condition["metrics"].get(k, 0.0)) - float(baseline["metrics"].get(k, 0.0)), 6)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--profile", choices=["ci", "full"], default="full")
    args = ap.parse_args()

    artifacts = Path(args.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)

    ticks = args.ticks if args.ticks is not None else PROFILE_TICKS[args.profile]

    baseline = _run_condition(args.artifacts_dir, ticks=ticks, seed=args.seed, intervention=None)

    interventions_meta: List[Dict[str, Any]] = []
    condition_results: Dict[str, Dict[str, Any]] = {}
    effects: Dict[str, Dict[str, float]] = {}

    for idx, (pid, kind) in enumerate(INTERVENTIONS, start=1):
        cond_seed = args.seed + idx
        result = _run_condition(args.artifacts_dir, ticks=ticks, seed=cond_seed, intervention=kind)
        condition_results[pid] = result
        effects[pid] = _effect_sizes(baseline, result)
        interventions_meta.append(
            {
                "id": pid,
                "kind": kind,
                "seed": cond_seed,
                "run_id": result["run_id"],
                "metrics": result["metrics"],
            }
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {
        "profile": args.profile,
        "ticks": ticks,
        "seed": args.seed,
        "baseline": baseline,
        "conditions": condition_results,
        "effect_sizes": effects,
        "ts": time.time(),
    }

    report_path = artifacts / f"full_soak_report_{ts}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    interventions_path = artifacts / "interventions.json"
    interventions_path.write_text(json.dumps({"interventions": interventions_meta}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "report_path": str(report_path),
                "interventions_path": str(interventions_path),
                "ticks": ticks,
                "profile": args.profile,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
