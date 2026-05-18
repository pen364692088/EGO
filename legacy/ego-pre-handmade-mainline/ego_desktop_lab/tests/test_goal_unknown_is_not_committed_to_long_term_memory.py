from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.goal_progress import GoalProgressState
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario
from ego_desktop_lab.strategy_memory import StrategyMemory


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/ambiguous_user_concern.txt")


def test_goal_unknown_is_not_committed_to_long_term_memory(tmp_path: Path) -> None:
    evidence_path = tmp_path / "semantic.jsonl"
    progress_before = GoalProgressState(goal_id="goal:001", progress_score=0.25)
    memory_before: dict[str, StrategyMemory] = {}

    result = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=evidence_path,
    )
    records = read_evidence_records(evidence_path)

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.related_goal_id is None
    assert result.semantic_proposal.binding_status == "pending_goal_binding"
    assert result.handoff.applied is False
    assert progress_before == GoalProgressState(goal_id="goal:001", progress_score=0.25)
    assert memory_before == {}
    assert records[-1]["pending_goal_binding"] is True
    assert records[-1]["strategy_memory_after"] is None
    assert records[-1]["goal_progress_after"] is None
