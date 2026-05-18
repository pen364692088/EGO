from __future__ import annotations

from app.runtime_v2.proactive_outbox_drain import drain_controlled_proactive_outbox
from app.runtime_v2.state import RuntimeV2State


def test_drain_controlled_proactive_outbox_drains_queue() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.push_proactive_outbox_event(
        {
            "schema_version": "mvp12.proactive_outbox_event.v1",
            "initiative_candidate_id": "candidate-1",
            "outbox_lane": "host_proactive_outbox",
            "outbox_status": "queued",
            "reply_text": "我又想到一个后续问题。",
            "text_length": 11,
            "reply_authority": "model_chat",
            "reply_origin": "proactive_followup",
            "authority_source": "runtime_v2.initiative_arbiter",
        }
    )

    result = drain_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
    )

    assert result.status == "drained"
    assert len(result.drained_records) == 1
    assert result.drained_records[0]["transport_source"] == "simulated_outbox_drain"
    assert not state.has_pending_proactive_outbox_events()


def test_drain_controlled_proactive_outbox_holds_without_queue() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = drain_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
    )

    assert result.status == "held"
    assert result.reason == "no_pending_outbox_events"
