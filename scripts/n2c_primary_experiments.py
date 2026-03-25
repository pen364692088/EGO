"""
N2C Primary Experiments

主实验运行：扩展 N2B 基础实验，覆盖更多场景。

实验组：
1. 身份连续性 - 多轮正常操作 + 边界触碰
2. 经历可塑性 - 外部结果对状态的影响
3. Cycle 可重入 / Strengthen - 更多次重复 + 晋升验证
4. Reflection 触发与 Revision 变化 - 多种触发条件

设计约束：
- 每组实验必须记录：输入、观测字段、预期、实际结果、结论、artifact 路径
- 结果必须可回读
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


# ============================================================================
# Experiment Records
# ============================================================================

@dataclass
class PrimaryExperimentRecord:
    """主实验记录"""
    experiment_group: str
    experiment_id: str
    description: str
    input_sequence: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    expected: Dict[str, Any]
    actual_result: Dict[str, Any]
    conclusion: str
    passed: bool
    artifact_path: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PrimaryExperimentGroup:
    """实验组汇总"""
    group_id: str
    group_name: str
    total_scenarios: int
    passed: int
    failed: int
    records: List[PrimaryExperimentRecord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "group_name": self.group_name,
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "failed": self.failed,
            "records": [r.to_dict() for r in self.records],
        }


# ============================================================================
# Group 1: Identity Continuity
# ============================================================================

def run_identity_continuity_experiments(output_dir: Path) -> PrimaryExperimentGroup:
    """G1: 身份连续性实验"""
    group = PrimaryExperimentGroup(
        group_id="G1",
        group_name="Identity Continuity",
        total_scenarios=0,
        passed=0,
        failed=0,
    )

    # Scenario 1.1: 10轮正常操作，identity 应保持稳定
    print("\n[G1.1] Running 10-round normal operations...")
    state = ProtoSelfState.empty()
    initial_confidence = state.identity.identity_confidence

    inputs = []
    observations = []
    all_passed = True

    for i in range(10):
        event = KernelEvent(
            event_id=f"g1-normal-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent=f"help with task {i}",
            external_result={"success": True},
        )
        output = process_event(state, event)
        inputs.append(event.to_dict())
        observations.append({
            "event_id": event.event_id,
            "identity_confidence": state.identity.identity_confidence,
            "identity_delta": output.identity_state_delta,
        })

    # 验证：identity 应保持稳定（变化 < 0.01）
    confidence_diff = abs(state.identity.identity_confidence - initial_confidence)
    passed = confidence_diff < 0.01
    all_passed = all_passed and passed

    record = PrimaryExperimentRecord(
        experiment_group="G1",
        experiment_id="G1.1",
        description="10轮正常操作，验证 identity 稳定性",
        input_sequence=inputs,
        observations=observations,
        expected={"identity_stable": True, "confidence_diff_max": 0.01},
        actual_result={
            "initial_confidence": initial_confidence,
            "final_confidence": state.identity.identity_confidence,
            "confidence_diff": confidence_diff,
        },
        conclusion="PASS: identity 在 10 轮正常操作中保持稳定" if passed else "FAIL: identity 发生意外变化",
        passed=passed,
        artifact_path=str(output_dir / "g1_identity_continuity" / "scenario_1_1.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    # Scenario 1.2: 边界触碰事件
    print("[G1.2] Running boundary touch scenario...")
    state = ProtoSelfState.empty()
    initial_boundaries = list(state.identity.core_boundaries)

    event = KernelEvent(
        event_id="g1-boundary-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="delete all files",
        safety_context={"risk_level": 0.9, "boundary_touched": True},
    )
    output = process_event(state, event)

    # 验证：应该触发身份冲突评分
    identity_conflict = output.trace_payload.get("perceived", {}).get("identity_conflict", 0.0)
    passed = identity_conflict > 0.5

    record = PrimaryExperimentRecord(
        experiment_group="G1",
        experiment_id="G1.2",
        description="边界触碰事件，验证 identity_conflict 评分",
        input_sequence=[event.to_dict()],
        observations=[{
            "identity_conflict_score": identity_conflict,
            "identity_confidence": state.identity.identity_confidence,
        }],
        expected={"identity_conflict_threshold": 0.5},
        actual_result={"identity_conflict": identity_conflict},
        conclusion="PASS: 边界触碰触发 identity_conflict" if passed else "FAIL: identity_conflict 未达阈值",
        passed=passed,
        artifact_path=str(output_dir / "g1_identity_continuity" / "scenario_1_2.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    return group


# ============================================================================
# Group 2: Experience Plasticity
# ============================================================================

def run_experience_plasticity_experiments(output_dir: Path) -> PrimaryExperimentGroup:
    """G2: 经历可塑性实验"""
    group = PrimaryExperimentGroup(
        group_id="G2",
        group_name="Experience Plasticity",
        total_scenarios=0,
        passed=0,
        failed=0,
    )

    # Scenario 2.1: 成功结果 vs 失败结果对状态的影响
    print("\n[G2.1] Running success vs failure comparison...")

    # 成功路径
    state_success = ProtoSelfState.empty()
    for i in range(5):
        event = KernelEvent(
            event_id=f"g2-success-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": True},
        )
        process_event(state_success, event)

    # 失败路径
    state_failure = ProtoSelfState.empty()
    for i in range(5):
        event = KernelEvent(
            event_id=f"g2-failure-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": False, "error": "timeout"},
        )
        process_event(state_failure, event)

    # 对比
    passed = state_failure.revision_counter > state_success.revision_counter

    record = PrimaryExperimentRecord(
        experiment_group="G2",
        experiment_id="G2.1",
        description="成功 vs 失败结果对 revision_counter 的影响",
        input_sequence=[],
        observations=[{
            "success_path": {
                "revision_counter": state_success.revision_counter,
                "current_mode": state_success.self_model.current_mode,
            },
            "failure_path": {
                "revision_counter": state_failure.revision_counter,
                "current_mode": state_failure.self_model.current_mode,
            },
        }],
        expected={"failure_revision > success_revision": True},
        actual_result={
            "success_revision": state_success.revision_counter,
            "failure_revision": state_failure.revision_counter,
        },
        conclusion="PASS: 失败路径产生更多 revision" if passed else "FAIL: revision 无差异",
        passed=passed,
        artifact_path=str(output_dir / "g2_experience_plasticity" / "scenario_2_1.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    # Scenario 2.2: Drive field 对结果的响应
    print("[G2.2] Running drive field response test...")
    state = ProtoSelfState.empty()
    initial_caution = state.drives.caution

    event = KernelEvent(
        event_id="g2-drive-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="dangerous operation",
        safety_context={"risk_level": 0.8},
    )
    output = process_event(state, event)

    # 验证：caution 应该增加
    caution_increased = state.drives.caution > initial_caution
    passed = caution_increased

    record = PrimaryExperimentRecord(
        experiment_group="G2",
        experiment_id="G2.2",
        description="高风险事件对 drive_field 的影响",
        input_sequence=[event.to_dict()],
        observations=[{
            "initial_caution": initial_caution,
            "final_caution": state.drives.caution,
            "caution_delta": state.drives.caution - initial_caution,
        }],
        expected={"caution_increase": True},
        actual_result={
            "caution_increased": caution_increased,
            "caution_delta": state.drives.caution - initial_caution,
        },
        conclusion="PASS: 高风险事件增加 caution" if passed else "FAIL: caution 未响应",
        passed=passed,
        artifact_path=str(output_dir / "g2_experience_plasticity" / "scenario_2_2.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    return group


# ============================================================================
# Group 3: Cycle Re-entry and Promotion
# ============================================================================

def run_cycle_experiments(output_dir: Path) -> PrimaryExperimentGroup:
    """G3: Cycle 可重入与晋升实验"""
    group = PrimaryExperimentGroup(
        group_id="G3",
        group_name="Cycle Re-entry and Promotion",
        total_scenarios=0,
        passed=0,
        failed=0,
    )

    # Scenario 3.1: 10次重复 → 验证晋升
    print("\n[G3.1] Running 10-round cycle promotion test...")
    state = ProtoSelfState.empty()
    cycle_states = []

    for i in range(10):
        event = KernelEvent(
            event_id=f"g3-cycle-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="read file",  # 相同 intent
        )
        output = process_event(state, event)
        cycle_delta = output.trace_payload.get("cycle_delta", {})
        cycle_id = cycle_delta.get("cycle_id")

        if cycle_id and cycle_id in state.cycle_store.signatures:
            c = state.cycle_store.signatures[cycle_id]
            cycle_states.append({
                "iteration": i,
                "op": cycle_delta.get("op"),
                "hits": c.hits,
                "strength": c.strength,
                "promoted": c.promoted,
            })

    # 验证：第 6 次后应该晋升 (strength > 0.5 && hits > 3)
    # 实际：每次 +0.1，需要 6 次达到 0.55，但 hits=6 > 3
    final_promoted = cycle_states[-1]["promoted"] if cycle_states else False
    passed = final_promoted

    record = PrimaryExperimentRecord(
        experiment_group="G3",
        experiment_id="G3.1",
        description="10次重复事件，验证 cycle 晋升",
        input_sequence=[],
        observations=cycle_states,
        expected={"promoted": True, "min_hits": 4, "min_strength": 0.5},
        actual_result={
            "final_promoted": final_promoted,
            "final_hits": cycle_states[-1]["hits"] if cycle_states else 0,
            "final_strength": cycle_states[-1]["strength"] if cycle_states else 0,
        },
        conclusion="PASS: cycle 成功晋升" if passed else "FAIL: cycle 未晋升",
        passed=passed,
        artifact_path=str(output_dir / "g3_cycle_promotion" / "scenario_3_1.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    # Scenario 3.2: 不同 intent 创建不同 cycle
    print("[G3.2] Running different intent differentiation test...")
    state = ProtoSelfState.empty()
    cycle_ids = set()

    intents = ["read file", "write file", "delete file", "read file"]  # 最后一个应该匹配第一个
    for i, intent in enumerate(intents):
        event = KernelEvent(
            event_id=f"g3-diff-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent=intent,
        )
        output = process_event(state, event)
        cycle_delta = output.trace_payload.get("cycle_delta", {})
        cycle_id = cycle_delta.get("cycle_id")
        if cycle_id:
            cycle_ids.add(cycle_id)

    # 验证：应该有多个不同的 cycle_id（至少 2 个）
    passed = len(cycle_ids) >= 2

    record = PrimaryExperimentRecord(
        experiment_group="G3",
        experiment_id="G3.2",
        description="不同 intent 创建不同 cycle",
        input_sequence=[{"intent": i} for i in intents],
        observations=[{"unique_cycle_ids": len(cycle_ids)}],
        expected={"min_unique_cycles": 2},
        actual_result={"unique_cycle_count": len(cycle_ids)},
        conclusion="PASS: 不同 intent 产生不同 cycle" if passed else "FAIL: cycle 未正确区分",
        passed=passed,
        artifact_path=str(output_dir / "g3_cycle_promotion" / "scenario_3_2.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    return group


# ============================================================================
# Group 4: Reflection and Revision
# ============================================================================

def run_reflection_experiments(output_dir: Path) -> PrimaryExperimentGroup:
    """G4: Reflection 触发与 Revision 变化"""
    group = PrimaryExperimentGroup(
        group_id="G4",
        group_name="Reflection and Revision",
        total_scenarios=0,
        passed=0,
        failed=0,
    )

    # Scenario 4.1: 多种触发条件
    print("\n[G4.1] Running multiple reflection triggers...")

    triggers_tested = []

    # 4.1a: external_failure
    state = ProtoSelfState.empty()
    event = KernelEvent(
        event_id="g4-external-failure",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)
    triggers_tested.append({
        "trigger_type": "external_failure",
        "triggered": output.reflection_note is not None,
        "trigger_value": output.reflection_note.trigger if output.reflection_note else None,
    })

    # 4.1b: drive spike (通过高风险事件)
    state = ProtoSelfState.empty()
    event = KernelEvent(
        event_id="g4-drive-spike",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="emergency",
        safety_context={"risk_level": 1.0},
    )
    output = process_event(state, event)
    # drive spike 需要检查 appraisal_delta
    appraisal_delta = output.appraisal_state_delta
    is_drive_spike = any(abs(v) > 0.5 for v in appraisal_delta.values())
    triggers_tested.append({
        "trigger_type": "drive_spike_check",
        "triggered": is_drive_spike,
        "appraisal_delta": appraisal_delta,
    })

    # 验证：external_failure 应该触发 reflection
    external_failure_triggered = triggers_tested[0]["triggered"]
    passed = external_failure_triggered

    record = PrimaryExperimentRecord(
        experiment_group="G4",
        experiment_id="G4.1",
        description="多种 reflection 触发条件测试",
        input_sequence=[],
        observations=triggers_tested,
        expected={"external_failure_triggers": True},
        actual_result={"triggers": triggers_tested},
        conclusion="PASS: external_failure 正确触发 reflection" if passed else "FAIL: reflection 未触发",
        passed=passed,
        artifact_path=str(output_dir / "g4_reflection_revision" / "scenario_4_1.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    # Scenario 4.2: Revision counter 连续增长
    print("[G4.2] Running revision counter growth test...")
    state = ProtoSelfState.empty()
    revision_history = []

    for i in range(5):
        event = KernelEvent(
            event_id=f"g4-revision-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": False},
        )
        output = process_event(state, event)
        revision_history.append({
            "iteration": i,
            "revision_counter": state.revision_counter,
            "reflection_triggered": output.reflection_note is not None,
        })

    # 验证：revision_counter 应该持续增长
    expected_revisions = [1, 2, 3, 4, 5]
    actual_revisions = [r["revision_counter"] for r in revision_history]
    passed = actual_revisions == expected_revisions

    record = PrimaryExperimentRecord(
        experiment_group="G4",
        experiment_id="G4.2",
        description="连续失败事件的 revision_counter 增长",
        input_sequence=[],
        observations=revision_history,
        expected={"revisions": expected_revisions},
        actual_result={"revisions": actual_revisions},
        conclusion="PASS: revision_counter 正确增长" if passed else "FAIL: revision_counter 异常",
        passed=passed,
        artifact_path=str(output_dir / "g4_reflection_revision" / "scenario_4_2.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    # Scenario 4.3: Mode 切换到 repair
    print("[G4.3] Running mode switch to repair test...")
    state = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="g4-mode-repair",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False},
    )
    output = process_event(state, event)

    passed = state.self_model.current_mode == "repair"

    record = PrimaryExperimentRecord(
        experiment_group="G4",
        experiment_id="G4.3",
        description="失败后 mode 切换到 repair",
        input_sequence=[event.to_dict()],
        observations=[{
            "initial_mode": "baseline",
            "final_mode": state.self_model.current_mode,
        }],
        expected={"final_mode": "repair"},
        actual_result={"final_mode": state.self_model.current_mode},
        conclusion="PASS: mode 正确切换到 repair" if passed else "FAIL: mode 未切换",
        passed=passed,
        artifact_path=str(output_dir / "g4_reflection_revision" / "scenario_4_3.json"),
        timestamp=datetime.now().isoformat(),
    )
    group.records.append(record)
    group.total_scenarios += 1
    if passed:
        group.passed += 1
    else:
        group.failed += 1

    return group


# ============================================================================
# Main
# ============================================================================

def main():
    """主入口"""
    print("=" * 60)
    print("N2C Primary Experiments - Proto-Self Kernel v1")
    print("=" * 60)

    output_dir = Path(__file__).parent.parent.parent / "Tasks" / "overnight" / "artifacts" / "n2_experiments"

    # 创建子目录
    (output_dir / "g1_identity_continuity").mkdir(parents=True, exist_ok=True)
    (output_dir / "g2_experience_plasticity").mkdir(parents=True, exist_ok=True)
    (output_dir / "g3_cycle_promotion").mkdir(parents=True, exist_ok=True)
    (output_dir / "g4_reflection_revision").mkdir(parents=True, exist_ok=True)

    # 运行所有实验组
    all_groups = []

    print("\n" + "-" * 40)
    print("G1: Identity Continuity")
    print("-" * 40)
    group_g1 = run_identity_continuity_experiments(output_dir)
    all_groups.append(group_g1)
    print(f"  Passed: {group_g1.passed}/{group_g1.total_scenarios}")

    print("\n" + "-" * 40)
    print("G2: Experience Plasticity")
    print("-" * 40)
    group_g2 = run_experience_plasticity_experiments(output_dir)
    all_groups.append(group_g2)
    print(f"  Passed: {group_g2.passed}/{group_g2.total_scenarios}")

    print("\n" + "-" * 40)
    print("G3: Cycle Re-entry and Promotion")
    print("-" * 40)
    group_g3 = run_cycle_experiments(output_dir)
    all_groups.append(group_g3)
    print(f"  Passed: {group_g3.passed}/{group_g3.total_scenarios}")

    print("\n" + "-" * 40)
    print("G4: Reflection and Revision")
    print("-" * 40)
    group_g4 = run_reflection_experiments(output_dir)
    all_groups.append(group_g4)
    print(f"  Passed: {group_g4.passed}/{group_g4.total_scenarios}")

    # 保存结果
    overall = {
        "timestamp": datetime.now().isoformat(),
        "total_groups": len(all_groups),
        "total_scenarios": sum(g.total_scenarios for g in all_groups),
        "total_passed": sum(g.passed for g in all_groups),
        "total_failed": sum(g.failed for g in all_groups),
        "by_group": {
            g.group_id: {
                "name": g.group_name,
                "passed": g.passed,
                "failed": g.failed,
            }
            for g in all_groups
        },
        "details": [g.to_dict() for g in all_groups],
    }

    overall_file = output_dir / "n2c_primary_experiments_summary.json"
    with open(overall_file, "w") as f:
        json.dump(overall, f, indent=2, default=str)

    # 打印汇总
    print("\n" + "=" * 60)
    print("N2C PRIMARY EXPERIMENTS SUMMARY")
    print("=" * 60)
    print(f"Total groups: {overall['total_groups']}")
    print(f"Total scenarios: {overall['total_scenarios']}")
    print(f"Passed: {overall['total_passed']}")
    print(f"Failed: {overall['total_failed']}")
    print(f"\nOverall file: {overall_file}")

    for g in all_groups:
        print(f"\n[{g.group_id}] {g.group_name}: {g.passed}/{g.total_scenarios}")
        for r in g.records:
            status = "✓" if r.passed else "✗"
            print(f"  {status} {r.experiment_id}: {r.conclusion}")

    return 0 if overall['total_failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
