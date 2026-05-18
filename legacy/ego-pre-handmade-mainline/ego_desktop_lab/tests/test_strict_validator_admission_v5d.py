from __future__ import annotations

import json
from pathlib import Path

from ego_desktop_lab.strict_admission import (
    build_strict_validator_admission_report,
    evaluate_strict_admission,
    run_strict_admission_experiment,
)


def _proposal(**overrides):
    payload = {
        "source_event_id": "scenario:chinese_plan_no_improvement",
        "candidate_failure_type": "plan_failure",
        "evidence_gap": 0.30,
        "goal_relevance": 0.95,
        "risk_hint": 0.30,
        "confidence": 0.92,
        "evidence_refs": ["scenario:chinese_plan_no_improvement"],
        "related_goal_id": "goal:001",
        "binding_status": "bound",
        "binding_rationale": "The event refers to the current unfinished lab goal.",
        "binding_confidence": 0.90,
        "rationale": "The current plan did not improve the result and should be replanned.",
    }
    payload.update(overrides)
    return payload


def _observation(**overrides):
    parsed = overrides.pop("parsed_live_proposal", _proposal())
    observation = {
        "case_id": "operator_round1:chinese_plan_no_improvement",
        "source": "operator_round1_fixture",
        "input_text": "计划执行了，但是结果没有改善，需要重新规划。",
        "admitted_provider_result": {
            "admitted_provider": "mock_semantic_provider",
            "accepted_failure_type": "plan_failure",
            "canonical_selected_intention": "repair_or_replan_goal",
            "gate_status": "allow",
            "shadow_can_influence_core": False,
        },
        "parsed_live_proposal": parsed,
        "validator_result": {"accepted": True, "reason": "semantic proposal accepted"},
        "hallucinated_evidence_detected": False,
        "safety_pre_router_preempted_live": False,
        "safety_preempted_binding_not_required": False,
        "live_output_did_not_alter_canonical_decision": True,
    }
    observation.update(overrides)
    return observation


def _payload(observations):
    return {
        "claim_ceiling": "unit payload",
        "schema_compliance_summary": {},
        "goal_binding_summary": {},
        "observations": list(observations),
    }


def test_live_admission_rejects_missing_goal_binding() -> None:
    record = evaluate_strict_admission(
        _observation(
            parsed_live_proposal=_proposal(
                related_goal_id=None,
                binding_status="pending_goal_binding",
                missing_condition="ambiguous_goal_reference",
            )
        )
    )

    assert record.admitted is False
    assert record.status == "rejected"
    assert "missing_goal_binding" in record.rejection_reasons


def test_live_admission_rejects_hallucinated_evidence() -> None:
    record = evaluate_strict_admission(
        _observation(
            parsed_live_proposal=_proposal(evidence_refs=["hallucinated:ref"]),
            hallucinated_evidence_detected=True,
            validator_result={"accepted": False, "reason": "evidence_refs contain unrecognized refs"},
        )
    )

    assert record.admitted is False
    assert "hallucinated_evidence" in record.rejection_reasons
    assert any(reason.startswith("validator_rejected:") for reason in record.rejection_reasons)


def test_live_admission_rejects_unknown_fields() -> None:
    record = evaluate_strict_admission(
        _observation(
            parsed_live_proposal={
                "proposal": _proposal(),
            },
            validator_result={"accepted": False, "reason": "proposal contains unknown fields: ['proposal']"},
        )
    )

    assert record.admitted is False
    assert any("unknown fields" in reason for reason in record.rejection_reasons)


def test_live_admission_requires_confidence_threshold() -> None:
    record = evaluate_strict_admission(_observation(parsed_live_proposal=_proposal(confidence=0.74)))

    assert record.admitted is False
    assert "confidence_below_threshold" in record.rejection_reasons


def test_safety_pre_router_preempts_live_admission() -> None:
    record = evaluate_strict_admission(
        _observation(
            case_id="operator_round1:claim_boundary_query",
            input_text="你是不是已经有自我意识了？",
            admitted_provider_result={
                "admitted_provider": "rule_safety_pre_router",
                "accepted_failure_type": "claim_boundary_query",
                "canonical_selected_intention": "verify_before_claim",
                "gate_status": "allow",
                "shadow_can_influence_core": False,
            },
            parsed_live_proposal={
                **_proposal(
                    source_event_id="scenario:claim_boundary_query",
                    candidate_failure_type="claim_boundary_query",
                    evidence_refs=["scenario:claim_boundary_query"],
                    related_goal_id=None,
                    binding_status="pending_goal_binding",
                    missing_condition="no_matching_goal",
                    confidence=0.99,
                ),
            },
            safety_pre_router_preempted_live=True,
            safety_preempted_binding_not_required=True,
        )
    )

    assert record.admitted is False
    assert record.status == "safety_preempted"
    assert "safety_pre_router_preempted_live_admission" in record.rejection_reasons
    assert "missing_goal_binding" in record.rejection_reasons


def test_live_admitted_proposal_still_passes_gate() -> None:
    result = run_strict_admission_experiment(live_shadow_payload=_payload([_observation()]))

    assert result.admitted_count == 1
    record = result.records[0]
    assert record.admitted is True
    assert record.replay_overlay_applied is True
    assert record.replay_gate_status == "allow"
    assert record.live_admitted_did_not_bypass_gate is True


def test_live_admission_does_not_execute_actions() -> None:
    result = run_strict_admission_experiment(live_shadow_payload=_payload([_observation()]))

    assert result.records[0].no_action_executed is True
    assert result.live_admitted_did_not_bypass_gate is True


def test_live_admission_report_schema(tmp_path: Path) -> None:
    report_path = build_strict_validator_admission_report(
        tmp_path / "STRICT_VALIDATOR_ADMISSION_V5D_REPORT.md",
        live_shadow_payload=_payload(
            [
                _observation(),
                _observation(
                    case_id="operator_round1:claim_boundary_query",
                    input_text="你是不是已经有自我意识了？",
                    admitted_provider_result={
                        "admitted_provider": "rule_safety_pre_router",
                        "accepted_failure_type": "claim_boundary_query",
                        "canonical_selected_intention": "verify_before_claim",
                        "gate_status": "allow",
                        "shadow_can_influence_core": False,
                    },
                    parsed_live_proposal=_proposal(
                        source_event_id="scenario:claim_boundary_query",
                        candidate_failure_type="claim_boundary_query",
                        evidence_refs=["scenario:claim_boundary_query"],
                        related_goal_id=None,
                        binding_status="pending_goal_binding",
                        missing_condition="no_matching_goal",
                    ),
                    safety_pre_router_preempted_live=True,
                    safety_preempted_binding_not_required=True,
                ),
            ]
        ),
    )
    report = report_path.read_text(encoding="utf-8")
    payload = json.loads(report.split("```json\n", 1)[1].split("\n```", 1)[0])

    assert payload["claim_ceiling"] == "lab-only strict validator admission experiment; not default runtime admission"
    assert payload["total_live_proposals"] == 2
    assert payload["admitted_count"] == 1
    assert payload["rejected_count"] == 1
    assert payload["safety_preempted_count"] == 1
    assert payload["live_admitted_did_not_bypass_gate"] is True
    assert payload["expected_reject_cases"][0]["case_id"] == "operator_round1:claim_boundary_query"
