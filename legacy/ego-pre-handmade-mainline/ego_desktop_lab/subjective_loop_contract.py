from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping, Sequence


CLAIM_CEILING = "replay-validated subjective-agent proxy; not consciousness, alive, soul, live autonomy, or runtime efficacy"


@dataclass(frozen=True)
class SubjectEvent:
    event_id: str
    user_text: str
    source: str = "lab_shell"
    recent_dialogue: tuple[str, ...] = ()
    safety_pre_route: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AffectiveAppraisal:
    feedback_signal: str | None
    valence: float
    arousal: float
    repair_need: float
    trust_delta: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SubjectDecision:
    semantic_understanding: dict[str, Any]
    affective_appraisal: AffectiveAppraisal
    memory_delta: dict[str, Any]
    intention_proposal: dict[str, Any]
    gate_decision: dict[str, Any]
    response_plan: dict[str, Any]
    decision_class: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["affective_appraisal"] = self.affective_appraisal.to_dict()
        return data


@dataclass(frozen=True)
class SubjectEvidence:
    subject_event: SubjectEvent
    subject_decision: SubjectDecision
    before_state_summary: dict[str, Any]
    after_state_summary: dict[str, Any]
    why_selected: str
    why_blocked_or_asked: str | None
    feedback_outcome: dict[str, Any] | None
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_event": self.subject_event.to_dict(),
            "subject_decision": self.subject_decision.to_dict(),
            "before_state_summary": self.before_state_summary,
            "after_state_summary": self.after_state_summary,
            "why_selected": self.why_selected,
            "why_blocked_or_asked": self.why_blocked_or_asked,
            "feedback_outcome": self.feedback_outcome,
            "claim_ceiling": self.claim_ceiling,
        }


def build_subject_event(
    user_text: str,
    *,
    source: str = "lab_shell",
    recent_dialogue: Sequence[str] = (),
    safety_pre_route: str | None = None,
) -> SubjectEvent:
    normalized = " ".join(user_text.strip().split())
    event_id = "subject_event:" + hashlib.sha256(f"{source}:{normalized}".encode("utf-8")).hexdigest()[:16]
    return SubjectEvent(
        event_id=event_id,
        user_text=normalized,
        source=source,
        recent_dialogue=tuple(recent_dialogue[-4:]),
        safety_pre_route=safety_pre_route,
    )


def build_subject_evidence(
    view: Mapping[str, Any] | Any,
    subject_event: SubjectEvent,
    *,
    previous_feedback_signal: str | None = None,
) -> SubjectEvidence:
    data = _view_to_dict(view)
    decision = build_subject_decision_from_view(
        data,
        subject_event,
        previous_feedback_signal=previous_feedback_signal,
    )
    gate = decision.gate_decision
    gate_status = str(gate.get("status") or "unknown")
    return SubjectEvidence(
        subject_event=subject_event,
        subject_decision=decision,
        before_state_summary={
            "previous_feedback_signal": previous_feedback_signal,
            "recent_dialogue_count": len(subject_event.recent_dialogue),
        },
        after_state_summary={
            "feedback_signal": decision.affective_appraisal.feedback_signal,
            "repair_need": decision.affective_appraisal.repair_need,
            "trust_delta": decision.affective_appraisal.trust_delta,
        },
        why_selected=_selection_reason(data),
        why_blocked_or_asked=_gate_reason(gate_status, gate),
        feedback_outcome=feedback_outcome_from_text(subject_event.user_text),
    )


def build_subject_decision_from_view(
    view: Mapping[str, Any] | Any,
    subject_event: SubjectEvent,
    *,
    previous_feedback_signal: str | None = None,
) -> SubjectDecision:
    data = _view_to_dict(view)
    canonical = _mapping(data.get("canonical_decision"))
    selected = _mapping(canonical.get("after_selected_intention"))
    gate = _mapping(data.get("gate_decision"))
    feedback_signal = classify_feedback_signal(subject_event.user_text)
    appraisal = appraise_feedback_signal(feedback_signal, previous_feedback_signal=previous_feedback_signal)
    return SubjectDecision(
        semantic_understanding=_mapping(data.get("semantic_understanding")),
        affective_appraisal=appraisal,
        memory_delta=_memory_delta(appraisal),
        intention_proposal=selected,
        gate_decision=gate,
        response_plan={
            "rendered_suggestion": data.get("rendered_suggestion") or data.get("suggestion"),
            "suggestion_source": data.get("suggestion_source"),
            "no_action_executed": bool(data.get("no_action_executed", True)),
        },
        decision_class=decision_class_from_view(data),
    )


def classify_feedback_signal(text: str) -> str | None:
    lowered = " ".join(text.strip().lower().split())
    if not lowered:
        return None
    misunderstood = (
        "误解" in lowered
        or "理解错" in lowered
        or "没理解" in lowered
        or "not what i meant" in lowered
        or "misunderstood" in lowered
    )
    negative = (
        "这样不对" in lowered
        or "不对" == lowered
        or "没帮助" in lowered
        or "没有帮助" in lowered
        or "太机械" in lowered
        or "wrong" in lowered
        or "not helpful" in lowered
    )
    positive = (
        "有帮助" in lowered
        or "这有用" in lowered
        or "这样可以" in lowered
        or "helpful" in lowered
        or "works" in lowered
    )
    if misunderstood:
        return "misunderstood"
    if negative:
        return "negative"
    if positive:
        return "helpful"
    return None


def appraise_feedback_signal(
    feedback_signal: str | None,
    *,
    previous_feedback_signal: str | None = None,
) -> AffectiveAppraisal:
    if feedback_signal in {"misunderstood", "negative"}:
        return AffectiveAppraisal(
            feedback_signal=feedback_signal,
            valence=-0.45,
            arousal=0.55,
            repair_need=0.85,
            trust_delta=-0.25,
            rationale="user feedback indicates misalignment; next reply should acknowledge risk before proposing a path",
        )
    if feedback_signal == "helpful":
        return AffectiveAppraisal(
            feedback_signal=feedback_signal,
            valence=0.35,
            arousal=0.25,
            repair_need=0.15,
            trust_delta=0.18,
            rationale="user feedback indicates the previous response was useful; preserve current strategy cautiously",
        )
    if previous_feedback_signal in {"misunderstood", "negative"}:
        return AffectiveAppraisal(
            feedback_signal=None,
            valence=-0.1,
            arousal=0.35,
            repair_need=0.55,
            trust_delta=-0.05,
            rationale="previous turn had negative feedback; next response should reduce assumption and ask more concretely",
        )
    return AffectiveAppraisal(
        feedback_signal=None,
        valence=0.0,
        arousal=0.15,
        repair_need=0.2,
        trust_delta=0.0,
        rationale="no explicit affective feedback detected",
    )


def feedback_outcome_from_text(text: str) -> dict[str, Any] | None:
    signal = classify_feedback_signal(text)
    if signal is None:
        return None
    appraisal = appraise_feedback_signal(signal)
    return {
        "feedback_signal": signal,
        "repair_need_delta": appraisal.repair_need,
        "trust_delta": appraisal.trust_delta,
        "reason": appraisal.rationale,
    }


def decision_class_from_view(view: Mapping[str, Any] | Any) -> str:
    data = _view_to_dict(view)
    canonical = _mapping(data.get("canonical_decision"))
    selected = _mapping(canonical.get("after_selected_intention"))
    semantic = _mapping(data.get("semantic_understanding"))
    goal = str(selected.get("goal") or "unknown")
    failure_type = str(canonical.get("accepted_failure_type") or semantic.get("accepted_failure_type") or goal)
    gate = _mapping(data.get("gate_decision"))
    gate_status = str(gate.get("status") or "unknown")
    if goal == "answer_local_time":
        return "local_time"
    if goal == "answer_local_system_info":
        return "local_system_info"
    if goal == "answer_capability_question":
        return "capability_boundary"
    if goal == "respond_to_feedback":
        return "feedback_outcome"
    if gate_status == "block" or goal in {"block_destructive_action", "block_external_send"}:
        return "safety_block"
    if gate_status == "ask" or goal == "ask_permission_or_defer":
        return "permission_ask"
    if goal == "verify_before_claim":
        return "evidence_boundary"
    if goal == "repair_or_replan_goal":
        return "repair_or_replan"
    if goal == "retry_or_change_tool":
        return "retry_or_change_tool"
    if goal in {"split_goal_or_redefine_success_criteria", "reframe_or_split_goal"}:
        return "goal_reframe"
    if failure_type == "claim_boundary_query":
        return "claim_boundary"
    if failure_type == "ambiguous_concern" or goal in {"ask_clarification", "unsupported_or_out_of_scope"}:
        return "clarification"
    return "generic_proposal"


def mainline_parity_decision_class_from_metadata(metadata: Mapping[str, Any]) -> str:
    conversation_act = metadata.get("conversation_act")
    if conversation_act:
        return str(conversation_act)
    gate_status = str(metadata.get("gate_status") or "unknown")
    response_tendency = str(metadata.get("response_tendency") or "")
    policy_hint = str(metadata.get("policy_hint") or "")
    if gate_status == "block":
        return "safety_block"
    if gate_status == "ask":
        return "permission_ask"
    if "time" in response_tendency:
        return "local_time"
    if "system" in response_tendency:
        return "local_system_info"
    if "repair" in response_tendency or "repair" in policy_hint:
        return "repair_or_replan"
    if "clarify" in response_tendency or "clarify" in policy_hint:
        return "clarification"
    return "generic_proposal"


def _memory_delta(appraisal: AffectiveAppraisal) -> dict[str, Any]:
    if appraisal.feedback_signal is None:
        return {"type": "none", "reason": appraisal.rationale}
    return {
        "type": "session_feedback_outcome",
        "feedback_signal": appraisal.feedback_signal,
        "repair_need": appraisal.repair_need,
        "trust_delta": appraisal.trust_delta,
        "commitment": "use feedback only inside lab session unless promoted by a formal memory gate",
    }


def _selection_reason(data: Mapping[str, Any]) -> str:
    canonical = _mapping(data.get("canonical_decision"))
    reason = canonical.get("selection_change_reason")
    if reason:
        return str(reason)
    selected = _mapping(canonical.get("after_selected_intention"))
    return str(selected.get("reason") or "canonical decision selected by existing DecisionView")


def _gate_reason(gate_status: str, gate: Mapping[str, Any]) -> str | None:
    if gate_status not in {"block", "ask"}:
        return None
    return str(gate.get("reason") or f"gate status is {gate_status}")


def _view_to_dict(view: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(view, Mapping):
        return {str(key): _jsonable(value) for key, value in view.items()}
    if hasattr(view, "to_dict"):
        return _view_to_dict(view.to_dict())
    if is_dataclass(view):
        return _view_to_dict(asdict(view))
    raise TypeError("subjective loop contract requires a DecisionView or mapping")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
