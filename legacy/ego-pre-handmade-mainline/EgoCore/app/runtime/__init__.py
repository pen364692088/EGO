"""
EgoCore Runtime - 三层架构运行时

参考 OpenClaw 架构设计，提供:
1. Session/Routing Layer: 会话管理、队列串行化
2. Real Agent Loop: 核心执行入口
3. Channel Reply/Streaming: 回复分发

版本: v2.0.0
Created: 2026-03-19
"""

# Layer 1: Session / Routing
from .types import (
    SessionKey,
    SessionState,
    SessionStatus,
    IngressEvent,
    LanePriority,
)
from .lane_manager import (
    LaneManager,
    get_lane_manager,
    enqueue_in_lane,
)
from .session_manager import (
    SessionManager,
    get_session_manager,
)

# Layer 2: Agent Loop
from .types import (
    EgoCoreRunParams,
    EgoCoreRunResult,
    RunStatus,
    LifecyclePhase,
    LifecycleEvent,
    ToolEvent,
)
from .event_bus import (
    AgentEventBusImpl,
    get_event_bus,
    emit_lifecycle_event,
    emit_tool_event,
    emit_reply_event,
)
from .context_assembler import (
    ContextAssembler,
    ExecutionContext,
    get_context_assembler,
)
from .completion_guard import (
    CompletionGuard,
    get_completion_guard,
)
from .repair_context_manager import (
    RepairContextManager,
    get_repair_context_manager,
)
from .agent_runner import (
    runEmbeddedEgoCoreAgent,
    run_agent,
    run_agent_sync,
    create_run_id,
)
from .request_identity import RequestIdentity, derive_chain_id
from .request_lifecycle import RequestLifecycleState
from .delivery_policy import DeliveryIdentity, DeliveryDedupePolicy
from .completion_contract import CompletionContract, CompletionVerificationResult, HtmlEffectVerifier
from .request_resolution_policy import RequestResolutionPolicy

# Layer 3: Reply / Streaming
from .types import (
    ReplyPayload,
    ReplyType,
    ChannelAdapter,
)
from .reply_dispatcher import (
    ReplyDispatcher,
    get_reply_dispatcher,
    CLIAdapter,
    TelegramAdapter,
    get_cli_adapter,
    get_telegram_adapter,
    set_telegram_bot,
)

__all__ = [
    # Layer 1
    "SessionKey",
    "SessionState",
    "SessionStatus",
    "IngressEvent",
    "LanePriority",
    "LaneManager",
    "get_lane_manager",
    "enqueue_in_lane",
    "SessionManager",
    "get_session_manager",
    # Layer 2
    "EgoCoreRunParams",
    "EgoCoreRunResult",
    "RunStatus",
    "LifecyclePhase",
    "LifecycleEvent",
    "ToolEvent",
    "AgentEventBusImpl",
    "get_event_bus",
    "emit_lifecycle_event",
    "emit_tool_event",
    "emit_reply_event",
    "ContextAssembler",
    "ExecutionContext",
    "get_context_assembler",
    "CompletionGuard",
    "get_completion_guard",
    "RepairContextManager",
    "get_repair_context_manager",
    "runEmbeddedEgoCoreAgent",
    "run_agent",
    "run_agent_sync",
    "create_run_id",
    "RequestIdentity",
    "derive_chain_id",
    "RequestLifecycleState",
    "DeliveryIdentity",
    "DeliveryDedupePolicy",
    "CompletionContract",
    "CompletionVerificationResult",
    "HtmlEffectVerifier",
    "RequestResolutionPolicy",
    # Layer 3
    "ReplyPayload",
    "ReplyType",
    "ChannelAdapter",
    "ReplyDispatcher",
    "get_reply_dispatcher",
    "CLIAdapter",
    "TelegramAdapter",
    "get_cli_adapter",
    "get_telegram_adapter",
    "set_telegram_bot",
]
