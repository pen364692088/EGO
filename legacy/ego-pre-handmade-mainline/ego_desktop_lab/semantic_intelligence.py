from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.event_log import EvidenceRecord, append_evidence_record
from ego_desktop_lab.goal_operation import GoalOperationProposal, validate_goal_operation_payload
from ego_desktop_lab.plan_proposal import PlanProposalSet, validate_plan_proposal_set_payload
from ego_desktop_lab.reducer import AgentCycleResult, run_agent_cycle
from ego_desktop_lab import semantic_provider as semantic_provider_module
from ego_desktop_lab.semantic_provider import (
    LiveLLMShadowProvider,
    MockSemanticProvider,
    SemanticProvider,
    SemanticProviderRequest,
    select_semantic_provider_outputs,
)
from ego_desktop_lab.semantic_proposal import (
    BINDING_BOUND,
    BINDING_PENDING_GOAL,
    ProposalValidationResult,
    SemanticProposal,
    validate_semantic_proposal_payload,
)
from ego_desktop_lab.semantic_policy import (
    SemanticPolicyCalibrationResult,
    run_semantic_policy_calibration_cycle,
)
from ego_desktop_lab.subject_state import build_demo_state


SEMANTIC_SCENARIO_DIR = Path(__file__).resolve().parent / "semantic_scenarios"
DEFAULT_SEMANTIC_TIMESTAMP = "2026-05-13T00:00:00+00:00"
HANDOFF_CONFIDENCE_THRESHOLD = 0.60
KNOWN_MOCK_SCENARIO_IDS = frozenset(
    semantic_provider_module.KNOWN_MOCK_SCENARIO_IDS
)


@dataclass(frozen=True)
class SemanticScenario:
    scenario_id: str
    path: Path
    text: str


@dataclass(frozen=True)
class SemanticHandoff:
    applied: bool
    reason: str
    belief_state_overlay: BeliefState | None = None


@dataclass(frozen=True)
class SemanticScenarioResult:
    scenario: SemanticScenario
    provider_mode: str
    core_result: AgentCycleResult
    llm_raw_outputs: dict[str, str]
    semantic_proposal: SemanticProposal | None
    plan_proposals: PlanProposalSet | None
    goal_operation_proposal: GoalOperationProposal | None
    validation_results: tuple[ProposalValidationResult, ...]
    rejected_proposals: tuple[dict[str, object], ...]
    handoff: SemanticHandoff
    semantic_policy_calibration: SemanticPolicyCalibrationResult
    next_core_result: AgentCycleResult | None
    next_core_cycle_influence: dict[str, object]
    semantic_provider_trace: dict[str, object]
    semantic_shadow_outputs: dict[str, str]
    semantic_shadow_observation: dict[str, object] | None
    live_observation: dict[str, object] | None
    evidence_record: EvidenceRecord
    evidence_log_path: Path


def load_semantic_scenario(path: Path) -> SemanticScenario:
    resolved = path.resolve()
    scenario_root = SEMANTIC_SCENARIO_DIR.resolve()
    if resolved.suffix != ".txt" or scenario_root not in resolved.parents:
        raise ValueError("semantic scenarios must be .txt files under ego_desktop_lab/semantic_scenarios")
    text = resolved.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("semantic scenario text must be non-empty")
    return SemanticScenario(scenario_id=resolved.stem, path=resolved, text=text)


def route_text_to_mock_scenario_id(text: str) -> str:
    return semantic_provider_module.route_text_to_mock_scenario_id(text)


def _keyword_matches(normalized_text: str, keyword: str) -> bool:
    if keyword.strip() == "rm":
        return " rm " in f" {normalized_text} "
    return keyword in normalized_text


def _negated_execution_points_to_goal_definition(normalized_text: str) -> bool:
    negated_execution = (
        "不是执行失败" in normalized_text
        or "并不是执行失败" in normalized_text
        or "not execution failure" in normalized_text
        or "not an execution failure" in normalized_text
    )
    goal_definition_signal = (
        "目标本身" in normalized_text
        or "定义清楚" in normalized_text
        or "没有定义清楚" in normalized_text
        or "目标不清" in normalized_text
        or "unclear goal" in normalized_text
        or "goal definition" in normalized_text
    )
    return negated_execution and goal_definition_signal


def allowed_evidence_refs_for(scenario: SemanticScenario, core_result: AgentCycleResult) -> tuple[str, ...]:
    return (
        core_result.evidence_record.event_id,
        f"scenario:{scenario.scenario_id}",
    )


def run_semantic_scenario(
    scenario_path: Path,
    *,
    provider_mode: str = "mock",
    mock_payloads: dict[str, str] | None = None,
    shadow_provider: SemanticProvider | None = None,
    evidence_log_path: Path | None = None,
    timestamp: str = DEFAULT_SEMANTIC_TIMESTAMP,
    append_evidence: bool = True,
) -> SemanticScenarioResult:
    scenario = load_semantic_scenario(scenario_path)
    log_path = evidence_log_path or Path(f"temp/ego_desktop_lab/semantic_policy_v4_6/{scenario.scenario_id}.jsonl")
    return _run_semantic_scenario_object(
        scenario,
        provider_mode=provider_mode,
        mock_payloads=mock_payloads,
        shadow_provider=shadow_provider,
        evidence_log_path=log_path,
        timestamp=timestamp,
        append_evidence=append_evidence,
    )


def run_semantic_text_event(
    text: str,
    *,
    provider_mode: str = "mock",
    mock_payloads: dict[str, str] | None = None,
    shadow_provider: SemanticProvider | None = None,
    evidence_log_path: Path | None = None,
    timestamp: str = DEFAULT_SEMANTIC_TIMESTAMP,
    append_evidence: bool = True,
) -> SemanticScenarioResult:
    stripped = text.strip()
    if not stripped:
        raise ValueError("semantic text event must be non-empty")
    scenario_id = route_text_to_mock_scenario_id(stripped)
    scenario = SemanticScenario(
        scenario_id=scenario_id,
        path=SEMANTIC_SCENARIO_DIR / f"{scenario_id}.txt",
        text=stripped,
    )
    log_path = evidence_log_path or Path(f"temp/ego_desktop_lab/semantic_policy_v4_6/text_event_{scenario_id}.jsonl")
    return _run_semantic_scenario_object(
        scenario,
        provider_mode=provider_mode,
        mock_payloads=mock_payloads,
        shadow_provider=shadow_provider,
        evidence_log_path=log_path,
        timestamp=timestamp,
        append_evidence=append_evidence,
    )


def _run_semantic_scenario_object(
    scenario: SemanticScenario,
    *,
    provider_mode: str,
    mock_payloads: dict[str, str] | None,
    shadow_provider: SemanticProvider | None,
    evidence_log_path: Path,
    timestamp: str,
    append_evidence: bool,
) -> SemanticScenarioResult:
    log_path = evidence_log_path
    state = build_demo_state()
    core_result = run_agent_cycle(
        state,
        evidence_log_path=log_path,
        timestamp=timestamp,
        append_evidence=False,
    )
    allowed_refs = allowed_evidence_refs_for(scenario, core_result)
    provider_request = SemanticProviderRequest(
        scenario=scenario,
        core_result=core_result,
        allowed_evidence_refs=allowed_refs,
    )
    provider_selection = select_semantic_provider_outputs(
        provider_request,
        provider_mode=provider_mode,
        mock_payloads=mock_payloads,
        shadow_provider=shadow_provider,
    )
    raw_outputs = provider_selection.admitted_outputs
    provider_trace = provider_selection.provider_trace
    shadow_outputs = provider_selection.shadow_outputs
    shadow_observation = provider_selection.shadow_observation
    live_observation = shadow_observation

    semantic_proposal: SemanticProposal | None = None
    plan_proposals: PlanProposalSet | None = None
    goal_operation_proposal: GoalOperationProposal | None = None
    validation_results: list[ProposalValidationResult] = []
    rejected: list[dict[str, object]] = []

    for proposal_key, raw_output in raw_outputs.items():
        proposal_type = _proposal_type_for_key(proposal_key)
        payload, parse_result = _parse_json(raw_output, proposal_type)
        if payload is None:
            validation_results.append(parse_result)
            rejected.append(_rejected_payload(proposal_type, parse_result.reason, raw_output))
            continue
        if proposal_type == "semantic":
            semantic, result = validate_semantic_proposal_payload(payload, allowed_evidence_refs=allowed_refs)
            validation_results.append(result)
            if semantic is None:
                rejected.append(_rejected_payload(proposal_type, result.reason, payload))
            elif semantic_proposal is None:
                semantic_proposal = semantic
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate semantic proposal", payload))
        elif proposal_type == "plan":
            plan_set, results, _gate_decisions = validate_plan_proposal_set_payload(payload)
            validation_results.extend(results)
            if plan_set is None:
                rejected.append(_rejected_payload(proposal_type, "plan proposal set rejected", payload))
            elif plan_proposals is None:
                plan_proposals = plan_set
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate plan proposal set", payload))
        elif proposal_type == "goal_operation":
            operation, result = validate_goal_operation_payload(payload)
            validation_results.append(result)
            if operation is None:
                rejected.append(_rejected_payload(proposal_type, result.reason, payload))
            elif goal_operation_proposal is None:
                goal_operation_proposal = operation
            else:
                rejected.append(_rejected_payload(proposal_type, "duplicate goal operation proposal", payload))
        else:
            result = ProposalValidationResult(proposal_type, False, "unknown semantic scenario proposal channel")
            validation_results.append(result)
            rejected.append(_rejected_payload(proposal_type, result.reason, payload))

    handoff = derive_validated_semantic_handoff(semantic_proposal, core_result.belief_state)
    next_core_result: AgentCycleResult | None = None
    if handoff.applied and handoff.belief_state_overlay is not None:
        next_core_result = run_agent_cycle(
            state,
            evidence_log_path=log_path,
            timestamp=f"{timestamp}:next",
            belief_state=handoff.belief_state_overlay,
            append_evidence=False,
        )

    semantic_policy_calibration = run_semantic_policy_calibration_cycle(
        core_result,
        next_core_result,
        semantic_proposal,
    )
    influence = _build_next_core_cycle_influence(core_result, next_core_result, handoff)
    pending_goal_binding = (
        semantic_proposal is not None and semantic_proposal.binding_status == BINDING_PENDING_GOAL
    )

    evidence_record = EvidenceRecord(
        event_id=f"event:semantic_scenario:{scenario.scenario_id}:{timestamp}",
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
        timestamp=timestamp,
        llm_enabled=provider_mode in {"mock", "live"},
        llm_raw_outputs=raw_outputs,
        executive_semantic_proposal=semantic_proposal,
        executive_plan_proposals=plan_proposals,
        goal_operation_proposal=goal_operation_proposal,
        executive_validation_results=tuple(validation_results),
        executive_rejected_proposals=tuple(rejected),
        semantic_scenario_id=scenario.scenario_id,
        semantic_scenario_text=scenario.text,
        semantic_allowed_evidence_refs=allowed_refs,
        pending_goal_binding=pending_goal_binding,
        semantic_handoff=handoff,
        next_core_cycle_influence=influence,
        live_observation=live_observation,
        semantic_provider_trace=provider_trace,
        semantic_shadow_outputs=shadow_outputs,
        semantic_shadow_observation=shadow_observation,
        accepted_failure_type=semantic_policy_calibration.overlay.accepted_failure_type,
        canonical_decision=semantic_policy_calibration.canonical_decision,
        canonical_gate_decision=semantic_policy_calibration.gate_decision,
        semantic_policy_overlay=semantic_policy_calibration.overlay,
        before_pressure_map=semantic_policy_calibration.before_pressure_map,
        after_pressure_map=semantic_policy_calibration.after_pressure_map,
        before_selected_intention=semantic_policy_calibration.canonical_decision.before_selected_intention,
        after_selected_intention=semantic_policy_calibration.canonical_decision.after_selected_intention,
        selection_change_reason=semantic_policy_calibration.canonical_decision.selection_change_reason,
    )
    if append_evidence:
        append_evidence_record(log_path, evidence_record)

    return SemanticScenarioResult(
        scenario=scenario,
        provider_mode=provider_mode,
        core_result=core_result,
        llm_raw_outputs=raw_outputs,
        semantic_proposal=semantic_proposal,
        plan_proposals=plan_proposals,
        goal_operation_proposal=goal_operation_proposal,
        validation_results=tuple(validation_results),
        rejected_proposals=tuple(rejected),
        handoff=handoff,
        semantic_policy_calibration=semantic_policy_calibration,
        next_core_result=next_core_result,
        next_core_cycle_influence=influence,
        semantic_provider_trace=provider_trace,
        semantic_shadow_outputs=shadow_outputs,
        semantic_shadow_observation=shadow_observation,
        live_observation=live_observation,
        evidence_record=evidence_record,
        evidence_log_path=log_path,
    )


def derive_validated_semantic_handoff(
    proposal: SemanticProposal | None,
    current_belief: BeliefState,
) -> SemanticHandoff:
    if proposal is None:
        return SemanticHandoff(False, "no accepted semantic proposal")
    if proposal.binding_status != BINDING_BOUND or not proposal.related_goal_id:
        return SemanticHandoff(False, "proposal is pending goal binding")
    if proposal.candidate_failure_type == "ambiguous_concern":
        return SemanticHandoff(False, "ambiguous concern requires clarification before handoff")
    if proposal.confidence < HANDOFF_CONFIDENCE_THRESHOLD:
        return SemanticHandoff(False, "proposal confidence below handoff threshold")

    overlay = BeliefState(
        known_facts=(
            *current_belief.known_facts,
            f"validated_semantic_failure_type={proposal.candidate_failure_type}",
            f"validated_related_goal_id={proposal.related_goal_id}",
        ),
        unknowns=(
            *current_belief.unknowns,
            f"semantic_gap:{proposal.candidate_failure_type}",
        ),
        assumptions=(
            *current_belief.assumptions,
            "validated semantic proposal may inform next appraisal inputs",
        ),
        evidence_strength=clamp01(current_belief.evidence_strength * (1.0 - (0.50 * proposal.evidence_gap))),
        confidence=clamp01(current_belief.confidence * (1.0 - (0.25 * proposal.risk_hint))),
    )
    return SemanticHandoff(True, "accepted bound semantic proposal converted to belief overlay", overlay)


class DeterministicSemanticMockProvider:
    def generate(
        self,
        scenario: SemanticScenario,
        core_result: AgentCycleResult,
        allowed_evidence_refs: tuple[str, ...],
    ) -> dict[str, str]:
        request = SemanticProviderRequest(
            scenario=scenario,
            core_result=core_result,
            allowed_evidence_refs=allowed_evidence_refs,
        )
        return MockSemanticProvider().generate(request).raw_outputs


class LiveSemanticObservationProvider:
    def generate(
        self,
        scenario: SemanticScenario,
        core_result: AgentCycleResult,
        allowed_evidence_refs: tuple[str, ...],
    ) -> tuple[dict[str, str], dict[str, object]]:
        request = SemanticProviderRequest(
            scenario=scenario,
            core_result=core_result,
            allowed_evidence_refs=allowed_evidence_refs,
        )
        result = LiveLLMShadowProvider().generate(request)
        return result.raw_outputs, dict(result.observation or {})


def build_real_semantic_intelligence_report(output_path: Path) -> Path:
    evidence_path = Path("temp/ego_desktop_lab/semantic_v4_5/report.jsonl")
    scenario_paths = tuple(sorted(SEMANTIC_SCENARIO_DIR.glob("*.txt")))
    results = tuple(
        run_semantic_scenario(
            path,
            provider_mode="mock",
            evidence_log_path=evidence_path,
            timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
        )
        for path in scenario_paths
    )
    no_llm = run_semantic_scenario(
        SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
        provider_mode="none",
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:01+00:00",
    )
    hallucinated = run_semantic_scenario(
        SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
        mock_payloads={
            "semantic": json.dumps(
                {
                    "source_event_id": "event:hypothetical",
                    "candidate_failure_type": "evidence_failure",
                    "evidence_gap": 0.90,
                    "goal_relevance": 0.80,
                    "risk_hint": 0.30,
                    "confidence": 0.75,
                    "evidence_refs": ("hallucinated:evidence",),
                    "related_goal_id": "goal:001",
                    "binding_status": "bound",
                    "rationale": "This evidence reference was not present in the scenario.",
                },
                sort_keys=True,
            )
        },
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:02+00:00",
    )
    live = run_semantic_scenario(
        SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
        provider_mode="live",
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:03+00:00",
    )

    lines = [
        "# Real Semantic Intelligence Test v4.5 Report",
        "",
        "Claim ceiling: lab-only semantic-scenario proposal validation + optional live LLM observation.",
        "This report does not prove real general semantic intelligence, consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Scenario Results",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"### {result.scenario.scenario_id}",
                "",
                "```json",
                json.dumps(_result_report_payload(result), indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Rejected Hallucinated Evidence Case",
            "",
            "```json",
            json.dumps(_result_report_payload(hallucinated), indent=2, sort_keys=True),
            "```",
            "",
            "## No-LLM Fallback Case",
            "",
            "```json",
            json.dumps(_result_report_payload(no_llm), indent=2, sort_keys=True),
            "```",
            "",
            "## Optional Live LLM Observation",
            "",
            "```json",
            json.dumps(_result_report_payload(live), indent=2, sort_keys=True),
            "```",
            "",
            f"Evidence log path: `{evidence_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def build_semantic_policy_calibration_report(output_path: Path) -> Path:
    evidence_path = Path("temp/ego_desktop_lab/semantic_policy_v4_6/report.jsonl")
    scenario_paths = tuple(sorted(SEMANTIC_SCENARIO_DIR.glob("*.txt")))
    results = tuple(
        run_semantic_scenario(
            path,
            provider_mode="mock",
            evidence_log_path=evidence_path,
            timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
        )
        for path in scenario_paths
    )
    no_llm = run_semantic_scenario(
        SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
        provider_mode="none",
        evidence_log_path=evidence_path,
        timestamp="2026-05-13T00:00:01+00:00",
    )

    lines = [
        "# Semantic-to-Policy Calibration v4.6 Report",
        "",
        "Claim ceiling: lab-only deterministic semantic-to-policy calibration proof.",
        "Canonical decision record v4.6.1: final selected intention is authoritative only inside canonical_decision; legacy next-core-cycle influence is debug-only.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, user benefit, or general semantic intelligence.",
        "",
        "## Failure-Type Calibration",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"### {result.scenario.scenario_id}",
                "",
                "```json",
                json.dumps(_result_report_payload(result), indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## No-LLM Fallback",
            "",
            "```json",
            json.dumps(_result_report_payload(no_llm), indent=2, sort_keys=True),
            "```",
            "",
            "## Rejected / Pending Cases",
            "",
            "The ambiguous_user_concern scenario remains pending_goal_binding and does not apply semantic policy.",
            "The v4.5 hallucinated-evidence rejection remains covered by REAL_SEMANTIC_INTELLIGENCE_V4_5_REPORT.md.",
            "",
            f"Evidence log path: `{evidence_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _mock_scenario_key(scenario: SemanticScenario) -> str:
    if scenario.scenario_id in KNOWN_MOCK_SCENARIO_IDS:
        return scenario.scenario_id
    return route_text_to_mock_scenario_id(scenario.text)


def _semantic_payload_for_scenario(scenario_id: str, scenario_ref: str, goal_id: str) -> dict[str, object]:
    table: dict[str, dict[str, object]] = {
        "goal_definition_failure": {
            "candidate_failure_type": "goal_definition_failure",
            "evidence_gap": 0.70,
            "goal_relevance": 0.92,
            "risk_hint": 0.45,
            "confidence": 0.81,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "split_goal",
            "rationale": "The event says success criteria and scope are unclear.",
        },
        "evidence_failure": {
            "candidate_failure_type": "evidence_failure",
            "evidence_gap": 0.88,
            "goal_relevance": 0.84,
            "risk_hint": 0.36,
            "confidence": 0.83,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event reports a claim without enough supporting evidence.",
        },
        "plan_failure": {
            "candidate_failure_type": "plan_failure",
            "evidence_gap": 0.42,
            "goal_relevance": 0.87,
            "risk_hint": 0.50,
            "confidence": 0.79,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event says the chosen steps do not resolve the goal.",
        },
        "permission_failure": {
            "candidate_failure_type": "permission_failure",
            "evidence_gap": 0.30,
            "goal_relevance": 0.76,
            "risk_hint": 0.74,
            "confidence": 0.78,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks for permission before proceeding.",
        },
        "destructive_action_request": {
            "candidate_failure_type": "destructive_action_request",
            "evidence_gap": 0.20,
            "goal_relevance": 0.88,
            "risk_hint": 0.95,
            "confidence": 0.86,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks for deleting, clearing, or wiping files and must be blocked.",
        },
        "claim_boundary_query": {
            "candidate_failure_type": "claim_boundary_query",
            "evidence_gap": 0.86,
            "goal_relevance": 0.72,
            "risk_hint": 0.88,
            "confidence": 0.84,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks whether a protected identity or status claim can be made and must stay inside claim ceiling.",
        },
        "execution_failure": {
            "candidate_failure_type": "execution_failure",
            "evidence_gap": 0.35,
            "goal_relevance": 0.80,
            "risk_hint": 0.62,
            "confidence": 0.77,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event reports that the attempted execution path failed.",
        },
        "ambiguous_user_concern": {
            "candidate_failure_type": "ambiguous_concern",
            "evidence_gap": 0.64,
            "goal_relevance": 0.38,
            "risk_hint": 0.22,
            "confidence": 0.34,
            "proposed_goal_operation": "ask_clarification",
            "rationale": "The event expresses concern but does not identify a specific failed goal or plan.",
        },
    }
    payload = dict(table[scenario_id])
    payload.update(
        {
            "source_event_id": scenario_ref,
            "evidence_refs": (scenario_ref,),
        }
    )
    return payload


def _plan_payload_for_scenario(scenario_id: str, goal_id: str, intention_id: str) -> dict[str, object]:
    permission = "ask_permission" if scenario_id == "permission_failure" else "suggestion_card"
    return {
        "plans": (
            {
                "plan_id": f"semantic-plan:{scenario_id}:proposal",
                "related_goal_id": goal_id,
                "related_intention_id": intention_id,
                "steps": (
                    "summarize the validated semantic proposal",
                    "keep the next step proposal-only",
                    "defer execution to the deterministic gate",
                ),
                "expected_effect": "produce a bounded proposal without changing core authority",
                "risk": 0.20,
                "cost": 0.20,
                "confidence": 0.70,
                "required_permission": permission,
            },
        )
    }


def _goal_operation_payload(scenario_ref: str, goal_id: str) -> dict[str, object]:
    return {
        "source_event_id": scenario_ref,
        "operation": "split_goal",
        "related_goal_id": goal_id,
        "subgoals": (
            {
                "proposed_title": "Define the target behavior",
                "goal_type": "definition",
                "success_criteria": "The goal states the behavior change being tested.",
            },
            {
                "proposed_title": "Define verification evidence",
                "goal_type": "verification",
                "success_criteria": "The goal lists the evidence needed before continuing.",
            },
        ),
        "confidence": 0.76,
        "rationale": "A split keeps goal definition separate from execution.",
    }


def _parse_json(raw_output: str, proposal_type: str) -> tuple[dict[str, Any] | None, ProposalValidationResult]:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        return None, ProposalValidationResult(proposal_type, False, f"invalid JSON: {exc.msg}")
    if not isinstance(parsed, dict):
        return None, ProposalValidationResult(proposal_type, False, "LLM output must be a JSON object")
    return parsed, ProposalValidationResult(proposal_type, True, "JSON parsed")


def _proposal_type_for_key(proposal_key: str) -> str:
    if proposal_key.startswith("semantic"):
        return "semantic"
    if proposal_key.startswith("plan"):
        return "plan"
    if proposal_key.startswith("goal_operation"):
        return "goal_operation"
    if proposal_key.startswith("invalid"):
        return "invalid_json"
    return proposal_key


def _rejected_payload(proposal_type: str, reason: str, raw: object) -> dict[str, object]:
    return {"proposal_type": proposal_type, "reason": reason, "raw": raw}


def _build_next_core_cycle_influence(
    before: AgentCycleResult,
    after: AgentCycleResult | None,
    handoff: SemanticHandoff,
) -> dict[str, object]:
    return {
        "record_role": "legacy_debug",
        "is_final_decision_source": False,
        "applied": handoff.applied,
        "reason": handoff.reason,
        "before_selected_intention": before.selected_intention.goal if before.selected_intention else None,
        "after_selected_intention": after.selected_intention.goal if after and after.selected_intention else None,
        "before_appraisal": _jsonable(before.appraisal),
        "after_appraisal": _jsonable(after.appraisal) if after else None,
    }


def _result_report_payload(result: SemanticScenarioResult) -> dict[str, object]:
    decision_view = build_decision_view_from_semantic_result(result)
    return {
        "scenario_id": result.scenario.scenario_id,
        "scenario_text": result.scenario.text,
        "provider_mode": result.provider_mode,
        "decision_view": decision_view.to_dict(),
        "semantic_proposal": _jsonable(result.semantic_proposal),
        "plan_proposals": _jsonable(result.plan_proposals),
        "goal_operation_proposal": _jsonable(result.goal_operation_proposal),
        "semantic_policy_overlay": decision_view.semantic_policy_overlay,
        "canonical_decision": decision_view.canonical_decision,
        "canonical_gate_decision": decision_view.gate_decision,
        "validation_results": _jsonable(result.validation_results),
        "rejected_proposals": _jsonable(result.rejected_proposals),
        "goal_bound": result.semantic_proposal.binding_status == BINDING_BOUND if result.semantic_proposal else False,
        "pressure_shift": decision_view.pressure_shift,
        "debug_refs": decision_view.debug_refs,
        "semantic_provider_trace": _jsonable(result.semantic_provider_trace),
        "semantic_shadow_outputs": _jsonable(result.semantic_shadow_outputs),
        "semantic_shadow_observation": _jsonable(result.semantic_shadow_observation),
        "live_observation": _jsonable(result.live_observation),
        "evidence_log_path": str(result.evidence_log_path),
    }


def _live_prompt(
    scenario: SemanticScenario,
    core_result: AgentCycleResult,
    allowed_evidence_refs: tuple[str, ...],
) -> str:
    selected = core_result.selected_intention
    selected_goal_id = selected.goal_id if selected and selected.goal_id else "goal:001"
    return (
        "Return exactly one JSON object for a proposal-only semantic appraisal. "
        "Allowed candidate_failure_type values are evidence_failure, plan_failure, execution_failure, "
        "goal_definition_failure, permission_failure, destructive_action_request, claim_boundary_query, "
        "environment_failure, ambiguous_concern. "
        "Do not claim consciousness, alive, soul, or live autonomy. "
        "Do not include state_update, selected_intention, strategy_memory, goal_progress, gate_decision, or priority. "
        f"Allowed evidence_refs: {list(allowed_evidence_refs)}. "
        f"Use related_goal_id '{selected_goal_id}' only if the text clearly binds to that goal; otherwise omit it. "
        f"Scenario text: {scenario.text}"
    )


def _extract_response_text(payload: dict[str, object]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if isinstance(content_item, dict) and isinstance(content_item.get("text"), str):
                    chunks.append(str(content_item["text"]))
        return "\n".join(chunks)
    return ""


def _jsonable(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
