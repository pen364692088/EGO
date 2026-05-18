from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ControlledProactiveOutboxDrainResult:
    status: str
    reason: str
    drained_records: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "drained_records": [dict(record) for record in self.drained_records],
        }


def drain_controlled_proactive_outbox(
    *,
    session_id: str,
    state: Any,
    now_ts: Optional[float] = None,
    drain_mode: str = "simulated_send_record",
    transport_source: str = "simulated_outbox_drain",
) -> ControlledProactiveOutboxDrainResult:
    if not hasattr(state, "has_pending_proactive_outbox_events") or not state.has_pending_proactive_outbox_events():
        return ControlledProactiveOutboxDrainResult(
            status="held",
            reason="no_pending_outbox_events",
            drained_records=[],
        )

    events = state.pop_proactive_outbox_events() if hasattr(state, "pop_proactive_outbox_events") else []
    if not events:
        return ControlledProactiveOutboxDrainResult(
            status="held",
            reason="no_pending_outbox_events",
            drained_records=[],
        )

    base_dt = (
        datetime.fromtimestamp(now_ts, tz=UTC)
        if now_ts is not None
        else datetime.now(UTC)
    )
    drained_records: List[Dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        drained_at = base_dt.isoformat()
        drained_record = {
            "schema_version": "mvp12.simulated_outbox_record.v1",
            "session_id": session_id,
            "message_id": f"simulated:{session_id}:{index}",
            "chat_id": None,
            "date": drained_at,
            "text_length": event.get("text_length"),
            "success": True,
            "drain_mode": drain_mode,
            "transport_source": transport_source,
            "outbox_lane": event.get("outbox_lane"),
            "outbox_status": "drained",
            "reply_text": event.get("reply_text"),
            "reply_authority": event.get("reply_authority"),
            "reply_origin": event.get("reply_origin"),
            "authority_source": event.get("authority_source"),
            "chat_cadence_mode": event.get("chat_cadence_mode"),
            "chat_expression_hint": dict(event.get("chat_expression_hint") or {}),
            "response_tendency_summary": dict(event.get("response_tendency_summary") or {}),
            "initiative_mode": event.get("initiative_mode"),
            "initiative_candidate_id": event.get("initiative_candidate_id"),
            "initiative_source_cycle": event.get("initiative_source_cycle"),
            "initiative_source_hash": event.get("initiative_source_hash"),
            "initiative_score": event.get("initiative_score"),
            "queued_event": dict(event),
        }
        drained_records.append(drained_record)
        if hasattr(state, "record"):
            state.record(
                "proactive_followup_outbox_drain",
                {
                    "status": "drained",
                    "initiative_candidate_id": drained_record.get("initiative_candidate_id"),
                    "reply_origin": drained_record.get("reply_origin"),
                    "reply_authority": drained_record.get("reply_authority"),
                    "text_preview": str(drained_record.get("reply_text") or "")[:120],
                },
            )

    return ControlledProactiveOutboxDrainResult(
        status="drained",
        reason="ok",
        drained_records=drained_records,
    )
