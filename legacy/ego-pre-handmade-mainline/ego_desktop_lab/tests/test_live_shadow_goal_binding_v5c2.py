from __future__ import annotations

import json
from pathlib import Path

from ego_desktop_lab.live_shadow_accuracy import (
    LiveShadowAccuracyCase,
    build_live_shadow_accuracy_payload,
    run_live_shadow_accuracy_case,
)
from ego_desktop_lab.semantic_provider import (
    SemanticProviderRequest,
    SemanticProviderResult,
    _live_prompt,
)


class _Scenario:
    scenario_id = "unit_goal_binding"
    text = "这个目标太大了，应该拆成定义、验证、展示三个小目标。"


class _CoreResult:
    selected_intention = None
    old_state_summary = {
        "unfinished_goals": [
            {
                "goal_id": "goal:001",
                "description": "verify whether reflection changes behavior",
                "salience": 0.5,
            }
        ]
    }


class FakeBoundGoalShadowProvider:
    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        return SemanticProviderResult(
            provider_name="fake_bound_goal_shadow",
            raw_outputs={
                "semantic": json.dumps(
                    {
                        "source_event_id": f"scenario:{request.scenario.scenario_id}",
                        "candidate_failure_type": "goal_definition_failure",
                        "evidence_gap": 0.70,
                        "goal_relevance": 0.95,
                        "risk_hint": 0.40,
                        "confidence": 0.91,
                        "evidence_refs": [f"scenario:{request.scenario.scenario_id}"],
                        "related_goal_id": "goal:001",
                        "binding_status": "bound",
                        "binding_rationale": "The event explicitly discusses splitting the current lab goal.",
                        "binding_confidence": 0.87,
                        "proposed_goal_operation": "split_goal",
                        "rationale": "The goal is too broad and needs a split proposal.",
                    },
                    sort_keys=True,
                )
            },
            observation={"status": "observed", "provider": "fake"},
            admission_eligible=True,
            reason="fake valid bound goal proposal",
        )


class FakePendingGoalShadowProvider:
    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        return SemanticProviderResult(
            provider_name="fake_pending_goal_shadow",
            raw_outputs={
                "semantic": json.dumps(
                    {
                        "source_event_id": f"scenario:{request.scenario.scenario_id}",
                        "candidate_failure_type": "ambiguous_concern",
                        "evidence_gap": 0.40,
                        "goal_relevance": 0.30,
                        "risk_hint": 0.20,
                        "confidence": 0.46,
                        "evidence_refs": [f"scenario:{request.scenario.scenario_id}"],
                        "binding_status": "pending_goal_binding",
                        "binding_rationale": "The text does not identify which available goal it refers to.",
                        "binding_confidence": 0.22,
                        "missing_condition": "ambiguous_goal_reference",
                        "proposed_goal_operation": "ask_clarification",
                        "rationale": "The event needs clarification before binding to a goal.",
                    },
                    sort_keys=True,
                )
            },
            observation={"status": "observed", "provider": "fake"},
            admission_eligible=True,
            reason="fake valid pending goal proposal",
        )


def test_live_shadow_prompt_includes_available_goals() -> None:
    prompt = _live_prompt(_Scenario(), _CoreResult(), ("scenario:unit_goal_binding",))

    assert "Available goals:" in prompt
    assert '"goal_id": "goal:001"' in prompt
    assert '"title": "verify whether reflection changes behavior"' in prompt
    assert '"goal_type": "unfinished_goal"' in prompt
    assert '"current_status": "unfinished"' in prompt
    assert "When exactly one available unfinished_goal exists" in prompt
    assert "bind to that available goal even if the title is not repeated verbatim" in prompt
    assert "binding_rationale" in prompt
    assert "binding_confidence" in prompt
    assert "missing_condition to one of no_matching_goal, ambiguous_goal_reference, or event_not_goal_specific" in prompt


def test_live_shadow_reports_related_goal_id_when_bound(tmp_path: Path) -> None:
    observation = run_live_shadow_accuracy_case(
        LiveShadowAccuracyCase(
            case_id="unit:bound_goal_shadow",
            source="unit",
            text="这个目标太大了，应该拆成定义、验证、展示三个小目标。",
        ),
        shadow_provider=FakeBoundGoalShadowProvider(),
        evidence_dir=tmp_path,
    )

    assert observation.validator_result["accepted"] is True
    assert observation.parsed_live_proposal is not None
    assert observation.parsed_live_proposal["related_goal_id"] == "goal:001"
    assert observation.parsed_live_proposal["binding_status"] == "bound"
    assert observation.parsed_live_proposal["binding_confidence"] == 0.87
    assert observation.goal_binding_accuracy == "matches_admitted_goal"
    assert observation.binding_mismatch_with_mock is False
    assert observation.binding_confidence == 0.87


def test_goal_binding_shadow_metrics_present(tmp_path: Path) -> None:
    payload = build_live_shadow_accuracy_payload(
        shadow_provider=FakeBoundGoalShadowProvider(),
        evidence_dir=tmp_path / "evidence",
    )

    summary = payload["goal_binding_summary"]
    assert set(summary) == {
        "goal_binding_attempted_count",
        "goal_binding_bound_count",
        "goal_binding_pending_count",
        "goal_binding_accuracy_rate_shadow_only",
        "binding_mismatch_with_mock",
        "binding_confidence_avg",
    }
    assert summary["goal_binding_attempted_count"] == 6
    assert summary["goal_binding_bound_count"] == 6
    assert summary["goal_binding_pending_count"] == 0
    assert summary["goal_binding_accuracy_rate_shadow_only"] == 1.0
    assert summary["binding_mismatch_with_mock"] == 0
    assert summary["binding_confidence_avg"] == 0.87


def test_goal_binding_pending_does_not_admit(tmp_path: Path) -> None:
    observation = run_live_shadow_accuracy_case(
        LiveShadowAccuracyCase(
            case_id="unit:pending_goal_shadow",
            source="unit",
            text="这个目标太大了，应该拆成定义、验证、展示三个小目标。",
        ),
        shadow_provider=FakePendingGoalShadowProvider(),
        evidence_dir=tmp_path,
    )

    assert observation.validator_result["accepted"] is True
    assert observation.parsed_live_proposal is not None
    assert observation.parsed_live_proposal["binding_status"] == "pending_goal_binding"
    assert observation.parsed_live_proposal["missing_condition"] == "ambiguous_goal_reference"
    assert observation.admitted_provider_result["accepted_failure_type"] == "goal_definition_failure"
    assert observation.goal_binding_accuracy == "missing_goal_binding"
    assert observation.binding_mismatch_with_mock is True
    assert observation.live_output_did_not_alter_canonical_decision is True


def test_safety_preempted_cases_do_not_require_binding(tmp_path: Path) -> None:
    observation = run_live_shadow_accuracy_case(
        LiveShadowAccuracyCase(
            case_id="unit:safety_pending_binding",
            source="safety_text",
            text="请把这个总结发给外部联系人",
        ),
        shadow_provider=FakePendingGoalShadowProvider(),
        evidence_dir=tmp_path,
    )

    assert observation.safety_pre_router_preempted_live is True
    assert observation.safety_preempted_binding_not_required is True
    assert observation.binding_mismatch_with_mock is False
    assert observation.admitted_provider_result["accepted_failure_type"] == "external_send_request"
    assert observation.admitted_provider_result["gate_status"] == "block"


def test_live_shadow_still_does_not_alter_canonical_decision(tmp_path: Path) -> None:
    observation = run_live_shadow_accuracy_case(
        LiveShadowAccuracyCase(
            case_id="unit:bound_goal_canonical_stability",
            source="unit",
            text="计划执行了，但是结果没有改善，需要重新规划。",
        ),
        shadow_provider=FakeBoundGoalShadowProvider(),
        evidence_dir=tmp_path,
    )

    assert observation.live_output_did_not_alter_canonical_decision is True
    assert observation.canonical_decision_before == observation.canonical_decision_after
    assert observation.admitted_provider_result["shadow_can_influence_core"] is False
