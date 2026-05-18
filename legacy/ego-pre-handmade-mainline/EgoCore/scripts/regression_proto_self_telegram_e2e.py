#!/usr/bin/env python3
"""
Proto-Self Kernel v1 - Telegram E2E Regression Test

验证项：
1. Cycle strengthen: 相似消息命中同一 cycle，hits 递增
2. External failure reflection: 工具失败触发 reflection
3. Revision counter: 状态修订计数增长

用法：
    python scripts/regression_proto_self_telegram_e2e.py

返回值：
    0 - 全部通过
    1 - 有失败项

依赖：
    - EgoCore 运行中 (telegram 模式)
    - 用户发送 4 条测试消息
    - 读取 artifacts/proto_self_mirror/state.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def load_state() -> Optional[Dict[str, Any]]:
    """加载 Proto-Self state mirror。"""
    state_path = Path("artifacts/proto_self_mirror/state.json")
    if not state_path.exists():
        print(f"❌ State file not found: {state_path}")
        return None

    with open(state_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_cycle(state: Dict, psi_bucket: str) -> Optional[Dict]:
    """查找指定 psi_bucket 的 cycle。"""
    cycles = state.get("cycle_store", {}).get("signatures", {})
    for cycle_id, cycle in cycles.items():
        if cycle.get("psi_bucket") == psi_bucket:
            return cycle
    return None


def check_cycle_strengthen(state: Dict) -> Dict[str, Any]:
    """
    验证 cycle strengthen。

    期望：
    - 存在 telegram:user_message:file_read cycle
    - hits >= 3 (baseline) + 3 (new) = 6
    - promoted = true
    """
    result = {
        "test": "cycle_strengthen",
        "passed": False,
        "details": {}
    }

    cycle = find_cycle(state, "telegram:user_message:file_read")
    if not cycle:
        result["details"]["error"] = "file_read cycle not found"
        return result

    hits = cycle.get("hits", 0)
    promoted = cycle.get("promoted", False)
    strength = cycle.get("strength", 0.0)

    result["details"] = {
        "cycle_id": cycle.get("cycle_id"),
        "hits": hits,
        "strength": strength,
        "promoted": promoted
    }

    # 验证条件
    if hits < 6:
        result["details"]["error"] = f"hits too low: {hits} < 6 (expected baseline 3 + new 3)"
        return result

    if not promoted:
        result["details"]["error"] = "cycle not promoted"
        return result

    result["passed"] = True
    return result


def check_external_failure_reflection(state: Dict) -> Dict[str, Any]:
    """
    验证 external failure reflection。

    期望：
    - episodic_trace 中有 external_outcome_type=failure 的记录
    - external_result.success = false
    """
    result = {
        "test": "external_failure_reflection",
        "passed": False,
        "details": {}
    }

    trace = state.get("episodic_trace", [])
    failure_events = []

    for event in trace:
        perceived = event.get("perceived_summary", {})
        external_result = event.get("external_result")

        if perceived.get("external_outcome_type") == "failure":
            failure_events.append({
                "event_id": event.get("event_id"),
                "external_result": external_result
            })

    result["details"]["failure_events_count"] = len(failure_events)

    if not failure_events:
        result["details"]["error"] = "no failure events found in trace"
        return result

    # 检查是否有 external_result
    has_external_result = any(
        e.get("external_result") is not None
        for e in failure_events
    )

    if not has_external_result:
        result["details"]["error"] = "failure events but no external_result"
        return result

    # 检查是否有 success=false
    has_failure = any(
        e.get("external_result", {}).get("success") is False
        for e in failure_events
    )

    if not has_failure:
        result["details"]["error"] = "no success=false in external_result"
        return result

    result["details"]["failure_events"] = failure_events[-3:]  # 最近 3 个
    result["passed"] = True
    return result


def check_revision_counter(state: Dict) -> Dict[str, Any]:
    """
    验证 revision counter 增长。

    期望：
    - revision_counter >= 30 (本次测试后)
    """
    result = {
        "test": "revision_counter",
        "passed": False,
        "details": {}
    }

    revision = state.get("revision_counter", 0)
    result["details"]["revision_counter"] = revision

    if revision < 30:
        result["details"]["error"] = f"revision_counter too low: {revision} < 30"
        return result

    result["passed"] = True
    return result


def main():
    print("=" * 60)
    print("Proto-Self Kernel v1 - Telegram E2E Regression Test")
    print("=" * 60)
    print()

    # 加载状态
    state = load_state()
    if not state:
        print("❌ Failed to load state")
        return 1

    # 执行测试
    tests = [
        check_cycle_strengthen(state),
        check_external_failure_reflection(state),
        check_revision_counter(state)
    ]

    # 输出结果
    all_passed = True
    for test in tests:
        status = "✅ PASS" if test["passed"] else "❌ FAIL"
        print(f"{status}: {test['test']}")

        for key, value in test["details"].items():
            if key == "error":
                print(f"    Error: {value}")
            else:
                print(f"    {key}: {value}")
        print()

        if not test["passed"]:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("✅ All tests passed")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
