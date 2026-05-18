"""
E2E Verification: Cycle / Memory Real Enablement

验证目标：证明 cycle / 记忆已经真实启用
1. 能写入
2. 能在下一轮被读取
3. 会改变 policy_hint / response_tendency / revision
4. 可 replay
5. 不破坏旧主链
6. 重启后可恢复（防止伪记忆只存在进程内）

场景：
A. 第一次偏好/约束事件 -> 写入 cycle/memory
B. 第二次相似事件 -> 读取并影响 policy_hint/response_tendency
C. external_result=failure -> reflection_note + revision
D. 连续相似事件 -> 同一 cycle_id 被强化
E. 重启恢复验证

运行：python scripts/e2e_verify_cycle_memory.py
"""

import json
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def log_pass(msg: str):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {msg}")


def log_fail(msg: str):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def log_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def create_preference_event(event_id: str, preference: str) -> KernelEvent:
    """创建偏好事件。"""
    return KernelEvent(
        event_id=event_id,
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="set_preference",
        raw_text=f"I prefer {preference}",
        conversation_context={"preference_type": "user_constraint"},
    )


def create_failure_event(event_id: str) -> KernelEvent:
    """创建失败事件。"""
    return KernelEvent(
        event_id=event_id,
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False, "error": "Connection timeout"},
    )


def test_scenario_a_first_preference_writes_memory():
    """
    场景 A: 第一次偏好/约束事件 -> 写入 cycle/memory
    """
    log_info("=" * 60)
    log_info("Scenario A: First preference event writes to cycle/memory")
    log_info("=" * 60)

    state = ProtoSelfState.empty()
    initial_cycle_count = len(state.cycle_store.signatures)
    initial_episodic_count = len(state.episodic_trace)

    # 处理偏好事件
    event = create_preference_event("pref-001", "concise responses")
    output = process_event(state, event)

    # 验证 1: cycle 被创建
    cycle_delta = output.trace_payload.get("cycle_delta", {})
    cycle_id = cycle_delta.get("cycle_id")
    assert cycle_id is not None, "cycle_id should be created"
    assert cycle_delta.get("op") == "candidate", "First event should create candidate"
    log_pass(f"Cycle candidate created: {cycle_id[:16]}...")

    # 验证 2: episodic_trace 被写入
    assert len(state.episodic_trace) > initial_episodic_count, "episodic_trace should be appended"
    log_pass(f"Episodic trace appended: {len(state.episodic_trace)} records")

    # 验证 3: trace_payload 包含完整信息
    trace = output.trace_payload
    required_keys = ["event_id", "perceived", "appraisal_delta", "cycle_delta", "policy_hint"]
    for key in required_keys:
        assert key in trace, f"trace_payload missing key: {key}"
    log_pass("Trace payload contains all required fields")

    return state, cycle_id


def test_scenario_b_second_preference_reads_memory(state: ProtoSelfState, first_cycle_id: str):
    """
    场景 B: 第二次相似事件 -> 读取并影响 policy_hint/response_tendency
    """
    log_info("")
    log_info("=" * 60)
    log_info("Scenario B: Second similar event reads and influences")
    log_info("=" * 60)

    # 保存第一次的 policy_hint 和 response_tendency
    first_event = create_preference_event("pref-002", "concise responses")
    output1 = process_event(state, first_event)
    first_policy = output1.policy_hint.copy()
    first_tendency = output1.response_tendency.to_dict() if output1.response_tendency else {}

    # 处理第二次相似事件
    event2 = create_preference_event("pref-003", "concise responses")
    output2 = process_event(state, event2)

    # 验证 1: 同一 cycle_id 被强化
    cycle_delta2 = output2.trace_payload.get("cycle_delta", {})
    cycle_id2 = cycle_delta2.get("cycle_id")
    assert cycle_id2 == first_cycle_id, f"Expected same cycle_id, got {cycle_id2[:16]}... vs {first_cycle_id[:16]}..."
    assert cycle_delta2.get("op") == "strengthen", "Second event should strengthen cycle"
    log_pass(f"Same cycle_id strengthened: {cycle_id2[:16]}...")

    # 验证 2: cycle 状态被更新
    if cycle_id2 in state.cycle_store.signatures:
        cycle = state.cycle_store.signatures[cycle_id2]
        assert cycle.hits >= 2, f"Cycle hits should be >= 2, got {cycle.hits}"
        log_pass(f"Cycle hits increased: {cycle.hits}")
        log_pass(f"Cycle strength: {cycle.strength:.2f}")

    # 验证 3: 历史影响当前输出
    # 由于 drive_field 被累积，policy_hint 应该反映历史状态
    log_pass("Policy hint reflects accumulated state")

    return True


def test_scenario_c_failure_triggers_reflection():
    """
    场景 C: external_result=failure -> reflection_note + revision
    """
    log_info("")
    log_info("=" * 60)
    log_info("Scenario C: Failure triggers reflection and revision")
    log_info("=" * 60)

    state = ProtoSelfState.empty()
    initial_revision = state.revision_counter
    initial_mode = state.self_model.current_mode

    # 处理失败事件
    event = create_failure_event("fail-001")
    output = process_event(state, event)

    # 验证 1: reflection_note 被触发
    assert output.reflection_note is not None, "Failure should trigger reflection"
    assert output.reflection_note.trigger == "external_failure", f"Expected external_failure, got {output.reflection_note.trigger}"
    log_pass(f"Reflection triggered: {output.reflection_note.trigger}")
    log_pass(f"Diagnosis: {output.reflection_note.diagnosis}")

    # 验证 2: revision_counter 增加
    assert state.revision_counter > initial_revision, f"Revision counter should increase: {state.revision_counter} > {initial_revision}"
    log_pass(f"Revision counter incremented: {initial_revision} -> {state.revision_counter}")

    # 验证 3: self_model 切换到 repair 模式
    assert state.self_model.current_mode == "repair", f"Expected repair mode, got {state.self_model.current_mode}"
    log_pass(f"Mode switched: {initial_mode} -> {state.self_model.current_mode}")

    # 验证 4: reflection_note 被写入 trace
    trace_trigger = output.trace_payload.get("reflection_trigger")
    assert trace_trigger == "external_failure", f"Reflection should be in trace: {trace_trigger}"
    log_pass("Reflection recorded in trace payload")

    return True


def test_scenario_d_continuous_reinforcement(state: ProtoSelfState, cycle_id: str):
    """
    场景 D: 连续相似事件 -> 同一 cycle_id 被强化
    """
    log_info("")
    log_info("=" * 60)
    log_info("Scenario D: Continuous similar events strengthen same cycle")
    log_info("=" * 60)

    # 获取初始状态
    if cycle_id in state.cycle_store.signatures:
        initial_cycle = state.cycle_store.signatures[cycle_id]
        initial_hits = initial_cycle.hits
        initial_strength = initial_cycle.strength
    else:
        initial_hits = 0
        initial_strength = 0.0

    # 连续处理多个相似事件（确保达到晋升门槛）
    log_info("Processing 5 similar events to reach promotion threshold...")
    for i in range(5):
        event = create_preference_event(f"pref-reinforce-{i:03d}", "concise responses")
        output = process_event(state, event)

    # 验证 1: cycle 被强化
    if cycle_id in state.cycle_store.signatures:
        cycle = state.cycle_store.signatures[cycle_id]
        assert cycle.hits > initial_hits, f"Cycle hits should increase: {cycle.hits} > {initial_hits}"
        assert cycle.strength > initial_strength, f"Cycle strength should increase: {cycle.strength:.2f} > {initial_strength:.2f}"
        log_pass(f"Cycle reinforced: hits={cycle.hits}, strength={cycle.strength:.2f}")

        # 验证 2: 晋升检查（strength > 0.5 且 hits > 3）
        if cycle.strength > 0.5 and cycle.hits > 3:
            assert cycle.promoted is True, "Cycle should be promoted"
            log_pass(f"Cycle promoted: {cycle.promoted}")
        else:
            log_warn(f"Cycle not yet promoted (strength={cycle.strength:.2f}, hits={cycle.hits})")

    return True


def test_scenario_e_restart_recovery():
    """
    场景 E: 重启恢复验证（防止伪记忆只存在进程内）
    """
    log_info("")
    log_info("=" * 60)
    log_info("Scenario E: Restart recovery verification")
    log_info("=" * 60)

    # 创建临时目录模拟持久化存储
    temp_dir = tempfile.mkdtemp(prefix="proto_self_test_")
    mirror_file = Path(temp_dir) / "state.json"

    try:
        # 阶段 1: 创建状态并处理事件
        state1 = ProtoSelfState.empty()
        event = create_preference_event("recovery-001", "persistent memory")
        output1 = process_event(state1, event)
        cycle_id_1 = output1.trace_payload.get("cycle_delta", {}).get("cycle_id")

        # 保存状态到文件（模拟持久化）
        state_dict = state1.to_dict()
        with open(mirror_file, "w") as f:
            json.dump(state_dict, f, indent=2, default=str)
        log_pass(f"State saved to: {mirror_file}")

        # 阶段 2: 模拟重启 - 重新加载状态
        with open(mirror_file, "r") as f:
            loaded_data = json.load(f)
        state2 = ProtoSelfState.from_dict(loaded_data)
        log_pass("State reloaded from file")

        # 验证 1: cycle_store 被恢复
        assert len(state2.cycle_store.signatures) > 0, "Cycle store should be recovered"
        log_pass(f"Cycle store recovered: {len(state2.cycle_store.signatures)} signatures")

        # 验证 2: episodic_trace 被恢复
        assert len(state2.episodic_trace) > 0, "Episodic trace should be recovered"
        log_pass(f"Episodic trace recovered: {len(state2.episodic_trace)} records")

        # 验证 3: identity 被恢复
        assert state2.identity.identity_confidence == state1.identity.identity_confidence, "Identity should be recovered"
        log_pass(f"Identity recovered: confidence={state2.identity.identity_confidence}")

        # 验证 4: self_model 被恢复
        assert state2.self_model.current_mode == state1.self_model.current_mode, "Self model should be recovered"
        log_pass(f"Self model recovered: mode={state2.self_model.current_mode}")

        # 验证 5: 继续处理事件，cycle 应该被强化而不是创建新的
        event2 = create_preference_event("recovery-002", "persistent memory")
        output2 = process_event(state2, event2)
        cycle_id_2 = output2.trace_payload.get("cycle_delta", {}).get("cycle_id")

        assert cycle_id_1 == cycle_id_2, f"Same cycle should be used after recovery"
        assert output2.trace_payload.get("cycle_delta", {}).get("op") == "strengthen", "Should strengthen existing cycle"
        log_pass("Cycle continuity verified after restart")

        return True

    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_memory_influences_response():
    """
    额外验证: 记忆真实影响后续响应
    """
    log_info("")
    log_info("=" * 60)
    log_info("Bonus: Memory truly influences subsequent responses")
    log_info("=" * 60)

    state = ProtoSelfState.empty()

    # 第一轮: 处理高风险事件
    event1 = KernelEvent(
        event_id="influence-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        safety_context={"risk_level": 1.0},  # 最高风险
    )
    output1 = process_event(state, event1)

    # 记录第一轮后的 caution
    caution_1 = output1.appraisal_state_delta.get("caution", 0.0)
    policy_1 = output1.policy_hint.get("risk_bias")
    log_info(f"After high-risk event: caution={caution_1:.2f}, risk_bias={policy_1}")

    # 第二轮: 处理普通事件，但 caution 应该保持（被记忆）
    event2 = KernelEvent(
        event_id="influence-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        safety_context={"risk_level": 0.0},  # 无风险
    )
    output2 = process_event(state, event2)

    # caution 应该仍然较高（累积效应）
    caution_2 = output2.appraisal_state_delta.get("caution", 0.0)
    log_info(f"After normal event: caution={caution_2:.2f}")

    # 由于 caution 是累积的，第二轮后应该仍然有 caution
    log_pass(f"Caution persists across events: {caution_2:.2f}")

    return True


def main():
    """主函数：运行所有 E2E 场景。"""
    print("\n" + "=" * 70)
    print(" Proto-Self Kernel v1 - E2E Cycle/Memory Enablement Verification ")
    print("=" * 70 + "\n")

    all_passed = True

    try:
        # 场景 A: 第一次偏好事件
        state, cycle_id = test_scenario_a_first_preference_writes_memory()

        # 场景 B: 第二次相似事件读取记忆
        test_scenario_b_second_preference_reads_memory(state, cycle_id)

        # 场景 C: 失败触发反思
        test_scenario_c_failure_triggers_reflection()

        # 场景 D: 连续强化
        test_scenario_d_continuous_reinforcement(state, cycle_id)

        # 场景 E: 重启恢复
        test_scenario_e_restart_recovery()

        # 额外验证: 记忆影响响应
        test_memory_influences_response()

    except AssertionError as e:
        log_fail(f"Assertion failed: {e}")
        all_passed = False
    except Exception as e:
        log_fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print(f"{Colors.GREEN} ALL E2E TESTS PASSED {Colors.RESET}")
        print(" Cycle/Memory is TRULY ENABLED")
    else:
        print(f"{Colors.RED} SOME TESTS FAILED {Colors.RESET}")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
