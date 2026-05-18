"""
EgoCore Runtime Types - 三层架构类型定义

参考 OpenClaw 架构，定义 EgoCore 作为真正 agent runtime 的核心类型。

版本: v2.0.0
Created: 2026-03-19
"""

from typing import (
    Dict, Any, Optional, List, Callable, Awaitable,
    Union, Literal, TypedDict, Protocol, runtime_checkable,
)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import asyncio


# =============================================================================
# Layer 1: Session / Routing Types
# =============================================================================

class SessionStatus(str, Enum):
    """会话状态"""
    ACTIVE = "active"
    IDLE = "idle"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"


class LanePriority(int, Enum):
    """Lane 优先级"""
    HIGH = 0      # 用户交互
    NORMAL = 1    # 普通任务
    LOW = 2       # 后台任务


@dataclass
class SessionKey:
    """会话标识"""
    raw: str
    channel: str
    scope: str  # 'dm', 'group', 'channel'
    peer_id: Optional[str] = None
    group_id: Optional[str] = None
    thread_id: Optional[str] = None
    
    @classmethod
    def parse(cls, raw: str) -> "SessionKey":
        """解析会话 key"""
        # 格式: channel:scope:peer_id 或 channel:group:group_id[:thread:thread_id]
        parts = raw.split(":")
        if len(parts) < 2:
            return cls(raw=raw, channel="unknown", scope="dm")
        
        channel = parts[0]
        scope = parts[1] if len(parts) > 1 else "dm"
        peer_id = parts[2] if len(parts) > 2 and scope == "dm" else None
        group_id = parts[2] if len(parts) > 2 and scope in ("group", "channel") else None
        thread_id = parts[4] if len(parts) > 4 else None
        
        return cls(
            raw=raw,
            channel=channel,
            scope=scope,
            peer_id=peer_id,
            group_id=group_id,
            thread_id=thread_id,
        )
    
    @property
    def lane_key(self) -> str:
        """生成 lane key (用于队列串行化)"""
        return f"lane:{self.raw}"


@dataclass
class SessionState:
    """会话状态"""
    session_key: str
    session_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    turn_index: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # 上下文
    active_task_id: Optional[str] = None
    task_plan: Dict[str, Any] = field(default_factory=dict)
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    targets: List[Dict[str, Any]] = field(default_factory=list)
    active_target: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    last_observation: Dict[str, Any] = field(default_factory=dict)
    artifact_context_by_path: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    last_intent: Optional[str] = None
    active_artifact_path: Optional[str] = None
    artifact_kind: Optional[str] = None
    active_focus: Optional[str] = None
    default_edit_target: Optional[str] = None
    artifact_summary: Dict[str, Any] = field(default_factory=dict)
    last_known_state: Dict[str, Any] = field(default_factory=dict)
    last_tool_result: Dict[str, Any] = field(default_factory=dict)
    last_reply_turn: int = 0
    last_reply_content: str = ""
    
    # 计数
    total_turns: int = 0
    total_tokens: int = 0
    
    def touch(self):
        """更新时间戳"""
        self.updated_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_key": self.session_key,
            "session_id": self.session_id,
            "status": self.status.value,
            "turn_index": self.turn_index,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active_task_id": self.active_task_id,
            "task_plan": self.task_plan,
            "plan_steps": self.plan_steps,
            "targets": self.targets,
            "active_target": self.active_target,
            "completed_steps": self.completed_steps,
            "last_observation": self.last_observation,
            "artifact_context_by_path": self.artifact_context_by_path,
            "last_intent": self.last_intent,
            "active_artifact_path": self.active_artifact_path,
            "artifact_kind": self.artifact_kind,
            "active_focus": self.active_focus,
            "default_edit_target": self.default_edit_target,
            "artifact_summary": self.artifact_summary,
            "last_known_state": self.last_known_state,
            "last_tool_result": self.last_tool_result,
            "last_reply_turn": self.last_reply_turn,
            "last_reply_content": self.last_reply_content,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
        }


@dataclass
class IngressEvent:
    """入口事件 (标准化后的输入)"""
    event_id: str
    session_key: str
    user_id: str
    content: str
    channel: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # 元数据
    username: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    
    # 上下文
    images: List[Dict[str, Any]] = field(default_factory=list)
    reply_to: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_key": self.session_key,
            "user_id": self.user_id,
            "content": self.content,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
            "username": self.username,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "thread_id": self.thread_id,
        }


# =============================================================================
# Layer 2: Agent Loop Types
# =============================================================================

class RunStatus(str, Enum):
    """运行状态"""
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ABORTED = "aborted"


class LifecyclePhase(str, Enum):
    """生命周期阶段"""
    START = "start"
    CONTEXT_LOADED = "context_loaded"
    COGNITION_COMPLETE = "cognition_complete"
    TOOLS_EXECUTED = "tools_executed"
    END = "end"
    ERROR = "error"


@dataclass
class EgoCoreRunParams:
    """
    EgoCore 运行参数
    
    类似 OpenClaw 的 RunEmbeddedPiAgentParams，这是唯一的正式入口参数。
    """
    # 必需
    session_id: str
    session_key: str
    run_id: str
    prompt: str
    
    # 可选
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    channel: str = "cli"
    
    # 路由
    message_to: Optional[str] = None
    thread_id: Optional[str] = None
    group_id: Optional[str] = None
    
    # 发送者
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    sender_is_owner: bool = False
    
    # 模型
    provider: Optional[str] = None
    model: Optional[str] = None
    think_level: str = "medium"  # off, low, medium, high
    
    # 执行
    timeout_ms: int = 600000  # 10 分钟
    trigger: str = "user"  # user, cron, heartbeat, memory
    
    # 回调
    on_partial_reply: Optional[Callable[[str], Awaitable[None]]] = None
    on_tool_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    on_lifecycle: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
    
    # 控制
    abort_signal: Optional[asyncio.Event] = None
    
    # 额外
    images: List[Dict[str, Any]] = field(default_factory=list)
    extra_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EgoCoreRunResult:
    """运行结果"""
    run_id: str
    session_id: str
    status: RunStatus
    
    # 回复
    reply_text: Optional[str] = None
    reply_payloads: List[Dict[str, Any]] = field(default_factory=list)
    request_id: Optional[str] = None
    
    # 元数据
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    duration_ms: int = 0
    
    # 诊断
    trace_id: Optional[str] = None
    error: Optional[str] = None
    
    # 使用量
    input_tokens: int = 0
    output_tokens: int = 0
    
    # 认知结果
    primary_mode: Optional[str] = None
    runtime_route: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "reply_text": self.reply_text,
            "request_id": self.request_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "trace_id": self.trace_id,
            "error": self.error,
            "primary_mode": self.primary_mode,
            "runtime_route": self.runtime_route,
        }


# =============================================================================
# Layer 3: Reply / Streaming Types
# =============================================================================

class ReplyType(str, Enum):
    """回复类型"""
    TEXT = "text"
    MARKDOWN = "markdown"
    MEDIA = "media"
    TOOL_SUMMARY = "tool_summary"
    LIFECYCLE = "lifecycle"
    ERROR = "error"
    SILENT = "silent"  # NO_REPLY


@dataclass
class ReplyPayload:
    """
    回复载荷
    
    标准化的回复结构，由 ReplyDispatcher 分发到各 channel。
    """
    type: ReplyType
    content: str
    run_id: str
    session_id: str
    
    # 元数据
    is_final: bool = True
    is_partial: bool = False
    sequence: int = 0
    
    # 附加
    media_urls: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "is_final": self.is_final,
            "is_partial": self.is_partial,
            "sequence": self.sequence,
            "media_urls": self.media_urls,
            "metadata": self.metadata,
        }


@dataclass
class ToolEvent:
    """工具事件"""
    tool_name: str
    tool_args: Dict[str, Any]
    status: str  # start, progress, end, error
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "status": self.status,
            "output": self.output[:500] if self.output else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class LifecycleEvent:
    """生命周期事件"""
    phase: LifecyclePhase
    run_id: str
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # 附加数据
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


# =============================================================================
# Channel Adapter Protocol
# =============================================================================

@runtime_checkable
class ChannelAdapter(Protocol):
    """Channel 适配器协议"""
    
    @property
    def channel_name(self) -> str:
        """Channel 名称"""
        ...
    
    async def send_reply(self, payload: ReplyPayload) -> bool:
        """发送回复"""
        ...
    
    async def send_partial(self, text: str, sequence: int) -> bool:
        """发送部分回复 (streaming)"""
        ...
    
    async def send_typing(self, is_typing: bool) -> bool:
        """发送打字状态"""
        ...
    
    def format_for_channel(self, payload: ReplyPayload) -> str:
        """格式化回复内容"""
        ...


# =============================================================================
# Event Bus Protocol
# =============================================================================

@runtime_checkable
class AgentEventBus(Protocol):
    """Agent 事件总线协议"""
    
    def emit_lifecycle(self, event: LifecycleEvent) -> None:
        """发射生命周期事件"""
        ...
    
    def emit_tool(self, event: ToolEvent) -> None:
        """发射工具事件"""
        ...
    
    def emit_reply(self, payload: ReplyPayload) -> None:
        """发射回复事件"""
        ...
    
    def subscribe(
        self,
        run_id: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> None:
        """订阅事件"""
        ...
    
    def unsubscribe(self, run_id: str) -> None:
        """取消订阅"""
        ...


# =============================================================================
# Constants
# =============================================================================

# 默认超时
DEFAULT_TIMEOUT_MS = 600000  # 10 分钟
DEFAULT_RUN_TIMEOUT_MS = 600000
DEFAULT_WAIT_TIMEOUT_MS = 30000

# Lane 配置
MAX_CONCURRENT_RUNS_PER_SESSION = 1
MAX_CONCURRENT_RUNS_GLOBAL = 10

# Reply 配置
MAX_REPLY_LENGTH = 4096  # Telegram 限制
MAX_PARTIAL_REPLY_LENGTH = 200

# 事件流
STREAM_LIFECYCLE = "lifecycle"
STREAM_ASSISTANT = "assistant"
STREAM_TOOL = "tool"
STREAM_REPLY = "reply"

# 静默回复
NO_REPLY = "NO_REPLY"
SILENT_REPLY_TOKENS = ["NO_REPLY", "..."]
