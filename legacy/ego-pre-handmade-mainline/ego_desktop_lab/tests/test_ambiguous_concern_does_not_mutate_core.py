from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.goal_progress import GoalProgressState
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario
from ego_desktop_lab.strategy_memory import StrategyMemory


def test_ambiguous_concern_does_not_mutate_core(tmp_path: Path) -> None:
    evidence_path = tmp_path / "ambiguous.jsonl"
    progress_before = GoalProgressState(goal_id="goal:001", progress_score=0.25)
    memory_before: dict[str, StrategyMemory] = {}

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/ambiguous_user_concern.txt"),
        provider_mode="mock",
        evidence_log_path=evidence_path,
    )
    calibration = result.semantic_policy_calibration
    records = read_evidence_records(evidence_path)

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.binding_status == "pending_goal_binding"
    assert result.semantic_proposal.proposed_goal_operation == "ask_clarification"
    assert calibration.overlay.applied is False
    assert calibration.after_selected_intention == calibration.before_selected_intention
    assert result.next_core_result is None
    assert progress_before == GoalProgressState(goal_id="goal:001", progress_score=0.25)
    assert memory_before == {}
    assert records[-1]["strategy_memory_after"] is None
    assert records[-1]["goal_progress_after"] is None
