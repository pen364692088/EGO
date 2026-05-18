"""
Event Mirror - Mirror Telegram events to OpenEmotion

This module provides event mirroring functionality to send
user messages and bot replies to OpenEmotion for emotional processing.
"""

import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.integrations.openemotion.client import (
    OpenEmotionClient,
    get_openemotion_client,
)
from app.integrations.openemotion.types import (
    OpenEmotionEvent,
    EventType,
    EventActor,
)


logger = logging.getLogger(__name__)


@dataclass
class MirrorResult:
    """Result of event mirror attempt."""
    success: bool
    latency_ms: float
    error: Optional[str] = None
    response: Optional[Dict[str, Any]] = None


class EventMirror:
    """
    Mirrors events from EgoCore to OpenEmotion.
    
    This is the core integration point for the formal chain:
    Telegram → EgoCore → emotiond (OpenEmotion)
    """
    
    def __init__(
        self,
        client: Optional[OpenEmotionClient] = None,
        enabled: bool = True,
    ):
        self.client = client or get_openemotion_client()
        self.enabled = enabled
        self._stats = {
            "total_mirrored": 0,
            "successful": 0,
            "failed": 0,
        }
    
    def mirror_user_message(
        self,
        user_id: str,
        message_text: str,
        chat_id: Optional[str] = None,
        username: Optional[str] = None,
    ) -> MirrorResult:
        """
        Mirror a user message to OpenEmotion.
        
        Args:
            user_id: Telegram user ID
            message_text: The message text
            chat_id: Optional chat ID
            username: Optional username
        
        Returns:
            MirrorResult with success status and metadata
        """
        if not self.enabled:
            return MirrorResult(
                success=False,
                latency_ms=0,
                error="Event mirror disabled"
            )
        
        start_time = time.time()
        
        try:
            # Build event payload
            event = {
                "type": "user_message",
                "actor": str(user_id),
                "target": "assistant",
                "text": message_text,
                "meta": {
                    "source": "egocore_telegram",
                    "chat_id": chat_id,
                    "username": username,
                }
            }
            
            # Build Cycle Core v1 event (formal chain)
            # event_v1 schema: schemas/openemotion_event_v1.schema.json
            from datetime import datetime, timezone
            
            # 构建稳定的会话 key: telegram:{user_id}
            target_id = f"telegram:{user_id}"
            
            cycle_event = {
                "event_id": f"evt_{int(start_time * 1000)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": str(user_id),
                "target_id": target_id,  # 用于会话状态隔离
                "source": "telegram",
                "event_type": "user_message",
                "content": message_text,
                "meta": {
                    "chat_id": chat_id,
                    "username": username,
                    "entry_point": "egocore_telegram",
                }
            }
            
            # Send to OpenEmotion /cycle (Cycle Core v1 formal chain)
            success, result, fallback = self.client.cycle(cycle_event)
            
            latency_ms = (time.time() - start_time) * 1000
            
            self._stats["total_mirrored"] += 1
            if success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
            
            logger.info(
                f"Cycle Core v1: user={user_id}, type=user_message, "
                f"latency={latency_ms:.1f}ms, success={success}, "
                f"trace_id={result.get('trace_id') if result else 'N/A'}"
            )
            
            return MirrorResult(
                success=success,
                latency_ms=latency_ms,
                error=fallback.message if fallback else None,
                response=result
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["total_mirrored"] += 1
            self._stats["failed"] += 1
            
            logger.error(f"Event mirror failed: {e}")
            
            return MirrorResult(
                success=False,
                latency_ms=latency_ms,
                error=str(e)
            )
    
    def mirror_assistant_reply(
        self,
        reply_text: str,
        user_id: str,
        intent: str = "inform",
    ) -> MirrorResult:
        """
        Mirror an assistant reply to OpenEmotion.
        
        Args:
            reply_text: The reply text
            user_id: Target user ID
            intent: Reply intent (inform, repair, etc.)
        
        Returns:
            MirrorResult with success status
        """
        if not self.enabled:
            return MirrorResult(
                success=False,
                latency_ms=0,
                error="Event mirror disabled"
            )
        
        start_time = time.time()
        
        try:
            oe_event = OpenEmotionEvent(
                type=EventType.ASSISTANT_REPLY,
                actor=EventActor.ASSISTANT,
                target=str(user_id),
                text=reply_text,
                meta={
                    "source": "egocore_telegram",
                    "intent": intent,
                }
            )
            
            success, fallback = self.client.send_event(oe_event)
            
            latency_ms = (time.time() - start_time) * 1000
            
            self._stats["total_mirrored"] += 1
            if success:
                self._stats["successful"] += 1
            else:
                self._stats["failed"] += 1
            
            return MirrorResult(
                success=success,
                latency_ms=latency_ms,
                error=fallback.message if fallback else None
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._stats["total_mirrored"] += 1
            self._stats["failed"] += 1
            
            return MirrorResult(
                success=False,
                latency_ms=latency_ms,
                error=str(e)
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get mirror statistics."""
        return self._stats.copy()


# Singleton instance
_mirror: Optional[EventMirror] = None


def get_event_mirror() -> EventMirror:
    """Get the singleton EventMirror instance."""
    global _mirror
    if _mirror is None:
        _mirror = EventMirror()
    return _mirror
