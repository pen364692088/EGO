#!/usr/bin/env python3
"""MVP11.3 soak profile runner for distribution-level gating.

Generates a distribution profile across scenario × seed for Gate-L prep.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics
from scripts.replay_mvp11 import load_run
from scripts.soak_mvp11 import compute_soak_metrics


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, int(round((len(sorted_vals) - 1) * p))))
    return float(sorted_vals[idx])


def _parse_csv(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _parse_int_csv(value: str) -> List[int]:
    out = []
    for token in _parse_csv(value):
        out.append(int(token))
    return out


def _goals_for_scenario(scenario: str, ticks: int, seed: int) -> List[str]:
    rng = random.Random(seed)
    n = ticks + 10

    if scenario == "baseline":
        return [f"goal_{i}" for i in range(n)]

    if scenario == "focused":
        pool = [f"focus_goal_{i}" for i in range(8)]
        return [pool[i % len(pool)] for i in range(n)]

    if scenario == "wide":
        pool = [f"wide_goal_{i}" for i in range(64)]
        return [pool[rng.randint(0, len(pool) - 1)] for _ in range(n)]

    # fallback custom scenario id
    pool = [f"{scenario}_goal_{i}" for i in range(16)]
    return [pool[rng.randint(0, len(pool) - 1)] for _ in range(n)]




def _select_sentinel_scenarios(
    sentinel_pool: List[str],
    *,
    rotation_mode: str,
    day_index_override: int = -1,
) -> List[str]:
    if not sentinel_pool:
        return []

    mode = (rotation_mode or "weekday").lower()

    if mode == "all":
        return sentinel_pool

    if mode == "first":
        return [sentinel_pool[0]]

    # weekday rotation (default): Monday->idx0, Tuesday->idx1 ...
    if day_index_override >= 0:
        day_idx = day_index_override
    else:
        day_idx = datetime.now(timezone.utc).weekday()

    pick = day_idx % len(sentinel_pool)
    return [sentinel_pool[pick]]

def _cleanup_run_files(artifacts_dir: Path, run_id: str) -> None:
    targets = [
        artifacts_dir / f"{run_id}.jsonl",
        artifacts_dir / f"summary_{run_id}.json",
    ]
    for p in targets:
        if p.exists():
            p.unlink(missing_ok=True)


def run_profile_once(
    *,
    artifacts_dir: Path,
    scenario: str,
    seed: int,
    ticks: int,
    intervention: Optional[str] = None,
    cleanup_logs: bool = True,
) -> Dict[str, Any]:
    t0 = time.time()

    loop = LoopMVP10(
        seed=seed,
        artifacts_dir=str(artifacts_dir),
        intervention=intervention,
        use_mock_planner=True,
    )

    goals = _goals_for_scenario(scenario, ticks=ticks, seed=seed)
    loop.start(goals=goals)

    ticks_executed = 0
    for _ in range(ticks):
        loop.tick()
        ticks_executed += 1

    summary = loop.stop()
    run_id = summary.get("run_id") or loop.ledger.run_id

    events = load_run(run_id, artifacts_dir=str(artifacts_dir))
    log_file = artifacts_dir / f"{run_id}.jsonl"

    behavior_metrics = compute_soak_metrics(events, log_file)
    cycle_metrics = compute_cycle_metrics(events)
    cycle_metrics["cycle_candidates_topK"] = compute_cycle_candidates(events, top_k=10)

    out = {
        "run_id": run_id,
        "scenario": scenario,
        "seed": seed,
        "ticks_requested": ticks,
        "ticks_executed": ticks_executed,
        "intervention": intervention,
        "duration_sec": round(time.time() - t0, 6),
        "metrics": behavior_metrics,
        "cycle_metrics": cycle_metrics,
        "sanity": cycle_metrics.get("sanity", {}),
    }

    if cleanup_logs:
        _cleanup_run_files(artifacts_dir, run_id)

    return out


def _aggregate_metric(rows: List[Dict[str, Any]], path: List[str]) -> Dict[str, float]:
    vals: List[float] = []
    for row in rows:
        cur: Any = row
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                cur = None
                break
        if isinstance(cur, (int, float)):
            vals.append(float(cur))

    if not vals:
        return {
            "count": 0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "max": 0.0,
        }

    return {
        "count": len(vals),
        "mean": round(statistics.mean(vals), 6),
        "std": round(statistics.stdev(vals), 6) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 6),
        "p50": round(_percentile(vals, 0.5), 6),
        "p95": round(_percentile(vals, 0.95), 6),
        "max": round(max(vals), 6),
    }


def build_distribution_report(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    sanity_ok = sum(1 for r in runs if (r.get("sanity") or {}).get("status") == "OK")
    total = len(runs)

    dist = {
        "cycle_persistence_score": _aggregate_metric(runs, ["cycle_metrics", "cycle_persistence_score"]),
        "dot_ratio": _aggregate_metric(runs, ["cycle_metrics", "dot_ratio"]),
        "return_time_p95": _aggregate_metric(runs, ["cycle_metrics", "return_time_p95"]),
        "governor_block_rate": _aggregate_metric(runs, ["metrics", "governor_block_rate"]),
        "homeostasis_drift_mean": _aggregate_metric(runs, ["metrics", "homeostasis_drift_mean"]),
        "order_invariance_score": _aggregate_metric(runs, ["cycle_metrics", "order_invariance_score"]),
        "order_invariance_action_multiset": _aggregate_metric(runs, ["cycle_metrics", "order_invariance_action_multiset"]),
        "order_invariance_goal_closure": _aggregate_metric(runs, ["cycle_metrics", "order_invariance_goal_closure"]),
    }

    thresholds = {
        "sanity_ok_rate_min": 0.99,
        "cycle_persistence_score_range": {
            "min": dist["cycle_persistence_score"]["min"],
            "max": dist["cycle_persistence_score"]["p95"],
        },
        "dot_ratio_range": {
            "min": dist["dot_ratio"]["min"],
            "max": dist["dot_ratio"]["p95"],
        },
        "return_time_p95_max": dist["return_time_p95"]["p95"],
        "governor_block_rate_max": dist["governor_block_rate"]["p95"],
        "homeostasis_drift_mean_max": dist["homeostasis_drift_mean"]["p95"],
    }

    return {
        "runs": runs,
        "distribution": dist,
        "threshold_recommendations": thresholds,
        "sanity_ok_coverage": round(sanity_ok / total, 6) if total else 0.0,
        "sanity_status_counts": {
            "OK": sanity_ok,
            "WARN_INCONSISTENT": total - sanity_ok,
            "total": total,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")
    ap.add_argument("--scenarios", default="baseline,focused,wide")
    ap.add_argument("--seeds", default="41,42,43,44,45")
    ap.add_argument("--ticks", type=int, default=10000)
    ap.add_argument("--sentinel-ticks", type=int, default=100000)
    ap.add_argument("--sentinel-seeds", default="42")
    ap.add_argument("--sentinel-scenarios", default="")
    ap.add_argument("--sentinel-rotation-mode", choices=["weekday", "first", "all"], default="weekday")
    ap.add_argument("--sentinel-day-index", type=int, default=-1, help="override weekday index for deterministic rotation")
    ap.add_argument("--cleanup-logs", type=int, default=1)
    ap.add_argument("--output", default="artifacts/mvp11/profiles/soak_profile.json")
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    scenarios = _parse_csv(args.scenarios)
    seeds = _parse_int_csv(args.seeds)
    sentinel_seeds = _parse_int_csv(args.sentinel_seeds)
    sentinel_pool = _parse_csv(args.sentinel_scenarios) or scenarios
    sentinel_scenarios = _select_sentinel_scenarios(
        sentinel_pool,
        rotation_mode=args.sentinel_rotation_mode,
        day_index_override=args.sentinel_day_index,
    )

    runs: List[Dict[str, Any]] = []

    # Gate-1 coverage profile: scenario × seed × 10k ticks
    for scenario in scenarios:
        for seed in seeds:
            runs.append(
                run_profile_once(
                    artifacts_dir=artifacts_dir,
                    scenario=scenario,
                    seed=seed,
                    ticks=args.ticks,
                    cleanup_logs=bool(args.cleanup_logs),
                )
            )

    # Optional long-run sentinel (100k) for tail monitoring.
    sentinel_runs: List[Dict[str, Any]] = []
    for scenario in sentinel_scenarios:
        for seed in sentinel_seeds:
            sentinel_runs.append(
                run_profile_once(
                    artifacts_dir=artifacts_dir,
                    scenario=scenario,
                    seed=seed,
                    ticks=args.sentinel_ticks,
                    cleanup_logs=bool(args.cleanup_logs),
                )
            )

    dist_report = build_distribution_report(runs)

    payload = {
        "schema_version": "mvp11.cycle_profile.v1",
        "ts": time.time(),
        "config": {
            "scenarios": scenarios,
            "seeds": seeds,
            "ticks": args.ticks,
            "sentinel_ticks": args.sentinel_ticks,
            "sentinel_seeds": sentinel_seeds,
            "sentinel_scenarios_pool": sentinel_pool,
            "sentinel_scenarios_selected": sentinel_scenarios,
            "sentinel_rotation_mode": args.sentinel_rotation_mode,
            "sentinel_day_index": args.sentinel_day_index,
            "cleanup_logs": bool(args.cleanup_logs),
        },
        "profile": dist_report,
        "sentinel_100k": sentinel_runs,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"output": str(out), "sanity_ok_coverage": payload["profile"]["sanity_ok_coverage"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
