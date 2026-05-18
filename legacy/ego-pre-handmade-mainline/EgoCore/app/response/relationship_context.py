"""
RelationshipContext v1 - EgoCore

短期关系上下文，用于支持关系连续性表达。

职责：
- 记录最近的关系事件（affective_probe, repair 等）
- 维护关系温度 (conversation_temperature)
- 跟踪 social arc（对话走向）
- 提供给 verbalizer 使用

边界：
- 仅用于短期（会话内）关系上下文
- 不侵入长期记忆系统
- 不存储敏感数据

版本：1.0.0
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import math


class RelationshipEvent(str, Enum):
    """关系事件类型"""
    GREETING = "greeting"
    TESTING = "testing"
    AFFECTIVE_PROBE = "affective_probe"
    RELATIONSHIP_REPAIR = "relationship_repair"
    GRATITUDE = "gratitude"
    FRUSTRATION = "frustration"
    STATUS_PROBE = "status_probe"
    TASK_REQUEST = "task_request"
    CHITCHAT = "chitchat"


class SocialArc(str, Enum):
    """对话走向"""
    WARMING = "warming"          # 关系升温
    STABLE = "stable"            # 稳定
    COOLING = "cooling"          # 关系降温
    REPAIRING = "repairing"      # 修复中
    TESTING = "testing"          # 测试中
    UNKNOWN = "unknown"


@dataclass
class AffectiveEvent:
    """情感事件记录"""
    event_type: str
    timestamp: str
    user_input_summary: str = ""
    agent_response_summary: str = ""
    impact: str = "neutral"  # positive, neutral, negative
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "user_input_summary": self.user_input_summary,
            "agent_response_summary": self.agent_response_summary,
            "impact": self.impact,
            "resolved": self.resolved,
        }


@dataclass
class RelationshipContext:
    """
    短期关系上下文 v1
    
    用于支持 verbalizer 生成关系连续性的回复。
    
    关键字段：
    - conversation_temperature: 当前对话温度 [0, 1]
    - recent_affective_events: 最近情感事件
    - current_social_arc: 当前对话走向
    - last_repair_state: 最近修复状态
    """
    # 会话标识
    session_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 关系温度 [0, 1]，0 = 冷，1 = 温暖
    conversation_temperature: float = 0.5
    
    # 最近情感事件（最多保留 10 个）
    recent_affective_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # 最近 social mode 历史
    recent_social_modes: List[str] = field(default_factory=list)
    
    # 用户最近关于语气的反馈
    last_user_feedback_about_tone: Optional[str] = None
    last_user_feedback_at: Optional[str] = None
    
    # 最近关系状态变化
    last_relationship_shift: Optional[str] = None  # warming, cooling, stable
    last_relationship_shift_at: Optional[str] = None
    
    # 最近修复状态
    last_repair_state: Optional[str] = None  # needed, in_progress, resolved
    last_repair_at: Optional[str] = None
    
    # 当前对话走向
    current_social_arc: str = "unknown"
    
    # 轮次计数
    turn_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "conversation_temperature": self.conversation_temperature,
            "recent_affective_events": self.recent_affective_events,
            "recent_social_modes": self.recent_social_modes,
            "last_user_feedback_about_tone": self.last_user_feedback_about_tone,
            "last_user_feedback_at": self.last_user_feedback_at,
            "last_relationship_shift": self.last_relationship_shift,
            "last_relationship_shift_at": self.last_relationship_shift_at,
            "last_repair_state": self.last_repair_state,
            "last_repair_at": self.last_repair_at,
            "current_social_arc": self.current_social_arc,
            "turn_count": self.turn_count,
        }
    
    def _update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def record_event(
        self,
        event_type: str,
        user_input: str = "",
        agent_response: str = "",
        impact: str = "neutral",
    ) -> None:
        """
        记录一个关系事件
        
        Args:
            event_type: 事件类型
            user_input: 用户输入摘要
            agent_response: 代理回复摘要
            impact: 影响 (positive, neutral, negative)
        """
        self._update_timestamp()
        self.turn_count += 1
        
        # 添加到事件列表
        event = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_input_summary": user_input[:50] if user_input else "",
            "agent_response_summary": agent_response[:50] if agent_response else "",
            "impact": impact,
            "resolved": False,
        }
        
        self.recent_affective_events.append(event)
        
        # 保持最多 10 个事件
        if len(self.recent_affective_events) > 10:
            self.recent_affective_events = self.recent_affective_events[-10:]
        
        # 更新 social modes
        self.recent_social_modes.append(event_type)
        if len(self.recent_social_modes) > 10:
            self.recent_social_modes = self.recent_social_modes[-10:]
        
        # 调整温度
        self._adjust_temperature(event_type, impact)
        
        # 更新 social arc
        self._update_social_arc()
    
    def _adjust_temperature(self, event_type: str, impact: str) -> None:
        """根据事件类型调整温度"""
        delta = 0.0
        
        if event_type == RelationshipEvent.AFFECTIVE_PROBE.value:
            # 用户反馈冷淡，需要降温
            delta = -0.1
            self.last_user_feedback_about_tone = "冷淡"
            self.last_user_feedback_at = datetime.now(timezone.utc).isoformat()
        
        elif event_type == RelationshipEvent.RELATIONSHIP_REPAIR.value:
            # 修复后，温度回升
            delta = 0.05
            self.last_repair_state = "in_progress"
            self.last_repair_at = datetime.now(timezone.utc).isoformat()
        
        elif event_type == RelationshipEvent.GRATITUDE.value:
            # 感谢，温度上升
            delta = 0.05
        
        elif event_type == RelationshipEvent.FRUSTRATION.value:
            # 挫败，温度下降
            delta = -0.1
        
        elif event_type == RelationshipEvent.GREETING.value:
            # 问候，轻微上升
            delta = 0.02
        
        elif event_type == RelationshipEvent.TESTING.value:
            # 测试，保持
            delta = 0.0
        
        # 应用影响调整
        if impact == "positive":
            delta += 0.02
        elif impact == "negative":
            delta -= 0.02
        
        # 更新温度，保持在 [0, 1] 范围
        self.conversation_temperature = max(0.0, min(1.0, self.conversation_temperature + delta))
    
    def _update_social_arc(self) -> None:
        """更新对话走向"""
        if len(self.recent_affective_events) < 2:
            self.current_social_arc = SocialArc.UNKNOWN.value
            return
        
        # 分析最近 5 个事件
        recent = self.recent_affective_events[-5:]
        
        # 检查是否有修复
        has_repair = any(
            e["event_type"] in [RelationshipEvent.AFFECTIVE_PROBE.value, RelationshipEvent.RELATIONSHIP_REPAIR.value]
            for e in recent
        )
        
        # 检查是否有测试
        has_testing = any(
            e["event_type"] == RelationshipEvent.TESTING.value
            for e in recent
        )
        
        # 检查温度趋势
        temp = self.conversation_temperature
        
        if has_repair:
            self.current_social_arc = SocialArc.REPAIRING.value
            self.last_relationship_shift = "repairing"
            self.last_relationship_shift_at = datetime.now(timezone.utc).isoformat()
        
        elif has_testing:
            self.current_social_arc = SocialArc.TESTING.value
        
        elif temp > 0.6:
            self.current_social_arc = SocialArc.WARMING.value
        
        elif temp < 0.4:
            self.current_social_arc = SocialArc.COOLING.value
        
        else:
            self.current_social_arc = SocialArc.STABLE.value
    
    def mark_repair_resolved(self) -> None:
        """标记修复已完成"""
        self.last_repair_state = "resolved"
        self.last_repair_at = datetime.now(timezone.utc).isoformat()
        self._update_timestamp()
    
    def needs_soft_acknowledgment(self) -> bool:
        """是否需要软性承认（关系修复后的后续回复）"""
        if self.last_repair_state == "resolved":
            # 修复刚完成，需要软性承认
            if self.last_repair_at:
                repair_time = datetime.fromisoformat(self.last_repair_at.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                # 5 分钟内算"刚完成"
                if (now - repair_time).total_seconds() < 300:
                    return True
        
        return False
    
    def get_recent_mode_summary(self) -> str:
        """获取最近的模式摘要"""
        if not self.recent_social_modes:
            return "fresh"
        
        # 最近 3 个模式
        recent = self.recent_social_modes[-3:]
        return " → ".join(recent)
    
    def is_in_repair_mode(self) -> bool:
        """是否在修复模式中"""
        return (
            self.current_social_arc == SocialArc.REPAIRING.value or
            self.last_repair_state == "in_progress"
        )
    
    def should_be_warmer(self) -> bool:
        """是否应该更温暖"""
        return (
            self.conversation_temperature < 0.5 or
            self.last_user_feedback_about_tone is not None or
            self.is_in_repair_mode()
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RelationshipContext":
        """从字典创建"""
        return cls(
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            conversation_temperature=data.get("conversation_temperature", 0.5),
            recent_affective_events=data.get("recent_affective_events", []),
            recent_social_modes=data.get("recent_social_modes", []),
            last_user_feedback_about_tone=data.get("last_user_feedback_about_tone"),
            last_user_feedback_at=data.get("last_user_feedback_at"),
            last_relationship_shift=data.get("last_relationship_shift"),
            last_relationship_shift_at=data.get("last_relationship_shift_at"),
            last_repair_state=data.get("last_repair_state"),
            last_repair_at=data.get("last_repair_at"),
            current_social_arc=data.get("current_social_arc", "unknown"),
            turn_count=data.get("turn_count", 0),
        )


# ============================================================================
# 会话级别的关系上下文管理器
# ============================================================================

class RelationshipContextManager:
    """
    关系上下文管理器
    
    管理多个会话的关系上下文。
    使用内存存储，不持久化。
    """
    
    def __init__(self):
        self._contexts: Dict[str, RelationshipContext] = {}
    
    def get_context(self, session_id: str) -> RelationshipContext:
        """获取会话的关系上下文"""
        if session_id not in self._contexts:
            self._contexts[session_id] = RelationshipContext(session_id=session_id)
        return self._contexts[session_id]
    
    def update_context(
        self,
        session_id: str,
        event_type: str,
        user_input: str = "",
        agent_response: str = "",
        impact: str = "neutral",
    ) -> RelationshipContext:
        """更新关系上下文"""
        ctx = self.get_context(session_id)
        ctx.record_event(event_type, user_input, agent_response, impact)
        return ctx
    
    def clear_context(self, session_id: str) -> None:
        """清除会话的关系上下文"""
        if session_id in self._contexts:
            del self._contexts[session_id]
    
    def cleanup_old_contexts(self, max_age_minutes: int = 60) -> int:
        """清理旧的上下文"""
        now = datetime.now(timezone.utc)
        to_remove = []
        
        for session_id, ctx in self._contexts.items():
            if ctx.updated_at:
                updated = datetime.fromisoformat(ctx.updated_at.replace('Z', '+00:00'))
                age_minutes = (now - updated).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    to_remove.append(session_id)
        
        for session_id in to_remove:
            del self._contexts[session_id]
        
        return len(to_remove)


# 全局实例
_manager: Optional[RelationshipContextManager] = None


def get_relationship_context_manager() -> RelationshipContextManager:
    """获取全局关系上下文管理器"""
    global _manager
    if _manager is None:
        _manager = RelationshipContextManager()
    return _manager
