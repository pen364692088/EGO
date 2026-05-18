"""
MVP-3 A2: Time Passed Cumulative Rate Limiting Tests

Tests for:
- Multiple time_passed within window -> cumulative limit enforced
- Window expiry -> budget reset
- Audit shows clamp details
"""
import pytest
import pytest_asyncio
import asyncio
import time
from emotiond.db import (
    init_db, get_time_passed_window_sum, record_time_passed
)
from emotiond.core import process_event
from emotiond.models import Event
from emotiond.config import TIME_PASSED_WINDOW_SECONDS, TIME_PASSED_MAX_CUMULATIVE
from emotiond.security import validate_time_passed_cumulative


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


class TestCumulativeRateLimiting:
    """Test cumulative rate limiting for time_passed events"""
    
    @pytest.mark.asyncio
    async def test_single_time_passed_within_limit(self, isolated_db):
        """Single time_passed event within limit should be processed fully"""
        event = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 30
            }
        )
        
        result = await process_event(event)
        
        assert result["status"] == "processed"
        assert result["time_passed_audit"]["requested"] == 30
        assert result["time_passed_audit"]["clamped_to"] == 30
        assert result["time_passed_audit"]["reason"] == "within_budget"
    
    @pytest.mark.asyncio
    async def test_multiple_time_passed_cumulative(self, isolated_db):
        """Multiple time_passed events should accumulate within window"""
        # First event: 30 seconds
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 30
            }
        )
        result1 = await process_event(event1)
        assert result1["time_passed_audit"]["window_sum"] == 0
        
        # Second event: 30 seconds (total 60, at limit)
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 30
            }
        )
        result2 = await process_event(event2)
        assert result2["time_passed_audit"]["window_sum"] == 30
        assert result2["time_passed_audit"]["clamped_to"] == 30
        
        # Third event: should be clamped to 0 (budget exhausted)
        event3 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 30
            }
        )
        result3 = await process_event(event3)
        assert result3["time_passed_audit"]["window_sum"] == 60
        assert result3["time_passed_audit"]["clamped_to"] == 0
        assert result3["time_passed_audit"]["reason"] == "cumulative_budget_exhausted"
    
    @pytest.mark.asyncio
    async def test_window_expiry_resets_budget(self, isolated_db):
        """After window expires, budget should reset"""
        # Add a time_passed event
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 60
            }
        )
        await process_event(event1)
        
        # Manually insert an old record to simulate window expiry
        # (This tests the window logic directly)
        old_time = time.time() - 20  # 20 seconds ago, outside 10s window
        import aiosqlite
        from emotiond.db import get_db_path
        
        async with aiosqlite.connect(get_db_path()) as db:
            await db.execute(
                "INSERT INTO time_passed_tracking (source, seconds, created_at) VALUES (?, ?, datetime(?, 'unixepoch'))",
                ("user", 60, old_time)
            )
            await db.commit()
        
        # Check that old record is not counted
        window_sum = await get_time_passed_window_sum("user", 10.0)
        assert window_sum == 60  # Only the recent event should count
    
    @pytest.mark.asyncio
    async def test_audit_shows_clamp_details(self, isolated_db):
        """Audit info should include window_sum, requested, clamped_to, reason"""
        # First, fill up the budget
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 50
            }
        )
        await process_event(event1)
        
        # Now request more than remaining budget
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 20  # Only 10 remaining (60 - 50)
            }
        )
        result = await process_event(event2)
        
        audit = result["time_passed_audit"]
        assert audit["window_sum"] == 50
        assert audit["requested"] == 20
        assert audit["clamped_to"] == 10
        assert audit["reason"] == "clamped_to_remaining_budget"
    
    @pytest.mark.asyncio
    async def test_different_sources_independent(self, isolated_db):
        """Different sources should have independent budgets"""
        # User source: 60 seconds
        event1 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "user",
                "seconds": 60
            }
        )
        await process_event(event1)
        
        # System source: should have its own budget
        event2 = Event(
            type="world_event",
            actor="test_actor",
            target="test_target",
            meta={
                "subtype": "time_passed",
                "source": "system",
                "seconds": 30
            }
        )
        result = await process_event(event2)
        
        # System should be allowed (independent budget)
        assert result["time_passed_audit"]["window_sum"] == 0  # Fresh budget for system
        assert result["time_passed_audit"]["clamped_to"] == 30


class TestValidateTimePassedCumulative:
    """Test the validate_time_passed_cumulative function directly"""
    
    def test_within_budget(self):
        """Seconds within budget should be allowed fully"""
        clamped, audit = validate_time_passed_cumulative(30, 20, 60)
        
        assert clamped == 30
        assert audit["reason"] == "within_budget"
    
    def test_exceeds_budget(self):
        """Seconds exceeding remaining budget should be clamped"""
        clamped, audit = validate_time_passed_cumulative(30, 50, 60)
        
        assert clamped == 10  # 60 - 50 = 10 remaining
        assert audit["reason"] == "clamped_to_remaining_budget"
    
    def test_budget_exhausted(self):
        """When budget exhausted, should return 0"""
        clamped, audit = validate_time_passed_cumulative(30, 60, 60)
        
        assert clamped == 0
        assert audit["reason"] == "cumulative_budget_exhausted"
    
    def test_budget_negative(self):
        """When window_sum exceeds max, should return 0"""
        clamped, audit = validate_time_passed_cumulative(30, 70, 60)
        
        assert clamped == 0
        assert audit["reason"] == "cumulative_budget_exhausted"


class TestTimePassedDBFunctions:
    """Test low-level time_passed database functions"""
    
    @pytest.mark.asyncio
    async def test_record_and_get_window_sum(self, isolated_db):
        """Should record and retrieve time_passed sum correctly"""
        await record_time_passed("user", 30)
        await record_time_passed("user", 20)
        
        window_sum = await get_time_passed_window_sum("user", 10.0)
        
        assert window_sum == 50
    
    @pytest.mark.asyncio
    async def test_window_sum_empty(self, isolated_db):
        """Empty source should return 0"""
        window_sum = await get_time_passed_window_sum("nonexistent", 10.0)
        
        assert window_sum == 0
    
    @pytest.mark.asyncio
    async def test_different_sources_separate(self, isolated_db):
        """Different sources should have separate tracking"""
        await record_time_passed("user", 30)
        await record_time_passed("system", 20)
        
        user_sum = await get_time_passed_window_sum("user", 10.0)
        system_sum = await get_time_passed_window_sum("system", 10.0)
        
        assert user_sum == 30
        assert system_sum == 20
