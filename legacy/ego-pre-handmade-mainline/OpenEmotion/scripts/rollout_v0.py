#!/usr/bin/env python3
"""
MVP-6.2 D6: Offline rollout simulator (diagnostic only).

Runs fixed-seed reproducible K-step simulations over candidate strategies and
returns rankings by persistence_cost, info_gain, risk, and relationship_change.

No online side effects by default: reads optional input JSON, writes report JSON.
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any


DEFAULT_STRATEGIES = ["repair", "boundary", "withdraw"]


@dataclass
class RolloutState:
    energy: float = 0.7
    safety_stress: float = 0.4
    focus_fatigue: float = 0.3
    bond: float = 0.5
    trust: float = 0.5
    grudge: float = 0.2
    novelty_need: float = 0.5


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _step_transition(state: RolloutState, strategy: str, rng: random.Random, other_mind: Dict[str, float]) -> Dict[str, float]:
    reliability = other_mind.get("reliability", 0.5)
    cooperativeness = other_mind.get("cooperativeness", 0.5)
    attentiveness = other_mind.get("attentiveness", 0.5)

    noise = lambda s=0.02: rng.uniform(-s, s)

    if strategy == "repair":
        bond_delta = 0.03 + 0.07 * cooperativeness + noise()
        trust_delta = 0.02 + 0.08 * reliability + noise()
        grudge_delta = -(0.02 + 0.06 * cooperativeness) + noise()
        energy_delta = -(0.02 + 0.03 * (1.0 - attentiveness)) + noise(0.01)
        stress_delta = -(0.01 + 0.04 * reliability) + noise(0.01)
        info_gain = 0.04 + 0.1 * attentiveness + noise(0.01)
    elif strategy == "boundary":
        bond_delta = -(0.01 + 0.03 * (1.0 - cooperativeness)) + noise()
        trust_delta = 0.01 + 0.05 * reliability + noise()
        grudge_delta = 0.01 + 0.03 * (1.0 - cooperativeness) + noise()
        energy_delta = -0.01 + noise(0.01)
        stress_delta = -(0.02 + 0.03 * (1.0 - reliability)) + noise(0.01)
        info_gain = 0.03 + 0.05 * attentiveness + noise(0.01)
    elif strategy == "withdraw":
        bond_delta = -(0.02 + 0.04 * attentiveness) + noise()
        trust_delta = -(0.01 + 0.03 * attentiveness) + noise()
        grudge_delta = -0.01 + noise()
        energy_delta = 0.02 + 0.02 * (1.0 - state.focus_fatigue) + noise(0.01)
        stress_delta = -(0.03 + 0.04 * (1.0 - reliability)) + noise(0.01)
        info_gain = 0.01 + 0.03 * (1.0 - attentiveness) + noise(0.01)
    else:
        raise ValueError(f"Unsupported strategy: {strategy}")

    state.bond = _clamp(state.bond + bond_delta)
    state.trust = _clamp(state.trust + trust_delta)
    state.grudge = _clamp(state.grudge + grudge_delta)
    state.energy = _clamp(state.energy + energy_delta)
    state.safety_stress = _clamp(state.safety_stress + stress_delta)
    state.focus_fatigue = _clamp(state.focus_fatigue + (0.01 if strategy != "withdraw" else -0.01) + noise(0.005))
    state.novelty_need = _clamp(state.novelty_need + (0.01 - info_gain * 0.1))

    risk = _clamp(0.5 * state.safety_stress + 0.35 * state.grudge + 0.15 * (1.0 - state.energy))
    persistence_cost = _clamp(0.4 * state.safety_stress + 0.3 * (1.0 - state.energy) + 0.3 * state.focus_fatigue)
    relationship_change = (state.bond + state.trust - state.grudge) - 0.8

    return {
        "risk": risk,
        "persistence_cost": persistence_cost,
        "info_gain": _clamp(info_gain, 0.0, 1.0),
        "relationship_change": relationship_change,
    }


def simulate_strategy(
    strategy: str,
    k_steps: int,
    seed: int,
    initial_state: Dict[str, float],
    other_mind: Dict[str, float],
) -> Dict[str, Any]:
    rng = random.Random(seed)
    state = RolloutState(**{k: initial_state[k] for k in RolloutState.__dataclass_fields__.keys() if k in initial_state})

    trajectory: List[Dict[str, float]] = []
    agg = {"risk": 0.0, "persistence_cost": 0.0, "info_gain": 0.0, "relationship_change": 0.0}

    for _ in range(k_steps):
        step = _step_transition(state, strategy, rng, other_mind)
        trajectory.append(step)
        for k in agg:
            agg[k] += step[k]

    avg = {k: agg[k] / float(k_steps) for k in agg}
    return {
        "strategy": strategy,
        "k_steps": k_steps,
        "seed": seed,
        "averages": avg,
        "trajectory": trajectory,
        "final_state": state.__dict__.copy(),
    }


def rank_results(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "by_persistence_cost": sorted(results, key=lambda r: (r["averages"]["persistence_cost"], r["strategy"])),
        "by_info_gain": sorted(results, key=lambda r: (-r["averages"]["info_gain"], r["strategy"])),
        "by_risk": sorted(results, key=lambda r: (r["averages"]["risk"], r["strategy"])),
        "by_relationship_change": sorted(results, key=lambda r: (-r["averages"]["relationship_change"], r["strategy"])),
    }


def run_rollout(config: Dict[str, Any]) -> Dict[str, Any]:
    seed = int(config.get("seed", 42))
    k_steps = int(config.get("k_steps", 7))
    strategies = list(config.get("strategies", DEFAULT_STRATEGIES))
    initial_state = config.get("initial_state", {})
    other_mind = config.get("other_minds_state", {"reliability": 0.5, "cooperativeness": 0.5, "attentiveness": 0.5})

    results = [simulate_strategy(s, k_steps, seed + i * 9973, initial_state, other_mind) for i, s in enumerate(strategies)]
    rankings = rank_results(results)

    return {
        "version": "rollout_v0",
        "diagnostic_only": True,
        "side_effects": "none",
        "seed": seed,
        "k_steps": k_steps,
        "strategies": strategies,
        "rankings": {
            k: [
                {
                    "strategy": r["strategy"],
                    "persistence_cost": r["averages"]["persistence_cost"],
                    "info_gain": r["averages"]["info_gain"],
                    "risk": r["averages"]["risk"],
                    "relationship_change": r["averages"]["relationship_change"],
                }
                for r in v
            ]
            for k, v in rankings.items()
        },
        "details": results,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Offline rollout v0 (diagnostic only)")
    p.add_argument("--input", type=str, default="", help="Path to rollout config JSON")
    p.add_argument("--output", type=str, default="", help="Path to write result JSON")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--k-steps", type=int, default=7)
    p.add_argument("--strategies", type=str, default=",".join(DEFAULT_STRATEGIES))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg: Dict[str, Any] = {
        "seed": args.seed,
        "k_steps": args.k_steps,
        "strategies": [s.strip() for s in args.strategies.split(",") if s.strip()],
    }

    if args.input:
        cfg.update(json.loads(Path(args.input).read_text()))

    result = run_rollout(cfg)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)

    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
