from pathlib import Path

from ego_desktop_lab.affective_drive_loop import AffectiveDriveState
from ego_desktop_lab.agency_kernel import (
    CLAIM_CEILING,
    run_self_maintaining_agency_cycle,
)
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.policy import GATE_ACTION_STATUS
from ego_desktop_lab.verification_pack import load_scenario


def _selected_outcome(
    *,
    scenario_path: str,
    expected_effect: str,
    actual_effect: str,
    success_score: float,
    user_feedback: str,
    prediction_error: float,
) -> tuple[object, OutcomeRecord]:
    scenario = load_scenario(Path(scenario_path))
    probe = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    selected = probe.selected_intention
    assert selected is not None
    return scenario, OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect=expected_effect,
        actual_effect=actual_effect,
        success_score=success_score,
        user_feedback=user_feedback,
        prediction_error=prediction_error,
        evidence_refs=("test:v7_agency_kernel",),
    )


def test_continue_failure_drives_next_cycle_toward_repair(tmp_path: Path) -> None:
    scenario, outcome = _selected_outcome(
        scenario_path="ego_desktop_lab/scenarios/high_evidence_same_goal.json",
        expected_effect="continue goal without repair",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
    )

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        evidence_log_path=tmp_path / "continue_failure.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.next_cycle_delta["before_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert result.next_cycle_delta["after_selected_goal"] == "repair_or_replan_goal"
    assert result.next_cycle_delta["selected_intention_changed"] is True
    assert result.next_cycle_delta["selected_transition"] == {
        "before_selected_goal": "continue_or_verify_unfinished_goal",
        "after_selected_goal": "repair_or_replan_goal",
        "selected_intention_changed": True,
    }
    assert result.next_cycle_delta["affordance_pressure_delta"]["repair"] > 0
    assert result.next_cycle_delta["pressure_transition"]["repair"]["delta"] > 0
    assert result.next_cycle_delta["priority_delta_by_goal"]["repair_or_replan_goal"] > 0
    assert result.next_cycle_delta["rank_delta_by_goal"]["repair_or_replan_goal"] < 0
    repair_transition = result.next_cycle_delta["ranking_transition_by_goal"]["repair_or_replan_goal"]
    assert repair_transition["before_rank"] is None
    assert repair_transition["after_rank"] == 1
    assert repair_transition["entered_ranking"] is True
    assert repair_transition["moved_up"] is True
    continue_transition = result.next_cycle_delta["ranking_transition_by_goal"][
        "continue_or_verify_unfinished_goal"
    ]
    assert continue_transition["before_rank"] == 1
    assert continue_transition["after_rank"] == 3
    assert continue_transition["moved_down"] is True
    assert result.plasticity_update is not None
    assert result.plasticity_update["prediction_error_delta"] > 0
    assert result.plasticity_update["strategy_success_delta"] < 0
    assert result.selected_behavior_option is not None
    assert result.selected_behavior_option["option_type"] == "skill_option"
    assert result.behavior_options[0]["goal"] == "repair_or_replan_goal"
    assert result.candidate_options[0]["goal"] == "repair_or_replan_goal"
    assert result.no_action_executed is True


def test_verify_success_reduces_verify_pressure_and_releases_continue(tmp_path: Path) -> None:
    scenario, outcome = _selected_outcome(
        scenario_path="ego_desktop_lab/scenarios/low_evidence_same_goal.json",
        expected_effect="reduce uncertainty before claiming",
        actual_effect="verify_success",
        success_score=0.90,
        user_feedback="verification reduced uncertainty",
        prediction_error=0.05,
    )

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        evidence_log_path=tmp_path / "verify_success.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.next_cycle_delta["before_selected_goal"] == "verify_before_claim"
    assert result.next_cycle_delta["after_selected_goal"] == "continue_or_verify_unfinished_goal"
    assert result.next_cycle_delta["affordance_pressure_delta"]["verify"] < 0
    assert result.next_cycle_delta["pressure_transition"]["verify"]["delta"] < 0
    assert result.next_cycle_delta["rank_delta_by_goal"]["verify_before_claim"] > 0
    verify_transition = result.next_cycle_delta["ranking_transition_by_goal"]["verify_before_claim"]
    assert verify_transition["before_rank"] == 1
    assert verify_transition["left_ranking"] is True or verify_transition["moved_down"] is True
    assert verify_transition["moved_up"] is False
    assert result.plasticity_update is not None
    assert result.plasticity_update["uncertainty_delta"] < 0
    assert result.selected_intention is not None
    assert result.selected_intention["goal"] != "verify_before_claim"


def test_no_outcome_keeps_current_cycle_stable_without_plasticity() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )

    assert result.plasticity_update is None
    assert result.next_cycle_delta["plasticity_applied"] is False
    assert result.next_cycle_delta["selected_intention_changed"] is False
    assert result.next_cycle_delta["before_selected_goal"] == result.next_cycle_delta["after_selected_goal"]
    assert result.next_cycle_delta["selected_transition"]["selected_intention_changed"] is False
    for transition in result.next_cycle_delta["ranking_transition_by_goal"].values():
        assert transition["entered_ranking"] is False
        assert transition["left_ranking"] is False
        assert transition["rank_delta"] == 0
        assert transition["priority_delta"] == 0
        assert transition["moved_up"] is False
        assert transition["moved_down"] is False
    for transition in result.next_cycle_delta["pressure_transition"].values():
        assert transition["delta"] == 0
    assert result.evidence_log_path is None
    assert result.affective_drive_snapshot["applied_to_pressure"] is False


def test_gate_boundary_remains_proposal_only_and_blocks_external_actions() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    permissions = result.boundary_summary["permission_status_by_action"]

    assert permissions["file_delete"] == "block"
    assert permissions["system_command"] == "block"
    assert permissions["external_send"] == "block"
    assert permissions["ask_permission"] == "ask"
    assert permissions["suggestion_card"] == "allow"
    for option in (*result.behavior_options, *result.candidate_options):
        assert option["gate_status"] == GATE_ACTION_STATUS[option["proposed_action"]]
    assert result.gate_decision["status"] == "allow"
    assert result.gate_decision["allowed_as"] == "suggestion_card"
    assert result.no_action_executed is True


def test_v7_cycle_is_deterministic_without_repo_writes() -> None:
    scenario, outcome = _selected_outcome(
        scenario_path="ego_desktop_lab/scenarios/high_evidence_same_goal.json",
        expected_effect="continue goal without repair",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
    )

    first = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        timestamp=scenario.timestamp,
    )
    second = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        timestamp=scenario.timestamp,
    )

    assert first.evidence_log_path is None
    assert second.evidence_log_path is None
    assert first.selected_intention == second.selected_intention
    assert first.candidate_options == second.candidate_options
    assert first.predictions_by_affordance == second.predictions_by_affordance
    assert first.next_cycle_delta == second.next_cycle_delta
    assert first.next_cycle_delta["selected_transition"] == second.next_cycle_delta["selected_transition"]
    assert (
        first.next_cycle_delta["ranking_transition_by_goal"]
        == second.next_cycle_delta["ranking_transition_by_goal"]
    )
    assert first.next_cycle_delta["pressure_transition"] == second.next_cycle_delta["pressure_transition"]


def test_affective_drive_can_shift_ranking_without_runtime_side_effects() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))

    baseline = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    driven = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        affective_drive_state=AffectiveDriveState(
            frustration_pressure=1.0,
            curiosity_pressure=1.0,
        ),
    )

    assert baseline.selected_intention is not None
    assert baseline.selected_intention["goal"] == "verify_before_claim"
    assert driven.selected_intention is not None
    assert driven.selected_intention["goal"] == "repair_or_replan_goal"
    assert driven.affective_drive_snapshot["applied_to_pressure"] is True
    assert driven.affective_drive_snapshot["pressure_bias_delta"]["viability_error"] > 0
    assert driven.selected_behavior_option is not None
    assert driven.selected_behavior_option["option_type"] == "skill_option"
    assert driven.gate_decision["status"] == "allow"
    assert driven.no_action_executed is True


def test_lab_spine_summary_preserves_dual_track_boundary() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )

    assert result.lab_spine_summary["active_innovation_spine"] == "ego_desktop_lab"
    assert result.lab_spine_summary["formal_program_state_override"] is False
    assert result.lab_spine_summary["formal_evidence_ledger_write"] is False
    assert result.lab_spine_summary["runtime_reply_influence"] is False
    assert result.lab_spine_summary["openemotion_state_mutation"] is False


def test_claim_ceiling_keeps_lab_only_boundary_text() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    ceiling = result.claim_ceiling.lower()

    assert result.claim_ceiling == CLAIM_CEILING
    assert "lab-only" in ceiling
    assert "no consciousness" in ceiling
    assert "no alive" in ceiling
    assert "no external action executed" in ceiling
