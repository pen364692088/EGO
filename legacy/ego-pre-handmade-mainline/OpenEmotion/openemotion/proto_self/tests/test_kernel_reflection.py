"""
Test: Reflection

验证 failure 触发 reflection 与 revision。
"""

import pytest
from datetime import datetime

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def test_failure_generates_reflection_note():
    """失败应该触发 reflection_note。"""
    state = ProtoSelfState.empty()

    # 处理失败事件
    event = KernelEvent(
        event_id="failure-001",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False, "error": "Connection timeout"},
    )
    output = process_event(state, event)

    # 应该触发反思
    assert output.reflection_note is not None
    assert output.reflection_note.trigger == "external_failure"
    assert output.reflection_note.promote_to_memory is True


def test_failure_increments_revision_counter():
    """失败应该增加 revision_counter。"""
    state = ProtoSelfState.empty()
    initial_counter = state.revision_counter

    # 处理失败事件
    event = KernelEvent(
        event_id="failure-002",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)

    # revision_counter 应该增加
    assert state.revision_counter == initial_counter + 1


def test_failure_changes_mode_to_repair():
    """失败应该将 mode 切换到 repair。"""
    state = ProtoSelfState.empty()

    # 处理失败事件
    event = KernelEvent(
        event_id="failure-003",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)

    # self_model 应该切换到 repair 模式
    assert output.self_model_delta.get("current_mode") == "repair"
    assert state.self_model.current_mode == "repair"


def test_success_does_not_trigger_reflection():
    """成功不应该触发 reflection。"""
    state = ProtoSelfState.empty()

    # 处理成功事件
    event = KernelEvent(
        event_id="success-001",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": True},
    )
    output = process_event(state, event)

    # 不应该触发反思
    assert output.reflection_note is None


def test_reflection_proposed_adjustment():
    """反思应该提出调整建议。"""
    state = ProtoSelfState.empty()

    # 处理失败事件
    event = KernelEvent(
        event_id="failure-004",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)

    # 应该有调整建议
    assert output.reflection_note.proposed_adjustment is not None
    assert "current_mode" in output.reflection_note.proposed_adjustment
    assert output.reflection_note.proposed_adjustment["current_mode"] == "repair"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
