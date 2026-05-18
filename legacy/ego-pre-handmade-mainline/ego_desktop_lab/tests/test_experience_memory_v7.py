import json
from pathlib import Path

from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.experience_memory import (
    ACTIVE_STATUS,
    NEEDS_REVIEW_STATUS,
    build_experience_card,
    derive_experience_bias,
    resolve_experience_conflicts,
)
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.policy import GATE_ACTION_STATUS
from ego_desktop_lab.root_cause import diagnose_failure
from ego_desktop_lab.shell import main
from ego_desktop_lab.verification_pack import load_scenario


def _baseline_and_selected(scenario_path: str):
    scenario = load_scenario(Path(scenario_path))
    baseline = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    selected = baseline.selected_intention
    assert selected is not None
    return scenario, baseline, selected


def _continue_failure_card():
    scenario, baseline, selected = _baseline_and_selected(
        "ego_desktop_lab/scenarios/high_evidence_same_goal.json"
    )
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect="continue should reduce stagnation",
        actual_effect="continue_failure",
        success_score=0.10,
        user_feedback="continuation failed and needs repair",
        prediction_error=0.90,
        evidence_refs=("test:v7_experience_memory",),
    )
    failure_cycle = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        outcome=outcome,
        timestamp=scenario.timestamp,
    )
    ticket = diagnose_failure(
        failure_cycle,
        expected={"selected_goal": "continue_or_verify_unfinished_goal", "effect": "continue_improves"},
        observed={"actual_effect": "continue_failure", "success_score": 0.10},
    )
    return scenario, baseline, build_experience_card(
        outcome,
        cycle_result=baseline,
        ticket=ticket,
        timestamp=scenario.timestamp,
    )


def test_negative_similar_experience_changes_future_ranking_without_new_outcome() -> None:
    scenario, baseline, card = _continue_failure_card()

    experienced = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(card,),
    )

    assert baseline.selected_intention is not None
    assert baseline.selected_intention["goal"] == "continue_or_verify_unfinished_goal"
    assert experienced.selected_intention is not None
    assert experienced.selected_intention["goal"] == "repair_or_replan_goal"
    assert experienced.plasticity_update is None
    assert experienced.experience_memory_snapshot["experience_applied"] is True
    assert experienced.experience_memory_snapshot["applied_card_ids"] == [card.card_id]
    assert experienced.experience_memory_snapshot["pressure_bias_delta"]["prediction_error"] > 0
    assert experienced.predictions_by_affordance["continue_goal"]["strategy_confidence"] < (
        baseline.predictions_by_affordance["continue_goal"]["strategy_confidence"]
    )
    assert _priority_for_goal(experienced, "continue_or_verify_unfinished_goal") < _priority_for_goal(
        baseline,
        "continue_or_verify_unfinished_goal",
    )
    assert experienced.candidate_options[0]["goal"] == "repair_or_replan_goal"
    assert experienced.no_action_executed is True


def test_positive_experience_raises_similar_prediction_score() -> None:
    scenario, baseline, selected = _baseline_and_selected(
        "ego_desktop_lab/scenarios/high_prediction_error_same_goal.json"
    )
    assert selected["goal"] == "repair_or_replan_goal"
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect="repair should reduce prediction error",
        actual_effect="repair_success",
        success_score=0.92,
        user_feedback="repair reduced prediction error",
        prediction_error=0.08,
        evidence_refs=("test:v7_positive_experience",),
    )
    card = build_experience_card(outcome, cycle_result=baseline, timestamp=scenario.timestamp)

    experienced = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(card,),
    )

    assert card.valence == "positive"
    assert experienced.experience_memory_snapshot["experience_applied"] is True
    assert experienced.predictions_by_affordance["repair"]["strategy_confidence"] > (
        baseline.predictions_by_affordance["repair"]["strategy_confidence"]
    )
    assert experienced.predictions_by_affordance["repair"]["experience_confidence_delta"] > 0


def test_unrelated_experience_has_no_effect_on_ranking() -> None:
    _, _, card = _continue_failure_card()
    unrelated = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))

    baseline = run_self_maintaining_agency_cycle(
        unrelated.state,
        unrelated.belief_state,
        timestamp=unrelated.timestamp,
    )
    experienced = run_self_maintaining_agency_cycle(
        unrelated.state,
        unrelated.belief_state,
        timestamp=unrelated.timestamp,
        experience_cards=(card,),
    )

    assert experienced.experience_memory_snapshot["experience_applied"] is False
    assert experienced.experience_memory_snapshot["ignored_card_ids"] == [card.card_id]
    assert experienced.selected_intention == baseline.selected_intention
    assert experienced.candidate_options == baseline.candidate_options
    assert experienced.predictions_by_affordance == baseline.predictions_by_affordance


def test_conflicting_experiences_are_marked_needs_review_without_forcing_change() -> None:
    scenario, baseline, negative_card = _continue_failure_card()
    selected = baseline.selected_intention
    assert selected is not None
    positive_outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id=str(selected["id"]),
        selected_plan_id=str(selected["goal"]),
        expected_effect="continue should reduce stagnation",
        actual_effect="continue_success",
        success_score=0.90,
        user_feedback="continuation worked in this exact context",
        prediction_error=0.05,
        evidence_refs=("test:v7_conflict_positive",),
    )
    positive_card = build_experience_card(
        positive_outcome,
        cycle_result=baseline,
        timestamp=scenario.timestamp,
    )

    resolved = resolve_experience_conflicts((negative_card, positive_card))
    bias = derive_experience_bias(resolved, negative_card.context_signature)
    experienced = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(negative_card, positive_card),
    )

    assert negative_card.status == ACTIVE_STATUS
    assert {card.status for card in resolved} == {NEEDS_REVIEW_STATUS}
    assert set(bias.needs_review_card_ids) == {negative_card.card_id, positive_card.card_id}
    assert experienced.experience_memory_snapshot["experience_applied"] is False
    assert set(experienced.experience_memory_snapshot["needs_review_card_ids"]) == {
        negative_card.card_id,
        positive_card.card_id,
    }
    assert experienced.selected_intention == baseline.selected_intention


def test_experience_memory_replay_is_deterministic() -> None:
    scenario, _, card = _continue_failure_card()

    first = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(card,),
    )
    second = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(card,),
    )

    assert first.experience_memory_snapshot == second.experience_memory_snapshot
    assert first.predictions_by_affordance == second.predictions_by_affordance
    assert first.candidate_options == second.candidate_options
    assert first.selected_intention == second.selected_intention


def test_experience_memory_keeps_gate_invariance() -> None:
    scenario, _, card = _continue_failure_card()

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        experience_cards=(card,),
    )
    permissions = result.boundary_summary["permission_status_by_action"]

    assert permissions["file_delete"] == "block"
    assert permissions["system_command"] == "block"
    assert permissions["external_send"] == "block"
    assert permissions["ask_permission"] == "ask"
    assert permissions["suggestion_card"] == "allow"
    for option in (*result.behavior_options, *result.candidate_options):
        assert option["gate_status"] == GATE_ACTION_STATUS[option["proposed_action"]]
    assert result.gate_decision["allowed_as"] == "suggestion_card"
    assert result.no_action_executed is True


def test_shell_experience_memory_report_command_writes_human_check(tmp_path: Path, capsys) -> None:
    report_path = tmp_path / "experience_memory.md"

    status = main(["--experience-memory-report", str(report_path)])
    captured = capsys.readouterr()
    text = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert str(report_path) in captured.out
    assert "# v7 Stage 2 Experience Memory Report" in text
    assert "experience_applied = true" in text
    assert "baseline_selected_goal = continue_or_verify_unfinished_goal" in text
    assert "experience_selected_goal = repair_or_replan_goal" in text
    assert "ranking_changed = true" in text
    assert "unrelated_experience_no_effect = true" in text
    assert "conflict_cards = needs_review" in text
    assert "no_action_executed = true" in text
    assert "## Behavior Change Summary" in text
    assert "before_behavior = 继续当前目标" in text
    assert "after_behavior = 修复或重新规划目标" in text
    assert "selected_changed = true" in text
    assert "before_rank = 1" in text
    assert "after_rank = 1" in text
    assert "selected_priority_delta =" in text
    assert "continue_priority_delta =" in text
    assert "repair_entered_ranking = true" in text
    assert "gate_status = allow" in text
    assert "action_class = suggestion_card" in text
    assert "no runtime influence" in text


def test_shell_custom_experience_memory_case_uses_operator_supplied_json(tmp_path: Path, capsys) -> None:
    case_path = tmp_path / "new_operator_case.json"
    report_path = tmp_path / "new_operator_case_report.md"
    case_path.write_text(
        json.dumps(
            {
                "name": "operator_new_probe_case",
                "learn_scenario": {
                    "name": "operator_new_probe_case",
                    "timestamp": "2026-05-14T00:00:00+00:00",
                    "state": {
                        "agent_id": "operator-custom-agent",
                        "core_commitments": [
                            "avoid false claims",
                            "complete commitments",
                            "preserve identity boundaries",
                        ],
                        "uncertainty": 0.1,
                        "integrity": 0.92,
                        "goal_pressure": 0.74,
                        "risk_sensitivity": 0.6,
                        "unfinished_goals": [
                            "ship a brand new operator probe without fixed fixtures"
                        ],
                        "recent_failures": [],
                        "identity_conflict": False,
                    },
                    "belief_state": {
                        "known_facts": ["operator case is not a built-in fixture"],
                        "unknowns": [],
                        "assumptions": [],
                        "evidence_strength": 0.96,
                        "confidence": 0.93,
                    },
                },
                "outcome": {
                    "expected_effect": "continue should reduce custom probe stagnation",
                    "actual_effect": "custom_continue_failure",
                    "success_score": 0.1,
                    "user_feedback": "custom continuation failed and needs repair",
                    "prediction_error": 0.9,
                    "evidence_refs": ["operator:new_case"],
                },
            },
            indent=2,
        ),
        encoding="utf-8-sig",
    )

    status = main(
        [
            "--experience-memory-case",
            str(case_path),
            "--experience-memory-case-report",
            str(report_path),
        ]
    )
    captured = capsys.readouterr()
    text = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert str(report_path) in captured.out
    assert "# v7 Stage 2 Custom Experience Memory Case Report" in text
    assert "case_name = operator_new_probe_case" in text
    assert "learn_baseline_selected_goal = continue_or_verify_unfinished_goal" in text
    assert "apply_baseline_selected_goal = continue_or_verify_unfinished_goal" in text
    assert "apply_experience_selected_goal = repair_or_replan_goal" in text
    assert "experience_applied = true" in text
    assert "ranking_changed = true" in text
    assert "no_action_executed = true" in text
    assert "## Behavior Change Summary" in text
    assert "before_behavior = 继续当前目标" in text
    assert "after_behavior = 修复或重新规划目标" in text
    assert "selected_changed = true" in text
    assert "before_rank = 1" in text
    assert "after_rank = 1" in text
    assert "selected_priority_delta =" in text
    assert "continue_priority_delta =" in text
    assert "repair_entered_ranking = true" in text
    assert "gate_status = allow" in text
    assert "action_class = suggestion_card" in text


def _priority_for_goal(cycle_result: object, goal: str) -> float:
    for option in cycle_result.candidate_options:
        if option["goal"] == goal:
            return float(option["priority"])
    raise AssertionError(f"missing goal {goal}")
