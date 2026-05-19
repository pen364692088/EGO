from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .initiative_scheduler import (
    _build_observation_refs,
    _build_state_snapshot,
    _derive_long_term_goals,
    _derive_unresolved_tensions,
)
from .proto_self_runtime import RuntimeV2ProtoSelfRuntime
from .state import RuntimeV2State
from .subject_system_v1_delivery_bridge import (
    SubjectSystemV1DeliveryBridgeResult,
    build_pending_proactive_followup_from_subject_system_v1,
)


@dataclass(frozen=True)
class SubjectSystemV1IdleSchedulerResult:
    status: str
    reason: str
    idle_seconds: float
    developmental_result: Optional[Dict[str, Any]]
    bridge_result: Optional[SubjectSystemV1DeliveryBridgeResult]
    pending_proactive_followup: Optional[Dict[str, Any]]
    observation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "status": self.status,
            "reason": self.reason,
            "idle_seconds": round(self.idle_seconds, 3),
            "scheduler_source": "subject_system_v1",
            "pending_proactive_followup": (
                dict(self.pending_proactive_followup or {}) if self.pending_proactive_followup else None
            ),
        }
        payload.update(dict(self.observation or {}))
        if self.developmental_result is not None:
            payload["developmental_summary"] = dict(self.developmental_result.get("developmental_summary") or {})
            payload["developmental_gate"] = dict(self.developmental_result.get("developmental_gate") or {})
            payload["host_proactive_decision"] = dict(self.developmental_result.get("host_proactive_decision") or {})
        if self.bridge_result is not None:
            payload["bridge_result"] = self.bridge_result.to_dict()
        return payload


def _build_scheduler_observation(
    *,
    state: RuntimeV2State,
    idle_seconds: float,
    developmental_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    chat_state = state.get_chat_state()
    recent_user_turns = list(chat_state.recent_user_turns or [])
    recent_assistant_replies = list(chat_state.recent_assistant_replies or [])
    developmental_payload = dict(developmental_result or {})
    subject_system_v1 = dict(developmental_payload.get("subject_system_v1") or {})
    trace_payload = dict(subject_system_v1.get("trace_payload") or developmental_payload.get("trace_payload") or {})
    initiative_context = dict(trace_payload.get("initiative_context") or {})
    host_candidate = dict(subject_system_v1.get("host_proactive_candidate") or {})
    host_proactive_context = dict(trace_payload.get("host_proactive_context") or {})
    priority_snapshot = dict(developmental_payload.get("cross_axis_priority_snapshot") or {})

    observation: Dict[str, Any] = {
        "recent_user_turns_count": len(recent_user_turns),
        "recent_assistant_replies_count": len(recent_assistant_replies),
        "chat_followup_inferred": bool(initiative_context.get("chat_followup_source")),
        "initiative_trigger": str(initiative_context.get("initiative_trigger") or "").strip(),
        "continuity_ref": str(
            initiative_context.get("continuity_ref") or host_candidate.get("continuity_ref") or ""
        ).strip(),
        "continuity_confidence": host_candidate.get("continuity_confidence"),
        "candidate_family": str(host_candidate.get("candidate_family") or host_proactive_context.get("candidate_family") or "").strip(),
        "topic_source": str(host_candidate.get("topic_source") or host_proactive_context.get("topic_source") or "").strip(),
        "topic_fingerprint": str(host_candidate.get("topic_fingerprint") or host_proactive_context.get("topic_fingerprint") or "").strip(),
        "topic_cluster_ref": str(host_candidate.get("topic_cluster_ref") or host_proactive_context.get("topic_cluster_ref") or "").strip(),
        "topic_anchor_summary": str(host_candidate.get("topic_anchor_summary") or host_proactive_context.get("topic_anchor_summary") or "").strip(),
        "topic_anchor_source": str(host_candidate.get("topic_anchor_source") or host_proactive_context.get("topic_anchor_source") or "").strip(),
        "topic_anchor_kind": str(host_candidate.get("topic_anchor_kind") or host_proactive_context.get("topic_anchor_kind") or "").strip(),
        "topic_binding_mode": str(host_candidate.get("topic_binding_mode") or host_proactive_context.get("topic_binding_mode") or "").strip(),
        "topic_sendability": str(host_candidate.get("topic_sendability") or host_proactive_context.get("topic_sendability") or "").strip(),
        "topic_conversation_grade": str(host_candidate.get("topic_conversation_grade") or host_proactive_context.get("topic_conversation_grade") or "").strip(),
        "raw_topic_anchor_summary": str(host_candidate.get("raw_topic_anchor_summary") or host_proactive_context.get("raw_topic_anchor_summary") or "").strip(),
        "effective_topic_anchor_summary": str(host_candidate.get("effective_topic_anchor_summary") or host_proactive_context.get("effective_topic_anchor_summary") or "").strip(),
        "topic_anchor_rebound_source": str(host_candidate.get("topic_anchor_rebound_source") or host_proactive_context.get("topic_anchor_rebound_source") or "").strip(),
        "timing_mode": str(((host_candidate.get("timing_advice") or {}).get("timing_mode") or "")).strip(),
        "quiet_state": str(host_candidate.get("quiet_state") or initiative_context.get("quiet_state") or "").strip(),
        "feedback_signal": str(host_candidate.get("feedback_signal") or initiative_context.get("feedback_signal") or "").strip(),
        "outreach_reason": str(host_candidate.get("outreach_reason") or "").strip(),
        "selfhood_priority": str(
            host_candidate.get("selfhood_priority") or priority_snapshot.get("selected_priority") or ""
        ).strip(),
    }
    if initiative_context.get("chat_followup_source"):
        observation["chat_followup_source"] = str(initiative_context.get("chat_followup_source") or "").strip()
    if initiative_context.get("pending_commitment_source"):
        observation["pending_commitment_source"] = str(
            initiative_context.get("pending_commitment_source") or ""
        ).strip()
    if initiative_context.get("proactive_topic_permission"):
        observation["proactive_topic_permission"] = str(
            initiative_context.get("proactive_topic_permission") or ""
        ).strip()
    observation["idle_seconds"] = round(idle_seconds, 3)
    return observation


def _current_lane_explicitly_disabled(state: RuntimeV2State) -> bool:
    ingress_context = dict(state.ingress_context or {})
    return bool(ingress_context.get("subject_system_v1_proactive_disabled"))


def run_subject_system_v1_idle_scheduler(
    *,
    session_id: str,
    state: RuntimeV2State,
    proto_self_runtime: Optional[RuntimeV2ProtoSelfRuntime],
    now_ts: Optional[float] = None,
    min_idle_seconds: float = 600.0,
    observation_source: str = "direct_real",
) -> SubjectSystemV1IdleSchedulerResult:
    idle_seconds = state.idle_seconds_since_chat_activity(now_ts=now_ts)
    base_observation = _build_scheduler_observation(
        state=state,
        idle_seconds=idle_seconds,
        developmental_result=None,
    )

    if _current_lane_explicitly_disabled(state):
        return SubjectSystemV1IdleSchedulerResult(
            status="held",
            reason="current_lane_disabled",
            idle_seconds=idle_seconds,
            developmental_result=None,
            bridge_result=None,
            pending_proactive_followup=None,
            observation=base_observation,
        )

    if proto_self_runtime is None:
        return SubjectSystemV1IdleSchedulerResult(
            status="held",
            reason="proto_self_runtime_unavailable",
            idle_seconds=idle_seconds,
            developmental_result=None,
            bridge_result=None,
            pending_proactive_followup=None,
            observation=base_observation,
        )

    existing_pending = state.get_pending_proactive_followup()
    if existing_pending:
        return SubjectSystemV1IdleSchedulerResult(
            status="held",
            reason="pending_followup_exists",
            idle_seconds=idle_seconds,
            developmental_result=None,
            bridge_result=None,
            pending_proactive_followup=existing_pending,
            observation=base_observation,
        )

    chat_state = state.get_chat_state()
    if not chat_state.recent_user_turns or not chat_state.recent_assistant_replies:
        return SubjectSystemV1IdleSchedulerResult(
            status="held",
            reason="insufficient_chat_history",
            idle_seconds=idle_seconds,
            developmental_result=None,
            bridge_result=None,
            pending_proactive_followup=None,
            observation=base_observation,
        )

    developmental_result = proto_self_runtime.process_developmental_tick(
        session_id=session_id,
        turn_id="turn_subject_system_v1_idle_scheduler",
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
    scheduler_observation = _build_scheduler_observation(
        state=state,
        idle_seconds=idle_seconds,
        developmental_result=developmental_result,
    )
    if developmental_result is None:
        return SubjectSystemV1IdleSchedulerResult(
            status="held",
            reason="developmental_tick_unavailable",
            idle_seconds=idle_seconds,
            developmental_result=None,
            bridge_result=None,
            pending_proactive_followup=None,
            observation=base_observation,
        )

    bridge_result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=session_id,
        state=state,
        now_ts=now_ts,
        subject_system_v1=dict(developmental_result.get("subject_system_v1") or {}),
        host_proactive_decision=dict(developmental_result.get("host_proactive_decision") or {}),
    )
    if bridge_result.status == "pending_created":
        if hasattr(state, "record"):
            state.record(
                "subject_system_v1_proactive_scheduler",
                {
                    "status": "pending_created",
                    "reason": bridge_result.reason,
                    "candidate_id": (bridge_result.selected_candidate or {}).get("candidate_id"),
                    **scheduler_observation,
                },
            )
        return SubjectSystemV1IdleSchedulerResult(
            status="pending_created",
            reason=bridge_result.reason,
            idle_seconds=idle_seconds,
            developmental_result=developmental_result,
            bridge_result=bridge_result,
            pending_proactive_followup=bridge_result.pending_proactive_followup,
            observation=scheduler_observation,
        )

    if idle_seconds < min_idle_seconds and bridge_result.reason == "host_proactive_decision:not_idle":
        reason = "idle_window_too_short"
    else:
        reason = bridge_result.reason
    if hasattr(state, "record"):
        state.record(
            "subject_system_v1_proactive_scheduler",
            {
                "status": "held",
                "reason": reason,
                **scheduler_observation,
            },
        )
    return SubjectSystemV1IdleSchedulerResult(
        status="held",
        reason=reason,
        idle_seconds=idle_seconds,
        developmental_result=developmental_result,
        bridge_result=bridge_result,
        pending_proactive_followup=None,
        observation=scheduler_observation,
    )
