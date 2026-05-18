"""
OpenEmotion Integration - Types

Defines request/response schemas for OpenEmotion API.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Types of events sent to OpenEmotion."""
    USER_MESSAGE = "user_message"
    ASSISTANT_REPLY = "assistant_reply"
    WORLD_EVENT = "world_event"


class EventActor(str, Enum):
    """Actors in events."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ============================================================================
# Event Types
# ============================================================================

@dataclass
class OpenEmotionEvent:
    """
    Event sent to OpenEmotion /event endpoint.
    
    Mirrors Telegram messages and system events.
    """
    type: EventType
    actor: EventActor
    target: str = "assistant"
    text: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API request format."""
        return {
            "type": self.type.value,
            "actor": self.actor.value,
            "target": self.target,
            "text": self.text,
            "meta": self.meta,
        }


@dataclass
class OpenEmotionEventMeta:
    """Metadata for OpenEmotion events."""
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    intent: Optional[str] = None  # chat, question, new_task, continue, command
    source: str = "telegram"
    tool_name: Optional[str] = None
    tool_status: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {"source": self.source}
        if self.thread_id:
            result["thread_id"] = self.thread_id
        if self.task_id:
            result["task_id"] = self.task_id
        if self.intent:
            result["intent"] = self.intent
        if self.tool_name:
            result["tool_name"] = self.tool_name
        if self.tool_status:
            result["tool_status"] = self.tool_status
        return result


# ============================================================================
# Plan Types
# ============================================================================

@dataclass
class OpenEmotionPlanRequest:
    """
    Request to OpenEmotion /plan endpoint.
    
    Phase 2: Only user_id and user_text are sent.
    """
    user_id: str
    user_text: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API request format."""
        return {
            "user_id": self.user_id,
            "user_text": self.user_text,
        }


@dataclass
class OpenEmotionPlanResponse:
    """
    Response from OpenEmotion /plan endpoint.
    
    Phase 2: Only certain fields are consumed.
    """
    tone: Optional[str] = None
    intent: Optional[str] = None
    focus_target: Optional[str] = None
    key_points: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    emotion: Optional[str] = None
    relationship: Optional[str] = None
    
    # Raw response for debugging
    raw: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenEmotionPlanResponse":
        """Create from API response."""
        return cls(
            tone=data.get("tone"),
            intent=data.get("intent"),
            focus_target=data.get("focus_target"),
            key_points=data.get("key_points", []),
            constraints=data.get("constraints", []),
            emotion=data.get("emotion"),
            relationship=data.get("relationship"),
            raw=data,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for compatibility."""
        result = {}
        if self.tone:
            result["tone"] = self.tone
        if self.intent:
            result["intent"] = self.intent
        if self.focus_target:
            result["focus_target"] = self.focus_target
        if self.key_points:
            result["key_points"] = self.key_points
        if self.constraints:
            result["constraints"] = self.constraints
        if self.emotion:
            result["emotion"] = self.emotion
        if self.relationship:
            result["relationship"] = self.relationship
        if self.raw:
            result["raw"] = self.raw
        return result


# ============================================================================
# Health Types
# ============================================================================

@dataclass
class OpenEmotionHealthStatus:
    """Health status from OpenEmotion /health endpoint."""
    healthy: bool
    version: Optional[str] = None
    uptime_seconds: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenEmotionHealthStatus":
        """Create from API response."""
        return cls(
            healthy=data.get("healthy", False),
            version=data.get("version"),
            uptime_seconds=data.get("uptime_seconds"),
        )


# ============================================================================
# Fallback Types
# ============================================================================

class FallbackReason(str, Enum):
    """Reasons for falling back to degraded mode."""
    TIMEOUT = "timeout"
    CONNECTION_REFUSED = "connection_refused"
    HTTP_5XX = "http_5xx"
    HTTP_4XX = "http_4xx"
    INVALID_SCHEMA = "invalid_schema"
    NOT_ENABLED = "not_enabled"
    NOT_READY = "not_ready"


@dataclass
class FallbackResult:
    """Result of a fallback operation."""
    success: bool
    reason: FallbackReason
    message: str = ""
    original_error: Optional[str] = None
