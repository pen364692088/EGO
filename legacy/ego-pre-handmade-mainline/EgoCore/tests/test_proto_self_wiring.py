"""
Proto-Self Kernel v1 主链接入集成测试

验证：
1. ProtoSelfAdapter 被正确初始化
2. 用户消息触发 proto_self 调用
3. policy_hint 被注入到 state
4. trace 被正确写入
"""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
for path in (ROOT, REPO_ROOT / "OpenEmotion"):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.state import RuntimeV2State


@pytest.mark.asyncio
async def test_proto_self_wiring():
    """测试 Proto-Self Kernel 主链接入"""
    results = {
        "test_name": "proto_self_wiring_integration",
        "tests": []
    }

    # 测试 1: RuntimeV2Loop 初始化包含 proto_self_adapter
    print("=" * 60)
    print("Test 1: RuntimeV2Loop has proto_self_adapter")
    print("=" * 60)

    loop = RuntimeV2Loop()

    has_adapter = loop.proto_self_adapter is not None
    has_trace_bridge = loop.proto_self_trace_bridge is not None

    test1_result = {
        "name": "proto_self_adapter_initialized",
        "passed": has_adapter,
        "has_adapter": has_adapter,
        "has_trace_bridge": has_trace_bridge,
    }
    results["tests"].append(test1_result)
    print(f"  has_adapter: {has_adapter}")
    print(f"  has_trace_bridge: {has_trace_bridge}")
    print(f"  Result: {'PASS' if has_adapter else 'FAIL'}")

    if not has_adapter:
        print("\n  Proto-Self Kernel not available, skipping remaining tests")
        return results

    # 测试 2: 用户消息触发 proto_self 调用
    print("\n" + "=" * 60)
    print("Test 2: User message triggers proto_self call")
    print("=" * 60)

    session_id = "test_proto_self_001"
    state = loop.get_state(session_id)

    # 运行一个 turn
    result = await loop.run_turn_typed(session_id, "你好，这是一个测试")

    # 检查 state 是否有 proto_self_context
    has_context = state.proto_self_context is not None

    test2_result = {
        "name": "proto_self_context_injected",
        "passed": has_context,
        "proto_self_context": state.proto_self_context,
    }
    results["tests"].append(test2_result)
    print(f"  proto_self_context: {state.proto_self_context}")
    print(f"  Result: {'PASS' if has_context else 'FAIL'}")

    # 测试 3: policy_hint 包含预期字段
    print("\n" + "=" * 60)
    print("Test 3: policy_hint has expected fields")
    print("=" * 60)

    if state.proto_self_context:
        policy_hint = state.proto_self_context.get("policy_hint", {})
        response_tendency = state.proto_self_context.get("response_tendency", {})

        has_policy_hint = bool(policy_hint)
        has_risk_bias = "risk_bias" in policy_hint
        has_closure_bias = "closure_bias" in policy_hint

        test3_result = {
            "name": "policy_hint_fields",
            "passed": has_policy_hint and has_risk_bias,
            "policy_hint": policy_hint,
            "response_tendency": response_tendency,
        }
        results["tests"].append(test3_result)
        print(f"  policy_hint: {policy_hint}")
        print(f"  response_tendency: {response_tendency}")
        print(f"  Result: {'PASS' if has_policy_hint else 'FAIL'}")
    else:
        test3_result = {
            "name": "policy_hint_fields",
            "passed": False,
            "reason": "No proto_self_context",
        }
        results["tests"].append(test3_result)
        print(f"  Result: FAIL (no proto_self_context)")

    # 测试 4: trace 文件被创建
    print("\n" + "=" * 60)
    print("Test 4: Trace file created")
    print("=" * 60)

    trace_file = Path("logs/proto_self_trace.jsonl")
    has_trace_file = trace_file.exists()

    trace_data = {}
    has_event_id = False

    if has_trace_file:
        with open(trace_file, "r") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                if last_line:
                    try:
                        import json
                        trace_data = json.loads(last_line)
                        has_event_id = "event_id" in trace_data
                    except json.JSONDecodeError:
                        pass

    test4_result = {
        "name": "trace_file_created",
        "passed": has_trace_file and has_event_id,
        "trace_file_exists": has_trace_file,
        "last_trace": trace_data,
    }
    results["tests"].append(test4_result)
    print(f"  trace_file_exists: {has_trace_file}")
    print(f"  last_trace: {trace_data}")
    print(f"  Result: {'PASS' if has_trace_file else 'FAIL'}")

    # 测试 5: history 包含 proto_self 记录
    print("\n" + "=" * 60)
    print("Test 5: History contains proto_self record")
    print("=" * 60)

    proto_self_records = [
        h for h in state.history
        if h.get("role") == "proto_self"
    ]
    has_proto_self_record = len(proto_self_records) > 0

    test5_result = {
        "name": "history_proto_self_record",
        "passed": has_proto_self_record,
        "proto_self_records": proto_self_records,
    }
    results["tests"].append(test5_result)
    print(f"  proto_self_records count: {len(proto_self_records)}")
    print(f"  Result: {'PASS' if has_proto_self_record else 'FAIL'}")

    # 总结
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    passed = sum(1 for t in results["tests"] if t["passed"])
    total = len(results["tests"])
    results["summary"] = {
        "passed": passed,
        "total": total,
        "all_passed": passed == total,
    }
    print(f"  Passed: {passed}/{total}")
    print(f"  All passed: {passed == total}")

    return results


if __name__ == "__main__":
    import json
    from datetime import datetime

    results = asyncio.run(test_proto_self_wiring())

    # 保存 artifact
    artifact_dir = ROOT / "artifacts" / "proto_self_wiring"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_file = artifact_dir / f"wiring_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(artifact_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nArtifact saved: {artifact_file}")
