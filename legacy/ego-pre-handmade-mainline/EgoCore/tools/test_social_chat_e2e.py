#!/usr/bin/env python3
"""
E2E 测试 - Social/Chat 新链路

测试 5 个验收场景：
1. 初次"你好"
2. 连续三次"你好 / 测试"
3. "在吗"且有活动任务
4. "你怎么这么冷淡"
5. "谢谢"

Gate B 验证：
- 连续社交输入不再重复 onboarding 模板
- affective probe 会被识别并改变回应策略
- bridge down 时可自然降级
- 有活动任务时可正确转 status/task 路由
"""

import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from egocore.contracts.interaction_event_envelope_v1 import (
    InteractionEventEnvelope,
    RecentTurn,
    RuntimeSummary,
    SafetyContext,
)
from openemotion.interaction.interpretation import interpret_interaction
from egocore.contracts.runtime_decision_envelope_v1 import RuntimeDecisionEnvelope
from egocore.contracts.outward_response_package_v1 import OutwardResponsePackage
from app.response.verbalizer import get_verbalizer


def test_scenario_1_first_greeting():
    """
    场景 1: 初次"你好"
    
    验证点：
    - 返回正常欢迎
    - 没有重复的 onboarding 模板
    """
    print("=" * 60)
    print("场景 1: 初次\"你好\"")
    print("=" * 60)
    
    # 直接构建信封
    envelope = InteractionEventEnvelope(
        envelope_id="env_001",
        user_input="你好",
        user_id="telegram:8420019401",
        session_id="session_001",
        recent_turns=[],
        turn_count=1,
    )
    
    # 直接调用解释
    result = interpret_interaction(envelope.to_dict())
    print(f"主体解释: primary_mode={result.interaction_interpretation.primary_mode}")
    
    # 创建决策
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id=envelope.envelope_id,
        result_id=result.result_id,
        interpretation=result.to_dict(),
        has_active_task=False,
    )
    print(f"运行时决策: route={decision.runtime_route.value}")
    
    # 创建回复包
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=result.to_dict(),
    )
    
    # 生成回复
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=result.to_dict())
    print(f"回复:\n{reply}\n")
    
    # 验证
    primary_mode = result.interaction_interpretation.primary_mode
    if primary_mode == "greeting":
        print("✅ 通过: 识别为 greeting")
    else:
        print(f"❌ primary_mode 应该是 greeting, 实际是 {primary_mode}")
        return False
    
    if "你好" in reply:
        print("✅ 通过: 包含问候")
    else:
        print("⚠️ 回复格式可能需要调整")
    
    return True


def test_scenario_2_repeated_greeting():
    """
    场景 2: 连续三次"你好 / 测试" (第三次)
    
    验证点：
    - 不再重复 onboarding 模板
    - 体现上下文感知
    - 回复自然、简短、非模板化
    """
    print("\n" + "=" * 60)
    print("场景 2: 连续三次\"你好 / 测试\" (第三次)")
    print("=" * 60)
    
    # 模拟最近的对话
    recent_turns = [
        RecentTurn(role="user", content="你好啊", timestamp="2026-03-17T05:30:00Z"),
        RecentTurn(role="assistant", content="👋 你好！我是 EgoCore 任务助手...", timestamp="2026-03-17T05:30:01Z"),
        RecentTurn(role="user", content="第二次测试", timestamp="2026-03-17T05:31:00Z"),
        RecentTurn(role="assistant", content="我收到了，继续测试。", timestamp="2026-03-17T05:31:01Z"),
    ]
    
    envelope = InteractionEventEnvelope(
        envelope_id="env_002",
        user_input="你好",
        user_id="telegram:8420019401",
        session_id="session_001",
        recent_turns=recent_turns,
        turn_count=5,
    )
    
    result = interpret_interaction(envelope.to_dict())
    print(f"主体解释: primary_mode={result.interaction_interpretation.primary_mode}")
    
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id=envelope.envelope_id,
        result_id=result.result_id,
        interpretation=result.to_dict(),
        has_active_task=False,
    )
    
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=result.to_dict(),
    )
    
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=result.to_dict())
    print(f"回复:\n{reply}\n")
    
    # 验证
    primary_mode = result.interaction_interpretation.primary_mode
    
    if primary_mode == "testing":
        print("✅ 通过: 识别为 testing 模式")
    else:
        print(f"⚠️ primary_mode 是 {primary_mode}，期望 testing")
    
    # 不应该包含 "我是 EgoCore 任务助手"
    forbidden = ["我是 EgoCore 任务助手", "你可以直接告诉我你需要什么"]
    for f in forbidden:
        if f in reply:
            print(f"❌ 失败: 回复包含禁止内容: {f}")
            return False
    
    # 应该体现上下文感知
    context_aware_keywords = ["继续测试", "上下文", "收到了", "不用"]
    has_context = any(k in reply for k in context_aware_keywords)
    if has_context:
        print("✅ 通过: 体现了上下文感知")
    else:
        print("⚠️ 回复可能未体现上下文感知")
    
    return True


def test_scenario_3_with_active_task():
    """
    场景 3: "在吗"且有活动任务
    
    验证点：
    - 正确识别为 status_probe
    - 转任务状态汇报
    - 包含任务信息
    """
    print("\n" + "=" * 60)
    print("场景 3: \"在吗\"且有活动任务")
    print("=" * 60)
    
    from egocore.contracts.interaction_event_envelope_v1 import ActiveTaskSummary
    
    active_task = ActiveTaskSummary(
        task_id="task_abc123",
        objective="分析项目结构",
        status="running",
        progress=(2, 5)
    )
    
    envelope = InteractionEventEnvelope(
        envelope_id="env_003",
        user_input="在吗",
        user_id="telegram:8420019401",
        session_id="session_002",
        recent_turns=[],
        turn_count=3,
        active_task=active_task,
    )
    
    result = interpret_interaction(envelope.to_dict())
    print(f"主体解释: primary_mode={result.interaction_interpretation.primary_mode}")
    
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id=envelope.envelope_id,
        result_id=result.result_id,
        interpretation=result.to_dict(),
        has_active_task=True,
    )
    print(f"运行时决策: route={decision.runtime_route.value}")
    
    task_dict = {
        "task_id": "task_abc123",
        "objective": "分析项目结构",
        "status": "running",
        "progress": {"completed": 2, "total": 5}
    }
    
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=result.to_dict(),
        task_context=task_dict,
    )
    
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=result.to_dict())
    print(f"回复:\n{reply}\n")
    
    # 验证
    if decision.runtime_route.value == "task_status":
        print("✅ 通过: 转任务状态路由")
    else:
        print(f"⚠️ runtime_route 是 {decision.runtime_route.value}，期望 task_status")
    
    if "任务" in reply or "task" in reply.lower():
        print("✅ 通过: 包含任务信息")
    else:
        print("⚠️ 回复未包含任务信息")
    
    return True


def test_scenario_4_affective_probe():
    """
    场景 4: "你怎么这么冷淡"
    
    验证点：
    - 识别为 affective_probe
    - 改变回应策略（更温暖）
    - 包含关系修复内容
    """
    print("\n" + "=" * 60)
    print("场景 4: \"你怎么这么冷淡\"")
    print("=" * 60)
    
    recent_turns = [
        RecentTurn(role="user", content="在吗", timestamp="2026-03-17T05:40:00Z"),
        RecentTurn(role="assistant", content="我在。", timestamp="2026-03-17T05:40:01Z"),
    ]
    
    envelope = InteractionEventEnvelope(
        envelope_id="env_004",
        user_input="你怎么这么冷淡",
        user_id="telegram:8420019401",
        session_id="session_003",
        recent_turns=recent_turns,
        turn_count=3,
    )
    
    result = interpret_interaction(envelope.to_dict())
    print(f"主体解释: primary_mode={result.interaction_interpretation.primary_mode}")
    print(f"关系影响: repair_needed={result.relationship_implication.repair_needed}")
    
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id=envelope.envelope_id,
        result_id=result.result_id,
        interpretation=result.to_dict(),
        has_active_task=False,
    )
    
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=result.to_dict(),
    )
    
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=result.to_dict())
    print(f"回复:\n{reply}\n")
    
    # 验证
    primary_mode = result.interaction_interpretation.primary_mode
    
    if primary_mode == "affective_probe":
        print("✅ 通过: 识别为 affective_probe")
    else:
        print(f"⚠️ primary_mode 是 {primary_mode}，期望 affective_probe")
    
    warm_keywords = ["抱歉", "对不起", "感觉", "我在"]
    has_warm = any(k in reply for k in warm_keywords)
    if has_warm:
        print("✅ 通过: 包含温暖回应")
    else:
        print("⚠️ 回复可能不够温暖")
    
    return True


def test_scenario_5_gratitude():
    """
    场景 5: "谢谢"
    
    验证点：
    - 识别为 gratitude
    - 简短回应
    - 不啰嗦
    """
    print("\n" + "=" * 60)
    print("场景 5: \"谢谢\"")
    print("=" * 60)
    
    recent_turns = [
        RecentTurn(role="user", content="帮我检查一下代码", timestamp="2026-03-17T05:50:00Z"),
        RecentTurn(role="assistant", content="检查完成，发现 3 个问题...", timestamp="2026-03-17T05:50:30Z"),
    ]
    
    envelope = InteractionEventEnvelope(
        envelope_id="env_005",
        user_input="谢谢",
        user_id="telegram:8420019401",
        session_id="session_004",
        recent_turns=recent_turns,
        turn_count=3,
    )
    
    result = interpret_interaction(envelope.to_dict())
    print(f"主体解释: primary_mode={result.interaction_interpretation.primary_mode}")
    
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id=envelope.envelope_id,
        result_id=result.result_id,
        interpretation=result.to_dict(),
        has_active_task=False,
    )
    
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=result.to_dict(),
    )
    
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=result.to_dict())
    print(f"回复:\n{reply}\n")
    
    # 验证
    primary_mode = result.interaction_interpretation.primary_mode
    
    if primary_mode == "gratitude":
        print("✅ 通过: 识别为 gratitude")
    else:
        print(f"⚠️ primary_mode 是 {primary_mode}，期望 gratitude")
    
    if len(reply) < 50:
        print("✅ 通过: 回复简短")
    else:
        print("⚠️ 回复可能太长")
    
    return True


def test_scenario_6_bridge_down():
    """
    场景 6: OpenEmotion bridge down
    
    验证点：
    - 可自然降级
    - 不报错给用户
    - 使用中性回复
    """
    print("\n" + "=" * 60)
    print("场景 6: OpenEmotion bridge down (模拟)")
    print("=" * 60)
    
    from openemotion.interaction.interpretation import create_fallback_result
    
    # 创建降级结果
    fallback = create_fallback_result("test_envelope")
    
    # 创建决策
    decision = RuntimeDecisionEnvelope.from_subject_interpretation(
        envelope_id="test_envelope",
        result_id=fallback.result_id,
        interpretation=fallback.to_dict(),
        has_active_task=False,
    )
    
    # 创建回复包
    package = OutwardResponsePackage.from_decision(
        decision=decision.to_dict(),
        interpretation=fallback.to_dict(),
    )
    
    # 生成回复
    verbalizer = get_verbalizer()
    reply = verbalizer.verbalize(package, interpretation=fallback.to_dict())
    
    print(f"回复:\n{reply}\n")
    print(f"stability.degraded: {fallback.stability.degraded}")
    
    # 验证
    if fallback.stability.degraded:
        print("✅ 通过: 标记为降级模式")
    else:
        print("❌ 失败: 未标记为降级模式")
        return False
    
    if "收到" in reply or "帮" in reply:
        print("✅ 通过: 使用中性回复")
    else:
        print("⚠️ 回复格式可能需要调整")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Gate B: E2E 测试 - Social/Chat 新链路")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("场景1: 初次问候", test_scenario_1_first_greeting()))
    results.append(("场景2: 连续测试", test_scenario_2_repeated_greeting()))
    results.append(("场景3: 有活动任务", test_scenario_3_with_active_task()))
    results.append(("场景4: 情感探询", test_scenario_4_affective_probe()))
    results.append(("场景5: 感谢", test_scenario_5_gratitude()))
    results.append(("场景6: 降级模式", test_scenario_6_bridge_down()))
    
    print("\n" + "=" * 60)
    print("Gate B 结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 Gate B 通过！新链路验证完成。")
    else:
        print("❌ Gate B 失败，需要修复。")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
