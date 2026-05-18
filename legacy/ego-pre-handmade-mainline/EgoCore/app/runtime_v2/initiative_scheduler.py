from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from .initiative_arbiter import InitiativeArbiterVerdict, evaluate_proactive_followup
from .proto_self_runtime import RuntimeV2ProtoSelfRuntime
from .state import RuntimeV2State


def _trim_text(text: Any, *, limit: int = 72) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _build_state_snapshot(state: RuntimeV2State) -> Dict[str, Any]:
    chat_state = state.get_chat_state()
    return {
        "recent_user_turns": list(chat_state.recent_user_turns[-4:]),
        "recent_assistant_replies": list(chat_state.recent_assistant_replies[-4:]),
        "last_chat_act": chat_state.last_chat_act,
        "active_task_summary": state.build_active_task_summary(),
        "current_goal": state.current_goal,
        "task_status": state.task_status,
        "pending_proactive_followup": state.get_pending_proactive_followup(),
    }


def _build_observation_refs(state: RuntimeV2State) -> List[Dict[str, Any]]:
    chat_state = state.get_chat_state()
    refs: List[Dict[str, Any]] = []
    user_created_at = (
        datetime.fromtimestamp(chat_state.last_user_turn_at, tz=UTC).isoformat()
        if chat_state.last_user_turn_at
        else None
    )
    assistant_created_at = (
        datetime.fromtimestamp(chat_state.last_assistant_reply_at, tz=UTC).isoformat()
        if chat_state.last_assistant_reply_at
        else None
    )
    for index, text in enumerate(list(chat_state.recent_user_turns[-4:]), start=1):
        refs.append(
            {
                "kind": "runtime_chat_user_turn",
                "event_id": f"{state.session_id}:chat_user:{index}",
                "created_at": user_created_at,
                "text_preview": _trim_text(text, limit=56),
            }
        )
    for index, text in enumerate(list(chat_state.recent_assistant_replies[-4:]), start=1):
        refs.append(
            {
                "kind": "runtime_chat_assistant_reply",
                "event_id": f"{state.session_id}:chat_assistant:{index}",
                "created_at": assistant_created_at,
                "text_preview": _trim_text(text, limit=72),
            }
        )
    return refs[-8:]


def _derive_unresolved_tensions(state: RuntimeV2State) -> List[Dict[str, Any]]:
    chat_state = state.get_chat_state()
    latest_user_turn = str(chat_state.recent_user_turns[-1] if chat_state.recent_user_turns else "").strip()
    if not latest_user_turn:
        return []
    return [
        {
            "kind": "reflective_thread",
            "label": _trim_text(latest_user_turn, limit=48),
            "intensity": 0.78,
        }
    ]


def _derive_long_term_goals(state: RuntimeV2State) -> List[Dict[str, Any]]:
    chat_state = state.get_chat_state()
    latest_user_turn = str(chat_state.recent_user_turns[-1] if chat_state.recent_user_turns else "").strip()
    if not latest_user_turn:
        return []
    return [
        {
            "label": f"continue:{_trim_text(latest_user_turn, limit=32)}",
            "pressure": 0.74,
        }
    ]


@dataclass(frozen=True)
class InitiativeSchedulerResult:
    status: str
    reason: str
    idle_seconds: float
    developmental_result: Optional[Dict[str, Any]]
    initiative_verdict: Optional[InitiativeArbiterVerdict]
    pending_proactive_followup: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status,
            "reason": self.reason,
            "idle_seconds": round(self.idle_seconds, 3),
            "pending_proactive_followup": dict(self.pending_proactive_followup or {}) if self.pending_proactive_followup else None,
        }
        if self.developmental_result is not None:
            payload["developmental_summary"] = dict(self.developmental_result.get("developmental_summary") or {})
            payload["developmental_gate"] = dict(self.developmental_result.get("developmental_gate") or {})
        if self.initiative_verdict is not None:
            payload["initiative_verdict"] = self.initiative_verdict.to_dict()
        return payload


def run_controlled_idle_scheduler(
    *,
    session_id: str,
    state: RuntimeV2State,
    proto_self_runtime: Optional[RuntimeV2ProtoSelfRuntime],
    now_ts: Optional[float] = None,
    min_idle_seconds: float = 600.0,
    observation_source: str = "direct_real",
    controlled_mode: bool = True,
) -> InitiativeSchedulerResult:
    idle_seconds = state.idle_seconds_since_chat_activity(now_ts=now_ts)

    if proto_self_runtime is None:
        return InitiativeSchedulerResult(
            status="held",
            reason="proto_self_runtime_unavailable",
            idle_seconds=idle_seconds,
            developmental_result=None,
            initiative_verdict=None,
            pending_proactive_followup=None,
        )

    existing_pending = state.get_pending_proactive_followup()
    if existing_pending:
        return InitiativeSchedulerResult(
            status="held",
            reason="pending_followup_exists",
            idle_seconds=idle_seconds,
            developmental_result=None,
            initiative_verdict=None,
            pending_proactive_followup=existing_pending,
        )

    chat_state = state.get_chat_state()
    if not chat_state.recent_user_turns or not chat_state.recent_assistant_replies:
        return InitiativeSchedulerResult(
            status="held",
            reason="insufficient_chat_history",
            idle_seconds=idle_seconds,
            developmental_result=None,
            initiative_verdict=None,
            pending_proactive_followup=None,
        )

    developmental_result = proto_self_runtime.process_developmental_tick(
        session_id=session_id,
        turn_id="turn_controlled_idle_scheduler",
        state=state,
        observation_source=observation_source,
        trigger="idle",
        idle_seconds=idle_seconds,
        unresolved_tensions=_derive_unresolved_tensions(state),
        long_term_goals=_derive_long_term_goals(state),
        observation_refs=_build_observation_refs(state),
        state_snapshot=_build_state_snapshot(state),
        force_enable=True,
    )
    if developmental_result is None:
        return InitiativeSchedulerResult(
            status="held",
            reason="developmental_tick_unavailable",
            idle_seconds=idle_seconds,
            developmental_result=None,
            initiative_verdict=None,
            pending_proactive_followup=None,
        )

    verdict = evaluate_proactive_followup(
        state=state,
        developmental_result=developmental_result,
        idle_seconds=idle_seconds,
        min_idle_seconds=min_idle_seconds,
        controlled_mode=controlled_mode,
    )
    if not verdict.delivery_ready:
        state.record(
            "proactive_followup_scheduler",
            {
                "status": "held",
                "reason": verdict.reason,
                "idle_seconds": round(idle_seconds, 3),
            },
        )
        return InitiativeSchedulerResult(
            status="held",
            reason=verdict.reason,
            idle_seconds=idle_seconds,
            developmental_result=developmental_result,
            initiative_verdict=verdict,
            pending_proactive_followup=None,
        )

    created_at = (
        datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
        if now_ts is not None
        else datetime.now(UTC).isoformat()
    )
    pending_payload = {
        "schema_version": "mvp12.pending_proactive_followup.v1",
        "session_id": session_id,
        "created_at": created_at,
        "idle_seconds": round(idle_seconds, 3),
        "delivery_status": "pending",
        "initiative_verdict": verdict.to_dict(),
        "developmental_summary": dict(developmental_result.get("developmental_summary") or {}),
        "developmental_gate": dict(developmental_result.get("developmental_gate") or {}),
    }
    state.set_pending_proactive_followup(pending_payload)
    state.record(
        "proactive_followup_scheduler",
        {
            "status": "pending_created",
            "reason": verdict.reason,
            "idle_seconds": round(idle_seconds, 3),
            "candidate_id": (verdict.selected_candidate or {}).get("candidate_id"),
        },
    )
    return InitiativeSchedulerResult(
        status="pending_created",
        reason=verdict.reason,
        idle_seconds=idle_seconds,
        developmental_result=developmental_result,
        initiative_verdict=verdict,
        pending_proactive_followup=pending_payload,
    )
