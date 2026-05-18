"""
OpenEmotion Embedded Integration Tests

Tests for:
- Phase 0: Manager + Health + Degraded
- Phase 1: Shadow event mirror
- Phase 2: Read-only plan injection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

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
)
from app.integrations.openemotion.manager import (
    OpenEmotionManager,
    OpenEmotionManagerConfig,
)
from app.integrations.openemotion.adapter import (
    EventAdapter,
)
from app.integrations.openemotion.fallback import (
    FallbackHandler,
    FallbackMetrics,
)


# ============================================================================
# Phase 0: Manager + Health Tests
# ============================================================================

class TestOpenEmotionTypes:
    """Tests for OpenEmotion types."""
    
    def test_event_type_values(self):
        """Event types should have correct values."""
        assert EventType.USER_MESSAGE.value == "user_message"
        assert EventType.ASSISTANT_REPLY.value == "assistant_reply"
        assert EventType.WORLD_EVENT.value == "world_event"
    
    def test_event_actor_values(self):
        """Event actors should have correct values."""
        assert EventActor.USER.value == "user"
        assert EventActor.ASSISTANT.value == "assistant"
        assert EventActor.SYSTEM.value == "system"
    
    def test_openemotion_event_serialization(self):
        """OpenEmotionEvent should serialize correctly."""
        event = OpenEmotionEvent(
            type=EventType.USER_MESSAGE,
            actor=EventActor.USER,
            text="Hello",
            meta={"thread_id": "test_123"},
        )
        
        data = event.to_dict()
        
        assert data["type"] == "user_message"
        assert data["actor"] == "user"
        assert data["text"] == "Hello"
        assert data["meta"]["thread_id"] == "test_123"
    
    def test_plan_request_serialization(self):
        """OpenEmotionPlanRequest should serialize correctly."""
        request = OpenEmotionPlanRequest(
            user_id="user_123",
            user_text="Hello",
        )
        
        data = request.to_dict()
        
        assert data["user_id"] == "user_123"
        assert data["user_text"] == "Hello"
    
    def test_plan_response_from_dict(self):
        """OpenEmotionPlanResponse should parse correctly."""
        data = {
            "tone": "friendly",
            "intent": "greeting",
            "key_points": ["Say hello"],
        }
        
        response = OpenEmotionPlanResponse.from_dict(data)
        
        assert response.tone == "friendly"
        assert response.intent == "greeting"
        assert response.key_points == ["Say hello"]
    
    def test_health_status_from_dict(self):
        """OpenEmotionHealthStatus should parse correctly."""
        data = {
            "healthy": True,
            "version": "1.0.0",
        }
        
        status = OpenEmotionHealthStatus.from_dict(data)
        
        assert status.healthy is True
        assert status.version == "1.0.0"


class TestOpenEmotionClient:
    """Tests for OpenEmotion client."""
    
    def test_client_config_defaults(self):
        """Client config should have safe defaults."""
        config = OpenEmotionClientConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 18080
        assert config.enabled is True
        assert config.healthcheck_timeout_ms == 1000
    
    def test_health_not_enabled(self):
        """Health check should fail when not enabled."""
        config = OpenEmotionClientConfig(enabled=False)
        client = OpenEmotionClient(config)
        
        success, status, fallback = client.health()
        
        assert success is False
        assert fallback is not None
        assert fallback.reason == FallbackReason.NOT_ENABLED
    
    def test_send_event_not_enabled(self):
        """Send event should fail when not enabled."""
        config = OpenEmotionClientConfig(enabled=False)
        client = OpenEmotionClient(config)
        
        event = OpenEmotionEvent(
            type=EventType.USER_MESSAGE,
            actor=EventActor.USER,
            text="Test",
        )
        
        success, fallback = client.send_event(event)
        
        assert success is False
        assert fallback.reason == FallbackReason.NOT_ENABLED
    
    def test_get_plan_not_enabled(self):
        """Get plan should fail when not enabled."""
        config = OpenEmotionClientConfig(enabled=False)
        client = OpenEmotionClient(config)
        
        request = OpenEmotionPlanRequest(
            user_id="test",
            user_text="Hello",
        )
        
        success, plan, fallback = client.get_plan(request)
        
        assert success is False
        assert fallback.reason == FallbackReason.NOT_ENABLED


class TestOpenEmotionManager:
    """Tests for OpenEmotion manager."""
    
    def test_manager_config_defaults(self):
        """Manager config should have safe defaults."""
        config = OpenEmotionManagerConfig()
        
        assert config.enabled is True
        assert config.auto_start is True
        assert config.restart_on_failure is True
        assert config.max_restart_attempts == 3
    
    def test_manager_not_enabled(self):
        """Manager should not start when disabled."""
        config = OpenEmotionManagerConfig(enabled=False)
        manager = OpenEmotionManager(config)
        
        success, message = manager.start()
        
        assert success is False
        assert "not enabled" in message
    
    def test_manager_is_running_false_initially(self):
        """Manager should report not running initially."""
        config = OpenEmotionManagerConfig()
        manager = OpenEmotionManager(config)
        
        assert manager.is_running is False
    
    def test_manager_is_healthy_false_initially(self):
        """Manager should report not healthy initially."""
        config = OpenEmotionManagerConfig()
        manager = OpenEmotionManager(config)
        
        assert manager.is_healthy is False


# ============================================================================
# Phase 1: Shadow Event Mirror Tests
# ============================================================================

class TestEventAdapter:
    """Tests for event adapter."""
    
    def test_adapt_user_message(self):
        """Adapt user message should create correct event."""
        event = EventAdapter.adapt_user_message(
            text="Hello",
            chat_id="123",
            user_id="456",
            thread_id="thread_789",
            intent="chat",
        )
        
        assert event.type == EventType.USER_MESSAGE
        assert event.actor == EventActor.USER
        assert event.text == "Hello"
        assert event.meta["thread_id"] == "thread_789"
        assert event.meta["intent"] == "chat"
        assert event.meta["source"] == "telegram"
    
    def test_adapt_user_message_command_marked(self):
        """Command messages should be marked."""
        event = EventAdapter.adapt_user_message(
            text="/status",
            chat_id="123",
            user_id="456",
            is_command=True,
        )
        
        assert event.meta.get("is_command") is True
    
    def test_adapt_assistant_reply(self):
        """Adapt assistant reply should create correct event."""
        event = EventAdapter.adapt_assistant_reply(
            text="Hello there!",
            chat_id="123",
            thread_id="thread_789",
            tool_name="file",
            tool_status="success",
        )
        
        assert event.type == EventType.ASSISTANT_REPLY
        assert event.actor == EventActor.ASSISTANT
        assert event.text == "Hello there!"
        assert event.meta["tool_name"] == "file"
    
    def test_adapt_world_event(self):
        """Adapt world event should create correct event."""
        event = EventAdapter.adapt_world_event(
            event_type="tool_execution",
            description="Tool file executed successfully",
            chat_id="123",
            task_id="task_456",
        )
        
        assert event.type == EventType.WORLD_EVENT
        assert event.actor == EventActor.SYSTEM
        assert "file" in event.text.lower()
    
    def test_adapt_tool_execution(self):
        """Adapt tool execution should create correct event."""
        event = EventAdapter.adapt_tool_execution(
            tool_name="shell",
            status="failed",
            chat_id="123",
            error="Command not found",
        )
        
        assert event.type == EventType.WORLD_EVENT
        assert event.actor == EventActor.SYSTEM
        assert "shell" in event.text
        assert "failed" in event.text


# ============================================================================
# Phase 2: Read-only Plan Tests
# ============================================================================

class TestFallbackHandler:
    """Tests for fallback handler."""
    
    def test_handle_plan_fallback_returns_neutral(self):
        """Plan fallback should return neutral response."""
        handler = FallbackHandler()
        
        fallback = FallbackResult(
            success=False,
            reason=FallbackReason.TIMEOUT,
            message="Timed out",
        )
        
        response = handler.handle_plan_fallback(fallback, "Hello")
        
        assert response.tone is None
        assert response.intent is None
        assert response.key_points == []
    
    def test_handle_event_fallback_returns_true(self):
        """Event fallback should return True (fire-and-forget)."""
        handler = FallbackHandler()
        
        fallback = FallbackResult(
            success=False,
            reason=FallbackReason.CONNECTION_REFUSED,
            message="Connection refused",
        )
        
        result = handler.handle_event_fallback(fallback)
        
        assert result is True
    
    def test_should_use_degraded_mode_repeated_failures(self):
        """Should enter degraded mode after repeated failures."""
        handler = FallbackHandler()
        
        recent_fallbacks = [
            FallbackResult(success=False, reason=FallbackReason.CONNECTION_REFUSED, message=""),
            FallbackResult(success=False, reason=FallbackReason.CONNECTION_REFUSED, message=""),
            FallbackResult(success=False, reason=FallbackReason.CONNECTION_REFUSED, message=""),
        ]
        
        assert handler.should_use_degraded_mode(recent_fallbacks) is True
    
    def test_should_not_use_degraded_mode_mixed(self):
        """Should not enter degraded mode with mixed results."""
        handler = FallbackHandler()
        
        recent_fallbacks = [
            FallbackResult(success=False, reason=FallbackReason.TIMEOUT, message=""),
            FallbackResult(success=False, reason=FallbackReason.HTTP_5XX, message=""),
        ]
        
        assert handler.should_use_degraded_mode(recent_fallbacks) is False


class TestFallbackMetrics:
    """Tests for fallback metrics."""
    
    def test_record_event_attempt(self):
        """Should record event attempts."""
        metrics = FallbackMetrics()
        
        metrics.record_event_attempt(True)
        metrics.record_event_attempt(False, "timeout")
        metrics.record_event_attempt(False, "timeout")
        
        assert metrics._event_attempts == 3
        assert metrics._event_failures == 2
        assert metrics._fallback_reasons["timeout"] == 2
    
    def test_get_metrics(self):
        """Should return metrics summary."""
        metrics = FallbackMetrics()
        
        metrics.record_plan_attempt(True)
        metrics.record_plan_attempt(True)
        metrics.record_plan_attempt(False, "connection_refused")
        
        result = metrics.get_metrics()
        
        assert result["plan_attempts"] == 3
        assert result["plan_failures"] == 1
        assert result["plan_success_rate"] == 2/3


# ============================================================================
# Integration Tests
# ============================================================================

class TestOpenEmotionIntegration:
    """Integration tests for OpenEmotion embedded mode."""
    
    def test_degraded_mode_when_not_running(self):
        """Should enter degraded mode when OpenEmotion not running."""
        config = OpenEmotionManagerConfig(
            enabled=True,
            auto_start=False,  # Don't try to start
        )
        manager = OpenEmotionManager(config)
        
        healthy, message = manager.ensure_running()
        
        # Should fail because not running and auto_start disabled
        assert healthy is False
    
    def test_event_flow_with_disabled(self):
        """Event should be dropped when OpenEmotion disabled."""
        config = OpenEmotionClientConfig(enabled=False)
        client = OpenEmotionClient(config)
        
        event = EventAdapter.adapt_user_message(
            text="Hello",
            chat_id="123",
            user_id="456",
        )
        
        success, fallback = client.send_event(event)
        
        assert success is False
        assert fallback.reason == FallbackReason.NOT_ENABLED
    
    def test_plan_flow_with_disabled(self):
        """Plan should return neutral when OpenEmotion disabled."""
        config = OpenEmotionClientConfig(enabled=False)
        client = OpenEmotionClient(config)
        
        request = OpenEmotionPlanRequest(
            user_id="user_123",
            user_text="Hello",
        )
        
        success, plan, fallback = client.get_plan(request)
        
        assert success is False
        assert fallback.reason == FallbackReason.NOT_ENABLED
