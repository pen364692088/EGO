import json
from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt")
AMBIGUOUS_SCENARIO = Path("ego_desktop_lab/semantic_scenarios/ambiguous_user_concern.txt")


def test_llm_proposal_can_affect_next_core_cycle_only_after_validation(tmp_path: Path) -> None:
    accepted = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "accepted.jsonl",
    )
    unbound = run_semantic_scenario(
        AMBIGUOUS_SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "unbound.jsonl",
    )
    invalid = run_semantic_scenario(
        SCENARIO,
        mock_payloads={
            "semantic": json.dumps(
                {
                    "source_event_id": "event:test",
                    "candidate_failure_type": "evidence_failure",
                    "evidence_gap": 0.90,
                    "goal_relevance": 0.80,
                    "risk_hint": 0.40,
                    "confidence": 0.82,
                    "evidence_refs": ("hallucinated:evidence",),
                    "related_goal_id": "goal:001",
                    "binding_status": "bound",
                    "rationale": "This should be rejected because the evidence ref is not allowed.",
                },
                sort_keys=True,
            )
        },
        evidence_log_path=tmp_path / "invalid.jsonl",
    )

    assert accepted.handoff.applied is True
    assert accepted.next_core_result is not None
    assert accepted.next_core_result.belief_state != accepted.core_result.belief_state
    assert accepted.next_core_cycle_influence["applied"] is True

    assert unbound.handoff.applied is False
    assert unbound.next_core_result is None
    assert unbound.next_core_cycle_influence["applied"] is False

    assert invalid.semantic_proposal is None
    assert invalid.handoff.applied is False
    assert invalid.next_core_result is None
    assert "unrecognized refs" in invalid.rejected_proposals[0]["reason"]
