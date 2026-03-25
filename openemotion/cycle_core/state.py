"""
Latent Self State - 最小内部状态

职责: 定义循环主体核的内部状态表示

设计原则:
- 状态是连续可更新的
- 不是简单 tag 列表
- 能被序列事件逐步推移
- 支持 state diff / merge / decay

版本: v1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import math


@dataclass
class IdentityAnchors:
    """
    身份锚点的当前投影

    这些是从 identity_invariants 投影出来的当前状态，
    不是完整的身份定义。
    """
    # 核心特质（连续值，0-1）
    openness: float = 0.5
    conscientiousness: float = 0.5
    agreeableness: float = 0.5
    emotional_stability: float = 0.5

    # 价值取向（连续值，0-1）
    autonomy: float = 0.5
    competence: float = 0.5
    relatedness: float = 0.5

    # 稳定性指标
    anchor_stability: float = 1.0

    def decay(self, rate: float = 0.01):
        """向中性值衰减"""
        self.openness = self._decay_toward(self.openness, 0.5, rate)
        self.conscientiousness = self._decay_toward(self.conscientiousness, 0.5, rate)
        self.agreeableness = self._decay_toward(self.agreeableness, 0.5, rate)
        self.emotional_stability = self._decay_toward(self.emotional_stability, 0.5, rate)

    def _decay_toward(self, value: float, target: float, rate: float) -> float:
        """向目标值衰减"""
        return value + (target - value) * rate


@dataclass
class GoalActivation:
    """
    目标激活状态

    每个目标有激活强度和当前状态
    """
    goal_id: str
    description: str
    activation: float = 0.0  # 0-1，激活强度
    progress: float = 0.0  # 0-1，完成进度
    priority: float = 0.5  # 0-1，优先级
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activated_at: Optional[datetime] = None


@dataclass
class ConstraintActivation:
    """
    约束激活状态

    约束是"不要做某事"的规则
    """
    constraint_id: str
    description: str
    activation: float = 0.0  # 0-1，激活强度
    strictness: float = 0.5  # 0-1，严格程度
    source: str = "system"  # 来源：system/user/learned


@dataclass
class AffectiveTension:
    """
    情感张力（连续值）

    这是"连续值，不要做成纯枚举"的核心实现
    """
    # 效价：正面(1) 到 负面(-1)
    valence: float = 0.0

    # 唤醒度：平静(0) 到 激动(1)
    arousal: float = 0.0

    # 主导性：被动(0) 到 主动(1)
    dominance: float = 0.5

    # 持续时间因子：新事件影响大，旧事件影响衰减
    recency_weight: float = 1.0

    def update(self, delta_valence: float, delta_arousal: float, delta_dominance: float = 0.0):
        """更新张力（带衰减）"""
        self.valence = max(-1.0, min(1.0, self.valence * 0.8 + delta_valence * 0.2))
        self.arousal = max(0.0, min(1.0, self.arousal * 0.8 + delta_arousal * 0.2))
        self.dominance = max(0.0, min(1.0, self.dominance * 0.8 + delta_dominance * 0.2))
        self.recency_weight = 1.0

    def decay(self, rate: float = 0.05):
        """自然衰减"""
        self.valence *= (1 - rate)
        self.arousal *= (1 - rate)
        self.recency_weight *= (1 - rate)

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
            "recency_weight": round(self.recency_weight, 3),
        }


@dataclass
class ObjectStance:
    """
    对象立场

    对"某个对象"（人/物/概念）的态度
    """
    object_id: str
    object_type: str  # person/concept/object/goal

    # 立场：负面(-1) 到 正面(1)
    stance: float = 0.0

    # 置信度：0-1
    confidence: float = 0.0

    # 接触次数
    contact_count: int = 0

    # 最近接触时间
    last_contact_at: Optional[datetime] = None

    # 关键事件摘要
    key_events: list[str] = field(default_factory=list)


@dataclass
class RelationBias:
    """
    关系偏向

    对特定用户的关系倾向
    """
    user_id: str

    # 信任度：0-1
    trust: float = 0.5

    # 亲密度：0-1
    intimacy: float = 0.3

    # 权力感知：对方更有权(1) 到 我更有权(0)
    power_perception: float = 0.5

    # 互动历史
    interaction_count: int = 0
    positive_count: int = 0
    negative_count: int = 0

    # 关系模式
    relation_pattern: str = "neutral"  # neutral/seeking/avoiding/conflicted

    def update_from_event(self, positive: bool, impact: float = 0.1):
        """从事件更新关系偏向"""
        self.interaction_count += 1
        if positive:
            self.positive_count += 1
            self.trust = min(1.0, self.trust + impact * 0.1)
            self.intimacy = min(1.0, self.intimacy + impact * 0.05)
        else:
            self.negative_count += 1
            self.trust = max(0.0, self.trust - impact * 0.15)
            self.intimacy = max(0.0, self.intimacy - impact * 0.1)

        # 更新关系模式
        self._update_pattern()

    def _update_pattern(self):
        """更新关系模式"""
        if self.interaction_count < 3:
            self.relation_pattern = "neutral"
            return

        pos_ratio = self.positive_count / max(1, self.interaction_count)

        if pos_ratio > 0.7:
            self.relation_pattern = "seeking"
        elif pos_ratio < 0.3:
            self.relation_pattern = "avoiding"
        elif abs(self.trust - 0.5) < 0.2 and self.interaction_count > 5:
            self.relation_pattern = "conflicted"
        else:
            self.relation_pattern = "neutral"


@dataclass
class StabilityMetrics:
    """
    稳定性指标

    衡量状态是否稳定，还是在剧烈变化
    """
    # 整体稳定性：0(不稳定) 到 1(稳定)
    overall_stability: float = 1.0

    # 漂移指标：最近状态变化幅度
    drift_magnitude: float = 0.0

    # 一致性：最近决策是否一致
    consistency: float = 1.0

    # 震荡检测：是否在两个极端间反复
    oscillation_detected: bool = False
    oscillation_count: int = 0

    def record_change(self, magnitude: float):
        """记录状态变化"""
        self.drift_magnitude = magnitude
        self.overall_stability = max(0.0, 1.0 - magnitude * 0.5)

        # 检测震荡
        if magnitude > 0.3:
            self.oscillation_count += 1
            if self.oscillation_count > 3:
                self.oscillation_detected = True

    def decay(self, rate: float = 0.02):
        """自然恢复"""
        self.overall_stability = min(1.0, self.overall_stability + rate)
        self.drift_magnitude = max(0.0, self.drift_magnitude - rate * 0.5)


@dataclass
class LatentSelfState:
    """
    最小内部状态 - 主类

    这是循环主体核的核心状态表示
    """
    # 身份锚点投影
    identity: IdentityAnchors = field(default_factory=IdentityAnchors)

    # 目标激活
    goals: dict[str, GoalActivation] = field(default_factory=dict)

    # 约束激活
    constraints: dict[str, ConstraintActivation] = field(default_factory=dict)

    # 情感张力（连续值）
    affective_tension: AffectiveTension = field(default_factory=AffectiveTension)

    # 对象立场
    object_stances: dict[str, ObjectStance] = field(default_factory=dict)

    # 关系偏向
    relation_biases: dict[str, RelationBias] = field(default_factory=dict)

    # 稳定性指标
    stability: StabilityMetrics = field(default_factory=StabilityMetrics)

    # 元数据
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    update_count: int = 0

    def update_goal(self, goal_id: str, description: str, delta_activation: float = 0.0, delta_progress: float = 0.0):
        """更新目标激活"""
        if goal_id not in self.goals:
            self.goals[goal_id] = GoalActivation(
                goal_id=goal_id,
                description=description,
            )

        goal = self.goals[goal_id]
        goal.activation = max(0.0, min(1.0, goal.activation + delta_activation))
        goal.progress = max(0.0, min(1.0, goal.progress + delta_progress))
        goal.last_activated_at = datetime.now(timezone.utc)

        self._record_update()

    def update_constraint(self, constraint_id: str, description: str, activation: float, strictness: float = 0.5, source: str = "system"):
        """更新约束激活"""
        self.constraints[constraint_id] = ConstraintActivation(
            constraint_id=constraint_id,
            description=description,
            activation=activation,
            strictness=strictness,
            source=source,
        )
        self._record_update()

    def update_affective_tension(self, delta_valence: float, delta_arousal: float, delta_dominance: float = 0.0):
        """更新情感张力"""
        old_valence = self.affective_tension.valence
        self.affective_tension.update(delta_valence, delta_arousal, delta_dominance)

        # 记录变化幅度
        change_magnitude = abs(self.affective_tension.valence - old_valence)
        self.stability.record_change(change_magnitude)

        self._record_update()

    def update_object_stance(self, object_id: str, object_type: str, stance_delta: float, event_summary: Optional[str] = None):
        """更新对象立场"""
        if object_id not in self.object_stances:
            self.object_stances[object_id] = ObjectStance(
                object_id=object_id,
                object_type=object_type,
            )

        stance = self.object_stances[object_id]
        stance.stance = max(-1.0, min(1.0, stance.stance + stance_delta))
        stance.confidence = min(1.0, stance.confidence + 0.1)
        stance.contact_count += 1
        stance.last_contact_at = datetime.now(timezone.utc)

        if event_summary:
            stance.key_events.append(event_summary)
            if len(stance.key_events) > 10:
                stance.key_events = stance.key_events[-10:]

        self._record_update()

    def update_relation_bias(self, user_id: str, positive: bool, impact: float = 0.1):
        """更新关系偏向"""
        if user_id not in self.relation_biases:
            self.relation_biases[user_id] = RelationBias(user_id=user_id)

        self.relation_biases[user_id].update_from_event(positive, impact)
        self._record_update()

    def get_active_goals(self, threshold: float = 0.3) -> list[GoalActivation]:
        """获取当前激活的目标"""
        return [g for g in self.goals.values() if g.activation >= threshold]

    def get_active_constraints(self, threshold: float = 0.5) -> list[ConstraintActivation]:
        """获取当前激活的约束"""
        return [c for c in self.constraints.values() if c.activation >= threshold]

    def get_object_stance(self, object_id: str) -> Optional[ObjectStance]:
        """获取对象立场"""
        return self.object_stances.get(object_id)

    def get_relation_bias(self, user_id: str) -> Optional[RelationBias]:
        """获取关系偏向"""
        return self.relation_biases.get(user_id)

    def decay(self, rate: float = 0.02):
        """状态自然衰减（向中性态）"""
        self.identity.decay(rate)
        self.affective_tension.decay(rate)
        self.stability.decay(rate)

        # 目标激活衰减
        for goal in self.goals.values():
            goal.activation *= (1 - rate * 0.5)

        # 约束激活衰减
        for constraint in self.constraints.values():
            constraint.activation *= (1 - rate * 0.3)

    def _record_update(self):
        """记录更新"""
        self.last_updated_at = datetime.now(timezone.utc)
        self.update_count += 1

    def to_dict(self) -> dict[str, Any]:
        """序列化"""
        return {
            "identity": {
                "openness": round(self.identity.openness, 3),
                "conscientiousness": round(self.identity.conscientiousness, 3),
                "agreeableness": round(self.identity.agreeableness, 3),
                "emotional_stability": round(self.identity.emotional_stability, 3),
                "autonomy": round(self.identity.autonomy, 3),
                "competence": round(self.identity.competence, 3),
                "relatedness": round(self.identity.relatedness, 3),
            },
            "affective_tension": self.affective_tension.to_dict(),
            "active_goals": [
                {"id": g.goal_id, "activation": round(g.activation, 3), "progress": round(g.progress, 3)}
                for g in self.get_active_goals()
            ],
            "active_constraints": [
                {"id": c.constraint_id, "activation": round(c.activation, 3)}
                for c in self.get_active_constraints()
            ],
            "object_stances": {
                oid: {"stance": round(s.stance, 3), "confidence": round(s.confidence, 3)}
                for oid, s in self.object_stances.items()
            },
            "relation_biases": {
                uid: {"trust": round(r.trust, 3), "pattern": r.relation_pattern}
                for uid, r in self.relation_biases.items()
            },
            "stability": {
                "overall": round(self.stability.overall_stability, 3),
                "drift": round(self.stability.drift_magnitude, 3),
                "oscillating": self.stability.oscillation_detected,
            },
            "meta": {
                "update_count": self.update_count,
                "last_updated": self.last_updated_at.isoformat(),
            },
        }

    def diff(self, other: "LatentSelfState") -> dict[str, Any]:
        """计算与另一个状态的差异"""
        return {
            "affective_tension_diff": {
                "valence": round(self.affective_tension.valence - other.affective_tension.valence, 3),
                "arousal": round(self.affective_tension.arousal - other.affective_tension.arousal, 3),
            },
            "goal_activation_diff": {
                gid: round(self.goals[gid].activation - other.goals.get(gid, GoalActivation(gid, "")).activation, 3)
                for gid in set(self.goals.keys()) | set(other.goals.keys())
            },
            "relation_bias_diff": {
                uid: round(self.relation_biases[uid].trust - other.relation_biases.get(uid, RelationBias(uid)).trust, 3)
                for uid in set(self.relation_biases.keys()) | set(other.relation_biases.keys())
            },
        }


# 版本标记
STATE_V1_VERSION = "1.0.0"
