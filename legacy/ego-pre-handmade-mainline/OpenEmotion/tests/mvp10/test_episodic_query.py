"""MVP-10 T18: Tests for Episodic Memory query functionality."""
import pytest
import pytest_asyncio
import tempfile
import os
import time
import asyncio

from emotiond.memory.episodic import (
    EpisodicEvent,
    EpisodicMemory,
    EventType,
    FailureType,
    get_episodic_memory,
)


@pytest_asyncio.fixture
async def episodic_memory():
    """Create an isolated episodic memory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="episodic_test_")
    db_path = os.path.join(temp_dir, "test_episodic.db")
    
    memory = EpisodicMemory(db_path=db_path)
    await memory.init_db()
    
    yield memory
    
    # Cleanup
    await memory.clear()
    try:
        os.remove(db_path)
    except:
        pass
    os.rmdir(temp_dir)


class TestEpisodicEvent:
    """Tests for EpisodicEvent dataclass."""
    
    def test_create_event(self):
        """Test creating a basic event."""
        event = EpisodicEvent(
            event_id="evt_001",
            timestamp=time.time(),
            event_type="goal_set",
            context={"goal": "fix bug"},
        )
        
        assert event.event_id == "evt_001"
        assert event.event_type == "goal_set"
        assert event.context["goal"] == "fix bug"
        assert event.outcome == "neutral"
        assert event.goal_id is None
    
    def test_event_to_dict(self):
        """Test serializing event to dictionary."""
        event = EpisodicEvent(
            event_id="evt_002",
            timestamp=1000.0,
            event_type="action_taken",
            context={"action": "deploy"},
            outcome="success",
            goal_id="goal_123",
            tags=["deployment", "production"],
        )
        
        data = event.to_dict()
        
        assert data["event_id"] == "evt_002"
        assert data["timestamp"] == 1000.0
        assert data["event_type"] == "action_taken"
        assert data["outcome"] == "success"
        assert data["goal_id"] == "goal_123"
        assert "deployment" in data["tags"]
    
    def test_event_from_dict(self):
        """Test deserializing event from dictionary."""
        data = {
            "event_id": "evt_003",
            "timestamp": 2000.0,
            "event_type": "failure_occurred",
            "context": {"error": "timeout"},
            "outcome": "failure",
            "goal_id": "goal_456",
            "failure_type": "timeout",
            "tags": ["critical"],
        }
        
        event = EpisodicEvent.from_dict(data)
        
        assert event.event_id == "evt_003"
        assert event.event_type == "failure_occurred"
        assert event.outcome == "failure"
        assert event.failure_type == "timeout"
    
    def test_compute_hash(self):
        """Test hash computation is deterministic."""
        event1 = EpisodicEvent(
            event_id="evt_004",
            timestamp=3000.0,
            event_type="decision_made",
            outcome="success",
        )
        
        event2 = EpisodicEvent(
            event_id="evt_004",
            timestamp=3000.0,
            event_type="decision_made",
            outcome="success",
        )
        
        # Same data should produce same hash
        assert event1.compute_hash() == event2.compute_hash()
        
        # Different data should produce different hash
        event3 = EpisodicEvent(
            event_id="evt_004",
            timestamp=3000.0,
            event_type="decision_made",
            outcome="failure",
        )
        assert event1.compute_hash() != event3.compute_hash()


class TestEpisodicMemoryStore:
    """Tests for storing events in EpisodicMemory."""
    
    @pytest.mark.asyncio
    async def test_store_basic_event(self, episodic_memory):
        """Test storing a basic event."""
        event = await episodic_memory.store(
            event_type="goal_set",
            context={"goal": "complete task"},
        )
        
        assert event.event_id.startswith("evt_")
        assert event.event_type == "goal_set"
        assert event.context["goal"] == "complete task"
        assert event.timestamp > 0
    
    @pytest.mark.asyncio
    async def test_store_event_with_goal_id(self, episodic_memory):
        """Test storing event with goal ID."""
        event = await episodic_memory.store(
            event_type="goal_progress",
            context={"progress": 50},
            goal_id="goal_001",
            outcome="partial",
        )
        
        assert event.goal_id == "goal_001"
        assert event.outcome == "partial"
    
    @pytest.mark.asyncio
    async def test_store_event_with_failure(self, episodic_memory):
        """Test storing failure event."""
        event = await episodic_memory.store(
            event_type="failure_occurred",
            context={"error": "connection refused"},
            outcome="failure",
            failure_type="resource_unavailable",
            evidence={"error_code": "ECONNREFUSED"},
        )
        
        assert event.outcome == "failure"
        assert event.failure_type == "resource_unavailable"
        assert event.evidence["error_code"] == "ECONNREFUSED"
    
    @pytest.mark.asyncio
    async def test_store_event_chain(self, episodic_memory):
        """Test storing events with parent-child relationship."""
        parent = await episodic_memory.store(
            event_type="goal_set",
            context={"goal": "deploy service"},
            goal_id="goal_chain",
        )
        
        child = await episodic_memory.store(
            event_type="action_taken",
            context={"action": "build"},
            goal_id="goal_chain",
            parent_event_id=parent.event_id,
        )
        
        assert child.parent_event_id == parent.event_id


class TestEpisodicMemoryRetrieve:
    """Tests for retrieving events from EpisodicMemory."""
    
    @pytest.mark.asyncio
    async def test_retrieve_by_id(self, episodic_memory):
        """Test retrieving event by ID."""
        stored = await episodic_memory.store(
            event_type="decision_made",
            context={"decision": "use approach A"},
        )
        
        retrieved = await episodic_memory.retrieve(stored.event_id)
        
        assert retrieved is not None
        assert retrieved.event_id == stored.event_id
        assert retrieved.context["decision"] == "use approach A"
    
    @pytest.mark.asyncio
    async def test_retrieve_nonexistent(self, episodic_memory):
        """Test retrieving nonexistent event."""
        result = await episodic_memory.retrieve("nonexistent_id")
        assert result is None


class TestEpisodicMemoryQueryByGoal:
    """Tests for querying events by goal ID."""
    
    @pytest.mark.asyncio
    async def test_query_by_goal_id(self, episodic_memory):
        """Test querying events by goal ID."""
        # Store events for different goals
        await episodic_memory.store(
            event_type="goal_set",
            context={"goal": "goal A"},
            goal_id="goal_a",
        )
        await episodic_memory.store(
            event_type="goal_progress",
            context={"progress": 50},
            goal_id="goal_a",
        )
        await episodic_memory.store(
            event_type="goal_set",
            context={"goal": "goal B"},
            goal_id="goal_b",
        )
        
        # Query for goal_a
        events = await episodic_memory.query_by_goal_id("goal_a")
        
        assert len(events) == 2
        for e in events:
            assert e.goal_id == "goal_a"
    
    @pytest.mark.asyncio
    async def test_query_by_goal_id_order(self, episodic_memory):
        """Test query order (descending by default)."""
        base_time = time.time()
        
        await episodic_memory.store(
            event_type="goal_set",
            context={"order": 1},
            goal_id="goal_order",
            timestamp=base_time - 100,
        )
        await episodic_memory.store(
            event_type="goal_progress",
            context={"order": 2},
            goal_id="goal_order",
            timestamp=base_time,
        )
        await episodic_memory.store(
            event_type="goal_achieved",
            context={"order": 3},
            goal_id="goal_order",
            timestamp=base_time + 100,
        )
        
        events = await episodic_memory.query_by_goal_id("goal_order", order_desc=True)
        
        # Should be in descending order (newest first)
        assert events[0].timestamp > events[1].timestamp > events[2].timestamp
    
    @pytest.mark.asyncio
    async def test_query_by_goal_id_empty(self, episodic_memory):
        """Test querying for nonexistent goal."""
        events = await episodic_memory.query_by_goal_id("nonexistent_goal")
        assert len(events) == 0


class TestEpisodicMemoryQueryByFailure:
    """Tests for querying events by failure type."""
    
    @pytest.mark.asyncio
    async def test_query_by_failure_type(self, episodic_memory):
        """Test querying events by failure type."""
        await episodic_memory.store(
            event_type="failure_occurred",
            context={"error": "timeout 1"},
            outcome="failure",
            failure_type="timeout",
        )
        await episodic_memory.store(
            event_type="failure_occurred",
            context={"error": "timeout 2"},
            outcome="failure",
            failure_type="timeout",
        )
        await episodic_memory.store(
            event_type="failure_occurred",
            context={"error": "other"},
            outcome="failure",
            failure_type="execution_error",
        )
        
        events = await episodic_memory.query_by_failure_type("timeout")
        
        assert len(events) == 2
        for e in events:
            assert e.failure_type == "timeout"
    
    @pytest.mark.asyncio
    async def test_query_by_failure_type_empty(self, episodic_memory):
        """Test querying for nonexistent failure type."""
        events = await episodic_memory.query_by_failure_type("nonexistent_failure")
        assert len(events) == 0


class TestEpisodicMemoryQueryByTimeRange:
    """Tests for querying events by time range."""
    
    @pytest.mark.asyncio
    async def test_query_by_time_range(self, episodic_memory):
        """Test querying events within time range."""
        base_time = time.time()
        
        await episodic_memory.store(
            event_type="event_before",
            context={"when": "before"},
            timestamp=base_time - 1000,
        )
        await episodic_memory.store(
            event_type="event_in_range",
            context={"when": "in"},
            timestamp=base_time,
        )
        await episodic_memory.store(
            event_type="event_after",
            context={"when": "after"},
            timestamp=base_time + 1000,
        )
        
        events = await episodic_memory.query_by_time_range(
            start_time=base_time - 100,
            end_time=base_time + 100,
        )
        
        assert len(events) == 1
        assert events[0].context["when"] == "in"
    
    @pytest.mark.asyncio
    async def test_query_by_time_range_with_type(self, episodic_memory):
        """Test querying with both time range and event type."""
        base_time = time.time()
        
        await episodic_memory.store(
            event_type="goal_set",
            context={"id": 1},
            timestamp=base_time,
        )
        await episodic_memory.store(
            event_type="action_taken",
            context={"id": 2},
            timestamp=base_time,
        )
        
        events = await episodic_memory.query_by_time_range(
            start_time=base_time - 10,
            end_time=base_time + 10,
            event_type="action_taken",
        )
        
        assert len(events) == 1
        assert events[0].event_type == "action_taken"


class TestEpisodicMemoryEventChain:
    """Tests for event chain retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_event_chain(self, episodic_memory):
        """Test getting event chain."""
        # Create chain: event1 -> event2 -> event3
        event1 = await episodic_memory.store(
            event_type="goal_set",
            context={"step": 1},
            goal_id="chain_goal",
        )
        event2 = await episodic_memory.store(
            event_type="action_taken",
            context={"step": 2},
            goal_id="chain_goal",
            parent_event_id=event1.event_id,
        )
        event3 = await episodic_memory.store(
            event_type="goal_achieved",
            context={"step": 3},
            goal_id="chain_goal",
            parent_event_id=event2.event_id,
        )
        
        chain = await episodic_memory.get_event_chain(event3.event_id)
        
        assert len(chain) == 3
        # Should be in root-to-leaf order
        assert chain[0].event_id == event1.event_id
        assert chain[1].event_id == event2.event_id
        assert chain[2].event_id == event3.event_id
    
    @pytest.mark.asyncio
    async def test_get_children(self, episodic_memory):
        """Test getting child events."""
        parent = await episodic_memory.store(
            event_type="goal_set",
            context={"parent": True},
        )
        
        child1 = await episodic_memory.store(
            event_type="action_taken",
            context={"child": 1},
            parent_event_id=parent.event_id,
        )
        child2 = await episodic_memory.store(
            event_type="action_taken",
            context={"child": 2},
            parent_event_id=parent.event_id,
        )
        
        children = await episodic_memory.get_children(parent.event_id)
        
        assert len(children) == 2
        child_ids = [c.event_id for c in children]
        assert child1.event_id in child_ids
        assert child2.event_id in child_ids


class TestEpisodicMemoryLedger:
    """Tests for ledger integration."""
    
    @pytest.mark.asyncio
    async def test_log_to_ledger(self, episodic_memory):
        """Test logging event to ledger."""
        event = await episodic_memory.store(
            event_type="goal_set",
            context={"goal": "test ledger"},
        )
        
        temp_dir = tempfile.mkdtemp(prefix="ledger_test_")
        ledger_path = os.path.join(temp_dir, "test_ledger.jsonl")
        
        entry_id = await episodic_memory.log_to_ledger(event, ledger_path)
        
        assert entry_id == event.event_id
        
        # Verify ledger file was created and contains entry
        with open(ledger_path, "r") as f:
            content = f.read()
            assert event.event_id in content
        
        # Cleanup
        os.remove(ledger_path)
        os.rmdir(temp_dir)


class TestEpisodicMemoryStatistics:
    """Tests for memory statistics."""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, episodic_memory):
        """Test getting memory statistics."""
        await episodic_memory.store(
            event_type="goal_set",
            context={},
            outcome="neutral",
        )
        await episodic_memory.store(
            event_type="action_taken",
            context={},
            outcome="success",
        )
        await episodic_memory.store(
            event_type="failure_occurred",
            context={},
            outcome="failure",
            failure_type="timeout",
        )
        
        stats = await episodic_memory.get_statistics()
        
        assert stats["total_events"] == 3
        assert "goal_set" in stats["by_type"]
        assert stats["by_outcome"]["success"] == 1
        assert stats["total_failures"] == 1


class TestEpisodicMemoryClear:
    """Tests for clearing memory."""
    
    @pytest.mark.asyncio
    async def test_clear(self, episodic_memory):
        """Test clearing all events."""
        await episodic_memory.store(
            event_type="goal_set",
            context={},
        )
        await episodic_memory.store(
            event_type="action_taken",
            context={},
        )
        
        stats = await episodic_memory.get_statistics()
        assert stats["total_events"] == 2
        
        await episodic_memory.clear()
        
        stats = await episodic_memory.get_statistics()
        assert stats["total_events"] == 0
