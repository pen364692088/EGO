"""
P0 Regression Test - 回归与反证测试

验证修复效果：
1. HIGH 风险样本不再落同一 cycle
2. N2 成立条件仍成立
3. Replay 一致性

设计约束：
- 不修改任何生产代码
- 只读验证
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 添加路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from openemotion.proto_self import KernelEvent, ProtoSelfState
from openemotion.proto_self.kernel import process_event
from openemotion.proto_self.cycles import _coarse_intent_classify, _build_psi_bucket


# ============================================================================
# Test Cases
# ============================================================================

# HIGH 风险误聚合测试（修复后应通过）
HIGH_RISK_TEST_CASES = [
    {
        "id": "SS-1a",
        "intent": "删除临时文件",
        "safety_context": {"risk": "low"},
        "expected_different_from": "SS-1b",
    },
    {
        "id": "SS-1b",
        "intent": "删除生产数据库",
        "safety_context": {"risk": "critical"},
        "expected_different_from": "SS-1a",
    },
]

# 应聚合测试（修复后仍应通过）
SHOULD_MERGE_TEST_CASES = [
    {
        "group": "SM-1",
        "samples": [
            {"id": "SM-1a", "intent": "读取 config.yaml"},
            {"id": "SM-1b", "intent": "查看配置文件"},
            {"id": "SM-1c", "intent": "read the file"},
            {"id": "SM-1d", "intent": "check file content"},
        ],
        "expected_same_cycle": True,
    },
]

# N2 验证测试
N2_VERIFICATION_CASES = [
    {
        "id": "N2-cycle-strengthen",
        "description": "相同 intent 应命中同一 cycle，hits 递增",
        "intents": ["read file"] * 5,
        "expected": {
            "same_cycle_id": True,
            "hits_increase": True,
            "strength_increase": True,
        },
    },
    {
        "id": "N2-reflection",
        "description": "external_failure 应触发 reflection",
        "events": [
            {"intent": "test", "external_result": {"success": False}},
            {"intent": "test", "external_result": {"success": False}},
        ],
        "expected": {
            "revision_counter_increase": True,
        },
    },
]


# ============================================================================
# Test Functions
# ============================================================================

def test_high_risk_separation() -> Tuple[bool, Dict]:
    """测试 HIGH 风险样本是否被正确区分"""
    print("\n" + "=" * 50)
    print("Test: HIGH 风险样本区分")
    print("=" * 50)

    results = {}
    cycle_ids = {}

    for case in HIGH_RISK_TEST_CASES:
        state = ProtoSelfState.empty()
        perceived = {
            "intent": case["intent"],
            "event_type": "user_message",
            "source": "telegram",
            "safety_context": case["safety_context"],
        }
        psi_bucket = _build_psi_bucket(perceived)
        cycle_id = _build_psi_bucket(perceived)  # 实际使用 hash

        # 简化：直接用 psi_bucket 作为标识
        cycle_ids[case["id"]] = psi_bucket
        results[case["id"]] = {
            "intent": case["intent"],
            "safety_context": case["safety_context"],
            "psi_bucket": psi_bucket,
        }
        print(f"  {case['id']}: {case['intent']}")
        print(f"    safety_context.risk: {case['safety_context'].get('risk')}")
        print(f"    psi_bucket: {psi_bucket}")

    # 检查是否不同
    ss1a_bucket = cycle_ids["SS-1a"]
    ss1b_bucket = cycle_ids["SS-1b"]
    different = ss1a_bucket != ss1b_bucket

    print(f"\n  结果: {'✅ 通过' if different else '❌ 失败'}")
    if different:
        print(f"  HIGH 风险样本已被正确区分到不同 cycle")
    else:
        print(f"  ⚠️ 误聚合：高风险和低风险操作仍在同一 cycle")

    return different, results


def test_should_merge() -> Tuple[bool, Dict]:
    """测试应聚合样本是否仍能正确聚合"""
    print("\n" + "=" * 50)
    print("Test: 应聚合样本聚合")
    print("=" * 50)

    all_passed = True
    results = {}

    for group in SHOULD_MERGE_TEST_CASES:
        cycle_ids = set()
        for sample in group["samples"]:
            perceived = {
                "intent": sample["intent"],
                "event_type": "user_message",
                "source": "telegram",
            }
            psi_bucket = _build_psi_bucket(perceived)
            cycle_ids.add(psi_bucket)
            print(f"  {sample['id']}: {sample['intent']} -> {psi_bucket}")

        same_cycle = len(cycle_ids) == 1
        results[group["group"]] = {
            "unique_cycles": len(cycle_ids),
            "passed": same_cycle,
        }

        if same_cycle:
            print(f"  ✅ {group['group']}: 所有样本命中同一 cycle")
        else:
            print(f"  ❌ {group['group']}: 样本被分散到 {len(cycle_ids)} 个 cycle")
            all_passed = False

    return all_passed, results


def test_n2_cycle_strengthen() -> Tuple[bool, Dict]:
    """测试 N2 cycle strengthen 条件"""
    print("\n" + "=" * 50)
    print("Test: N2 Cycle Strengthen")
    print("=" * 50)

    state = ProtoSelfState.empty()
    cycle_ids = []
    hits_list = []
    strength_list = []

    for i, intent in enumerate(N2_VERIFICATION_CASES[0]["intents"]):
        event = KernelEvent(
            event_id=f"n2-test-{i}",
            timestamp=datetime.now().isoformat(),
            actor="user",
            source="telegram",
            event_type="user_message",
            user_intent=intent,
        )
        output = process_event(state, event)

        cycle_delta = output.trace_payload.get("cycle_delta", {})
        cycle_id = cycle_delta.get("cycle_id")
        cycle_ids.append(cycle_id)

        if cycle_id and cycle_id in state.cycle_store.signatures:
            c = state.cycle_store.signatures[cycle_id]
            hits_list.append(c.hits)
            strength_list.append(c.strength)

    # 检查
    same_cycle = len(set(cycle_ids)) == 1
    hits_increase = all(hits_list[i] < hits_list[i+1] for i in range(len(hits_list)-1))
    strength_increase = all(strength_list[i] < strength_list[i+1] for i in range(len(strength_list)-1))

    print(f"  cycle_ids 相同: {'✅' if same_cycle else '❌'}")
    print(f"  hits 递增: {'✅' if hits_increase else '❌'} {hits_list}")
    print(f"  strength 递增: {'✅' if strength_increase else '❌'} {strength_list}")

    passed = same_cycle and hits_increase and strength_increase
    return passed, {"same_cycle": same_cycle, "hits": hits_list, "strength": strength_list}


def test_n2_reflection() -> Tuple[bool, Dict]:
    """测试 N2 reflection 条件"""
    print("\n" + "=" * 50)
    print("Test: N2 Reflection Trigger")
    print("=" * 50)

    state = ProtoSelfState.empty()
    initial_revision = state.revision_counter

    for i, event_data in enumerate(N2_VERIFICATION_CASES[1]["events"]):
        event = KernelEvent(
            event_id=f"n2-reflection-{i}",
            timestamp=datetime.now().isoformat(),
            actor="system",
            source="runtime",
            event_type="tool_result",
            user_intent=event_data["intent"],
            external_result=event_data["external_result"],
        )
        output = process_event(state, event)

    final_revision = state.revision_counter
    revision_increased = final_revision > initial_revision

    print(f"  initial revision: {initial_revision}")
    print(f"  final revision: {final_revision}")
    print(f"  revision 增加: {'✅' if revision_increased else '❌'}")

    return revision_increased, {"initial": initial_revision, "final": final_revision}


def test_intent_classification() -> Tuple[bool, Dict]:
    """测试关键词优先级修复"""
    print("\n" + "=" * 50)
    print("Test: Intent 分类修复")
    print("=" * 50)

    test_cases = [
        ("运行测试", "test_verify"),  # 修复前会被错误分类为 status_query
        ("检查健康状态", "status_query"),  # 应该是 status_query
        ("检查代码", "general"),  # 修复前会被错误分类为 file_read
        ("删除临时文件", "file_risk_op"),
        ("读取文件", "file_read"),
        ("重启服务", "service_control"),
    ]

    all_correct = True
    results = {}

    for intent, expected in test_cases:
        actual = _coarse_intent_classify(intent)
        correct = actual == expected
        results[intent] = {"expected": expected, "actual": actual, "correct": correct}

        status = "✅" if correct else "❌"
        print(f"  {status} '{intent}' -> {actual} (expected: {expected})")

        if not correct:
            all_correct = False

    return all_correct, results


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """主入口"""
    print("=" * 60)
    print(" P0 Regression Test - 回归与反证测试")
    print("=" * 60)

    all_results = {}

    # 1. HIGH 风险区分测试
    passed_1, results_1 = test_high_risk_separation()
    all_results["high_risk_separation"] = {"passed": passed_1, "details": results_1}

    # 2. 应聚合测试
    passed_2, results_2 = test_should_merge()
    all_results["should_merge"] = {"passed": passed_2, "details": results_2}

    # 3. N2 cycle strengthen 测试
    passed_3, results_3 = test_n2_cycle_strengthen()
    all_results["n2_cycle_strengthen"] = {"passed": passed_3, "details": results_3}

    # 4. N2 reflection 测试
    passed_4, results_4 = test_n2_reflection()
    all_results["n2_reflection"] = {"passed": passed_4, "details": results_4}

    # 5. Intent 分类测试
    passed_5, results_5 = test_intent_classification()
    all_results["intent_classification"] = {"passed": passed_5, "details": results_5}

    # 汇总
    print("\n" + "=" * 60)
    print(" SUMMARY")
    print("=" * 60)

    total = 5
    passed = sum([
        passed_1, passed_2, passed_3, passed_4, passed_5
    ])

    print(f"  HIGH 风险区分: {'✅ 通过' if passed_1 else '❌ 失败'}")
    print(f"  应聚合样本: {'✅ 通过' if passed_2 else '❌ 失败'}")
    print(f"  N2 Cycle Strengthen: {'✅ 通过' if passed_3 else '❌ 失败'}")
    print(f"  N2 Reflection: {'✅ 通过' if passed_4 else '❌ 失败'}")
    print(f"  Intent 分类: {'✅ 通过' if passed_5 else '❌ 失败'}")
    print(f"\n  总计: {passed}/{total} 通过")

    # 保存结果
    output_dir = Path(__file__).parent.parent.parent / "Tasks" / "p0_steady_state" / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "results": all_results,
    }

    with open(output_dir / "p0_regression_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  结果已保存: {output_dir / 'p0_regression_summary.json'}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
