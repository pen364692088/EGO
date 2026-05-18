"""
N2D Ablation Experiments

验证递归核中的关键组件是否真的带来差异。

Ablation 方向：
1. 关闭 reflection 回流 → 观察 revision_counter 和 mode 变化差异
2. 关闭 cycle strengthen → 观察 cycle 创建但不强化
3. 关闭 external_result 影响 → 观察状态变化差异
4. 固定 drive_field → 观察 policy_hint 差异

设计约束：
- 不修改生产代码
- 通过 mock/patch 实现组件禁用
- 对比结果必须可量化
"""

import json
import sys
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


# ============================================================================
# Ablation Framework
# ============================================================================

@dataclass
class AblationResult:
    """Ablation 实验结果"""
    ablation_type: str
    description: str
    baseline_result: Dict[str, Any]
    ablated_result: Dict[str, Any]
    difference: Dict[str, Any]
    has_effect: bool
    conclusion: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AblationSummary:
    """Ablation 汇总"""
    total_ablations: int
    with_effect: int
    without_effect: int
    results: List[AblationResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_ablations": self.total_ablations,
            "with_effect": self.with_effect,
            "without_effect": self.without_effect,
            "results": [r.to_dict() for r in self.results],
        }


# ============================================================================
# Baseline Runner
# ============================================================================

def run_baseline(state: ProtoSelfState, events: List[KernelEvent]) -> Dict[str, Any]:
    """运行基准测试"""
    for event in events:
        process_event(state, event)

    return {
        "revision_counter": state.revision_counter,
        "current_mode": state.self_model.current_mode,
        "cycle_count": len(state.cycle_store.signatures),
        "cycle_hits": {
            cid: c.hits for cid, c in state.cycle_store.signatures.items()
        },
        "cycle_strengths": {
            cid: c.strength for cid, c in state.cycle_store.signatures.items()
        },
        "drives": state.drives.to_dict(),
        "episodic_count": len(state.episodic_trace),
    }


# ============================================================================
# Ablation 1: Disable Reflection
# ============================================================================

def ablation_disable_reflection(output_dir: Path) -> AblationResult:
    """Ablation: 关闭 reflection 回流"""
    print("\n[A1] Running ablation: Disable Reflection...")

    # 创建相同的事件序列
    events = [
        KernelEvent(
            event_id=f"abl-ref-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": False},
        )
        for i in range(5)
    ]

    # Baseline
    state_baseline = ProtoSelfState.empty()
    result_baseline = run_baseline(state_baseline, events)

    # Ablated: 禁用 reflection
    state_ablated = ProtoSelfState.empty()

    # Patch reflection 模块返回 None
    with patch('openemotion.proto_self.reflection.maybe_reflect', return_value=None):
        for event in events:
            process_event(state_ablated, event)

    result_ablated = {
        "revision_counter": state_ablated.revision_counter,
        "current_mode": state_ablated.self_model.current_mode,
        "cycle_count": len(state_ablated.cycle_store.signatures),
        "episodic_count": len(state_ablated.episodic_trace),
    }

    # 对比
    difference = {
        "revision_counter_diff": result_baseline["revision_counter"] - result_ablated["revision_counter"],
        "mode_different": result_baseline["current_mode"] != result_ablated["current_mode"],
    }

    has_effect = difference["revision_counter_diff"] > 0 or difference["mode_different"]

    return AblationResult(
        ablation_type="disable_reflection",
        description="关闭 reflection 回流，观察 revision_counter 和 mode 差异",
        baseline_result=result_baseline,
        ablated_result=result_ablated,
        difference=difference,
        has_effect=has_effect,
        conclusion=f"Reflection {'有' if has_effect else '无'}显著影响：revision_counter 差异 {difference['revision_counter_diff']}, mode {'不同' if difference['mode_different'] else '相同'}",
        timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# Ablation 2: Disable Cycle Strengthen
# ============================================================================

def ablation_disable_cycle_strengthen(output_dir: Path) -> AblationResult:
    """Ablation: 关闭 cycle strengthen（只允许创建，不允许强化）"""
    print("\n[A2] Running ablation: Disable Cycle Strengthen...")

    # 创建相同的事件序列（相同 intent）
    events = [
        KernelEvent(
            event_id=f"abl-cycle-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="read file",  # 相同 intent
        )
        for i in range(10)
    ]

    # Baseline
    state_baseline = ProtoSelfState.empty()
    result_baseline = run_baseline(state_baseline, events)

    # Ablated: 禁用 cycle strengthen
    state_ablated = ProtoSelfState.empty()

    # Patch apply_cycle_delta 使其不更新 strength
    original_apply = None
    def patched_apply_cycle_delta(cycle_store, cycle_delta, timestamp):
        from openemotion.proto_self.state import CycleSignature
        cycle_id = cycle_delta["cycle_id"]
        op = cycle_delta["op"]

        # 只允许 candidate，不允许 strengthen
        if op == "candidate":
            cycle_store.signatures[cycle_id] = CycleSignature(
                cycle_id=cycle_id,
                psi_bucket=cycle_delta["psi_bucket"],
                phi_signature=cycle_delta["phi_signature"],
                strength=0.05,
                hits=1,
                last_seen_ts=timestamp,
                promoted=False,
            )
        # strengthen 被禁用，不更新

    with patch('openemotion.proto_self.cycles.apply_cycle_delta', patched_apply_cycle_delta):
        for event in events:
            process_event(state_ablated, event)

    result_ablated = {
        "cycle_count": len(state_ablated.cycle_store.signatures),
        "cycle_hits": {
            cid: c.hits for cid, c in state_ablated.cycle_store.signatures.items()
        },
        "cycle_strengths": {
            cid: c.strength for cid, c in state_ablated.cycle_store.signatures.items()
        },
    }

    # 对比
    baseline_strength = max(result_baseline["cycle_strengths"].values()) if result_baseline["cycle_strengths"] else 0
    ablated_strength = max(result_ablated["cycle_strengths"].values()) if result_ablated["cycle_strengths"] else 0

    difference = {
        "baseline_max_strength": baseline_strength,
        "ablated_max_strength": ablated_strength,
        "strength_diff": baseline_strength - ablated_strength,
    }

    has_effect = difference["strength_diff"] > 0.1

    return AblationResult(
        ablation_type="disable_cycle_strengthen",
        description="关闭 cycle strengthen，观察 strength 差异",
        baseline_result=result_baseline,
        ablated_result=result_ablated,
        difference=difference,
        has_effect=has_effect,
        conclusion=f"Cycle Strengthen {'有' if has_effect else '无'}显著影响：strength 差异 {difference['strength_diff']:.2f}",
        timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# Ablation 3: Disable External Result Impact
# ============================================================================

def ablation_disable_external_result(output_dir: Path) -> AblationResult:
    """Ablation: 关闭 external_result 对状态的影响"""
    print("\n[A3] Running ablation: Disable External Result Impact...")

    # 创建包含 external_result 的事件序列
    events = [
        KernelEvent(
            event_id=f"abl-ext-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            external_result={"success": i % 2 == 0},  # 交替成功/失败
        )
        for i in range(10)
    ]

    # Baseline
    state_baseline = ProtoSelfState.empty()
    result_baseline = run_baseline(state_baseline, events)

    # Ablated: 将所有 external_result 设为 None
    state_ablated = ProtoSelfState.empty()

    for event in events:
        # 创建一个没有 external_result 的事件
        event_no_ext = KernelEvent(
            event_id=event.event_id,
            timestamp=event.timestamp,
            actor=event.actor,
            source=event.source,
            event_type=event.event_type,
            external_result=None,  # 禁用 external_result
        )
        process_event(state_ablated, event_no_ext)

    result_ablated = {
        "revision_counter": state_ablated.revision_counter,
        "current_mode": state_ablated.self_model.current_mode,
        "episodic_count": len(state_ablated.episodic_trace),
    }

    # 对比
    difference = {
        "revision_counter_diff": result_baseline["revision_counter"] - result_ablated["revision_counter"],
        "mode_different": result_baseline["current_mode"] != result_ablated["current_mode"],
    }

    has_effect = difference["revision_counter_diff"] > 0

    return AblationResult(
        ablation_type="disable_external_result",
        description="关闭 external_result 影响，观察 revision_counter 差异",
        baseline_result=result_baseline,
        ablated_result=result_ablated,
        difference=difference,
        has_effect=has_effect,
        conclusion=f"External Result {'有' if has_effect else '无'}显著影响：revision_counter 差异 {difference['revision_counter_diff']}",
        timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# Ablation 4: Fixed Drive Field
# ============================================================================

def ablation_fixed_drive_field(output_dir: Path) -> AblationResult:
    """Ablation: 固定 drive_field，观察 policy_hint 差异"""
    print("\n[A4] Running ablation: Fixed Drive Field...")

    # 创建高风险事件序列
    events = [
        KernelEvent(
            event_id=f"abl-drive-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="dangerous operation",
            safety_context={"risk_level": 0.9},
        )
        for i in range(3)
    ]

    # Baseline
    state_baseline = ProtoSelfState.empty()
    result_baseline = run_baseline(state_baseline, events)

    # Ablated: 固定 drive_field
    state_ablated = ProtoSelfState.empty()
    # 保持初始 drive_field 不变

    # Patch update_drive_field 使其返回初始值
    def fixed_drive_field(state, perceived):
        return state.drives.to_dict()  # 返回当前值，不更新

    with patch('openemotion.proto_self.appraisal.update_drive_field', fixed_drive_field):
        for event in events:
            process_event(state_ablated, event)

    result_ablated = {
        "drives": state_ablated.drives.to_dict(),
        "final_caution": state_ablated.drives.caution,
    }

    # 对比
    difference = {
        "baseline_caution": result_baseline["drives"]["caution"],
        "ablated_caution": result_ablated["drives"]["caution"],
        "caution_diff": result_baseline["drives"]["caution"] - result_ablated["drives"]["caution"],
    }

    has_effect = difference["caution_diff"] > 0.1

    return AblationResult(
        ablation_type="fixed_drive_field",
        description="固定 drive_field，观察 caution 差异",
        baseline_result=result_baseline,
        ablated_result=result_ablated,
        difference=difference,
        has_effect=has_effect,
        conclusion=f"Drive Field 更新 {'有' if has_effect else '无'}显著影响：caution 差异 {difference['caution_diff']:.2f}",
        timestamp=datetime.now().isoformat(),
    )


# ============================================================================
# Main
# ============================================================================

def main():
    """主入口"""
    print("=" * 60)
    print("N2D Ablation Experiments - Proto-Self Kernel v1")
    print("=" * 60)

    output_dir = Path(__file__).parent.parent.parent / "Tasks" / "overnight" / "artifacts" / "n2_experiments"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = AblationSummary(
        total_ablations=0,
        with_effect=0,
        without_effect=0,
    )

    # 运行所有 ablation
    ablations = [
        ablation_disable_reflection,
        ablation_disable_cycle_strengthen,
        ablation_disable_external_result,
        ablation_fixed_drive_field,
    ]

    for ablation_fn in ablations:
        try:
            result = ablation_fn(output_dir)
            summary.results.append(result)
            summary.total_ablations += 1
            if result.has_effect:
                summary.with_effect += 1
            else:
                summary.without_effect += 1
            print(f"  - {result.ablation_type}: {'有影响' if result.has_effect else '无影响'}")
        except Exception as e:
            print(f"  - {ablation_fn.__name__} FAILED: {e}")
            summary.results.append(AblationResult(
                ablation_type=ablation_fn.__name__,
                description="Execution failed",
                baseline_result={},
                ablated_result={},
                difference={},
                has_effect=False,
                conclusion=f"FAILED: {e}",
                timestamp=datetime.now().isoformat(),
            ))
            summary.total_ablations += 1
            summary.without_effect += 1

    # 保存结果
    output_file = output_dir / "n2d_ablation_summary.json"
    with open(output_file, "w") as f:
        json.dump(summary.to_dict(), f, indent=2, default=str)

    # 打印汇总
    print("\n" + "=" * 60)
    print("ABLATION SUMMARY")
    print("=" * 60)
    print(f"Total ablations: {summary.total_ablations}")
    print(f"With effect: {summary.with_effect}")
    print(f"Without effect: {summary.without_effect}")
    print(f"\nOutput: {output_file}")

    for r in summary.results:
        status = "✓ EFFECT" if r.has_effect else "✗ NO EFFECT"
        print(f"\n[{r.ablation_type}] {status}")
        print(f"  {r.conclusion}")

    return 0 if summary.with_effect > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
