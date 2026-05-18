from ego_desktop_lab.goal_progress import FailureType
from ego_desktop_lab.oscillation import route_failure_type


def test_failure_type_routes_to_different_intention() -> None:
    assert route_failure_type(FailureType.evidence_failure) == "verify_before_claim"
    assert route_failure_type(FailureType.plan_failure) == "repair_or_replan_goal"
    assert route_failure_type(FailureType.goal_definition_failure) == "reframe_or_split_goal"
    assert route_failure_type(FailureType.permission_failure) == "ask_permission_or_defer"
    assert route_failure_type(FailureType.execution_failure) == "retry_or_change_tool"
