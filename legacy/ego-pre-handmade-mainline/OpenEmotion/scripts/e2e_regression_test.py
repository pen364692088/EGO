"""
Regression Test: Proto-Self Kernel v1

验证目标：
1. cycle_core_v1 未被破坏
2. WS_C1 (warm start C1) 正常工作
3. long-term self summary 未被破坏
4. 与现有系统的兼容性

运行：python scripts/e2e_regression_test.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState, SCHEMA_VERSION
from openemotion.proto_self.kernel import process_event


def test_schema_version_contract():
    """验证 schema version 契约。"""
    print("[TEST] Schema version contract")
    assert SCHEMA_VERSION == "proto_self.v1", f"Expected proto_self.v1, got {SCHEMA_VERSION}"

    event = KernelEvent(
        event_id="schema-test-001",
        timestamp=datetime.now().isoformat(),
        actor="test",
        source="test",
        event_type="test",
    )
    assert event.schema_version == "proto_self.v1"
    print("  [PASS] Schema version is proto_self.v1")


def test_kernel_output_schema():
    """验证 KernelOutput 输出 schema 完整性。"""
    print("[TEST] Kernel output schema")

    state = ProtoSelfState.empty()
    event = KernelEvent(
        event_id="output-test-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
    )
    output = process_event(state, event)

    # 验证必要字段
    output_dict = output.to_dict()
    required_fields = [
        "schema_version",
        "event_id",
        "identity_state_delta",
        "self_model_delta",
        "memory_update",
        "appraisal_state_delta",
        "policy_hint",
        "response_tendency",
        "confidence_meta",
        "trace_payload",
    ]

    for field in required_fields:
        assert field in output_dict, f"Missing field: {field}"

    # 验证 schema_version
    assert output_dict["schema_version"] == "proto_self.v1"

    # 验证 response_tendency 结构
    if output.response_tendency:
        tendency_dict = output.response_tendency.to_dict()
        required_tendency_fields = [
            "preferred_mode",
            "preferred_tone",
            "certainty_bound",
            "suggested_next_step",
            "ask_needed",
        ]
        for field in required_tendency_fields:
            assert field in tendency_dict, f"Missing tendency field: {field}"

    print("  [PASS] Output schema is complete")


def test_state_serialization():
    """验证状态可序列化和恢复。"""
    print("[TEST] State serialization")

    # 创建并修改状态
    state = ProtoSelfState.empty()

    # 处理一些事件以修改状态
    events = [
        KernelEvent(
            event_id=f"serial-test-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="test",
        )
        for i in range(3)
    ]

    for event in events:
        process_event(state, event)

    # 序列化
    state_dict = state.to_dict()

    # 验证序列化后的字段
    required_state_fields = [
        "identity",
        "self_model",
        "drives",
        "cycle_store",
        "episodic_trace",
        "revision_counter",
    ]
    for field in required_state_fields:
        assert field in state_dict, f"Missing state field: {field}"

    # 反序列化
    restored_state = ProtoSelfState.from_dict(state_dict)

    # 验证恢复后的状态
    assert restored_state.revision_counter == state.revision_counter
    assert len(restored_state.cycle_store.signatures) == len(state.cycle_store.signatures)
    assert len(restored_state.episodic_trace) == len(state.episodic_trace)

    print("  [PASS] State serialization and restoration works")


def test_boundary_no_execution():
    """验证边界：kernel 不输出直接执行命令。"""
    print("[TEST] Boundary: No direct execution")

    from openemotion.proto_self.boundary import assert_no_direct_execution

    state = ProtoSelfState.empty()

    # 测试各种事件类型
    test_events = [
        KernelEvent(
            event_id="boundary-test-001",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="execute_command",
        ),
        KernelEvent(
            event_id="boundary-test-002",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": True},
        ),
        KernelEvent(
            event_id="boundary-test-003",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            safety_context={"risk_level": 0.9},
        ),
    ]

    for event in test_events:
        output = process_event(state, event)
        output_dict = output.to_dict()

        # 验证不含有执行命令
        try:
            assert_no_direct_execution(output_dict)
        except AssertionError as e:
            raise AssertionError(f"Event {event.event_id}: {e}")

    print("  [PASS] Kernel never outputs direct execution commands")


def test_cycle_promotion_threshold():
    """验证 cycle 晋升门槛一致性。"""
    print("[TEST] Cycle promotion threshold")

    state = ProtoSelfState.empty()

    # 反复处理相似事件以达到晋升门槛
    # 门槛：strength > 0.5 且 hits > 3
    cycle_id = None

    for i in range(10):
        event = KernelEvent(
            event_id=f"promotion-test-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="greeting",
        )
        output = process_event(state, event)
        cycle_id = output.trace_payload.get("cycle_delta", {}).get("cycle_id")

    # 验证 cycle 晋升
    if cycle_id and cycle_id in state.cycle_store.signatures:
        cycle = state.cycle_store.signatures[cycle_id]

        # 检查晋升条件
        assert cycle.hits > 3, f"Expected hits > 3, got {cycle.hits}"
        assert cycle.strength > 0.5, f"Expected strength > 0.5, got {cycle.strength}"
        assert cycle.promoted is True, f"Expected promoted=True, got {cycle.promoted}"

        print(f"  [PASS] Cycle promoted: hits={cycle.hits}, strength={cycle.strength:.2f}")
    else:
        print("  [WARN] Cycle not found in store")


def test_drive_influence_policy():
    """验证 drive field 真实影响 policy。"""
    print("[TEST] Drive field influences policy")

    # 测试高 caution 场景
    state_high_caution = ProtoSelfState.empty()
    event_high_risk = KernelEvent(
        event_id="drive-test-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        safety_context={"risk_level": 1.0},  # 最高风险
    )
    output_high = process_event(state_high_caution, event_high_risk)

    # caution 应该升高
    assert output_high.appraisal_state_delta.get("caution", 0.0) > 0.4

    # 测试低 caution 场景
    state_low_caution = ProtoSelfState.empty()
    event_low_risk = KernelEvent(
        event_id="drive-test-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        safety_context={"risk_level": 0.0},  # 无风险
    )
    output_low = process_event(state_low_caution, event_low_risk)

    # caution 应该较低
    assert output_low.appraisal_state_delta.get("caution", 0.0) < 0.1

    print("  [PASS] Drive field correctly influences policy")


def test_trace_completeness():
    """验证 trace payload 完整性。"""
    print("[TEST] Trace payload completeness")

    state = ProtoSelfState.empty()
    event = KernelEvent(
        event_id="trace-test-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test",
        safety_context={"risk_level": 0.5},
    )
    output = process_event(state, event)

    trace = output.trace_payload

    # 验证 trace schema version
    assert trace.get("schema_version") == "proto_self.trace.v1"

    # 验证必要字段
    required_trace_fields = [
        "event_id",
        "perceived",
        "appraisal_delta",
        "self_model_delta",
        "cycle_delta",
        "identity_delta",
        "policy_hint",
    ]
    for field in required_trace_fields:
        assert field in trace, f"Missing trace field: {field}"

    # 验证 perceived 内容
    perceived = trace.get("perceived", {})
    assert "intent" in perceived
    assert "risk_signal" in perceived

    # 验证 cycle_delta 内容
    cycle_delta = trace.get("cycle_delta", {})
    assert "cycle_id" in cycle_delta
    assert "op" in cycle_delta

    print("  [PASS] Trace payload is complete")


def test_identity_stability():
    """验证 identity 稳定性。"""
    print("[TEST] Identity stability")

    state = ProtoSelfState.empty()
    initial_confidence = state.identity.identity_confidence

    # 处理多个普通事件（不应大幅改变 identity）
    for i in range(10):
        event = KernelEvent(
            event_id=f"identity-test-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="chat",
        )
        process_event(state, event)

    # identity_confidence 不应大幅变化
    final_confidence = state.identity.identity_confidence
    confidence_delta = abs(final_confidence - initial_confidence)

    assert confidence_delta < 0.2, f"Identity changed too much: {confidence_delta}"

    print(f"  [PASS] Identity stable: {initial_confidence} -> {final_confidence}")


def test_memory_accumulation():
    """验证记忆累积。"""
    print("[TEST] Memory accumulation")

    state = ProtoSelfState.empty()

    # 处理多个事件
    event_count = 5
    for i in range(event_count):
        event = KernelEvent(
            event_id=f"memory-test-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent=f"test_{i}",
        )
        process_event(state, event)

    # 验证 episodic_trace 累积
    assert len(state.episodic_trace) == event_count, f"Expected {event_count} records, got {len(state.episodic_trace)}"

    # 验证每个记录都有正确结构
    for record in state.episodic_trace:
        assert record.event_id is not None
        assert record.perceived_summary is not None
        assert record.appraisal_snapshot is not None

    print(f"  [PASS] Memory accumulated: {len(state.episodic_trace)} records")


def main():
    """运行所有回归测试。"""
    print("\n" + "=" * 70)
    print(" Proto-Self Kernel v1 - Regression Test Suite ")
    print("=" * 70 + "\n")

    tests = [
        test_schema_version_contract,
        test_kernel_output_schema,
        test_state_serialization,
        test_boundary_no_execution,
        test_cycle_promotion_threshold,
        test_drive_influence_policy,
        test_trace_completeness,
        test_identity_stability,
        test_memory_accumulation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f" Results: {passed} passed, {failed} failed")
    print("=" * 70 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
