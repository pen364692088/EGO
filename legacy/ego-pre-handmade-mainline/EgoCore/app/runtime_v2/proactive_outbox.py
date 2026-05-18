from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


def _queued_candidate_ids(state: Any) -> List[str]:
    if not hasattr(state, "peek_proactive_outbox_events"):
        return []
    queued = state.peek_proactive_outbox_events()
    result: List[str] = []
    for event in queued:
        candidate_id = str(event.get("initiative_candidate_id") or "").strip()
        if candidate_id:
            result.append(candidate_id)
    return result


@dataclass(frozen=True)
class ControlledProactiveOutboxResult:
    status: str
    reason: str
    queued_event: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "queued_event": dict(self.queued_event or {}) if self.queued_event else None,
        }


def enqueue_controlled_proactive_outbox(
    *,
    session_id: str,
    state: Any,
    emitted_delivery: Optional[Dict[str, Any]],
    now_ts: Optional[float] = None,
    outbox_lane: str = "host_proactive_outbox",
) -> ControlledProactiveOutboxResult:
    delivery = dict(emitted_delivery or {})
    if not delivery:
        return ControlledProactiveOutboxResult(
            status="held",
            reason="no_emitted_delivery",
            queued_event=None,
        )

    delivery_status = str(delivery.get("delivery_status") or "").strip()
    if delivery_status != "artifact_emitted":
        return ControlledProactiveOutboxResult(
            status="held",
            reason="delivery_not_artifact_emitted",
            queued_event=None,
        )

    candidate_id = str(delivery.get("initiative_candidate_id") or "").strip()
    if candidate_id and candidate_id in _queued_candidate_ids(state):
        return ControlledProactiveOutboxResult(
            status="held",
            reason="duplicate_candidate",
            queued_event=None,
        )

    queued_at = (
        datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
        if now_ts is not None
        else datetime.now(UTC).isoformat()
    )
    queued_event = {
        "schema_version": "mvp12.proactive_outbox_event.v1",
        "session_id": session_id,
        "queued_at": queued_at,
        "outbox_lane": outbox_lane,
        "outbox_status": "queued",
        "reply_text": delivery.get("reply_text"),
        "text_length": delivery.get("text_length"),
        "delivery_kind": delivery.get("delivery_kind"),
        "reply_authority": delivery.get("reply_authority"),
        "reply_origin": delivery.get("reply_origin"),
        "authority_source": delivery.get("authority_source"),
        "chat_cadence_mode": delivery.get("chat_cadence_mode"),
        "chat_expression_hint": dict(delivery.get("chat_expression_hint") or {}),
        "response_tendency_summary": dict(delivery.get("response_tendency_summary") or {}),
        "transport_source": delivery.get("transport_source"),
        "initiative_mode": delivery.get("initiative_mode"),
        "initiative_candidate_id": delivery.get("initiative_candidate_id"),
        "initiative_source_cycle": delivery.get("initiative_source_cycle"),
        "initiative_source_hash": delivery.get("initiative_source_hash"),
        "initiative_score": delivery.get("initiative_score"),
        "delivery_record": delivery,
    }
    if hasattr(state, "push_proactive_outbox_event"):
        state.push_proactive_outbox_event(queued_event)
    if hasattr(state, "record"):
        state.record(
            "proactive_followup_outbox",
            {
                "status": "queued",
                "initiative_candidate_id": queued_event.get("initiative_candidate_id"),
                "reply_origin": queued_event.get("reply_origin"),
                "reply_authority": queued_event.get("reply_authority"),
                "text_preview": str(queued_event.get("reply_text") or "")[:120],
            },
        )
    return ControlledProactiveOutboxResult(
        status="queued",
        reason="ok",
        queued_event=queued_event,
    )
