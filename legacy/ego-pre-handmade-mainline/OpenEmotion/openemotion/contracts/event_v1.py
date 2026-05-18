"""
OpenEmotion Event v1 - 正式输入事件类型

对应 schema: schemas/openemotion_event_v1.schema.json
用途: EgoCore → OpenEmotion 的标准输入格式

版本: v1.0.0
冻结状态: FROZEN (不允许破坏性修改)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventSource(str, Enum):
    """事件来源"""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    CLI = "cli"
    API = "api"
    INTERNAL = "internal"
    SCHEDULED = "scheduled"


class EventType(str, Enum):
    """事件类型"""
    USER_MESSAGE = "user_message"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    WORLD_EVENT = "world_event"
    REFLECTION_REQUEST = "reflection_request"
    BOUNDARY_CROSSING = "boundary_crossing"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    """风险级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class UserIntent:
    """用户意图"""
    primary: Optional[str] = None
    secondary: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Message:
    """消息"""
    role: str  # user / assistant / system
    content: str


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: Optional[str] = None
    turn_index: int = 0
    recent_messages: list[Message] = field(default_factory=list)


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[TaskStatus] = None


@dataclass
class RuntimeSummary:
    """运行时摘要"""
    tools_available: list[str] = field(default_factory=list)
    active_tasks: int = 0
    session_duration_seconds: float = 0.0


@dataclass
class SafetyContext:
    """安全上下文"""
    risk_level: RiskLevel = RiskLevel.LOW
    guardrails_triggered: list[str] = field(default_factory=list)
    requires_approval: bool = False


@dataclass
class ExternalResult:
    """外部结果"""
    success: bool = True
    output: Any = None
    error: Optional[str] = None


@dataclass
class OpenEmotionEventV1:
    """
    OpenEmotion 正式输入事件 v1

    用途: EgoCore → OpenEmotion 的标准输入格式
    版本: v1.0.0
    冻结: 是
    """

    # 必需字段
    event_id: str
    timestamp: datetime
    actor: str
    source: EventSource
    event_type: EventType

    # 可选字段
    user_intent: Optional[UserIntent] = None
    conversation_context: Optional[ConversationContext] = None
    task_context: Optional[TaskContext] = None
    runtime_summary: Optional[RuntimeSummary] = None
    safety_context: Optional[SafetyContext] = None
    external_result: Optional[ExternalResult] = None
    content: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "source": self.source.value,
            "event_type": self.event_type.value,
            "user_intent": self.user_intent.__dict__ if self.user_intent else None,
            "conversation_context": self._conv_context_to_dict(),
            "task_context": self._task_context_to_dict(),
            "runtime_summary": self._runtime_summary_to_dict(),
            "safety_context": self._safety_context_to_dict(),
            "external_result": self._external_result_to_dict(),
            "content": self.content,
            "metadata": self.metadata,
        }

    def _conv_context_to_dict(self) -> Optional[dict]:
        if not self.conversation_context:
            return None
        return {
            "session_id": self.conversation_context.session_id,
            "turn_index": self.conversation_context.turn_index,
            "recent_messages": [
                {"role": m.role, "content": m.content}
                for m in self.conversation_context.recent_messages
            ],
        }

    def _task_context_to_dict(self) -> Optional[dict]:
        if not self.task_context:
            return None
        return {
            "task_id": self.task_context.task_id,
            "task_type": self.task_context.task_type,
            "status": self.task_context.status.value if self.task_context.status else None,
        }

    def _runtime_summary_to_dict(self) -> Optional[dict]:
        if not self.runtime_summary:
            return None
        return {
            "tools_available": self.runtime_summary.tools_available,
            "active_tasks": self.runtime_summary.active_tasks,
            "session_duration_seconds": self.runtime_summary.session_duration_seconds,
        }

    def _safety_context_to_dict(self) -> Optional[dict]:
        if not self.safety_context:
            return None
        return {
            "risk_level": self.safety_context.risk_level.value,
            "guardrails_triggered": self.safety_context.guardrails_triggered,
            "requires_approval": self.safety_context.requires_approval,
        }

    def _external_result_to_dict(self) -> Optional[dict]:
        if not self.external_result:
            return None
        return {
            "success": self.external_result.success,
            "output": self.external_result.output,
            "error": self.external_result.error,
        }


# 版本标记
EVENT_V1_VERSION = "1.0.0"
EVENT_V1_FROZEN = True
