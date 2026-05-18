#!/usr/bin/env python3
"""MVP11.4 A/B causal evaluation for runtime cycle prior.

Design:
- Paired runs on same (scenario, seed, ticks)
- A: prior OFF
- B: prior ON via ENABLE_CYCLE_PRIOR intervention manager
- Per-pair cycle memory for B is built from A events to guarantee meaningful matches

v2.0 Enhancements:
- A. checkpoint/resume: append to pairs.jsonl, SIGTERM flush, --resume
- B. sharding: --shard-index k --shard-count n
- C. parallel: --workers N (ProcessPoolExecutor)
- D. timeout: --per-pair-timeout-sec, --max-runtime-sec
"""

from __future__ import annotations

import argparse
import json
import math
import random
import signal
import statistics
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.efe_policy import EFEPolicy
from emotiond.governor_v2 import GovernorDecision, GovernorV2, create_action, create_homeostasis
from emotiond.homeostasis import HomeostasisState
from emotiond.science.cycle import annotate_event_with_cycle, compute_cycle_metrics, compute_cycle_candidates
from emotiond.science.cycle_store import build_consolidated_cycles, save_cycle_store
from emotiond.science.interventions import InterventionManager, InterventionType


# Global shutdown flag for SIGTERM handling
_shutdown_requested = False


def _setup_signal_handlers():
    """Setup graceful shutdown on SIGTERM/SIGINT."""
    global _shutdown_requested
    
    def handler(signum, frame):
        global _shutdown_requested
        _shutdown_requested = True
        print(f"[SIGNAL] Received signal {signum}, will flush and exit after current pair", flush=True)
    
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _mean(vals: Sequence[float]) -> float:
    return float(sum(vals) / len(vals)) if vals else 0.0


def _quantile(vals: Sequence[float], q: float) -> float:
    if not vals:
        return 0.0
    arr = sorted(float(v) for v in vals)
    idx = int(round((len(arr) - 1) * q))
    return float(arr[max(0, min(len(arr) - 1, idx))])


def _bootstrap_ci(deltas: Sequence[float], *, n: int = 1000, alpha: float = 0.05, seed: int = 123) -> Dict[str, float]:
    arr = [float(x) for x in deltas]
    if not arr:
        return {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    rng = random.Random(seed)
    means = []
    for _ in range(max(200, n)):
        sample = [arr[rng.randrange(len(arr))] for _ in range(len(arr))]
        means.append(_mean(sample))
    means.sort()
    lo = means[int((alpha / 2) * (len(means) - 1))]
    hi = means[int((1 - alpha / 2) * (len(means) - 1))]
    return {"mean": round(_mean(arr), 6), "ci_low": round(lo, 6), "ci_high": round(hi, 6)}


def _scenario_adjustments(scenario: str) -> Dict[str, float]:
    if scenario == "focused":
        return {"risk_shift": -0.05, "novelty_shift": -0.05, "stability_shift": 0.04}
    if scenario == "wide":
        return {"risk_shift": 0.03, "novelty_shift": 0.08, "stability_shift": -0.03}
    return {"risk_shift": 0.0, "novelty_shift": 0.0, "stability_shift": 0.0}


def _make_candidates(state: Dict[str, float], scenario: str, tick: int, rng: random.Random) -> List[Dict[str, Any]]:
    adj = _scenario_adjustments(scenario)
    low_safety_pressure = max(0.0, 0.6 - state.get("safety", 0.5))
    low_energy_pressure = max(0.0, 0.55 - state.get("energy", 0.5))

    repair_risk = _clamp(0.18 + 0.15 * low_energy_pressure + adj["risk_shift"] * 0.3)
    explore_risk = _clamp(0.42 + adj["risk_shift"])
    push_risk = _clamp(0.78 + 0.35 * low_safety_pressure + adj["risk_shift"])

    base = [
        {
            "name": "repair",
            "focus": "stability",
            "intent": "stabilize",
            "action_type": "repair",
            "risk": repair_risk,
            "ambiguity": _clamp(0.22 - adj["stability_shift"]),
            "info_gain": 0.22,
            "cost": _clamp(0.28 + 0.15 * low_energy_pressure),
            "delta": {"energy": 0.03, "safety": 0.04, "certainty": 0.03, "autonomy": 0.01},
        },
        {
            "name": "explore",
            "focus": "discovery",
            "intent": "probe",
            "action_type": "probe",
            "risk": explore_risk,
            "ambiguity": _clamp(0.52 + adj["novelty_shift"]),
            "info_gain": _clamp(0.72 + adj["novelty_shift"]),
            "cost": 0.36,
            "delta": {"energy": -0.02, "safety": -0.01, "certainty": 0.04, "autonomy": 0.03},
        },
        {
            "name": "push",
            "focus": "throughput",
            "intent": "execute",
            "action_type": "push",
            "risk": push_risk,
            "ambiguity": 0.28,
            "info_gain": 0.24,
            "cost": 0.44,
            "delta": {"energy": -0.03, "safety": -0.03, "certainty": -0.01, "autonomy": 0.05},
        },
    ]

    # controlled deterministic jitter
    for c in base:
        c["risk"] = _clamp(c["risk"] + rng.uniform(-0.03, 0.03))
        c["cost"] = _clamp(c["cost"] + rng.uniform(-0.03, 0.03))
        c["ambiguity"] = _clamp(c["ambiguity"] + rng.uniform(-0.04, 0.04))
        c["info_gain"] = _clamp(c["info_gain"] + rng.uniform(-0.04, 0.04))

    if scenario == "wide" and tick % 5 == 0:
        # encourage broader novelty in wide scenario
        base[1]["focus"] = "novel_goal"
        base[1]["intent"] = "diverge"

    return base


def _state_mean(st: Dict[str, float]) -> float:
    return _mean([st.get("energy", 0.5), st.get("safety", 0.5), st.get("certainty", 0.5), st.get("autonomy", 0.5)])


def _update_state(
    state: Dict[str, float],
    candidate: Dict[str, Any],
    decision: GovernorDecision,
    rng: random.Random,
) -> Dict[str, float]:
    st = dict(state)

    if decision == GovernorDecision.DENY:
        st["energy"] = _clamp(st["energy"] - 0.02)
        st["safety"] = _clamp(st["safety"] - 0.03)
        st["certainty"] = _clamp(st["certainty"] - 0.02)
        st["autonomy"] = _clamp(st["autonomy"] - 0.02)
    elif decision == GovernorDecision.REQUIRE_APPROVAL:
        st["energy"] = _clamp(st["energy"] - 0.01)
        st["certainty"] = _clamp(st["certainty"] - 0.01)
        st["autonomy"] = _clamp(st["autonomy"] - 0.005)
    else:
        delta = candidate.get("delta") or {}
        for k in ("energy", "safety", "certainty", "autonomy"):
            st[k] = _clamp(st.get(k, 0.5) + float(delta.get(k, 0.0)) + rng.uniform(-0.008, 0.008))

        # risk penalty when aggressive action in fragile regime
        if candidate.get("risk", 0.0) > 0.88 and st["safety"] < 0.5:
            st["safety"] = _clamp(st["safety"] - 0.03)
            st["energy"] = _clamp(st["energy"] - 0.01)

    # mild pull-to-setpoint for stability realism
    for k in ("energy", "safety", "certainty", "autonomy"):
        st[k] = _clamp(st[k] + 0.01 * (0.65 - st[k]))

    return st


def _simulate_run(
    *,
    scenario: str,
    seed: int,
    ticks: int,
    prior_enabled: bool,
    cycle_memory_path: str,
) -> Dict[str, Any]:
    rng = random.Random((hash(scenario) & 0xFFFF) * 100000 + seed)
    run_id = f"{scenario}_{seed}_{'on' if prior_enabled else 'off'}"

    state = {"energy": 0.62, "safety": 0.62, "certainty": 0.60, "autonomy": 0.58}
    initial_mean = _state_mean(state)

    policy = EFEPolicy(
        seed=seed,
        cycle_prior_enabled=False,  # use intervention path for ON
        cycle_memory_path=cycle_memory_path,
    )
    governor = GovernorV2()

    iv_manager = InterventionManager()
    if prior_enabled:
        iv_manager.enable(InterventionType.ENABLE_CYCLE_PRIOR, params={"cycle_prior_enabled": True}, reason="ab_eval")

    events: List[Dict[str, Any]] = []
    bias_strengths: List[float] = []
    matched_count = 0
    pass_count = 0
    deny_count = 0
    req_count = 0

    for t in range(1, ticks + 1):
        candidates = _make_candidates(state, scenario, t, rng)
        hs_obj = HomeostasisState(
            energy=state["energy"],
            safety=state["safety"],
            certainty=state["certainty"],
            autonomy=state["autonomy"],
            affiliation=0.5,
            fairness=0.5,
        )

        context = {
            "scenario_id": scenario,
            "intervention_manager": iv_manager,
        }

        selected, selected_efe, _ranked = policy.select_action(
            candidates,
            context=context,
            homeostasis=hs_obj,
            stochastic=True,
        )
        trace = policy.get_last_selection_trace() or {}

        action = create_action(
            selected.get("action_type", "noop"),
            risk=float(selected.get("risk", 0.0)),
            modifies_self_state=False,
            is_destructive=bool(selected.get("risk", 0.0) > 0.97),
            is_recovery=False,
        )
        gov_hs = create_homeostasis(
            energy=state["energy"],
            stability=(state["safety"] + state["certainty"]) / 2,
            stress=(1.0 - state["safety"]),
        )
        decision = governor.evaluate(action, {}, gov_hs)

        if decision == GovernorDecision.DENY:
            deny_count += 1
        elif decision == GovernorDecision.REQUIRE_APPROVAL:
            req_count += 1

        state = _update_state(state, selected, decision, rng)

        # pass criterion: not denied and mean homeostasis not in degraded zone
        if decision != GovernorDecision.DENY and _state_mean(state) >= 0.35:
            pass_count += 1

        if "bias_strength" in trace:
            b = float(trace.get("bias_strength", 0.0) or 0.0)
            bias_strengths.append(b)
            if b > 0:
                matched_count += 1

        event = {
            "tick_id": t,
            "run_id": run_id,
            "seed": seed,
            "scenario_id": scenario,
            "chosen_focus": selected.get("focus"),
            "chosen_intent": selected.get("intent"),
            "action": {"type": selected.get("action_type"), "risk": selected.get("risk")},
            "governor_decision": {"decision": decision.value},
            "homeostasis_state": dict(state),
            "efe_terms": {
                "risk": float(selected.get("risk", 0.0)),
                "ambiguity": float(selected.get("ambiguity", 0.0)),
                "info_gain": float(selected.get("info_gain", 0.0)),
                "cost": float(selected.get("cost", 0.0)),
            },
            "selection_trace": trace,
            "ts": time.time() + t / 10000.0,
        }
        annotate_event_with_cycle(event)
        events.append(event)

    cycle = compute_cycle_metrics(events)
    signatures = [e.get("cycle_signature") for e in events if e.get("cycle_signature")]
    novelty_ratio = (len(set(signatures)) / len(signatures)) if signatures else 0.0

    out = {
        "run_id": run_id,
        "scenario": scenario,
        "seed": seed,
        "prior_enabled": prior_enabled,
        "ticks": ticks,
        "metrics": {
            "pass_rate": round(pass_count / max(1, ticks), 6),
            "governor_deny_rate": round(deny_count / max(1, ticks), 6),
            "governor_require_approval_rate": round(req_count / max(1, ticks), 6),
            "homeostasis_delta": round(_state_mean(state) - initial_mean, 6),
            "homeostasis_final_mean": round(_state_mean(state), 6),
            "cycle_persistence_score": float(cycle.get("cycle_persistence_score", 0.0)),
            "return_time_mean": float(cycle.get("return_time_mean", 0.0)),
            "order_invariance_score": float(cycle.get("order_invariance_score", 0.0)),
            "dot_ratio": float(cycle.get("dot_ratio", 0.0)),
            "novelty_ratio": round(novelty_ratio, 6),
            "bias_strength_mean": round(_mean(bias_strengths), 6),
            "bias_strength_p95": round(_quantile(bias_strengths, 0.95), 6),
            "bias_strength_max": round(max(bias_strengths) if bias_strengths else 0.0, 6),
            "bias_near_cap_rate": round(sum(1 for x in bias_strengths if x >= 0.95 * 0.15) / max(1, len(bias_strengths)), 6),
            "cycle_prior_applied_rate": round(matched_count / max(1, ticks), 6),
            "sanity_ok": bool((cycle.get("sanity") or {}).get("ok", True)),
        },
        "events": events,
    }
    return out


def _build_cycle_store_for_on(events: List[Dict[str, Any]], run_id: str, out_path: Path) -> Path:
    candidates = compute_cycle_candidates(
        events,
        min_count=3,
        min_order_invariance=0.0,
        min_return_time_p50=1.0,
        max_return_time_p50=512.0,
        top_k=128,
    )
    cycles = build_consolidated_cycles(
        run_id=run_id,
        candidates=candidates,
        scenario_id="ab_eval",
        policy_version="mvp11.4.ab",
        schema_version="mvp11.4.v1",
    )
    sanity = (compute_cycle_metrics(events).get("sanity") or {"ok": True})
    save_cycle_store(cycles, out_path, run_id=run_id, sanity=sanity, max_entries=128)
    return out_path


def _metric_delta(off: Dict[str, Any], on: Dict[str, Any], key: str) -> float:
    return float(on.get("metrics", {}).get(key, 0.0)) - float(off.get("metrics", {}).get(key, 0.0))


def _summarize_pairs(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    keys = [
        "pass_rate",
        "governor_deny_rate",
        "governor_require_approval_rate",
        "homeostasis_delta",
        "cycle_persistence_score",
        "return_time_mean",
        "order_invariance_score",
        "dot_ratio",
        "novelty_ratio",
    ]

    out: Dict[str, Any] = {}
    for k in keys:
        deltas = [_metric_delta(r["off"], r["on"], k) for r in rows]
        out[k] = _bootstrap_ci(deltas, n=1200, seed=17)

    bias_vals = [float(r["on"]["metrics"].get("bias_strength_mean", 0.0)) for r in rows]
    bias_caps = [float(r["on"]["metrics"].get("bias_near_cap_rate", 0.0)) for r in rows]

    out["bias_strength"] = {
        "mean": round(_mean(bias_vals), 6),
        "p95": round(_quantile(bias_vals, 0.95), 6),
        "near_cap_rate_mean": round(_mean(bias_caps), 6),
    }

    safe = (
        out["governor_deny_rate"]["mean"] <= 0.01
        and out["governor_require_approval_rate"]["mean"] <= 0.02
        and out["pass_rate"]["mean"] >= -0.01
    )

    out["recommendation"] = {
        "nightly_gate_ready": bool(safe),
        "reason": "safety/main metrics stable" if safe else "requires tuning (safety or pass-rate regression)",
    }
    return out


def _render_md(report: Dict[str, Any]) -> str:
    agg = report.get("aggregate") or {}
    rec = (agg.get("recommendation") or {})
    lines = [
        "# MVP11.4 Prior A/B Report",
        "",
        "## Setup",
        f"- scenarios: `{','.join(report.get('config', {}).get('scenarios', []))}`",
        f"- seeds: `{','.join(str(s) for s in report.get('config', {}).get('seeds', []))}`",
        f"- ticks_per_run: `{report.get('config', {}).get('ticks')}`",
        f"- paired_runs: `{report.get('summary', {}).get('pairs')}`",
        "",
        "## Key deltas (ON - OFF, mean [95% CI])",
    ]

    for k in [
        "pass_rate",
        "governor_deny_rate",
        "governor_require_approval_rate",
        "homeostasis_delta",
        "cycle_persistence_score",
        "return_time_mean",
        "order_invariance_score",
        "dot_ratio",
        "novelty_ratio",
    ]:
        row = agg.get(k) or {}
        lines.append(f"- {k}: `{row.get('mean', 0.0):.6f}` [`{row.get('ci_low', 0.0):.6f}`, `{row.get('ci_high', 0.0):.6f}`]")

    bias = agg.get("bias_strength") or {}
    lines.extend(
        [
            "",
            "## Prior activity",
            f"- bias_strength_mean: `{bias.get('mean', 0.0):.6f}`",
            f"- bias_strength_p95: `{bias.get('p95', 0.0):.6f}`",
            f"- near_cap_rate_mean: `{bias.get('near_cap_rate_mean', 0.0):.6f}`",
            "",
            "## Recommendation",
            f"- nightly_gate_ready: `{rec.get('nightly_gate_ready')}`",
            f"- reason: `{rec.get('reason')}`",
            "",
        ]
    )
    return "\n".join(lines)


def _run_single_pair(
    scenario: str,
    seed: int,
    ticks: int,
    artifacts_dir: Path,
    timeout_sec: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Run a single OFF+ON pair. Returns None on timeout or shutdown."""
    global _shutdown_requested
    
    if _shutdown_requested:
        return None
    
    start_time = time.time()
    
    try:
        artifacts = artifacts_dir
        ab_dir = artifacts / "ab"
        ab_dir.mkdir(parents=True, exist_ok=True)

        off = _simulate_run(
            scenario=scenario,
            seed=seed,
            ticks=ticks,
            prior_enabled=False,
            cycle_memory_path=str(artifacts / "cycle_memory.json"),
        )

        mem_path = ab_dir / scenario / f"seed_{seed}" / "cycle_memory_off.json"
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        _build_cycle_store_for_on(off["events"], off["run_id"], mem_path)

        on = _simulate_run(
            scenario=scenario,
            seed=seed,
            ticks=ticks,
            prior_enabled=True,
            cycle_memory_path=str(mem_path),
        )

        # persist compact per-pair artifacts
        pair_payload = {
            "scenario": scenario,
            "seed": seed,
            "off": off["metrics"],
            "on": on["metrics"],
        }
        (mem_path.parent / "pair_metrics.json").write_text(json.dumps(pair_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        result = {
            "scenario": scenario,
            "seed": seed,
            "off": {"metrics": off["metrics"]},
            "on": {"metrics": on["metrics"]},
            "elapsed_sec": round(time.time() - start_time, 2),
        }
        
        if timeout_sec and (time.time() - start_time) > timeout_sec:
            result["timeout"] = True
            
        return result
        
    except Exception as e:
        return {
            "scenario": scenario,
            "seed": seed,
            "error": str(e),
            "elapsed_sec": round(time.time() - start_time, 2),
        }


def _get_completed_pairs(pairs_file: Path) -> set:
    """Load completed pair IDs from checkpoint file."""
    completed = set()
    if pairs_file.exists():
        with open(pairs_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    pair_id = f"{data['scenario']}_{data['seed']}"
                    completed.add(pair_id)
                except (json.JSONDecodeError, KeyError):
                    continue
    return completed


def _append_pair_result(pairs_file: Path, result: Dict[str, Any]) -> None:
    """Append a single pair result to checkpoint file (atomic)."""
    tmp_file = pairs_file.with_suffix(".tmp")
    with open(tmp_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    # Atomic append by renaming (works on same filesystem)
    if not pairs_file.exists():
        tmp_file.rename(pairs_file)
    else:
        # Append to existing file
        with open(pairs_file, "a", encoding="utf-8") as dst:
            with open(tmp_file, "r", encoding="utf-8") as src:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
        tmp_file.unlink()


def _get_pair_id(scenario: str, seed: int) -> str:
    return f"{scenario}_{seed}"


def main() -> None:
    ap = argparse.ArgumentParser(description="MVP11.4 A/B evaluation with checkpoint/resume/sharding support")
    
    # Core parameters
    ap.add_argument("--scenarios", default="baseline,focused,wide", help="Comma-separated scenario IDs")
    ap.add_argument("--seeds", default="41,42,43,44,45,46,47,48,49,50", help="Comma-separated seed values")
    ap.add_argument("--ticks", type=int, default=600, help="Ticks per run")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11", help="Output directory")
    ap.add_argument("--out", default="artifacts/mvp11/mvp114_ab_report.json", help="Final report JSON")
    ap.add_argument("--out-md", default="artifacts/mvp11/mvp114_ab_report.md", help="Final report Markdown")
    
    # v2.0: Checkpoint/Resume
    ap.add_argument("--resume", action="store_true", help="Resume from checkpoint (skip completed pairs)")
    ap.add_argument("--pairs-file", default=None, help="Checkpoint file path (default: <artifacts-dir>/ab/pairs.jsonl)")
    
    # v2.0: Sharding
    ap.add_argument("--shard-index", type=int, default=0, help="Shard index (0-based, requires --shard-count)")
    ap.add_argument("--shard-count", type=int, default=1, help="Total number of shards")
    
    # v2.0: Parallelism
    ap.add_argument("--workers", type=int, default=1, help="Number of parallel workers (ProcessPoolExecutor)")
    
    # v2.0: Timeout protection
    ap.add_argument("--per-pair-timeout-sec", type=float, default=0, help="Timeout per pair in seconds (0=disabled)")
    ap.add_argument("--max-runtime-sec", type=float, default=0, help="Maximum total runtime in seconds (0=disabled)")
    
    args = ap.parse_args()

    # Setup signal handlers
    _setup_signal_handlers()

    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]

    artifacts = Path(args.artifacts_dir)
    ab_dir = artifacts / "ab"
    ab_dir.mkdir(parents=True, exist_ok=True)

    # Checkpoint file
    pairs_file = Path(args.pairs_file) if args.pairs_file else (ab_dir / "pairs.jsonl")
    
    # Validate sharding
    if args.shard_count < 1:
        print("ERROR: --shard-count must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        print(f"ERROR: --shard-index must be 0 <= index < {args.shard_count}", file=sys.stderr)
        sys.exit(1)

    # Build pair list
    all_pairs = []
    for scenario in scenarios:
        for seed in seeds:
            all_pairs.append((scenario, seed))
    
    # Apply sharding
    if args.shard_count > 1:
        shard_pairs = [p for i, p in enumerate(all_pairs) if i % args.shard_count == args.shard_index]
        print(f"[SHARD] Running shard {args.shard_index}/{args.shard_count}: {len(shard_pairs)}/{len(all_pairs)} pairs", flush=True)
        all_pairs = shard_pairs
    
    # Load completed pairs if resuming
    completed = set()
    if args.resume:
        completed = _get_completed_pairs(pairs_file)
        print(f"[RESUME] Found {len(completed)} completed pairs", flush=True)
    
    # Filter out completed
    pending_pairs = [(s, seed) for s, seed in all_pairs if _get_pair_id(s, seed) not in completed]
    print(f"[PLAN] Total pairs: {len(all_pairs)}, Completed: {len(completed)}, Pending: {len(pending_pairs)}", flush=True)
    
    if not pending_pairs:
        print("[DONE] All pairs already completed", flush=True)
    else:
        # Track runtime
        start_time = time.time()
        pairs_processed = 0
        pairs_timed_out = 0
        pairs_errored = 0
        
        # Run pairs (with optional parallelism)
        if args.workers > 1:
            print(f"[PARALLEL] Using {args.workers} workers", flush=True)
            with ProcessPoolExecutor(max_workers=args.workers) as executor:
                futures = {}
                for scenario, seed in pending_pairs:
                    if _shutdown_requested:
                        break
                    future = executor.submit(
                        _run_single_pair,
                        scenario=scenario,
                        seed=seed,
                        ticks=args.ticks,
                        artifacts_dir=artifacts,
                        timeout_sec=args.per_pair_timeout_sec if args.per_pair_timeout_sec > 0 else None,
                    )
                    futures[future] = (scenario, seed)
                
                for future in as_completed(futures):
                    if _shutdown_requested:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    # Check max runtime
                    if args.max_runtime_sec > 0:
                        elapsed = time.time() - start_time
                        if elapsed > args.max_runtime_sec:
                            print(f"[TIMEOUT] Max runtime {args.max_runtime_sec}s exceeded, stopping", flush=True)
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                    
                    scenario, seed = futures[future]
                    try:
                        result = future.result(timeout=args.per_pair_timeout_sec if args.per_pair_timeout_sec > 0 else None)
                        if result is None:
                            print(f"[SKIP] Pair {scenario}_{seed} skipped (shutdown)", flush=True)
                        elif "error" in result:
                            print(f"[ERROR] Pair {scenario}_{seed}: {result['error']}", flush=True)
                            pairs_errored += 1
                        elif result.get("timeout"):
                            print(f"[TIMEOUT] Pair {scenario}_{seed} timed out", flush=True)
                            pairs_timed_out += 1
                            _append_pair_result(pairs_file, result)
                            pairs_processed += 1
                        else:
                            _append_pair_result(pairs_file, result)
                            pairs_processed += 1
                            print(f"[OK] Pair {scenario}_{seed} completed in {result.get('elapsed_sec', 0):.2f}s", flush=True)
                    except Exception as e:
                        print(f"[ERROR] Pair {scenario}_{seed} failed: {e}", flush=True)
                        pairs_errored += 1
        else:
            # Sequential execution
            for scenario, seed in pending_pairs:
                if _shutdown_requested:
                    print(f"[INTERRUPT] Shutdown requested, stopping after {pairs_processed} pairs", flush=True)
                    break
                
                # Check max runtime
                if args.max_runtime_sec > 0:
                    elapsed = time.time() - start_time
                    if elapsed > args.max_runtime_sec:
                        print(f"[TIMEOUT] Max runtime {args.max_runtime_sec}s exceeded, stopping after {pairs_processed} pairs", flush=True)
                        break
                
                print(f"[RUN] Processing pair {scenario}_{seed}...", flush=True)
                result = _run_single_pair(
                    scenario=scenario,
                    seed=seed,
                    ticks=args.ticks,
                    artifacts_dir=artifacts,
                    timeout_sec=args.per_pair_timeout_sec if args.per_pair_timeout_sec > 0 else None,
                )
                
                if result is None:
                    print(f"[SKIP] Pair {scenario}_{seed} skipped (shutdown)", flush=True)
                elif "error" in result:
                    print(f"[ERROR] Pair {scenario}_{seed}: {result['error']}", flush=True)
                    pairs_errored += 1
                elif result.get("timeout"):
                    print(f"[TIMEOUT] Pair {scenario}_{seed} timed out", flush=True)
                    pairs_timed_out += 1
                    _append_pair_result(pairs_file, result)
                    pairs_processed += 1
                else:
                    _append_pair_result(pairs_file, result)
                    pairs_processed += 1
                    print(f"[OK] Pair {scenario}_{seed} completed in {result.get('elapsed_sec', 0):.2f}s", flush=True)
        
        print(f"[SUMMARY] Processed: {pairs_processed}, Timed out: {pairs_timed_out}, Errored: {pairs_errored}", flush=True)

    # Generate final report from checkpoint file
    print("[REPORT] Generating final report...", flush=True)
    pairs: List[Dict[str, Any]] = []
    if pairs_file.exists():
        with open(pairs_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "error" not in data:  # Skip errored entries
                        pairs.append(data)
                except json.JSONDecodeError:
                    continue

    # scenario summaries
    by_scenario: Dict[str, Any] = {}
    for sc in scenarios:
        rows = [r for r in pairs if r.get("scenario") == sc]
        if rows:
            by_scenario[sc] = _summarize_pairs(rows)

    aggregate = _summarize_pairs(pairs) if pairs else {}

    report = {
        "schema_version": "mvp11.4.ab.v2",
        "ts": time.time(),
        "config": {
            "scenarios": scenarios,
            "seeds": seeds,
            "ticks": args.ticks,
            "group_a": "prior_off",
            "group_b": "prior_on_via_enable_cycle_prior",
            "shard_index": args.shard_index,
            "shard_count": args.shard_count,
            "workers": args.workers,
        },
        "summary": {
            "pairs": len(pairs),
            "events_per_group": len(pairs) * args.ticks,
        },
        "by_scenario": by_scenario,
        "aggregate": aggregate,
    }

    out = Path(args.out)
    out_md = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")

    print(json.dumps({
        "output": str(out),
        "output_md": str(out_md),
        "pairs": len(pairs),
        "nightly_gate_ready": bool((aggregate.get("recommendation") or {}).get("nightly_gate_ready", False)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
