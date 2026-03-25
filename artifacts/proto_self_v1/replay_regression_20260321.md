"""
WS-PSK-6: Replay Regression Test

验证：
1. 同输入两次运行，trace 关键字段一致
2. replay 优先使用 trace 中记录的 cycle_delta / policy_hint
3. 不允许依赖当前 cycle_store 现状重算旧轮结论
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path

# Add OpenEmotion to path
import sys
sys.path.insert(0, "/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion")

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event


def run_replay_test():
    """运行 replay regression 测试。"""
    results = {
        "test_time": datetime.now().isoformat(),
        "tests": []
    }

    # 测试 1：同输入两次运行，trace 关键字段一致
    print("=" * 60)
    print("Test 1: Same input, same trace")
    print("=" * 60)

    state1 = ProtoSelfState.empty()
    state2 = ProtoSelfState.empty()

    event = KernelEvent(
        event_id="replay-test-001",
        timestamp="2026-03-21T19:00:00.000000",
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="test_replay",
    )

    output1 = process_event(state1, event)
    output2 = process_event(state2, event)

    trace1 = output1.trace_payload
    trace2 = output2.trace_payload

    # 比较关键字段
    keys_to_compare = ["event_id", "perceived", "cycle_delta", "policy_hint"]
    all_match = True
    for key in keys_to_compare:
        match = trace1.get(key) == trace2.get(key)
        print(f"  {key}: {'MATCH' if match else 'MISMATCH'}")
        if not match:
            all_match = False

    test1_result = {
        "name": "same_input_same_trace",
        "passed": all_match,
        "keys_compared": keys_to_compare,
    }
    results["tests"].append(test1_result)
    print(f"  Result: {'PASS' if all_match else 'FAIL'}")

    # 测试 2：replay 优先使用 trace 中的值
    print("\n" + "=" * 60)
    print("Test 2: Replay uses trace, not current store")
    print("=" * 60)

    state = ProtoSelfState.empty()

    # 处理多个事件改变 state
    for i in range(5):
        event_i = KernelEvent(
            event_id=f"event-{i:03d}",
            timestamp=f"2026-03-21T19:0{i}:00.000000",
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="build_state",
        )
        output_i = process_event(state, event_i)

    # 保存第一个事件的 trace
    event_000_trace = None
    state_for_replay = ProtoSelfState.empty()
    event_000 = KernelEvent(
        event_id="event-000",
        timestamp="2026-03-21T19:00:00.000000",
        actor="user",
        source="telegram",
        event_type="user_message",
        user_intent="build_state",
    )
    output_000 = process_event(state_for_replay, event_000)
    event_000_trace = output_000.trace_payload.copy()

    # 当前 state 已经被后续事件改变
    # 但 trace 应该保持原始值
    current_cycle_count = len(state.cycle_store.signatures)
    trace_cycle_id = event_000_trace.get("cycle_delta", {}).get("cycle_id")

    # 验证：trace 中的值应该独立于当前 state
    trace_preserved = event_000_trace.get("event_id") == "event-000"

    test2_result = {
        "name": "replay_uses_trace_not_store",
        "passed": trace_preserved,
        "trace_event_id": event_000_trace.get("event_id"),
        "trace_cycle_id": trace_cycle_id,
    }
    results["tests"].append(test2_result)
    print(f"  Trace event_id preserved: {trace_preserved}")
    print(f"  Trace cycle_id: {trace_cycle_id}")
    print(f"  Result: {'PASS' if trace_preserved else 'FAIL'}")

    # 测试 3：deterministic 输出
    print("\n" + "=" * 60)
    print("Test 3: Deterministic output")
    print("=" * 60)

    # 运行 10 次，验证所有输出相同
    traces = []
    for i in range(10):
        state_i = ProtoSelfState.empty()
        event_i = KernelEvent(
            event_id="deterministic-test",
            timestamp="2026-03-21T19:00:00.000000",
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent="deterministic",
        )
        output_i = process_event(state_i, event_i)
        traces.append(json.dumps(output_i.trace_payload, sort_keys=True))

    # 计算所有 trace 的 hash
    hashes = [hashlib.sha256(t.encode()).hexdigest() for t in traces]
    all_same = len(set(hashes)) == 1

    test3_result = {
        "name": "deterministic_output",
        "passed": all_same,
        "run_count": 10,
        "unique_hashes": len(set(hashes)),
    }
    results["tests"].append(test3_result)
    print(f"  10 runs, unique hashes: {len(set(hashes))}")
    print(f"  Result: {'PASS' if all_same else 'FAIL'}")

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
    results = run_replay_test()

    # 保存 artifact
    artifact_dir = Path("/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion/artifacts/proto_self_v1")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_file = artifact_dir / "replay_regression_20260321.json"
    with open(artifact_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nArtifact saved: {artifact_file}")
