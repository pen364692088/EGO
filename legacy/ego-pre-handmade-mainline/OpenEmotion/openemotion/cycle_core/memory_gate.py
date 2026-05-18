"""
Memory Gate - 记忆写入决策

职责: 决定事件如何写入记忆系统

决策类型:
- 不写 (skip)
- 只写 event layer
- 写 narrative candidate
- 写 policy candidate

决策依据:
- salience score
- current state
- event type

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import math


class MemoryWriteDecision(str, Enum):
    """记忆写入决策类型"""
    SKIP = "skip"  # 不写
    EVENT_ONLY = "event_only"  # 只写事件层
    NARRATIVE_CANDIDATE = "narrative_candidate"  # 写叙事候选
    POLICY_CANDIDATE = "policy_candidate"  # 写策略候选
    FULL_WRITE = "full_write"  # 全量写入


@dataclass
class MemoryGateResult:
    """
    记忆门决策结果
    """
    decision: MemoryWriteDecision
    salience_score: float
    reasons: list[str] = field(default_factory=list)

    # 写入详情
    event_layer: bool = False
    narrative_candidate: bool = False
    policy_candidate: bool = False

    # 附加信息
    narrative_theme: Optional[str] = None
    policy_type: Optional[str] = None

    # 置信度
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "salience_score": round(self.salience_score, 3),
            "reasons": self.reasons,
            "event_layer": self.event_layer,
            "narrative_candidate": self.narrative_candidate,
            "policy_candidate": self.policy_candidate,
            "narrative_theme": self.narrative_theme,
            "policy_type": self.policy_type,
            "confidence": round(self.confidence, 3),
        }


class MemoryGate:
    """
    记忆门控制器

    职责: 根据事件特征和当前状态，决定如何写入记忆
    """

    def __init__(self):
        # 决策阈值（可调）
        self.event_threshold = 0.2  # 高于此值才写事件
        self.narrative_threshold = 0.5  # 高于此值才写叙事候选
        self.policy_threshold = 0.7  # 高于此值才写策略候选

        # 状态影响权重
        self.state_weight = 0.3
        self.salience_weight = 0.5
        self.event_type_weight = 0.2

    def decide(
        self,
        salience_breakdown: Any,  # SalienceBreakdown
        event_type: str,
        current_state: Any,  # LatentSelfState
        event_metadata: Optional[dict] = None,
    ) -> MemoryGateResult:
        """
        做出记忆写入决策

        Args:
            salience_breakdown: 重要性评分分解
            event_type: 事件类型
            current_state: 当前状态
            event_metadata: 事件元数据

        Returns:
            MemoryGateResult: 决策结果
        """
        result = MemoryGateResult(
            decision=MemoryWriteDecision.SKIP,
            salience_score=salience_breakdown.compute_weighted_score(),
        )

        # 综合评分
        composite_score = self._compute_composite_score(
            salience_breakdown, event_type, current_state
        )

        result.salience_score = composite_score
        result.reasons.extend(salience_breakdown.reasons)

        # 决策逻辑：分级判断
        if composite_score < self.event_threshold:
            result.decision = MemoryWriteDecision.SKIP
            result.reasons.append("重要性过低，跳过写入")

        elif composite_score < self.narrative_threshold:
            result.decision = MemoryWriteDecision.EVENT_ONLY
            result.event_layer = True
            result.reasons.append("重要性中等，仅写入事件层")

        elif composite_score < self.policy_threshold:
            # 检查是否适合生成叙事
            if self._should_create_narrative(event_type, current_state):
                result.decision = MemoryWriteDecision.NARRATIVE_CANDIDATE
                result.event_layer = True
                result.narrative_candidate = True
                result.narrative_theme = self._infer_narrative_theme(event_type, current_state)
                result.reasons.append("重要性较高，生成叙事候选")
            else:
                result.decision = MemoryWriteDecision.EVENT_ONLY
                result.event_layer = True
                result.reasons.append("重要性较高但不适合叙事，仅写入事件层")

        else:
            # 高重要性事件，检查是否适合生成策略
            result.event_layer = True

            if self._should_create_policy(event_type, current_state, salience_breakdown):
                result.decision = MemoryWriteDecision.POLICY_CANDIDATE
                result.policy_candidate = True
                result.policy_type = self._infer_policy_type(event_type, salience_breakdown)
                result.reasons.append("高重要性，生成策略候选")

            if self._should_create_narrative(event_type, current_state):
                result.narrative_candidate = True
                result.narrative_theme = self._infer_narrative_theme(event_type, current_state)
                result.reasons.append("生成叙事候选")

            if result.policy_candidate or result.narrative_candidate:
                result.decision = MemoryWriteDecision.FULL_WRITE
            else:
                result.decision = MemoryWriteDecision.EVENT_ONLY

        # 计算置信度
        result.confidence = self._compute_confidence(composite_score, event_type, current_state)

        return result

    def _compute_composite_score(
        self,
        salience_breakdown: Any,
        event_type: str,
        current_state: Any,
    ) -> float:
        """
        计算综合评分

        结合 salience + state + event_type
        """
        salience_score = salience_breakdown.compute_weighted_score()

        # 状态影响
        state_factor = 0.0
        if hasattr(current_state, 'affective_tension'):
            # 高唤醒时更敏感
            arousal = current_state.affective_tension.arousal
            state_factor += arousal * 0.2

            # 低稳定性时更敏感
            if hasattr(current_state, 'stability'):
                instability = 1.0 - current_state.stability.overall_stability
                state_factor += instability * 0.3

        # 事件类型影响
        event_type_factor = 0.0
        high_priority_types = ["boundary_crossing", "world_event", "user_message"]
        if event_type in high_priority_types:
            event_type_factor = 0.3

        # 加权组合
        composite = (
            salience_score * self.salience_weight +
            state_factor * self.state_weight +
            event_type_factor * self.event_type_weight
        )

        return min(1.0, composite)

    def _should_create_narrative(self, event_type: str, current_state: Any) -> bool:
        """
        判断是否应该创建叙事候选

        叙事适用于：连续性事件、有意义的变化
        """
        # 事件类型检查
        narrative_suitable_types = [
            "task_complete",
            "goal_set",
            "boundary_crossing",
            "user_message",
            "world_event",
        ]
        if event_type not in narrative_suitable_types:
            return False

        # 状态检查：需要有足够的稳定性来形成叙事
        if hasattr(current_state, 'stability'):
            if current_state.stability.oscillation_detected:
                # 震荡中不适合形成叙事
                return False

        return True

    def _should_create_policy(
        self,
        event_type: str,
        current_state: Any,
        salience_breakdown: Any,
    ) -> bool:
        """
        判断是否应该创建策略候选

        策略适用于：重复模式、强冲突、重要偏好
        """
        # 高冲突度
        if salience_breakdown.contradiction > 0.5:
            return True

        # 高目标相关性
        if salience_breakdown.goal_relevance > 0.6:
            return True

        # 特定事件类型
        policy_suitable_types = ["boundary_crossing", "world_event"]
        if event_type in policy_suitable_types:
            return True

        return False

    def _infer_narrative_theme(self, event_type: str, current_state: Any) -> str:
        """推断叙事主题"""
        theme_map = {
            "task_complete": "progress",
            "goal_set": "aspiration",
            "boundary_crossing": "boundary",
            "user_message": "interaction",
            "world_event": "world",
        }
        return theme_map.get(event_type, "general")

    def _infer_policy_type(self, event_type: str, salience_breakdown: Any) -> str:
        """推断策略类型"""
        if salience_breakdown.contradiction > 0.6:
            return "avoid"
        elif salience_breakdown.goal_relevance > 0.6:
            return "prefer"
        else:
            return "observe"

    def _compute_confidence(
        self,
        composite_score: float,
        event_type: str,
        current_state: Any,
    ) -> float:
        """
        计算决策置信度

        基于评分的明确程度
        """
        # 评分极端时置信度高，中间值时置信度低
        score_clarity = 1.0 - abs(composite_score - 0.5) * 2

        # 基础置信度
        base_confidence = 0.5 + score_clarity * 0.3

        # 状态稳定性加成
        if hasattr(current_state, 'stability'):
            base_confidence += current_state.stability.overall_stability * 0.2

        return min(1.0, base_confidence)

    def adjust_thresholds(
        self,
        event_threshold: Optional[float] = None,
        narrative_threshold: Optional[float] = None,
        policy_threshold: Optional[float] = None,
    ):
        """动态调整阈值"""
        if event_threshold is not None:
            self.event_threshold = event_threshold
        if narrative_threshold is not None:
            self.narrative_threshold = narrative_threshold
        if policy_threshold is not None:
            self.policy_threshold = policy_threshold


# 默认实例
default_memory_gate = MemoryGate()


# 版本标记
MEMORY_GATE_V1_VERSION = "1.0.0"
