"""
Plan Injection - Reply Injection

Integrates plan injection into EgoCore's reply generation path.
This is the main entry point for plan-augmented reply generation.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.integrations.openemotion.client import (
    OpenEmotionClient,
    get_openemotion_client,
)
from app.integrations.openemotion.injection_gate import (
    InjectionGate,
    GateResult,
    get_injection_gate,
)
from app.integrations.openemotion.plan_adapter import (
    PlanAdapter,
    ReplyGuidance,
)
from app.integrations.openemotion.fallback import (
    FallbackHandler,
    get_fallback_handler,
)


logger = logging.getLogger(__name__)


@dataclass
class InjectionResult:
    """
    Result of plan injection attempt.
    
    Contains:
    - guidance: ReplyGuidance to use for response
    - injected: Whether plan was successfully injected
    - latency_ms: Time taken for injection
    - gate_result: Gate decision
    - fallback_reason: Reason if fallback was used
    """
    guidance: ReplyGuidance
    injected: bool
    latency_ms: float
    gate_result: str
    fallback_reason: Optional[str] = None


class ReplyInjection:
    """
    Handles plan injection into reply generation.
    
    This is EgoCore's native implementation - no OpenClaw hooks required.
    
    Usage:
        injection = ReplyInjection()
        result = injection.maybe_inject(
            user_id="telegram:123",
            message_text="Hello!",
            context={}
        )
        
        if result.injected:
            # Use result.guidance to inform response
            tone = result.guidance.tone
            key_points = result.guidance.key_points
    """
    
    def __init__(
        self,
        client: Optional[OpenEmotionClient] = None,
        gate: Optional[InjectionGate] = None,
        fallback_handler: Optional[FallbackHandler] = None,
        timeout_ms: int = 1500,
    ):
        self.client = client or get_openemotion_client()
        self.gate = gate or get_injection_gate()
        self.fallback_handler = fallback_handler or get_fallback_handler()
        self.timeout_ms = timeout_ms
    
    def maybe_inject(
        self,
        user_id: str,
        message_text: str,
        context: Optional[Dict[str, Any]] = None,
        focus_target: Optional[str] = None,
    ) -> InjectionResult:
        """
        Attempt to inject plan into reply generation.
        
        This method:
        1. Evaluates the injection gate
        2. If allowed, calls OpenEmotion /plan
        3. Adapts the response to ReplyGuidance
        4. Handles fallback on any failure
        
        Args:
            user_id: User identifier (e.g., "telegram:123")
            message_text: The user's message
            context: Optional context for gate evaluation
            focus_target: Optional focus target override
        
        Returns:
            InjectionResult with guidance and metadata
        """
        start_time = time.time()
        
        # Step 1: Evaluate gate
        gate_decision = self.gate.evaluate(message_text, context)
        
        if gate_decision.result != GateResult.ALLOWED:
            # Gate blocked - return with fallback guidance
            latency_ms = (time.time() - start_time) * 1000
            return InjectionResult(
                guidance=PlanAdapter._fallback(gate_decision.reason or "gate_blocked"),
                injected=False,
                latency_ms=latency_ms,
                gate_result=gate_decision.result.value,
                fallback_reason=gate_decision.reason,
            )
        
        # Step 2: Call /plan API
        try:
            success, plan_response, fallback = self.client.plan(
                user_id=user_id,
                user_text=message_text,
                focus_target=focus_target or user_id,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            if success and plan_response:
                # Step 3: Adapt successful response
                guidance = PlanAdapter.adapt(plan_response)
                
                logger.info(
                    f"Plan injection success: user={user_id}, "
                    f"tone={guidance.tone}, latency={latency_ms:.1f}ms"
                )
                
                return InjectionResult(
                    guidance=guidance,
                    injected=True,
                    latency_ms=latency_ms,
                    gate_result=GateResult.ALLOWED.value,
                )
            
            else:
                # Plan failed - use fallback
                reason = fallback.reason.value if fallback else "unknown"
                
                logger.warning(
                    f"Plan injection fallback: user={user_id}, "
                    f"reason={reason}, latency={latency_ms:.1f}ms"
                )
                
                return InjectionResult(
                    guidance=PlanAdapter._fallback(reason),
                    injected=False,
                    latency_ms=latency_ms,
                    gate_result=GateResult.ERROR.value,
                    fallback_reason=reason,
                )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Plan injection error: {e}")
            
            return InjectionResult(
                guidance=PlanAdapter._fallback(f"exception: {e}"),
                injected=False,
                latency_ms=latency_ms,
                gate_result=GateResult.ERROR.value,
                fallback_reason=str(e),
            )
    
    def get_reply_context(
        self,
        user_id: str,
        message_text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get a prompt context string for reply generation.
        
        This is a convenience method that returns the guidance
        as a formatted string suitable for LLM prompt injection.
        
        Args:
            user_id: User identifier
            message_text: User's message
            context: Optional context
        
        Returns:
            Formatted guidance string for prompt
        """
        result = self.maybe_inject(user_id, message_text, context)
        return result.guidance.to_prompt_context()


# Global instance
_reply_injection: Optional[ReplyInjection] = None


def get_reply_injection() -> ReplyInjection:
    """Get the global ReplyInjection instance."""
    global _reply_injection
    if _reply_injection is None:
        _reply_injection = ReplyInjection()
    return _reply_injection


def maybe_inject_plan(
    user_id: str,
    message_text: str,
    context: Optional[Dict[str, Any]] = None,
) -> InjectionResult:
    """
    Convenience function for plan injection.
    
    Args:
        user_id: User identifier
        message_text: User's message
        context: Optional context
    
    Returns:
        InjectionResult
    """
    return get_reply_injection().maybe_inject(user_id, message_text, context)
