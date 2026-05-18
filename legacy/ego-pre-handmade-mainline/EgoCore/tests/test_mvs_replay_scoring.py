from __future__ import annotations

from scripts.codex.score_mvs_replay_validator import (
    VariantScores,
    _bridge_selection_decision,
    _canonical_trace,
    _selection_decision,
    _trace_replayable,
)


def test_canonical_trace_accepts_v2_surface_with_cycles_delta() -> None:
    step = {
        "policy_hint": {"mvs_boundary_guard": "low_boundary_confidence"},
        "trace_payload": {
            "event_id": "evt_001",
            "perceived": {"boundary_state": "boundary_touched"},
            "drives_delta": {"viability_pressure": 0.53},
            "self_model_delta": {"current_mode": "repair"},
            "identity_delta": {"identity_conflict": 0.0},
            "cycles_delta": {
                "closure_signature": "sig_001",
                "closure_family_id": "fam_001",
                "action_signature": "tool:file",
                "outcome_signature": "blocked",
                "closure_consistency_score": 0.75,
                "repair_closure": True,
            },
            "predicted_outcome": 0.55,
            "actual_outcome": "blocked",
            "adjustment_applied": "repair_and_request_replan",
            "next_guard": "request_replan",
            "replay_variant_id": "mvs_candidate_aligned_compact",
        },
    }

    canonical = _canonical_trace(step)

    assert canonical["appraisal_delta"]["viability_pressure"] == 0.53
    assert canonical["cycle_delta"]["repair_closure"] is True
    assert canonical["closure_signature"] == "sig_001"
    assert canonical["action_signature"] == "tool:file"
    assert _trace_replayable(step, require_corrective_fields=True) is True


def test_selection_decision_switches_when_challenger_passes_and_candidate_fails() -> None:
    baseline = VariantScores(
        target_scores={"T1": 0.0, "T2": 0.0, "T3": 0.0, "T4": 0.0, "T5": 0.0},
        composite=0.0,
        boundary_integrity=1.0,
        repair_closure_capture=0.0,
        trace_replayability=0.0,
    )
    candidate = VariantScores(
        target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.58, "T5": 0.91},
        composite=0.898,
        boundary_integrity=1.0,
        repair_closure_capture=0.75,
        trace_replayability=1.0,
    )
    challenger = VariantScores(
        target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.75, "T5": 0.95},
        composite=0.94,
        boundary_integrity=1.0,
        repair_closure_capture=0.9,
        trace_replayability=1.0,
    )
    ablations = {
        "mvs_minus_counterfactual_writeback": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 0.5, "T4": 0.58, "T5": 0.91},
            composite=0.798,
            boundary_integrity=1.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
        "mvs_minus_viability_pressure": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.4, "T5": 0.91},
            composite=0.862,
            boundary_integrity=1.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
        "mvs_minus_corrective_trace": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.58, "T5": 0.4},
            composite=0.796,
            boundary_integrity=1.0,
            repair_closure_capture=0.2,
            trace_replayability=1.0,
        ),
        "mvs_minus_boundary_confidence": VariantScores(
            target_scores={"T1": 1.0, "T2": 0.4, "T3": 1.0, "T4": 0.58, "T5": 0.91},
            composite=0.778,
            boundary_integrity=0.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
    }

    selection = _selection_decision(
        candidate=candidate,
        baseline_a=baseline,
        ablations=ablations,
        challenger=challenger,
    )

    assert selection["candidate_pass"] is False
    assert selection["challenger_pass"] is True
    assert selection["challenger_status"] == "pass"
    assert selection["decision"] == "switch_to_active_inference"


def test_selection_allows_saturated_baseline_target_without_impossible_positive_delta() -> None:
    baseline = VariantScores(
        target_scores={"T1": 1.0, "T2": 0.75, "T3": 0.33, "T4": 0.33, "T5": 0.25},
        composite=0.532,
        boundary_integrity=1.0,
        repair_closure_capture=0.25,
        trace_replayability=1.0,
    )
    candidate = VariantScores(
        target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.58, "T5": 0.91},
        composite=0.9,
        boundary_integrity=1.0,
        repair_closure_capture=0.75,
        trace_replayability=1.0,
    )
    challenger = VariantScores(
        target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 1.0, "T5": 1.0},
        composite=1.0,
        boundary_integrity=1.0,
        repair_closure_capture=1.0,
        trace_replayability=1.0,
    )
    ablations = {
        "mvs_minus_counterfactual_writeback": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 0.5, "T4": 0.58, "T5": 0.91},
            composite=0.798,
            boundary_integrity=1.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
        "mvs_minus_viability_pressure": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.4, "T5": 0.91},
            composite=0.862,
            boundary_integrity=1.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
        "mvs_minus_corrective_trace": VariantScores(
            target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 0.58, "T5": 0.4},
            composite=0.796,
            boundary_integrity=1.0,
            repair_closure_capture=0.2,
            trace_replayability=1.0,
        ),
        "mvs_minus_boundary_confidence": VariantScores(
            target_scores={"T1": 1.0, "T2": 0.4, "T3": 1.0, "T4": 0.58, "T5": 0.91},
            composite=0.778,
            boundary_integrity=0.0,
            repair_closure_capture=0.75,
            trace_replayability=1.0,
        ),
    }

    selection = _selection_decision(
        candidate=candidate,
        baseline_a=baseline,
        ablations=ablations,
        challenger=challenger,
    )

    assert selection["challenger_pass"] is True
    assert selection["challenger_status"] == "pass"
    assert selection["target_delta_rules"]["T1"] == "non_regression>=-0.02"
    assert selection["challenger_target_delta_rules"]["T1"] == "non_regression>=-0.02"


def test_bridge_selection_passes_without_ablation_requirements() -> None:
    baseline = VariantScores(
        target_scores={"T1": 1.0, "T2": 0.75, "T3": 0.33, "T4": 0.33, "T5": 0.25},
        composite=0.5333,
        boundary_integrity=1.0,
        repair_closure_capture=0.75,
        trace_replayability=1.0,
    )
    candidate = VariantScores(
        target_scores={"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 1.0, "T5": 1.0},
        composite=1.0,
        boundary_integrity=1.0,
        repair_closure_capture=1.0,
        trace_replayability=1.0,
    )

    selection = _bridge_selection_decision(candidate=candidate, baseline_a=baseline)

    assert selection["bridge_mode"] is True
    assert selection["candidate_pass"] is True
    assert selection["decision"] == "bridge_pass"
    assert selection["ablation_drops"] == {}
    assert selection["challenger_status"] == "not_applicable"
