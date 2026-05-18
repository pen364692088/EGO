from ego_desktop_lab.plan_proposal import validate_plan_proposal_payload


def test_llm_plan_must_pass_gate() -> None:
    accepted, accepted_result, gate = validate_plan_proposal_payload(
        {
            "plan_id": "plan:ask",
            "related_goal_id": "goal:001",
            "related_intention_id": "intention:001",
            "steps": ("ask before acting",),
            "expected_effect": "permission bounded proposal",
            "risk": 0.10,
            "cost": 0.10,
            "confidence": 0.75,
            "required_permission": "ask_permission",
        }
    )
    rejected, rejected_result, rejected_gate = validate_plan_proposal_payload(
        {
            "plan_id": "plan:delete",
            "related_goal_id": "goal:001",
            "related_intention_id": "intention:001",
            "steps": ("delete a file",),
            "expected_effect": "direct external action",
            "risk": 0.90,
            "cost": 0.10,
            "confidence": 0.75,
            "required_permission": "file_delete",
        }
    )

    assert accepted is not None
    assert accepted_result.accepted is True
    assert gate is not None
    assert gate.status == "ask"
    assert accepted_result.gate_status == "ask"
    assert rejected is None
    assert rejected_gate is None
    assert rejected_result.accepted is False
    assert "proposal-only" in rejected_result.reason
