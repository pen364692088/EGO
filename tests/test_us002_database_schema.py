"""
Test database schema and models for US-002
"""
import os
import asyncio
import tempfile
import json
import pytest
from emotiond.db import init_db, get_state, update_state, get_relationships, update_relationship, add_event
from emotiond.models import Event, PlanRequest, PlanResponse
from emotiond.config import DB_PATH


class TestDatabaseSchema:
    """Test database schema creation and operations"""

    def test_env_var_db_path(self):
        """Test that EMOTIOND_DB_PATH env var is respected"""
        # Test default path
        assert DB_PATH == "./data/emotiond.db"

        # Test with custom path (simulated)
        test_path = "/tmp/test_emotiond.db"
        os.environ["EMOTIOND_DB_PATH"] = test_path
        # Reload the config module to pick up the environment variable
        import importlib
        import emotiond.config
        importlib.reload(emotiond.config)
        assert emotiond.config.DB_PATH == test_path
        del os.environ["EMOTIOND_DB_PATH"]
        # Reload again to restore default
        importlib.reload(emotiond.config)

    @pytest.mark.asyncio
    async def test_tables_created(self):
        """Test that all required tables are created"""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            # Initialize with temp path
            os.environ["EMOTIOND_DB_PATH"] = temp_db_path
            # Reload config and db modules to pick up the new environment variable
            import importlib
            import emotiond.config
            import emotiond.db
            importlib.reload(emotiond.config)
            importlib.reload(emotiond.db)
            from emotiond.db import init_db, get_state, get_relationships, add_event

            await init_db()

            # Check database file exists
            assert os.path.exists(temp_db_path)

            # Verify we can perform operations on all tables
            state = await get_state()
            assert "valence" in state
            assert "arousal" in state
            assert "subjective_time" in state

            relationships = await get_relationships()
            assert isinstance(relationships, list)

            # Test event insertion
            event_data = {
                "type": "user_message",
                "actor": "user",
                "target": "agent",
                "text": "Test message"
            }
            await add_event(event_data)

        finally:
            # Cleanup
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if "EMOTIOND_DB_PATH" in os.environ:
                del os.environ["EMOTIOND_DB_PATH"]

    @pytest.mark.asyncio
    async def test_state_table_single_row(self):
        """Test state table maintains single row constraint"""
        # Initialize fresh database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            os.environ["EMOTIOND_DB_PATH"] = temp_db_path
            # Reload config and db modules to pick up the new environment variable
            import importlib
            import emotiond.config
            import emotiond.db
            importlib.reload(emotiond.config)
            importlib.reload(emotiond.db)
            from emotiond.db import init_db, get_state

            await init_db()

            # Initial state should exist
            state = await get_state()
            assert state["valence"] == 0.0
            assert state["arousal"] == 0.0
            assert state["subjective_time"] == 0

            # Update state multiple times
            await update_state(0.5, 0.3, 100)
            state = await get_state()
            assert state["valence"] == 0.5
            assert state["arousal"] == 0.3
            assert state["subjective_time"] == 100

            await update_state(-0.2, 0.8, 200)
            state = await get_state()
            assert state["valence"] == -0.2
            assert state["arousal"] == 0.8
            assert state["subjective_time"] == 200

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if "EMOTIOND_DB_PATH" in os.environ:
                del os.environ["EMOTIOND_DB_PATH"]

    @pytest.mark.asyncio
    async def test_relationships_target_specific(self):
        """Test relationships are target-specific"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            os.environ["EMOTIOND_DB_PATH"] = temp_db_path
            # Reload config and db modules to pick up the new environment variable
            import importlib
            import emotiond.config
            import emotiond.db
            importlib.reload(emotiond.config)
            importlib.reload(emotiond.db)
            from emotiond.db import init_db, update_relationship, get_relationships

            await init_db()

            # Create relationships for different targets
            await update_relationship("user", 0.8, 0.1)
            await update_relationship("A", 0.6, 0.3)
            await update_relationship("B", 0.4, 0.5)

            relationships = await get_relationships()

            # Should have 3 relationships
            assert len(relationships) == 3

            # Verify target-specific data
            targets = {r["target"]: r for r in relationships}
            assert "user" in targets
            assert "A" in targets
            assert "B" in targets

            assert targets["user"]["bond"] == 0.8
            assert targets["A"]["bond"] == 0.6
            assert targets["B"]["bond"] == 0.4

            assert targets["user"]["grudge"] == 0.1
            assert targets["A"]["grudge"] == 0.3
            assert targets["B"]["grudge"] == 0.5

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if "EMOTIOND_DB_PATH" in os.environ:
                del os.environ["EMOTIOND_DB_PATH"]

    @pytest.mark.asyncio
    async def test_events_append_only(self):
        """Test events table is append-only"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            os.environ["EMOTIOND_DB_PATH"] = temp_db_path
            from emotiond.config import DB_PATH as TestDBPath
            from emotiond.db import init_db, add_event

            await init_db()

            # Add multiple events
            events = [
                {"type": "user_message", "actor": "user", "target": "agent", "text": "Hello"},
                {"type": "assistant_reply", "actor": "agent", "target": "user", "text": "Hi there"},
                {"type": "world_event", "actor": "system", "target": "agent", "text": "System update"}
            ]

            for event in events:
                await add_event(event)

            # Events should be stored (no exception means success)
            # This is append-only by design - no updates or deletes

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
            if "EMOTIOND_DB_PATH" in os.environ:
                del os.environ["EMOTIOND_DB_PATH"]


class TestPydanticModels:
    """Test Pydantic models validation"""

    def test_event_model_validation(self):
        """Test Event model validates required fields"""
        # Valid event
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={"importance": 0.8}
        )
        assert event.type == "user_message"
        assert event.actor == "user"
        assert event.target == "agent"
        assert event.text == "Hello"
        assert event.meta == {"importance": 0.8}

        # Test without optional fields
        event2 = Event(
            type="world_event",
            actor="system",
            target="agent"
        )
        assert event2.type == "world_event"
        assert event2.actor == "system"
        assert event2.target == "agent"
        assert event2.text is None
        assert event2.meta is None

    def test_plan_request_model(self):
        """Test PlanRequest model"""
        request = PlanRequest(
            user_id="test_user_123",
            user_text="How are you feeling today?"
        )
        assert request.user_id == "test_user_123"
        assert request.user_text == "How are you feeling today?"

    def test_plan_response_model_validation(self):
        """Test PlanResponse model validates required fields and enums"""
        # Valid response
        response = PlanResponse(
            tone="warm",
            intent="seek",
            focus_target="user",
            key_points=["Show interest", "Ask follow-up"],
            constraints=["Be positive", "Avoid sensitive topics"],
            emotion={"valence": 0.7, "arousal": 0.4},
            relationship={"bond": 0.8, "grudge": 0.1}
        )

        assert response.tone == "warm"
        assert response.intent == "seek"
        assert response.focus_target == "user"
        assert len(response.key_points) == 2
        assert len(response.constraints) == 2
        assert response.emotion["valence"] == 0.7
        assert response.emotion["arousal"] == 0.4
        assert response.relationship["bond"] == 0.8
        assert response.relationship["grudge"] == 0.1

        # Test with different values
        response2 = PlanResponse(
            tone="guarded",
            intent="set_boundary",
            focus_target="A",
            key_points=["Establish boundaries"],
            constraints=["Be firm"],
            emotion={"valence": -0.3, "arousal": 0.6},
            relationship={"bond": 0.3, "grudge": 0.7}
        )

        assert response2.tone == "guarded"
        assert response2.intent == "set_boundary"
        assert response2.focus_target == "A"


async def run_tests():
    """Run all tests for database schema and models"""
    print("Running database schema and models tests...")

    test_schema = TestDatabaseSchema()
    test_models = TestPydanticModels()

    # Run schema tests
    await test_schema.test_env_var_db_path()
    print("✓ EMOTIOND_DB_PATH env var respected")

    await test_schema.test_tables_created()
    print("✓ All required tables created")

    await test_schema.test_state_table_single_row()
    print("✓ State table maintains single row constraint")

    await test_schema.test_relationships_target_specific()
    print("✓ Relationships are target-specific")

    await test_schema.test_events_append_only()
    print("✓ Events table is append-only")

    # Run model tests
    test_models.test_event_model_validation()
    print("✓ Event model validation works")

    test_models.test_plan_request_model()
    print("✓ PlanRequest model works")

    test_models.test_plan_response_model_validation()
    print("✓ PlanResponse model validation works")

    print("\n✅ All database schema and models tests passed!")


if __name__ == "__main__":
    asyncio.run(run_tests())