#!/usr/bin/env python3
"""MVP11 cycle-aware effect size evaluator.

Modes:
1) Matrix mode (default): run baseline vs P1~P4 and emit cycle effects.
2) Legacy mode: compare two soak reports via --baseline/--intervention.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.cycle import compute_cycle_candidates, compute_cycle_metrics
from scripts.replay_mvp11 import load_run


INTERVENTIONS: List[Tuple[str, str]] = [
    ("P1", "disable_broadcast"),
    ("P2", "disable_homeostasis"),
    ("P3", "remove_self_state"),
    ("P4", "open_loop"),
]

METRIC_KEYS = [
    "focus_switch_rate",
    "replan_rate",
    "governor_block_rate",
    "homeostasis_drift_mean",
    "dot_ratio",
    "cycle_persistence_score",
    "return_time_mean",
    "order_invariance_score",
    "cycle_candidate_count",
]


@dataclass
class RunSample:
    run_id: str
    seed: int
    intervention: Optional[str]
    ticks: int
    metrics: Dict[str, float]


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.stdev(values)


def cohens_d(mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int) -> float:
    if n1 < 2 or n2 < 2:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / max(1, (n1 + n2 - 2))
    pooled_std = math.sqrt(max(1e-12, pooled_var))
    return (mean2 - mean1) / pooled_std


def _behavior_metrics(events: List[Dict[str, Any]]) -> Dict[str, float]:
    n = len(events)
    if n == 0:
        return {
            "focus_switch_rate": 0.0,
            "replan_rate": 0.0,
            "governor_block_rate": 0.0,
            "homeostasis_drift_mean": 0.0,
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

    return {
        "focus_switch_rate": round(focus_switch / max(1, n - 1), 6),
        "replan_rate": round(replan / n, 6),
        "governor_block_rate": round(blocked / n, 6),
        "homeostasis_drift_mean": round((sum(drifts) / len(drifts)) if drifts else 0.0, 6),
    }


def collect_run_sample(ticks: int, seed: int, artifacts_dir: Path, intervention: Optional[str]) -> RunSample:
    loop = LoopMVP10(seed=seed, artifacts_dir=str(artifacts_dir), intervention=intervention, use_mock_planner=True)
    goals = [f"goal_{i}" for i in range(max(24, ticks // 3))]
    loop.start(goals=goals)
    for _ in range(ticks):
        loop.tick()
    summary = loop.stop()

    run_id = summary["run_id"]
    events = load_run(run_id, artifacts_dir=str(artifacts_dir))

    metrics: Dict[str, float] = {}
    metrics.update(_behavior_metrics(events))

    cm = compute_cycle_metrics(events)
    candidates = compute_cycle_candidates(events, top_k=10)
    metrics.update(
        {
            "dot_ratio": float(cm.get("dot_ratio", 0.0)),
            "cycle_persistence_score": float(cm.get("cycle_persistence_score", 0.0)),
            "return_time_mean": float(cm.get("return_time_mean", 0.0)),
            "order_invariance_score": float(cm.get("order_invariance_score", 0.0)),
            "cycle_candidate_count": float(len(candidates)),
        }
    )

    return RunSample(run_id=run_id, seed=seed, intervention=intervention, ticks=ticks, metrics=metrics)


def aggregate(samples: List[RunSample], key: str) -> Tuple[float, float, int]:
    vals = [float(s.metrics.get(key, 0.0)) for s in samples]
    if not vals:
        return 0.0, 0.0, 0
    return statistics.mean(vals), _std(vals), len(vals)


def compute_effects(baseline: List[RunSample], condition: List[RunSample]) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for key in METRIC_KEYS:
        b_mean, b_std, b_n = aggregate(baseline, key)
        c_mean, c_std, c_n = aggregate(condition, key)
        out[key] = {
            "baseline_mean": round(b_mean, 6),
            "baseline_std": round(b_std, 6),
            "intervention_mean": round(c_mean, 6),
            "intervention_std": round(c_std, 6),
            "delta": round(c_mean - b_mean, 6),
            "cohens_d": round(cohens_d(b_mean, b_std, b_n, c_mean, c_std, c_n), 6),
            "n_baseline": b_n,
            "n_intervention": c_n,
        }
    return out


def evaluate_structural_assertions(effects: Dict[str, Dict[str, Dict[str, float]]]) -> List[Dict[str, Any]]:
    checks = [
        {
            "name": "open_loop lowers cycle persistence",
            "condition": "P4",
            "metric": "cycle_persistence_score",
            "expected": "delta < 0",
            "pass": effects.get("P4", {}).get("cycle_persistence_score", {}).get("delta", 0.0) < 0,
        },
        {
            "name": "open_loop increases dot ratio",
            "condition": "P4",
            "metric": "dot_ratio",
            "expected": "delta > 0",
            "pass": effects.get("P4", {}).get("dot_ratio", {}).get("delta", 0.0) > 0,
        },
        {
            "name": "remove_self_state weakens self-cycle structure",
            "condition": "P3",
            "metric": "cycle_candidate_count|order_invariance_score",
            "expected": "candidate_delta < 0 OR order_invariance_delta < 0",
            "pass": (
                effects.get("P3", {}).get("cycle_candidate_count", {}).get("delta", 0.0) < 0
                or effects.get("P3", {}).get("order_invariance_score", {}).get("delta", 0.0) < 0
            ),
        },
        {
            "name": "disable_homeostasis weakens closure",
            "condition": "P2",
            "metric": "cycle_persistence_score",
            "expected": "delta < 0",
            "pass": effects.get("P2", {}).get("cycle_persistence_score", {}).get("delta", 0.0) < 0,
        },
    ]
    return checks


def render_markdown(output: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# MVP11 Cycle Effect Size Report",
        "",
        f"- profile: `{output.get('profile')}`",
        f"- ticks: `{output.get('ticks')}`",
        f"- runs_per_condition: `{output.get('runs')}`",
        "",
    ]

    for pid, kind in INTERVENTIONS:
        effects = output["effects"].get(pid, {})
        lines.append(f"## {pid} · {kind}")
        lines.append("")
        lines.append("| metric | baseline | intervention | Δ | d |")
        lines.append("|---|---:|---:|---:|---:|")
        for key in METRIC_KEYS:
            e = effects.get(key, {})
            lines.append(
                f"| {key} | {e.get('baseline_mean', 0.0):.6f} | {e.get('intervention_mean', 0.0):.6f} | {e.get('delta', 0.0):+.6f} | {e.get('cohens_d', 0.0):.6f} |"
            )
        lines.append("")

    lines.append("## Structural Assertions")
    lines.append("")
    lines.append("| check | expected | result |")
    lines.append("|---|---|---|")
    for row in output.get("structural_assertions", []):
        icon = "✅" if row.get("pass") else "⚠️"
        lines.append(f"| {row.get('name')} | {row.get('expected')} | {icon} |")
    lines.append("")
    lines.append("- 注：⚠️ 不代表失败，只表示该干预与当前指标定义不一致，需要回看机制或指标定义。")
    lines.append("")
    return "\n".join(lines)


def legacy_mode(baseline_path: Path, intervention_path: Path, out_path: Path) -> Dict[str, Any]:
    b = json.loads(baseline_path.read_text(encoding="utf-8"))
    i = json.loads(intervention_path.read_text(encoding="utf-8"))

    b_metrics = b.get("metrics", {})
    i_metrics = i.get("metrics", {})

    out: Dict[str, Any] = {
        "baseline_run_id": b.get("run_id"),
        "intervention_run_id": i.get("run_id"),
        "effect_size": {},
        "mode": "legacy",
        "ts": time.time(),
    }

    for k in sorted(set(b_metrics.keys()) | set(i_metrics.keys())):
        try:
            bv = float(b_metrics.get(k, 0.0))
            iv = float(i_metrics.get(k, 0.0))
        except (TypeError, ValueError):
            continue
        out["effect_size"][k] = {
            "baseline": bv,
            "intervention": iv,
            "delta": round(iv - bv, 6),
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()

    # Legacy mode options
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--intervention", default=None)

    # Matrix mode options
    ap.add_argument("--ticks", type=int, default=600)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--profile", choices=["ci", "full"], default="full")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11")

    ap.add_argument("--out", default="artifacts/mvp11/effects/cycle_effects.json")
    ap.add_argument("--out-md", default="artifacts/mvp11/effects/cycle_effects.md")
    args = ap.parse_args()

    out_path = Path(args.out)

    # Legacy mode: keep backward compatibility.
    if args.baseline and args.intervention:
        result = legacy_mode(Path(args.baseline), Path(args.intervention), out_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    ticks = 200 if args.profile == "ci" else args.ticks

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    baseline_samples: List[RunSample] = []
    for i in range(args.runs):
        baseline_samples.append(
            collect_run_sample(ticks=ticks, seed=args.seed + i, artifacts_dir=artifacts_dir, intervention=None)
        )

    all_condition_samples: Dict[str, List[RunSample]] = {}
    all_effects: Dict[str, Dict[str, Dict[str, float]]] = {}

    for idx, (pid, kind) in enumerate(INTERVENTIONS, start=1):
        cond_samples: List[RunSample] = []
        for i in range(args.runs):
            cond_samples.append(
                collect_run_sample(
                    ticks=ticks,
                    seed=args.seed + 100 * idx + i,
                    artifacts_dir=artifacts_dir,
                    intervention=kind,
                )
            )
        all_condition_samples[pid] = cond_samples
        all_effects[pid] = compute_effects(baseline_samples, cond_samples)

    structural_assertions = evaluate_structural_assertions(all_effects)

    payload = {
        "mode": "matrix",
        "profile": args.profile,
        "ticks": ticks,
        "runs": args.runs,
        "seed": args.seed,
        "effects": all_effects,
        "structural_assertions": structural_assertions,
        "baseline_runs": [s.__dict__ for s in baseline_samples],
        "condition_runs": {
            pid: [s.__dict__ for s in samples] for pid, samples in all_condition_samples.items()
        },
        "ts": time.time(),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = Path(args.out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "output_json": str(out_path),
                "output_md": str(md_path),
                "assertions": structural_assertions,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
