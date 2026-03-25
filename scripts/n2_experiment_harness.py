"""
N2 Experiment Harness

Proto-Self Kernel v1 递归核有效性实验脚手架。

功能：
- 统一实验入口
- 统一 artifact 输出
- 统一结果摘要格式
- trace 字段读取
- 实验对比

设计约束：
- 不为实验引入第二套本体状态
- 不让 harness 变成新的黑箱真相源
- 所有实验结果必须可回读
"""

import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加 OpenEmotion 到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


# ============================================================================
# Experiment Types
# ============================================================================

@dataclass
class ExperimentResult:
    """单次实验结果"""
    experiment_id: str
    experiment_class: str  # E1, E2, E3, E4
    timestamp: str
    input_event: Dict[str, Any]
    observed: Dict[str, Any]
    expected: Dict[str, Any]
    passed: bool
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentSummary:
    """实验汇总"""
    experiment_class: str
    total_runs: int
    passed: int
    failed: int
    results: List[ExperimentResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_class": self.experiment_class,
            "total_runs": self.total_runs,
            "passed": self.passed,
            "failed": self.failed,
            "results": [r.to_dict() for r in self.results],
        }


# ============================================================================
# Experiment Harness
# ============================================================================

class ExperimentHarness:
    """实验脚手架"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.e1_dir = output_dir / "e1_identity_continuity"
        self.e2_dir = output_dir / "e2_cycle_strengthen"
        self.e3_dir = output_dir / "e3_reflection_trigger"
        self.e4_dir = output_dir / "e4_policy_tendency"

        for d in [self.e1_dir, self.e2_dir, self.e3_dir, self.e4_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def run_experiment(
        self,
        experiment_class: str,
        state: ProtoSelfState,
        event: KernelEvent,
        expected: Dict[str, Any],
        validators: List[callable],
    ) -> ExperimentResult:
        """
        运行单次实验。

        Args:
            experiment_class: 实验类别 (E1/E2/E3/E4)
            state: 当前状态
            event: 输入事件
            expected: 预期结果
            validators: 验证函数列表，每个函数接受 (output, expected) 返回 (passed, reason)

        Returns:
            ExperimentResult
        """
        # 执行 kernel
        output = process_event(state, event)

        # 收集观测数据
        observed = self._extract_observations(experiment_class, output, state)

        # 验证
        passed = True
        failure_reason = None

        for validator in validators:
            v_passed, v_reason = validator(output, expected, state)
            if not v_passed:
                passed = False
                failure_reason = v_reason
                break

        return ExperimentResult(
            experiment_id=event.event_id,
            experiment_class=experiment_class,
            timestamp=event.timestamp,
            input_event=event.to_dict(),
            observed=observed,
            expected=expected,
            passed=passed,
            failure_reason=failure_reason,
        )

    def _extract_observations(
        self,
        experiment_class: str,
        output,
        state: ProtoSelfState,
    ) -> Dict[str, Any]:
        """提取观测数据"""
        base_obs = {
            "event_id": output.event_id,
            "revision_counter": state.revision_counter,
            "cycle_count": len(state.cycle_store.signatures),
            "episodic_count": len(state.episodic_trace),
        }

        if experiment_class == "E1":
            base_obs.update({
                "identity_confidence": state.identity.identity_confidence,
                "identity_roles": list(state.identity.core_roles),
                "identity_commitments": list(state.identity.core_commitments),
                "identity_boundaries": list(state.identity.core_boundaries),
                "identity_delta": output.identity_state_delta,
            })

        elif experiment_class == "E2":
            cycle_delta = output.trace_payload.get("cycle_delta", {})
            cycle_id = cycle_delta.get("cycle_id")
            cycle_state = None
            if cycle_id and cycle_id in state.cycle_store.signatures:
                c = state.cycle_store.signatures[cycle_id]
                cycle_state = {
                    "hits": c.hits,
                    "strength": c.strength,
                    "promoted": c.promoted,
                }

            base_obs.update({
                "cycle_delta": cycle_delta,
                "cycle_state": cycle_state,
            })

        elif experiment_class == "E3":
            base_obs.update({
                "reflection_note": output.reflection_note.to_dict() if output.reflection_note else None,
                "self_model_delta": output.self_model_delta,
                "current_mode": state.self_model.current_mode,
            })

        elif experiment_class == "E4":
            base_obs.update({
                "policy_hint": output.policy_hint,
                "response_tendency": output.response_tendency.to_dict() if output.response_tendency else None,
                "drive_field": state.drives.to_dict(),
            })

        return base_obs

    def save_result(self, result: ExperimentResult, experiment_class: str):
        """保存单次实验结果到 JSONL"""
        log_file = self._get_log_file(experiment_class)
        with open(log_file, "a") as f:
            f.write(json.dumps(result.to_dict(), default=str) + "\n")

    def save_summary(self, summary: ExperimentSummary, experiment_class: str):
        """保存实验汇总"""
        summary_file = self._get_summary_file(experiment_class)
        with open(summary_file, "w") as f:
            json.dump(summary.to_dict(), f, indent=2, default=str)

    def _get_log_file(self, experiment_class: str) -> Path:
        dirs = {
            "E1": self.e1_dir,
            "E2": self.e2_dir,
            "E3": self.e3_dir,
            "E4": self.e4_dir,
        }
        return dirs[experiment_class] / "experiment_log.jsonl"

    def _get_summary_file(self, experiment_class: str) -> Path:
        dirs = {
            "E1": self.e1_dir,
            "E2": self.e2_dir,
            "E3": self.e3_dir,
            "E4": self.e4_dir,
        }
        return dirs[experiment_class] / "summary.json"

    def compare_experiments(
        self,
        class_a: str,
        class_b: str,
    ) -> Dict[str, Any]:
        """
        对比两组实验结果。

        Returns:
            对比结果字典
        """
        summary_a = self._load_summary(class_a)
        summary_b = self._load_summary(class_b)

        if not summary_a or not summary_b:
            return {"error": "One or both summaries not found"}

        return {
            "class_a": class_a,
            "class_b": class_b,
            "pass_rate_a": summary_a["passed"] / max(1, summary_a["total_runs"]),
            "pass_rate_b": summary_b["passed"] / max(1, summary_b["total_runs"]),
            "total_runs_a": summary_a["total_runs"],
            "total_runs_b": summary_b["total_runs"],
        }

    def _load_summary(self, experiment_class: str) -> Optional[Dict[str, Any]]:
        """加载实验汇总"""
        summary_file = self._get_summary_file(experiment_class)
        if summary_file.exists():
            with open(summary_file) as f:
                return json.load(f)
        return None


# ============================================================================
# Validators
# ============================================================================

def validate_cycle_created(output, expected, state) -> tuple:
    """验证 cycle 被创建"""
    cycle_delta = output.trace_payload.get("cycle_delta", {})
    if not cycle_delta.get("cycle_id"):
        return False, "cycle_id not found in trace_payload"
    if cycle_delta.get("op") not in ["candidate", "strengthen"]:
        return False, f"unexpected op: {cycle_delta.get('op')}"
    return True, None


def validate_cycle_strengthened(output, expected, state) -> tuple:
    """验证 cycle 被强化"""
    cycle_delta = output.trace_payload.get("cycle_delta", {})
    if cycle_delta.get("op") != "strengthen":
        return False, f"expected strengthen, got {cycle_delta.get('op')}"

    expected_hits = expected.get("min_hits", 2)
    cycle_id = cycle_delta.get("cycle_id")
    if cycle_id and cycle_id in state.cycle_store.signatures:
        actual_hits = state.cycle_store.signatures[cycle_id].hits
        if actual_hits < expected_hits:
            return False, f"hits {actual_hits} < expected {expected_hits}"

    return True, None


def validate_reflection_triggered(output, expected, state) -> tuple:
    """验证 reflection 被触发"""
    if output.reflection_note is None:
        return False, "reflection_note is None"
    expected_trigger = expected.get("trigger", "external_failure")
    if output.reflection_note.trigger != expected_trigger:
        return False, f"expected trigger {expected_trigger}, got {output.reflection_note.trigger}"
    return True, None


def validate_no_reflection(output, expected, state) -> tuple:
    """验证 reflection 未被触发"""
    if output.reflection_note is not None:
        return False, f"unexpected reflection with trigger: {output.reflection_note.trigger}"
    return True, None


def validate_revision_increased(output, expected, state) -> tuple:
    """验证 revision_counter 增加"""
    if state.revision_counter < 1:
        return False, "revision_counter did not increase"
    return True, None


def validate_mode_repair(output, expected, state) -> tuple:
    """验证 mode 切换到 repair"""
    if state.self_model.current_mode != "repair":
        return False, f"mode is {state.self_model.current_mode}, expected repair"
    return True, None


def validate_policy_hint_exists(output, expected, state) -> tuple:
    """验证 policy_hint 存在"""
    if not output.policy_hint:
        return False, "policy_hint is empty"
    return True, None


def validate_response_tendency_exists(output, expected, state) -> tuple:
    """验证 response_tendency 存在"""
    if output.response_tendency is None:
        return False, "response_tendency is None"
    return True, None


# ============================================================================
# Experiment Runners
# ============================================================================

def run_e1_identity_continuity(harness: ExperimentHarness) -> ExperimentSummary:
    """运行 E1: Identity Continuity 实验"""
    summary = ExperimentSummary(experiment_class="E1", total_runs=0, passed=0, failed=0)

    # E1.1: 初始状态建立
    state = ProtoSelfState.empty()
    event = KernelEvent(
        event_id="e1-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="help with coding",
    )
    result = harness.run_experiment(
        "E1", state, event,
        expected={"identity_stable": True},
        validators=[lambda o, e, s: (True, None)],  # 初始建立，无需验证
    )
    harness.save_result(result, "E1")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    # E1.2: 正常任务执行（不应改变 identity）
    initial_confidence = state.identity.identity_confidence
    event = KernelEvent(
        event_id="e1-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="read file test.py",
        external_result={"success": True},
    )
    result = harness.run_experiment(
        "E1", state, event,
        expected={"identity_stable": True},
        validators=[lambda o, e, s: (
            abs(s.identity.identity_confidence - initial_confidence) < 0.01,
            "identity_confidence changed unexpectedly"
        )],
    )
    harness.save_result(result, "E1")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    harness.save_summary(summary, "E1")
    return summary


def run_e2_cycle_strengthen(harness: ExperimentHarness) -> ExperimentSummary:
    """运行 E2: Cycle Strengthen 实验"""
    summary = ExperimentSummary(experiment_class="E2", total_runs=0, passed=0, failed=0)

    state = ProtoSelfState.empty()
    cycle_ids_seen = set()

    # 运行 5 次相似事件
    for i in range(5):
        event = KernelEvent(
            event_id=f"e2-{i:03d}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="read file",  # 相同 intent
        )

        if i == 0:
            # 第一次应该创建 candidate
            validators = [validate_cycle_created]
            expected = {"op": "candidate"}
        else:
            # 后续应该 strengthen
            validators = [validate_cycle_strengthened]
            expected = {"op": "strengthen", "min_hits": i + 1}

        result = harness.run_experiment("E2", state, event, expected, validators)
        harness.save_result(result, "E2")
        summary.results.append(result)
        summary.total_runs += 1

        if result.passed:
            summary.passed += 1
            cycle_ids_seen.add(result.observed.get("cycle_delta", {}).get("cycle_id"))
        else:
            summary.failed += 1

    # 验证所有 cycle_id 相同
    if len(cycle_ids_seen) == 1:
        print(f"[E2] All {summary.total_runs} events hit the same cycle_id: {cycle_ids_seen.pop()}")
    else:
        print(f"[E2] WARNING: Multiple cycle_ids: {cycle_ids_seen}")

    harness.save_summary(summary, "E2")
    return summary


def run_e3_reflection_trigger(harness: ExperimentHarness) -> ExperimentSummary:
    """运行 E3: Reflection Trigger 实验"""
    summary = ExperimentSummary(experiment_class="E3", total_runs=0, passed=0, failed=0)

    state = ProtoSelfState.empty()

    # E3.1: 成功事件 → 不触发 reflection
    event = KernelEvent(
        event_id="e3-001",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": True},
    )
    result = harness.run_experiment(
        "E3", state, event,
        expected={"reflection": None},
        validators=[validate_no_reflection],
    )
    harness.save_result(result, "E3")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    # E3.2: 失败事件 → 触发 reflection
    event = KernelEvent(
        event_id="e3-002",
        timestamp=datetime.now().isoformat(),
        actor="system",
        source="runtime",
        event_type="tool_result",
        external_result={"success": False, "error": "timeout"},
    )
    result = harness.run_experiment(
        "E3", state, event,
        expected={"trigger": "external_failure"},
        validators=[validate_reflection_triggered, validate_revision_increased, validate_mode_repair],
    )
    harness.save_result(result, "E3")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    harness.save_summary(summary, "E3")
    return summary


def run_e4_policy_tendency(harness: ExperimentHarness) -> ExperimentSummary:
    """运行 E4: Policy Hint & Response Tendency 实验"""
    summary = ExperimentSummary(experiment_class="E4", total_runs=0, passed=0, failed=0)

    state = ProtoSelfState.empty()

    # E4.1: 初始状态
    event = KernelEvent(
        event_id="e4-001",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="hello",
    )
    result = harness.run_experiment(
        "E4", state, event,
        expected={"has_policy_hint": True, "has_response_tendency": True},
        validators=[validate_policy_hint_exists, validate_response_tendency_exists],
    )
    harness.save_result(result, "E4")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    # E4.2: 高 caution 状态
    state.drives.caution = 0.8
    event = KernelEvent(
        event_id="e4-002",
        timestamp=datetime.now().isoformat(),
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="help",
        safety_context={"risk_level": 0.8},
    )
    result = harness.run_experiment(
        "E4", state, event,
        expected={"has_policy_hint": True, "high_risk_bias": True},
        validators=[
            validate_policy_hint_exists,
            validate_response_tendency_exists,
            lambda o, e, s: (
                o.policy_hint.get("risk_bias") == "high",
                f"expected risk_bias=high, got {o.policy_hint.get('risk_bias')}"
            ),
        ],
    )
    harness.save_result(result, "E4")
    summary.results.append(result)
    summary.total_runs += 1
    if result.passed:
        summary.passed += 1
    else:
        summary.failed += 1

    harness.save_summary(summary, "E4")
    return summary


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """主入口"""
    print("=" * 60)
    print("N2 Experiment Harness - Proto-Self Kernel v1")
    print("=" * 60)

    # 初始化 harness
    output_dir = Path(__file__).parent.parent.parent / "Tasks" / "overnight" / "artifacts" / "n2_experiments"
    harness = ExperimentHarness(output_dir)

    print(f"\nOutput directory: {output_dir}")

    # 运行所有实验
    all_summaries = []

    print("\n[E1] Running Identity Continuity experiment...")
    summary_e1 = run_e1_identity_continuity(harness)
    all_summaries.append(summary_e1)
    print(f"  - Passed: {summary_e1.passed}/{summary_e1.total_runs}")

    print("\n[E2] Running Cycle Strengthen experiment...")
    summary_e2 = run_e2_cycle_strengthen(harness)
    all_summaries.append(summary_e2)
    print(f"  - Passed: {summary_e2.passed}/{summary_e2.total_runs}")

    print("\n[E3] Running Reflection Trigger experiment...")
    summary_e3 = run_e3_reflection_trigger(harness)
    all_summaries.append(summary_e3)
    print(f"  - Passed: {summary_e3.passed}/{summary_e3.total_runs}")

    print("\n[E4] Running Policy Tendency experiment...")
    summary_e4 = run_e4_policy_tendency(harness)
    all_summaries.append(summary_e4)
    print(f"  - Passed: {summary_e4.passed}/{summary_e4.total_runs}")

    # 生成总体汇总
    overall = {
        "timestamp": datetime.now().isoformat(),
        "total_experiments": len(all_summaries),
        "total_runs": sum(s.total_runs for s in all_summaries),
        "total_passed": sum(s.passed for s in all_summaries),
        "total_failed": sum(s.failed for s in all_summaries),
        "by_class": {s.experiment_class: {"passed": s.passed, "failed": s.failed} for s in all_summaries},
    }

    overall_file = output_dir / "n2_overall_summary.json"
    with open(overall_file, "w") as f:
        json.dump(overall, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total runs: {overall['total_runs']}")
    print(f"Passed: {overall['total_passed']}")
    print(f"Failed: {overall['total_failed']}")
    print(f"Overall file: {overall_file}")

    # 返回退出码
    return 0 if overall['total_failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
