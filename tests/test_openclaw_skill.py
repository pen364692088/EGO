"""
Tests for OpenClaw skill integration
"""

import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add the skill directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'openclaw_skill', 'emotion_core'))

from skill import (
    check_daemon_health,
    send_event,
    send_assistant_reply,
    get_plan,
    process_user_message,
    process_assistant_reply
)


class TestOpenClawSkill:
    """Test cases for OpenClaw skill functionality"""

    @pytest.fixture
    def mock_httpx(self):
        """Mock httpx for testing"""
        with patch('skill.httpx') as mock_httpx:
            yield mock_httpx

    def test_check_daemon_health_success(self, mock_httpx):
        """Test health check when daemon is reachable"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.get.return_value = mock_response
        
        assert check_daemon_health() is True
        mock_httpx.get.assert_called_once_with("http://127.0.0.1:18080/health", timeout=2.0)

    def test_check_daemon_health_failure(self, mock_httpx):
        """Test health check when daemon is not reachable"""
        mock_httpx.get.side_effect = Exception("Connection failed")
        
        assert check_daemon_health() is False

    def test_check_daemon_health_bad_status(self, mock_httpx):
        """Test health check when daemon returns non-200 status"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_httpx.get.return_value = mock_response
        
        assert check_daemon_health() is False

    def test_send_event_success(self, mock_httpx):
        """Test sending event successfully"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response
        
        event_data = {"type": "user_message", "actor": "user1", "target": "agent", "text": "Hello"}
        result = send_event(event_data)
        
        assert result is True
        mock_httpx.post.assert_called_once_with(
            "http://127.0.0.1:18080/event",
            json=event_data,
            timeout=5.0
        )

    def test_send_event_failure(self, mock_httpx):
        """Test sending event when connection fails"""
        mock_httpx.post.side_effect = Exception("Connection failed")
        
        event_data = {"type": "user_message", "actor": "user1", "target": "agent", "text": "Hello"}
        result = send_event(event_data)
        
        assert result is False

    def test_send_assistant_reply_success(self, mock_httpx):
        """Test sending assistant reply successfully"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx.post.return_value = mock_response
        
        result = send_assistant_reply("user1", "Hello there!")
        
        assert result is True
        mock_httpx.post.assert_called_once_with(
            "http://127.0.0.1:18080/event",
            json={
                "type": "assistant_reply",
                "actor": "agent",
                "target": "user1",
                "text": "Hello there!"
            },
            timeout=5.0
        )

    def test_get_plan_success(self, mock_httpx):
        """Test getting response plan successfully"""
        expected_plan = {
            "tone": "friendly",
            "intent": "respond",
            "focus_target": "user1",
            "key_points": ["acknowledge greeting"],
            "constraints": ["be concise"],
            "emotion": {"valence": 0.5, "arousal": 0.3},
            "relationship": {"bond": 0.8, "grudge": 0.1, "trust": 0.9}
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected_plan
        mock_httpx.post.return_value = mock_response
        
        result = get_plan("user1", "Hello")
        
        assert result == expected_plan
        mock_httpx.post.assert_called_once_with(
            "http://127.0.0.1:18080/plan",
            json={"user_id": "user1", "user_text": "Hello"},
            timeout=5.0
        )

    def test_get_plan_server_error(self, mock_httpx):
        """Test getting response plan when server returns error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_httpx.post.return_value = mock_response
        
        result = get_plan("user1", "Hello")
        
        assert "error" in result
        assert "emotiond returned status 500" in result["error"]

    def test_get_plan_connection_error(self, mock_httpx):
        """Test getting response plan when connection fails"""
        mock_httpx.post.side_effect = Exception("Connection failed")
        
        result = get_plan("user1", "Hello")
        
        assert "error" in result
        assert "Failed to connect to emotiond" in result["error"]

    def test_process_user_message_success(self, mock_httpx):
        """Test processing user message successfully"""
        # Mock health check
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_httpx.get.return_value = mock_health_response
        
        # Mock event sending
        mock_event_response = MagicMock()
        mock_event_response.status_code = 200
        mock_httpx.post.return_value = mock_event_response
        
        # Mock plan response
        expected_plan = {
            "tone": "friendly",
            "intent": "respond",
            "focus_target": "user1",
            "key_points": ["acknowledge greeting"],
            "constraints": ["be concise"],
            "emotion": {"valence": 0.5, "arousal": 0.3},
            "relationship": {"bond": 0.8, "grudge": 0.1, "trust": 0.9}
        }
        mock_plan_response = MagicMock()
        mock_plan_response.status_code = 200
        mock_plan_response.json.return_value = expected_plan
        mock_httpx.post.side_effect = [mock_event_response, mock_plan_response]
        
        result = process_user_message("user1", "Hello")
        
        assert result == expected_plan
        assert mock_httpx.get.call_count == 1
        assert mock_httpx.post.call_count == 2

    def test_process_user_message_daemon_unreachable(self, mock_httpx):
        """Test processing user message when daemon is unreachable"""
        mock_httpx.get.side_effect = Exception("Connection failed")
        
        result = process_user_message("user1", "Hello")
        
        assert "error" in result
        assert "emotiond daemon is not reachable" in result["error"]
        mock_httpx.post.assert_not_called()

    def test_process_user_message_event_failed(self, mock_httpx):
        """Test processing user message when event sending fails"""
        # Mock health check
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_httpx.get.return_value = mock_health_response
        
        # Mock event sending failure
        mock_httpx.post.side_effect = Exception("Connection failed")
        
        result = process_user_message("user1", "Hello")
        
        assert "error" in result
        assert "Failed to send user message event" in result["error"]

    def test_process_assistant_reply_success(self, mock_httpx):
        """Test processing assistant reply successfully"""
        # Mock health check
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_httpx.get.return_value = mock_health_response
        
        # Mock event sending
        mock_event_response = MagicMock()
        mock_event_response.status_code = 200
        mock_httpx.post.return_value = mock_event_response
        
        result = process_assistant_reply("user1", "Hello there!")
        
        assert result == {"status": "success", "message": "Assistant reply tracked successfully"}
        mock_httpx.get.assert_called_once_with("http://127.0.0.1:18080/health", timeout=2.0)
        mock_httpx.post.assert_called_once_with(
            "http://127.0.0.1:18080/event",
            json={
                "type": "assistant_reply",
                "actor": "agent",
                "target": "user1",
                "text": "Hello there!"
            },
            timeout=5.0
        )

    def test_process_assistant_reply_daemon_unreachable(self, mock_httpx):
        """Test processing assistant reply when daemon is unreachable"""
        mock_httpx.get.side_effect = Exception("Connection failed")
        
        result = process_assistant_reply("user1", "Hello there!")
        
        assert "error" in result
        assert "emotiond daemon is not reachable" in result["error"]
        mock_httpx.post.assert_not_called()

    def test_process_assistant_reply_event_failed(self, mock_httpx):
        """Test processing assistant reply when event sending fails"""
        # Mock health check
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_httpx.get.return_value = mock_health_response
        
        # Mock event sending failure
        mock_httpx.post.side_effect = Exception("Connection failed")
        
        result = process_assistant_reply("user1", "Hello there!")
        
        assert "error" in result
        assert "Failed to send assistant reply event" in result["error"]

    def test_skill_integration_flow(self, mock_httpx):
        """Test complete integration flow: user message -> plan -> assistant reply"""
        # Mock all responses
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        
        mock_event_response = MagicMock()
        mock_event_response.status_code = 200
        
        expected_plan = {
            "tone": "friendly",
            "intent": "respond",
            "focus_target": "user1",
            "key_points": ["acknowledge greeting"],
            "constraints": ["be concise"],
            "emotion": {"valence": 0.5, "arousal": 0.3},
            "relationship": {"bond": 0.8, "grudge": 0.1, "trust": 0.9}
        }
        mock_plan_response = MagicMock()
        mock_plan_response.status_code = 200
        mock_plan_response.json.return_value = expected_plan
        
        # Set up mock sequence
        mock_httpx.get.return_value = mock_health_response
        mock_httpx.post.side_effect = [mock_event_response, mock_plan_response, mock_event_response]
        
        # Process user message
        user_result = process_user_message("user1", "Hello")
        assert user_result == expected_plan
        
        # Process assistant reply
        reply_result = process_assistant_reply("user1", "Hello there!")
        assert reply_result == {"status": "success", "message": "Assistant reply tracked successfully"}
        
        # Verify all calls
        assert mock_httpx.get.call_count == 2  # One for user message, one for assistant reply
        assert mock_httpx.post.call_count == 3  # Event + plan for user message, event for assistant reply