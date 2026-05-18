"""
Verbalizer v3 - EgoCore

自然表达层 v3：关系感知 + 风格条件化

v3 改进：
- 整合 RelationshipContext，支持关系连续性
- 整合 StyleProfile，支持风格一致性
- 细分 social mode
- 支持修复后软性承认
- 支持 social → task 平滑过渡

归属：EgoCore
作用：只能按 contract 组织自然语言，不能擅自升级。

版本：3.0.0
"""

import logging
import random
from typing import Dict, Any, List, Optional

from egocore.contracts.outward_response_package_v1 import (
    OutwardResponsePackage,
    ResponsePlan,
    SpeakerMode,
)

from app.response.relationship_context import (
    RelationshipContext,
    SocialArc,
    RelationshipEvent,
)
from app.response.style_profile import (
    StyleProfile,
    StyleDimensions,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Social Mode 定义（细分）
# ============================================================================

class SocialMode:
    """细分的 social mode"""
    
    # 问候类
    GREETING_WARM_START = "greeting_warm_start"           # 首次温暖问候
    GREETING_CONTINUATION = "greeting_continuation"       # 后续问候
    GREETING_POST_REPAIR = "greeting_post_repair"         # 修复后的问候
    
    # 在线确认类
    STATUS_PRESENCE_ACK = "status_presence_ack"           # 简单在线确认
    LIGHT_TEST_ACK = "light_test_ack"                     # 轻测试确认
    
    # 关系修复类
    TONE_REPAIR = "tone_repair"                           # 语气修复
    POST_REPAIR_SOFT_RESPONSE = "post_repair_soft_response"  # 修复后软性回应
    
    # 社交保持类
    LIGHT_SOCIAL_KEEPALIVE = "light_social_keepalive"     # 轻社交保持
    
    # 过渡类
    SOCIAL_TO_TASK_BRIDGE = "social_to_task_bridge"       # 社交到任务过渡


# ============================================================================
# Verbalizer v3
# ============================================================================

class VerbalizerV3:
    """
    自然表达层 v3
    
    关键原则：
    - 内部判断可以深，外部表达必须短
    - 关系连续性优先于模板
    - 风格轻度稳定，不僵硬
    - 修复后软性承认，不重复道歉
    """
    
    # 内部字段名/判断词，绝不允许出现在用户回复中
    INTERNAL_PHRASES = {
        "testing", "probe", "repair", "route", "interpret", "mode",
        "contract", "acknowledge_testing", "repair_relationship",
        "acknowledge_context", "acknowledge_affect", "shift_to_task",
        "我注意到这是你连续", "这轮我知道你是在", "不用再给你重复",
        "系统识别", "判断为", "切换到", "模式",
        "degraded", "fallback", "stability",
    }
    
    # ========================================
    # 自然表达变体库（每个 mode 3~5 个变体）
    # ========================================
    
    # 首次问候变体
    GREETING_WARM_START = [
        "👋 你好！有什么我可以帮你的吗？",
        "你好，我在。可以直接说你需要什么。",
        "嗨！我在这里。",
        "你好！我在，有什么想说的？",
    ]
    
    # 后续问候变体（体现连续性）
    GREETING_CONTINUATION = [
        "嗯，我在。",
        "收到，继续说。",
        "我在，刚才那条我记得。",
        "嗯，我在听。",
    ]
    
    # 修复后的问候变体（更柔和）
    GREETING_POST_REPAIR = [
        "嗯，我在。",
        "好，继续说吧。",
        "我在。",
        "嗯，我在这儿。",
    ]
    
    # 简单在线确认
    STATUS_PRESENCE_ACK = [
        "我在。",
        "在的。",
        "嗯？",
        "在。",
    ]
    
    # 轻测试确认
    LIGHT_TEST_ACK = [
        "我在。",
        "收到。",
        "嗯，我在。",
        "在的，继续说吧。",
    ]
    
    # 语气修复（承认 + 修正 + 继续）
    TONE_REPAIR = [
        "嗯，你这个提醒是对的。我换种更自然的方式跟你聊。",
        "好，我改一下。刚才确实太像模板了。",
        "收到。我尽量不那么机械。",
        "嗯，我注意到了。继续说吧，我在听。",
        "好，我改。刚才那几句确实不太对。",
    ]
    
    # 修复后软性回应（不完全重复道歉）
    POST_REPAIR_SOFT_RESPONSE = [
        "好，我在。继续说吧。",
        "嗯，我在。",
        "好，我尽量保持这样。继续？",
        "我在。",
    ]
    
    # 轻社交保持
    LIGHT_SOCIAL_KEEPALIVE = [
        "嗯，收到了。",
        "好。",
        "收到。",
        "我在。",
        "嗯。",
    ]
    
    # 社交到任务过渡
    SOCIAL_TO_TASK_BRIDGE = [
        "好，你要做什么？",
        "我在。有什么需要帮忙的？",
        "好，说吧。",
        "我在，直接说任务就行。",
    ]
    
    # 感谢回复
    GRATEFUL = [
        "嗯。",
        "不客气。",
        "好的。",
        "嗯，有需要再说。",
    ]
    
    # 降级回复
    FALLBACK = [
        "我在。",
        "收到。",
        "嗯？",
    ]
    
    def __init__(
        self,
        relationship_context: Optional[RelationshipContext] = None,
        style_profile: Optional[StyleProfile] = None,
    ):
        self.relationship_context = relationship_context
        self.style_profile = style_profile
    
    def _filter_internal_phrases(self, text: str) -> str:
        """过滤掉内部判断语言"""
        text_lower = text.lower()
        for phrase in self.INTERNAL_PHRASES:
            if phrase.lower() in text_lower:
                # 返回一个安全的简短回复
                return random.choice(self.LIGHT_SOCIAL_KEEPALIVE)
        return text

    def _apply_response_tendency(self, reply: str, tendency: Dict[str, Any]) -> str:
        """
        根据 response_tendency 调整回复

        支持两种格式：
        
        格式 A (OpenEmotionResultV1.ResponseTendency):
        - mode: REPLY / TASK / BLOCK / ASK / ESCALATE
        - tone: CALM / WARM / GUARDED / NEUTRAL
        - goal: str
        - suggested_reply_outline: List[str]

        格式 B (扩展格式):
        - tone: warm / concise / neutral
        - length: short / medium / long
        - directness: high / medium / low
        - urgency: high / medium / low

        Args:
            reply: 原始回复
            tendency: response_tendency 字典

        Returns:
            调整后的回复
        """
        if not tendency:
            return reply

        # 格式 A: OpenEmotionResultV1 格式
        oe_tone = tendency.get("tone", "")
        if oe_tone and oe_tone.upper() in ["CALM", "WARM", "GUARDED", "NEUTRAL"]:
            # WARM → 保持柔和
            if oe_tone.upper() == "WARM":
                pass  # 原回复已经足够柔和
            # GUARDED → 更简洁，少承诺
            elif oe_tone.upper() == "GUARDED":
                if len(reply) > 20:
                    reply = self._shorten_reply(reply)
            # CALM / NEUTRAL → 保持原样
            # 不做额外处理

        # 格式 B: OpenEmotion readout 格式 (主要)
        tone = tendency.get("tone", "")
        length = tendency.get("length", "moderate")
        urgency = tendency.get("urgency", 0.5)

        # length = brief 或 tone = direct → 强制更短
        if length == "brief" or tone == "direct":
            if len(reply) > 15:
                reply = self._shorten_reply(reply)

        # tone = soft 或 warm → 保持原样
        elif tone in ("soft", "warm"):
            pass  # 原回复已经足够柔和

        # directness (如果有)
        directness = tendency.get("directness", "medium")

        # directness = high → 去掉铺垫
        if directness == "high":
            prefixes_to_remove = ["嗯，", "好，", "收到，"]
            for prefix in prefixes_to_remove:
                if reply.startswith(prefix) and len(reply) > len(prefix) + 3:
                    reply = reply[len(prefix):].capitalize()
                    break

        # urgency (OpenEmotion: 0-1 float)
        # 高紧急度 → 更直接
        if isinstance(urgency, (int, float)) and urgency > 0.7:
            if len(reply) > 20:
                reply = self._shorten_reply(reply)

        return reply

    def _apply_policy_hint(self, reply: str, hint: Dict[str, Any]) -> str:
        """
        根据 policy_hint 调整回复

        支持两种格式：

        格式 A (OpenEmotion PolicyHint):
        - hint_type: PREFER / AVOID / ESCALATE / DEFER / IGNORE / SEEK_CLARIFICATION
        - reason: str
        - confidence: float
        - context: dict

        格式 B (旧格式):
        - ask_for_clarification: bool
        - be_cautious: bool
        - prefer_task_mode: bool

        Args:
            reply: 原始回复
            hint: policy_hint 字典

        Returns:
            调整后的回复
        """
        if not hint:
            return reply

        # 格式 A: OpenEmotion hint_type
        hint_type = hint.get("hint_type", "")
        if hint_type:
            if hint_type == "seek_clarification":
                clarification_prompts = ["你是指...?", "能再说清楚一点吗？", "具体是哪个？"]
                if not any(p in reply for p in clarification_prompts):
                    reply = reply.rstrip("。") + "。" + random.choice(clarification_prompts)
            elif hint_type == "avoid":
                # 减少承诺性语言
                commitment_words = ["一定", "肯定", "绝对"]
                for word in commitment_words:
                    if word in reply:
                        reply = reply.replace(word, "尽量")
            elif hint_type == "prefer":
                # 保持原样
                pass
            return reply

        # 格式 B: 旧格式
        ask_for_clarification = hint.get("ask_for_clarification", False)
        be_cautious = hint.get("be_cautious", False)
        prefer_task_mode = hint.get("prefer_task_mode", False)

        # ask_for_clarification → 末尾加确认句
        if ask_for_clarification:
            clarification_prompts = [
                "你是指...?",
                "能再说清楚一点吗？",
                "具体是哪个？",
            ]
            if not any(p in reply for p in clarification_prompts):
                reply = reply.rstrip("。") + "。" + random.choice(clarification_prompts)

        # be_cautious → 减少承诺性语言
        if be_cautious:
            # 简单处理：如果回复里有强承诺词，换成更谨慎的表达
            commitment_words = ["一定", "肯定", "绝对"]
            for word in commitment_words:
                if word in reply:
                    reply = reply.replace(word, "尽量")

        # prefer_task_mode → 引导向任务
        if prefer_task_mode:
            if "你想做" not in reply and "需要帮忙" not in reply:
                reply = reply.rstrip("。") + "。有什么要做的吗？"

        return reply

    def _shorten_reply(self, reply: str) -> str:
        """缩短回复"""
        # 简单策略：取第一句
        sentences = reply.split("。")
        if len(sentences) > 1:
            return sentences[0] + "。"
        # 如果还是太长，取前 15 字符
        if len(reply) > 15:
            return reply[:15].rstrip("，。") + "。"
        return reply
    
    def _select_variant(
        self,
        variants: List[str],
        mode: str,
        style: Optional[StyleDimensions] = None,
    ) -> str:
        """
        选择一个变体，考虑风格和避免重复
        
        Args:
            variants: 变体列表
            mode: social mode
            style: 风格维度
        
        Returns:
            选择的变体
        """
        if not variants:
            return "我在。"
        
        # 如果有风格配置，使用它来选择
        if self.style_profile:
            index = self.style_profile.select_variant_index(mode, len(variants))
            return variants[index]
        
        # 否则随机选择
        return random.choice(variants)
    
    def _get_turn_index(self, context: Optional[Dict[str, Any]]) -> int:
        """获取会话轮次索引"""
        if context and "turn_index" in context:
            return context["turn_index"]
        return 1
    
    def _determine_social_mode(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
        turn_index: int,
    ) -> str:
        """
        根据包和上下文确定细分的 social mode
        
        Args:
            package: 回复包
            context: 上下文
            turn_index: 轮次索引
        
        Returns:
            social mode 名称
        """
        response_plan = package.response_plan
        
        # 有关系上下文时，做更细致的判断
        if self.relationship_context:
            # 检查是否在修复后
            if self.relationship_context.needs_soft_acknowledgment():
                if response_plan == ResponsePlan.WARM_GREETING:
                    return SocialMode.GREETING_POST_REPAIR
                else:
                    return SocialMode.POST_REPAIR_SOFT_RESPONSE
            
            # 检查是否在修复模式中
            if self.relationship_context.is_in_repair_mode():
                return SocialMode.TONE_REPAIR
            
            # 检查 social arc
            arc = self.relationship_context.current_social_arc
            
            if arc == SocialArc.TESTING.value:
                return SocialMode.LIGHT_TEST_ACK
            
            if arc == SocialArc.REPAIRING.value:
                if response_plan == ResponsePlan.RELATIONSHIP_REPAIR:
                    return SocialMode.TONE_REPAIR
        
        # 根据 response_plan 和 turn_index 判断
        if response_plan == ResponsePlan.WARM_GREETING:
            if turn_index <= 1:
                return SocialMode.GREETING_WARM_START
            else:
                return SocialMode.GREETING_CONTINUATION
        
        elif response_plan == ResponsePlan.CONTEXT_AWARE:
            if turn_index <= 1:
                return SocialMode.GREETING_WARM_START
            else:
                return SocialMode.LIGHT_TEST_ACK
        
        elif response_plan == ResponsePlan.RELATIONSHIP_REPAIR:
            return SocialMode.TONE_REPAIR
        
        elif response_plan == ResponsePlan.GRATEFUL_RESPONSE:
            return "grateful"
        
        elif response_plan == ResponsePlan.TASK_STATUS:
            return SocialMode.SOCIAL_TO_TASK_BRIDGE
        
        elif response_plan == ResponsePlan.NEUTRAL_FALLBACK:
            return "fallback"
        
        # 默认
        return SocialMode.LIGHT_SOCIAL_KEEPALIVE
    
    def verbalize(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]] = None,
        interpretation: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        根据 package 生成自然回复

        Args:
            package: OutwardResponsePackage
            context: 额外上下文（包含 turn_index, last_reply_type, response_tendency, policy_hint）
            interpretation: 主体解释结果

        Returns:
            自然语言回复（1~2 句）
        """
        response_plan = package.response_plan
        turn_index = self._get_turn_index(context)

        # 提取 response_tendency
        response_tendency = context.get("response_tendency") if context else None
        policy_hint = context.get("policy_hint") if context else None

        # 确定细分的 social mode
        social_mode = self._determine_social_mode(package, context, turn_index)

        # 根据社交模式选择变体
        reply = self._verbalize_by_mode(social_mode, package, context, turn_index)

        # 如果有 response_tendency，做轻量调整
        if response_tendency:
            reply = self._apply_response_tendency(reply, response_tendency)

        # 如果有 policy_hint，做轻量调整
        if policy_hint:
            reply = self._apply_policy_hint(reply, policy_hint)

        # 过滤内部短语
        reply = self._filter_internal_phrases(reply)

        return reply
    
    def _verbalize_by_mode(
        self,
        mode: str,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
        turn_index: int,
    ) -> str:
        """根据 social mode 选择回复变体"""
        
        # 问候类
        if mode == SocialMode.GREETING_WARM_START:
            return self._select_variant(self.GREETING_WARM_START, mode)
        
        elif mode == SocialMode.GREETING_CONTINUATION:
            return self._select_variant(self.GREETING_CONTINUATION, mode)
        
        elif mode == SocialMode.GREETING_POST_REPAIR:
            return self._select_variant(self.GREETING_POST_REPAIR, mode)
        
        # 在线确认类
        elif mode == SocialMode.STATUS_PRESENCE_ACK:
            return self._select_variant(self.STATUS_PRESENCE_ACK, mode)
        
        elif mode == SocialMode.LIGHT_TEST_ACK:
            return self._select_variant(self.LIGHT_TEST_ACK, mode)
        
        # 关系修复类
        elif mode == SocialMode.TONE_REPAIR:
            return self._select_variant(self.TONE_REPAIR, mode)
        
        elif mode == SocialMode.POST_REPAIR_SOFT_RESPONSE:
            return self._select_variant(self.POST_REPAIR_SOFT_RESPONSE, mode)
        
        # 社交保持类
        elif mode == SocialMode.LIGHT_SOCIAL_KEEPALIVE:
            return self._select_variant(self.LIGHT_SOCIAL_KEEPALIVE, mode)
        
        # 过渡类
        elif mode == SocialMode.SOCIAL_TO_TASK_BRIDGE:
            return self._verbalize_task_bridge(package, context)
        
        # 感谢
        elif mode == "grateful":
            return self._select_variant(self.GRATEFUL, mode)
        
        # 降级
        elif mode == "fallback":
            return self._select_variant(self.FALLBACK, mode)
        
        # 默认
        return self._select_variant(self.LIGHT_SOCIAL_KEEPALIVE, mode)
    
    def _verbalize_task_bridge(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """社交到任务过渡"""
        if package.task_context:
            task = package.task_context
            objective = task.get("objective", "任务")
            progress = task.get("progress", {})
            completed = progress.get("completed", 0)
            total = progress.get("total", 0)
            
            # 简洁版本
            return f"我在。当前有个任务：{objective[:30]}（{completed}/{total}）。说\"继续\"可以继续。"
        
        return self._select_variant(self.SOCIAL_TO_TASK_BRIDGE, SocialMode.SOCIAL_TO_TASK_BRIDGE)


# ============================================================================
# 工厂函数
# ============================================================================

def create_verbalizer_v3(
    relationship_context: Optional[RelationshipContext] = None,
    style_profile: Optional[StyleProfile] = None,
) -> VerbalizerV3:
    """创建 VerbalizerV3 实例"""
    return VerbalizerV3(
        relationship_context=relationship_context,
        style_profile=style_profile,
    )


# 全局实例（向后兼容）
_verbalizer: Optional[VerbalizerV3] = None


def get_verbalizer() -> VerbalizerV3:
    """获取全局语言生成器"""
    global _verbalizer
    if _verbalizer is None:
        _verbalizer = VerbalizerV3()
    return _verbalizer


def verbalize(
    package: OutwardResponsePackage,
    context: Optional[Dict[str, Any]] = None,
    relationship_context: Optional[RelationshipContext] = None,
    style_profile: Optional[StyleProfile] = None,
) -> str:
    """
    便捷函数：生成回复
    
    支持传入关系上下文和风格配置
    """
    verbalizer = VerbalizerV3(
        relationship_context=relationship_context,
        style_profile=style_profile,
    )
    return verbalizer.verbalize(package, context)
