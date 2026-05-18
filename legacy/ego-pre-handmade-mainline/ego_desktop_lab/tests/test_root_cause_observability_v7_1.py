from pathlib import Path

from ego_desktop_lab.agency_decision_view import build_agency_decision_view
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.root_cause import (
    ROOT_CAUSE_CATEGORIES,
    TICKET_STATUSES,
    build_operator_observability_report,
    build_root_cause_operator_report,
    build_root_cause_trace,
    diagnose_failure,
)
from ego_desktop_lab.shell import main
from ego_desktop_lab.verification_pack import load_scenario


def _continue_failure_cycle(tmp_path: Path):
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    probe = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    selected = probe.selected_intention
    assert selected is not None
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect="continue should reduce stagnation",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
        evidence_refs=("test:v7_1_root_cause",),
    )
    return run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        evidence_log_path=tmp_path / "continue_failure.jsonl",
        timestamp=scenario.timestamp,
    )


def test_outcome_failure_localizes_prediction_or_policy_layer(tmp_path: Path) -> None:
    result = _continue_failure_cycle(tmp_path)

    ticket = diagnose_failure(
        result,
        expected={"selected_goal": "continue_or_verify_unfinished_goal", "effect": "continue_improves"},
        observed={"actual_effect": "continue_failure", "success_score": 0.10},
        input_summary="high evidence same goal continuation",
    )

    assert ticket.category in {"prediction_wrong", "policy_ranking_wrong"}
    assert ticket.category == "prediction_wrong"
    assert ticket.status == "localized"
    assert ticket.confidence > 0.70
    assert "Replay" in ticket.next_minimal_probe
    assert ticket.trace_diff["before_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert ticket.trace_diff["after_selected_goal"] == "repair_or_replan_goal"
    assert ticket.trace_diff["prediction_error_delta"] > 0
    assert ticket.trace_diff["recomputed_decision"] is False


def test_final_text_candidate_or_template_risk_maps_to_expression_surface() -> None:
    trace = build_root_cause_trace(
        {
            "viability_snapshot": {"before": {"evidence_gap_pressure": 0.1}},
            "predictions_by_affordance": {"suggest": {"expected_viability_improvement": 0.3}},
            "candidate_options": [{"rank": 1, "goal": "suggest", "affordance": "suggest"}],
            "selected_behavior_option": {"goal": "suggest", "option_type": "skill_option"},
            "gate_decision": {"status": "allow", "allowed_as": "suggestion_card"},
            "next_cycle_delta": {"plasticity_applied": False},
            "no_action_executed": True,
            "claim_ceiling": "lab-only",
        },
        input_summary="proactive visible text candidate",
    )

    ticket = diagnose_failure(
        trace,
        expected={"surface": "OpenEmotion final_text_candidate"},
        observed={
            "final_text_candidate": None,
            "fallback_text": "围绕随机的分享，我想轻轻接回来。现在继续吗？",
            "template_like": True,
        },
    )

    assert ticket.category == "expression_surface"
    assert ticket.status == "localized"
    assert ticket.trace_diff["gate_status"] == "allow"
    assert "output_check" in ticket.next_minimal_probe


def test_listener_online_without_fresh_send_is_evidence_claim_mismatch() -> None:
    ticket = diagnose_failure(
        {
            "gate_decision": {"status": "allow"},
            "next_cycle_delta": {"plasticity_applied": False},
            "no_action_executed": True,
        },
        expected={"claim": "fresh live proactive send"},
        observed={
            "listener_status": "online",
            "soak_status": "waiting",
            "fresh_send_observed": False,
        },
    )

    assert ticket.category in {"evidence_claim_mismatch", "runtime_bridge"}
    assert ticket.category == "evidence_claim_mismatch"
    assert ticket.status == "needs_live_probe"
    assert "fresh allowlisted live window" in ticket.next_minimal_probe
    assert "fresh proactive-send evidence" in " ".join(ticket.evidence)


def test_insufficient_trace_returns_unknown_without_guessing() -> None:
    ticket = diagnose_failure(
        {},
        expected="behavior should improve",
        observed="it seems wrong",
    )

    assert ticket.category == "unknown"
    assert ticket.status == "unknown"
    assert ticket.confidence <= 0.25
    assert "missing enough decision fields" in " ".join(ticket.evidence)
    assert "Capture a RootCauseTrace" in ticket.next_minimal_probe


def test_root_cause_trace_reads_decision_view_without_recomputing() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    cycle = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    view = build_agency_decision_view(cycle)

    trace = build_root_cause_trace(view, input_summary="decision view read")

    assert trace.selected_option == cycle.selected_behavior_option
    assert trace.gate_decision == cycle.gate_decision
    assert trace.no_action_executed is True
    assert trace.debug_refs["read_only"] is True
    assert trace.debug_refs["recomputed_decision"] is False


def test_root_cause_trace_preserves_outcome_record_payload(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    probe = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    selected = probe.selected_intention
    assert selected is not None
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect="continue should reduce stagnation",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
        evidence_refs=("test:v7_1_root_cause",),
    )
    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        evidence_log_path=tmp_path / "outcome_payload.jsonl",
        timestamp=scenario.timestamp,
    )

    trace = build_root_cause_trace(result, outcome=outcome)

    assert trace.outcome is not None
    assert trace.outcome["actual_effect"] == "continue_failure"
    assert trace.outcome["selected_plan_id"] == "continue_or_verify_unfinished_goal"


def test_operator_report_uses_allowed_status_and_claim_ceiling(tmp_path: Path) -> None:
    result = _continue_failure_cycle(tmp_path)
    ticket = diagnose_failure(
        result,
        expected="continue should improve",
        observed={"actual_effect": "continue_failure", "success_score": 0.10},
    )

    report = build_root_cause_operator_report(ticket)

    assert ticket.category in ROOT_CAUSE_CATEGORIES
    assert ticket.status in TICKET_STATUSES
    assert "# Root-Cause Failure Ticket" in report
    assert "status: localized" in report
    assert "no runtime influence" in report
    assert "runtime efficacy" in report
    assert "live user benefit" in report
    assert "consciousness" in report
    assert "resolved" not in report.lower()
    assert "fixed" not in report.lower()


def test_stage0_operator_observability_report_exposes_required_sections(tmp_path: Path) -> None:
    result = _continue_failure_cycle(tmp_path)
    view = build_agency_decision_view(result)
    trace = build_root_cause_trace(
        result,
        input_summary="high evidence same goal continuation",
    )
    ticket = diagnose_failure(
        trace,
        expected={"selected_goal": "continue_or_verify_unfinished_goal", "effect": "continue_improves"},
        observed={"actual_effect": "continue_failure", "success_score": 0.10},
    )

    report = build_operator_observability_report(view, trace=trace, ticket=ticket)

    assert "# v7 Stage 0 Operator Observability Report" in report
    assert "## Boundary" in report
    assert "## Viability" in report
    assert "## Prediction" in report
    assert "## Ranking" in report
    assert "## Gate" in report
    assert "## Plasticity" in report
    assert "## Root Cause" in report
    assert "## Before / After Decision" in report
    assert "## Stage Ladder" in report
    assert "## Current Gate" in report
    assert "## Next Probe" in report
    assert "## Claim Ceiling" in report
    assert '"before_selected_goal": "continue_or_verify_unfinished_goal"' in report
    assert '"after_selected_goal": "repair_or_replan_goal"' in report
    assert '"selected_intention_changed": true' in report
    assert '"rank_delta_by_goal"' in report
    assert '"ranking_transition_by_goal"' in report
    assert '"priority_delta_by_goal"' in report
    assert '"pressure_transition"' in report
    assert '"prediction_error_delta": 0.72135' in report
    assert "It does not recompute selected option, policy, or gate" in report
    assert "Replay continue_failure fixture" in report
    assert "before=continue_or_verify_unfinished_goal" in report
    assert "after=repair_or_replan_goal" in report
    assert "same selected goal" not in report
    assert "prediction" in report
    assert "no runtime influence" in report


def test_operator_report_layer_does_not_recompute_decisions() -> None:
    source = Path("ego_desktop_lab/root_cause.py").read_text(encoding="utf-8")

    forbidden_tokens = (
        "run_self_maintaining_agency_cycle",
        "run_agent_cycle",
        "select_intention",
        "select_behavior_option",
        "evaluate_gate",
        "derive_motivation_pressure",
    )
    for token in forbidden_tokens:
        assert token not in source


def test_shell_operator_report_command_writes_stage0_report(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "operator_observability.md"

    status = main(["--operator-report", str(report_path)])
    captured = capsys.readouterr()
    text = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert str(report_path) in captured.out
    assert "# v7 Stage 0 Operator Observability Report" in text
    assert "## Before / After Decision" in text
    assert "## Stage Ladder" in text
    assert "continue_or_verify_unfinished_goal" in text
    assert "repair_or_replan_goal" in text
    assert "rank_delta_by_goal" in text
    assert "ranking_transition_by_goal" in text
    assert "pressure_transition" in text
    assert "Replay continue_failure fixture" in text
    assert "same selected goal" not in text
    assert "no runtime influence" in text
