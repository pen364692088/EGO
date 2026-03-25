"""
Proto-Self Kernel v1 Schemas

输入输出契约定义。严格遵循边界文档：
- EgoCore → OpenEmotion 是结构化事件
- OpenEmotion → EgoCore 是结构化结果
- 禁止靠 prompt 文本临时约定字段
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


SCHEMA_VERSION = "proto_self.v1"


# ============================================================================
# Input: EgoCore → OpenEmotion
# ============================================================================

@dataclass
class KernelEvent:
    """
    EgoCore 传递给 Proto-Self Kernel 的结构化事件。
    
    每个事件必须是完整、可序列化、可回放的结构。
    """
    schema_version: str = SCHEMA_VERSION
    event_id: str = ""
    timestamp: str = ""
    actor: str = ""
    source: str = ""  # telegram / cli / api / system
    event_type: str = ""  # user_message / system_event / tool_result / etc.

    # 用户意图（可选）
    user_intent: Optional[str] = None
    raw_text: Optional[str] = None

    # 上下文
    conversation_context: Dict[str, Any] = field(default_factory=dict)
    task_context: Dict[str, Any] = field(default_factory=dict)
    runtime_summary: Dict[str, Any] = field(default_factory=dict)
    safety_context: Dict[str, Any] = field(default_factory=dict)

    # 后果回流（一等输入）
    external_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，用于 trace 写入。"""
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "source": self.source,
            "event_type": self.event_type,
            "user_intent": self.user_intent,
            "raw_text": self.raw_text,
            "conversation_context": self.conversation_context,
            "task_context": self.task_context,
            "runtime_summary": self.runtime_summary,
            "safety_context": self.safety_context,
            "external_result": self.external_result,
        }


# ============================================================================
# Output: OpenEmotion → EgoCore
# ============================================================================

@dataclass
class ReflectionNote:
    """
    反思笔记：失败或冲突后生成的结构化修正建议。
    
    注意：
    - 只产出建议，不产出现实动作
    - 不允许成为第二个大脑
    - 必须通过 EgoCore 才能生效
    """
    trigger: str  # external_failure / identity_conflict / drive_spike / cycle_failure
    diagnosis: str
    proposed_adjustment: Dict[str, Any] = field(default_factory=dict)
    promote_to_memory: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger": self.trigger,
            "diagnosis": self.diagnosis,
            "proposed_adjustment": self.proposed_adjustment,
            "promote_to_memory": self.promote_to_memory,
        }


@dataclass
class ResponseTendency:
    """
    响应倾向：影响下一步行为的内部偏置。
    
    注意：
    - 只表达建议与倾向
    - 不能包含直接工具执行命令
    - 不能直接替 EgoCore 做现实裁决
    """
    preferred_mode: str  # respond / ask / defer / repair
    preferred_tone: str  # calm / cautious / direct / supportive
    certainty_bound: str  # bounded / high / low
    suggested_next_step: str
    ask_needed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preferred_mode": self.preferred_mode,
            "preferred_tone": self.preferred_tone,
            "certainty_bound": self.certainty_bound,
            "suggested_next_step": self.suggested_next_step,
            "ask_needed": self.ask_needed,
        }


@dataclass
class KernelOutput:
    """
    Proto-Self Kernel 输出：结构化结果，程序消费依赖结构字段。
    
    约束：
    - policy_hint / response_tendency 只表达建议与倾向
    - 不能包含直接工具执行命令
    - 不能直接替 EgoCore 做现实裁决
    - 自由文本只能放在 diagnosis 或 explanation 字段
    """
    schema_version: str = SCHEMA_VERSION
    event_id: str = ""

    # 状态增量
    identity_state_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    memory_update: Dict[str, Any] = field(default_factory=dict)
    relationship_update: Dict[str, Any] = field(default_factory=dict)
    appraisal_state_delta: Dict[str, Any] = field(default_factory=dict)

    # 反思与倾向
    reflection_note: Optional[ReflectionNote] = None
    policy_hint: Dict[str, Any] = field(default_factory=dict)
    response_tendency: Optional[ResponseTendency] = None
    confidence_meta: Dict[str, Any] = field(default_factory=dict)

    # Trace payload（一等输出）
    trace_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "identity_state_delta": self.identity_state_delta,
            "self_model_delta": self.self_model_delta,
            "memory_update": self.memory_update,
            "relationship_update": self.relationship_update,
            "appraisal_state_delta": self.appraisal_state_delta,
            "reflection_note": self.reflection_note.to_dict() if self.reflection_note else None,
            "policy_hint": self.policy_hint,
            "response_tendency": self.response_tendency.to_dict() if self.response_tendency else None,
            "confidence_meta": self.confidence_meta,
            "trace_payload": self.trace_payload,
        }
