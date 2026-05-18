"""
调试 affective_probe 处理链路
"""

import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/EgoCore')

from egocore.contracts.outward_response_package_v1 import (
    OutwardResponsePackage,
    ResponsePlan,
)
from egocore.contracts.runtime_decision_envelope_v1 import RuntimeDecisionEnvelope

# 模拟 OpenEmotion 返回的 affective_probe 解释
interpretation = {
    "result_id": "res_test",
    "schema_version": "1.0.0",
    "envelope_id": "env_test",
    "interaction_interpretation": {
        "primary_mode": "affective_probe",
        "secondary_modes": ["frustration"],
        "user_goal_rewrite": "表达不满，期待更温暖的回应",
        "ambiguity_level": 0.2,
        "confidence": 0.85,
    },
    "social_signals": ["affective_probe", "frustration_feedback"],
    "relationship_implication": {
        "interaction_effect": "negative",
        "trust_delta": -0.1,
        "tension_delta": 0.2,
        "repair_needed": True,
        "notes": None,
    },
    "response_tendency": {
        "preferred_action": "acknowledge",
        "should_acknowledge_context": True,
        "should_acknowledge_affect": True,
        "should_invite_next_step": False,
        "should_explain_self": True,
        "should_shift_to_task_mode": False,
    },
    "expressive_intent_candidate": {
        "speaker_stance": "warm",
        "warmth_preference": 0.8,
        "directness_preference": 0.4,
        "preferred_opening": "抱歉让你有这种感觉",
        "must_include_candidates": ["我在认真听你说话"],
        "must_avoid_candidates": ["冷漠回复", "机械模板"],
    },
    "reply_urge": {
        "value": 0.9,
        "reason": "关系修复需求，高优先响应",
    },
    "reflection_note": "用户感到被冷落，需要更温暖、更人性化的回应",
    "policy_hint": None,
    "stability": {
        "model_confidence": 0.85,
        "ood_flag": False,
        "degraded": False,
    },
    "created_at": "2026-03-17T15:18:51.461767+00:00",
    "processing_time_ms": 0.0,
}

# 创建决策
decision = RuntimeDecisionEnvelope.from_subject_interpretation(
    envelope_id="env_test",
    result_id="res_test",
    interpretation=interpretation,
    has_active_task=False,
    safety_context=None,
)

print("=== 决策信息 ===")
print(f"runtime_route: {decision.runtime_route.value}")
print(f"should_reply: {decision.should_reply}")

# 创建回复包
package = OutwardResponsePackage.from_decision(
    decision=decision.to_dict(),
    interpretation=interpretation,
    task_context=None,
)

print("\n=== 回复包信息 ===")
print(f"response_plan: {package.response_plan.value}")
print(f"speaker_mode: {package.speaker_mode.value}")
print(f"core_points: {package.core_points}")
print(f"must_include: {package.must_include}")

# 检查是否为 RELATIONSHIP_REPAIR
if package.response_plan == ResponsePlan.RELATIONSHIP_REPAIR:
    print("\n✅ 正确: response_plan 是 RELATIONSHIP_REPAIR")
else:
    print(f"\n❌ 错误: response_plan 是 {package.response_plan.value}，期望 RELATIONSHIP_REPAIR")

# 使用 VerbalizerV3
from app.response.verbalizer_v3 import VerbalizerV3
from app.response.relationship_context import RelationshipContext
from app.response.style_profile import StyleProfile

rel_ctx = RelationshipContext(session_id="test_session")
style_profile = StyleProfile(session_id="test_session")

verbalizer = VerbalizerV3(
    relationship_context=rel_ctx,
    style_profile=style_profile,
)

reply = verbalizer.verbalize(
    package,
    context={"turn_index": 1},
    interpretation=interpretation,
)

print(f"\n=== VerbalizerV3 输出 ===")
print(f"回复: {reply}")

# 期望的回复应该在 TONE_REPAIR 变体库中
expected_variants = [
    "嗯，你这个提醒是对的。我换种更自然的方式跟你聊。",
    "好，我改一下。刚才确实太像模板了。",
    "收到。我尽量不那么机械。",
    "嗯，我注意到了。继续说吧，我在听。",
    "好，我改。刚才那几句确实不太对。",
]

if reply in expected_variants:
    print("\n✅ 正确: 回复在 TONE_REPAIR 变体库中")
else:
    print(f"\n⚠️ 回复不在预期的 TONE_REPAIR 变体库中")
    print(f"预期变体: {expected_variants}")
