#!/usr/bin/env python3
"""
OpenClaw skill for emotiond integration
"""

import httpx
import json
import sys
from typing import Dict, Any, Optional

EMOTIOND_URL = "http://127.0.0.1:18080"

def check_daemon_health() -> bool:
    """Check if emotiond daemon is reachable"""
    try:
        response = httpx.get(f"{EMOTIOND_URL}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False

def send_event(event_data: Dict[str, Any]) -> bool:
    """Send an event to emotiond"""
    try:
        response = httpx.post(f"{EMOTIOND_URL}/event", json=event_data, timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False

def send_assistant_reply(user_id: str, reply_text: str) -> bool:
    """Send assistant reply event to emotiond"""
    return send_event({
        "type": "assistant_reply",
        "actor": "agent",
        "target": user_id,
        "text": reply_text
    })

def get_plan(user_id: str, user_text: str) -> Dict[str, Any]:
    """Get response plan from emotiond"""
    try:
        response = httpx.post(
            f"{EMOTIOND_URL}/plan", 
            json={"user_id": user_id, "user_text": user_text},
            timeout=5.0
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"emotiond returned status {response.status_code}"}
    except Exception as e:
        return {"error": f"Failed to connect to emotiond: {e}"}

def process_user_message(user_id: str, user_text: str) -> Dict[str, Any]:
    """Process user message and return response plan"""
    # Check if daemon is reachable first
    if not check_daemon_health():
        return {"error": "emotiond daemon is not reachable. Please ensure it is running on 127.0.0.1:18080"}
    
    # Send user message event
    event_sent = send_event({
        "type": "user_message",
        "actor": user_id,
        "target": "agent",
        "text": user_text
    })
    
    if not event_sent:
        return {"error": "Failed to send user message event to emotiond"}
    
    # Get response plan
    plan = get_plan(user_id, user_text)
    return plan

def process_assistant_reply(user_id: str, reply_text: str) -> Dict[str, Any]:
    """Process assistant reply and track it with emotiond"""
    # Check if daemon is reachable first
    if not check_daemon_health():
        return {"error": "emotiond daemon is not reachable. Please ensure it is running on 127.0.0.1:18080"}
    
    # Send assistant reply event
    event_sent = send_assistant_reply(user_id, reply_text)
    
    if not event_sent:
        return {"error": "Failed to send assistant reply event to emotiond"}
    
    return {"status": "success", "message": "Assistant reply tracked successfully"}

if __name__ == "__main__":
    # Command-line interface for testing
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  skill.py user <user_id> <user_text>     - Process user message and get response plan")
        print("  skill.py reply <user_id> <reply_text>  - Send assistant reply")
        print("  skill.py health                        - Check daemon health")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "user":
        if len(sys.argv) < 4:
            print("Usage: skill.py user <user_id> <user_text>")
            sys.exit(1)
        user_id = sys.argv[2]
        user_text = sys.argv[3]
        result = process_user_message(user_id, user_text)
        print(json.dumps(result, indent=2))
        if "error" in result:
            sys.exit(1)
    
    elif command == "reply":
        if len(sys.argv) < 4:
            print("Usage: skill.py reply <user_id> <reply_text>")
            sys.exit(1)
        user_id = sys.argv[2]
        reply_text = sys.argv[3]
        result = process_assistant_reply(user_id, reply_text)
        print(json.dumps(result, indent=2))
        if "error" in result:
            sys.exit(1)
    
    elif command == "health":
        is_healthy = check_daemon_health()
        result = {"healthy": is_healthy}
        print(json.dumps(result, indent=2))
        sys.exit(0 if is_healthy else 1)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)