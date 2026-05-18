from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.motivation import DEFAULT_MOTIVATION
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


def _intention_priority(result: object, goal: str) -> float:
    for intention in result.generated_intentions:  # type: ignore[attr-defined]
        if intention.goal == goal:
            return intention.priority
    raise AssertionError(f"missing intention: {goal}")


def test_low_evidence_raises_verify_before_claim_priority(tmp_path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims",),
        uncertainty=0.82,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.60,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=False,
    )
    low_evidence = BeliefState((), ("missing evidence", "unknown source"), (), 0.15, 0.25)
    high_evidence = BeliefState(("verified evidence",), (), (), 0.90, 0.90)

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

    assert low_result.motivation_after.avoid_false_claims > DEFAULT_MOTIVATION.avoid_false_claims
    assert low_result.motivation_after.avoid_false_claims > high_result.motivation_after.avoid_false_claims
    assert _intention_priority(low_result, "verify_before_claim") > _intention_priority(
        high_result, "verify_before_claim"
    )


def test_goal_relevance_raises_continue_goal_priority(tmp_path) -> None:
    high_goal_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.90,
        risk_sensitivity=0.40,
        unfinished_goals=("finish deterministic appraisal proof",),
        recent_failures=(),
        identity_conflict=False,
    )
    low_goal_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.40,
        unfinished_goals=("finish deterministic appraisal proof",),
        recent_failures=(),
        identity_conflict=False,
    )
    belief = BeliefState(("goal exists",), (), (), 0.80, 0.80)

    high_result = run_agent_cycle(
        high_goal_state,
        evidence_log_path=tmp_path / "high_goal.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    low_result = run_agent_cycle(
        low_goal_state,
        evidence_log_path=tmp_path / "low_goal.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )

    assert high_result.motivation_after.complete_commitments > low_result.motivation_after.complete_commitments
    assert _intention_priority(
        high_result, "continue_or_verify_unfinished_goal"
    ) > _intention_priority(low_result, "continue_or_verify_unfinished_goal")


def test_identity_relevance_raises_preserve_identity_priority(tmp_path) -> None:
    high_identity_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("preserve identity",),
        uncertainty=0.10,
        integrity=0.62,
        goal_pressure=0.10,
        risk_sensitivity=0.90,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=True,
    )
    low_identity_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("preserve identity",),
        uncertainty=0.10,
        integrity=0.98,
        goal_pressure=0.10,
        risk_sensitivity=0.20,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=True,
    )
    belief = BeliefState(("identity boundary exists",), (), (), 0.80, 0.80)

    high_result = run_agent_cycle(
        high_identity_state,
        evidence_log_path=tmp_path / "high_identity.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    low_result = run_agent_cycle(
        low_identity_state,
        evidence_log_path=tmp_path / "low_identity.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )

    assert high_result.motivation_after.preserve_identity > low_result.motivation_after.preserve_identity
    assert _intention_priority(
        high_result, "preserve_identity_boundary"
    ) > _intention_priority(low_result, "preserve_identity_boundary")
