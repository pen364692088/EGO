"""
OpenEmotion Event v1 Contract

符合 oe.event.v1 规范的完整事件结构。
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import json


class ActorType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class EventType(str, Enum):
    USER_MESSAGE = "user_message"
    ASSISTANT_REPLY = "assistant_reply"
    WORLD_EVENT = "world_event"
    EXTERNAL_RESULT = "external_result"


class IntentType(str, Enum):
    CHAT = "chat"
    QUESTION = "question"
    NEW_TASK = "new_task"
    CONTINUE_TASK = "continue_task"
    COMMAND = "command"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Actor:
    """事件发起者"""
    type: ActorType
    id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "id": self.id,
        }


@dataclass
class UserIntent:
    """用户意图"""
    raw_text: str
    intent_type: IntentType
    confidence: float = 0.9
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "intent_type": self.intent_type.value,
            "confidence": self.confidence,
        }


@dataclass
class ConversationContext:
    """对话上下文"""
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    recent_turns: List[Dict[str, Any]] = field(default_factory=list)
    current_topic: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.session_id:
            result["session_id"] = self.session_id
        if self.conversation_id:
            result["conversation_id"] = self.conversation_id
        if self.recent_turns:
            result["recent_turns"] = self.recent_turns
        if self.current_topic:
            result["current_topic"] = self.current_topic
        return result


@dataclass
class TaskContext:
    """任务上下文"""
    active_task_id: Optional[str] = None
    task_state: Optional[str] = None
    task_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.active_task_id:
            result["active_task_id"] = self.active_task_id
        if self.task_state:
            result["task_state"] = self.task_state
        if self.task_type:
            result["task_type"] = self.task_type
        return result


@dataclass
class RuntimeSummary:
    """运行时摘要"""
    mode: str = "interactive"
    available_tools: List[str] = field(default_factory=lambda: ["shell", "file", "python"])
    host_state: str = "healthy"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "available_tools": self.available_tools,
            "host_state": self.host_state,
        }


@dataclass
class SafetyContext:
    """安全上下文"""
    risk_level: RiskLevel = RiskLevel.LOW
    approval_required: bool = False
    permissions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "approval_required": self.approval_required,
            "permissions": self.permissions,
        }


@dataclass
class ExternalResult:
    """外部执行结果"""
    task_id: Optional[str] = None
    action: Optional[str] = None
    status: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {}
        if self.task_id:
            result["task_id"] = self.task_id
        if self.action:
            result["action"] = self.action
        if self.status:
            result["status"] = self.status
        if self.output:
            result["output"] = self.output
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class OpenEmotionEventV1:
    """
    OpenEmotion 事件契约 v1
    
    符合 oe.event.v1 规范的完整事件结构。
    """
    # 必填字段
    event_id: str
    timestamp: str
    actor: Actor
    source: str
    event_type: EventType
    user_intent: UserIntent
    safety_context: SafetyContext
    
    # 可选字段
    schema_version: str = "1.0.0"
    conversation_context: Optional[ConversationContext] = None
    task_context: Optional[TaskContext] = None
    runtime_summary: Optional[RuntimeSummary] = None
    external_result: Optional[ExternalResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "actor": self.actor.to_dict(),
            "source": self.source,
            "event_type": self.event_type.value,
            "user_intent": self.user_intent.to_dict(),
            "safety_context": self.safety_context.to_dict(),
        }
        
        if self.conversation_context:
            result["conversation_context"] = self.conversation_context.to_dict()
        if self.task_context:
            result["task_context"] = self.task_context.to_dict()
        if self.runtime_summary:
            result["runtime_summary"] = self.runtime_summary.to_dict()
        if self.external_result:
            result["external_result"] = self.external_result.to_dict()
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def create_user_message(
        cls,
        event_id: str,
        user_id: str,
        message_text: str,
        source: str = "telegram",
        intent_type: IntentType = IntentType.CHAT,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> "OpenEmotionEventV1":
        """创建用户消息事件"""
        return cls(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=Actor(type=ActorType.USER, id=user_id),
            source=source,
            event_type=EventType.USER_MESSAGE,
            user_intent=UserIntent(
                raw_text=message_text,
                intent_type=intent_type,
            ),
            safety_context=SafetyContext(),
            conversation_context=ConversationContext(
                session_id=session_id,
                conversation_id=conversation_id,
            ),
            metadata={"message_text": message_text},
        )
    
    @classmethod
    def create_assistant_reply(
        cls,
        event_id: str,
        user_id: str,
        reply_text: str,
        intent: str = "inform",
    ) -> "OpenEmotionEventV1":
        """创建助手回复事件"""
        return cls(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=Actor(type=ActorType.ASSISTANT, id="assistant"),
            source="egocore",
            event_type=EventType.ASSISTANT_REPLY,
            user_intent=UserIntent(
                raw_text=reply_text,
                intent_type=IntentType.CHAT,
            ),
            safety_context=SafetyContext(),
            metadata={"reply_text": reply_text, "intent": intent},
        )
    
    @classmethod
    def create_external_result(
        cls,
        event_id: str,
        task_id: str,
        action: str,
        status: str,
        output: Optional[str] = None,
        error: Optional[str] = None,
    ) -> "OpenEmotionEventV1":
        """创建外部结果事件"""
        return cls(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor=Actor(type=ActorType.SYSTEM, id="egocore_runtime"),
            source="egocore_task",
            event_type=EventType.EXTERNAL_RESULT,
            user_intent=UserIntent(
                raw_text="",
                intent_type=IntentType.COMMAND,
            ),
            safety_context=SafetyContext(),
            external_result=ExternalResult(
                task_id=task_id,
                action=action,
                status=status,
                output=output,
                error=error,
            ),
        )
