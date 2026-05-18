"""MVP11.4 tests: cycle bucket layering, graph determinism, runtime prior guards."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from emotiond.cycle_prior import MAX_BIAS
from emotiond.efe_policy import EFEPolicy
from emotiond.governor_v2 import GovernorDecision, GovernorV2, create_action, create_homeostasis
from emotiond.science.cycle import build_cycle_bucket, signature, signature_phi, signature_psi
from emotiond.science.cycle_graph import build_cycle_graph


def _event() -> dict:
    return {
        "scenario_id": "s1",
        "chosen_focus": "goal_alpha",
        "chosen_intent": "stabilize",
        "action": {"type": "repair"},
        "governor_decision": {"decision": "ALLOW"},
        "homeostasis_state": {"energy": 0.8, "safety": 0.7, "certainty": 0.75, "autonomy": 0.65},
        "efe_terms": {"risk": 0.3, "ambiguity": 0.2, "info_gain": 0.6, "cost": 0.2},
    }


def test_cycle_signature_backward_compatible_when_extra_fields_added():
    bucket = build_cycle_bucket(_event())

    legacy_like = {
        "scenario_id": bucket["scenario_id"],
        "focus": bucket["focus"],
        "intent": bucket["intent"],
        "action_type": bucket["action_type"],
        "gov": bucket["gov"],
        "intervention": bucket["intervention"],
        "hs": bucket["hs"],
        "efe": bucket["efe"],
    }

    extended = dict(bucket)
    extended["new_extension"] = {"x": 1}
    extended["phi"] = dict(bucket.get("phi") or {})
    extended["phi"]["extra"] = "ignored"

    assert signature(bucket) == signature(legacy_like)
    assert signature(bucket) == signature(extended)


def test_cycle_signature_psi_phi_deterministic():
    b1 = build_cycle_bucket(_event())
    b2 = build_cycle_bucket(_event())

    assert signature_psi(b1) == signature_psi(b2)
    assert signature_phi(b1) == signature_phi(b2)


def test_cycle_graph_build_deterministic_same_events():
    events = [
        {"cycle_signature": "A"},
        {"cycle_signature": "B"},
        {"cycle_signature": "A"},
        {"cycle_signature": "C"},
        {"cycle_signature": "A"},
    ]
    g1 = build_cycle_graph(events, max_nodes=16, max_edges=32)
    g2 = build_cycle_graph(events, max_nodes=16, max_edges=32)
    assert g1 == g2


def test_cycle_prior_disabled_by_default_no_log_fields():
    policy = EFEPolicy(seed=123, cycle_prior_enabled=False)
    candidates = [
        {"type": "repair", "risk": 0.2, "ambiguity": 0.2, "info_gain": 0.3, "cost": 0.2},
        {"type": "observe", "risk": 0.3, "ambiguity": 0.4, "info_gain": 0.2, "cost": 0.1},
    ]

    policy.select_action(candidates, stochastic=False)
    trace = policy.get_last_selection_trace() or {}

    assert "cycle_prior_applied" not in trace
    assert "matched_signatures_topK" not in trace
    assert "bias_strength" not in trace


def test_cycle_prior_enabled_logs_fields_and_clamps_bias():
    with tempfile.TemporaryDirectory() as td:
        mem = Path(td) / "cycle_memory.json"
        proto = build_cycle_bucket(_event())
        payload = {
            "schema_version": "cycle_store.v1",
            "count": 1,
            "items": [
                {
                    "signature": "sig_match",
                    "prototype_bucket": proto,
                    "stats": {"counts": 10, "support_ratio": 1.0, "order_invariance_score": 1.0},
                    "provenance": {"run_id": "r1"},
                }
            ],
        }
        mem.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        policy = EFEPolicy(seed=7, cycle_prior_enabled=True, cycle_memory_path=str(mem))
        candidates = [
            {
                "scenario_id": "s1",
                "focus": "goal_alpha",
                "intent": "stabilize",
                "action_type": "repair",
                "type": "repair",
                "risk": 0.25,
                "ambiguity": 0.2,
                "info_gain": 0.4,
                "cost": 0.2,
                "homeostasis_state": {"energy": 0.8, "safety": 0.7, "certainty": 0.75, "autonomy": 0.65},
            }
        ]

        policy.select_action(candidates, stochastic=False)
        trace = policy.get_last_selection_trace() or {}

        assert "cycle_prior_applied" in trace
        assert "matched_signatures_topK" in trace
        assert "bias_strength" in trace
        assert 0.0 <= float(trace["bias_strength"]) <= float(MAX_BIAS)


def test_cycle_prior_never_overrides_governor_decision():
    governor = GovernorV2()
    action = create_action("high_risk_action", risk=0.95)
    homeostasis = create_homeostasis(energy=1.0)

    decision_before = governor.evaluate(action, {}, homeostasis)

    # Prior toggle must not affect governor authority.
    policy = EFEPolicy(cycle_prior_enabled=True)
    policy.select_action(
        [{"type": "high_risk_action", "risk": 0.95, "ambiguity": 0.1, "info_gain": 0.1, "cost": 0.1}],
        stochastic=False,
    )

    decision_after = governor.evaluate(action, {}, homeostasis)

    assert decision_before == GovernorDecision.REQUIRE_APPROVAL
    assert decision_after == GovernorDecision.REQUIRE_APPROVAL


def test_replay_trace_stable_with_prior_off():
    candidates = [
        {"type": "repair", "risk": 0.2, "ambiguity": 0.2, "info_gain": 0.3, "cost": 0.2},
        {"type": "observe", "risk": 0.3, "ambiguity": 0.4, "info_gain": 0.2, "cost": 0.1},
        {"type": "nudge", "risk": 0.1, "ambiguity": 0.5, "info_gain": 0.6, "cost": 0.4},
    ]

    p1 = EFEPolicy(seed=42, cycle_prior_enabled=False)
    p2 = EFEPolicy(seed=42, cycle_prior_enabled=False)

    for _ in range(30):
        p1.select_action(candidates, stochastic=True)
        p2.select_action(candidates, stochastic=True)

        t1 = p1.get_last_selection_trace()
        t2 = p2.get_last_selection_trace()
        assert t1 == t2
