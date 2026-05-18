from ego_desktop_lab.semantic_proposal import validate_semantic_proposal_payload


def test_llm_failure_type_proposal_requires_validation() -> None:
    accepted, accepted_result = validate_semantic_proposal_payload(
        {
            "source_event_id": "event:001",
            "candidate_failure_type": "plan_failure",
            "confidence": 0.70,
            "evidence_refs": ("event:001",),
            "rationale": "planner failure is plausible",
        }
    )
    rejected, rejected_result = validate_semantic_proposal_payload(
        {
            "source_event_id": "event:001",
            "candidate_failure_type": "unbounded_failure",
            "confidence": 0.70,
            "evidence_refs": ("event:001",),
            "rationale": "unknown failure type",
        }
    )

    assert accepted is not None
    assert accepted.candidate_failure_type == "plan_failure"
    assert accepted_result.accepted is True
    assert rejected is None
    assert rejected_result.accepted is False
    assert "not recognized" in rejected_result.reason
