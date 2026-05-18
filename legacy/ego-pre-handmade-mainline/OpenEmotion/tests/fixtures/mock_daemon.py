#!/usr/bin/env python3
"""
Mock daemon for integration testing.
Provides the same API as the real daemon but without actually starting a server.
"""

import json
import time
import threading
from typing import Dict, Any, List
from pathlib import Path

# Mock data store
mock_events = []
mock_predictions = {}
mock_deltas = {}


def mock_daemon_health():
    """Mock health endpoint response."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "test-mock"
    }


def mock_daemon_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Mock event endpoint."""
    mock_events.append({
        "id": len(mock_events) + 1,
        "timestamp": time.time(),
        "data": event_data
    })
    return {
        "status": "accepted",
        "event_id": len(mock_events)
    }


def mock_daemon_plan(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Mock plan endpoint."""
    plan_id = f"plan_{int(time.time())}"
    
    # Generate a mock plan
    plan = {
        "plan_id": plan_id,
        "tone": "neutral",
        "intent": "respond",
        "focus_target": plan_data.get("user_text", "")[:50],
        "key_points": ["Mock response point 1", "Mock response point 2"],
        "constraints": ["be helpful", "be concise"],
        "emotion": {
            "valence": 0.0,
            "arousal": 0.5
        },
        "timestamp": time.time()
    }
    
    return plan


def mock_daemon_predict(predict_data: Dict[str, Any]) -> Dict[str, Any]:
    """Mock predict endpoint."""
    prediction_id = f"pred_{int(time.time())}"
    
    prediction = {
        "prediction_id": prediction_id,
        "input": predict_data,
        "prediction": {
            "emotion": "neutral",
            "confidence": 0.8,
            "suggested_action": "respond"
        },
        "timestamp": time.time()
    }
    
    mock_predictions[prediction_id] = prediction
    return prediction


def get_prediction(prediction_id: str) -> Dict[str, Any]:
    """Get prediction by ID."""
    return mock_predictions.get(prediction_id, {"error": "not found"})


def get_delta(delta_id: str) -> Dict[str, Any]:
    """Get delta by ID."""
    return mock_deltas.get(delta_id, {"error": "not found"})


def get_events(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent events."""
    return mock_events[-limit:]


# Mock the OpenClaw skill functions
def check_daemon_health(port: int = 18080) -> bool:
    """Mock daemon health check."""
    return True


def send_event(event_data: Dict[str, Any], port: int = 18080) -> Dict[str, Any]:
    """Mock sending event to daemon."""
    return mock_daemon_event(event_data)


def get_plan(plan_data: Dict[str, Any], port: int = 18080) -> Dict[str, Any]:
    """Mock getting plan from daemon."""
    return mock_daemon_plan(plan_data)


def process_user_message(user_text: str, user_id: str = "test_user", port: int = 18080) -> Dict[str, Any]:
    """Mock processing user message."""
    plan_data = {
        "user_id": user_id,
        "user_text": user_text
    }
    return get_plan(plan_data, port)


def process_assistant_reply(assistant_text: str, user_id: str = "test_user", port: int = 18080) -> Dict[str, Any]:
    """Mock processing assistant reply."""
    event_data = {
        "type": "assistant_message",
        "actor": "assistant",
        "target": user_id,
        "text": assistant_text
    }
    return send_event(event_data, port)
