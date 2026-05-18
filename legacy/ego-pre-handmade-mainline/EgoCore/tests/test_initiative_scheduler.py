from __future__ import annotations

from app.openemotion_adapter import ProtoSelfAdapter
from app.runtime_v2.initiative_scheduler import run_controlled_idle_scheduler
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.runtime_v2.state import RuntimeV2State


def _state_with_chat() -> RuntimeV2State:
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_subject_profile": "seed_v0_2",
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "parser_source": "chat_default",
        "primary_intent": "chat",
    }
    state.prepare_chat_turn(user_text="我觉得是有了OS的操作员的感觉。", chat_act="light_chitchat")
    state.finalize_chat_turn(
        assistant_reply="这个比喻很妙——不是系统自己在跑，而是有人在\"用\"它。",
        chat_act="light_chitchat",
    )
    return state


def test_controlled_idle_scheduler_creates_pending_followup() -> None:
    state = _state_with_chat()
    proto_self_runtime = RuntimeV2ProtoSelfRuntime(adapter=ProtoSelfAdapter())
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_controlled_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=proto_self_runtime,
        now_ts=base_ts + 900.0,
    )

    assert result.status == "pending_created"
    assert state.get_pending_proactive_followup() is not None
    assert state.get_pending_proactive_followup()["delivery_status"] == "pending"


def test_controlled_idle_scheduler_holds_when_window_too_short() -> None:
    state = _state_with_chat()
    proto_self_runtime = RuntimeV2ProtoSelfRuntime(adapter=ProtoSelfAdapter())
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_controlled_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=proto_self_runtime,
        now_ts=base_ts + 60.0,
    )

    assert result.status == "held"
    assert result.reason == "idle_window_too_short"
    assert state.get_pending_proactive_followup() is None


def test_controlled_idle_scheduler_holds_when_pending_exists() -> None:
    state = _state_with_chat()
    proto_self_runtime = RuntimeV2ProtoSelfRuntime(adapter=ProtoSelfAdapter())
    state.set_pending_proactive_followup(
        {
            "schema_version": "mvp12.pending_proactive_followup.v1",
            "delivery_status": "pending",
        }
    )

    result = run_controlled_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=proto_self_runtime,
        now_ts=(state.get_chat_state().last_activity_at or 0.0) + 900.0,
    )

    assert result.status == "held"
    assert result.reason == "pending_followup_exists"
