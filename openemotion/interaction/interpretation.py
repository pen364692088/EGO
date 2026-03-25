"""
OpenEmotion Interaction Interpretation Module

主体解释模块 - 负责"这次互动对我意味着什么"的解释。

关键边界：
- 此模块只负责解释，不负责决策
- 输出 SubjectInterpretationResult，不包含 should_* 字段
- 所有解释都是 OpenEmotion 的权威
"""

from openemotion.interaction.schema import (
    SubjectInterpretationResult,
    InteractionInterpretation,
    RelationshipImplication,
    ResponseTendency,
    ExpressiveIntentCandidate,
    ReplyUrge,
    StabilityInfo,
    PrimaryMode,
    SocialSignal,
)
from typing import Dict, Any, List, Optional
import uuid
import time


def classify_primary_mode(
    user_input: str,
    recent_turns: List[Dict[str, Any]],
    has_active_task: bool,
) -> tuple[str, float]:
    """
    分类主要互动模式
    
    Args:
        user_input: 用户输入
        recent_turns: 最近对话轮次
        has_active_task: 是否有活动任务
    
    Returns:
        (primary_mode, confidence)
    """
    text = user_input.lower().strip()
    
    # 问候模式
    greeting_patterns = ["你好", "您好", "hi", "hello", "hey", "嗨"]
    if any(p in text for p in greeting_patterns) and len(text) < 10:
        # 检查是否是重复测试
        if len(recent_turns) >= 2:
            # 检查最近是否有类似的问候
            recent_user_inputs = [
                t.get("content", "").lower() 
                for t in recent_turns 
                if t.get("role") == "user"
            ]
            similar_count = sum(
                1 for inp in recent_user_inputs 
                if any(p in inp for p in greeting_patterns) or "测试" in inp
            )
            if similar_count >= 2:
                return "testing", 0.85
        return "greeting", 0.9
    
    # 状态探询
    status_patterns = ["在吗", "在不在", "怎么样", "还好吗"]
    if any(p in text for p in status_patterns):
        return "status_probe", 0.85
    
    # 情感探询
    affective_patterns = ["冷淡", "你怎么", "你不", "感觉你", "是不是烦"]
    if any(p in text for p in affective_patterns):
        return "affective_probe", 0.85
    
    # 感谢
    gratitude_patterns = ["谢谢", "感谢", "多谢", "thanks"]
    if any(p in text for p in gratitude_patterns):
        return "gratitude", 0.9
    
    # 测试行为
    if "测试" in text or "test" in text.lower():
        return "testing", 0.8
    
    # 挫折
    frustration_patterns = ["烦", "不爽", "生气", "讨厌", "失望"]
    if any(p in text for p in frustration_patterns):
        return "frustration", 0.75
    
    # 默认
    return "chitchat", 0.5


def detect_social_signals(
    primary_mode: str,
    user_input: str,
) -> List[str]:
    """
    检测社交信号
    
    Args:
        primary_mode: 主要模式
        user_input: 用户输入
    
    Returns:
        社交信号列表
    """
    signals = []
    
    if primary_mode == "greeting":
        signals.append("greeting")
    elif primary_mode == "status_probe":
        signals.append("status_probe")
    elif primary_mode == "affective_probe":
        signals.append("affective_probe")
        if "冷淡" in user_input or "不" in user_input:
            signals.append("frustration_feedback")
    elif primary_mode == "gratitude":
        signals.append("gratitude")
    elif primary_mode == "testing":
        signals.append("testing_behavior")
    
    return signals


def interpret_interaction(
    envelope: Dict[str, Any],
) -> SubjectInterpretationResult:
    """
    解释互动事件
    
    这是 OpenEmotion 的核心解释函数。
    
    Args:
        envelope: InteractionEventEnvelope dict
    
    Returns:
        SubjectInterpretationResult
    """
    start_time = time.time()
    
    # 提取信封信息
    envelope_id = envelope.get("envelope_id", "")
    user_input = envelope.get("user_input", "")
    recent_turns = envelope.get("recent_turns", [])
    active_task = envelope.get("active_task")
    turn_count = envelope.get("turn_count", 0)
    
    has_active_task = active_task is not None
    
    # 分类主要模式
    primary_mode, mode_confidence = classify_primary_mode(
        user_input, recent_turns, has_active_task
    )
    
    # 检测社交信号
    social_signals = detect_social_signals(primary_mode, user_input)
    
    # 构建解释
    user_goal_rewrite = None
    if primary_mode == "greeting":
        user_goal_rewrite = "发起对话，建立联系"
    elif primary_mode == "testing":
        user_goal_rewrite = "测试系统反应，验证上下文记忆"
    elif primary_mode == "status_probe":
        user_goal_rewrite = "确认系统状态，可能想继续任务或了解进度"
    elif primary_mode == "affective_probe":
        user_goal_rewrite = "表达不满，期待更温暖的回应"
    elif primary_mode == "gratitude":
        user_goal_rewrite = "表达感谢，结束当前互动或开启新话题"
    
    interaction_interpretation = InteractionInterpretation(
        primary_mode=primary_mode,
        secondary_modes=[],
        user_goal_rewrite=user_goal_rewrite,
        ambiguity_level=0.2 if mode_confidence > 0.8 else 0.4,
        confidence=mode_confidence,
    )
    
    # 关系影响
    trust_delta = 0.0
    tension_delta = 0.0
    repair_needed = False
    interaction_effect = "neutral"
    
    if primary_mode == "greeting":
        trust_delta = 0.1
        interaction_effect = "positive"
    elif primary_mode == "gratitude":
        trust_delta = 0.1
        tension_delta = -0.1
        interaction_effect = "positive"
    elif primary_mode == "affective_probe":
        trust_delta = -0.1
        tension_delta = 0.2
        repair_needed = True
        interaction_effect = "negative"
    elif primary_mode == "frustration":
        trust_delta = -0.15
        tension_delta = 0.25
        repair_needed = True
        interaction_effect = "negative"
    
    relationship_implication = RelationshipImplication(
        interaction_effect=interaction_effect,
        trust_delta=trust_delta,
        tension_delta=tension_delta,
        repair_needed=repair_needed,
    )
    
    # 回应倾向
    preferred_action = "acknowledge"
    should_acknowledge_context = False
    should_acknowledge_affect = False
    should_invite_next_step = False
    should_explain_self = False
    should_shift_to_task_mode = False
    
    if primary_mode == "greeting":
        should_invite_next_step = True
    elif primary_mode == "testing":
        should_acknowledge_context = True
        should_invite_next_step = True
    elif primary_mode == "status_probe" and has_active_task:
        should_shift_to_task_mode = True
        should_acknowledge_context = True
    elif primary_mode == "affective_probe":
        should_acknowledge_context = True
        should_acknowledge_affect = True
        should_explain_self = True
    elif primary_mode == "gratitude":
        should_acknowledge_affect = True
    
    response_tendency = ResponseTendency(
        preferred_action=preferred_action,
        should_acknowledge_context=should_acknowledge_context,
        should_acknowledge_affect=should_acknowledge_affect,
        should_invite_next_step=should_invite_next_step,
        should_explain_self=should_explain_self,
        should_shift_to_task_mode=should_shift_to_task_mode,
    )
    
    # 表达意图候选
    speaker_stance = "neutral"
    warmth_preference = 0.5
    directness_preference = 0.5
    preferred_opening = None
    must_include_candidates = []
    must_avoid_candidates = []
    
    if primary_mode == "greeting" and turn_count == 1:
        speaker_stance = "warm"
        warmth_preference = 0.7
        preferred_opening = "你好"
    elif primary_mode == "testing":
        speaker_stance = "neutral"
        directness_preference = 0.7
        preferred_opening = "我在，收到了"
        must_include_candidates = [
            "这轮我知道你是在继续测试",
            "不用再给你重复那套欢迎词"
        ]
        must_avoid_candidates = ["欢迎词模板", "我是 EgoCore 任务助手"]
    elif primary_mode == "status_probe" and has_active_task:
        speaker_stance = "warm"
        warmth_preference = 0.6
        directness_preference = 0.6
        preferred_opening = "我在"
        must_include_candidates = ["当前有活动任务"]
    elif primary_mode == "affective_probe":
        speaker_stance = "warm"
        warmth_preference = 0.8
        directness_preference = 0.4
        preferred_opening = "抱歉让你有这种感觉"
        must_include_candidates = ["我在认真听你说话"]
        must_avoid_candidates = ["冷漠回复", "机械模板"]
    elif primary_mode == "gratitude":
        speaker_stance = "warm"
        warmth_preference = 0.7
        directness_preference = 0.5
        preferred_opening = "不客气"
        must_avoid_candidates = ["啰嗦", "过度解释"]
    
    expressive_intent_candidate = ExpressiveIntentCandidate(
        speaker_stance=speaker_stance,
        warmth_preference=warmth_preference,
        directness_preference=directness_preference,
        preferred_opening=preferred_opening,
        must_include_candidates=must_include_candidates,
        must_avoid_candidates=must_avoid_candidates,
    )
    
    # 回复冲动
    reply_urge_value = 0.5
    reply_urge_reason = "default"
    
    if primary_mode == "greeting" and turn_count == 1:
        reply_urge_value = 0.8
        reply_urge_reason = "新用户首次互动"
    elif primary_mode == "testing":
        reply_urge_value = 0.6
        reply_urge_reason = "测试场景，适度回应"
    elif primary_mode == "status_probe" and has_active_task:
        reply_urge_value = 0.9
        reply_urge_reason = "用户有活动任务，高优先响应"
    elif primary_mode == "affective_probe":
        reply_urge_value = 0.9
        reply_urge_reason = "关系修复需求，高优先响应"
    elif primary_mode == "gratitude":
        reply_urge_value = 0.5
        reply_urge_reason = "感谢场景，简短回应即可"
    
    reply_urge = ReplyUrge(
        value=reply_urge_value,
        reason=reply_urge_reason,
    )
    
    # 反思笔记
    reflection_note = None
    if primary_mode == "testing" and len(recent_turns) >= 2:
        reflection_note = "用户已连续发送多次问候/测试，不应重复 onboarding 模板"
    elif primary_mode == "affective_probe":
        reflection_note = "用户感到被冷落，需要更温暖、更人性化的回应"
    
    # 策略提示
    policy_hint = None
    if primary_mode == "status_probe" and has_active_task:
        policy_hint = "考虑主动汇报任务状态"
    
    # 稳定性
    stability = StabilityInfo(
        model_confidence=mode_confidence,
        ood_flag=False,
        degraded=False,
    )
    
    processing_time_ms = (time.time() - start_time) * 1000
    
    return SubjectInterpretationResult(
        result_id=f"res_{uuid.uuid4().hex[:8]}",
        envelope_id=envelope_id,
        interaction_interpretation=interaction_interpretation,
        social_signals=social_signals,
        relationship_implication=relationship_implication,
        response_tendency=response_tendency,
        expressive_intent_candidate=expressive_intent_candidate,
        reply_urge=reply_urge,
        reflection_note=reflection_note,
        policy_hint=policy_hint,
        stability=stability,
        processing_time_ms=processing_time_ms,
    )


def create_fallback_result(envelope_id: str) -> SubjectInterpretationResult:
    """
    创建降级模式结果
    
    当 OpenEmotion 无法正常处理时使用。
    
    Args:
        envelope_id: 信封 ID
    
    Returns:
        SubjectInterpretationResult (降级模式)
    """
    return SubjectInterpretationResult(
        result_id=f"res_fallback_{uuid.uuid4().hex[:8]}",
        envelope_id=envelope_id,
        interaction_interpretation=InteractionInterpretation(
            primary_mode="unknown",
            ambiguity_level=0.5,
            confidence=0.3,
        ),
        social_signals=[],
        relationship_implication=RelationshipImplication(),
        response_tendency=ResponseTendency(
            preferred_action="acknowledge",
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="neutral",
            warmth_preference=0.5,
            directness_preference=0.5,
        ),
        reply_urge=ReplyUrge(
            value=0.5,
            reason="fallback",
        ),
        reflection_note="OpenEmotion 暂时不可用，使用降级模式",
        stability=StabilityInfo(
            model_confidence=0.3,
            ood_flag=True,
            degraded=True,
        ),
    )
