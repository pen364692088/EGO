#!/usr/bin/env python3
"""MVP11.4 Long-run Evaluation for Chronic Degradation Detection.

Designed to catch issues that short runs (600 ticks) miss:
- Cycle overfitting leading to exploration exhaustion
- Diversity tax too strong causing efficiency drop
- Prior-induced strategy collapse/drift over time

Recommended configs:
- 2 scenarios × 3 seeds × 1200 ticks = 12 pairs (ON/OFF)
- Or: 1 scenario × 3 seeds × 2000 ticks (more sensitive)

Key metrics:
- signature_concentration_top1/top3
- novelty/dot_ratio long-term trends
- homeostasis_recovery_time
"""

from __future__ import annotations

import argparse
import json
import random
import signal
import statistics
import time
from collections import Counter
from math import log2
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emotiond.efe_policy import EFEPolicy
from emotiond.governor_v2 import GovernorDecision, GovernorV2, create_action, create_homeostasis
from emotiond.homeostasis import HomeostasisState
from emotiond.science.cycle import annotate_event_with_cycle, compute_cycle_metrics, compute_cycle_candidates
from emotiond.science.cycle_store import build_consolidated_cycles, save_cycle_store
from emotiond.science.interventions import InterventionManager, InterventionType


# --- Diversity Metrics ---

def compute_signature_concentration(signatures: List[str], top_k: int = 3) -> Dict[str, float]:
    """Compute signature concentration metrics.
    
    Returns:
        - top1_share: fraction of hits from top-1 signature
        - top3_share: fraction of hits from top-3 signatures
        - hhi: Herfindahl-Hirschman Index (0=diverse, 1=monopoly)
        - unique_count: number of unique signatures
    """
    if not signatures:
        return {"top1_share": 0.0, "top3_share": 0.0, "hhi": 0.0, "unique_count": 0}
    
    counts = Counter(signatures)
    total = len(signatures)
    sorted_counts = sorted(counts.values(), reverse=True)
    
    top1_share = sorted_counts[0] / total if sorted_counts else 0.0
    top3_share = sum(sorted_counts[:3]) / total if len(sorted_counts) >= 3 else sum(sorted_counts) / total
    
    # HHI: sum of squared market shares
    hhi = sum((c / total) ** 2 for c in counts.values())
    
    return {
        "top1_share": round(top1_share, 6),
        "top3_share": round(top3_share, 6),
        "hhi": round(hhi, 6),
        "unique_count": len(counts),
    }


def compute_novelty_trend(events: List[Dict[str, Any]], window_size: int = 200) -> Dict[str, float]:
    """Compute novelty trend over time.
    
    Returns:
        - early_novelty: novelty ratio in first window
        - late_novelty: novelty ratio in last window
        - delta: late - early (negative = exploration exhaustion)
    """
    signatures = [e.get("cycle_signature") for e in events if e.get("cycle_signature")]
    
    if len(signatures) < window_size * 2:
        return {"early_novelty": 0.0, "late_novelty": 0.0, "delta": 0.0}
    
    early = signatures[:window_size]
    late = signatures[-window_size:]
    
    early_unique = len(set(early))
    late_unique = len(set(late))
    
    early_novelty = early_unique / len(early) if early else 0.0
    late_novelty = late_unique / len(late) if late else 0.0
    
    return {
        "early_novelty": round(early_novelty, 6),
        "late_novelty": round(late_novelty, 6),
        "delta": round(late_novelty - early_novelty, 6),
    }


def compute_homeostasis_recovery_time(events: List[Dict[str, Any]], danger_threshold: float = 0.35) -> Dict[str, float]:
    """Compute average time to recover from danger zone.
    
    Returns:
        - mean_recovery_ticks: average ticks to recover
        - danger_entries: number of times entering danger zone
    """
    recovery_times = []
    in_danger = False
    danger_start = 0
    
    for i, e in enumerate(events):
        hs = e.get("homeostasis_state") or {}
        safety = float(hs.get("safety", 0.5))
        energy = float(hs.get("energy", 0.5))
        
        is_danger = safety < danger_threshold or energy < danger_threshold
        
        if is_danger and not in_danger:
            in_danger = True
            danger_start = i
        elif not is_danger and in_danger:
            in_danger = False
            recovery_times.append(i - danger_start)
    
    # If still in danger at end, count until end
    if in_danger:
        recovery_times.append(len(events) - danger_start)
    
    return {
        "mean_recovery_ticks": round(statistics.mean(recovery_times), 2) if recovery_times else 0.0,
        "danger_entries": len(recovery_times),
    }


# --- Simulation ---

_shutdown_requested = False


def _setup_signal_handlers():
    global _shutdown_requested
    
    def handler(signum, frame):
        global _shutdown_requested
        _shutdown_requested = True
        print(f"[SIGNAL] Received signal {signum}, will flush and exit", flush=True)
    
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


def _scenario_adjustments(scenario: str) -> Dict[str, float]:
    if scenario == "focused":
        return {"risk_shift": -0.05, "novelty_shift": -0.05, "stability_shift": 0.04}
    if scenario == "wide":
        return {"risk_shift": 0.03, "novelty_shift": 0.08, "stability_shift": -0.03}
    if scenario == "stress":
        return {"risk_shift": 0.08, "novelty_shift": -0.03, "stability_shift": -0.05}
    if scenario == "chaos":
        return {"risk_shift": 0.10, "novelty_shift": 0.10, "stability_shift": -0.08}
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

    for c in base:
        c["risk"] = _clamp(c["risk"] + rng.uniform(-0.03, 0.03))
        c["cost"] = _clamp(c["cost"] + rng.uniform(-0.03, 0.03))
        c["ambiguity"] = _clamp(c["ambiguity"] + rng.uniform(-0.04, 0.04))
        c["info_gain"] = _clamp(c["info_gain"] + rng.uniform(-0.04, 0.04))

    if scenario == "wide" and tick % 5 == 0:
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

        if candidate.get("risk", 0.0) > 0.88 and st["safety"] < 0.5:
            st["safety"] = _clamp(st["safety"] - 0.03)
            st["energy"] = _clamp(st["energy"] - 0.01)

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
        cycle_prior_enabled=False,
        cycle_memory_path=cycle_memory_path,
    )
    governor = GovernorV2()

    iv_manager = InterventionManager()
    if prior_enabled:
        iv_manager.enable(InterventionType.ENABLE_CYCLE_PRIOR, params={"cycle_prior_enabled": True}, reason="longrun_eval")

    events: List[Dict[str, Any]] = []
    bias_strengths: List[float] = []
    signatures: List[str] = []
    pass_count = 0
    deny_count = 0

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

        state = _update_state(state, selected, decision, rng)

        if decision != GovernorDecision.DENY and _state_mean(state) >= 0.35:
            pass_count += 1

        if "bias_strength" in trace:
            b = float(trace.get("bias_strength", 0.0) or 0.0)
            bias_strengths.append(b)

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
        
        if event.get("cycle_signature"):
            signatures.append(event["cycle_signature"])

    cycle = compute_cycle_metrics(events)
    
    # Long-run specific metrics
    concentration = compute_signature_concentration(signatures)
    novelty_trend = compute_novelty_trend(events)
    recovery = compute_homeostasis_recovery_time(events)

    return {
        "run_id": run_id,
        "scenario": scenario,
        "seed": seed,
        "prior_enabled": prior_enabled,
        "ticks": ticks,
        "metrics": {
            "pass_rate": round(pass_count / max(1, ticks), 6),
            "governor_deny_rate": round(deny_count / max(1, ticks), 6),
            "homeostasis_delta": round(_state_mean(state) - initial_mean, 6),
            "homeostasis_final_mean": round(_state_mean(state), 6),
            "cycle_persistence_score": float(cycle.get("cycle_persistence_score", 0.0)),
            "novelty_ratio": float(cycle.get("novelty_ratio", 0.0)),
            "dot_ratio": float(cycle.get("dot_ratio", 0.0)),
            "bias_strength_mean": round(_mean(bias_strengths), 6),
            "bias_strength_p95": round(_quantile(bias_strengths, 0.95), 6),
            # Long-run metrics
            "signature_concentration": concentration,
            "novelty_trend": novelty_trend,
            "homeostasis_recovery": recovery,
        },
        "events": events,
    }


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
        scenario_id="longrun_eval",
        policy_version="mvp11.4.longrun",
        schema_version="mvp11.4.v1",
    )
    sanity = (compute_cycle_metrics(events).get("sanity") or {"ok": True})
    save_cycle_store(cycles, out_path, run_id=run_id, sanity=sanity, max_entries=128)
    return out_path


def _get_completed_pairs(pairs_file: Path) -> set:
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
    tmp_file = pairs_file.with_suffix(".tmp")
    with open(tmp_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    if not pairs_file.exists():
        tmp_file.rename(pairs_file)
    else:
        with open(pairs_file, "a", encoding="utf-8") as dst:
            with open(tmp_file, "r", encoding="utf-8") as src:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
        tmp_file.unlink()


def _render_longrun_md(report: Dict[str, Any]) -> str:
    lines = [
        "# MVP11.4 Long-run Evaluation Report",
        "",
        "## Setup",
        f"- scenarios: `{','.join(report.get('config', {}).get('scenarios', []))}`",
        f"- seeds: `{','.join(str(s) for s in report.get('config', {}).get('seeds', []))}`",
        f"- ticks_per_run: `{report.get('config', {}).get('ticks')}`",
        f"- pairs: `{report.get('summary', {}).get('pairs')}`",
        "",
        "## Key Long-run Metrics (ON - OFF)",
        "",
    ]
    
    agg = report.get("aggregate", {})
    
    # Standard metrics
    for k in ["pass_rate", "homeostasis_delta", "novelty_ratio"]:
        if k in agg:
            row = agg[k]
            lines.append(f"- {k}: `{row.get('mean', 0.0):.6f}` [`{row.get('ci_low', 0.0):.6f}`, `{row.get('ci_high', 0.0):.6f}`]")
    
    # Concentration metrics
    lines.extend([
        "",
        "## Signature Concentration (Chronic Degradation Detection)",
        "",
    ])
    
    conc = agg.get("signature_concentration", {})
    for k in ["top1_share", "top3_share", "hhi"]:
        if k in conc:
            lines.append(f"- {k}: `{conc[k].get('mean', 0.0):.6f}`")
    
    # Novelty trend
    lines.extend([
        "",
        "## Novelty Trend (Exploration Exhaustion)",
        "",
    ])
    
    nt = agg.get("novelty_trend", {})
    if "delta" in nt:
        lines.append(f"- novelty_delta: `{nt['delta'].get('mean', 0.0):.6f}` (late - early, negative = exhaustion)")
    
    # Recovery time
    lines.extend([
        "",
        "## Homeostasis Recovery",
        "",
    ])
    
    rec = agg.get("homeostasis_recovery", {})
    if "mean_recovery_ticks" in rec:
        lines.append(f"- mean_recovery_ticks: `{rec['mean_recovery_ticks'].get('mean', 0.0):.2f}`")
    
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="MVP11.4 Long-run evaluation for chronic degradation")
    
    ap.add_argument("--scenarios", default="baseline,stress", help="Comma-separated scenario IDs")
    ap.add_argument("--seeds", default="41,42,43", help="Comma-separated seed values")
    ap.add_argument("--ticks", type=int, default=1200, help="Ticks per run")
    ap.add_argument("--artifacts-dir", default="artifacts/mvp11_longrun")
    ap.add_argument("--out", default="artifacts/mvp11_longrun/mvp114_longrun_report.json")
    ap.add_argument("--out-md", default="artifacts/mvp11_longrun/mvp114_longrun_report.md")
    ap.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    ap.add_argument("--pairs-file", default=None)
    
    args = ap.parse_args()
    
    _setup_signal_handlers()
    
    scenarios = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    
    artifacts = Path(args.artifacts_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    
    pairs_file = Path(args.pairs_file) if args.pairs_file else (artifacts / "pairs.jsonl")
    
    completed = set()
    if args.resume:
        completed = _get_completed_pairs(pairs_file)
        print(f"[RESUME] Found {len(completed)} completed pairs", flush=True)
    
    all_pairs = [(s, seed) for s in scenarios for seed in seeds]
    pending = [(s, seed) for s, seed in all_pairs if f"{s}_{seed}" not in completed]
    
    print(f"[PLAN] Total: {len(all_pairs)}, Completed: {len(completed)}, Pending: {len(pending)}", flush=True)
    
    for scenario, seed in pending:
        if _shutdown_requested:
            print(f"[INTERRUPT] Shutdown requested", flush=True)
            break
        
        print(f"[RUN] {scenario}_{seed}...", flush=True)
        start = time.time()
        
        # OFF run
        off = _simulate_run(
            scenario=scenario,
            seed=seed,
            ticks=args.ticks,
            prior_enabled=False,
            cycle_memory_path=str(artifacts / "cycle_memory.json"),
        )
        
        # Build cycle store from OFF for ON
        mem_path = artifacts / "ab" / scenario / f"seed_{seed}" / "cycle_memory_off.json"
        mem_path.parent.mkdir(parents=True, exist_ok=True)
        _build_cycle_store_for_on(off["events"], off["run_id"], mem_path)
        
        # ON run
        on = _simulate_run(
            scenario=scenario,
            seed=seed,
            ticks=args.ticks,
            prior_enabled=True,
            cycle_memory_path=str(mem_path),
        )
        
        result = {
            "scenario": scenario,
            "seed": seed,
            "off": {"metrics": off["metrics"]},
            "on": {"metrics": on["metrics"]},
            "elapsed_sec": round(time.time() - start, 2),
        }
        
        _append_pair_result(pairs_file, result)
        print(f"[OK] {scenario}_{seed} in {result['elapsed_sec']}s", flush=True)
    
    # Generate report
    pairs: List[Dict[str, Any]] = []
    if pairs_file.exists():
        with open(pairs_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        pairs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    
    # Aggregate
    report = {
        "schema_version": "mvp11.4.longrun.v1",
        "ts": time.time(),
        "config": {
            "scenarios": scenarios,
            "seeds": seeds,
            "ticks": args.ticks,
        },
        "summary": {"pairs": len(pairs)},
        "pairs": pairs,
        "aggregate": {},
    }
    
    # Compute aggregates
    if pairs:
        # Standard metrics
        for mk in ["pass_rate", "homeostasis_delta", "novelty_ratio", "dot_ratio"]:
            deltas = []
            for p in pairs:
                off_v = p.get("off", {}).get("metrics", {}).get(mk, 0)
                on_v = p.get("on", {}).get("metrics", {}).get(mk, 0)
                if isinstance(off_v, dict) or isinstance(on_v, dict):
                    continue
                deltas.append(float(on_v) - float(off_v))
            
            if deltas:
                report["aggregate"][mk] = {
                    "mean": round(statistics.mean(deltas), 6),
                    "stdev": round(statistics.stdev(deltas), 6) if len(deltas) > 1 else 0.0,
                }
        
        # Concentration metrics (ON only)
        for ck in ["top1_share", "top3_share", "hhi", "unique_count"]:
            vals = []
            for p in pairs:
                conc = p.get("on", {}).get("metrics", {}).get("signature_concentration", {})
                if ck in conc:
                    vals.append(float(conc[ck]))
            
            if vals:
                report["aggregate"].setdefault("signature_concentration", {})[ck] = {
                    "mean": round(statistics.mean(vals), 6),
                }
        
        # Novelty trend
        for nk in ["delta", "early_novelty", "late_novelty"]:
            vals = []
            for p in pairs:
                nt = p.get("on", {}).get("metrics", {}).get("novelty_trend", {})
                if nk in nt:
                    vals.append(float(nt[nk]))
            
            if vals:
                report["aggregate"].setdefault("novelty_trend", {})[nk] = {
                    "mean": round(statistics.mean(vals), 6),
                }
    
    out = Path(args.out)
    out_md = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_render_longrun_md(report), encoding="utf-8")
    
    print(json.dumps({
        "output": str(out),
        "output_md": str(out_md),
        "pairs": len(pairs),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
