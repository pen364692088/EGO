from pathlib import Path

from ego_desktop_lab.gate import evaluate_gate
from ego_desktop_lab.learning import run_learning_cycle
from ego_desktop_lab.outcome import OutcomeRecord
from ego_desktop_lab.verification_pack import load_scenario


def test_identity_protection_success_stabilizes_boundary(tmp_path: Path) -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/identity_conflict_same_goal.json"))
    outcome = OutcomeRecord(
        scenario_id=scenario.name,
        selected_intention_id="intention:002:preserve_identity_boundary",
        selected_plan_id="preserve_identity_boundary",
        expected_effect="protect identity boundary",
        actual_effect="identity_protection_success",
        success_score=0.90,
        user_feedback="identity boundary was protected",
        prediction_error=0.05,
        evidence_refs=("test:identity_success",),
    )

    result = run_learning_cycle(
        scenario.state,
        scenario.belief_state,
        outcome,
        evidence_log_path=tmp_path / "learning.jsonl",
        timestamp=scenario.timestamp,
    )

    assert result.before_result.selected_intention is not None
    assert result.before_result.selected_intention.goal == "preserve_identity_boundary"
    assert (
        result.strategy_memory_after["preserve_identity"].confidence
        > result.strategy_memory_before["preserve_identity"].confidence
    )
    assert (
        result.next_result.affordance_pressure["preserve_identity"]
        <= result.before_result.affordance_pressure["preserve_identity"]
    )
    assert evaluate_gate("identity_modify").status == "block"
