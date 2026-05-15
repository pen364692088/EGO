from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


CLAIM_CEILING = (
    "lab-only canonical event/plan contract; no runtime influence, no live benefit, "
    "no consciousness, no alive status"
)

VALID_EVENT_TYPES = (
    "user_event",
    "outcome_feedback",
    "autonomous_tick",
    "system_observation",
)

VALID_EVENT_SOURCES = (
    "operator_case",
    "chat_corpus",
    "fixture",
    "future_shadow",
)


@dataclass(frozen=True)
class AgencyEvent:
    event_type: str
    source: str
    semantic_payload: dict[str, Any]
    evidence_refs: tuple[str, ...]
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        if self.event_type not in VALID_EVENT_TYPES:
            raise ValueError(f"unsupported agency event type: {self.event_type}")
        if self.source not in VALID_EVENT_SOURCES:
            raise ValueError(f"unsupported agency event source: {self.source}")
        object.__setattr__(
            self,
            "semantic_payload",
            {str(key): _jsonable(value) for key, value in self.semantic_payload.items()},
        )
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class PerceptionFrame:
    goal: str | None
    feedback: str | None
    feedback_class: str
    risk_hint: str
    relation_hint: str
    source_event_type: str
    source: str
    evidence_refs: tuple[str, ...]
    mutates_state: bool = False
    claim_ceiling: str = CLAIM_CEILING

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class BehaviorPlan:
    plan_id: str
    plan_status: str
    selected_registered_option_id: str | None
    selected_goal: str | None
    selected_option_type: str | None
    primitive_steps: tuple[dict[str, Any], ...]
    gate_status_per_step: tuple[dict[str, Any], ...]
    rollback_note: str | None
    no_action_executed: bool = True
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["primitive_steps"] = list(self.primitive_steps)
        payload["gate_status_per_step"] = list(self.gate_status_per_step)
        return _jsonable(payload)


def build_chat_corpus_agency_event(
    *,
    case_name: str,
    learn_chat: str,
    apply_chat: str,
    feedback: str,
    goal: str,
    expected: str = "",
) -> AgencyEvent:
    return AgencyEvent(
        event_type="outcome_feedback" if feedback.strip() else "user_event",
        source="chat_corpus",
        semantic_payload={
            "case_name": case_name,
            "learn_chat": learn_chat,
            "apply_chat": apply_chat,
            "feedback": feedback,
            "goal": goal,
            "expected": expected,
        },
        evidence_refs=(f"operator:chat_case:{case_name}",),
    )


def build_fixture_agency_event(
    *,
    agent_id: str,
    goals: tuple[str, ...],
    evidence_refs: tuple[str, ...] = ("lab:fixture_cycle",),
) -> AgencyEvent:
    return AgencyEvent(
        event_type="system_observation",
        source="fixture",
        semantic_payload={
            "agent_id": agent_id,
            "goals": list(goals),
            "goal": goals[0] if goals else None,
        },
        evidence_refs=evidence_refs,
    )


def derive_perception_frame(event: AgencyEvent) -> PerceptionFrame:
    payload = event.semantic_payload
    feedback = str(payload.get("feedback") or "").strip() or None
    goal = payload.get("goal")
    return PerceptionFrame(
        goal=str(goal) if goal is not None else None,
        feedback=feedback,
        feedback_class=classify_feedback_text(feedback or ""),
        risk_hint=_risk_hint_from_payload(payload),
        relation_hint=_relation_hint_from_feedback(feedback or ""),
        source_event_type=event.event_type,
        source=event.source,
        evidence_refs=event.evidence_refs,
    )


def build_behavior_plan(
    selected_behavior_option: Mapping[str, Any] | None,
    *,
    selection_restriction: Mapping[str, Any] | None = None,
    gate_decision: Mapping[str, Any] | None = None,
) -> BehaviorPlan:
    restriction = dict(selection_restriction or {})
    if selected_behavior_option is None:
        reason = str(restriction.get("reason") or "no_registered_behavior_option")
        return BehaviorPlan(
            plan_id=f"plan:blocked:{reason}",
            plan_status="no_registered_option",
            selected_registered_option_id=None,
            selected_goal=None,
            selected_option_type=None,
            primitive_steps=(),
            gate_status_per_step=(),
            rollback_note=None,
        )

    option = {str(key): _jsonable(value) for key, value in selected_behavior_option.items()}
    registered_id = str(option.get("registered_option_id"))
    proposed_action = str(option.get("proposed_action"))
    gate_status = str(option.get("gate_status") or (gate_decision or {}).get("status") or "unknown")
    step_id = f"step:001:{registered_id}"
    return BehaviorPlan(
        plan_id=f"plan:{registered_id}",
        plan_status="proposal_only" if bool(option.get("proposal_only")) else "gated",
        selected_registered_option_id=registered_id,
        selected_goal=str(option.get("goal")),
        selected_option_type=str(option.get("option_type")),
        primitive_steps=(
            {
                "step_id": step_id,
                "primitive": "proposal_step",
                "action": proposed_action,
                "registered_option_id": registered_id,
                "no_action_executed": True,
            },
        ),
        gate_status_per_step=(
            {
                "step_id": step_id,
                "action": proposed_action,
                "gate_status": gate_status,
                "allowed_as": option.get("permission_class"),
                "no_action_executed": True,
            },
        ),
        rollback_note=str(option.get("rollback_note")),
    )


def classify_feedback_text(feedback: str) -> str:
    normalized = _normalize(feedback)
    if not normalized:
        return "none"
    if _contains_positive_continue(normalized) and not _contains_unnegated_negative_marker(normalized):
        return "positive_continue"
    if _contains_unnegated_negative_marker(normalized):
        return "negative_continue"
    return "none"


def _contains_positive_continue(normalized: str) -> bool:
    return any(
        marker in normalized
        for marker in (
            "有帮助",
            "挺好",
            "很好",
            "继续推进可以",
            "继续推进挺好",
            "worked",
            "helped",
            "was helpful",
            "keep going",
            "continue worked",
        )
    )


def _contains_unnegated_negative_marker(normalized: str) -> bool:
    markers = (
        "没有帮助",
        "没帮助",
        "仍然卡住",
        "还是卡住",
        "卡住",
        "应该先修复",
        "应该修复",
        "需要修复",
        "修复计划",
        "重新拆目标",
        "重新规划",
        "failed",
        "did not help",
        "didn't help",
        "not help",
        "stuck",
        "needs repair",
        "need repair",
        "repair the plan",
        "replan",
        "split the goal",
        "break down the goal",
    )
    return any(
        marker in normalized and not _is_marker_negated(normalized, marker)
        for marker in markers
    )


def _is_marker_negated(normalized: str, marker: str) -> bool:
    index = normalized.find(marker)
    if index < 0:
        return False
    window = normalized[max(0, index - 12) : index + len(marker) + 8]
    negators = (
        "不要",
        "不需要",
        "不用",
        "无需",
        "不是",
        "别",
        "先别",
        "不该",
        "不要先",
        "do not",
        "don't",
        "dont",
        "no need to",
        "not need",
        "not necessary",
    )
    return any(negator in window for negator in negators)


def _risk_hint_from_payload(payload: Mapping[str, Any]) -> str:
    text = _normalize(" ".join(str(value) for value in payload.values()))
    dangerous = (
        "delete",
        "file_delete",
        "system_command",
        "external_send",
        "删除",
        "发外部消息",
        "执行系统命令",
    )
    return "safety_review" if any(marker in text for marker in dangerous) else "low"


def _relation_hint_from_feedback(feedback: str) -> str:
    normalized = _normalize(feedback)
    if any(marker in normalized for marker in ("误解", "不自然", "太绕", "confusing", "misread")):
        return "repair_needed"
    return "none"


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
