"""
Verbalizer v2 - EgoCore

自然表达层：根据 OutwardResponsePackage 生成自然语言回复。

v2 改进：
- 每个 social mode 支持多个自然变体
- 使用 conversation_turn_index 区分轮次
- 禁止外显内部判断（testing/probe/repair 等）
- 回复缩短到 1~2 句
- 关系连续性优先于模板

归属：EgoCore
作用：只能按 contract 组织自然语言，不能擅自升级。
"""

import logging
import random
from typing import Dict, Any, List, Optional

from egocore.contracts.outward_response_package_v1 import (
    OutwardResponsePackage,
    ResponsePlan,
    SpeakerMode,
)

logger = logging.getLogger(__name__)


class Verbalizer:
    """
    自然表达层 v2
    
    关键原则：
    - 内部判断可以深，外部表达必须短
    - 不解释系统状态，只体现关系连续性
    - 同一 response_plan 支持多个变体
    - 优先 1~2 句短回复
    """
    
    # 内部字段名/判断词，绝不允许出现在用户回复中
    INTERNAL_PHRASES = {
        "testing", "probe", "repair", "route", "interpret", "mode", 
        "contract", "acknowledge_testing", "repair_relationship",
        "acknowledge_context", "acknowledge_affect", "shift_to_task",
        "我注意到这是你连续", "这轮我知道你是在", "不用再给你重复",
        "系统识别", "判断为", "切换到", "模式",
    }
    
    # ========================================
    # 自然表达变体库
    # ========================================
    
    # 首次问候变体 (conversation_turn_index = 1)
    GREETING_FIRST = [
        "👋 你好！有什么我可以帮你的吗？",
        "你好，我在。可以直接说你需要什么。",
        "嗨！我在这里。",
    ]
    
    # 第二次问候变体 (conversation_turn_index = 2)
    GREETING_SECOND = [
        "嗯，我在。",
        "收到，继续说。",
        "我在，刚才那条我记得。",
    ]
    
    # 第三次及以后问候变体
    GREETING_REPEAT = [
        "我在。",
        "嗯。",
        "收到。",
        "在的。",
    ]
    
    # affective probe 回复变体
    AFFECTIVE_PROBE = [
        "嗯，你这个提醒是对的。我换种更自然的方式跟你聊。",
        "好，我改一下。刚才确实太像模板了。",
        "收到。我尽量不那么机械。",
        "嗯，我注意到了。继续说吧，我在听。",
    ]
    
    # status ping 变体
    STATUS_PING = [
        "我在。",
        "在的。",
        "嗯？",
    ]
    
    # 感谢回复变体
    GRATEFUL = [
        "嗯。",
        "不客气。",
        "好的。",
    ]
    
    # 轻社交确认变体
    LIGHT_SOCIAL = [
        "嗯，收到了。",
        "好。",
        "收到。",
        "我在。",
    ]
    
    # 降级回复变体
    FALLBACK = [
        "我在。",
        "收到。",
        "嗯？",
    ]
    
    def _filter_internal_phrases(self, text: str) -> str:
        """过滤掉内部判断语言"""
        # 如果包含内部短语，返回安全默认
        text_lower = text.lower()
        for phrase in self.INTERNAL_PHRASES:
            if phrase.lower() in text_lower:
                # 返回一个安全的简短回复
                return random.choice(self.LIGHT_SOCIAL)
        return text
    
    def _select_variant(
        self,
        variants: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """选择一个变体，可基于上下文做轻微变化"""
        if not variants:
            return "我在。"
        
        # 简单随机选择
        return random.choice(variants)
    
    def _get_turn_index(self, context: Optional[Dict[str, Any]]) -> int:
        """获取会话轮次索引"""
        if context and "turn_index" in context:
            return context["turn_index"]
        return 1
    
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
            context: 额外上下文（包含 turn_index, last_reply_type 等）
            interpretation: 主体解释结果
        
        Returns:
            自然语言回复（1~2 句）
        """
        response_plan = package.response_plan
        turn_index = self._get_turn_index(context)
        
        # 根据 response_plan 选择回复
        if response_plan == ResponsePlan.WARM_GREETING:
            return self._verbalize_greeting(package, context, turn_index)
        
        elif response_plan == ResponsePlan.CONTEXT_AWARE:
            return self._verbalize_context_aware(package, context, turn_index)
        
        elif response_plan == ResponsePlan.TASK_STATUS:
            return self._verbalize_task_status(package, context)
        
        elif response_plan == ResponsePlan.RELATIONSHIP_REPAIR:
            return self._verbalize_affective_probe(package, context)
        
        elif response_plan == ResponsePlan.GRATEFUL_RESPONSE:
            return self._verbalize_grateful(package, context)
        
        elif response_plan == ResponsePlan.NEUTRAL_FALLBACK:
            return self._verbalize_fallback(package, context)
        
        else:  # SIMPLE_ACKNOWLEDGE
            return self._verbalize_light_social(package, context)
    
    def _verbalize_greeting(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
        turn_index: int,
    ) -> str:
        """问候回复 - 区分轮次"""
        # 第一轮：正常欢迎
        if turn_index <= 1:
            return self._select_variant(self.GREETING_FIRST, context)
        
        # 第二轮：简短确认
        elif turn_index == 2:
            return self._select_variant(self.GREETING_SECOND, context)
        
        # 第三轮及以后：极简
        else:
            return self._select_variant(self.GREETING_REPEAT, context)
    
    def _verbalize_context_aware(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
        turn_index: int,
    ) -> str:
        """上下文感知回复 - 不解释内部判断"""
        # 根据轮次选择变体
        if turn_index <= 1:
            return self._select_variant(self.GREETING_FIRST, context)
        elif turn_index == 2:
            return self._select_variant(self.GREETING_SECOND, context)
        else:
            return self._select_variant(self.GREETING_REPEAT, context)
    
    def _verbalize_task_status(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """任务状态汇报 - 保持简洁"""
        if package.task_context:
            task = package.task_context
            objective = task.get("objective", "任务")
            progress = task.get("progress", {})
            completed = progress.get("completed", 0)
            total = progress.get("total", 0)
            
            # 简洁版本
            return f"我在。当前有个任务：{objective[:30]}（{completed}/{total}）。说\"继续\"可以继续。"
        
        return self._select_variant(self.STATUS_PING, context)
    
    def _verbalize_affective_probe(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """关系修复回复 - 自然、承认、继续"""
        return self._select_variant(self.AFFECTIVE_PROBE, context)
    
    def _verbalize_grateful(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """感谢回复 - 极简"""
        return self._select_variant(self.GRATEFUL, context)
    
    def _verbalize_light_social(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """轻社交确认"""
        return self._select_variant(self.LIGHT_SOCIAL, context)
    
    def _verbalize_fallback(
        self,
        package: OutwardResponsePackage,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """降级回复 - 中性、自然"""
        return self._select_variant(self.FALLBACK, context)


# 全局实例
_verbalizer: Optional[Verbalizer] = None


def get_verbalizer() -> Verbalizer:
    """获取全局语言生成器"""
    global _verbalizer
    if _verbalizer is None:
        _verbalizer = Verbalizer()
    return _verbalizer


def verbalize(package: OutwardResponsePackage, context: Optional[Dict[str, Any]] = None) -> str:
    """便捷函数：生成回复"""
    return get_verbalizer().verbalize(package, context)
