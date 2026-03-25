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
        # P0-R2 修复：添加 "risk" 字段映射到 OpenEmotion 期望的字段名
        safety_ctx = ctx_dict.get("safety_context", {})
        risk_level_value = safety_ctx.get("risk_level", "low")
        event["safety_context"] = {
            "risk": risk_level_value,  # OpenEmotion 期望的字段名
            "risk_level": risk_level_value,  # 保留原字段名
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
