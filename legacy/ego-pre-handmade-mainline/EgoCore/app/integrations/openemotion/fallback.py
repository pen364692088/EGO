"""
OpenEmotion Integration - Fallback

Fallback strategies when OpenEmotion is unavailable.
"""

import logging
from typing import Optional, Dict, Any

from app.integrations.openemotion.types import (
    OpenEmotionPlanResponse,
    FallbackReason,
    FallbackResult,
)


logger = logging.getLogger(__name__)


class FallbackHandler:
    """
    Handles fallback when OpenEmotion is unavailable.
    
    Core principle:
    - OpenEmotion failure must NOT crash EgoCore
    - Fallback must be transparent to user
    - All fallbacks are logged
    """
    
    @staticmethod
    def handle_plan_fallback(
        fallback: FallbackResult,
        user_text: str,
    ) -> OpenEmotionPlanResponse:
        """
        Handle fallback for /plan request.
        
        Returns a default plan that won't affect reply generation.
        
        Args:
            fallback: Fallback result
            user_text: Original user text
        
        Returns:
            Default OpenEmotionPlanResponse
        """
        logger.info(f"Plan fallback: {fallback.reason.value} - {fallback.message}")
        
        # Return neutral plan that won't affect reply
        return OpenEmotionPlanResponse(
            tone=None,
            intent=None,
            focus_target=None,
            key_points=[],
            constraints=[],
            emotion=None,
            relationship=None,
        )
    
    @staticmethod
    def handle_event_fallback(fallback: FallbackResult) -> bool:
        """
        Handle fallback for /event request.
        
        Events are fire-and-forget, so fallback is just logging.
        
        Args:
            fallback: Fallback result
        
        Returns:
            True to indicate event was handled (even if dropped)
        """
        logger.debug(f"Event fallback: {fallback.reason.value} - {fallback.message}")
        return True
    
    @staticmethod
    def should_use_degraded_mode(recent_fallbacks: list[FallbackResult]) -> bool:
        """
        Determine if we should enter degraded mode.
        
        Degraded mode means:
        - Don't try to call OpenEmotion for a while
        - All responses use fallback
        
        Args:
            recent_fallbacks: Recent fallback results
        
        Returns:
            True if should enter degraded mode
        """
        if not recent_fallbacks:
            return False
        
        # If last 3 attempts failed with connection refused, enter degraded mode
        if len(recent_fallbacks) >= 3:
            connection_failures = sum(
                1 for f in recent_fallbacks[-3:]
                if f.reason in (FallbackReason.CONNECTION_REFUSED, FallbackReason.TIMEOUT)
            )
            if connection_failures >= 3:
                logger.warning("Entering degraded mode due to repeated failures")
                return True
        
        return False
    
    @staticmethod
    def get_degraded_message() -> str:
        """Get message to log when entering degraded mode."""
        return "OpenEmotion unavailable, running in degraded mode"


# ============================================================================
# Metrics Tracking
# ============================================================================

class FallbackMetrics:
    """Track fallback metrics for monitoring."""
    
    def __init__(self):
        self._event_attempts = 0
        self._event_failures = 0
        self._plan_attempts = 0
        self._plan_failures = 0
        self._fallback_reasons: dict[str, int] = {}
    
    def record_event_attempt(self, success: bool, reason: Optional[str] = None) -> None:
        """Record an event attempt."""
        self._event_attempts += 1
        if not success:
            self._event_failures += 1
            if reason:
                self._fallback_reasons[reason] = self._fallback_reasons.get(reason, 0) + 1
    
    def record_plan_attempt(self, success: bool, reason: Optional[str] = None) -> None:
        """Record a plan attempt."""
        self._plan_attempts += 1
        if not success:
            self._plan_failures += 1
            if reason:
                self._fallback_reasons[reason] = self._fallback_reasons.get(reason, 0) + 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "event_attempts": self._event_attempts,
            "event_failures": self._event_failures,
            "event_success_rate": (
                (self._event_attempts - self._event_failures) / self._event_attempts
                if self._event_attempts > 0 else 1.0
            ),
            "plan_attempts": self._plan_attempts,
            "plan_failures": self._plan_failures,
            "plan_success_rate": (
                (self._plan_attempts - self._plan_failures) / self._plan_attempts
                if self._plan_attempts > 0 else 1.0
            ),
            "fallback_reasons": dict(self._fallback_reasons),
        }


# ============================================================================
# Global Instances
# ============================================================================

_fallback_handler: Optional[FallbackHandler] = None
_fallback_metrics: Optional[FallbackMetrics] = None


def get_fallback_handler() -> FallbackHandler:
    """Get or create global fallback handler."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = FallbackHandler()
    return _fallback_handler


def get_fallback_metrics() -> FallbackMetrics:
    """Get or create global fallback metrics."""
    global _fallback_metrics
    if _fallback_metrics is None:
        _fallback_metrics = FallbackMetrics()
    return _fallback_metrics
