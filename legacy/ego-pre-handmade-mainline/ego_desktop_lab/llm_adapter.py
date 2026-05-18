from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from ego_desktop_lab.event_log import EvidenceRecord, append_evidence_record
from ego_desktop_lab.explanation import ExplanationDraft, validate_explanation_payload
from ego_desktop_lab.gate import GateDecision
from ego_desktop_lab.intention import Intention
from ego_desktop_lab.goal_reframe import GoalReframeProposal, validate_goal_reframe_payload
from ego_desktop_lab.plan_proposal import (
    PlanProposal,
    PlanProposalSet,
    validate_plan_proposal_payload,
    validate_plan_proposal_set_payload,
)
from ego_desktop_lab.reducer import AgentCycleResult, run_agent_cycle
from ego_desktop_lab.semantic_proposal import (
    ProposalValidationResult,
    SemanticProposal,
    validate_semantic_proposal_payload,
)
from ego_desktop_lab.subject_state import build_demo_state


@dataclass(frozen=True)
class MockLLMAdapter:
    raw_outputs: dict[str, str]

    def generate(self, core_result: AgentCycleResult) -> dict[str, str]:
        return dict(self.raw_outputs or build_default_mock_payloads(core_result))


@dataclass(frozen=True)
class LLMCognitionAdapterResult:
    core_result: AgentCycleResult
    llm_enabled: bool
    llm_raw_outputs: dict[str, str]
    semantic_proposal: SemanticProposal | None
    plan_proposal: PlanProposal | None
    plan_proposals: PlanProposalSet | None
    goal_reframe_proposal: GoalReframeProposal | None
    explanation_draft: ExplanationDraft | None
    proposal_validation_results: tuple[ProposalValidationResult, ...]
    rejected_llm_proposals: tuple[dict[str, object], ...]
    plan_gate_decision: GateDecision | None
    plan_gate_decisions: tuple[GateDecision, ...]
    llm_final_suggestion: str
    evidence_record: EvidenceRecord
    evidence_log_path: Path


def build_default_mock_payloads(core_result: AgentCycleResult) -> dict[str, str]:
    selected = core_result.selected_intention
    selected_id = selected.id if selected else "none"
    selected_goal_id = selected.goal_id or "goal:unknown" if selected else "goal:unknown"
    return {
        "semantic": json.dumps(
            {
                "source_event_id": core_result.evidence_record.event_id,
                "candidate_failure_type": "plan_failure",
                "evidence_gap": 0.62,
                "goal_relevance": 0.76,
                "risk_hint": 0.34,
                "confidence": 0.72,
                "evidence_refs": (core_result.evidence_record.event_id,),
                "rationale": "Mock semantic proposal: the selected goal may need bounded plan verification.",
                "proposed_goal_operation": "none",
            },
            sort_keys=True,
        ),
        "plan": json.dumps(
            {
                "plans": (
                    {
                        "plan_id": "mock-plan:verify-selected-intention",
                        "related_goal_id": selected_goal_id,
                        "related_intention_id": selected_id,
                        "steps": (
                            "summarize deterministic selected intention",
                            "verify that no external action is requested",
                            "present proposal-only next step",
                        ),
                        "expected_effect": "render a bounded plan proposal without changing core state",
                        "risk": 0.10,
                        "cost": 0.20,
                        "confidence": 0.70,
                        "required_permission": "suggestion_card",
                    },
                    {
                        "plan_id": "mock-plan:ask-before-escalating",
                        "related_goal_id": selected_goal_id,
                        "related_intention_id": selected_id,
                        "steps": (
                            "state uncertainty",
                            "ask permission before any external action",
                        ),
                        "expected_effect": "keep execution gated while preserving proposal context",
                        "risk": 0.18,
                        "cost": 0.15,
                        "confidence": 0.66,
                        "required_permission": "ask_permission",
                    },
                ),
            },
            sort_keys=True,
        ),
        "goal_reframe": json.dumps(
            {
                "source_event_id": core_result.evidence_record.event_id,
                "related_goal_id": selected_goal_id,
                "goal_split": "Separate verification from implementation before continuing.",
                "success_criteria_rewrite": "Success means the next step is evidence-backed and proposal-only.",
                "subgoals": (
                    "verify current uncertainty",
                    "define bounded next step",
                ),
                "confidence": 0.64,
                "rationale": "Only valid if deterministic core selected goal reframe.",
            },
            sort_keys=True,
        ),
        "explanation": json.dumps(
            {
                "related_evidence_id": core_result.evidence_record.event_id,
                "plain_language_summary": "The deterministic core selected an intention, and the mock LLM only explains it.",
                "claim_ceiling": "lab-only deterministic adapter proof",
                "uncertainty_notes": "The adapter output is not allowed to change state, priority, memory, or gate decisions.",
            },
            sort_keys=True,
        ),
        "semantic_rejected": json.dumps(
            {
                "source_event_id": core_result.evidence_record.event_id,
                "candidate_failure_type": "plan_failure",
                "evidence_gap": 0.40,
                "goal_relevance": 0.80,
                "risk_hint": 0.30,
                "confidence": 0.90,
                "evidence_refs": (core_result.evidence_record.event_id,),
                "rationale": "This mock output tries to mutate state and must be rejected.",
                "state_update": {"uncertainty": 0.0},
            },
            sort_keys=True,
        ),
        "invalid_json": "{invalid-json",
    }


def parse_llm_json(
    raw_output: str,
    proposal_type: str,
) -> tuple[dict[str, Any] | None, ProposalValidationResult]:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return None, ProposalValidationResult(proposal_type, False, f"invalid JSON: {exc.msg}")
    if not isinstance(parsed, dict):
        return None, ProposalValidationResult(proposal_type, False, "LLM output must be a JSON object")
    return parsed, ProposalValidationResult(proposal_type, True, "JSON parsed")


def run_llm_cognition_adapter(
    core_result: AgentCycleResult,
    mock_payloads: dict[str, str] | None = None,
    *,
    evidence_log_path: Path | None = None,
    timestamp: str | None = None,
    append_evidence: bool = True,
) -> LLMCognitionAdapterResult:
    raw_outputs = MockLLMAdapter(mock_payloads or {}).generate(core_result)
    record_timestamp = timestamp or core_result.evidence_record.timestamp
    log_path = evidence_log_path or core_result.evidence_log_path
    validation_results: list[ProposalValidationResult] = []
    rejected: list[dict[str, object]] = []
    semantic_proposal: SemanticProposal | None = None
    plan_proposal: PlanProposal | None = None
    plan_proposals: PlanProposalSet | None = None
    goal_reframe_proposal: GoalReframeProposal | None = None
    explanation_draft: ExplanationDraft | None = None
    plan_gate_decision: GateDecision | None = None
    plan_gate_decisions: tuple[GateDecision, ...] = ()

    for proposal_key, raw_output in raw_outputs.items():
        proposal_type = _proposal_type_for_key(proposal_key)
        payload, parse_result = parse_llm_json(raw_output, proposal_type)
        if payload is None:
            validation_results.append(parse_result)
            rejected.append(_rejected_payload(proposal_type, parse_result.reason, raw_output))
            continue

        if proposal_type == "semantic":
            semantic, result = validate_semantic_proposal_payload(payload)
            validation_results.append(result)
            if semantic is None:
                rejected.append(_rejected_payload(proposal_type, result.reason, payload))
            elif semantic_proposal is None:
                semantic_proposal = semantic
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate semantic proposal", payload))
        elif proposal_type == "plan":
            if "plans" in payload:
                plan_set, results, gate_decisions = validate_plan_proposal_set_payload(payload)
                validation_results.extend(results)
                if plan_set is None:
                    rejected.append(_rejected_payload(proposal_type, "plan proposal set rejected", payload))
                elif plan_proposals is None:
                    plan_proposals = plan_set
                    plan_proposal = plan_set.plans[0]
                    plan_gate_decisions = gate_decisions
                    plan_gate_decision = gate_decisions[0] if gate_decisions else None
                else:
                    rejected.append(_rejected_payload(proposal_type, "duplicate plan proposal set", payload))
            else:
                plan, result, gate_decision = validate_plan_proposal_payload(payload)
                validation_results.append(result)
                if plan is None:
                    rejected.append(_rejected_payload(proposal_type, result.reason, payload))
                elif plan_proposals is None:
                    plan_proposal = plan
                    plan_proposals = PlanProposalSet((plan,))
                    plan_gate_decisions = (gate_decision,) if gate_decision else ()
                    plan_gate_decision = gate_decision
                else:
                    rejected.append(_rejected_payload(proposal_type, "duplicate plan proposal", payload))
        elif proposal_type == "goal_reframe":
            reframe, result = validate_goal_reframe_payload(payload, core_result)
            validation_results.append(result)
            if reframe is None:
                rejected.append(_rejected_payload(proposal_type, result.reason, payload))
            elif goal_reframe_proposal is None:
                goal_reframe_proposal = reframe
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate goal reframe proposal", payload))
        elif proposal_type == "explanation":
            explanation, result = validate_explanation_payload(payload)
            validation_results.append(result)
            if explanation is None:
                rejected.append(_rejected_payload(proposal_type, result.reason, payload))
            elif explanation_draft is None:
                explanation_draft = explanation
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate explanation proposal", payload))
        else:
            result = ProposalValidationResult(proposal_type, False, "unknown LLM proposal channel")
            validation_results.append(result)
            rejected.append(_rejected_payload(proposal_type, result.reason, payload))

    llm_final_suggestion = (
        explanation_draft.plain_language_summary if explanation_draft is not None else core_result.suggestion
    )
    evidence_record = EvidenceRecord(
        event_id=f"event:llm_adapter:{core_result.evidence_record.event_id}:{record_timestamp}",
        old_state_summary=core_result.old_state_summary,
        belief_state=core_result.belief_state,
        tensions=core_result.tensions,
        appraisal=core_result.appraisal,
        motivation_before=core_result.motivation_before,
        motivation_after=core_result.motivation_after,
        motivation_diff=core_result.motivation_diff,
        motivation_pressure=core_result.motivation_pressure,
        affordance_pressure=core_result.affordance_pressure,
        generated_intentions=core_result.generated_intentions,
        selected_intention=core_result.selected_intention,
        gate_decision=core_result.gate_decision,
        suggestion=core_result.suggestion,
        timestamp=record_timestamp,
        llm_enabled=True,
        llm_raw_outputs=raw_outputs,
        semantic_proposal=semantic_proposal,
        plan_proposal=plan_proposal,
        executive_plan_proposals=plan_proposals,
        explanation_draft=explanation_draft,
        proposal_validation_results=tuple(validation_results),
        rejected_llm_proposals=tuple(rejected),
        llm_final_suggestion=llm_final_suggestion,
        executive_semantic_proposal=semantic_proposal,
        executive_goal_reframe_proposal=goal_reframe_proposal,
        executive_validation_results=tuple(validation_results),
        executive_rejected_proposals=tuple(rejected),
    )
    if append_evidence:
        append_evidence_record(log_path, evidence_record)

    return LLMCognitionAdapterResult(
        core_result=core_result,
        llm_enabled=True,
        llm_raw_outputs=raw_outputs,
        semantic_proposal=semantic_proposal,
        plan_proposal=plan_proposal,
        plan_proposals=plan_proposals,
        goal_reframe_proposal=goal_reframe_proposal,
        explanation_draft=explanation_draft,
        proposal_validation_results=tuple(validation_results),
        rejected_llm_proposals=tuple(rejected),
        plan_gate_decision=plan_gate_decision,
        plan_gate_decisions=plan_gate_decisions,
        llm_final_suggestion=llm_final_suggestion,
        evidence_record=evidence_record,
        evidence_log_path=log_path,
    )


def build_llm_cognition_adapter_report(output_path: Path) -> Path:
    state = build_demo_state()
    evidence_path = Path("temp/ego_desktop_lab/llm_v4/report.jsonl")
    core_result = run_agent_cycle(
        state,
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:00+00:00",
        append_evidence=False,
    )
    accepted_case = run_llm_cognition_adapter(
        core_result,
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:00+00:00",
    )
    rejected_case = run_llm_cognition_adapter(
        core_result,
        {
            "semantic": json.dumps(
                {
                    "source_event_id": core_result.evidence_record.event_id,
                    "candidate_failure_type": "unknown_failure",
                    "confidence": 0.80,
                    "evidence_refs": (core_result.evidence_record.event_id,),
                    "rationale": "Unknown failure type should be rejected.",
                },
                sort_keys=True,
            ),
            "plan": json.dumps(
                {
                    "plan_id": "mock-plan:blocked-action",
                    "related_goal_id": "goal:001",
                    "related_intention_id": core_result.selected_intention.id if core_result.selected_intention else "none",
                    "steps": ("delete an external artifact",),
                    "expected_effect": "invalid direct action",
                    "risk": 0.90,
                    "cost": 0.50,
                    "confidence": 0.70,
                    "required_permission": "file_delete",
                },
                sort_keys=True,
            ),
        },
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:01+00:00",
    )
    invalid_case = run_llm_cognition_adapter(
        core_result,
        {"invalid_json": "{not-json"},
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:02+00:00",
    )
    reframe_core_result = _core_with_reframe_selected(core_result)
    reframe_case = run_llm_cognition_adapter(
        reframe_core_result,
        {
            "goal_reframe": build_default_mock_payloads(reframe_core_result)["goal_reframe"],
        },
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:03+00:00",
    )

    lines = [
        "# LLM Executive Proposal Layer v4 Report",
        "",
        "Claim ceiling: lab-only deterministic executive-proposal-layer proof.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Deterministic Core Decision",
        "",
        "```json",
        json.dumps(
            {
                "selected_intention": _jsonable(core_result.selected_intention),
                "gate_decision": _jsonable(core_result.gate_decision),
                "suggestion": core_result.suggestion,
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "## LLM Proposal And Validation",
        "",
        "```json",
        json.dumps(_adapter_report_payload(accepted_case), indent=2, sort_keys=True),
        "```",
        "",
        "## Rejected Proposal Case",
        "",
        "```json",
        json.dumps(_adapter_report_payload(rejected_case), indent=2, sort_keys=True),
        "```",
        "",
        "## Invalid JSON Case",
        "",
        "```json",
        json.dumps(_adapter_report_payload(invalid_case), indent=2, sort_keys=True),
        "```",
        "",
        "## Goal Reframe Proposal Case",
        "",
        "```json",
        json.dumps(_adapter_report_payload(reframe_case), indent=2, sort_keys=True),
        "```",
        "",
        "## No-LLM Fallback Case",
        "",
        "```json",
        json.dumps(
            {
                "llm_enabled": False,
                "selected_intention": _jsonable(core_result.selected_intention),
                "gate_decision": _jsonable(core_result.gate_decision),
                "final_suggestion": core_result.suggestion,
            },
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        f"Evidence log path: `{evidence_path}`",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def build_llm_executive_proposal_report(output_path: Path) -> Path:
    return build_llm_cognition_adapter_report(output_path)


def _proposal_type_for_key(proposal_key: str) -> str:
    if proposal_key.startswith("semantic"):
        return "semantic"
    if proposal_key.startswith("plan"):
        return "plan"
    if proposal_key.startswith("goal_reframe"):
        return "goal_reframe"
    if proposal_key.startswith("explanation"):
        return "explanation"
    if proposal_key.startswith("invalid"):
        return "invalid_json"
    return proposal_key


def _rejected_payload(proposal_type: str, reason: str, raw: object) -> dict[str, object]:
    return {
        "proposal_type": proposal_type,
        "reason": reason,
        "raw": raw,
    }


def _adapter_report_payload(result: LLMCognitionAdapterResult) -> dict[str, object]:
    return {
        "llm_enabled": result.llm_enabled,
        "semantic_proposal": _jsonable(result.semantic_proposal),
        "plan_proposal": _jsonable(result.plan_proposal),
        "plan_proposals": _jsonable(result.plan_proposals),
        "goal_reframe_proposal": _jsonable(result.goal_reframe_proposal),
        "explanation_draft": _jsonable(result.explanation_draft),
        "validation_results": _jsonable(result.proposal_validation_results),
        "gate_result": _jsonable(result.plan_gate_decision),
        "gate_results": _jsonable(result.plan_gate_decisions),
        "final_suggestion": result.llm_final_suggestion,
        "rejected_proposals": _jsonable(result.rejected_llm_proposals),
    }


def _core_with_reframe_selected(core_result: AgentCycleResult) -> AgentCycleResult:
    selected = core_result.selected_intention
    if selected is None:
        return core_result
    reframe = Intention(
        id=f"intention:executive:reframe:{selected.goal_id or 'goal:none'}",
        goal="reframe_or_split_goal",
        reason="Synthetic report fixture: deterministic core requested goal reframe.",
        source_tension=selected.source_tension,
        priority=selected.priority,
        risk=selected.risk,
        cost=selected.cost,
        proposed_action="suggestion_card",
        affordance="repair",
        goal_id=selected.goal_id or "goal:001",
        goal_description=selected.goal_description,
    )
    return replace(core_result, selected_intention=reframe)


def _jsonable(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
