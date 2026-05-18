"""
P1-B E2E 测试

模拟真实 Telegram 对话场景，验证关系连续性和风格表达增强。
"""

import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')

from app.response.relationship_context import (
    RelationshipContext,
    RelationshipContextManager,
    RelationshipEvent,
    SocialArc,
)
from app.response.style_profile import (
    StyleProfile,
    StyleDimensions,
    StyleProfileManager,
)
from app.response.verbalizer_v3 import VerbalizerV3, SocialMode
from egocore.contracts.outward_response_package_v1 import (
    OutwardResponsePackage,
    ResponsePlan,
)


def simulate_conversation(scenario_name: str, inputs: list):
    """
    模拟对话场景
    
    Args:
        scenario_name: 场景名称
        inputs: 输入列表 [(primary_mode, response_plan, turn_index), ...]
    """
    print(f"\n{'='*50}")
    print(f"场景: {scenario_name}")
    print(f"{'='*50}")
    
    rel_manager = RelationshipContextManager()
    style_manager = StyleProfileManager()
    session_id = f"session_{scenario_name.replace(' ', '_')}"
    
    for i, (user_input, primary_mode, response_plan, turn_index) in enumerate(inputs, 1):
        print(f"\n--- 第 {i} 轮 ---")
        print(f"用户: {user_input}")
        
        # 获取上下文
        rel_ctx = rel_manager.get_context(session_id)
        style_profile = style_manager.get_profile(session_id)
        
        # 创建 verbalizer
        verbalizer = VerbalizerV3(
            relationship_context=rel_ctx,
            style_profile=style_profile,
        )
        
        # 创建回复包
        package = OutwardResponsePackage(
            package_id=f"pkg_{i}",
            response_plan=response_plan,
        )
        
        # 生成回复
        reply = verbalizer.verbalize(package, context={"turn_index": turn_index})
        print(f"代理: {reply}")
        
        # 显示上下文状态
        print(f"[上下文: 温度={rel_ctx.conversation_temperature:.2f}, 弧={rel_ctx.current_social_arc}]")
        
        # 更新关系上下文
        event_type = primary_mode
        impact = "negative" if primary_mode == RelationshipEvent.AFFECTIVE_PROBE.value else "neutral"
        
        rel_manager.update_context(
            session_id=session_id,
            event_type=event_type,
            user_input=user_input[:30],
            agent_response=reply[:30],
            impact=impact,
        )
        
        # 如果是 affective probe，标记修复
        if primary_mode == RelationshipEvent.AFFECTIVE_PROBE.value:
            rel_ctx = rel_manager.get_context(session_id)
            rel_ctx.mark_repair_resolved()
        
        # 更新风格
        style_manager.adjust_for_context(session_id, rel_manager.get_context(session_id))


def test_scenario_1_repeated_greeting():
    """场景 1: 重复问候"""
    simulate_conversation(
        "重复问候",
        [
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 1),
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 2),
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 3),
        ]
    )


def test_scenario_2_affective_probe():
    """场景 2: affective probe + 后续"""
    simulate_conversation(
        "affective probe + 后续",
        [
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 1),
            ("你怎么这么冷淡", RelationshipEvent.AFFECTIVE_PROBE.value, ResponsePlan.RELATIONSHIP_REPAIR, 2),
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 3),
        ]
    )


def test_scenario_3_testing():
    """场景 3: 连续轻测试"""
    simulate_conversation(
        "连续轻测试",
        [
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 1),
            ("你好", RelationshipEvent.TESTING.value, ResponsePlan.CONTEXT_AWARE, 2),
            ("在吗", RelationshipEvent.STATUS_PROBE.value, ResponsePlan.CONTEXT_AWARE, 3),
            ("你好啊", RelationshipEvent.TESTING.value, ResponsePlan.CONTEXT_AWARE, 4),
        ]
    )


def test_scenario_4_social_to_task():
    """场景 4: 社交转任务"""
    simulate_conversation(
        "社交转任务",
        [
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 1),
            ("随便聊两句", RelationshipEvent.CHITCHAT.value, ResponsePlan.SIMPLE_ACKNOWLEDGE, 2),
            ("帮我看看这个项目问题", RelationshipEvent.TASK_REQUEST.value, ResponsePlan.TASK_STATUS, 3),
        ]
    )


def test_scenario_5_repair_continuation():
    """场景 5: 修复后延续"""
    simulate_conversation(
        "修复后延续",
        [
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 1),
            ("你刚才太像机器人了", RelationshipEvent.AFFECTIVE_PROBE.value, ResponsePlan.RELATIONSHIP_REPAIR, 2),
            ("现在好多了", RelationshipEvent.CHITCHAT.value, ResponsePlan.SIMPLE_ACKNOWLEDGE, 3),
            ("你好", RelationshipEvent.GREETING.value, ResponsePlan.WARM_GREETING, 4),
        ]
    )


def main():
    """运行所有 E2E 测试"""
    print("=" * 60)
    print("P1-B E2E 测试 - 模拟真实对话场景")
    print("=" * 60)
    
    test_scenario_1_repeated_greeting()
    test_scenario_2_affective_probe()
    test_scenario_3_testing()
    test_scenario_4_social_to_task()
    test_scenario_5_repair_continuation()
    
    print("\n" + "=" * 60)
    print("✅ 所有 E2E 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
