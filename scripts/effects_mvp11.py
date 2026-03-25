#!/usr/bin/env python3
"""
MVP11.2 Effect Size Evaluator for P1~P4 Interventions

Computes effect sizes for 4 causal predictions:
- P1: disable_broadcast -> 跨模块整合/长程规划坍塌
- P2: disable_homeostasis -> 预防性/恢复行为坍塌
- P3: remove_self_state -> 自我校准与缺陷归因坍塌
- P4: open_loop -> 自驱与连续性坍塌

Output:
  - reports/mvp11_effects.json (machine-readable)
  - reports/mvp11_effects.md (markdown table)

Usage:
  python scripts/effects_mvp11.py --ticks 1000 --seed 42 --runs 3
  python scripts/effects_mvp11.py --profile ci
  python scripts/effects_mvp11.py --profile full --output reports/mvp11_effects.json
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.loop_mvp10 import LoopMVP10
from emotiond.science.interventions import InterventionManager, InterventionType

# P1~P4 intervention definitions
INTERVENTIONS = [
    ("P1", "disable_broadcast", InterventionType.DISABLE_BROADCAST, "跨模块整合/长程规划坍塌"),
    ("P2", "disable_homeostasis", InterventionType.DISABLE_HOMEOSTASIS, "预防性/恢复行为坍塌"),
    ("P3", "remove_self_state", InterventionType.REMOVE_SELF_STATE, "自我校准与缺陷归因坍塌"),
    ("P4", "open_loop", InterventionType.OPEN_LOOP, "自驱与连续性坍塌"),
]

METRIC_KEYS = [
    "focus_switch_rate",
    "replan_rate",
    "governor_block_rate",
    "homeostasis_drift_mean",
    "homeostasis_drift_max",
    "bytes_per_event",
]

DEFAULT_CI_TICKS = 200
DEFAULT_FULL_TICKS = 1000
DEFAULT_RUNS = 3
DEFAULT_SEED = 42


@dataclass
class RunResult:
    """Result of a single soak run."""
    run_id: str
    seed: int
    ticks: int
    duration_sec: float
    intervention: Optional[str]
    metrics: Dict[str, Any]


@dataclass
class EffectSizeResult:
    """Effect size computation result."""
    metric: str
    baseline_mean: float
    baseline_std: float
    intervention_mean: float
    intervention_std: float
    delta: float
    cohens_d: float
    n_baseline: int
    n_intervention: int


def cohens_d(mean1: float, std1: float, n1: int, mean2: float, std2: float, n2: int) -> float:
    """Compute Cohen's d effect size."""
    if n1 < 2 or n2 < 2:
        return 0.0
    pooled_var = ((n1 - 1) * (std1 ** 2) + (n2 - 1) * (std2 ** 2)) / max(1, (n1 + n2 - 2))
    pooled_std = math.sqrt(max(1e-12, pooled_var))
    return (mean2 - mean1) / pooled_std


def compute_metrics(run_id: str, artifacts_dir: str) -> Dict[str, Any]:
    """Load and compute metrics from run log."""
    log_path = Path(artifacts_dir) / f"{run_id}.jsonl"
    if not log_path.exists():
        return {"error": "log not found", "events": 0}

    events = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    n = len(events)
    if n == 0:
        return {"events": 0}

    focus_switches = 0
    last_focus = None
    replan_ticks = 0
    governor_blocks = 0
    drift_vals = []

    for e in events:
        focus = e.get("chosen_focus")
        if last_focus is not None and focus != last_focus:
            focus_switches += 1
        last_focus = focus

        validation = e.get("validation", {})
        if validation.get("replan_count", 0) > 0:
            replan_ticks += 1

        decision = e.get("governor_decision", {}).get("decision", "")
        if decision in {"DENY", "REQUIRE_APPROVAL"}:
            governor_blocks += 1

        hs = e.get("homeostasis_state") or {}
        if hs:
            vals = [
                float(hs.get("energy", 0.5)),
                float(hs.get("safety", 0.5)),
                float(hs.get("affiliation", 0.5)),
            ]
            drift = sum(abs(v - 0.75) for v in vals) / len(vals)
            drift_vals.append(drift)

    log_bytes = log_path.stat().st_size

    return {
        "events": n,
        "focus_switch_rate": round(focus_switches / max(1, n - 1), 4),
        "replan_rate": round(replan_ticks / n, 4),
        "governor_block_rate": round(governor_blocks / n, 4),
        "homeostasis_drift_mean": round(sum(drift_vals) / len(drift_vals), 4) if drift_vals else 0,
        "homeostasis_drift_max": round(max(drift_vals), 4) if drift_vals else 0,
        "log_bytes": log_bytes,
        "bytes_per_event": round(log_bytes / n, 2),
    }


def run_soak(ticks: int, seed: int, artifacts_dir: str, 
             intervention_type: Optional[InterventionType] = None,
             intervention_name: Optional[str] = None) -> RunResult:
    """Run a single soak test."""
    t0 = time.time()
    
    loop = LoopMVP10(seed=seed, artifacts_dir=artifacts_dir, use_mock_planner=True)
    
    if intervention_type:
        # Create intervention manager and enable intervention
        manager = InterventionManager()
        manager.enable(intervention_type, {"reason": f"Testing {intervention_name}"})
    
    goals = [f"soak_goal_{i}" for i in range(ticks + 10)]
    loop.start(goals=goals)
    
    ticks_executed = 0
    for _ in range(ticks):
        try:
            loop.tick()
            ticks_executed += 1
        except Exception:
            break
    
    summary = loop.stop()
    run_id = summary.get("run_id", loop.ledger.run_id)
    metrics = compute_metrics(run_id, artifacts_dir)
    duration = time.time() - t0
    
    return RunResult(
        run_id=run_id,
        seed=seed,
        ticks=ticks_executed,
        duration_sec=round(duration, 3),
        intervention=intervention_name,
        metrics=metrics,
    )


def aggregate_runs(results: List[RunResult], metric_key: str) -> Tuple[float, float, int]:
    """Compute mean, std, n for a metric across runs."""
    values = [r.metrics.get(metric_key, 0.0) for r in results]
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0, n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return mean, std, n


def compute_effect_sizes(
    baseline_results: List[RunResult],
    intervention_results: List[RunResult],
    intervention_id: str,
) -> Dict[str, EffectSizeResult]:
    """Compute effect sizes for all metrics between baseline and intervention."""
    effects = {}
    for metric in METRIC_KEYS:
        b_mean, b_std, b_n = aggregate_runs(baseline_results, metric)
        i_mean, i_std, i_n = aggregate_runs(intervention_results, metric)
        
        delta = i_mean - b_mean
        d = cohens_d(b_mean, b_std, b_n, i_mean, i_std, i_n)
        
        effects[metric] = EffectSizeResult(
            metric=metric,
            baseline_mean=round(b_mean, 4),
            baseline_std=round(b_std, 4),
            intervention_mean=round(i_mean, 4),
            intervention_std=round(i_std, 4),
            delta=round(delta, 4),
            cohens_d=round(d, 4),
            n_baseline=b_n,
            n_intervention=i_n,
        )
    return effects


def generate_markdown_table(effects_by_intervention: Dict[str, Dict[str, EffectSizeResult]]) -> str:
    """Generate markdown table from effect sizes."""
    lines = []
    lines.append("# MVP11 Effect Size Report")
    lines.append("")
    lines.append("## Metrics by Intervention")
    lines.append("")
    
    # Header
    header = "| Metric | Baseline | Intervention | Δ | Cohen's d |"
    separator = "|--------|----------|--------------|---|-----------|"
    
    for int_id, int_name, _, int_desc in INTERVENTIONS:
        effects = effects_by_intervention.get(int_id, {})
        if not effects:
            continue
        
        lines.append(f"### {int_id}: {int_desc}")
        lines.append("")
        lines.append(header)
        lines.append(separator)
        
        for metric in METRIC_KEYS:
            if metric not in effects:
                continue
            e = effects[metric]
            lines.append(f"| {metric} | {e.baseline_mean:.4f} | {e.intervention_mean:.4f} | {e.delta:+.4f} | {e.cohens_d:.4f} |")
        
        lines.append("")
    
    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Intervention | Description | Avg |d| |")
    lines.append("|--------------|-------------|-------|")
    
    for int_id, int_name, _, int_desc in INTERVENTIONS:
        effects = effects_by_intervention.get(int_id, {})
        if not effects:
            continue
        avg_d = sum(e.cohens_d for e in effects.values()) / len(effects) if effects else 0
        lines.append(f"| {int_id} | {int_desc} | {avg_d:.4f} |")
    
    lines.append("")
    lines.append("### Interpretation")
    lines.append("")
    lines.append("- |d| < 0.2: negligible effect")
    lines.append("- 0.2 ≤ |d| < 0.5: small effect")
    lines.append("- 0.5 ≤ |d| < 0.8: medium effect")
    lines.append("- |d| ≥ 0.8: large effect")
    lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="MVP11.2 Effect Size Evaluator")
    parser.add_argument("--ticks", type=int, default=None, help="Ticks per run")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Base random seed")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Runs per intervention")
    parser.add_argument("--profile", choices=["ci", "full"], default="full", help="Preset profile")
    parser.add_argument("--artifacts-dir", default="artifacts/mvp11", help="Artifacts directory")
    parser.add_argument("--output", default="reports/mvp11_effects.json", help="Output JSON path")
    parser.add_argument("--output-md", default="reports/mvp11_effects.md", help="Output markdown path")
    args = parser.parse_args()

    # Resolve ticks from profile
    ticks = args.ticks
    if ticks is None:
        ticks = DEFAULT_CI_TICKS if args.profile == "ci" else DEFAULT_FULL_TICKS

    artifacts_dir = Path(args.artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    reports_dir = Path(args.output).parent
    reports_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MVP11.2 Effect Size Evaluator")
    print("=" * 60)
    print(f"Profile: {args.profile}")
    print(f"Ticks: {ticks}, Runs: {args.runs}, Base seed: {args.seed}")
    print(f"Artifacts: {artifacts_dir}")
    print(f"Output: {args.output}")
    print()

    # Collect baseline runs
    baseline_results: List[RunResult] = []
    print(f"[Baseline] Running {args.runs} baseline runs...")
    for i in range(args.runs):
        seed = args.seed + i
        print(f"  Run {i+1}/{args.runs} (seed={seed})...", end=" ", flush=True)
        result = run_soak(ticks, seed, str(artifacts_dir))
        baseline_results.append(result)
        print(f"done ({result.duration_sec}s, {result.metrics.get('events', 0)} events)")

    # Collect intervention runs
    effects_by_intervention: Dict[str, Dict[str, EffectSizeResult]] = {}
    intervention_results_map: Dict[str, List[RunResult]] = {}

    for int_id, int_name, int_type, int_desc in INTERVENTIONS:
        print(f"\n[{int_id}] {int_desc}")
        intervention_results: List[RunResult] = []
        
        for i in range(args.runs):
            seed = args.seed + i
            print(f"  Run {i+1}/{args.runs} (seed={seed})...", end=" ", flush=True)
            result = run_soak(ticks, seed, str(artifacts_dir), int_type, int_name)
            intervention_results.append(result)
            print(f"done ({result.duration_sec}s, {result.metrics.get('events', 0)} events)")
        
        intervention_results_map[int_id] = intervention_results
        effects_by_intervention[int_id] = compute_effect_sizes(
            baseline_results, intervention_results, int_id
        )

    # Generate outputs
    ts = int(time.time())
    
    # JSON output
    output_data = {
        "run_id": f"mvp11_effects_{ts}",
        "profile": args.profile,
        "ticks": ticks,
        "runs": args.runs,
        "base_seed": args.seed,
        "interventions": [
            {"id": int_id, "name": int_name, "description": int_desc}
            for int_id, int_name, _, int_desc in INTERVENTIONS
        ],
        "effects": {
            int_id: {
                metric: {
                    "baseline_mean": e.baseline_mean,
                    "baseline_std": e.baseline_std,
                    "intervention_mean": e.intervention_mean,
                    "intervention_std": e.intervention_std,
                    "delta": e.delta,
                    "cohens_d": e.cohens_d,
                    "n_baseline": e.n_baseline,
                    "n_intervention": e.n_intervention,
                }
                for metric, e in effects.items()
            }
            for int_id, effects in effects_by_intervention.items()
        },
        "baseline_runs": [r.__dict__ for r in baseline_results],
        "intervention_runs": {
            int_id: [r.__dict__ for r in results]
            for int_id, results in intervention_results_map.items()
        },
        "ts": ts,
    }

    json_path = Path(args.output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
    print(f"\nJSON output: {json_path}")

    # Markdown output
    md_content = generate_markdown_table(effects_by_intervention)
    md_path = Path(args.output_md)
    md_path.write_text(md_content)
    print(f"Markdown output: {md_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for int_id, int_name, _, int_desc in INTERVENTIONS:
        effects = effects_by_intervention.get(int_id, {})
        if effects:
            avg_d = sum(e.cohens_d for e in effects.values()) / len(effects)
            print(f"{int_id}: avg |d| = {avg_d:.4f}")

    print(f"\nREPORT_PATH={json_path}")
    print(f"MD_PATH={md_path}")


if __name__ == "__main__":
    main()
