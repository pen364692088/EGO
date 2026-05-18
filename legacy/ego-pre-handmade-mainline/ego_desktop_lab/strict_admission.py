from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from ego_desktop_lab.gate import evaluate_gate
from ego_desktop_lab.semantic_intelligence import (
    DEFAULT_SEMANTIC_TIMESTAMP,
    SEMANTIC_SCENARIO_DIR,
    run_semantic_scenario,
    run_semantic_text_event,
)
from ego_desktop_lab.semantic_proposal import (
    BINDING_BOUND,
    SEMANTIC_FAILURE_TYPES,
    SemanticProposal,
    validate_semantic_proposal_payload,
)
from ego_desktop_lab.semantic_policy import run_semantic_policy_calibration_cycle


CLAIM_CEILING = "lab-only strict validator admission experiment; not default runtime admission"
STRICT_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_LIVE_SHADOW_REPORT = Path("docs/LIVE_LLM_SHADOW_ACCURACY_V5C_REPORT.md")
SAFETY_FAILURE_TYPES = frozenset(
    {
        "destructive_action_request",
        "external_send_request",
        "permission_failure",
        "claim_boundary_query",
    }
)


@dataclass(frozen=True)
class StrictAdmissionRecord:
    case_id: str
    source: str
    input_text: str
    status: str
    admitted: bool
    safety_preempted: bool
    rejection_reasons: tuple[str, ...]
    mock_failure_type: str | None
    live_failure_type: str | None
    live_confidence: float | None
    live_binding_status: str | None
    live_related_goal_id: str | None
    expected_source_event_id: str
    live_source_event_id: str | None
    replay_overlay_applied: bool = False
    replay_selected_intention: str | None = None
    mock_selected_intention: str | None = None
    canonical_decision_delta_vs_mock: bool = False
    semantic_policy_changed_vs_mock: bool = False
    replay_gate_status: str | None = None
    replay_gate_reason: str | None = None
    live_admitted_did_not_bypass_gate: bool = True
    no_action_executed: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StrictAdmissionExperimentResult:
    claim_ceiling: str
    total_live_proposals: int
    admitted_count: int
    rejected_count: int
    safety_preempted_count: int
    rejection_reasons: dict[str, int]
    admission_changed_semantic_policy_count: int
    canonical_decision_delta_vs_mock: dict[str, object]
    live_admitted_did_not_bypass_gate: bool
    expected_reject_cases: tuple[dict[str, object], ...]
    records: tuple[StrictAdmissionRecord, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["records"] = [record.to_dict() for record in self.records]
        return data


def evaluate_strict_admission(observation: Mapping[str, Any]) -> StrictAdmissionRecord:
    parsed = _parsed_payload(observation)
    case_id = str(observation.get("case_id", "unknown"))
    source = str(observation.get("source", "unknown"))
    expected_source = _expected_source_event_id(case_id, parsed)
    safety_preempted = _safety_preempted(observation, parsed)
    reasons: list[str] = []

    validator_result = observation.get("validator_result")
    validator_accepted = isinstance(validator_result, Mapping) and validator_result.get("accepted") is True
    if parsed is None:
        reasons.append("live_shadow_output_unavailable")
    elif not validator_accepted:
        reason = str(validator_result.get("reason", "validator rejected proposal")) if isinstance(
            validator_result,
            Mapping,
        ) else "validator rejected proposal"
        reasons.append(f"validator_rejected:{reason}")

    if safety_preempted:
        reasons.append("safety_pre_router_preempted_live_admission")

    live_failure_type = _optional_str(parsed.get("candidate_failure_type")) if parsed else None
    if parsed is not None and live_failure_type not in SEMANTIC_FAILURE_TYPES:
        reasons.append("unknown_candidate_failure_type")

    live_source_event_id = _optional_str(parsed.get("source_event_id")) if parsed else None
    if parsed is not None and live_source_event_id != expected_source:
        reasons.append("source_event_id_mismatch")

    if bool(observation.get("hallucinated_evidence_detected")):
        reasons.append("hallucinated_evidence")

    confidence = _optional_float(parsed.get("confidence")) if parsed else None
    if confidence is None or confidence < STRICT_CONFIDENCE_THRESHOLD:
        reasons.append("confidence_below_threshold")

    rationale = _optional_str(parsed.get("rationale")) if parsed else None
    if not rationale:
        reasons.append("rationale_empty")

    binding_status = _optional_str(parsed.get("binding_status")) if parsed else None
    related_goal_id = _optional_str(parsed.get("related_goal_id")) if parsed else None
    if not safety_preempted and (binding_status != BINDING_BOUND or not related_goal_id):
        reasons.append("missing_goal_binding")
    elif safety_preempted and (binding_status != BINDING_BOUND or not related_goal_id):
        reasons.append("missing_goal_binding")

    admitted = not reasons
    status = "admitted" if admitted else ("safety_preempted" if safety_preempted else "rejected")
    return StrictAdmissionRecord(
        case_id=case_id,
        source=source,
        input_text=str(observation.get("input_text", "")),
        status=status,
        admitted=admitted,
        safety_preempted=safety_preempted,
        rejection_reasons=tuple(dict.fromkeys(reasons)),
        mock_failure_type=_mock_failure_type(observation),
        live_failure_type=live_failure_type,
        live_confidence=confidence,
        live_binding_status=binding_status,
        live_related_goal_id=related_goal_id,
        expected_source_event_id=expected_source,
        live_source_event_id=live_source_event_id,
    )


def run_strict_admission_experiment(
    live_shadow_report_path: Path = DEFAULT_LIVE_SHADOW_REPORT,
    *,
    live_shadow_payload: Mapping[str, Any] | None = None,
) -> StrictAdmissionExperimentResult:
    payload = dict(live_shadow_payload) if live_shadow_payload is not None else load_live_shadow_report_payload(
        live_shadow_report_path,
    )
    observations = tuple(_observations(payload))
    records = tuple(_replay_if_admitted(evaluate_strict_admission(item), item) for item in observations)
    reason_counts: dict[str, int] = {}
    for record in records:
        for reason in record.rejection_reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    delta_rows = tuple(record.case_id for record in records if record.canonical_decision_delta_vs_mock)
    expected_reject_cases = tuple(
        _expected_reject_case(record)
        for record in records
        if record.case_id == "operator_round1:claim_boundary_query"
    )
    return StrictAdmissionExperimentResult(
        claim_ceiling=CLAIM_CEILING,
        total_live_proposals=len(observations),
        admitted_count=sum(1 for record in records if record.admitted),
        rejected_count=sum(1 for record in records if not record.admitted),
        safety_preempted_count=sum(1 for record in records if record.safety_preempted),
        rejection_reasons=reason_counts,
        admission_changed_semantic_policy_count=sum(
            1 for record in records if record.semantic_policy_changed_vs_mock
        ),
        canonical_decision_delta_vs_mock={
            "count": len(delta_rows),
            "case_ids": list(delta_rows),
        },
        live_admitted_did_not_bypass_gate=all(
            record.live_admitted_did_not_bypass_gate for record in records if record.admitted
        ),
        expected_reject_cases=expected_reject_cases,
        records=records,
    )


def build_strict_validator_admission_report(
    output_path: Path,
    *,
    live_shadow_report_path: Path = DEFAULT_LIVE_SHADOW_REPORT,
    live_shadow_payload: Mapping[str, Any] | None = None,
) -> Path:
    result = run_strict_admission_experiment(
        live_shadow_report_path,
        live_shadow_payload=live_shadow_payload,
    )
    lines = [
        "# Strict Validator Admission v5d Report",
        "",
        f"Claim ceiling: {CLAIM_CEILING}.",
        "This report is an offline replay experiment. Live LLM proposals are not enabled as the default runtime admitted provider and do not bypass gate evaluation.",
        "",
        "## Admission Payload",
        "",
        "```json",
        json.dumps(result.to_dict(), indent=2, sort_keys=True, ensure_ascii=False),
        "```",
        "",
        "## Final Statement",
        "",
        "RuleSafetyPreRouter remains the highest-priority path. Safety-preempted rows are expected rejects and are not admitted into live semantic policy authority.",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def load_live_shadow_report_payload(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*)\n```", text, re.S)
    if not match:
        raise ValueError("live shadow report does not contain a JSON fenced payload")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("live shadow report payload must be a JSON object")
    return payload


def _replay_if_admitted(
    record: StrictAdmissionRecord,
    observation: Mapping[str, Any],
) -> StrictAdmissionRecord:
    if not record.admitted:
        return record
    parsed = _parsed_payload(observation)
    if parsed is None:
        return record
    baseline = _baseline_result_for_observation(observation)
    allowed_refs = tuple(baseline.evidence_record.semantic_allowed_evidence_refs or ())
    proposal, validation = validate_semantic_proposal_payload(parsed, allowed_evidence_refs=allowed_refs)
    if proposal is None:
        return replace(
            record,
            admitted=False,
            status="rejected",
            rejection_reasons=(*record.rejection_reasons, f"validator_rejected_on_replay:{validation.reason}"),
        )
    replay = run_semantic_policy_calibration_cycle(
        baseline.core_result,
        baseline.next_core_result,
        proposal,
    )
    selected = replay.canonical_decision.after_selected_intention
    gate_decision = replay.gate_decision
    expected_gate = evaluate_gate(selected.proposed_action) if selected else gate_decision
    mock_selected = baseline.semantic_policy_calibration.canonical_decision.after_selected_intention
    mock_overlay = baseline.semantic_policy_calibration.overlay
    semantic_policy_changed = (
        replay.overlay.accepted_failure_type != mock_overlay.accepted_failure_type
        or replay.overlay.target_affordance != mock_overlay.target_affordance
        or _goal(selected) != _goal(mock_selected)
    )
    return replace(
        record,
        replay_overlay_applied=replay.overlay.applied,
        replay_selected_intention=_goal(selected),
        mock_selected_intention=_goal(mock_selected),
        canonical_decision_delta_vs_mock=_goal(selected) != _goal(mock_selected),
        semantic_policy_changed_vs_mock=semantic_policy_changed,
        replay_gate_status=gate_decision.status,
        replay_gate_reason=gate_decision.reason,
        live_admitted_did_not_bypass_gate=gate_decision == expected_gate,
        no_action_executed=True,
    )


def _baseline_result_for_observation(observation: Mapping[str, Any]):
    case_id = str(observation.get("case_id", ""))
    timestamp = f"{DEFAULT_SEMANTIC_TIMESTAMP}:strict_admission"
    if case_id.startswith("operator_round1:"):
        scenario_id = case_id.split(":", 1)[1]
        scenario_path = SEMANTIC_SCENARIO_DIR / "operator_round1" / f"{scenario_id}.txt"
        if scenario_path.exists():
            return run_semantic_scenario(
                scenario_path,
                provider_mode="mock",
                evidence_log_path=Path("temp/ego_desktop_lab/strict_admission_v5d/replay.jsonl"),
                timestamp=timestamp,
                append_evidence=False,
            )
    return run_semantic_text_event(
        str(observation.get("input_text", "")),
        provider_mode="mock",
        evidence_log_path=Path("temp/ego_desktop_lab/strict_admission_v5d/replay.jsonl"),
        timestamp=timestamp,
        append_evidence=False,
    )


def _observations(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = payload.get("observations", ())
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _expected_reject_case(record: StrictAdmissionRecord) -> dict[str, object]:
    return {
        "case_id": record.case_id,
        "input_text": record.input_text,
        "status": record.status,
        "rejection_reasons": list(record.rejection_reasons),
        "expected_reason": "safety_preempted + missing_goal_binding",
    }


def _parsed_payload(observation: Mapping[str, Any]) -> dict[str, Any] | None:
    parsed = observation.get("parsed_live_proposal")
    return dict(parsed) if isinstance(parsed, Mapping) else None


def _expected_source_event_id(case_id: str, parsed: Mapping[str, Any] | None) -> str:
    if ":" in case_id:
        return f"scenario:{case_id.split(':', 1)[1]}"
    if parsed is not None and isinstance(parsed.get("source_event_id"), str):
        return str(parsed["source_event_id"])
    return "scenario:unknown"


def _safety_preempted(observation: Mapping[str, Any], parsed: Mapping[str, Any] | None) -> bool:
    if bool(observation.get("safety_pre_router_preempted_live")):
        return True
    if bool(observation.get("safety_preempted_binding_not_required")):
        return True
    admitted = observation.get("admitted_provider_result")
    if isinstance(admitted, Mapping) and admitted.get("admitted_provider") == "rule_safety_pre_router":
        return True
    candidate = parsed.get("candidate_failure_type") if parsed else None
    return str(candidate) in SAFETY_FAILURE_TYPES and bool(observation.get("source") == "safety_text")


def _mock_failure_type(observation: Mapping[str, Any]) -> str | None:
    admitted = observation.get("admitted_provider_result")
    if not isinstance(admitted, Mapping):
        return None
    value = admitted.get("accepted_failure_type")
    return str(value) if value is not None else None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _goal(intention: object | None) -> str | None:
    goal = getattr(intention, "goal", None)
    return str(goal) if goal is not None else None
