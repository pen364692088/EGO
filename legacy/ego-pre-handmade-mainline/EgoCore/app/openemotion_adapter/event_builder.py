"""
Event Builder - 宿主侧事件标准化

用途: 把 EgoCore 内部事件转换成 OpenEmotion 标准 EventV1 格式
职责: L3 边界适配层，不是主体本体层

重要:
- 不在这里定义主体字段语义
- 只做格式转换和标准化
- 主体逻辑在 OpenEmotion 侧

版本: v1.1.0 (2026-03-19)
- 新增 build_from_execution_context 支持完整上下文注入
- 强制规则: 没有上下文不允许直接规划或宣称完成
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from app.risk_signal import normalize_safety_context

# 从 OpenEmotion import 类型定义（如果可导入）
# 否则使用本地定义
try:
    from openemotion.contracts.event_v1 import (
        OpenEmotionEventV1,
        EventSource,
        EventType,
        UserIntent,
        ConversationContext,
        TaskContext,
        RuntimeSummary,
        SafetyContext,
        ExternalResult,
        Message,
        TaskStatus,
        RiskLevel,
    )
    HAS_OPENEMOTION = True
except ImportError:
    HAS_OPENEMOTION = False
    # 本地定义（fallback）
    from dataclasses import dataclass, field
    from enum import Enum

    class EventSource(str, Enum):
        TELEGRAM = "telegram"
        DISCORD = "discord"
        CLI = "cli"
        API = "api"
        INTERNAL = "internal"
        SCHEDULED = "scheduled"

    class EventType(str, Enum):
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


class EventBuilder:
    """
    事件构建器 - EgoCore 侧

    职责:
    - 把宿主内部事件转换成 OpenEmotionEventV1
    - 做格式标准化，不做语义解释
    - 语义解释在 OpenEmotion 侧
    """

    def __init__(self, default_source: EventSource = EventSource.TELEGRAM):
        self.default_source = default_source

    def build_from_user_message(
        self,
        user_id: str,
        content: str,
        session_id: Optional[str] = None,
        turn_index: int = 0,
        recent_messages: Optional[list[dict]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        从用户消息构建事件

        Args:
            user_id: 用户ID
            content: 消息内容
            session_id: 会话ID
            turn_index: 当前轮次
            recent_messages: 最近消息列表
            metadata: 附加元数据

        Returns:
            OpenEmotionEventV1 格式的字典
        """
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        event = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": user_id,
            "source": self.default_source.value,
            "event_type": EventType.USER_MESSAGE.value,
            "content": content,
            "metadata": metadata or {},
        }

        # 对话上下文
        if session_id or recent_messages:
            event["conversation_context"] = {
                "session_id": session_id,
                "turn_index": turn_index,
                "recent_messages": recent_messages or [],
            }

        return event

    def build_from_execution_context(
        self,
        execution_context: Any,  # ExecutionContext from context_assembler
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        从完整执行上下文构建事件

        强制规则:
        - 必须有 conversation_context
        - 必须有 task_context (即使是空)
        - 必须有 runtime_summary
        - 必须有 safety_context
        - 如果有 pending_repair，必须包含 repair_context

        Args:
            execution_context: ExecutionContext 实例
            content: 消息内容
            metadata: 附加元数据

        Returns:
            OpenEmotionEventV1 格式的字典，包含完整上下文
        """
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        # 提取上下文数据
        ctx_dict = execution_context.to_dict() if hasattr(execution_context, 'to_dict') else {}

        event = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": ctx_dict.get("conversation_context", {}).get("user_id", "unknown"),
            "source": self.default_source.value,
            "event_type": EventType.USER_MESSAGE.value,
            "content": content,
            "metadata": metadata or {},
        }

        # 对话上下文 (必须)
        conv_ctx = ctx_dict.get("conversation_context", {})
        event["conversation_context"] = {
            "session_id": conv_ctx.get("session_id"),
            "turn_index": conv_ctx.get("turn_index", 0),
            "recent_messages": conv_ctx.get("recent_messages", []),
            "user_id": conv_ctx.get("user_id"),
            "chat_id": conv_ctx.get("chat_id"),
        }

        # 任务上下文 (必须，即使是空)
        task_ctx = ctx_dict.get("task_context", {})
        event["task_context"] = {
            "active_task_id": task_ctx.get("active_task_id"),
            "task_goal": task_ctx.get("task_goal"),
            "task_status": task_ctx.get("task_status"),
            "current_step_index": task_ctx.get("current_step_index", 0),
            "total_steps": task_ctx.get("total_steps", 0),
            "has_task": task_ctx.get("has_task", False),
        }

        # 运行时摘要 (必须)
        runtime_ctx = ctx_dict.get("runtime_summary", {})
        event["runtime_summary"] = {
            "emotiond_available": runtime_ctx.get("emotiond_available", False),
            "llm_provider": runtime_ctx.get("llm_provider"),
            "tools_available": runtime_ctx.get("tools_available", []),
            "degraded_mode": runtime_ctx.get("degraded_mode", False),
        }

        # 安全上下文 (必须)
        safety_ctx = normalize_safety_context(ctx_dict.get("safety_context", {}))
        risk_level_value = safety_ctx.get("risk_level", "low")
        event["safety_context"] = {
            "risk_level": risk_level_value,
            "requires_approval": safety_ctx.get("requires_approval", False),
        }

        # 修复上下文 (如果有 pending repair)
        repair_ctx = ctx_dict.get("repair_context", {})
        if repair_ctx.get("has_pending_repair"):
            event["repair_context"] = {
                "has_pending_repair": True,
                "failed_task_id": repair_ctx.get("failed_task_id"),
                "failure_reason": repair_ctx.get("failure_reason"),
                "user_feedback": repair_ctx.get("user_feedback"),
            }

        # 执行追踪 (如果有)
        exec_tracking = ctx_dict.get("execution_tracking", {})
        if exec_tracking.get("target_path") or exec_tracking.get("tool_capability"):
            event["execution_tracking"] = exec_tracking

        # 项目记忆 (如果有)
        proj_ctx = ctx_dict.get("project_memory", {})
        if proj_ctx.get("project_name") or proj_ctx.get("key_files"):
            event["project_memory"] = proj_ctx

        return event

    def build_from_agent_response(
        self,
        agent_id: str,
        content: str,
        session_id: Optional[str] = None,
        turn_index: int = 0,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """从 agent 响应构建事件"""
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        event = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": agent_id,
            "source": EventSource.INTERNAL.value,
            "event_type": EventType.AGENT_RESPONSE.value,
            "content": content,
            "metadata": metadata or {},
        }

        if session_id:
            event["conversation_context"] = {
                "session_id": session_id,
                "turn_index": turn_index,
            }

        return event

    def build_from_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        actor: str = "agent",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """从工具调用构建事件"""
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        return {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": actor,
            "source": EventSource.INTERNAL.value,
            "event_type": EventType.TOOL_CALL.value,
            "metadata": {
                "tool_name": tool_name,
                "tool_args": tool_args,
                **(metadata or {}),
            },
        }

    def build_from_tool_result(
        self,
        tool_name: str,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        actor: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """从工具结果构建事件"""
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        event = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": actor,
            "source": EventSource.INTERNAL.value,
            "event_type": EventType.TOOL_RESULT.value,
            "external_result": {
                "success": success,
                "output": output,
                "error": error,
            },
            "metadata": {
                "tool_name": tool_name,
                **(metadata or {}),
            },
        }

        return event

    def build_session_start(
        self,
        user_id: str,
        session_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """构建会话开始事件"""
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        return {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": user_id,
            "source": self.default_source.value,
            "event_type": EventType.SESSION_START.value,
            "conversation_context": {
                "session_id": session_id,
                "turn_index": 0,
            },
            "metadata": metadata or {},
        }

    def build_session_end(
        self,
        user_id: str,
        session_id: str,
        turn_count: int,
        duration_seconds: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """构建会话结束事件"""
        event_id = f"evt_{uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc)

        return {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": user_id,
            "source": self.default_source.value,
            "event_type": EventType.SESSION_END.value,
            "conversation_context": {
                "session_id": session_id,
                "turn_index": turn_count,
            },
            "runtime_summary": {
                "session_duration_seconds": duration_seconds,
            },
            "metadata": metadata or {},
        }


# 默认实例
default_event_builder = EventBuilder()


def build_from_telegram_update(update: dict) -> dict[str, Any]:
    """
    从 Telegram Update 构建标准化事件。

    这是 Telegram 集成的正式入口函数，用于将原始 Telegram update
    转换为 OpenEmotion 标准 EventV1 格式。

    Args:
        update: Telegram API 返回的 Update 对象（字典形式）
            包含 update_id, message, edited_message 等字段

    Returns:
        OpenEmotionEventV1 格式的字典，包含：
        - event_id: 唯一事件标识
        - timestamp: ISO 格式时间戳
        - actor: 用户ID
        - source: "telegram"
        - event_type: 事件类型
        - content: 消息内容
        - conversation_context: 对话上下文
        - metadata: 原始 update 等

    Raises:
        ValueError: 如果 update 格式无效

    Example:
        >>> update = {"update_id": 123, "message": {...}}
        >>> event = build_from_telegram_update(update)
        >>> event["source"]
        'telegram'
    """
    if not isinstance(update, dict):
        raise ValueError(f"update must be dict, got {type(update)}")

    update_id = update.get("update_id")
    if update_id is None:
        raise ValueError("update must have 'update_id' field")

    # 提取消息对象
    message = update.get("message") or update.get("edited_message") or update.get("channel_post")

    if message is None:
        # 非消息类 update（如 inline_query 等）
        return _build_from_non_message_update(update)

    # 提取用户信息
    from_user = message.get("from", {})
    chat = message.get("chat", {})

    user_id = str(from_user.get("id", "unknown"))
    chat_id = str(chat.get("id", ""))
    username = from_user.get("username", "")

    # 提取消息内容
    text = message.get("text", "")
    caption = message.get("caption", "")
    content = text or caption or ""

    # 构建事件
    event_id = f"evt_{uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc)

    # 确定事件类型
    if message.get("text"):
        event_type = EventType.USER_MESSAGE.value
    elif message.get("photo") or message.get("document") or message.get("video"):
        event_type = EventType.USER_MESSAGE.value  # 媒体消息也作为用户消息
        content = content or "[媒体消息]"
    else:
        event_type = EventType.USER_MESSAGE.value
        content = content or "[其他消息类型]"

    event = {
        "event_id": event_id,
        "timestamp": timestamp.isoformat(),
        "actor": user_id,
        "source": EventSource.TELEGRAM.value,
        "event_type": event_type,
        "content": content,
        "conversation_context": {
            "session_id": chat_id,  # Telegram 用 chat_id 作为 session
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username,
            "message_id": message.get("message_id"),
            "turn_index": 0,
            "recent_messages": [],
        },
        "metadata": {
            "update_id": update_id,
            "message_date": message.get("date"),
            "chat_type": chat.get("type"),
            "raw_update": update,  # 保留原始 update 用于调试
        },
    }

    return event


def _build_from_non_message_update(update: dict) -> dict[str, Any]:
    """
    处理非消息类 Telegram update。

    包括：inline_query, chosen_inline_result, callback_query 等。
    """
    event_id = f"evt_{uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc)
    update_id = update.get("update_id", 0)

    # 确定类型
    if "inline_query" in update:
        inline = update["inline_query"]
        return {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": str(inline.get("from", {}).get("id", "unknown")),
            "source": EventSource.TELEGRAM.value,
            "event_type": "inline_query",
            "content": inline.get("query", ""),
            "conversation_context": {
                "session_id": str(inline.get("from", {}).get("id", "")),
            },
            "metadata": {
                "update_id": update_id,
                "inline_query_id": inline.get("id"),
                "raw_update": update,
            },
        }

    if "callback_query" in update:
        callback = update["callback_query"]
        message = callback.get("message", {})
        chat = message.get("chat", {})
        return {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "actor": str(callback.get("from", {}).get("id", "unknown")),
            "source": EventSource.TELEGRAM.value,
            "event_type": "callback_query",
            "content": callback.get("data", ""),
            "conversation_context": {
                "session_id": str(chat.get("id", "")),
                "chat_id": str(chat.get("id", "")),
                "message_id": message.get("message_id"),
            },
            "metadata": {
                "update_id": update_id,
                "callback_query_id": callback.get("id"),
                "raw_update": update,
            },
        }

    # 默认：未知类型
    return {
        "event_id": event_id,
        "timestamp": timestamp.isoformat(),
        "actor": "unknown",
        "source": EventSource.TELEGRAM.value,
        "event_type": "unknown_update",
        "content": "",
        "conversation_context": {},
        "metadata": {
            "update_id": update_id,
            "raw_update": update,
        },
    }
