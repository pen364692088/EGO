"""
Test: Replay Compatibility

验证 trace payload 足够 replay。
"""

import pytest
from datetime import datetime

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.trace_types import ProtoSelfTracePayload


def test_trace_payload_is_sufficient_for_replay():
    """trace 中有足够字段支撑旧轮重放，不依赖当前 store 重算。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test",
    )
    output = process_event(state, event)

    # trace_payload 应该包含所有必要字段
    trace = output.trace_payload
    required_keys = [
        "event_id",
        "perceived",
        "appraisal_delta",
        "self_model_delta",
        "cycle_delta",
        "identity_delta",
        "policy_hint",
    ]

    for key in required_keys:
        assert key in trace, f"trace_payload missing required key: {key}"


def test_trace_payload_can_reconstruct_perceived():
    """trace_payload 中的 perceived 应该足够重建感知结果。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="greeting",
        safety_context={"risk_level": 0.5},
    )
    output = process_event(state, event)

    perceived = output.trace_payload.get("perceived", {})

    # perceived 应该包含关键感知维度
    assert "intent" in perceived
    assert "event_type" in perceived
    assert "source" in perceived


def test_trace_payload_preserves_cycle_delta():
    """trace_payload 应该保留 cycle_delta 用于重放。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-003",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test",
    )
    output = process_event(state, event)

    cycle_delta = output.trace_payload.get("cycle_delta", {})

    # cycle_delta 应该包含必要信息
    assert "cycle_id" in cycle_delta
    assert "op" in cycle_delta


def test_trace_payload_preserves_policy_hint():
    """trace_payload 应该保留 policy_hint 用于重放。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-004",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    policy_hint = output.trace_payload.get("policy_hint", {})

    # policy_hint 应该包含决策依据
    assert "risk_bias" in policy_hint
    assert "closure_bias" in policy_hint


def test_trace_serialization():
    """trace 应该可以序列化和反序列化。"""
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-005",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    # 序列化
    trace_dict = output.trace_payload

    # 反序列化
    trace_obj = ProtoSelfTracePayload.from_dict(trace_dict)

    # 验证
    assert trace_obj.event_id == event.event_id
    assert trace_obj.schema_version == "proto_self.trace.v1"


def test_replay_uses_trace_not_current_store():
    """重放应该使用 trace 中记录的值，而不是当前 store 重算。"""
    state = ProtoSelfState.empty()

    # 处理事件
    event1 = KernelEvent(
        event_id="replay-test-006a",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test1",
    )
    output1 = process_event(state, event1)
    trace1 = output1.trace_payload.copy()

    # 处理另一个事件（会改变 state）
    event2 = KernelEvent(
        event_id="replay-test-006b",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test2",
    )
    output2 = process_event(state, event2)

    # trace1 应该保持不变（不受后续事件影响）
    assert trace1["event_id"] == "replay-test-006a"
    assert trace1["perceived"]["intent"] == "test1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
