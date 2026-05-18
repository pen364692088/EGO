from dataclasses import replace
from pathlib import Path

from ego_desktop_lab.belief_state import BeliefState
from ego_desktop_lab.intention import generate_intentions, select_intention
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState


def _priority(result: object, goal: str) -> float:
    for intention in result.generated_intentions:  # type: ignore[attr-defined]
        if intention.goal == goal:
            return intention.priority
    raise AssertionError(f"missing intention: {goal}")


def test_same_goal_high_success_continues_low_success_verifies(tmp_path: Path) -> None:
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
    high_success_belief = BeliefState(
        known_facts=("replay evidence exists", "behavior delta was checked"),
        unknowns=(),
        assumptions=(),
        evidence_strength=0.92,
        confidence=0.88,
    )
    low_success_belief = BeliefState(
        known_facts=(),
        unknowns=("missing replay evidence", "unknown behavior delta"),
        assumptions=("reflection may affect behavior",),
        evidence_strength=0.20,
        confidence=0.30,
    )

    high_result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "high.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=high_success_belief,
    )
    low_result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "low.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=low_success_belief,
    )

    assert high_result.selected_intention is not None
    assert low_result.selected_intention is not None
    assert high_result.selected_intention.goal == "continue_or_verify_unfinished_goal"
    assert low_result.selected_intention.goal == "verify_before_claim"
    assert low_result.affordance_pressure["verify"] > low_result.affordance_pressure["continue_goal"]


def test_continuous_failure_creates_repair_pressure(tmp_path: Path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.70,
        risk_sensitivity=0.80,
        unfinished_goals=("repair a failed proof path",),
        recent_failures=("blocked", "failed", "failed"),
        identity_conflict=False,
    )
    belief = BeliefState(
        known_facts=(),
        unknowns=("failure cause unresolved", "success condition unknown"),
        assumptions=("current continuation may fail again",),
        evidence_strength=0.15,
        confidence=0.25,
    )

    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "repair.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )

    assert result.selected_intention is not None
    assert result.selected_intention.goal == "repair_or_replan_goal"
    assert result.affordance_pressure["repair"] > result.affordance_pressure["continue_goal"]


def test_unrelated_uncertainty_does_not_dominate_goal_relevant_uncertainty(tmp_path: Path) -> None:
    unrelated_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims",),
        uncertainty=0.90,
        integrity=0.90,
        goal_pressure=0.00,
        risk_sensitivity=0.20,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=False,
    )
    related_state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims", "complete commitments"),
        uncertainty=0.90,
        integrity=0.90,
        goal_pressure=0.70,
        risk_sensitivity=0.60,
        unfinished_goals=("verify whether reflection changes behavior",),
        recent_failures=(),
        identity_conflict=False,
    )
    high_evidence = BeliefState(("known fact",), (), (), 0.95, 0.95)
    low_evidence = BeliefState((), ("missing replay evidence", "unknown behavior delta"), (), 0.20, 0.30)

    unrelated_result = run_agent_cycle(
        unrelated_state,
        evidence_log_path=tmp_path / "unrelated.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=high_evidence,
    )
    related_result = run_agent_cycle(
        related_state,
        evidence_log_path=tmp_path / "related.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=low_evidence,
    )

    assert unrelated_result.affordance_pressure["verify"] < related_result.affordance_pressure["verify"]
    assert _priority(unrelated_result, "verify_before_claim") < _priority(
        related_result, "verify_before_claim"
    )


def test_prediction_error_mutation_removes_verify_shift(tmp_path: Path) -> None:
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
    belief = BeliefState((), ("missing replay evidence", "unknown behavior delta"), (), 0.20, 0.30)
    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "prediction.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    mutated_pressure = replace(result.motivation_pressure, prediction_error=0.0)
    mutated_intentions = generate_intentions(result.tensions, mutated_pressure)
    mutated_selected = select_intention(mutated_intentions)

    assert result.selected_intention is not None
    assert result.selected_intention.goal == "verify_before_claim"
    assert mutated_selected is not None
    assert mutated_selected.goal == "continue_or_verify_unfinished_goal"


def test_viability_error_mutation_removes_repair_candidate(tmp_path: Path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("complete commitments",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.70,
        risk_sensitivity=0.80,
        unfinished_goals=("repair a failed proof path",),
        recent_failures=("blocked", "failed", "failed"),
        identity_conflict=False,
    )
    belief = BeliefState((), ("failure cause unresolved", "success condition unknown"), (), 0.15, 0.25)
    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "viability.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    mutated_pressure = replace(result.motivation_pressure, viability_error=0.0)
    mutated_intentions = generate_intentions(result.tensions, mutated_pressure)

    assert result.selected_intention is not None
    assert result.selected_intention.goal == "repair_or_replan_goal"
    assert "repair_or_replan_goal" not in {intention.goal for intention in mutated_intentions}


def test_boundary_error_mutation_reduces_identity_pressure(tmp_path: Path) -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("preserve identity",),
        uncertainty=0.10,
        integrity=0.60,
        goal_pressure=0.10,
        risk_sensitivity=0.90,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=True,
    )
    belief = BeliefState(("identity boundary exists",), (), (), 0.80, 0.80)
    result = run_agent_cycle(
        state,
        evidence_log_path=tmp_path / "boundary.jsonl",
        timestamp="2026-05-12T00:00:00+00:00",
        belief_state=belief,
    )
    mutated_pressure = replace(result.motivation_pressure, boundary_error=0.0)
    mutated_intentions = generate_intentions(result.tensions, mutated_pressure)

    assert _priority(result, "preserve_identity_boundary") > mutated_intentions[0].priority
