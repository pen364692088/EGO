"""
Event Normalizer - EgoCore

标准化用户输入为 InteractionEventEnvelope。

归属：EgoCore
作用：把用户/环境输入、最近上下文、任务状态、运行时摘要转换成主体可理解事件。
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from egocore.contracts.interaction_event_envelope_v1 import (
    InteractionEventEnvelope,
    RecentTurn,
    ActiveTaskSummary,
    RuntimeSummary,
    SafetyContext,
    EventSource,
    InputType,
)


class EventNormalizer:
    """
    事件标准化器
    
    负责将 EgoCore 内部状态转换为标准的 InteractionEventEnvelope。
    """
    
    def __init__(self):
        self._turn_limit = 10  # 最多保留最近 10 轮
    
    def normalize(
        self,
        user_input: str,
        user_id: str,
        session_id: str,
        source: str = "telegram",
        recent_turns: Optional[List[Dict[str, Any]]] = None,
        active_task: Optional[Dict[str, Any]] = None,
        runtime_context: Optional[Dict[str, Any]] = None,
        safety_context: Optional[Dict[str, Any]] = None,
    ) -> InteractionEventEnvelope:
        """
        标准化用户输入
        
        Args:
            user_input: 用户输入文本
            user_id: 用户 ID
            session_id: 会话 ID
            source: 来源（telegram, discord, cli, api）
            recent_turns: 最近对话轮次
            active_task: 活动任务
            runtime_context: 运行时上下文
            safety_context: 安全上下文
        
        Returns:
            InteractionEventEnvelope
        """
        envelope_id = f"env_{uuid.uuid4().hex[:8]}"
        
        # 转换来源
        source_map = {
            "telegram": EventSource.TELEGRAM,
            "discord": EventSource.DISCORD,
            "cli": EventSource.CLI,
            "api": EventSource.API,
        }
        event_source = source_map.get(source, EventSource.TELEGRAM)
        
        # 转换最近对话
        turns = []
        if recent_turns:
            for t in recent_turns[-self._turn_limit:]:
                turns.append(RecentTurn(
                    role=t.get("role", "user"),
                    content=t.get("content", ""),
                    timestamp=t.get("timestamp", datetime.now(timezone.utc).isoformat()),
                ))
        
        # 转换活动任务
        task_summary = None
        if active_task:
            progress = active_task.get("progress", {})
            task_summary = ActiveTaskSummary(
                task_id=active_task.get("task_id", ""),
                objective=active_task.get("objective", ""),
                status=active_task.get("status", "unknown"),
                progress=(
                    progress.get("completed", 0),
                    progress.get("total", 0)
                ),
            )
        
        # 转换运行时上下文
        runtime = RuntimeSummary()
        if runtime_context:
            runtime = RuntimeSummary(
                has_active_task=runtime_context.get("has_active_task", False),
                pending_confirmations=runtime_context.get("pending_confirmations", 0),
                last_activity_seconds_ago=runtime_context.get("last_activity_seconds_ago", 0),
            )
        
        # 转换安全上下文
        safety = SafetyContext()
        if safety_context:
            safety = SafetyContext(
                is_elevated=safety_context.get("is_elevated", False),
                is_restricted=safety_context.get("is_restricted", False),
                requires_confirmation=safety_context.get("requires_confirmation", False),
            )
        
        return InteractionEventEnvelope(
            envelope_id=envelope_id,
            user_input=user_input,
            user_id=user_id,
            session_id=session_id,
            source=event_source,
            input_type=InputType.TEXT,
            recent_turns=turns,
            turn_count=len(turns),
            active_task=task_summary,
            runtime=runtime,
            safety=safety,
        )
    
    def from_telegram_context(
        self,
        user_input: str,
        chat_id: int,
        user_id: int,
        username: Optional[str] = None,
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        active_task: Optional[Dict[str, Any]] = None,
    ) -> InteractionEventEnvelope:
        """
        从 Telegram 上下文创建信封
        
        Args:
            user_input: 用户输入
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            username: 用户名
            recent_messages: 最近消息列表
            active_task: 活动任务
        
        Returns:
            InteractionEventEnvelope
        """
        session_id = f"tg_{chat_id}"
        user_id_str = f"telegram:{user_id}"
        
        # 转换最近消息
        recent_turns = []
        if recent_messages:
            for msg in recent_messages:
                recent_turns.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", ""),
                })
        
        return self.normalize(
            user_input=user_input,
            user_id=user_id_str,
            session_id=session_id,
            source="telegram",
            recent_turns=recent_turns,
            active_task=active_task,
            runtime_context={
                "has_active_task": active_task is not None,
            },
        )


# 全局实例
_normalizer: Optional[EventNormalizer] = None


def get_event_normalizer() -> EventNormalizer:
    """获取全局事件标准化器"""
    global _normalizer
    if _normalizer is None:
        _normalizer = EventNormalizer()
    return _normalizer
