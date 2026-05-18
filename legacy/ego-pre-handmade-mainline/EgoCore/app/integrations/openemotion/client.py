"""
OpenEmotion Integration - Client

HTTP client for OpenEmotion API endpoints:
- /health
- /event
- /plan
"""

import logging
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from app.integrations.openemotion.types import (
    OpenEmotionEvent,
    OpenEmotionPlanRequest,
    OpenEmotionPlanResponse,
    OpenEmotionHealthStatus,
    FallbackReason,
    FallbackResult,
)


logger = logging.getLogger(__name__)


@dataclass
class OpenEmotionClientConfig:
    """Configuration for OpenEmotion client."""
    host: str = "127.0.0.1"
    port: int = 18080
    healthcheck_timeout_ms: int = 1000
    plan_timeout_ms: int = 1500
    event_timeout_ms: int = 800
    enabled: bool = True
    

class OpenEmotionClient:
    """
    HTTP client for OpenEmotion API.
    
    All methods have timeout protection and return fallback on failure.
    """
    
    def __init__(self, config: Optional[OpenEmotionClientConfig] = None):
        self.config = config or OpenEmotionClientConfig()
        self._base_url = f"http://{self.config.host}:{self.config.port}"
    
    def _get_timeout(self, timeout_ms: int) -> float:
        """Convert ms to seconds."""
        return timeout_ms / 1000.0
    
    def health(self) -> tuple[bool, Optional[OpenEmotionHealthStatus], Optional[FallbackResult]]:
        """
        Check OpenEmotion health.
        
        Returns:
            Tuple of (success, health_status, fallback_result)
        """
        if not self.config.enabled:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.NOT_ENABLED,
                message="OpenEmotion is not enabled",
            )
        
        url = f"{self._base_url}/health"
        timeout = self._get_timeout(self.config.healthcheck_timeout_ms)
        
        try:
            response = requests.get(url, timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                status = OpenEmotionHealthStatus.from_dict(data)
                return True, status, None
            
            elif 500 <= response.status_code < 600:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_5XX,
                    message=f"Server error: {response.status_code}",
                )
            
            else:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_4XX,
                    message=f"Client error: {response.status_code}",
                )
        
        except requests.exceptions.Timeout:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.TIMEOUT,
                message=f"Health check timed out after {self.config.healthcheck_timeout_ms}ms",
            )
        
        except requests.exceptions.ConnectionError as e:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.CONNECTION_REFUSED,
                message="Connection refused - OpenEmotion not running?",
                original_error=str(e),
            )
        
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.HTTP_5XX,
                message=str(e),
            )
    
    def send_event(self, event: OpenEmotionEvent) -> tuple[bool, Optional[FallbackResult]]:
        """
        Send an event to OpenEmotion.
        
        Args:
            event: Event to send
        
        Returns:
            Tuple of (success, fallback_result)
        """
        if not self.config.enabled:
            return False, FallbackResult(
                success=False,
                reason=FallbackReason.NOT_ENABLED,
                message="OpenEmotion is not enabled",
            )
        
        url = f"{self._base_url}/event"
        timeout = self._get_timeout(self.config.event_timeout_ms)
        
        try:
            response = requests.post(
                url,
                json=event.to_dict(),
                timeout=timeout,
            )
            
            if response.status_code == 200:
                logger.debug(f"Event sent: {event.type.value}")
                return True, None
            
            elif 500 <= response.status_code < 600:
                logger.warning(f"Event send failed: {response.status_code}")
                return False, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_5XX,
                    message=f"Server error: {response.status_code}",
                )
            
            else:
                return False, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_4XX,
                    message=f"Client error: {response.status_code}",
                )
        
        except requests.exceptions.Timeout:
            logger.warning(f"Event send timed out")
            return False, FallbackResult(
                success=False,
                reason=FallbackReason.TIMEOUT,
                message=f"Event send timed out after {self.config.event_timeout_ms}ms",
            )
        
        except requests.exceptions.ConnectionError:
            # Don't log connection errors too verbosely - expected when not running
            return False, FallbackResult(
                success=False,
                reason=FallbackReason.CONNECTION_REFUSED,
                message="Connection refused",
            )
        
        except Exception as e:
            logger.error(f"Event send failed: {e}")
            return False, FallbackResult(
                success=False,
                reason=FallbackReason.HTTP_5XX,
                message=str(e),
            )
    
    def get_plan(self, request: OpenEmotionPlanRequest) -> tuple[bool, Optional[OpenEmotionPlanResponse], Optional[FallbackResult]]:
        """
        Get a plan from OpenEmotion.
        
        Args:
            request: Plan request
        
        Returns:
            Tuple of (success, plan_response, fallback_result)
        """
        if not self.config.enabled:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.NOT_ENABLED,
                message="OpenEmotion is not enabled",
            )
        
        url = f"{self._base_url}/plan"
        timeout = self._get_timeout(self.config.plan_timeout_ms)
        
        try:
            response = requests.post(
                url,
                json=request.to_dict(),
                timeout=timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                plan = OpenEmotionPlanResponse.from_dict(data)
                logger.debug(f"Plan received for user {request.user_id}")
                return True, plan, None
            
            elif 500 <= response.status_code < 600:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_5XX,
                    message=f"Server error: {response.status_code}",
                )
            
            else:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_4XX,
                    message=f"Client error: {response.status_code}",
                )
        
        except requests.exceptions.Timeout:
            logger.warning(f"Plan request timed out")
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.TIMEOUT,
                message=f"Plan request timed out after {self.config.plan_timeout_ms}ms",
            )
        
        except requests.exceptions.ConnectionError:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.CONNECTION_REFUSED,
                message="Connection refused",
            )
        
        except Exception as e:
            logger.error(f"Plan request failed: {e}")
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.HTTP_5XX,
                message=str(e),
            )


    def plan(
        self,
        user_id: str,
        user_text: str,
        focus_target: Optional[str] = None,
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[FallbackResult]]:
        """
        Get a plan from OpenEmotion (simplified interface).
        
        This is a convenience method that wraps get_plan() with a simpler API.
        
        Args:
            user_id: User identifier
            user_text: User's message text
            focus_target: Optional focus target (not used in Phase 2)
        
        Returns:
            Tuple of (success, plan_dict, fallback_result)
        """
        from app.integrations.openemotion.types import OpenEmotionPlanRequest
        
        request = OpenEmotionPlanRequest(
            user_id=user_id,
            user_text=user_text,
        )
        
        success, plan_response, fallback = self.get_plan(request)
        
        if success and plan_response:
            return True, plan_response.to_dict(), None
        
        return False, None, fallback

    def cycle(
        self,
        event: Dict[str, Any],
        timeout_ms: int = 2000,
    ) -> tuple[bool, Optional[Dict[str, Any]], Optional[FallbackResult]]:
        """
        Execute cycle core v1: event -> state update -> memory gate -> readout.
        
        This is the new formal interface for Cycle Core v1.
        
        Args:
            event: OpenEmotionEventV1 dict (符合 schemas/openemotion_event_v1.schema.json)
            timeout_ms: Timeout in milliseconds
        
        Returns:
            Tuple of (success, result_dict, fallback_result)
        """
        if not self.config.enabled:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.NOT_ENABLED,
                message="OpenEmotion is not enabled",
            )
        
        url = f"{self._base_url}/cycle"
        timeout = self._get_timeout(timeout_ms)
        
        try:
            response = requests.post(
                url,
                json=event,
                timeout=timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Cycle completed: {data.get('trace_id')}")
                return True, data, None
            
            elif 500 <= response.status_code < 600:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_5XX,
                    message=f"Server error: {response.status_code}",
                )
            
            else:
                return False, None, FallbackResult(
                    success=False,
                    reason=FallbackReason.HTTP_4XX,
                    message=f"Client error: {response.status_code}",
                )
        
        except requests.exceptions.Timeout:
            logger.warning(f"Cycle request timed out")
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.TIMEOUT,
                message=f"Cycle request timed out after {timeout_ms}ms",
            )
        
        except requests.exceptions.ConnectionError:
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.CONNECTION_REFUSED,
                message="Connection refused",
            )
        
        except Exception as e:
            logger.error(f"Cycle request failed: {e}")
            return False, None, FallbackResult(
                success=False,
                reason=FallbackReason.HTTP_5XX,
                message=str(e),
            )


# ============================================================================
# Global Instance
# ============================================================================

_client: Optional[OpenEmotionClient] = None


def get_openemotion_client(config: Optional[OpenEmotionClientConfig] = None) -> OpenEmotionClient:
    """Get or create global OpenEmotion client."""
    global _client
    if _client is None:
        _client = OpenEmotionClient(config)
    return _client
