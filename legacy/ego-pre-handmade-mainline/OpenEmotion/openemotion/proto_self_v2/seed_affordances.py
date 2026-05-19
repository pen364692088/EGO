from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openemotion.proto_self_v2.seed_schemas import KernelEvent
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState

_EXPLICIT_FOLLOWUP_REMINDER_TOKENS = (
    "提醒我",
    "轻提醒",
    "提醒",
    "remindme",
    "reminder",
)

_EXPLICIT_FOLLOWUP_CONTINUATION_TOKENS = (
    "继续这个话题",
    "继续聊",
    "回来继续",
    "回头继续",
    "接着聊",
    "followup",
    "continue",
)


@dataclass(slots=True)
class Affordance:
    action_type: str
    expected_gain: float
    risk_level: str
    reversible: bool
    target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _pick_target(runtime_summary: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
    return (
        payload.get("resolved_target_path")
        or payload.get("resolved_target_name")
        or runtime_summary.get("resolved_target_path")
        or runtime_summary.get("resolved_target_name")
        or runtime_summary.get("recent_failure_target")
    )


def _normalize_text(text: Any) -> str:
    return "".join(str(text or "").strip().lower().split())


def _is_explicit_same_thread_followup_request(runtime_summary: Dict[str, Any], raw_text: Any) -> bool:
    initiative_context = dict(runtime_summary.get("initiative_context") or {})
    if str(initiative_context.get("chat_followup_source") or "").strip() == "explicit_same_thread_followup_request":
        return True

    normalized = _normalize_text(raw_text)
    if not normalized:
        return False
    has_reminder_request = any(token in normalized for token in _EXPLICIT_FOLLOWUP_REMINDER_TOKENS)
    has_continuation_request = any(token in normalized for token in _EXPLICIT_FOLLOWUP_CONTINUATION_TOKENS) or (
        "继续" in normalized and any(marker in normalized for marker in ("话题", "回来", "回头", "等下", "稍后", "过会儿", "接着"))
    )
    return has_reminder_request and has_continuation_request


def resolve_pending_commitment(
    runtime_summary: Dict[str, Any],
    state_pending_commitment: Optional[str],
    *,
    raw_text: Any = None,
) -> tuple[Optional[str], bool, str]:
    runtime_pending_commitment = str(runtime_summary.get("pending_commitment") or "").strip()
    if runtime_pending_commitment:
        return runtime_pending_commitment, False, "runtime"

    explicit_same_thread_followup = _is_explicit_same_thread_followup_request(runtime_summary, raw_text)
    if explicit_same_thread_followup:
        return None, bool(str(state_pending_commitment or "").strip()), "suppressed_for_explicit_followup"

    state_pending = str(state_pending_commitment or "").strip()
    if state_pending:
        return state_pending, False, "state_fallback"
    return None, False, ""


def extract_affordances(event: KernelEvent, state: ProtoSelfSeedState) -> List[Affordance]:
    runtime = event.runtime_summary or {}
    payload = event.payload or {}
    affordances: List[Affordance] = []
    target = _pick_target(runtime, payload)

    if target:
        affordances.append(
            Affordance(
                action_type="inspect_file",
                target=target,
                expected_gain=0.62,
                risk_level="low",
                reversible=True,
                metadata={"origin": "resolved_target"},
            )
        )
        if runtime.get("request_mode") == "write":
            affordances.append(
                Affordance(
                    action_type="write_file",
                    target=target,
                    expected_gain=0.68,
                    risk_level="medium",
                    reversible=False,
                    metadata={"origin": "write_target"},
                )
            )

    if runtime.get("recent_failure_target"):
        affordances.append(
            Affordance(
                action_type="review_recent_failure",
                target=str(runtime.get("recent_failure_target")),
                expected_gain=0.58,
                risk_level="low",
                reversible=True,
                metadata={"origin": "recent_failure"},
            )
        )

    pending_commitment, _, _ = resolve_pending_commitment(
        runtime,
        state.focus_goal.pending_commitment,
        raw_text=payload.get("raw_text"),
    )
    if pending_commitment:
        affordances.append(
            Affordance(
                action_type="continue_pending_commitment",
                target=str(pending_commitment),
                expected_gain=0.66,
                risk_level="low",
                reversible=True,
                metadata={"origin": "pending_commitment"},
            )
        )

    if runtime.get("clarification_needed") or runtime.get("confirm_pending"):
        affordances.append(
            Affordance(
                action_type="ask_user",
                expected_gain=0.42,
                risk_level="low",
                reversible=True,
                metadata={"origin": "clarification"},
            )
        )

    browser_tabs = runtime.get("browser_tabs") or []
    if browser_tabs:
        affordances.append(
            Affordance(
                action_type="inspect_browser",
                target=str(browser_tabs[0]),
                expected_gain=0.50,
                risk_level="low",
                reversible=True,
                metadata={"origin": "browser_tabs"},
            )
        )

    return affordances
