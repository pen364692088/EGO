from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.response_contract.output_check import OutputCheckVerdict, apply_output_check
from app.response_contract.response_plan import ResponsePlan, build_direct_response_plan

from .chat_state import normalize_chat_reply


def _normalize(text: str) -> str:
    return normalize_chat_reply(text)


def _active_task_present(state: Any) -> bool:
    if hasattr(state, "build_active_task_summary"):
        return bool(state.build_active_task_summary())
    return False


def _candidate_repeat_window(state: Any) -> List[str]:
    chat_state = getattr(state, "get_chat_state", lambda: None)()
    if chat_state is None:
        return []
    return [_normalize(text) for text in list(chat_state.recent_assistant_replies or [])[-3:] if _normalize(text)]


def _candidate_matches_recent_reply(state: Any, text: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    return normalized in _candidate_repeat_window(state)


@dataclass(frozen=True)
class InitiativeArbiterVerdict:
    status: str
    reason: str
    selected_candidate: Optional[Dict[str, Any]]
    delivery_ready: bool
    draft_reply_text: str
    response_plan: Optional[ResponsePlan] = None
    output_verdict: Optional[OutputCheckVerdict] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status,
            "reason": self.reason,
            "delivery_ready": self.delivery_ready,
            "draft_reply_text": self.draft_reply_text,
            "selected_candidate": dict(self.selected_candidate or {}) if self.selected_candidate else None,
        }
        if self.response_plan is not None:
            payload["response_plan"] = {
                "kind": self.response_plan.kind,
                "delivery_kind": self.response_plan.delivery_kind,
                "authority_source": self.response_plan.authority_source,
                "reply_authority": self.response_plan.reply_authority,
                "speaker_mode": self.response_plan.speaker_mode,
                "epistemic_status": self.response_plan.epistemic_status,
                "commitment_level": self.response_plan.commitment_level,
                "metadata": dict(self.response_plan.metadata or {}),
            }
        if self.output_verdict is not None:
            payload["output_verdict"] = {
                "passed": self.output_verdict.passed,
                "reason": self.output_verdict.reason,
                "reply_text": self.output_verdict.reply_text,
                "delivery_kind": self.output_verdict.delivery_kind,
                "applied_authority": self.output_verdict.applied_authority,
                "reply_origin": self.output_verdict.reply_origin,
                "intent_gate_status": self.output_verdict.intent_gate_status,
                "intent_gate_reason": self.output_verdict.intent_gate_reason,
            }
        return payload


def evaluate_proactive_followup(
    *,
    state: Any,
    developmental_result: Dict[str, Any],
    idle_seconds: float,
    min_idle_seconds: float = 600.0,
    controlled_mode: bool = True,
) -> InitiativeArbiterVerdict:
    summary = dict(developmental_result.get("developmental_summary") or {})
    gate = dict(developmental_result.get("developmental_gate") or {})
    candidates = list(summary.get("background_thought_candidates") or [])

    if gate.get("status") != "allow":
        return InitiativeArbiterVerdict(
            status="held",
            reason="developmental_gate_not_allow",
            selected_candidate=None,
            delivery_ready=False,
            draft_reply_text="",
        )
    if not candidates:
        return InitiativeArbiterVerdict(
            status="held",
            reason="no_background_thought_candidates",
            selected_candidate=None,
            delivery_ready=False,
            draft_reply_text="",
        )
    if _active_task_present(state):
        return InitiativeArbiterVerdict(
            status="held",
            reason="active_task_present",
            selected_candidate=None,
            delivery_ready=False,
            draft_reply_text="",
        )
    if idle_seconds < min_idle_seconds:
        return InitiativeArbiterVerdict(
            status="held",
            reason="idle_window_too_short",
            selected_candidate=None,
            delivery_ready=False,
            draft_reply_text="",
        )

    selected: Optional[Dict[str, Any]] = None
    for candidate in candidates:
        if not bool(candidate.get("delivery_ready")):
            continue
        draft_text = str(candidate.get("draft_text") or "").strip()
        if not draft_text or _candidate_matches_recent_reply(state, draft_text):
            continue
        selected = dict(candidate)
        break

    if selected is None:
        return InitiativeArbiterVerdict(
            status="held",
            reason="no_non_repetitive_candidate",
            selected_candidate=None,
            delivery_ready=False,
            draft_reply_text="",
        )

    response_plan = build_direct_response_plan(
        str(selected.get("draft_text") or "").strip(),
        kind="chat",
        delivery_kind="chat",
        authority_source="runtime_v2.initiative_arbiter",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "proactive_followup",
            "reply_origin": "proactive_followup",
            "initiative_mode": "controlled_shadow_delivery_draft" if controlled_mode else "live_candidate",
            "initiative_candidate_id": selected.get("candidate_id"),
            "initiative_score": selected.get("initiative_score"),
            "initiative_source_cycle": selected.get("source_cycle"),
            "initiative_source_hash": selected.get("source_candidate_hash"),
        },
        state=state,
    )
    output_verdict = apply_output_check(response_plan, state)
    delivery_ready = bool(output_verdict.passed and output_verdict.reply_text)
    return InitiativeArbiterVerdict(
        status="delivery_ready" if delivery_ready else "held",
        reason=output_verdict.reason if delivery_ready else "output_check_blocked",
        selected_candidate=selected,
        delivery_ready=delivery_ready,
        draft_reply_text=output_verdict.reply_text,
        response_plan=response_plan,
        output_verdict=output_verdict,
    )
