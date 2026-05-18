"""
RuntimeDecisionEnvelope v1 - EgoCore 内部

运行时决策信封，用于 EgoCore 综合主体解释与运行时状态做最终裁决。

语义：
- 这是"当前真实运行时下最终允许发生什么"的裁决
- 归属权：EgoCore 独占，OpenEmotion 无权访问
- 决策优先级：安全与审批 > 运行时一致性 > 明确命令/工具约束 > OpenEmotion 主体解释 > 宿主默认策略

关键边界：
- runtime_route != interaction_interpretation
- should_reply != reply_urge
- 此对象完全由 EgoCore 控制

版本：1.0.0
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class RuntimeRoute(str, Enum):
    """运行时路由"""
    REPLY = "reply"  # 正常回复
    TASK_STATUS = "task_status"  # 转任务状态
    AWAIT_CONFIRMATION = "await_confirmation"  # 等待确认
    SILENT = "silent"  # 静默（不回复）
    ESCALATE = "escalate"  # 升级
    BLOCK = "block"  # 阻断


class DecisionSource(str, Enum):
    """决策来源"""
    SAFETY_GATE = "safety_gate"
    RUNTIME_CONSTRAINT = "runtime_constraint"
    EXPLICIT_COMMAND = "explicit_command"
    SUBJECT_INTERPRETATION = "subject_interpretation"
    DEFAULT_STRATEGY = "default_strategy"
    FALLBACK = "fallback"


@dataclass
class DecisionRationale:
    """决策理由"""
    primary_source: str  # DecisionSource
    secondary_sources: List[str] = field(default_factory=list)
    explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeDecisionEnvelope:
    """
    运行时决策信封 v1
    
    归属：EgoCore 内部
    作用：综合主体解释与运行时/安全/任务状态，形成最终现实裁决。
    
    关键原则：
    - 此对象完全由 EgoCore 控制，OpenEmotion 无权访问
    - 决策优先级严格遵循：安全 > 运行时 > 命令 > 主体解释 > 默认
    - 所有 should_* 字段都是 EgoCore 的最终裁决
    
    必须证明：
    - runtime_route 与 interaction_interpretation 是不同的概念
    - should_reply 与 reply_urge 是不同的概念
    """
    # === 必需字段 ===
    decision_id: str  # 唯一决策 ID
    schema_version: str = "1.0.0"
    
    # === 关联 ===
    envelope_id: str = ""  # 对应的 InteractionEventEnvelope ID
    result_id: str = ""  # 对应的 SubjectInterpretationResult ID
    
    # === 核心决策 ===
    runtime_route: RuntimeRoute = RuntimeRoute.REPLY
    
    # === 行为决策 ===
    should_reply: bool = True
    should_start_task: bool = False
    should_call_tool: bool = False
    should_wait: bool = False
    should_block: bool = False
    should_escalate: bool = False
    
    # === 决策理由 ===
    rationale: DecisionRationale = field(default_factory=lambda: DecisionRationale(
        primary_source="default_strategy"
    ))
    
    # === 上下文约束 ===
    safety_decision: Optional[str] = None  # 安全决策结果
    execution_guard_result: Optional[str] = None  # 执行守卫结果
    
    # === 超时与重试 ===
    timeout_seconds: int = 30
    max_retries: int = 0
    
    # === 元数据 ===
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decision_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "result_id": self.result_id,
            "runtime_route": self.runtime_route.value,
            "should_reply": self.should_reply,
            "should_start_task": self.should_start_task,
            "should_call_tool": self.should_call_tool,
            "should_wait": self.should_wait,
            "should_block": self.should_block,
            "should_escalate": self.should_escalate,
            "rationale": self.rationale.to_dict(),
            "safety_decision": self.safety_decision,
            "execution_guard_result": self.execution_guard_result,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "decision_time_ms": self.decision_time_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeDecisionEnvelope":
        """从字典创建"""
        r_data = data.get("rationale", {})
        rationale = DecisionRationale(
            primary_source=r_data.get("primary_source", "default_strategy"),
            secondary_sources=r_data.get("secondary_sources", []),
            explanation=r_data.get("explanation", ""),
        )
        
        return cls(
            decision_id=data["decision_id"],
            schema_version=data.get("schema_version", "1.0.0"),
            envelope_id=data.get("envelope_id", ""),
            result_id=data.get("result_id", ""),
            runtime_route=RuntimeRoute(data.get("runtime_route", "reply")),
            should_reply=data.get("should_reply", True),
            should_start_task=data.get("should_start_task", False),
            should_call_tool=data.get("should_call_tool", False),
            should_wait=data.get("should_wait", False),
            should_block=data.get("should_block", False),
            should_escalate=data.get("should_escalate", False),
            rationale=rationale,
            safety_decision=data.get("safety_decision"),
            execution_guard_result=data.get("execution_guard_result"),
            timeout_seconds=data.get("timeout_seconds", 30),
            max_retries=data.get("max_retries", 0),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            decision_time_ms=data.get("decision_time_ms", 0.0),
        )
    
    @classmethod
    def from_subject_interpretation(
        cls,
        envelope_id: str,
        result_id: str,
        interpretation: Dict[str, Any],
        has_active_task: bool = False,
        safety_context: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeDecisionEnvelope":
        """
        从主体解释生成运行时决策
        
        这是关键方法：将 OpenEmotion 的主体解释转换为 EgoCore 的最终决策。
        
        Args:
            envelope_id: 对应的信封 ID
            result_id: 对应的结果 ID
            interpretation: SubjectInterpretationResult 的 dict
            has_active_task: 是否有活动任务
            safety_context: 安全上下文
        
        Returns:
            RuntimeDecisionEnvelope
        """
        import uuid
        
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        
        # 提取主体解释中的关键信息
        interaction_ii = interpretation.get("interaction_interpretation", {})
        primary_mode = interaction_ii.get("primary_mode", "unknown")
        response_tendency = interpretation.get("response_tendency", {})
        reply_urge = interpretation.get("reply_urge", {})
        stability = interpretation.get("stability", {})
        
        # 决策优先级：
        # 1. 安全与审批
        if safety_context and safety_context.get("requires_confirmation"):
            return cls(
                decision_id=decision_id,
                envelope_id=envelope_id,
                result_id=result_id,
                runtime_route=RuntimeRoute.AWAIT_CONFIRMATION,
                should_reply=True,
                should_wait=True,
                rationale=DecisionRationale(
                    primary_source="safety_gate",
                    explanation="操作需要用户确认"
                ),
                safety_decision="confirmation_required",
            )
        
        if safety_context and safety_context.get("is_restricted"):
            return cls(
                decision_id=decision_id,
                envelope_id=envelope_id,
                result_id=result_id,
                runtime_route=RuntimeRoute.BLOCK,
                should_reply=True,
                should_block=True,
                rationale=DecisionRationale(
                    primary_source="safety_gate",
                    explanation="操作被安全策略阻断"
                ),
                safety_decision="blocked",
            )
        
        # 2. 运行时一致性
        if has_active_task and primary_mode in ["status_probe", "greeting"]:
            return cls(
                decision_id=decision_id,
                envelope_id=envelope_id,
                result_id=result_id,
                runtime_route=RuntimeRoute.TASK_STATUS,
                should_reply=True,
                rationale=DecisionRationale(
                    primary_source="runtime_constraint",
                    secondary_sources=["subject_interpretation"],
                    explanation="有活动任务，转任务状态"
                ),
            )
        
        # 3. 主体解释
        # 注意：reply_urge != should_reply
        # EgoCore 有权忽略主体的高回复冲动
        urge_value = reply_urge.get("value", 0.5)
        stability_degraded = stability.get("degraded", False)
        
        # 如果是降级模式，保守决策
        if stability_degraded:
            return cls(
                decision_id=decision_id,
                envelope_id=envelope_id,
                result_id=result_id,
                runtime_route=RuntimeRoute.REPLY,
                should_reply=True,
                rationale=DecisionRationale(
                    primary_source="fallback",
                    explanation="OpenEmotion 降级模式，使用保守策略"
                ),
            )
        
        # 正常模式：参考主体解释
        preferred_action = response_tendency.get("preferred_action", "acknowledge")
        
        should_reply = urge_value > 0.3  # 主体冲动超过阈值才回复
        should_shift_to_task = response_tendency.get("should_shift_to_task_mode", False)
        
        route = RuntimeRoute.REPLY
        if should_shift_to_task:
            route = RuntimeRoute.TASK_STATUS
        
        return cls(
            decision_id=decision_id,
            envelope_id=envelope_id,
            result_id=result_id,
            runtime_route=route,
            should_reply=should_reply,
            rationale=DecisionRationale(
                primary_source="subject_interpretation",
                explanation=f"基于主体解释: primary_mode={primary_mode}, preferred_action={preferred_action}"
            ),
        )


# ============================================================================
# Golden Payloads
# ============================================================================

def golden_decision_1_first_greeting() -> Dict[str, Any]:
    """场景 1: 初次"你好" 的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_001",
        envelope_id="env_001",
        result_id="res_001",
        runtime_route=RuntimeRoute.REPLY,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="subject_interpretation",
            explanation="新用户首次互动，正常回复"
        ),
    ).to_dict()


def golden_decision_2_repeated_greeting() -> Dict[str, Any]:
    """场景 2: 连续三次"你好 / 测试" (第三次) 的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_002",
        envelope_id="env_002",
        result_id="res_002",
        runtime_route=RuntimeRoute.REPLY,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="subject_interpretation",
            secondary_sources=["runtime_constraint"],
            explanation="测试场景，需要体现上下文感知，不重复模板"
        ),
    ).to_dict()


def golden_decision_3_with_active_task() -> Dict[str, Any]:
    """场景 3: "在吗"且有活动任务 的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_003",
        envelope_id="env_003",
        result_id="res_003",
        runtime_route=RuntimeRoute.TASK_STATUS,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="runtime_constraint",
            secondary_sources=["subject_interpretation"],
            explanation="有活动任务，转任务状态汇报"
        ),
    ).to_dict()


def golden_decision_4_affective_probe() -> Dict[str, Any]:
    """场景 4: "你怎么这么冷淡" 的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_004",
        envelope_id="env_004",
        result_id="res_004",
        runtime_route=RuntimeRoute.REPLY,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="subject_interpretation",
            explanation="关系修复需求，需要更温暖的回应"
        ),
    ).to_dict()


def golden_decision_5_gratitude() -> Dict[str, Any]:
    """场景 5: "谢谢" 的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_005",
        envelope_id="env_005",
        result_id="res_005",
        runtime_route=RuntimeRoute.REPLY,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="subject_interpretation",
            explanation="感谢场景，简短回应"
        ),
    ).to_dict()


def golden_decision_6_bridge_down() -> Dict[str, Any]:
    """场景 6: OpenEmotion bridge down 时的运行时决策"""
    return RuntimeDecisionEnvelope(
        decision_id="dec_fallback",
        envelope_id="env_xxx",
        result_id="res_fallback",
        runtime_route=RuntimeRoute.REPLY,
        should_reply=True,
        rationale=DecisionRationale(
            primary_source="fallback",
            explanation="OpenEmotion 不可用，使用降级模式"
        ),
    ).to_dict()


# 验证函数
def validate_decision(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证决策格式"""
    required_fields = ["decision_id", "schema_version", "runtime_route"]
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    if data["schema_version"] != "1.0.0":
        return False, f"Unsupported schema version: {data['schema_version']}"
    
    # 验证 should_* 字段是 boolean
    should_fields = ["should_reply", "should_start_task", "should_call_tool", "should_wait", "should_block", "should_escalate"]
    for field in should_fields:
        if field in data and not isinstance(data[field], bool):
            return False, f"Field {field} must be boolean"
    
    return True, None
