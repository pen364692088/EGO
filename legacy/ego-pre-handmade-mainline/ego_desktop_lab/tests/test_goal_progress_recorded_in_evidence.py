from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.goal_progress import FailureType, GoalProgressState
from ego_desktop_lab.oscillation import run_oscillation_control_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.verification_pack import load_scenario


def test_goal_progress_recorded_in_evidence(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    evidence_path = tmp_path / "oscillation.jsonl"
    raw = run_agent_cycle(
        scenario.state,
        evidence_log_path=evidence_path,
        timestamp=scenario.timestamp,
        belief_state=scenario.belief_state,
        append_evidence=False,
    )
    assert raw.selected_intention is not None
    progress = GoalProgressState(goal_id=scenario.state.unfinished_goals[0].goal_id)
    outcome = OutcomeRecord(
        scenario_id="evidence",
        selected_intention_id=raw.selected_intention.id,
        selected_plan_id=raw.selected_intention.goal,
        expected_effect="continue should progress",
        actual_effect="continue_failure",
        success_score=0.20,
        user_feedback="continuation failed without progress",
        prediction_error=0.80,
        evidence_refs=("test:evidence",),
    )

    result = run_oscillation_control_cycle(
        scenario.state,
        scenario.belief_state,
        progress,
        outcome=outcome,
        failure_type=FailureType.plan_failure,
        evidence_log_path=evidence_path,
        timestamp=scenario.timestamp,
    )
    records = read_evidence_records(evidence_path)
    record = records[-1]

    assert result.selection_result.selected_intention is not None
    assert record["goal_id"] == progress.goal_id
    assert "goal_progress_before" in record
    assert "goal_progress_after" in record
    assert record["failure_type"] == "plan_failure"
    assert "oscillation_detected" in record
    assert "hysteresis_decision" in record
    assert "cooldown_decision" in record
    assert record["selected_intention"]["goal"] == result.selection_result.selected_intention.goal
    assert record["reason"] == result.selection_result.reason
