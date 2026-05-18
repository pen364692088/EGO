from ego_desktop_lab.intention import generate_intentions, select_intention
from ego_desktop_lab.subject_state import SubjectState
from ego_desktop_lab.tension import detect_tensions


def test_high_uncertainty_generates_verify_before_claim() -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims",),
        uncertainty=0.81,
        integrity=0.90,
        goal_pressure=0.10,
        risk_sensitivity=0.50,
        unfinished_goals=(),
        recent_failures=(),
        identity_conflict=False,
    )

    tensions = detect_tensions(state)
    intentions = generate_intentions(tensions)

    assert tensions[0].type == "high_uncertainty"
    assert intentions[0].goal == "verify_before_claim"
    assert intentions[0].source_tension == tensions[0]


def test_priority_selection_is_stable_for_mock_state() -> None:
    state = SubjectState(
        agent_id="test-agent",
        core_commitments=("avoid false claims", "complete commitments"),
        uncertainty=0.82,
        integrity=0.90,
        goal_pressure=0.67,
        risk_sensitivity=0.50,
        unfinished_goals=("verify whether reflection changes behavior",),
        recent_failures=(),
        identity_conflict=False,
    )

    intentions = generate_intentions(detect_tensions(state))
    selected = select_intention(intentions)

    assert [intention.goal for intention in intentions] == [
        "continue_or_verify_unfinished_goal",
        "verify_before_claim",
    ]
    assert selected is not None
    assert selected.goal == "verify_before_claim"
