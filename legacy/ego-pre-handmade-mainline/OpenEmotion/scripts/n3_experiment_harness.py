"""
N3 Experiment Harness - 泛化、误聚合与反证实验

Proto-Self Kernel v1 的泛化验证实验脚手架。

功能：
- 应聚合样本测试（SM组）
- 应区分样本测试（SS组）
- 误聚合检测
- Replay 一致性验证
- 风险清单生成

设计约束：
- 不为实验引入第二套本体状态
- 不让 harness 变成新的黑箱真相源
- 所有实验结果必须可回读
- 必须包含反例和边界样本
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 添加 OpenEmotion 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.cycles import _coarse_intent_classify, _build_psi_bucket


# ============================================================================
# Data Types
# ============================================================================

@dataclass
class SampleResult:
    """单样本测试结果"""
    sample_id: str
    sample_group: str
    intent: str
    expected_behavior: str
    observed_cycle_id: Optional[str]
    observed_coarse_intent: str
    observed_psi_bucket: str
    observed_op: str
    hits: int
    strength: float
    promoted: bool
    safety_context: Optional[Dict[str, Any]] = None
    extra_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MergeTestResult:
    """应聚合样本测试结果"""
    group_id: str
    samples: List[SampleResult]
    unique_cycle_ids: int
    expected_unique_cycle_ids: int
    passed: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "samples": [s.to_dict() for s in self.samples],
            "unique_cycle_ids": self.unique_cycle_ids,
            "expected_unique_cycle_ids": self.expected_unique_cycle_ids,
            "passed": self.passed,
            "reason": self.reason,
        }


@dataclass
class SeparateTestResult:
    """应区分样本测试结果"""
    group_id: str
    sample_a: SampleResult
    sample_b: SampleResult
    same_cycle: bool
    expected_same_cycle: bool
    misaggregation: bool  # 误聚合标记
    risk_level: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "sample_a": self.sample_a.to_dict(),
            "sample_b": self.sample_b.to_dict(),
            "same_cycle": self.same_cycle,
            "expected_same_cycle": self.expected_same_cycle,
            "misaggregation": self.misaggregation,
            "risk_level": self.risk_level,
            "reason": self.reason,
        }


@dataclass
class ReplayTestResult:
    """Replay 一致性测试结果"""
    test_id: str
    event_sequence: List[Dict[str, Any]]
    original_cycle_ids: List[str]
    replay_cycle_ids: List[str]
    original_strengths: List[float]
    replay_strengths: List[float]
    cycle_id_consistent: bool
    strength_consistent: bool
    passed: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Sample Definitions
# ============================================================================

# 应聚合样本定义
SHOULD_MERGE_SAMPLES = {
    "SM-1": {
        "name": "文件读取类",
        "samples": [
            {"id": "SM-1a", "intent": "读取 config.yaml"},
            {"id": "SM-1b", "intent": "查看配置文件"},
            {"id": "SM-1c", "intent": "read the file"},
            {"id": "SM-1d", "intent": "check file content"},
        ],
        "expected_unique_cycles": 1,
    },
    "SM-2": {
        "name": "测试验证类",
        "samples": [
            {"id": "SM-2a", "intent": "运行测试"},
            {"id": "SM-2b", "intent": "验证功能"},
            {"id": "SM-2c", "intent": "run e2e test"},
            {"id": "SM-2d", "intent": "confirm the result"},
        ],
        "expected_unique_cycles": 1,
    },
    "SM-3": {
        "name": "状态查询类",
        "samples": [
            {"id": "SM-3a", "intent": "查看系统状态"},
            {"id": "SM-3b", "intent": "检查日志"},
            {"id": "SM-3c", "intent": "check health"},
            {"id": "SM-3d", "intent": "show process list"},
        ],
        "expected_unique_cycles": 1,
    },
}

# 应区分样本定义
SHOULD_SEPARATE_SAMPLES = {
    "SS-1": {
        "name": "相同操作类别，不同风险等级",
        "samples": [
            {
                "id": "SS-1a",
                "intent": "删除临时文件",
                "safety_context": {"risk": "low"},
                "risk_level": "high",  # 误聚合风险等级
            },
            {
                "id": "SS-1b",
                "intent": "删除生产数据库",
                "safety_context": {"risk": "critical"},
                "risk_level": "high",
            },
        ],
    },
    "SS-2": {
        "name": "相同类别，不同目标对象",
        "samples": [
            {
                "id": "SS-2a",
                "intent": "修改用户配置",
                "extra": {"target": "user_config"},
                "risk_level": "medium",
            },
            {
                "id": "SS-2b",
                "intent": "修改系统配置",
                "extra": {"target": "system_config"},
                "risk_level": "medium",
            },
        ],
    },
    "SS-3": {
        "name": "测试类：生产 vs 开发",
        "samples": [
            {
                "id": "SS-3a",
                "intent": "测试登录功能",
                "extra": {"environment": "dev"},
                "risk_level": "medium",
            },
            {
                "id": "SS-3b",
                "intent": "测试生产环境",
                "extra": {"environment": "production"},
                "risk_level": "medium",
            },
        ],
    },
    "SS-4": {
        "name": "语言歧义样本",
        "samples": [
            {
                "id": "SS-4a",
                "intent": "检查代码",
                "extra": {"meaning": "code_review"},
                "risk_level": "low",
            },
            {
                "id": "SS-4b",
                "intent": "检查健康状态",
                "extra": {"meaning": "health_check"},
                "risk_level": "low",
            },
        ],
    },
}


# ============================================================================
# Experiment Harness
# ============================================================================

class N3ExperimentHarness:
    """N3 实验脚手架"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_single_sample(
        self,
        state: ProtoSelfState,
        sample_id: str,
        intent: str,
        safety_context: Optional[Dict[str, Any]] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> SampleResult:
        """运行单样本测试"""
        event = KernelEvent(
            event_id=sample_id,
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent=intent,
            safety_context=safety_context or {},
        )

        output = process_event(state, event)

        cycle_delta = output.trace_payload.get("cycle_delta", {})
        cycle_id = cycle_delta.get("cycle_id")
        op = cycle_delta.get("op", "unknown")
        psi_bucket = cycle_delta.get("psi_bucket", "unknown")

        # 解析 coarse_intent
        coarse_intent = "unknown"
        if psi_bucket and ":" in psi_bucket:
            parts = psi_bucket.split(":")
            if len(parts) >= 3:
                coarse_intent = parts[2]

        # 获取 cycle 状态
        hits = 0
        strength = 0.0
        promoted = False
        if cycle_id and cycle_id in state.cycle_store.signatures:
            c = state.cycle_store.signatures[cycle_id]
            hits = c.hits
            strength = c.strength
            promoted = c.promoted

        return SampleResult(
            sample_id=sample_id,
            sample_group=sample_id.split("-")[0],
            intent=intent,
            expected_behavior="aggregate" if sample_id.startswith("SM") else "separate",
            observed_cycle_id=cycle_id,
            observed_coarse_intent=coarse_intent,
            observed_psi_bucket=psi_bucket,
            observed_op=op,
            hits=hits,
            strength=strength,
            promoted=promoted,
            safety_context=safety_context,
            extra_context=extra_context,
        )

    def run_merge_test(self, group_id: str, group_data: Dict) -> MergeTestResult:
        """运行应聚合样本测试"""
        state = ProtoSelfState.empty()
        samples = []
        cycle_ids = set()

        for sample in group_data["samples"]:
            result = self.run_single_sample(
                state, sample["id"], sample["intent"]
            )
            samples.append(result)
            if result.observed_cycle_id:
                cycle_ids.add(result.observed_cycle_id)

        unique_cycles = len(cycle_ids)
        expected_cycles = group_data["expected_unique_cycles"]
        passed = unique_cycles == expected_cycles

        if passed:
            reason = f"所有 {len(samples)} 个样本正确聚合到 {unique_cycles} 个 cycle"
        else:
            reason = f"预期 {expected_cycles} 个 cycle，实际 {unique_cycles} 个（聚合失败）"

        return MergeTestResult(
            group_id=group_id,
            samples=samples,
            unique_cycle_ids=unique_cycles,
            expected_unique_cycle_ids=expected_cycles,
            passed=passed,
            reason=reason,
        )

    def run_separate_test(self, group_id: str, group_data: Dict) -> SeparateTestResult:
        """运行应区分样本测试"""
        # 每个样本使用独立状态
        sample_a_data = group_data["samples"][0]
        sample_b_data = group_data["samples"][1]

        state_a = ProtoSelfState.empty()
        result_a = self.run_single_sample(
            state_a,
            sample_a_data["id"],
            sample_a_data["intent"],
            sample_a_data.get("safety_context"),
            sample_a_data.get("extra"),
        )

        state_b = ProtoSelfState.empty()
        result_b = self.run_single_sample(
            state_b,
            sample_b_data["id"],
            sample_b_data["intent"],
            sample_b_data.get("safety_context"),
            sample_b_data.get("extra"),
        )

        same_cycle = result_a.observed_cycle_id == result_b.observed_cycle_id
        expected_same = False  # 应区分样本预期不同 cycle
        misaggregation = same_cycle  # 相同 cycle = 误聚合
        risk_level = group_data["samples"][0].get("risk_level", "low")

        if same_cycle:
            reason = f"⚠️ 误聚合：'{sample_a_data['intent']}' 和 '{sample_b_data['intent']}' 命中同一 cycle"
        else:
            reason = f"✅ 正确区分：'{sample_a_data['intent']}' 和 '{sample_b_data['intent']}' 命中不同 cycle"

        return SeparateTestResult(
            group_id=group_id,
            sample_a=result_a,
            sample_b=result_b,
            same_cycle=same_cycle,
            expected_same_cycle=False,
            misaggregation=misaggregation,
            risk_level=risk_level,
            reason=reason,
        )

    def run_replay_test(self, event_sequence: List[Dict[str, Any]]) -> ReplayTestResult:
        """运行 Replay 一致性测试"""
        # 原始执行
        state_original = ProtoSelfState.empty()
        original_cycle_ids = []
        original_strengths = []

        for event_data in event_sequence:
            event = KernelEvent(**event_data)
            output = process_event(state_original, event)
            cycle_delta = output.trace_payload.get("cycle_delta", {})
            original_cycle_ids.append(cycle_delta.get("cycle_id"))

            cycle_id = cycle_delta.get("cycle_id")
            if cycle_id and cycle_id in state_original.cycle_store.signatures:
                original_strengths.append(
                    state_original.cycle_store.signatures[cycle_id].strength
                )
            else:
                original_strengths.append(0.0)

        # Replay 执行
        state_replay = ProtoSelfState.empty()
        replay_cycle_ids = []
        replay_strengths = []

        for event_data in event_sequence:
            event = KernelEvent(**event_data)
            output = process_event(state_replay, event)
            cycle_delta = output.trace_payload.get("cycle_delta", {})
            replay_cycle_ids.append(cycle_delta.get("cycle_id"))

            cycle_id = cycle_delta.get("cycle_id")
            if cycle_id and cycle_id in state_replay.cycle_store.signatures:
                replay_strengths.append(
                    state_replay.cycle_store.signatures[cycle_id].strength
                )
            else:
                replay_strengths.append(0.0)

        # 对比
        cycle_id_consistent = original_cycle_ids == replay_cycle_ids

        strength_consistent = True
        for o, r in zip(original_strengths, replay_strengths):
            if abs(o - r) > 0.01:
                strength_consistent = False
                break

        passed = cycle_id_consistent and strength_consistent

        if passed:
            reason = "Replay 一致性验证通过"
        elif not cycle_id_consistent:
            reason = f"cycle_id 不一致：{original_cycle_ids} vs {replay_cycle_ids}"
        else:
            reason = f"strength 不一致：{original_strengths} vs {replay_strengths}"

        return ReplayTestResult(
            test_id="replay-001",
            event_sequence=event_sequence,
            original_cycle_ids=original_cycle_ids,
            replay_cycle_ids=replay_cycle_ids,
            original_strengths=original_strengths,
            replay_strengths=replay_strengths,
            cycle_id_consistent=cycle_id_consistent,
            strength_consistent=strength_consistent,
            passed=passed,
            reason=reason,
        )

    def save_results(
        self,
        merge_results: List[MergeTestResult],
        separate_results: List[SeparateTestResult],
        replay_results: List[ReplayTestResult],
    ):
        """保存所有结果"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "merge_tests": {
                "total": len(merge_results),
                "passed": sum(1 for r in merge_results if r.passed),
                "failed": sum(1 for r in merge_results if not r.passed),
                "details": [r.to_dict() for r in merge_results],
            },
            "separate_tests": {
                "total": len(separate_results),
                "misaggregations": sum(1 for r in separate_results if r.misaggregation),
                "correct_separations": sum(1 for r in separate_results if not r.misaggregation),
                "details": [r.to_dict() for r in separate_results],
            },
            "replay_tests": {
                "total": len(replay_results),
                "passed": sum(1 for r in replay_results if r.passed),
                "failed": sum(1 for r in replay_results if not r.passed),
                "details": [r.to_dict() for r in replay_results],
            },
        }

        # 风险清单
        misaggregations = [r for r in separate_results if r.misaggregation]
        risk_summary = {
            "high_risk_misaggregations": sum(1 for r in misaggregations if r.risk_level == "high"),
            "medium_risk_misaggregations": sum(1 for r in misaggregations if r.risk_level == "medium"),
            "low_risk_misaggregations": sum(1 for r in misaggregations if r.risk_level == "low"),
        }
        summary["risk_summary"] = risk_summary

        # 保存
        output_file = self.output_dir / "n3_summary.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

        return summary


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """主入口"""
    print("=" * 60)
    print("N3 Experiment Harness - 泛化、误聚合与反证")
    print("=" * 60)

    output_dir = Path(__file__).parent.parent.parent / "Tasks" / "overnight" / "artifacts" / "n3_experiments"
    harness = N3ExperimentHarness(output_dir)

    print(f"\nOutput directory: {output_dir}")

    # 1. 应聚合样本测试
    print("\n" + "=" * 40)
    print("Phase 1: 应聚合样本测试 (SM组)")
    print("=" * 40)

    merge_results = []
    for group_id, group_data in SHOULD_MERGE_SAMPLES.items():
        print(f"\n[{group_id}] {group_data['name']}")
        result = harness.run_merge_test(group_id, group_data)
        merge_results.append(result)
        print(f"  - 样本数: {len(result.samples)}")
        print(f"  - 唯一 cycle 数: {result.unique_cycle_ids}")
        print(f"  - 预期: {result.expected_unique_cycle_ids}")
        print(f"  - 结果: {'✅ 通过' if result.passed else '❌ 失败'}")
        print(f"  - 原因: {result.reason}")

    # 2. 应区分样本测试
    print("\n" + "=" * 40)
    print("Phase 2: 应区分样本测试 (SS组)")
    print("=" * 40)

    separate_results = []
    for group_id, group_data in SHOULD_SEPARATE_SAMPLES.items():
        print(f"\n[{group_id}] {group_data['name']}")
        result = harness.run_separate_test(group_id, group_data)
        separate_results.append(result)
        print(f"  - 样本A: {result.sample_a.intent}")
        print(f"  - 样本B: {result.sample_b.intent}")
        print(f"  - cycle_id 相同: {result.same_cycle}")
        print(f"  - 风险等级: {result.risk_level}")
        if result.misaggregation:
            print(f"  - ⚠️ 误聚合检测！")
        print(f"  - {result.reason}")

    # 3. Replay 一致性测试
    print("\n" + "=" * 40)
    print("Phase 3: Replay 一致性测试")
    print("=" * 40)

    # 使用 SM-1 样本序列进行 replay 测试
    replay_sequence = [
        {
            "event_id": f"replay-{i:03d}",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "user_intent": "read file",
        }
        for i in range(5)
    ]

    replay_results = [harness.run_replay_test(replay_sequence)]

    for result in replay_results:
        print(f"\n[{result.test_id}]")
        print(f"  - 事件数: {len(result.event_sequence)}")
        print(f"  - cycle_id 一致: {result.cycle_id_consistent}")
        print(f"  - strength 一致: {result.strength_consistent}")
        print(f"  - 结果: {'✅ 通过' if result.passed else '❌ 失败'}")
        print(f"  - 原因: {result.reason}")

    # 4. 保存结果
    print("\n" + "=" * 40)
    print("保存结果")
    print("=" * 40)

    summary = harness.save_results(merge_results, separate_results, replay_results)

    print(f"\n汇总:")
    print(f"  应聚合测试: {summary['merge_tests']['passed']}/{summary['merge_tests']['total']} 通过")
    print(f"  应区分测试: {summary['separate_tests']['correct_separations']}/{summary['separate_tests']['total']} 正确区分")
    print(f"  误聚合数: {summary['separate_tests']['misaggregations']}")
    print(f"  Replay 测试: {summary['replay_tests']['passed']}/{summary['replay_tests']['total']} 通过")

    print(f"\n风险清单:")
    print(f"  高风险误聚合: {summary['risk_summary']['high_risk_misaggregations']}")
    print(f"  中风险误聚合: {summary['risk_summary']['medium_risk_misaggregations']}")
    print(f"  低风险误聚合: {summary['risk_summary']['low_risk_misaggregations']}")

    print(f"\n结果文件: {output_dir / 'n3_summary.json'}")

    # 返回退出码
    has_issues = (
        summary['merge_tests']['failed'] > 0 or
        summary['separate_tests']['misaggregations'] > 0 or
        summary['replay_tests']['failed'] > 0
    )
    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
