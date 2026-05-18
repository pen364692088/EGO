"""
OpenEmotion Integration Package

Provides controlled integration with OpenEmotion as a managed local service.

Native EgoCore integration - no OpenClaw hooks required.
"""

from app.integrations.openemotion.types import (
    EventType,
    EventActor,
    OpenEmotionEvent,
    OpenEmotionEventMeta,
    OpenEmotionPlanRequest,
    OpenEmotionPlanResponse,
    OpenEmotionHealthStatus,
    FallbackReason,
    FallbackResult,
)
from app.integrations.openemotion.client import (
    OpenEmotionClient,
    OpenEmotionClientConfig,
    get_openemotion_client,
)
from app.integrations.openemotion.manager import (
    OpenEmotionManager,
    OpenEmotionManagerConfig,
    get_openemotion_manager,
)
from app.integrations.openemotion.adapter import (
    EventAdapter,
)
from app.integrations.openemotion.fallback import (
    FallbackHandler,
    FallbackMetrics,
    get_fallback_handler,
    get_fallback_metrics,
)
from app.integrations.openemotion.injection_gate import (
    InjectionGate,
    GateResult,
    GateDecision,
    get_injection_gate,
    configure_injection_gate,
)
from app.integrations.openemotion.plan_adapter import (
    PlanAdapter,
    ReplyGuidance,
    adapt_plan,
)
from app.integrations.openemotion.reply_injection import (
    ReplyInjection,
    InjectionResult,
    get_reply_injection,
    maybe_inject_plan,
)


__all__ = [
    # Types
    "EventType",
    "EventActor",
    "OpenEmotionEvent",
    "OpenEmotionEventMeta",
    "OpenEmotionPlanRequest",
    "OpenEmotionPlanResponse",
    "OpenEmotionHealthStatus",
    "FallbackReason",
    "FallbackResult",
    # Client
    "OpenEmotionClient",
    "OpenEmotionClientConfig",
    "get_openemotion_client",
    # Manager
    "OpenEmotionManager",
    "OpenEmotionManagerConfig",
    "get_openemotion_manager",
    # Adapter
    "EventAdapter",
    # Fallback
    "FallbackHandler",
    "FallbackMetrics",
    "get_fallback_handler",
    "get_fallback_metrics",
    # Injection Gate
    "InjectionGate",
    "GateResult",
    "GateDecision",
    "get_injection_gate",
    "configure_injection_gate",
    # Plan Adapter
    "PlanAdapter",
    "ReplyGuidance",
    "adapt_plan",
    # Reply Injection
    "ReplyInjection",
    "InjectionResult",
    "get_reply_injection",
    "maybe_inject_plan",
]
