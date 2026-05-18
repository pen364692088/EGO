from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, Optional


def _active_task_present(state: Any) -> bool:
    if hasattr(state, "build_active_task_summary"):
        return bool(state.build_active_task_summary())
    return False


def _pending_output_verdict(pending: Dict[str, Any]) -> Dict[str, Any]:
    verdict = dict(pending.get("initiative_verdict") or {})
    return dict(verdict.get("output_verdict") or {})


def _pending_response_plan(pending: Dict[str, Any]) -> Dict[str, Any]:
    verdict = dict(pending.get("initiative_verdict") or {})
    return dict(verdict.get("response_plan") or {})


@dataclass(frozen=True)
class ControlledProactiveDeliveryResult:
    status: str
    reason: str
    emitted_delivery: Optional[Dict[str, Any]]
    consumed_pending: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "emitted_delivery": dict(self.emitted_delivery or {}) if self.emitted_delivery else None,
            "consumed_pending": dict(self.consumed_pending or {}) if self.consumed_pending else None,
        }


def consume_pending_proactive_followup(
    *,
    session_id: str,
    state: Any,
    now_ts: Optional[float] = None,
    delivery_mode: str = "controlled_artifact_only",
    transport_source: str = "controlled_runner",
) -> ControlledProactiveDeliveryResult:
    pending = state.get_pending_proactive_followup() if hasattr(state, "get_pending_proactive_followup") else None
    if not pending:
        return ControlledProactiveDeliveryResult(
            status="held",
            reason="no_pending_followup",
            emitted_delivery=None,
            consumed_pending=None,
        )

    if _active_task_present(state):
        return ControlledProactiveDeliveryResult(
            status="held",
            reason="active_task_present",
            emitted_delivery=None,
            consumed_pending=dict(pending),
        )

    delivery_status = str(pending.get("delivery_status") or "").strip()
    if delivery_status != "pending":
        return ControlledProactiveDeliveryResult(
            status="held",
            reason="pending_not_ready",
            emitted_delivery=None,
            consumed_pending=dict(pending),
        )

    initiative_verdict = dict(pending.get("initiative_verdict") or {})
    output_verdict = _pending_output_verdict(pending)
    response_plan = _pending_response_plan(pending)
    reply_text = str(output_verdict.get("reply_text") or "").strip()
    if not bool(initiative_verdict.get("delivery_ready")):
        return ControlledProactiveDeliveryResult(
            status="held",
            reason="initiative_not_delivery_ready",
            emitted_delivery=None,
            consumed_pending=dict(pending),
        )
    if not bool(output_verdict.get("passed")) or not reply_text:
        return ControlledProactiveDeliveryResult(
            status="held",
            reason="output_verdict_not_sendable",
            emitted_delivery=None,
            consumed_pending=dict(pending),
        )

    emitted_at = (
        datetime.fromtimestamp(now_ts, tz=UTC).isoformat()
        if now_ts is not None
        else datetime.now(UTC).isoformat()
    )
    response_metadata = dict(response_plan.get("metadata") or {})
    selected_candidate = dict(initiative_verdict.get("selected_candidate") or {})
    emitted_delivery = {
        "schema_version": "mvp12.controlled_delivery_record.v1",
        "session_id": session_id,
        "emitted_at": emitted_at,
        "delivery_mode": delivery_mode,
        "transport_source": transport_source,
        "delivery_status": "artifact_emitted",
        "reply_text": reply_text,
        "text_length": len(reply_text),
        "delivery_kind": output_verdict.get("delivery_kind") or response_plan.get("delivery_kind") or "chat",
        "reply_authority": output_verdict.get("applied_authority") or response_plan.get("reply_authority"),
        "reply_origin": output_verdict.get("reply_origin") or response_metadata.get("reply_origin"),
        "authority_source": response_plan.get("authority_source"),
        "initiative_mode": response_metadata.get("initiative_mode"),
        "initiative_candidate_id": response_metadata.get("initiative_candidate_id") or selected_candidate.get("candidate_id"),
        "initiative_source_cycle": response_metadata.get("initiative_source_cycle") or selected_candidate.get("source_cycle"),
        "initiative_source_hash": response_metadata.get("initiative_source_hash") or selected_candidate.get("source_candidate_hash"),
        "initiative_score": response_metadata.get("initiative_score") or selected_candidate.get("initiative_score"),
        "pending_created_at": pending.get("created_at"),
        "idle_seconds": pending.get("idle_seconds"),
    }

    consumed_pending = dict(pending)
    consumed_pending["delivery_status"] = "artifact_emitted"
    consumed_pending["consumed_at"] = emitted_at
    consumed_pending["emitted_delivery"] = dict(emitted_delivery)

    if hasattr(state, "record"):
        state.record(
            "proactive_followup_delivery",
            {
                "status": "artifact_emitted",
                "reply_origin": emitted_delivery.get("reply_origin"),
                "reply_authority": emitted_delivery.get("reply_authority"),
                "initiative_candidate_id": emitted_delivery.get("initiative_candidate_id"),
                "text_preview": reply_text[:120],
            },
        )
    if hasattr(state, "clear_pending_proactive_followup"):
        state.clear_pending_proactive_followup()

    return ControlledProactiveDeliveryResult(
        status="artifact_emitted",
        reason="ok",
        emitted_delivery=emitted_delivery,
        consumed_pending=consumed_pending,
    )
