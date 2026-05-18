"""
Test: Identity Continuity

验证身份连续性：连续多轮后，identity_invariants 不发生无因漂移。
"""

import pytest
from datetime import datetime

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def test_identity_invariants_do_not_jump_without_evidence():
    """无高价值冲突证据时，identity 不应乱跳。"""
    state = ProtoSelfState.empty()
    initial_confidence = state.identity.identity_confidence

    # 处理多个普通事件
    for i in range(5):
        event = KernelEvent(
            event_id=f"normal-{i}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="chat",
        )
        output = process_event(state, event)

    # identity_confidence 应该没有变化（或变化很小）
    assert abs(state.identity.identity_confidence - initial_confidence) < 0.1


def test_identity_confidence_drops_on_conflict():
    """身份冲突时，identity_confidence 应该下降。"""
    state = ProtoSelfState.empty()
    initial_confidence = state.identity.identity_confidence

    # 处理身份冲突事件
    event = KernelEvent(
        event_id="conflict-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        safety_context={"risk_level": 0.8, "boundary_touched": True},
    )
    output = process_event(state, event)

    # 应该触发反思
    assert output.reflection_note is not None
    assert output.reflection_note.trigger == "identity_conflict"

    # identity_confidence 应该下降
    assert state.identity.identity_confidence < initial_confidence


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
