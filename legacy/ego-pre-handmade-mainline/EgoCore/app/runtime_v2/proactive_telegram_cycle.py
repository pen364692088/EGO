from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from .initiative_scheduler import InitiativeSchedulerResult, run_controlled_idle_scheduler
from .proactive_delivery import ControlledProactiveDeliveryResult, consume_pending_proactive_followup
from .proactive_outbox import ControlledProactiveOutboxResult, enqueue_controlled_proactive_outbox


def _active_turn_running(state: Any) -> bool:
    return str(getattr(state, "active_turn_status", "idle") or "idle") not in {"idle", "terminal"}


def _state_busy(state: Any) -> bool:
    return bool(getattr(state, "is_busy", lambda: False)())


@dataclass(frozen=True)
class ProactiveTransportGateVerdict:
    status: str
    reason: str
    idle_seconds: float
    assistant_gap_seconds: float
    pending_outbox_count: int

    @property
    def allowed(self) -> bool:
        return self.status == "allow"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "idle_seconds": round(self.idle_seconds, 3),
            "assistant_gap_seconds": round(self.assistant_gap_seconds, 3),
            "pending_outbox_count": self.pending_outbox_count,
        }


@dataclass(frozen=True)
class HostGovernedProactiveCycleResult:
    status: str
    reason: str
    enable_policy: Optional[Dict[str, Any]]
    scheduler_result: Optional[Dict[str, Any]]
    delivery_result: Optional[Dict[str, Any]]
    outbox_result: Optional[Dict[str, Any]]
    transport_gate: Dict[str, Any]
    transport_result: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "enable_policy": dict(self.enable_policy or {}) if self.enable_policy else None,
            "scheduler_result": dict(self.scheduler_result or {}) if self.scheduler_result else None,
            "delivery_result": dict(self.delivery_result or {}) if self.delivery_result else None,
            "outbox_result": dict(self.outbox_result or {}) if self.outbox_result else None,
            "transport_gate": dict(self.transport_gate or {}),
            "transport_result": dict(self.transport_result or {}) if self.transport_result else None,
        }


def evaluate_proactive_transport_gate(
    *,
    state: Any,
    now_ts: Optional[float] = None,
    min_idle_seconds: float = 900.0,
    min_assistant_gap_seconds: float = 900.0,
) -> ProactiveTransportGateVerdict:
    idle_seconds = float(getattr(state, "idle_seconds_since_chat_activity", lambda **_: 0.0)(now_ts=now_ts))
    pending_events = list(getattr(state, "peek_proactive_outbox_events", lambda: [])() or [])
    pending_count = len(pending_events)
    chat_state = getattr(state, "get_chat_state", lambda: None)()
    last_assistant_reply_at = getattr(chat_state, "last_assistant_reply_at", None) if chat_state is not None else None
    current_ts = float(now_ts if now_ts is not None else 0.0)
    if now_ts is None and chat_state is not None:
        current_ts = float(getattr(chat_state, "last_activity_at", 0.0) or 0.0) + idle_seconds
    assistant_gap_seconds = idle_seconds if not last_assistant_reply_at else max(0.0, current_ts - float(last_assistant_reply_at))

    if pending_count <= 0:
        return ProactiveTransportGateVerdict("hold", "no_pending_outbox_events", idle_seconds, assistant_gap_seconds, pending_count)
    if _active_turn_running(state):
        return ProactiveTransportGateVerdict("hold", "active_turn_running", idle_seconds, assistant_gap_seconds, pending_count)
    if _state_busy(state):
        return ProactiveTransportGateVerdict("hold", "state_busy", idle_seconds, assistant_gap_seconds, pending_count)
    if idle_seconds < float(min_idle_seconds):
        return ProactiveTransportGateVerdict("hold", "idle_window_too_short", idle_seconds, assistant_gap_seconds, pending_count)
    if assistant_gap_seconds < float(min_assistant_gap_seconds):
        return ProactiveTransportGateVerdict("hold", "assistant_reply_cooldown_active", idle_seconds, assistant_gap_seconds, pending_count)
    return ProactiveTransportGateVerdict("allow", "ok", idle_seconds, assistant_gap_seconds, pending_count)


async def run_host_governed_proactive_cycle(
    *,
    session_id: str,
    state: Any,
    proto_self_runtime: Any,
    transport_drain: Callable[[str, Optional[int]], Awaitable[Dict[str, Any]]],
    now_ts: Optional[float] = None,
    scheduler_min_idle_seconds: float = 600.0,
    transport_min_idle_seconds: float = 900.0,
    assistant_reply_cooldown_seconds: float = 900.0,
    max_transport_events: int = 1,
    observation_source: str = "direct_real",
    controlled_mode: bool = False,
) -> HostGovernedProactiveCycleResult:
    scheduler_payload: Optional[Dict[str, Any]] = None
    delivery_payload: Optional[Dict[str, Any]] = None
    outbox_payload: Optional[Dict[str, Any]] = None

    if proto_self_runtime is None:
        gate = evaluate_proactive_transport_gate(
            state=state,
            now_ts=now_ts,
            min_idle_seconds=transport_min_idle_seconds,
            min_assistant_gap_seconds=assistant_reply_cooldown_seconds,
        )
        return HostGovernedProactiveCycleResult(
            status="held",
            reason="proto_self_runtime_unavailable",
            enable_policy=None,
            scheduler_result=None,
            delivery_result=None,
            outbox_result=None,
            transport_gate=gate.to_dict(),
            transport_result=None,
        )

    if not getattr(state, "has_pending_proactive_outbox_events", lambda: False)():
        pending_followup = getattr(state, "get_pending_proactive_followup", lambda: None)()
        if pending_followup:
            delivery_result = consume_pending_proactive_followup(
                session_id=session_id,
                state=state,
                now_ts=now_ts,
                delivery_mode="host_governed_transport_ready",
                transport_source="host_governed_scheduler",
            )
            delivery_payload = delivery_result.to_dict()
        else:
            scheduler_result = run_controlled_idle_scheduler(
                session_id=session_id,
                state=state,
                proto_self_runtime=proto_self_runtime,
                now_ts=now_ts,
                min_idle_seconds=scheduler_min_idle_seconds,
                observation_source=observation_source,
                controlled_mode=controlled_mode,
            )
            scheduler_payload = scheduler_result.to_dict()
            if scheduler_result.status != "pending_created":
                gate = evaluate_proactive_transport_gate(
                    state=state,
                    now_ts=now_ts,
                    min_idle_seconds=transport_min_idle_seconds,
                    min_assistant_gap_seconds=assistant_reply_cooldown_seconds,
                )
                return HostGovernedProactiveCycleResult(
                    status="held",
                    reason=f"scheduler:{scheduler_result.reason}",
                    enable_policy=None,
                    scheduler_result=scheduler_payload,
                    delivery_result=None,
                    outbox_result=None,
                    transport_gate=gate.to_dict(),
                    transport_result=None,
                )

            delivery_result = consume_pending_proactive_followup(
                session_id=session_id,
                state=state,
                now_ts=(float(now_ts) + 1.0) if now_ts is not None else None,
                delivery_mode="host_governed_transport_ready",
                transport_source="host_governed_scheduler",
            )
            delivery_payload = delivery_result.to_dict()

        if delivery_payload is None or delivery_payload.get("status") != "artifact_emitted":
            gate = evaluate_proactive_transport_gate(
                state=state,
                now_ts=now_ts,
                min_idle_seconds=transport_min_idle_seconds,
                min_assistant_gap_seconds=assistant_reply_cooldown_seconds,
            )
            return HostGovernedProactiveCycleResult(
                status="held",
                reason=f"delivery:{(delivery_payload or {}).get('reason') or 'unavailable'}",
                enable_policy=None,
                scheduler_result=scheduler_payload,
                delivery_result=delivery_payload,
                outbox_result=None,
                transport_gate=gate.to_dict(),
                transport_result=None,
            )

        emitted_delivery = dict(delivery_payload.get("emitted_delivery") or {})
        outbox_result = enqueue_controlled_proactive_outbox(
            session_id=session_id,
            state=state,
            emitted_delivery=emitted_delivery,
            now_ts=(float(now_ts) + 2.0) if now_ts is not None else None,
            outbox_lane="host_proactive_outbox",
        )
        outbox_payload = outbox_result.to_dict()
        if outbox_result.status != "queued":
            gate = evaluate_proactive_transport_gate(
                state=state,
                now_ts=now_ts,
                min_idle_seconds=transport_min_idle_seconds,
                min_assistant_gap_seconds=assistant_reply_cooldown_seconds,
            )
            return HostGovernedProactiveCycleResult(
                status="held",
                reason=f"outbox:{outbox_result.reason}",
                enable_policy=None,
                scheduler_result=scheduler_payload,
                delivery_result=delivery_payload,
                outbox_result=outbox_payload,
                transport_gate=gate.to_dict(),
                transport_result=None,
            )

    gate = evaluate_proactive_transport_gate(
        state=state,
        now_ts=now_ts,
        min_idle_seconds=transport_min_idle_seconds,
        min_assistant_gap_seconds=assistant_reply_cooldown_seconds,
    )
    if hasattr(state, "record"):
        state.record(
            "proactive_followup_transport_gate",
            {
                "status": gate.status,
                "reason": gate.reason,
                "idle_seconds": round(gate.idle_seconds, 3),
                "assistant_gap_seconds": round(gate.assistant_gap_seconds, 3),
                "pending_outbox_count": gate.pending_outbox_count,
            },
        )
    if not gate.allowed:
        return HostGovernedProactiveCycleResult(
            status="held",
            reason=f"transport_gate:{gate.reason}",
            enable_policy=None,
            scheduler_result=scheduler_payload,
            delivery_result=delivery_payload,
            outbox_result=outbox_payload,
            transport_gate=gate.to_dict(),
            transport_result=None,
        )

    transport_result = await transport_drain(session_id, max(1, int(max_transport_events)))
    status = str(transport_result.get("status") or "held")
    reason = str(transport_result.get("reason") or ("ok" if status == "sent" else "transport_held"))
    return HostGovernedProactiveCycleResult(
        status=status,
        reason=reason,
        enable_policy=None,
        scheduler_result=scheduler_payload,
        delivery_result=delivery_payload,
        outbox_result=outbox_payload,
        transport_gate=gate.to_dict(),
        transport_result=transport_result,
    )
