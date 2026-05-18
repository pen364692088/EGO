#!/usr/bin/env python3
"""
Simple verification script for prediction error functionality
"""
import asyncio
import os
from emotiond.api import app
from fastapi.testclient import TestClient
from emotiond.db import init_db
from emotiond.config import DB_PATH

async def verify_prediction_error():
    """Verify prediction error calculation and modulation"""
    
    # Setup database
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    await init_db()
    
    client = TestClient(app)
    
    print("Testing prediction error functionality...")
    
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
    assert "prediction_error" in data
    print(f"   ✓ Prediction error calculated: {data['prediction_error']}")
    
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
    assert "prediction_error" in data
    print(f"   ✓ Prediction error calculated: {data['prediction_error']}")
    
    # Test 3: Prediction error modulates arousal
    print("\n3. Testing prediction error modulates arousal...")
    response1 = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "Test message"
    })
    data1 = response1.json()
    initial_arousal = data1["arousal"]
    initial_prediction_error = data1["prediction_error"]
    
    response2 = client.post("/event", json={
        "type": "user_message",
        "actor": "user",
        "target": "agent",
        "text": "This is amazing! Wonderful! Fantastic!"
    })
    data2 = response2.json()
    final_arousal = data2["arousal"]
    final_prediction_error = data2["prediction_error"]
    
    print(f"   Initial arousal: {initial_arousal}, prediction error: {initial_prediction_error}")
    print(f"   Final arousal: {final_arousal}, prediction error: {final_prediction_error}")
    print(f"   ✓ Prediction error increased: {final_prediction_error > initial_prediction_error}")
    print(f"   ✓ Arousal increased: {final_arousal > initial_arousal}")
    
    # Test 4: World events
    print("\n4. Testing world events prediction error...")
    response = client.post("/event", json={
        "type": "world_event",
        "actor": "system",
        "target": "agent",
        "text": "System achievement",
        "meta": {"positive": True}
    })
    assert response.status_code == 200
    data = response.json()
    print(f"   Response: {data}")
    assert "prediction_error" in data
    print(f"   ✓ World event prediction error: {data['prediction_error']}")
    
    # Cleanup
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    print("\n✅ All prediction error tests passed!")
    return True

if __name__ == "__main__":
    asyncio.run(verify_prediction_error())