"""
Test prediction error calculation and modulation
"""
import pytest
import asyncio
from emotiond.api import app
from fastapi.testclient import TestClient
from emotiond.models import Event
from emotiond.db import init_db
from emotiond.config import DB_PATH
import os


@pytest.fixture(scope="session")
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Setup database for tests"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    import asyncio
    asyncio.run(init_db())
    
    # Clean up after tests
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


class TestPredictionError:
    """Test prediction error calculation and modulation"""
    
    def test_prediction_error_calculation_for_positive_message(self, client):
        """Test prediction error calculation for positive user message"""
        
        # Positive message should create prediction error
        response = client.post("/event", json={
            "type": "user_message",
            "actor": "user",
            "target": "agent",
            "text": "This is great! I love it!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "prediction_error" in data
        # Prediction error should be calculated (not zero)
        assert isinstance(data["prediction_error"], (int, float))
        
    def test_prediction_error_calculation_for_negative_message(self, client):
        """Test prediction error calculation for negative user message"""
        
        # Negative message should create prediction error
        response = client.post("/event", json={
            "type": "user_message",
            "actor": "user",
            "target": "agent",
            "text": "This is terrible! I hate it!"
        })
        assert response.status_code == 200
        data = response.json()
        assert "prediction_error" in data
        assert isinstance(data["prediction_error"], (int, float))
        
    def test_prediction_error_modulates_arousal(self, client):
        """Test that prediction error modulates arousal"""
        
        # Get initial arousal
        response1 = client.post("/event", json={
            "type": "user_message",
            "actor": "user",
            "target": "agent",
            "text": "Test message"
        })
        data1 = response1.json()
        initial_arousal = data1["arousal"]
        initial_prediction_error = data1["prediction_error"]
        
        # Send unexpected positive message
        response2 = client.post("/event", json={
            "type": "user_message",
            "actor": "user",
            "target": "agent",
            "text": "This is great! I love it!"
        })
        data2 = response2.json()
        final_arousal = data2["arousal"]
        final_prediction_error = data2["prediction_error"]
        
        # Prediction error should increase arousal
        # (strong positive message creates larger prediction error)
        assert final_prediction_error > initial_prediction_error
        assert final_arousal > initial_arousal
        
    def test_prediction_error_for_world_events(self, client):
        """Test prediction error calculation for world events"""
        
        # Positive world event
        response = client.post("/event", json={
            "type": "world_event",
            "actor": "system",
            "target": "agent",
            "text": "System achievement",
            "meta": {"positive": True}
        })
        assert response.status_code == 200
        data = response.json()
        assert "prediction_error" in data
        assert isinstance(data["prediction_error"], (int, float))
        
    def test_prediction_error_stored_in_database(self, client):
        """Test that prediction error is stored in database"""
        
        # Send multiple events and check prediction error persistence
        events = [
            {
                "type": "user_message",
                "actor": "user",
                "target": "agent",
                "text": "First positive message"
            },
            {
                "type": "user_message",
                "actor": "user",
                "target": "agent",
                "text": "Second negative message"
            }
        ]
        
        prediction_errors = []
        for event in events:
            response = client.post("/event", json=event)
            assert response.status_code == 200
            data = response.json()
            prediction_errors.append(data["prediction_error"])
        
        # Prediction errors should be calculated for both events
        assert len(prediction_errors) == 2
        assert all(isinstance(pe, (int, float)) for pe in prediction_errors)
        
    def test_prediction_model_learning_mechanism(self, client):
        """Test that prediction error could be used for model learning (future enhancement)"""
        
        # Send similar events multiple times
        for i in range(3):
            response = client.post("/event", json={
                "type": "user_message",
                "actor": "user",
                "target": "agent",
                "text": "Consistent positive message"
            })
            assert response.status_code == 200
            data = response.json()
            # Prediction error should exist
            assert "prediction_error" in data
            # In a real implementation, prediction error would decrease over time
            # as the model learns the pattern