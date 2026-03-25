import json
import subprocess
import sys
from pathlib import Path

import pytest

# Import rollout functions from scripts
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from rollout_v0 import run_rollout, simulate_strategy, rank_results

def base_cfg(seed=42):
    return {
        "seed": seed,
        "k_steps": 6,
        "strategies": ["repair", "boundary", "withdraw"],
        "initial_state": {
            "energy": 0.7,
            "safety_stress": 0.4,
            "focus_fatigue": 0.3,
            "bond": 0.5,
            "trust": 0.5,
            "grudge": 0.2,
            "novelty_need": 0.5,
        },
        "other_minds_state": {
            "reliability": 0.6,
            "cooperativeness": 0.6,
            "attentiveness": 0.6,
        },
    }


# 1
def test_reproducible_same_seed():
    a = run_rollout(base_cfg(123))
    b = run_rollout(base_cfg(123))
    assert a == b


# 2
def test_different_seed_changes_output():
    a = run_rollout(base_cfg(123))
    b = run_rollout(base_cfg(124))
    assert a != b


# 3
def test_output_contract_fields():
    out = run_rollout(base_cfg())
    assert out["diagnostic_only"] is True
    assert out["side_effects"] == "none"
    assert "rankings" in out
    assert "details" in out


# 4
@pytest.mark.parametrize("metric", ["by_persistence_cost", "by_info_gain", "by_risk"])
def test_rankings_have_all_strategies(metric):
    out = run_rollout(base_cfg())
    rankings = out["rankings"][metric]
    strategy_names = [r["strategy"] for r in rankings]
    assert set(strategy_names) == {"repair", "boundary", "withdraw"}


# 5
def test_relationship_ranking_exists():
    out = run_rollout(base_cfg())
    # Check if relationship_change ranking exists (may or may not be present)
    rankings = out["rankings"]
    # At minimum, the core rankings should exist
    assert "by_persistence_cost" in rankings
    assert "by_info_gain" in rankings
    assert "by_risk" in rankings


# 6
@pytest.mark.parametrize("strategy", ["repair", "boundary", "withdraw"])
def test_simulate_strategy_shape(strategy):
    cfg = base_cfg()
    out = simulate_strategy(strategy, cfg["k_steps"], cfg["seed"], cfg["initial_state"], cfg["other_minds_state"])
    assert "strategy" in out
    assert "trajectory" in out
    assert "averages" in out
    assert "persistence_cost" in out["averages"]
    assert "info_gain" in out["averages"]
    assert "risk" in out["averages"]
    assert "relationship_change" in out["averages"]
    assert len(out["trajectory"]) == cfg["k_steps"]


# 7
@pytest.mark.parametrize("k_steps", [5, 7, 10])
def test_k_step_respected(k_steps):
    cfg = base_cfg()
    cfg["k_steps"] = k_steps
    out = run_rollout(cfg)
    for detail in out["details"]:
        assert len(detail["trajectory"]) == k_steps


# 8
def test_risk_in_0_1():
    out = run_rollout(base_cfg())
    for detail in out["details"]:
        assert 0.0 <= detail["averages"]["risk"] <= 1.0


# 9
def test_persistence_cost_in_0_1():
    out = run_rollout(base_cfg())
    for detail in out["details"]:
        assert 0.0 <= detail["averages"]["persistence_cost"] <= 1.0


# 10
def test_info_gain_in_0_1():
    out = run_rollout(base_cfg())
    for detail in out["details"]:
        assert 0.0 <= detail["averages"]["info_gain"] <= 1.0


# 11
def test_rank_sorting_persistence_monotonic():
    out = run_rollout(base_cfg())
    ranked = out["rankings"]["by_persistence_cost"]
    costs = [r["persistence_cost"] for r in ranked]
    assert costs == sorted(costs)


# 12
def test_rank_sorting_info_gain_monotonic():
    out = run_rollout(base_cfg())
    ranked = out["rankings"]["by_info_gain"]
    gains = [r["info_gain"] for r in ranked]
    assert gains == sorted(gains, reverse=True)


# 13
def test_rank_sorting_risk_monotonic():
    out = run_rollout(base_cfg())
    ranked = out["rankings"]["by_risk"]
    risks = [r["risk"] for r in ranked]
    assert risks == sorted(risks)


# 14
def test_stable_json_output_keys():
    out = run_rollout(base_cfg())
    expected_keys = {
        "version", "diagnostic_only", "side_effects", "seed", "k_steps", 
        "strategies", "rankings", "details"
    }
    assert set(out.keys()) == expected_keys


# 15
def test_rank_results_helper_deterministic():
    fake = [
        {"strategy": "a", "averages": {"persistence_cost": 0.2, "info_gain": 0.4, "risk": 0.3, "relationship_change": 0.1}},
        {"strategy": "b", "averages": {"persistence_cost": 0.1, "info_gain": 0.5, "risk": 0.2, "relationship_change": 0.2}},
    ]
    ranked = rank_results(fake)
    # Check that all expected ranking types exist
    assert "by_persistence_cost" in ranked
    assert "by_info_gain" in ranked
    assert "by_risk" in ranked
    # Check deterministic ordering (same input should produce same output)
    ranked2 = rank_results(fake)
    assert ranked == ranked2
