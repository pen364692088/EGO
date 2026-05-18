""" Test actual implementation functionality """
import os
import pytest
import pytest_asyncio
import asyncio
from emotiond.db import init_db, get_state, update_state, add_event
from emotiond.models import Event, PlanRequest, PlanResponse
from emotiond.config import DB_PATH


@pytest.mark.asyncio
class TestDatabase:
    """Test database operations"""
    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self):
        """Setup database for tests"""
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        # Initialize database
        await init_db()
        # Clean up after tests
        yield
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    async def test_db_initializes(self):
        """Test that database initializes and tables exist"""
        # Database should exist after init
        assert os.path.exists(DB_PATH)
        # Should be able to get state
        state = await get_state()
        assert "valence" in state
        assert "arousal" in state
        assert "subjective_time" in state

    async def test_state_update(self):
        """Test state update functionality"""
        # Update state
        await update_state(0.5, 0.3, 100)
        # Verify update
        state = await get_state()
        assert state["valence"] == 0.5
        assert state["arousal"] == 0.3
        assert state["subjective_time"] == 100

    async def test_event_ingestion(self):
        """Test event ingestion"""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={"test": True}
        )
        await add_event(event.dict())
        # Should not raise exception


class TestModels:
    """Test Pydantic models"""
    def test_event_model(self):
        """Test Event model validation"""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello"
        )
        assert event.type == "user_message"
        assert event.actor == "user"
        assert event.target == "agent"
        assert event.text == "Hello"

    def test_plan_request_model(self):
        """Test PlanRequest model validation"""
        request = PlanRequest(
            user_id="test_user",
            user_text="How are you?"
        )
        assert request.user_id == "test_user"
        assert request.user_text == "How are you?"

    def test_plan_response_model(self):
        """Test PlanResponse model validation"""
        response = PlanResponse(
            tone="warm",
            intent="seek",
            focus_target="user",
            key_points=["Respond positively"],
            constraints=["Be helpful"],
            emotion={"valence": 0.5, "arousal": 0.3},
            relationship={"bond": 0.7, "grudge": 0.1}
        )
        assert response.tone == "warm"
        assert response.intent == "seek"
        assert response.focus_target == "user"
        assert len(response.key_points) == 1
        assert len(response.constraints) == 1
        assert response.emotion["valence"] == 0.5
        assert response.relationship["bond"] == 0.7


class TestAPI:
    """Test API endpoints"""
    def test_health_endpoint(self):
        """Test /health endpoint returns required fields"""
        # Import the app directly to test the endpoint
        from emotiond.api import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert "ts" in data
        assert data["ok"] is True
        # Check that ts is a valid ISO timestamp
        assert isinstance(data["ts"], str)
        # Should be able to parse as datetime
        import datetime
        parsed_time = datetime.datetime.fromisoformat(data["ts"])
        assert isinstance(parsed_time, datetime.datetime)
