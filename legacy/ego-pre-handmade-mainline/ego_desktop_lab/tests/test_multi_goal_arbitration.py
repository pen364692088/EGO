from pathlib import Path

from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState
from ego_desktop_lab.verification_pack import build_priority_table


def test_multi_goal_arbitration_uses_goal_id_and_priority_explanation(tmp_path: Path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.72,
        risk_sensitivity=0.60,
        unfinished_goals=(
            {
                "goal_id": "goal:low",
                "description": "low salience documentation cleanup",
                "salience": 0.10,
            },
            {
                "goal_id": "goal:high",
                "description": "high salience repair proof",
                "salience": 0.95,
            },
        ),
        recent_failures=(),
        identity_conflict=False,
    )
    belief = BeliefState(
        known_facts=("evidence exists",),
        unknowns=(),
        assumptions=(),
        evidence_strength=0.95,
        confidence=0.92,
    )

    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "multi_goal.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    table = build_priority_table(result)
    high_rows = [row for row in table if row["goal_id"] == "goal:high"]
    low_rows = [row for row in table if row["goal_id"] == "goal:low"]

    assert result.selected_intention is not None
    assert result.selected_intention.goal_id == "goal:high"
    assert result.selected_intention.goal_description == "high salience repair proof"
    assert high_rows
    assert low_rows
    assert max(row["priority"] for row in high_rows) > max(row["priority"] for row in low_rows)
