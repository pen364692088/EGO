"""
OutwardResponsePackage v1 - EgoCore → verbalizer

对外回复包，用于约束 LLM 只能 verbalize，不能擅自升级。

语义：
- 这是"最终允许对外输出的内容约束"
- 归属权：EgoCore 构建，verbalizer 执行
- LLM 只能在 contract 范围内组织语言，不能自行决定升级 certainty/commitment/emotion

关键边界：
- outward_response_contract != expressive_intent_candidate
- 此对象完全由 EgoCore 控制，OpenEmotion 无权访问

版本：1.0.0
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class ResponsePlan(str, Enum):
    """回复计划"""
    SIMPLE_ACKNOWLEDGE = "simple_acknowledge"  # 简单确认
    WARM_GREETING = "warm_greeting"  # 温暖问候
    CONTEXT_AWARE = "context_aware"  # 上下文感知
    TASK_STATUS = "task_status"  # 任务状态
    RELATIONSHIP_REPAIR = "relationship_repair"  # 关系修复
    GRATEFUL_RESPONSE = "grateful_response"  # 感谢回应
    NEUTRAL_FALLBACK = "neutral_fallback"  # 中性降级


class SpeakerMode(str, Enum):
    """说话模式"""
    WARM = "warm"
    NEUTRAL = "neutral"
    GUARDED = "guarded"
    COLD = "cold"


class EpistemicStatus(str, Enum):
    """认知状态"""
    CERTAIN = "certain"
    LIKELY = "likely"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class CommitmentLevel(str, Enum):
    """承诺级别"""
    FULL = "full"  # 完全承诺
    TENTATIVE = "tentative"  # 尝试性
    CONDITIONAL = "conditional"  # 条件性
    NONE = "none"  # 无承诺


@dataclass
class ToneBounds:
    """语气边界"""
    min_warmth: float = 0.0  # [0, 1]
    max_warmth: float = 1.0  # [0, 1]
    min_directness: float = 0.0  # [0, 1]
    max_directness: float = 1.0  # [0, 1]
    avoid_tones: List[str] = field(default_factory=list)  # 禁止的语气
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutwardResponsePackage:
    """
    对外回复包 v1
    
    方向：EgoCore → verbalizer/sender
    作用：输出最终 response contract，约束 LLM 只能 verbalize，不能擅自升级。
    
    关键原则：
    - LLM 只能在此 contract 范围内组织语言
    - 不能擅自升级 certainty/commitment/emotion/tool/action
    - 所有约束必须明确，不留模糊空间
    
    边界约束：
    - 此对象完全由 EgoCore 控制
    - expressive_intent_candidate 只是"建议"，outward_response_contract 是"约束"
    """
    # === 必需字段 ===
    package_id: str  # 唯一包 ID
    schema_version: str = "1.0.0"
    
    # === 关联 ===
    decision_id: str = ""  # 对应的 RuntimeDecisionEnvelope ID
    
    # === 回复计划 ===
    response_plan: ResponsePlan = ResponsePlan.SIMPLE_ACKNOWLEDGE
    
    # === 说话模式 ===
    speaker_mode: SpeakerMode = SpeakerMode.NEUTRAL
    
    # === 认知状态 ===
    epistemic_status: EpistemicStatus = EpistemicStatus.CERTAIN
    commitment_level: CommitmentLevel = CommitmentLevel.NONE
    
    # === 核心内容 ===
    core_points: List[str] = field(default_factory=list)  # 必须包含的核心点
    
    # === 约束 ===
    must_include: List[str] = field(default_factory=list)  # 必须包含的短语
    must_not_upgrade: List[str] = field(default_factory=list)  # 禁止升级的内容
    tone_bounds: ToneBounds = field(default_factory=ToneBounds)
    
    # === 任务相关 ===
    task_context: Optional[Dict[str, Any]] = None  # 任务上下文（如有）

    # === Response Tendency 扩展 ===
    response_length_hint: Optional[str] = None  # "short" | "detailed" | None
    style_hints: List[str] = field(default_factory=list)  # 风格提示，如 ["gentle", "direct"]

    # === 元数据 ===
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "response_plan": self.response_plan.value,
            "speaker_mode": self.speaker_mode.value,
            "epistemic_status": self.epistemic_status.value,
            "commitment_level": self.commitment_level.value,
            "core_points": self.core_points,
            "must_include": self.must_include,
            "must_not_upgrade": self.must_not_upgrade,
            "tone_bounds": self.tone_bounds.to_dict(),
            "task_context": self.task_context,
            "response_length_hint": self.response_length_hint,
            "style_hints": self.style_hints,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutwardResponsePackage":
        """从字典创建"""
        tb_data = data.get("tone_bounds", {})
        tone_bounds = ToneBounds(
            min_warmth=tb_data.get("min_warmth", 0.0),
            max_warmth=tb_data.get("max_warmth", 1.0),
            min_directness=tb_data.get("min_directness", 0.0),
            max_directness=tb_data.get("max_directness", 1.0),
            avoid_tones=tb_data.get("avoid_tones", []),
        )
        
        return cls(
            package_id=data["package_id"],
            schema_version=data.get("schema_version", "1.0.0"),
            decision_id=data.get("decision_id", ""),
            response_plan=ResponsePlan(data.get("response_plan", "simple_acknowledge")),
            speaker_mode=SpeakerMode(data.get("speaker_mode", "neutral")),
            epistemic_status=EpistemicStatus(data.get("epistemic_status", "certain")),
            commitment_level=CommitmentLevel(data.get("commitment_level", "none")),
            core_points=data.get("core_points", []),
            must_include=data.get("must_include", []),
            must_not_upgrade=data.get("must_not_upgrade", []),
            tone_bounds=tone_bounds,
            task_context=data.get("task_context"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )
    
    @classmethod
    def from_decision(
        cls,
        decision: Dict[str, Any],
        interpretation: Optional[Dict[str, Any]] = None,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> "OutwardResponsePackage":
        """
        从运行时决策生成对外回复包
        
        这是关键方法：将 EgoCore 的决策转换为最终的回复约束。
        
        Args:
            decision: RuntimeDecisionEnvelope 的 dict
            interpretation: SubjectInterpretationResult 的 dict（可选）
            task_context: 任务上下文
        
        Returns:
            OutwardResponsePackage
        """
        import uuid
        
        package_id = f"pkg_{uuid.uuid4().hex[:8]}"
        decision_id = decision.get("decision_id", "")
        runtime_route = decision.get("runtime_route", "reply")
        
        # 默认值
        response_plan = ResponsePlan.SIMPLE_ACKNOWLEDGE
        speaker_mode = SpeakerMode.NEUTRAL
        core_points = []
        must_include = []
        must_not_upgrade = ["certainty", "commitment", "emotion", "tool", "action"]
        tone_bounds = ToneBounds()
        
        # 如果有主体解释，提取关键信息
        if interpretation:
            eic = interpretation.get("expressive_intent_candidate", {})
            rt = interpretation.get("response_tendency", {})
            ii = interpretation.get("interaction_interpretation", {})
            primary_mode = ii.get("primary_mode", "unknown")
            
            # 说话模式
            stance = eic.get("speaker_stance", "neutral")
            if stance == "warm":
                speaker_mode = SpeakerMode.WARM
            elif stance == "guarded":
                speaker_mode = SpeakerMode.GUARDED
            elif stance == "cold":
                speaker_mode = SpeakerMode.COLD
            
            # 必须包含
            must_include = eic.get("must_include_candidates", [])
            
            # 必须避免
            avoid = eic.get("must_avoid_candidates", [])
            tone_bounds.avoid_tones = avoid
            
            # 温度约束
            warmth = eic.get("warmth_preference", 0.5)
            directness = eic.get("directness_preference", 0.5)
            tone_bounds.min_warmth = max(0, warmth - 0.2)
            tone_bounds.max_warmth = min(1, warmth + 0.2)
            tone_bounds.min_directness = max(0, directness - 0.2)
            tone_bounds.max_directness = min(1, directness + 0.2)
            
            # 回应倾向
            if rt.get("should_acknowledge_context"):
                core_points.append("acknowledge_context")
            if rt.get("should_acknowledge_affect"):
                core_points.append("acknowledge_affect")
            if rt.get("should_shift_to_task_mode"):
                core_points.append("shift_to_task")
        
        # 根据运行时路由确定回复计划
        if runtime_route == "task_status":
            response_plan = ResponsePlan.TASK_STATUS
            if task_context:
                core_points.append(f"task_status:{task_context.get('status', 'unknown')}")
        
        # 根据主体解释模式调整
        if interpretation:
            ii = interpretation.get("interaction_interpretation", {})
            primary_mode = ii.get("primary_mode", "unknown")
            ri = interpretation.get("relationship_implication", {})
            
            if primary_mode == "greeting" and not interpretation.get("stability", {}).get("degraded"):
                response_plan = ResponsePlan.WARM_GREETING
            elif primary_mode == "testing":
                response_plan = ResponsePlan.CONTEXT_AWARE
                must_include.append("acknowledge_testing")
            elif primary_mode == "affective_probe":
                response_plan = ResponsePlan.RELATIONSHIP_REPAIR
                if ri.get("repair_needed"):
                    must_include.append("repair_relationship")
                # DEBUG
                import logging
                logging.getLogger(__name__).info(f"DEBUG: affective_probe detected, response_plan={response_plan.value}")
            elif primary_mode == "gratitude":
                response_plan = ResponsePlan.GRATEFUL_RESPONSE
            elif interpretation.get("stability", {}).get("degraded"):
                response_plan = ResponsePlan.NEUTRAL_FALLBACK
        
        return cls(
            package_id=package_id,
            decision_id=decision_id,
            response_plan=response_plan,
            speaker_mode=speaker_mode,
            core_points=core_points,
            must_include=must_include,
            must_not_upgrade=must_not_upgrade,
            tone_bounds=tone_bounds,
            task_context=task_context,
        )
    
    def to_verbalizer_prompt(self) -> str:
        """
        转换为 verbalizer 可用的 prompt
        
        Returns:
            格式化的 prompt 字符串
        """
        parts = [
            f"# 回复约束",
            f"",
            f"## 回复计划",
            f"{self.response_plan.value}",
            f"",
            f"## 说话模式",
            f"- 语气: {self.speaker_mode.value}",
            f"- 温度范围: [{self.tone_bounds.min_warmth:.1f}, {self.tone_bounds.max_warmth:.1f}]",
            f"- 直接度范围: [{self.tone_bounds.min_directness:.1f}, {self.tone_bounds.max_directness:.1f}]",
            f"",
            f"## 核心要点",
        ]
        
        for point in self.core_points:
            parts.append(f"- {point}")
        
        if self.must_include:
            parts.append(f"")
            parts.append(f"## 必须包含")
            for item in self.must_include:
                parts.append(f"- {item}")
        
        parts.append(f"")
        parts.append(f"## 禁止升级")
        parts.append(f"以下内容不得自行升级：{', '.join(self.must_not_upgrade)}")
        
        if self.tone_bounds.avoid_tones:
            parts.append(f"")
            parts.append(f"## 禁止语气")
            for avoid in self.tone_bounds.avoid_tones:
                parts.append(f"- {avoid}")
        
        return "\n".join(parts)


# ============================================================================
# Golden Payloads
# ============================================================================

def golden_package_1_first_greeting() -> Dict[str, Any]:
    """场景 1: 初次"你好" 的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_001",
        decision_id="dec_001",
        response_plan=ResponsePlan.WARM_GREETING,
        speaker_mode=SpeakerMode.WARM,
        core_points=["greeting", "introduce_self"],
        must_include=[],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.5,
            max_warmth=0.9,
            min_directness=0.3,
            max_directness=0.7,
        ),
    ).to_dict()


def golden_package_2_repeated_greeting() -> Dict[str, Any]:
    """场景 2: 连续三次"你好 / 测试" (第三次) 的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_002",
        decision_id="dec_002",
        response_plan=ResponsePlan.CONTEXT_AWARE,
        speaker_mode=SpeakerMode.NEUTRAL,
        core_points=["acknowledge_context", "acknowledge_testing"],
        must_include=["这轮我知道你是在继续测试", "不用再给你重复那套欢迎词"],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.3,
            max_warmth=0.6,
            min_directness=0.5,
            max_directness=0.8,
            avoid_tones=["欢迎词模板", "我是 EgoCore 任务助手"],
        ),
    ).to_dict()


def golden_package_3_with_active_task() -> Dict[str, Any]:
    """场景 3: "在吗"且有活动任务 的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_003",
        decision_id="dec_003",
        response_plan=ResponsePlan.TASK_STATUS,
        speaker_mode=SpeakerMode.WARM,
        core_points=["acknowledge_context", "shift_to_task", "task_status:running"],
        must_include=["当前有活动任务"],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.4,
            max_warmth=0.7,
            min_directness=0.4,
            max_directness=0.7,
        ),
        task_context={
            "task_id": "task_abc123",
            "objective": "分析项目结构",
            "status": "running",
            "progress": {"completed": 2, "total": 5}
        },
    ).to_dict()


def golden_package_4_affective_probe() -> Dict[str, Any]:
    """场景 4: "你怎么这么冷淡" 的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_004",
        decision_id="dec_004",
        response_plan=ResponsePlan.RELATIONSHIP_REPAIR,
        speaker_mode=SpeakerMode.WARM,
        core_points=["acknowledge_affect", "repair_relationship"],
        must_include=["抱歉让你有这种感觉", "我在认真听你说话"],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.6,
            max_warmth=0.9,
            min_directness=0.2,
            max_directness=0.5,
            avoid_tones=["冷漠回复", "机械模板"],
        ),
    ).to_dict()


def golden_package_5_gratitude() -> Dict[str, Any]:
    """场景 5: "谢谢" 的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_005",
        decision_id="dec_005",
        response_plan=ResponsePlan.GRATEFUL_RESPONSE,
        speaker_mode=SpeakerMode.WARM,
        core_points=["acknowledge_gratitude"],
        must_include=[],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.5,
            max_warmth=0.8,
            min_directness=0.3,
            max_directness=0.6,
            avoid_tones=["啰嗦", "过度解释"],
        ),
    ).to_dict()


def golden_package_6_bridge_down() -> Dict[str, Any]:
    """场景 6: OpenEmotion bridge down 时的回复包"""
    return OutwardResponsePackage(
        package_id="pkg_fallback",
        decision_id="dec_fallback",
        response_plan=ResponsePlan.NEUTRAL_FALLBACK,
        speaker_mode=SpeakerMode.NEUTRAL,
        core_points=["acknowledge"],
        must_include=[],
        must_not_upgrade=["certainty", "commitment", "emotion", "tool", "action"],
        tone_bounds=ToneBounds(
            min_warmth=0.3,
            max_warmth=0.6,
            min_directness=0.4,
            max_directness=0.7,
        ),
    ).to_dict()


# 验证函数
def validate_package(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证包格式"""
    required_fields = ["package_id", "schema_version", "response_plan"]
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if data["schema_version"] != "1.0.0":
        return False, f"Unsupported schema version: {data['schema_version']}"
    
    # 验证 must_not_upgrade 存在且不为空
    if not data.get("must_not_upgrade"):
        return False, "must_not_upgrade must not be empty"
    
    return True, None
