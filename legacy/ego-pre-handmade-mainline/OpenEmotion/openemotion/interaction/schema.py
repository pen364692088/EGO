"""
SubjectInterpretationResult v1 - OpenEmotion → EgoCore

主体解释结果，用于 OpenEmotion 向 EgoCore 返回互动解释。

语义：
- 这是"主体认为这次互动意味着什么"的解释
- 不包含任何最终决策（should_reply 等）
- 归属权：OpenEmotion 构建，EgoCore 消费

关键边界：
- interaction_interpretation != runtime_route
- expressive_intent_candidate != outward_response_contract
- reply_urge != should_reply

版本：1.0.0
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class PrimaryMode(str, Enum):
    """主要互动模式"""
    GREETING = "greeting"
    TESTING = "testing"
    STATUS_PROBE = "status_probe"
    TASK_REQUEST = "task_request"
    AFFECTIVE_PROBE = "affective_probe"
    GRATITUDE = "gratitude"
    FRUSTRATION = "frustration"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"


class SocialSignal(str, Enum):
    """社交信号类型"""
    GREETING = "greeting"
    STATUS_PROBE = "status_probe"
    TASK_REQUEST = "task_request"
    AFFECTIVE_PROBE = "affective_probe"
    GRATITUDE = "gratitude"
    FRUSTRATION_FEEDBACK = "frustration_feedback"
    TESTING_BEHAVIOR = "testing_behavior"


# ============================================================================
# 子结构定义
# ============================================================================

@dataclass
class InteractionInterpretation:
    """
    互动解释
    
    这是 OpenEmotion 的核心输出，描述"主体认为这次互动是什么"
    """
    primary_mode: str  # PrimaryMode
    secondary_modes: List[str] = field(default_factory=list)
    user_goal_rewrite: Optional[str] = None  # 主体认为用户的真实意图
    ambiguity_level: float = 0.0  # [0, 1]
    confidence: float = 0.5  # [0, 1]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RelationshipImplication:
    """
    关系影响
    
    描述这次互动对关系的影响
    """
    interaction_effect: str = "neutral"  # positive, neutral, negative
    trust_delta: float = 0.0  # [-1, 1]
    tension_delta: float = 0.0  # [-1, 1]
    repair_needed: bool = False
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResponseTendency:
    """
    回应倾向
    
    这是"主体倾向于如何回应"，不是最终决策
    """
    preferred_action: str = "acknowledge"  # acknowledge, explain, invite_task, wait
    should_acknowledge_context: bool = False
    should_acknowledge_affect: bool = False
    should_invite_next_step: bool = False
    should_explain_self: bool = False
    should_shift_to_task_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExpressiveIntentCandidate:
    """
    表达意图候选
    
    这是"主体想要如何表达自己"，最终表达由 EgoCore 的 verbalizer 决定
    """
    speaker_stance: str = "neutral"  # warm, neutral, guarded, cold
    warmth_preference: float = 0.5  # [0, 1]
    directness_preference: float = 0.5  # [0, 1]
    preferred_opening: Optional[str] = None  # 建议的开场白
    must_include_candidates: List[str] = field(default_factory=list)
    must_avoid_candidates: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplyUrge:
    """
    回复冲动
    
    这是"主体想要回复的程度"，不是最终 should_reply 决策
    """
    value: float = 0.5  # [0, 1]
    reason: str = "default"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StabilityInfo:
    """
    稳定性信息
    
    描述解释的稳定性
    """
    model_confidence: float = 0.5  # [0, 1]
    ood_flag: bool = False  # Out-of-distribution 标记
    degraded: bool = False  # 是否使用了降级模式
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# 主结构
# ============================================================================

@dataclass
class SubjectInterpretationResult:
    """
    主体解释结果 v1
    
    方向：OpenEmotion → EgoCore
    作用：返回主体解释、关系语义、appraisal 变化、回应倾向。
    
    关键原则：
    - 只描述主体层面的解释，不决定最终行为
    - 所有字段都是 OpenEmotion 的权威
    - EgoCore 必须基于这些解释做最终裁决
    
    边界约束：
    - 此对象不包含 should_reply / should_start_task / should_call_tool
    - 此对象不包含 runtime_route
    - 此对象不包含 safety_decision
    """
    # === 必需字段 ===
    result_id: str  # 唯一结果 ID
    schema_version: str = "1.0.0"
    envelope_id: str = ""  # 对应的 InteractionEventEnvelope ID
    
    # === 核心解释 ===
    interaction_interpretation: InteractionInterpretation = field(default_factory=InteractionInterpretation)
    social_signals: List[str] = field(default_factory=list)  # SocialSignal 列表
    relationship_implication: RelationshipImplication = field(default_factory=RelationshipImplication)
    
    # === 状态变化 ===
    appraisal_state_delta: Dict[str, float] = field(default_factory=dict)  # appraisal 变化
    
    # === 回应倾向 ===
    response_tendency: ResponseTendency = field(default_factory=ResponseTendency)
    expressive_intent_candidate: ExpressiveIntentCandidate = field(default_factory=ExpressiveIntentCandidate)
    reply_urge: ReplyUrge = field(default_factory=ReplyUrge)
    
    # === 反思与策略提示 ===
    reflection_note: Optional[str] = None  # 主体层面的反思
    policy_hint: Optional[str] = None  # 给 EgoCore 的策略提示
    
    # === 稳定性 ===
    stability: StabilityInfo = field(default_factory=StabilityInfo)
    
    # === 元数据 ===
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "interaction_interpretation": self.interaction_interpretation.to_dict(),
            "social_signals": self.social_signals,
            "relationship_implication": self.relationship_implication.to_dict(),
            "appraisal_state_delta": self.appraisal_state_delta,
            "response_tendency": self.response_tendency.to_dict(),
            "expressive_intent_candidate": self.expressive_intent_candidate.to_dict(),
            "reply_urge": self.reply_urge.to_dict(),
            "reflection_note": self.reflection_note,
            "policy_hint": self.policy_hint,
            "stability": self.stability.to_dict(),
            "created_at": self.created_at,
            "processing_time_ms": self.processing_time_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubjectInterpretationResult":
        """从字典创建"""
        ii_data = data.get("interaction_interpretation", {})
        interaction_interpretation = InteractionInterpretation(
            primary_mode=ii_data.get("primary_mode", "unknown"),
            secondary_modes=ii_data.get("secondary_modes", []),
            user_goal_rewrite=ii_data.get("user_goal_rewrite"),
            ambiguity_level=ii_data.get("ambiguity_level", 0.0),
            confidence=ii_data.get("confidence", 0.5),
        )
        
        ri_data = data.get("relationship_implication", {})
        relationship_implication = RelationshipImplication(
            interaction_effect=ri_data.get("interaction_effect", "neutral"),
            trust_delta=ri_data.get("trust_delta", 0.0),
            tension_delta=ri_data.get("tension_delta", 0.0),
            repair_needed=ri_data.get("repair_needed", False),
            notes=ri_data.get("notes"),
        )
        
        rt_data = data.get("response_tendency", {})
        response_tendency = ResponseTendency(
            preferred_action=rt_data.get("preferred_action", "acknowledge"),
            should_acknowledge_context=rt_data.get("should_acknowledge_context", False),
            should_acknowledge_affect=rt_data.get("should_acknowledge_affect", False),
            should_invite_next_step=rt_data.get("should_invite_next_step", False),
            should_explain_self=rt_data.get("should_explain_self", False),
            should_shift_to_task_mode=rt_data.get("should_shift_to_task_mode", False),
        )
        
        eic_data = data.get("expressive_intent_candidate", {})
        expressive_intent_candidate = ExpressiveIntentCandidate(
            speaker_stance=eic_data.get("speaker_stance", "neutral"),
            warmth_preference=eic_data.get("warmth_preference", 0.5),
            directness_preference=eic_data.get("directness_preference", 0.5),
            preferred_opening=eic_data.get("preferred_opening"),
            must_include_candidates=eic_data.get("must_include_candidates", []),
            must_avoid_candidates=eic_data.get("must_avoid_candidates", []),
        )
        
        ru_data = data.get("reply_urge", {})
        reply_urge = ReplyUrge(
            value=ru_data.get("value", 0.5),
            reason=ru_data.get("reason", "default"),
        )
        
        s_data = data.get("stability", {})
        stability = StabilityInfo(
            model_confidence=s_data.get("model_confidence", 0.5),
            ood_flag=s_data.get("ood_flag", False),
            degraded=s_data.get("degraded", False),
        )
        
        return cls(
            result_id=data["result_id"],
            schema_version=data.get("schema_version", "1.0.0"),
            envelope_id=data.get("envelope_id", ""),
            interaction_interpretation=interaction_interpretation,
            social_signals=data.get("social_signals", []),
            relationship_implication=relationship_implication,
            appraisal_state_delta=data.get("appraisal_state_delta", {}),
            response_tendency=response_tendency,
            expressive_intent_candidate=expressive_intent_candidate,
            reply_urge=reply_urge,
            reflection_note=data.get("reflection_note"),
            policy_hint=data.get("policy_hint"),
            stability=stability,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            processing_time_ms=data.get("processing_time_ms", 0.0),
        )


# ============================================================================
# Golden Payloads
# ============================================================================

def golden_result_1_first_greeting() -> Dict[str, Any]:
    """场景 1: 初次"你好" 的主体解释"""
    return SubjectInterpretationResult(
        result_id="res_001",
        envelope_id="env_001",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="greeting",
            secondary_modes=[],
            user_goal_rewrite="发起对话，建立联系",
            ambiguity_level=0.1,
            confidence=0.9,
        ),
        social_signals=["greeting"],
        relationship_implication=RelationshipImplication(
            interaction_effect="positive",
            trust_delta=0.1,
            tension_delta=0.0,
            repair_needed=False,
            notes="首次互动，建立关系",
        ),
        response_tendency=ResponseTendency(
            preferred_action="acknowledge",
            should_acknowledge_context=False,
            should_acknowledge_affect=False,
            should_invite_next_step=True,
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="warm",
            warmth_preference=0.7,
            directness_preference=0.5,
            preferred_opening="你好",
            must_include_candidates=[],
            must_avoid_candidates=["重复欢迎词"],
        ),
        reply_urge=ReplyUrge(value=0.8, reason="新用户首次互动"),
        stability=StabilityInfo(model_confidence=0.9, ood_flag=False, degraded=False),
    ).to_dict()


def golden_result_2_repeated_greeting() -> Dict[str, Any]:
    """场景 2: 连续三次"你好 / 测试" (第三次) 的主体解释"""
    return SubjectInterpretationResult(
        result_id="res_002",
        envelope_id="env_002",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="testing",
            secondary_modes=["greeting"],
            user_goal_rewrite="测试系统反应，验证上下文记忆",
            ambiguity_level=0.3,
            confidence=0.85,
        ),
        social_signals=["testing_behavior", "greeting"],
        relationship_implication=RelationshipImplication(
            interaction_effect="neutral",
            trust_delta=0.0,
            tension_delta=0.0,
            repair_needed=False,
            notes="用户在测试系统，需要体现上下文感知",
        ),
        response_tendency=ResponseTendency(
            preferred_action="acknowledge",
            should_acknowledge_context=True,  # 关键：需要体现上下文感知
            should_acknowledge_affect=False,
            should_invite_next_step=True,
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="neutral",
            warmth_preference=0.5,
            directness_preference=0.7,  # 更直接
            preferred_opening="我在，收到了",
            must_include_candidates=["这轮我知道你是在继续测试", "不用再给你重复那套欢迎词"],
            must_avoid_candidates=["欢迎词模板", "我是 EgoCore 任务助手"],
        ),
        reply_urge=ReplyUrge(value=0.6, reason="测试场景，适度回应"),
        reflection_note="用户已连续发送多次问候/测试，不应重复 onboarding 模板",
        stability=StabilityInfo(model_confidence=0.85, ood_flag=False, degraded=False),
    ).to_dict()


def golden_result_3_with_active_task() -> Dict[str, Any]:
    """场景 3: "在吗"且有活动任务 的主体解释"""
    return SubjectInterpretationResult(
        result_id="res_003",
        envelope_id="env_003",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="status_probe",
            secondary_modes=[],
            user_goal_rewrite="确认系统状态，可能想继续任务或了解进度",
            ambiguity_level=0.4,
            confidence=0.8,
        ),
        social_signals=["status_probe"],
        relationship_implication=RelationshipImplication(
            interaction_effect="neutral",
            trust_delta=0.0,
            tension_delta=0.0,
            repair_needed=False,
        ),
        response_tendency=ResponseTendency(
            preferred_action="explain",
            should_acknowledge_context=True,
            should_shift_to_task_mode=True,  # 关键：引导到任务状态
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="warm",
            warmth_preference=0.6,
            directness_preference=0.6,
            preferred_opening="我在",
            must_include_candidates=["当前有活动任务"],
            must_avoid_candidates=[],
        ),
        reply_urge=ReplyUrge(value=0.9, reason="用户有活动任务，高优先响应"),
        policy_hint="考虑主动汇报任务状态",
        stability=StabilityInfo(model_confidence=0.8, ood_flag=False, degraded=False),
    ).to_dict()


def golden_result_4_affective_probe() -> Dict[str, Any]:
    """场景 4: "你怎么这么冷淡" 的主体解释"""
    return SubjectInterpretationResult(
        result_id="res_004",
        envelope_id="env_004",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="affective_probe",
            secondary_modes=["frustration"],
            user_goal_rewrite="表达不满，期待更温暖的回应",
            ambiguity_level=0.3,
            confidence=0.85,
        ),
        social_signals=["affective_probe", "frustration_feedback"],
        relationship_implication=RelationshipImplication(
            interaction_effect="negative",
            trust_delta=-0.1,
            tension_delta=0.2,
            repair_needed=True,  # 关键：需要修复关系
            notes="用户感到被冷落，需要更温暖的回应",
        ),
        appraisal_state_delta={"social_safety": -0.1, "valence": -0.2},
        response_tendency=ResponseTendency(
            preferred_action="acknowledge",
            should_acknowledge_context=True,
            should_acknowledge_affect=True,  # 关键：需要承认用户的感受
            should_explain_self=True,
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="warm",
            warmth_preference=0.8,  # 提高温度
            directness_preference=0.4,
            preferred_opening="抱歉让你有这种感觉",
            must_include_candidates=["我在认真听你说话"],
            must_avoid_candidates=["冷漠回复", "机械模板"],
        ),
        reply_urge=ReplyUrge(value=0.9, reason="关系修复需求，高优先响应"),
        reflection_note="用户感到被冷落，需要更温暖、更人性化的回应",
        stability=StabilityInfo(model_confidence=0.85, ood_flag=False, degraded=False),
    ).to_dict()


def golden_result_5_gratitude() -> Dict[str, Any]:
    """场景 5: "谢谢" 的主体解释"""
    return SubjectInterpretationResult(
        result_id="res_005",
        envelope_id="env_005",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="gratitude",
            secondary_modes=[],
            user_goal_rewrite="表达感谢，结束当前互动或开启新话题",
            ambiguity_level=0.2,
            confidence=0.9,
        ),
        social_signals=["gratitude"],
        relationship_implication=RelationshipImplication(
            interaction_effect="positive",
            trust_delta=0.1,
            tension_delta=-0.1,
            repair_needed=False,
            notes="正面互动，关系增强",
        ),
        response_tendency=ResponseTendency(
            preferred_action="acknowledge",
            should_acknowledge_affect=True,
            should_invite_next_step=False,  # 不急于引导下一步
        ),
        expressive_intent_candidate=ExpressiveIntentCandidate(
            speaker_stance="warm",
            warmth_preference=0.7,
            directness_preference=0.5,
            preferred_opening="不客气",
            must_include_candidates=[],
            must_avoid_candidates=["啰嗦", "过度解释"],
        ),
        reply_urge=ReplyUrge(value=0.5, reason="感谢场景，简短回应即可"),
        stability=StabilityInfo(model_confidence=0.9, ood_flag=False, degraded=False),
    ).to_dict()


def golden_result_6_bridge_down() -> Dict[str, Any]:
    """场景 6: OpenEmotion bridge down 时的降级结果"""
    return SubjectInterpretationResult(
        result_id="res_fallback",
        envelope_id="env_xxx",
        interaction_interpretation=InteractionInterpretation(
            primary_mode="unknown",
            secondary_modes=[],
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
        reply_urge=ReplyUrge(value=0.5, reason="fallback"),
        reflection_note="OpenEmotion 暂时不可用，使用降级模式",
        stability=StabilityInfo(model_confidence=0.3, ood_flag=True, degraded=True),
    ).to_dict()


# 验证函数
def validate_result(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证结果格式"""
    required_fields = ["result_id", "schema_version", "interaction_interpretation"]
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if data["schema_version"] != "1.0.0":
        return False, f"Unsupported schema version: {data['schema_version']}"
    
    # 验证不包含禁止字段
    forbidden_fields = ["should_reply", "should_start_task", "should_call_tool", "runtime_route", "safety_decision"]
    for field in forbidden_fields:
        if field in data:
            return False, f"Forbidden field in SubjectInterpretationResult: {field}"
    
    return True, None
