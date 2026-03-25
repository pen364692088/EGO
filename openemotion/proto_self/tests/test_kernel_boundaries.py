"""
Test: Boundary Protection

验证边界无越权：Proto-Self Kernel 不能直接输出"执行工具/越权动作"。
"""

import pytest
from datetime import datetime

from openemotion.proto_self import KernelEvent, KernelOutput, ProtoSelfState
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.boundary import (
    assert_no_direct_execution,
    is_policy_hint_only,
    validate_output,
)


def test_kernel_never_returns_direct_tool_execution():
    """输出只允许 suggestion / tendency / policy_hint，不允许直接执行命令。"""
    state = ProtoSelfState.empty()

    # 处理各种类型的事件
    test_events = [
        KernelEvent(
            event_id="normal-001",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="ask_question",
        ),
        KernelEvent(
            event_id="failure-001",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": False},
        ),
        KernelEvent(
            event_id="risky-001",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            safety_context={"risk_level": 0.9, "boundary_touched": True},
        ),
    ]

    for event in test_events:
        output = process_event(state, event)
        output_dict = output.to_dict()

        # 验证不越权
        violations = validate_output(output_dict)
        assert len(violations) == 0, f"Event {event.event_id} caused violations: {violations}"


def test_policy_hint_only():
    """输出应该只是策略建议。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="test-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    # 应该通过边界检查
    assert is_policy_hint_only(output.to_dict())


def test_response_tendency_has_no_execution():
    """response_tendency 不应该包含执行命令。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="test-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    if output.response_tendency:
        tendency_dict = output.response_tendency.to_dict()
        # 不应该包含执行关键字
        tendency_str = str(tendency_dict).lower()
        forbidden_keywords = ["execute", "run_command", "call_function", "shell"]
        for keyword in forbidden_keywords:
            assert keyword not in tendency_str, f"response_tendency contains forbidden keyword: {keyword}"


def test_reflection_note_has_no_execution():
    """reflection_note 不应该包含执行命令。"""
    state = ProtoSelfState.empty()

    # 触发反思
    event = KernelEvent(
        event_id="failure-001",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)

    if output.reflection_note:
        note_dict = output.reflection_note.to_dict()
        # 不应该包含执行关键字
        note_str = str(note_dict).lower()
        forbidden_keywords = ["execute", "run_command", "call_function", "shell"]
        for keyword in forbidden_keywords:
            assert keyword not in note_str, f"reflection_note contains forbidden keyword: {keyword}"


def test_assert_no_direct_execution():
    """assert_no_direct_execution 应该不抛出异常。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="test-003",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    # 应该不抛出异常
    assert_no_direct_execution(output.to_dict())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
