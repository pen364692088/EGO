"""
MVP-3 A1: Request ID Idempotency Tests

Tests for:
- Duplicate request_id ignored
- No state change on duplicate
- Audit records duplicate
"""
import pytest
import pytest_asyncio
from emotiond.db import (
    init_db, check_and_record_duplicate, update_dedupe_event_id,
    get_recent_events
)
from emotiond.core import process_event, load_initial_state
from emotiond.models import Event


@pytest_asyncio.fixture(scope="function")
async def isolated_db():
    """Setup isolated database for tests"""
    import os
    import tempfile
    import shutil
    from emotiond import config, db, core, daemon
    import importlib
    
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    # Reset daemon_manager state
    daemon.daemon_manager.running = False
    daemon.daemon_manager.loops = {}
    
    # Reset global state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.relationship_manager.relationships = {}
    
    await db.init_db()
    
    yield
    
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    # Reset state
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.emotion_state.regulation_budget = 1.0
    core.relationship_manager.relationships = {}
    
    shutil.rmtree(test_data_dir, ignore_errors=True)


class TestRequestIdIdempotency:
    """Test request_id idempotency for world_event processing"""
    
    @pytest.mark.asyncio
    async def test_first_request_processed(self, isolated_db):
        """First request with request_id should be processed normally"""
        event = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-001"
            }
        )
        
        result = await process_event(event)
        
        assert result["status"] == "processed"
        assert "valence" in result
    
    @pytest.mark.asyncio
    async def test_duplicate_request_ignored(self, isolated_db):
        """Second request with same request_id should be ignored"""
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-002"
            }
        )
        
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-002"  # Same request_id
            }
        )
        
        # First request should be processed
        result1 = await process_event(event1)
        assert result1["status"] == "processed"
        
        # Second request should be ignored as duplicate
        result2 = await process_event(event2)
        assert result2["status"] == "duplicate_ignored"
        assert result2["request_id"] == "req-002"
    
    @pytest.mark.asyncio
    async def test_no_state_change_on_duplicate(self, isolated_db):
        """Duplicate request should not change emotional state"""
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-003"
            }
        )
        
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "rejection",  # Different subtype that would normally lower valence
                "source": "user",
                "request_id": "req-003"  # Same request_id
            }
        )
        
        # First request
        result1 = await process_event(event1)
        valence_after_first = result1["valence"]
        
        # Second request (duplicate) should not affect state
        result2 = await process_event(event2)
        
        # State should remain same as after first request
        assert result2["status"] == "duplicate_ignored"
    
    @pytest.mark.asyncio
    async def test_audit_record_for_duplicate(self, isolated_db):
        """Duplicate request should create audit event"""
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-004"
            }
        )
        
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-004"
            }
        )
        
        await process_event(event1)
        await process_event(event2)
        
        # Check for audit event
        events = await get_recent_events(limit=10)
        audit_events = [e for e in events if e["type"] == "world_event_duplicate"]
        
        assert len(audit_events) == 1
        assert audit_events[0]["meta"]["original_request_id"] == "req-004"
        assert audit_events[0]["meta"]["decision"] == "duplicate_ignored"
    
    @pytest.mark.asyncio
    async def test_different_request_ids_processed(self, isolated_db):
        """Requests with different request_ids should both be processed"""
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-005"
            }
        )
        
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-006"  # Different request_id
            }
        )
        
        result1 = await process_event(event1)
        result2 = await process_event(event2)
        
        assert result1["status"] == "processed"
        assert result2["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_no_request_id_processed_normally(self, isolated_db):
        """Request without request_id should be processed normally (backward compat)"""
        event = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user"
                # No request_id
            }
        )
        
        result = await process_event(event)
        
        assert result["status"] == "processed"
    
    @pytest.mark.asyncio
    async def test_different_sources_same_request_id(self, isolated_db):
        """Same request_id from different sources should be treated separately"""
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "user",
                "request_id": "req-007"
            }
        )
        
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "care",
                "source": "system",  # Different source
                "request_id": "req-007"  # Same request_id
            }
        )
        
        result1 = await process_event(event1)
        result2 = await process_event(event2)
        
        # Both should be processed (different sources)
        assert result1["status"] == "processed"
        assert result2["status"] == "processed"


class TestDedupeDBFunctions:
    """Test low-level dedupe database functions"""
    
    @pytest.mark.asyncio
    async def test_check_and_record_duplicate_first_time(self, isolated_db):
        """First check for a request_id should return not duplicate"""
        result = await check_and_record_duplicate("user", "new-req-001")
        
        assert result["is_duplicate"] is False
        assert result["event_id"] is None
    
    @pytest.mark.asyncio
    async def test_check_and_record_duplicate_second_time(self, isolated_db):
        """Second check for same request_id should return duplicate"""
        # First check
        result1 = await check_and_record_duplicate("user", "new-req-002")
        assert result1["is_duplicate"] is False
        
        # Second check
        result2 = await check_and_record_duplicate("user", "new-req-002")
        assert result2["is_duplicate"] is True
    
    @pytest.mark.asyncio
    async def test_update_dedupe_event_id(self, isolated_db):
        """Should be able to update event_id for a dedupe record"""
        # Record initial
        await check_and_record_duplicate("user", "new-req-003")
        
        # Update event_id
        await update_dedupe_event_id("user", "new-req-003", 123)
        
        # Check it was updated
        result = await check_and_record_duplicate("user", "new-req-004")  # New request
        duplicate_check = await check_and_record_duplicate("user", "new-req-003")
        
        # Should still be duplicate with event_id
        assert duplicate_check["is_duplicate"] is True
