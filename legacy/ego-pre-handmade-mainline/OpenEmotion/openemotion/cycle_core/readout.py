"""
Readout - 状态解码输出

职责: 把 latent/self state 解码成结构化输出

输出:
- response_tendency
- policy_hint

设计原则:
- appraisal 只做 readout，不是主驱动
- 输出必须是结构化字段，不是自然语言段落
- 同一状态 + 不同事件 = 不同输出

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ResponseTone(str, Enum):
    """响应语调"""
    WARM = "warm"
    NEUTRAL = "neutral"
    GUARDED = "guarded"
    APOLOGETIC = "apologetic"
    ENTHUSIASTIC = "enthusiastic"
    CAUTIOUS = "cautious"
    DIRECT = "direct"
    SOFT = "soft"


class ResponseLength(str, Enum):
    """响应长度"""
    BRIEF = "brief"
    MODERATE = "moderate"
    DETAILED = "detailed"


class HintType(str, Enum):
    """策略提示类型"""
    PREFER = "prefer"
    AVOID = "avoid"
    ESCALATE = "escalate"
    DEFER = "defer"
    IGNORE = "ignore"
    SEEK_CLARIFICATION = "seek_clarification"


@dataclass
class ResponseTendency:
    """
    响应倾向

    给 EgoCore 的参考，非强制
    """
    tone: ResponseTone = ResponseTone.NEUTRAL
    length: ResponseLength = ResponseLength.MODERATE
    urgency: float = 0.5  # 0-1

    # 附加建议
    avoid_topics: list[str] = field(default_factory=list)
    emphasize_topics: list[str] = field(default_factory=list)

    # 置信度
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "tone": self.tone.value,
            "length": self.length.value,
            "urgency": round(self.urgency, 3),
            "avoid_topics": self.avoid_topics,
            "emphasize_topics": self.emphasize_topics,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class PolicyHint:
    """
    策略提示

    给 EgoCore 的参考，非强制
    """
    hint_type: HintType = HintType.PREFER
    reason: str = ""
    confidence: float = 0.5

    # 有效期
    expires_at: Optional[datetime] = None

    # 附加信息
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hint_type": self.hint_type.value,
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "context": self.context,
        }


@dataclass
class ReadoutResult:
    """
    解码输出结果
    """
    response_tendency: ResponseTendency = field(default_factory=ResponseTendency)
    policy_hint: Optional[PolicyHint] = None

    # 置信度
    overall_confidence: float = 0.5

    # 原因说明
    reasons: list[str] = field(default_factory=list)

    # 元数据
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_tendency": self.response_tendency.to_dict(),
            "policy_hint": self.policy_hint.to_dict() if self.policy_hint else None,
            "overall_confidence": round(self.overall_confidence, 3),
            "reasons": self.reasons,
            "generated_at": self.generated_at.isoformat(),
        }


class ReadoutDecoder:
    """
    状态解码器

    职责: 把 latent state 解码成可消费的结构化输出
    """

    def __init__(self):
        # 语调映射规则
        self.tone_rules = {
            "high_trust": ResponseTone.WARM,
            "low_trust": ResponseTone.GUARDED,
            "positive_valence": ResponseTone.ENTHUSIASTIC,
            "negative_valence": ResponseTone.APOLOGETIC,
            "high_arousal": ResponseTone.DIRECT,
            "low_arousal": ResponseTone.SOFT,
        }

    def decode(
        self,
        current_state: Any,  # LatentSelfState
        event_dict: dict[str, Any],
        consolidation_result: Optional[Any] = None,
    ) -> ReadoutResult:
        """
        解码状态到输出

        Args:
            current_state: 当前自我状态
            event_dict: 事件数据
            consolidation_result: 整合结果（可选）

        Returns:
            ReadoutResult: 解码输出
        """
        result = ReadoutResult()

        # 1. 解码响应倾向
        result.response_tendency = self._decode_response_tendency(
            current_state, event_dict
        )

        # 2. 解码策略提示
        policy_hint = self._decode_policy_hint(
            current_state, event_dict, consolidation_result
        )
        if policy_hint:
            result.policy_hint = policy_hint

        # 3. 计算整体置信度
        result.overall_confidence = self._compute_overall_confidence(
            result.response_tendency, result.policy_hint
        )

        # 4. 生成原因说明
        result.reasons = self._generate_reasons(
            current_state, event_dict, result
        )

        return result

    def _decode_response_tendency(
        self,
        current_state: Any,
        event_dict: dict[str, Any],
    ) -> ResponseTendency:
        """
        解码响应倾向

        基于状态和事件特征
        """
        tendency = ResponseTendency()

        # 获取状态特征
        affective = current_state.affective_tension if hasattr(current_state, 'affective_tension') else None
        stability = current_state.stability if hasattr(current_state, 'stability') else None

        # 判断语调
        if affective:
            tendency.tone = self._infer_tone_from_affective(affective)

        # 判断长度
        event_type = event_dict.get("event_type", "")
        tendency.length = self._infer_length_from_event(event_type)

        # 判断紧急度
        tendency.urgency = self._infer_urgency(affective, event_dict)

        # 生成避免话题
        tendency.avoid_topics = self._infer_avoid_topics(current_state, event_dict)

        # 生成强调话题
        tendency.emphasize_topics = self._infer_emphasize_topics(current_state, event_dict)

        # 计算置信度
        tendency.confidence = self._compute_tendency_confidence(current_state)

        return tendency

    def _decode_policy_hint(
        self,
        current_state: Any,
        event_dict: dict[str, Any],
        consolidation_result: Optional[Any],
    ) -> Optional[PolicyHint]:
        """
        解码策略提示

        基于状态和整合结果
        """
        # 检查是否有来自 consolidation 的策略候选
        if consolidation_result and hasattr(consolidation_result, 'policy_candidates'):
            if consolidation_result.policy_candidates:
                # 使用第一个高置信度的候选
                for candidate in consolidation_result.policy_candidates:
                    if candidate.confidence > 0.6:
                        return PolicyHint(
                            hint_type=self._map_policy_type_to_hint(candidate.policy_type),
                            reason=candidate.description,
                            confidence=candidate.confidence,
                            context={"source": "consolidation"},
                        )

        # 基于状态生成提示
        return self._infer_policy_hint_from_state(current_state, event_dict)

    def _infer_tone_from_affective(self, affective: Any) -> ResponseTone:
        """从情感张力推断语调"""
        valence = affective.valence
        arousal = affective.arousal

        # 高唤醒 + 正面 = 热情
        if arousal > 0.6 and valence > 0.3:
            return ResponseTone.ENTHUSIASTIC

        # 高唤醒 + 负面 = 警惕
        if arousal > 0.6 and valence < -0.3:
            return ResponseTone.GUARDED

        # 低唤醒 + 正面 = 温和
        if arousal < 0.4 and valence > 0.3:
            return ResponseTone.WARM

        # 低唤醒 + 负面 = 道歉
        if arousal < 0.4 and valence < -0.3:
            return ResponseTone.APOLOGETIC

        # 极端负面 = 谨慎
        if valence < -0.6:
            return ResponseTone.CAUTIOUS

        return ResponseTone.NEUTRAL

    def _infer_length_from_event(self, event_type: str) -> ResponseLength:
        """从事件类型推断长度"""
        length_map = {
            "user_message": ResponseLength.MODERATE,
            "tool_result": ResponseLength.BRIEF,
            "task_complete": ResponseLength.MODERATE,
            "boundary_crossing": ResponseLength.DETAILED,
            "world_event": ResponseLength.DETAILED,
        }
        return length_map.get(event_type, ResponseLength.MODERATE)

    def _infer_urgency(self, affective: Any, event_dict: dict[str, Any]) -> float:
        """推断紧急度"""
        urgency = 0.5

        # 情感张力影响
        if affective:
            urgency += affective.arousal * 0.3

        # 事件类型影响
        event_type = event_dict.get("event_type", "")
        high_urgency_types = ["boundary_crossing", "world_event"]
        if event_type in high_urgency_types:
            urgency += 0.2

        # 内容标记
        content = event_dict.get("content", "")
        urgency_markers = ["紧急", "马上", "立刻", "现在", "快点"]
        for marker in urgency_markers:
            if marker in content:
                urgency += 0.1

        return min(1.0, urgency)

    def _infer_avoid_topics(self, current_state: Any, event_dict: dict[str, Any]) -> list[str]:
        """推断避免话题"""
        avoid = []

        # 检查活跃约束
        if hasattr(current_state, 'constraints'):
            active_constraints = current_state.get_active_constraints(threshold=0.7)
            for c in active_constraints:
                if "不要" in c.description or "禁止" in c.description:
                    avoid.append(c.description)

        return avoid

    def _infer_emphasize_topics(self, current_state: Any, event_dict: dict[str, Any]) -> list[str]:
        """推断强调话题"""
        emphasize = []

        # 检查活跃目标
        if hasattr(current_state, 'goals'):
            active_goals = current_state.get_active_goals(threshold=0.5)
            for g in active_goals[:2]:  # 最多两个
                emphasize.append(g.description)

        return emphasize

    def _compute_tendency_confidence(self, current_state: Any) -> float:
        """计算倾向置信度"""
        confidence = 0.5

        # 状态稳定性加成
        if hasattr(current_state, 'stability'):
            confidence += current_state.stability.overall_stability * 0.3

        # 状态更新次数加成
        if hasattr(current_state, 'update_count'):
            if current_state.update_count > 10:
                confidence += 0.2

        return min(1.0, confidence)

    def _map_policy_type_to_hint(self, policy_type: str) -> HintType:
        """映射策略类型到提示类型"""
        mapping = {
            "preference": HintType.PREFER,
            "constraint": HintType.AVOID,
            "rule": HintType.DEFER,
        }
        return mapping.get(policy_type, HintType.PREFER)

    def _infer_policy_hint_from_state(
        self,
        current_state: Any,
        event_dict: dict[str, Any],
    ) -> Optional[PolicyHint]:
        """从状态推断策略提示"""
        # 检查关系偏向
        if hasattr(current_state, 'relation_biases'):
            user_id = event_dict.get("actor", "")
            if user_id in current_state.relation_biases:
                bias = current_state.relation_biases[user_id]

                if bias.relation_pattern == "avoiding":
                    return PolicyHint(
                        hint_type=HintType.AVOID,
                        reason=f"关系偏向: {bias.relation_pattern}",
                        confidence=0.6,
                    )
                elif bias.relation_pattern == "seeking":
                    return PolicyHint(
                        hint_type=HintType.PREFER,
                        reason=f"关系偏向: {bias.relation_pattern}",
                        confidence=0.6,
                    )

        # 检查情感张力
        if hasattr(current_state, 'affective_tension'):
            affective = current_state.affective_tension

            if affective.valence < -0.5 and affective.arousal > 0.6:
                return PolicyHint(
                    hint_type=HintType.CAUTIOUS,
                    reason="高负面情感张力",
                    confidence=0.5,
                )

        return None

    def _compute_overall_confidence(
        self,
        tendency: ResponseTendency,
        hint: Optional[PolicyHint],
    ) -> float:
        """计算整体置信度"""
        confidences = [tendency.confidence]
        if hint:
            confidences.append(hint.confidence)

        return sum(confidences) / len(confidences)

    def _generate_reasons(
        self,
        current_state: Any,
        event_dict: dict[str, Any],
        result: ReadoutResult,
    ) -> list[str]:
        """生成原因说明"""
        reasons = []

        # 语调原因
        if hasattr(current_state, 'affective_tension'):
            affective = current_state.affective_tension
            reasons.append(
                f"情感张力: valence={affective.valence:.2f}, arousal={affective.arousal:.2f}"
            )

        # 策略提示原因
        if result.policy_hint:
            reasons.append(f"策略提示: {result.policy_hint.reason}")

        return reasons


# 默认实例
default_readout_decoder = ReadoutDecoder()


# 版本标记
READOUT_V1_VERSION = "1.0.0"
