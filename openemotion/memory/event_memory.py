"""
Event Memory - 事件层

职责:
- 存储原始事件（不可变）
- 提供时间序列查询
- 作为叙事层的唯一数据源

边界:
- 不负责聚合/解释
- 不直接生成策略
- 只存储，不判断重要性

权威源: OpenEmotion
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum
import json
import uuid


class EventType(Enum):
    """事件类型枚举"""
    # 会话层
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    
    # 交互层
    USER_MESSAGE = "user_message"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    
    # 决策层
    DECISION_MADE = "decision_made"
    GOAL_SET = "goal_set"
    GOAL_COMPLETED = "goal_completed"
    
    # 反思层
    REFLECTION_TRIGGERED = "reflection_triggered"
    POLICY_CANDIDATE = "policy_candidate"
    
    # 系统层
    ERROR = "error"
    MILESTONE = "milestone"
    BOUNDARY_CROSSING = "boundary_crossing"


@dataclass
class Event:
    """
    事件 - 不可变原始记录
    
    设计原则:
    - 一旦创建，不可修改
    - 只增不减（append-only）
    - 最小必要字段
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.USER_MESSAGE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content: str = ""
    metadata: dict = field(default_factory=dict)
    session_id: Optional[str] = None
    related_event_ids: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "metadata": self.metadata,
            "session_id": self.session_id,
            "related_event_ids": self.related_event_ids,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """从字典反序列化"""
        return cls(
            id=data["id"],
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            content=data["content"],
            metadata=data.get("metadata", {}),
            session_id=data.get("session_id"),
            related_event_ids=data.get("related_event_ids", []),
        )


class EventMemory:
    """
    事件存储
    
    职责:
    - append-only 事件存储
    - 时间序列查询
    - 类型过滤查询
    
    不负责:
    - 重要性判断
    - 聚合/抽象
    - 策略生成
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self._events: list[Event] = []
        self._storage_path = storage_path
    
    def append(self, event: Event) -> str:
        """
        追加事件
        
        Args:
            event: 事件对象
            
        Returns:
            事件ID
        """
        self._events.append(event)
        return event.id
    
    def create(
        self,
        event_type: EventType,
        content: str,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
        related_event_ids: Optional[list] = None,
    ) -> Event:
        """
        创建并追加事件
        
        Returns:
            创建的事件对象
        """
        event = Event(
            event_type=event_type,
            content=content,
            metadata=metadata or {},
            session_id=session_id,
            related_event_ids=related_event_ids or [],
        )
        self.append(event)
        return event
    
    def get(self, event_id: str) -> Optional[Event]:
        """按ID获取事件"""
        for event in self._events:
            if event.id == event_id:
                return event
        return None
    
    def query(
        self,
        event_type: Optional[EventType] = None,
        session_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        查询事件
        
        Args:
            event_type: 过滤事件类型
            session_id: 过滤会话ID
            since: 起始时间
            until: 结束时间
            limit: 最大返回数量
            
        Returns:
            匹配的事件列表（按时间排序）
        """
        results = self._events
        
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        
        if since:
            results = [e for e in results if e.timestamp >= since]
        
        if until:
            results = [e for e in results if e.timestamp <= until]
        
        # 按时间排序
        results = sorted(results, key=lambda e: e.timestamp)
        
        return results[-limit:] if len(results) > limit else results
    
    def count(self, event_type: Optional[EventType] = None) -> int:
        """统计事件数量"""
        if event_type:
            return sum(1 for e in self._events if e.event_type == event_type)
        return len(self._events)
    
    def to_dict(self) -> dict:
        """导出为字典（用于持久化）"""
        return {
            "events": [e.to_dict() for e in self._events],
            "count": len(self._events),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EventMemory":
        """从字典恢复"""
        memory = cls()
        memory._events = [Event.from_dict(e) for e in data.get("events", [])]
        return memory
