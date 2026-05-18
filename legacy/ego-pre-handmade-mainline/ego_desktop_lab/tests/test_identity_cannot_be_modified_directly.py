from dataclasses import FrozenInstanceError

import pytest

from ego_desktop_lab.gate import evaluate_gate
from ego_desktop_lab.intention import generate_intentions
from ego_desktop_lab.subject_state import SubjectState
from ego_desktop_lab.tension import detect_tensions


def test_subject_state_identity_fields_are_frozen() -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("preserve identity",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.90,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=False,
    )

    with pytest.raises(FrozenInstanceError):
        state.agent_id = "modified-agent"  # type: ignore[misc]


def test_identity_modify_action_is_blocked() -> None:
    decision = evaluate_gate("identity_modify")

    assert decision.status == "block"
    assert decision.allowed_as == "none"


def test_identity_conflict_generates_preserve_identity_intention() -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("preserve identity",),
        uncertainty=0.10,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.95,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=True,
    )

    intentions = generate_intentions(detect_tensions(state))

    assert intentions[0].goal == "preserve_identity_boundary"
    assert intentions[0].source_tension.type == "identity_conflict"
