from __future__ import annotations

from app.memory.memory_manager import MemoryManager
from app.telegram_runtime_bridge import TelegramRuntimeBridge
from app.runtime_v2.state import RuntimeV2State


def _make_manager(tmp_path):
    return MemoryManager(
        db_path=tmp_path / "memory.db",
        memory_dir=tmp_path / "memory_store",
    )


def _make_bridge(manager):
    from app.memory.profile_memory import ProfileMemory

    return TelegramRuntimeBridge(
        profile_memory_factory=lambda scope: ProfileMemory(scope, manager=manager)
    )


def test_proactive_topic_permission_survives_new_command(tmp_path) -> None:
    manager = _make_manager(tmp_path)
    bridge = _make_bridge(manager)
    state = RuntimeV2State(session_id="telegram:dm:456")

    allow = bridge.inspect_ingress("以后你可以主动找我聊新的想法，不用每次都问我。", state)
    allow_context = bridge.build_ingress_context(allow, state)
    assert allow_context["proactive_topic_permission"] == "long_term_allow"

    state.increment_generation()

    ordinary = bridge.inspect_ingress("你好，我们继续聊。", state)
    ordinary_context = bridge.build_ingress_context(ordinary, state)
    assert ordinary_context["proactive_topic_permission"] == "long_term_allow"
    assert ordinary_context["outreach_aggression_mode"] == "high_exploration"
    assert ordinary_context["outreach_feedback_adaptation"] == "enabled"
    assert ordinary_context["quiet_state"] == "normal"


def test_proactive_topic_permission_survives_restart_with_same_memory_db(tmp_path) -> None:
    first_manager = _make_manager(tmp_path)
    first_bridge = _make_bridge(first_manager)
    state = RuntimeV2State(session_id="telegram:dm:456")

    allow = first_bridge.inspect_ingress("默认允许你主动来找我聊新的想法。", state)
    allow_context = first_bridge.build_ingress_context(allow, state)
    assert allow_context["proactive_topic_permission"] == "long_term_allow"

    restarted_manager = MemoryManager(
        db_path=tmp_path / "memory.db",
        memory_dir=tmp_path / "memory_store",
    )
    restarted_bridge = _make_bridge(restarted_manager)
    restarted_state = RuntimeV2State(session_id="telegram:dm:456")

    ordinary = restarted_bridge.inspect_ingress("我们换个话题继续聊。", restarted_state)
    ordinary_context = restarted_bridge.build_ingress_context(ordinary, restarted_state)
    assert ordinary_context["proactive_topic_permission"] == "long_term_allow"


def test_proactive_topic_permission_can_be_revoked(tmp_path) -> None:
    manager = _make_manager(tmp_path)
    bridge = _make_bridge(manager)
    state = RuntimeV2State(session_id="telegram:dm:456")

    bridge.build_ingress_context(
        bridge.inspect_ingress("以后你可以主动找我聊新的想法，不用每次都问我。", state),
        state,
    )
    revoke = bridge.inspect_ingress("以后不要主动来找我，先停掉这个。", state)
    revoke_context = bridge.build_ingress_context(revoke, state)

    assert revoke_context["proactive_topic_permission"] == "disabled"


def test_outreach_policy_reduce_pause_resume_are_durable_preferences(tmp_path) -> None:
    manager = _make_manager(tmp_path)
    bridge = _make_bridge(manager)
    state = RuntimeV2State(session_id="telegram:dm:456")

    allow_context = bridge.build_ingress_context(
        bridge.inspect_ingress("以后你可以主动找我聊新的想法，不用每次都问我。", state),
        state,
    )
    assert allow_context["quiet_state"] == "normal"

    reduced_context = bridge.build_ingress_context(
        bridge.inspect_ingress("降低频率，别太频繁。", state),
        state,
    )
    assert reduced_context["quiet_state"] == "reduced"
    assert reduced_context["feedback_signal"] == "explicit_reduce"

    paused_context = bridge.build_ingress_context(
        bridge.inspect_ingress("暂停一下，这几个小时先别打扰。", state),
        state,
    )
    assert paused_context["quiet_state"] == "paused"
    assert paused_context["feedback_signal"] == "explicit_pause"

    state.increment_generation()

    persisted = bridge.build_ingress_context(bridge.inspect_ingress("你好", state), state)
    assert persisted["quiet_state"] == "paused"

    resumed_context = bridge.build_ingress_context(
        bridge.inspect_ingress("恢复正常，可以继续主动找我。", state),
        state,
    )
    assert resumed_context["quiet_state"] == "normal"
    assert resumed_context["feedback_signal"] == "explicit_resume"
    assert resumed_context["proactive_topic_permission"] == "long_term_allow"
