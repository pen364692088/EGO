#!/usr/bin/env python3
"""
Detailed verification script for prediction error functionality
"""
import asyncio
import os
from emotiond.api import app
from fastapi.testclient import TestClient
from emotiond.db import init_db
from emotiond.config import DB_PATH

async def verify_prediction_error_detailed():
    """Verify prediction error calculation and modulation with detailed state tracking"""
    
    # Setup database
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    await init_db()
    
    client = TestClient(app)
    
    print("Testing prediction error functionality with detailed state tracking...")
    
    # Test 1: Prediction error calculation for positive message
    print("\n1. Testing positive message prediction error...")
    response = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "This is great! I love it!"
    })
    assert response.status_code == 200
    data = response.json()
    print(f"   Response: {data}")
    
    # Test 2: Prediction error calculation for negative message
    print("\n2. Testing negative message prediction error...")
    response = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "This is terrible! I hate it!"
    })
    assert response.status_code == 200
    data = response.json()
    print(f"   Response: {data}")
    
    # Test 3: Prediction error modulates arousal with state tracking
    print("\n3. Testing prediction error modulates arousal with state tracking...")
    
    # First event - establish baseline
    response1 = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "Baseline test message"
    })
    data1 = response1.json()
    initial_arousal = data1["arousal"]
    initial_prediction_error = data1["prediction_error"]
    print(f"   Baseline: arousal={initial_arousal}, prediction_error={initial_prediction_error}")
    
    # Second event - strong positive message
    response2 = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "This is amazing! Wonderful! Fantastic!"
    })
    data2 = response2.json()
    final_arousal = data2["arousal"]
    final_prediction_error = data2["prediction_error"]
    print(f"   Strong positive: arousal={final_arousal}, prediction_error={final_prediction_error}")
    
    # Check if prediction error increased arousal
    arousal_increased = final_arousal > initial_arousal
    prediction_error_increased = final_prediction_error > initial_prediction_error
    
    print(f"   ✓ Prediction error increased: {prediction_error_increased}")
    print(f"   ✓ Arousal increased: {arousal_increased}")
    
    # Test 4: Multiple events to show prediction error pattern
    print("\n4. Testing multiple events pattern...")
    events = [
        {"type": "user_message", "text": "Good morning"},
        {"type": "user_message", "text": "You're doing great"},
        {"type": "user_message", "text": "I appreciate your help"},
        {"type": "user_message", "text": "This is terrible"},
        {"type": "world_event", "text": "System update", "meta": {"positive": True}}
    ]
    
    for i, event in enumerate(events):
        response = client.post("/event", json={
            "type": event["type"],
            "actor": "user",
            "target": "agent",
            "text": event["text"],
            "meta": event.get("meta", {})
        })
        data = response.json()
        print(f"   Event {i+1}: valence={data['valence']:.3f}, arousal={data['arousal']:.3f}, prediction_error={data['prediction_error']:.3f}")
    
    # Cleanup
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    print("\n✅ All prediction error tests completed!")
    return True

if __name__ == "__main__":
    asyncio.run(verify_prediction_error_detailed())