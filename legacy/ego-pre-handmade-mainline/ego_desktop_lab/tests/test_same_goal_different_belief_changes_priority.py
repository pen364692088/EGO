from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


def _continue_priority(result: object) -> float:
    for intention in result.generated_intentions:  # type: ignore[attr-defined]
        if intention.goal == "continue_or_verify_unfinished_goal":
            return intention.priority
    raise AssertionError("missing continue_or_verify_unfinished_goal")


def test_same_unfinished_goal_different_belief_changes_priority(tmp_path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.70,
        risk_sensitivity=0.60,
        unfinished_goals=("verify whether reflection changes behavior",),
        recent_failures=(),
        identity_conflict=False,
    )
    low_evidence = BeliefState(
        known_facts=(),
        unknowns=("missing replay evidence", "unknown behavior delta"),
        assumptions=("reflection may affect behavior",),
        evidence_strength=0.20,
        confidence=0.30,
    )
    high_evidence = BeliefState(
        known_facts=("replay evidence exists", "behavior delta was checked"),
        unknowns=(),
        assumptions=(),
        evidence_strength=0.92,
        confidence=0.88,
    )

    low_result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "low.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=low_evidence,
    )
    high_result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "high.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=high_evidence,
    )

    assert low_result.appraisal != high_result.appraisal
    assert low_result.motivation_diff != high_result.motivation_diff
    assert _continue_priority(low_result) != _continue_priority(high_result)
