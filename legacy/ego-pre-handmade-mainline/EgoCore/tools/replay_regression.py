"""
Replay Regression Suite

将 replay 从演示升级为回归保护。
固定 canonical cases，确保关键结构稳定。
"""

import json
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CanonicalCase:
    """标准化重放测试用例"""
    case_id: str
    description: str
    fixed_input: Dict[str, Any]
    expected_keys: List[str]
    expected_field_patterns: Dict[str, Any]
    assertions: List[Dict[str, Any]]


# 5 组 Canonical Replay Cases
CANONICAL_CASES: List[CanonicalCase] = [
    # Case 1: 用户消息 - 基本交互
    CanonicalCase(
        case_id="case_001_user_message",
        description="基本用户消息交互",
        fixed_input={
            "schema_version": "1.0.0",
            "event_id": "evt_canonical_001",
            "timestamp": "2026-03-16T00:00:00Z",
            "actor": {
                "actor_id": "user_canonical",
                "actor_type": "user",
                "display_name": "Canonical User"
            },
            "source": {
                "channel": "telegram",
                "surface": "telegram",
                "session_id": "session_canonical_001"
            },
            "event_type": "user_message",
            "user_intent": {
                "primary_intent": "greeting",
                "confidence": 0.95
            },
            "safety_context": {
                "risk_level": "low",
                "flags": []
            }
        },
        expected_keys=[
            "output_id", "timestamp", "event_id_ref",
            "confidence_metadata", "appraisal_state_delta",
            "policy_hint", "response_tendency"
        ],
        expected_field_patterns={
            "output_id": r"^out_",
            "event_id_ref": "evt_canonical_001",
            "confidence_metadata.overall_confidence": {"type": "number", "min": 0, "max": 1}
        },
        assertions=[
            {"field": "output_id", "check": "not_empty"},
            {"field": "event_id_ref", "check": "equals", "value": "evt_canonical_001"},
            {"field": "confidence_metadata.overall_confidence", "check": "range", "min": 0, "max": 1}
        ]
    ),

    # Case 2: 任务完成 - 正向反馈
    CanonicalCase(
        case_id="case_002_task_completed",
        description="任务完成后的正向状态",
        fixed_input={
            "schema_version": "1.0.0",
            "event_id": "evt_canonical_002",
            "timestamp": "2026-03-16T01:00:00Z",
            "actor": {
                "actor_id": "system",
                "actor_type": "system"
            },
            "source": {
                "channel": "internal",
                "surface": "runtime"
            },
            "event_type": "task_completed",
            "user_intent": {
                "primary_intent": "notification"
            },
            "safety_context": {
                "risk_level": "low"
            },
            "task_context": {
                "task_id": "task_canonical_001",
                "task_status": "completed",
                "task_goal": "Canonical task"
            },
            "external_result": {
                "operation_type": "task",
                "success": True,
                "result_summary": "Task completed successfully"
            }
        },
        expected_keys=[
            "output_id", "event_id_ref", "confidence_metadata",
            "appraisal_state_delta"
        ],
        expected_field_patterns={
            "appraisal_state_delta.valence": {"check": "gte", "value": 0}
        },
        assertions=[
            {"field": "event_id_ref", "check": "equals", "value": "evt_canonical_002"}
        ]
    ),

    # Case 3: 任务失败 - 负向状态
    CanonicalCase(
        case_id="case_003_task_failed",
        description="任务失败后的负向状态",
        fixed_input={
            "schema_version": "1.0.0",
            "event_id": "evt_canonical_003",
            "timestamp": "2026-03-16T02:00:00Z",
            "actor": {
                "actor_id": "system",
                "actor_type": "system"
            },
            "source": {
                "channel": "internal",
                "surface": "runtime"
            },
            "event_type": "task_failed",
            "user_intent": {
                "primary_intent": "notification"
            },
            "safety_context": {
                "risk_level": "medium",
                "flags": ["failure"]
            },
            "task_context": {
                "task_id": "task_canonical_002",
                "task_status": "failed"
            }
        },
        expected_keys=[
            "output_id", "event_id_ref", "confidence_metadata"
        ],
        expected_field_patterns={
            "appraisal_state_delta.valence": {"check": "lte", "value": 0}
        },
        assertions=[
            {"field": "event_id_ref", "check": "equals", "value": "evt_canonical_003"}
        ]
    ),

    # Case 4: 工具调用 - 操作记录
    CanonicalCase(
        case_id="case_004_tool_invoked",
        description="工具调用事件",
        fixed_input={
            "schema_version": "1.0.0",
            "event_id": "evt_canonical_004",
            "timestamp": "2026-03-16T03:00:00Z",
            "actor": {
                "actor_id": "agent_canonical",
                "actor_type": "agent"
            },
            "source": {
                "channel": "internal",
                "surface": "runtime"
            },
            "event_type": "tool_invoked",
            "user_intent": {
                "primary_intent": "file_read"
            },
            "safety_context": {
                "risk_level": "low",
                "gate_status": {
                    "gate_a": "passed",
                    "gate_b": "passed",
                    "gate_c": "passed"
                }
            },
            "external_result": {
                "operation_type": "file_read",
                "success": True
            }
        },
        expected_keys=[
            "output_id", "event_id_ref", "confidence_metadata"
        ],
        expected_field_patterns={
            "policy_hint.preferred_action_type": {"check": "one_of", "values": ["respond", "act", "wait", "ask_clarify"]}
        },
        assertions=[
            {"field": "event_id_ref", "check": "equals", "value": "evt_canonical_004"}
        ]
    ),

    # Case 5: 高风险操作 - 安全检查
    CanonicalCase(
        case_id="case_005_high_risk",
        description="高风险操作检测",
        fixed_input={
            "schema_version": "1.0.0",
            "event_id": "evt_canonical_005",
            "timestamp": "2026-03-16T04:00:00Z",
            "actor": {
                "actor_id": "user_canonical",
                "actor_type": "user"
            },
            "source": {
                "channel": "telegram",
                "surface": "telegram"
            },
            "event_type": "user_command",
            "user_intent": {
                "primary_intent": "destructive_operation",
                "confidence": 0.6
            },
            "safety_context": {
                "risk_level": "high",
                "flags": ["destructive", "requires_approval"],
                "constraints_applied": ["blocked_without_approval"]
            }
        },
        expected_keys=[
            "output_id", "event_id_ref", "confidence_metadata"
        ],
        expected_field_patterns={
            "confidence_metadata.overall_confidence": {"type": "number"}
        },
        assertions=[
            {"field": "event_id_ref", "check": "equals", "value": "evt_canonical_005"}
        ]
    ),
]


class ReplayRegression:
    """重放回归测试套件"""

    def __init__(self, artifacts_dir: Optional[Path] = None):
        """
        初始化回归套件

        Args:
            artifacts_dir: artifact 存储目录
        """
        self.artifacts_dir = artifacts_dir or Path("./artifacts/replay_regression")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.results: List[Dict[str, Any]] = []

    def run_all(self, adapter) -> Dict[str, Any]:
        """
        运行所有 canonical cases

        Args:
            adapter: OpenEmotionAdapter 实例

        Returns:
            回归测试结果
        """
        self.results = []
        passed = 0
        failed = 0

        for case in CANONICAL_CASES:
            result = self._run_case(case, adapter)
            self.results.append(result)

            if result["status"] == "PASS":
                passed += 1
            else:
                failed += 1

        # 保存结果
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_cases": len(CANONICAL_CASES),
            "passed": passed,
            "failed": failed,
            "status": "PASS" if failed == 0 else "FAIL",
            "cases": self.results,
        }

        report_file = self.artifacts_dir / "REPLAY_REGRESSION_REPORT.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        # 保存各 case 的 artifact
        for case, result in zip(CANONICAL_CASES, self.results):
            case_file = self.artifacts_dir / f"{case.case_id}.json"
            with open(case_file, 'w') as f:
                json.dump({
                    "case_id": case.case_id,
                    "description": case.description,
                    "input": case.fixed_input,
                    "output": result["output"],
                    "assertions": result["assertions"],
                }, f, indent=2)

        return report

    def _run_case(self, case: CanonicalCase, adapter) -> Dict[str, Any]:
        """运行单个 case"""
        # 处理事件
        output = adapter.process_event(case.fixed_input)

        # 检查必需键
        missing_keys = []
        for key in case.expected_keys:
            if key not in output:
                missing_keys.append(key)

        # 执行断言
        assertion_results = []
        for assertion in case.assertions:
            result = self._check_assertion(output, assertion)
            assertion_results.append(result)

        all_assertions_passed = all(r["passed"] for r in assertion_results)

        # 判定
        if missing_keys:
            status = "FAIL"
        elif not all_assertions_passed:
            status = "FAIL"
        else:
            status = "PASS"

        return {
            "case_id": case.case_id,
            "status": status,
            "missing_keys": missing_keys,
            "assertions": assertion_results,
            "output": output,
        }

    def _check_assertion(self, output: Dict[str, Any], assertion: Dict[str, Any]) -> Dict[str, Any]:
        """检查断言"""
        field = assertion["field"]
        check = assertion["check"]

        # 获取字段值
        value = self._get_nested_value(output, field)

        passed = False
        message = ""

        if check == "not_empty":
            passed = value is not None and value != ""
            message = f"Value: {value}"

        elif check == "equals":
            expected = assertion["value"]
            passed = value == expected
            message = f"Expected: {expected}, Got: {value}"

        elif check == "range":
            min_val = assertion.get("min", float("-inf"))
            max_val = assertion.get("max", float("inf"))
            passed = isinstance(value, (int, float)) and min_val <= value <= max_val
            message = f"Value: {value}, Range: [{min_val}, {max_val}]"

        elif check == "gte":
            threshold = assertion["value"]
            passed = isinstance(value, (int, float)) and value >= threshold
            message = f"Value: {value}, Threshold: {threshold}"

        elif check == "lte":
            threshold = assertion["value"]
            passed = isinstance(value, (int, float)) and value <= threshold
            message = f"Value: {value}, Threshold: {threshold}"

        elif check == "one_of":
            allowed = assertion["values"]
            passed = value in allowed
            message = f"Value: {value}, Allowed: {allowed}"

        else:
            message = f"Unknown check: {check}"

        return {
            "field": field,
            "check": check,
            "passed": passed,
            "message": message,
        }

    @staticmethod
    def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
        """获取嵌套字段值"""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value


def run_regression(adapter, artifacts_dir: Path = None) -> Dict[str, Any]:
    """
    运行回归测试

    Args:
        adapter: OpenEmotionAdapter 实例
        artifacts_dir: artifact 目录

    Returns:
        测试报告
    """
    suite = ReplayRegression(artifacts_dir=artifacts_dir)
    return suite.run_all(adapter)
