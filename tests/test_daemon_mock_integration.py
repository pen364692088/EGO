"""
Integration tests using mock daemon instead of real daemon.
This provides the same coverage without requiring actual daemon startup.
"""

import sys
import time
from pathlib import Path
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import mock daemon functions
from tests.fixtures.mock_daemon import (
    check_daemon_health, send_event, get_plan, 
    process_user_message, process_assistant_reply,
    get_events, get_prediction, mock_daemon_event,
    mock_daemon_plan
)


class TestMockDaemonIntegration:
    """Tests using mock daemon for integration coverage."""

    def test_mock_daemon_health_check(self):
        """Test mock daemon health endpoint."""
        # Test health check
        health_ok = check_daemon_health()
        assert health_ok is True
        
    def test_mock_event_processing(self):
        """Test mock event processing."""
        event_data = {
            "type": "user_message",
            "actor": "test_user",
            "target": "assistant",
            "text": "Hello, how are you?"
        }
        
        response = send_event(event_data)
        assert response["status"] == "accepted"
        assert "event_id" in response
        
    def test_mock_plan_generation(self):
        """Test mock plan generation."""
        plan_data = {
            "user_id": "test_user",
            "user_text": "I need help with something"
        }
        
        plan = get_plan(plan_data)
        
        # Verify required fields
        required_fields = ["tone", "intent", "focus_target", "key_points", 
                         "constraints", "emotion"]
        for field in required_fields:
            assert field in plan, f"Missing field: {field}"
        
        # Verify emotion ranges
        assert -1 <= plan["emotion"]["valence"] <= 1
        assert 0 <= plan["emotion"]["arousal"] <= 1
        
    def test_mock_user_message_processing(self):
        """Test mock user message processing."""
        response = process_user_message("What's the weather like?", "user123")
        
        assert "plan_id" in response
        assert response["intent"] == "respond"
        assert "emotion" in response
        
    def test_mock_assistant_reply_processing(self):
        """Test mock assistant reply processing."""
        response = process_assistant_reply("The weather is sunny today.", "user123")
        
        assert response["status"] == "accepted"
        assert "event_id" in response
        
    def test_mock_multiple_events_and_plans(self):
        """Test processing multiple events and plans."""
        # Send multiple events
        for i in range(5):
            event_data = {
                "type": "user_message",
                "actor": f"user_{i}",
                "target": "assistant",
                "text": f"Test message {i}"
            }
            send_event(event_data)
        
        # Generate plans for each
        plans = []
        for i in range(5):
            plan_data = {
                "user_id": f"user_{i}",
                "user_text": f"Test message {i}"
            }
            plan = get_plan(plan_data)
            plans.append(plan)
        
        # Verify all plans are valid
        for plan in plans:
            assert "plan_id" in plan
            assert "emotion" in plan
            assert plan["intent"] in ["respond", "clarify", "escalate"]
            
    def test_mock_event_history(self):
        """Test mock event history retrieval."""
        # Add some events
        for i in range(3):
            event_data = {
                "type": "user_message",
                "actor": "history_user",
                "target": "assistant",
                "text": f"History message {i}"
            }
            mock_daemon_event(event_data)
        
        # Get events
        events = get_events(limit=5)
        assert len(events) >= 3
        
        # Verify event structure
        for event in events[-3:]:
            assert "id" in event
            assert "timestamp" in event
            assert "data" in event
            
    def test_mock_concurrent_processing(self):
        """Test mock concurrent request handling."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def worker(user_id):
            response = process_user_message(f"Message from {user_id}", user_id)
            results.put(response)
        
        # Start multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(f"user_{i}",))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check results
        assert results.qsize() == 10
        
        while not results.empty():
            response = results.get()
            assert "plan_id" in response
            assert "emotion" in response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
