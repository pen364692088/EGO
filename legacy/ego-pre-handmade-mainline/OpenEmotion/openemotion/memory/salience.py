"""
Salience - 事件重要性评分

职责: 判断事件是否值得进入更高层处理

设计原则:
- 不是纯关键词命中
- 多因子综合评分
- 可解释的评分过程

评分因子:
- novelty: 新颖度
- self_impact: 自我影响
- goal_relevance: 目标相关性
- contradiction: 冲突度

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import math


@dataclass
class SalienceBreakdown:
    """
    重要性评分分解

    便于审计和理解评分来源
    """
    novelty: float = 0.0
    self_impact: float = 0.0
    goal_relevance: float = 0.0
    contradiction: float = 0.0
    user_instruction_boost: float = 0.0  # P4-B: 显式用户目标/偏好/约束 boost

    # 权重
    novelty_weight: float = 0.25
    self_impact_weight: float = 0.35
    goal_relevance_weight: float = 0.25
    contradiction_weight: float = 0.15
    user_instruction_boost_weight: float = 0.2  # P4-B: 额外权重

    # 原因说明
    reasons: list[str] = field(default_factory=list)

    def compute_weighted_score(self) -> float:
        """计算加权总分"""
        weighted_sum = (
            self.novelty * self.novelty_weight +
            self.self_impact * self.self_impact_weight +
            self.goal_relevance * self.goal_relevance_weight +
            self.contradiction * self.contradiction_weight +
            self.user_instruction_boost * self.user_instruction_boost_weight
        )
        return min(1.0, weighted_sum)

    def to_dict(self) -> dict[str, Any]:
        return {
            "novelty": round(self.novelty, 3),
            "self_impact": round(self.self_impact, 3),
            "goal_relevance": round(self.goal_relevance, 3),
            "contradiction": round(self.contradiction, 3),
            "user_instruction_boost": round(self.user_instruction_boost, 3),
            "weighted_score": round(self.compute_weighted_score(), 3),
            "reasons": self.reasons,
        }


class SalienceEvaluator:
    """
    重要性评分器

    职责: 评估事件的重要性，决定是否值得进入更高层处理
    """

    def __init__(self):
        # 已见过的模式（用于新颖度计算）
        self.seen_patterns: dict[str, int] = {}
        self.total_events: int = 0

    def evaluate(
        self,
        event_type: str,
        event_content: str,
        current_state: Any,  # LatentSelfState
        event_metadata: Optional[dict] = None,
    ) -> SalienceBreakdown:
        """
        评估事件重要性

        Args:
            event_type: 事件类型
            event_content: 事件内容
            current_state: 当前自我状态
            event_metadata: 事件元数据

        Returns:
            SalienceBreakdown: 评分分解
        """
        breakdown = SalienceBreakdown()

        # 1. 计算新颖度
        breakdown.novelty = self._compute_novelty(event_type, event_content)

        # 2. 计算自我影响
        breakdown.self_impact = self._compute_self_impact(
            event_type, event_content, current_state, event_metadata
        )

        # 3. 计算目标相关性
        breakdown.goal_relevance = self._compute_goal_relevance(
            event_type, event_content, current_state
        )

        # 4. 计算冲突度
        breakdown.contradiction = self._compute_contradiction(
            event_type, event_content, current_state
        )

        # 5. P4-B: 检测显式用户目标/偏好/约束，给与 boost
        breakdown.user_instruction_boost = self._compute_user_instruction_boost(
            event_type, event_content
        )

        # 更新统计
        self.total_events += 1
        pattern_key = self._extract_pattern_key(event_type, event_content)
        self.seen_patterns[pattern_key] = self.seen_patterns.get(pattern_key, 0) + 1

        return breakdown

    def _compute_novelty(self, event_type: str, event_content: str) -> float:
        """
        计算新颖度

        高新颖度 = 未见过的模式
        低新颖度 = 常见模式
        """
        pattern_key = self._extract_pattern_key(event_type, event_content)
        seen_count = self.seen_patterns.get(pattern_key, 0)

        # 首次见到 = 1.0，重复出现逐渐降低
        if self.total_events == 0:
            return 1.0

        novelty = 1.0 / (1.0 + seen_count * 0.3)

        # 检查内容独特性
        content_novelty = self._compute_content_novelty(event_content)

        return min(1.0, (novelty + content_novelty) / 2)

    def _compute_content_novelty(self, content: str) -> float:
        """
        计算内容独特性

        基于内容长度、特殊词汇、语气等
        """
        if not content:
            return 0.0

        score = 0.0

        # 长度因子
        if len(content) > 200:
            score += 0.2

        # 特殊标记
        novelty_markers = ["!", "?", "...", "竟然", "居然", "没想到", "意外"]
        for marker in novelty_markers:
            if marker in content:
                score += 0.15

        # 情感标记
        emotion_markers = ["很", "非常", "特别", "极其", "太"]
        for marker in emotion_markers:
            if marker in content:
                score += 0.1

        return min(1.0, score)

    def _compute_self_impact(
        self,
        event_type: str,
        event_content: str,
        current_state: Any,
        event_metadata: Optional[dict],
    ) -> float:
        """
        计算自我影响

        事件是否直接影响"我"的状态
        """
        impact = 0.0

        # 事件类型影响
        high_impact_types = {
            "user_message": 0.4,
            "world_event": 0.5,
            "boundary_crossing": 0.7,
            "task_complete": 0.3,
            "task_start": 0.2,
        }
        impact += high_impact_types.get(event_type, 0.1)

        # 内容影响标记
        impact_markers = [
            ("你", 0.15),
            ("我", 0.1),
            ("帮我", 0.2),
            ("谢谢你", 0.25),
            ("对不起", 0.3),
            ("你错了", 0.35),
            ("做得好", 0.25),
            ("太慢了", 0.2),
        ]
        for marker, delta in impact_markers:
            if marker in event_content:
                impact += delta

        # 当前状态影响
        if hasattr(current_state, 'affective_tension'):
            # 如果当前状态已经不稳定，影响更大
            if current_state.affective_tension.arousal > 0.6:
                impact *= 1.2

        return min(1.0, impact)

    def _compute_goal_relevance(
        self,
        event_type: str,
        event_content: str,
        current_state: Any,
    ) -> float:
        """
        计算目标相关性

        事件是否与当前激活的目标相关
        """
        if not hasattr(current_state, 'goals'):
            return 0.0

        active_goals = current_state.get_active_goals()
        if not active_goals:
            return 0.0

        relevance = 0.0

        # 检查内容与目标描述的匹配
        content_lower = event_content.lower()
        for goal in active_goals:
            # 简单的关键词匹配（可扩展为语义匹配）
            goal_keywords = self._extract_keywords(goal.description)
            for keyword in goal_keywords:
                if keyword in content_lower:
                    relevance += goal.activation * 0.3

        return min(1.0, relevance)

    def _compute_contradiction(
        self,
        event_type: str,
        event_content: str,
        current_state: Any,
    ) -> float:
        """
        计算冲突度

        事件是否与当前状态/信念/目标冲突
        """
        contradiction = 0.0

        # 检查与约束的冲突
        if hasattr(current_state, 'constraints'):
            active_constraints = current_state.get_active_constraints()
            contradiction_keywords = ["不要", "别", "禁止", "必须", "不能"]

            for constraint in active_constraints:
                for kw in contradiction_keywords:
                    if kw in constraint.description and kw in event_content:
                        contradiction += 0.3

        # 检查与情感的冲突
        if hasattr(current_state, 'affective_tension'):
            valence = current_state.affective_tension.valence

            # 正面情绪时遇到负面事件
            if valence > 0.3:
                negative_markers = ["不", "错", "失败", "问题", "糟糕", "不行"]
                for marker in negative_markers:
                    if marker in event_content:
                        contradiction += 0.2

            # 负面情绪时遇到正面事件
            elif valence < -0.3:
                positive_markers = ["好", "成功", "完成", "谢谢", "棒"]
                for marker in positive_markers:
                    if marker in event_content:
                        contradiction += 0.15

        return min(1.0, contradiction)

    def _compute_user_instruction_boost(
        self,
        event_type: str,
        event_content: str,
    ) -> float:
        """
        P4-B: 检测显式用户目标/偏好/约束，给与 boost
        
        这 4 类事件需要稳定通过 memory gate：
        - 用户显式偏好 (记住、偏好、喜欢)
        - 用户明确目标 (要、想做、完成)
        - 用户边界/约束 (不要、别、禁止)
        - 用户纠正系统行为 (不对、重新、改为)
        
        Returns:
            float: 0.0 - 1.0 的 boost 值
        """
        if not event_content:
            return 0.0
        
        content_lower = event_content.lower()
        
        # 关键词模式检测
        preference_keywords = [
            "记住", "偏好", "喜欢", "想要", "希望", "以后", "之后",
            "我的", "给我", "请用", "采用", "设置", "调整"
        ]
        goal_keywords = [
            "要", "想做", "完成", "实现", "达到", "目标", "目的是",
            "先", "首先", "下一步", "最小", "闭环"
        ]
        constraint_keywords = [
            "不要", "别", "禁止", "不能", "不要", "尽量", "控制",
            "简短", "短一点", "少一点", "别铺", "别展开"
        ]
        correction_keywords = [
            "不对", "不是", "重新", "改为", "换", "改成", "错了",
            "我不是说", "我的意思是"
        ]
        
        boost = 0.0
        
        # 检测匹配
        for kw in preference_keywords:
            if kw in content_lower:
                boost = max(boost, 0.6)
                break
        
        for kw in goal_keywords:
            if kw in content_lower:
                boost = max(boost, 0.5)
                break
        
        for kw in constraint_keywords:
            if kw in content_lower:
                boost = max(boost, 0.6)
                break
        
        for kw in correction_keywords:
            if kw in content_lower:
                boost = max(boost, 0.7)
                break
        
        # 额外：检测句子模式
        if "记住" in content_lower or "偏好" in content_lower:
            boost = max(boost, 0.8)
        if "别铺" in content_lower or "短" in content_lower:
            boost = max(boost, 0.7)
            
        return min(1.0, boost)

    def _extract_pattern_key(self, event_type: str, event_content: str) -> str:
        """提取模式键（用于新颖度计算）"""
        # 简化内容为关键词组合
        words = event_content.lower().split()[:5]
        return f"{event_type}:{':'.join(words)}"

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        # 简单实现：分词 + 过滤停用词
        stop_words = {"的", "了", "是", "在", "我", "你", "他", "她", "它", "这", "那"}
        words = text.lower().split()
        return [w for w in words if w not in stop_words and len(w) > 1]

    def get_salience_level(self, score: float) -> str:
        """获取重要性级别"""
        if score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        else:
            return "low"


# 默认实例
default_salience_evaluator = SalienceEvaluator()


# 版本标记
SALIENCE_V1_VERSION = "1.0.0"
