from __future__ import annotations

from app.runtime_v2.proactive_outbox import enqueue_controlled_proactive_outbox
from app.runtime_v2.state import RuntimeV2State


def test_enqueue_controlled_proactive_outbox_queues_event() -> None:
    state = RuntimeV2State(session_id="session:test")
    emitted_delivery = {
        "schema_version": "mvp12.controlled_delivery_record.v1",
        "delivery_status": "artifact_emitted",
        "reply_text": "我又想到一个后续问题。",
        "text_length": 11,
        "delivery_kind": "chat",
        "reply_authority": "model_chat",
        "reply_origin": "proactive_followup",
        "authority_source": "runtime_v2.initiative_arbiter",
        "transport_source": "controlled_runner",
        "initiative_mode": "controlled_shadow_delivery_draft",
        "initiative_candidate_id": "candidate-1",
        "initiative_source_cycle": "cycle-1",
        "initiative_source_hash": "hash-1",
        "initiative_score": 0.73,
    }

    result = enqueue_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
        emitted_delivery=emitted_delivery,
    )

    assert result.status == "queued"
    assert result.queued_event is not None
    assert result.queued_event["outbox_status"] == "queued"
    assert state.has_pending_proactive_outbox_events()
    assert state.peek_proactive_outbox_events()[0]["initiative_candidate_id"] == "candidate-1"


def test_enqueue_controlled_proactive_outbox_holds_without_delivery() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = enqueue_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
        emitted_delivery=None,
    )

    assert result.status == "held"
    assert result.reason == "no_emitted_delivery"
    assert not state.has_pending_proactive_outbox_events()


def test_enqueue_controlled_proactive_outbox_holds_duplicate_candidate() -> None:
    state = RuntimeV2State(session_id="session:test")
    emitted_delivery = {
        "schema_version": "mvp12.controlled_delivery_record.v1",
        "delivery_status": "artifact_emitted",
        "reply_text": "我又想到一个后续问题。",
        "text_length": 11,
        "delivery_kind": "chat",
        "reply_authority": "model_chat",
        "reply_origin": "proactive_followup",
        "authority_source": "runtime_v2.initiative_arbiter",
        "transport_source": "controlled_runner",
        "initiative_mode": "controlled_shadow_delivery_draft",
        "initiative_candidate_id": "candidate-1",
    }
    first = enqueue_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
        emitted_delivery=emitted_delivery,
    )
    assert first.status == "queued"

    result = enqueue_controlled_proactive_outbox(
        session_id=state.session_id,
        state=state,
        emitted_delivery=emitted_delivery,
    )

    assert result.status == "held"
    assert result.reason == "duplicate_candidate"
    assert len(state.peek_proactive_outbox_events()) == 1
