"""
QuestionVerbalizer - EgoCore

Question intent 专用 verbalizer，处理短问句的自然表达。

职责：
- 短问句识别与分类
- 自然回复生成
- 跨 intent 风格对齐

版本：1.0.0
"""

import logging
import random
from typing import Dict, Any, List, Optional

from app.response.relationship_context import RelationshipContext
from app.response.style_profile import StyleProfile

logger = logging.getLogger(__name__)


class ShortQuestionType:
    """短问句类型"""
    SHORT_CLARIFICATION = "short_clarification"      # "什么？"
    SURPRISED_FOLLOWUP = "surprised_followup"        # "啊？"
    WHY_PROBE = "why_probe"                          # "为什么？"
    MEANING_PROBE = "meaning_probe"                  # "啥意思？"
    REPEAT_REQUEST = "repeat_request"                # "你说什么？"
    INVITATION = "invitation"                        # "说吧" / "请讲"
    UNKNOWN = "unknown"


class QuestionVerbalizer:
    """
    Question intent 专用 verbalizer
    
    关键原则：
    - 短问句优先短回复
    - 口语化，不解释系统
    - 与 social/chat 风格对齐
    """
    
    # 短问句检测模式 v1.1 (P1-C.1)
    # 顺序重要：更具体的模式放前面，避免被通用模式抢先匹配
    # 注意：使用精确匹配，避免子串误匹配（如 "啥" 匹配 "啥意思"）
    SHORT_QUESTION_PATTERNS = {
        ShortQuestionType.REPEAT_REQUEST: [
            "你说什么？", "你说什么", "再说一遍", "重复一下", "没听清",
        ],
        ShortQuestionType.MEANING_PROBE: [
            "啥意思？", "什么意思？", "什么意思", "意思是",
            "没懂", "没明白", "不懂", "我不太懂", "还是不明白",
            "说清楚点", "再说明白一点", "没太明白", "没理解",
        ],
        ShortQuestionType.WHY_PROBE: [
            "为什么？", "为什么", "为啥？", "为啥", "怎么突然",
        ],
        ShortQuestionType.SURPRISED_FOLLOWUP: [
            "啊？", "嗯？", "哦？", "哈？",  # 移除单字 "啊" "嗯" "哦" 避免过度匹配
        ],
        ShortQuestionType.INVITATION: [
            "说吧", "请讲", "你说", "继续", "然后呢", "接着呢",
        ],
        ShortQuestionType.SHORT_CLARIFICATION: [
            "什么？", "什么", "啥？", "？", "?",  # 纯问号也走短澄清
        ],
    }
    
    # ========================================
    # 自然表达变体库 v1.1 (P1-C.1)
    # 原则：短但自然，有轻澄清能力，禁止纯占位句
    # ========================================

    # 短澄清 "什么？/啥？" — 表达没听清/需要对方展开 (P1-C.2)
    # 禁止纯语气词，必须有轻澄清能力
    SHORT_CLARIFICATION = [
        "没太跟上，你再说说？",
        "具体指哪部分？",
        "你说的是…？",
        "展开讲讲？",
        "指的是什么？",
    ]

    # 惊讶跟进 "啊？/嗯？" — 表达意外/需要确认
    SURPRISED_FOLLOWUP = [
        "嗯？",
        "有点意外，怎么了？",
        "出什么事了？",
        "突然这么问？",
        "哈？",
    ]

    # 原因追问 "为什么？/为啥？" — 轻反问，邀请对方说动机
    WHY_PROBE = [
        "怎么了？",
        "哪块让你想问了？",
        "突然好奇这个？",
        "有什么情况吗？",
        "你想了解哪方面？",
    ]

    # 意思询问 "啥意思？/什么意思？" — 表达需要解释，带轻微困惑 (P1-C.2)
    # 禁止纯语气词开头
    MEANING_PROBE = [
        "我没说明白？",
        "哪句让你困惑了？",
        "需要我换个说法？",
        "你说的是刚才哪部分？",
        "展开说说？",
        "具体哪部分不清楚？",
    ]

    # 重复请求 "你说什么？/再说一遍" — 提供上下文摘要
    REPEAT_REQUEST = [
        "我说：{context}",
        "刚才说的是：{context}",
        "简单来说：{context}",
        "重复一下：{context}",
    ]

    # 邀请 "说吧/请讲" — 表达开放倾听姿态
    INVITATION = [
        "嗯，你说。",
        "我听着，你说。",
        "说吧，我在。",
        "你说，我记着。",
    ]

    # 通用短回复（fallback）— 禁止 "收到/好/我在/嗯？" 纯占位
    GENERIC_SHORT = [
        "你说。",
        "怎么了？",
        "展开讲讲？",
        "具体说说？",
    ]
    
    def __init__(
        self,
        relationship_context: Optional[RelationshipContext] = None,
        style_profile: Optional[StyleProfile] = None,
    ):
        self.relationship_context = relationship_context
        self.style_profile = style_profile
    
    def classify_short_question(self, message: str) -> str:
        """
        分类短问句类型

        Args:
            message: 用户输入

        Returns:
            ShortQuestionType
        """
        message_clean = message.strip().rstrip("？?！!")

        # 检查是否匹配已知模式（精确匹配或后缀匹配，避免子串误匹配）
        for qtype, patterns in self.SHORT_QUESTION_PATTERNS.items():
            for pattern in patterns:
                pattern_clean = pattern.rstrip("？?！!")
                # 精确匹配 或 以 pattern_clean 结尾
                if message_clean == pattern_clean or message_clean.endswith(pattern_clean):
                    return qtype

        # 长度 <=3 且包含疑问词（整词匹配，避免子串）
        if len(message_clean) <= 3:
            question_words = ["什么", "为什么", "怎么", "啊", "嗯", "哦", "吗", "啥"]
            for word in question_words:
                if message_clean == word:
                    return ShortQuestionType.SHORT_CLARIFICATION

        return ShortQuestionType.UNKNOWN
    
    def is_short_question(self, message: str) -> bool:
        """检测是否为短问句"""
        return self.classify_short_question(message) != ShortQuestionType.UNKNOWN
    
    def _get_context_summary(self, recent_messages: Optional[List[Dict]] = None) -> str:
        """获取上下文摘要（用于重复请求）"""
        if not recent_messages or len(recent_messages) < 2:
            return "刚才的内容"
        
        # 找最近一条助手回复
        for msg in reversed(recent_messages[:-1]):  # 排除当前输入
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # 截取前 30 字
                return content[:30] + "..." if len(content) > 30 else content
        
        return "刚才的内容"
    
    def _select_variant(
        self,
        variants: List[str],
        mode: str,
    ) -> str:
        """选择变体，避免重复"""
        if not variants:
            return "嗯？"
        
        # 如果有 style_profile，使用它来选择
        if self.style_profile:
            index = self.style_profile.select_variant_index(mode, len(variants))
            return variants[index]
        
        return random.choice(variants)
    
    def verbalize(
        self,
        message: str,
        recent_messages: Optional[List[Dict]] = None,
    ) -> str:
        """
        生成自然回复
        
        Args:
            message: 用户输入
            recent_messages: 最近消息上下文
        
        Returns:
            自然语言回复（1~2 句）
        """
        qtype = self.classify_short_question(message)
        
        # 根据类型选择变体
        if qtype == ShortQuestionType.SHORT_CLARIFICATION:
            return self._select_variant(self.SHORT_CLARIFICATION, qtype)
        
        elif qtype == ShortQuestionType.SURPRISED_FOLLOWUP:
            return self._select_variant(self.SURPRISED_FOLLOWUP, qtype)
        
        elif qtype == ShortQuestionType.WHY_PROBE:
            return self._select_variant(self.WHY_PROBE, qtype)
        
        elif qtype == ShortQuestionType.MEANING_PROBE:
            return self._select_variant(self.MEANING_PROBE, qtype)
        
        elif qtype == ShortQuestionType.REPEAT_REQUEST:
            context = self._get_context_summary(recent_messages)
            variants = [v.format(context=context) for v in self.REPEAT_REQUEST]
            return self._select_variant(variants, qtype)

        elif qtype == ShortQuestionType.INVITATION:
            return self._select_variant(self.INVITATION, qtype)

        # 默认
        return self._select_variant(self.GENERIC_SHORT, "generic")


# 便捷函数
def verbalize_question(
    message: str,
    recent_messages: Optional[List[Dict]] = None,
    relationship_context: Optional[RelationshipContext] = None,
    style_profile: Optional[StyleProfile] = None,
) -> str:
    """便捷函数：生成 question 回复"""
    verbalizer = QuestionVerbalizer(
        relationship_context=relationship_context,
        style_profile=style_profile,
    )
    return verbalizer.verbalize(message, recent_messages)


def is_short_question(message: str) -> bool:
    """便捷函数：检测是否为短问句"""
    return QuestionVerbalizer().is_short_question(message)
