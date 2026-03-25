"""
Test: Cycle Consolidation

验证 cycle 可重入 / 可强化。
"""

import pytest
from datetime import datetime

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def test_repeated_pattern_creates_cycle():
    """反复相似事件应该创建 cycle candidate。"""
    state = ProtoSelfState.empty()

    # 处理第一个事件
    event1 = KernelEvent(
        event_id="repeat-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="greeting",
    )
    output1 = process_event(state, event1)

    # 应该创建 candidate（cycle_delta 在 trace_payload 中）
    cycle_delta = output1.trace_payload.get("cycle_delta", {})
    assert cycle_delta.get("op") == "candidate"
    assert cycle_delta.get("cycle_id") is not None


def test_repeated_pattern_strengthens_same_cycle():
    """反复相似事件应该强化同一个 cycle_id。"""
    state = ProtoSelfState.empty()
    cycle_ids = set()

    # 处理多个相似事件
    for i in range(3):
        event = KernelEvent(
            event_id=f"repeat-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="greeting",
        )
        output = process_event(state, event)
        cycle_delta = output.trace_payload.get("cycle_delta", {})
        if cycle_delta.get("cycle_id"):
            cycle_ids.add(cycle_delta.get("cycle_id"))

    # 所有 cycle_id 应该相同
    assert len(cycle_ids) == 1

    # 最后一次应该是 strengthen
    assert cycle_delta.get("op") == "strengthen"


def test_different_patterns_create_different_cycles():
    """不同模式应该创建不同的 cycle。"""
    state = ProtoSelfState.empty()
    cycle_ids = set()

    # 处理不同类型的事件
    event_types = ["user_message", "tool_result", "system_event"]
    for i, event_type in enumerate(event_types):
        event = KernelEvent(
            event_id=f"different-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type=event_type,
        )
        output = process_event(state, event)
        cycle_delta = output.trace_payload.get("cycle_delta", {})
        if cycle_delta.get("cycle_id"):
            cycle_ids.add(cycle_delta.get("cycle_id"))

    # 应该有多个不同的 cycle_id
    assert len(cycle_ids) > 1


def test_cycle_promotion():
    """满足条件的 cycle 应该晋升。"""
    state = ProtoSelfState.empty()

    # 处理多个相似事件以达到晋升门槛（strength > 0.5 且 hits > 3）
    # 每次增加 0.1 strength，需要 6 次以上
    for i in range(7):
        event = KernelEvent(
            event_id=f"promote-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="greeting",
        )
        output = process_event(state, event)

    # 检查 cycle 是否晋升
    cycle_delta = output.trace_payload.get("cycle_delta", {})
    cycle_id = cycle_delta.get("cycle_id")
    if cycle_id and cycle_id in state.cycle_store.signatures:
        cycle = state.cycle_store.signatures[cycle_id]
        # 应该已经晋升（strength > 0.5 且 hits > 3）
        assert cycle.promoted is True
        assert cycle.hits > 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
