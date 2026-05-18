from pathlib import Path

from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


def test_unfinished_goal_creates_continue_or_verify_suggestion(tmp_path: Path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.70,
        risk_sensitivity=0.50,
        unfinished_goals=("verify whether reflection changes behavior",),
        recent_failures=(),
        identity_conflict=False,
    )

    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "evidence.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
    )

    assert result.selected_intention is not None
    assert result.selected_intention.goal == "continue_or_verify_unfinished_goal"
    assert "continue or verify unfinished goal" in result.suggestion
