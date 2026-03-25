""" Tests for the memory system and event storage """
import pytest
import pytest_asyncio
import asyncio
import time
from emotiond.memory import MemorySystem, memory_system
from emotiond.db import add_event, init_db, get_recent_events, get_events_by_target
import os
from emotiond.models import Event
from emotiond.config import DB_PATH


@pytest.mark.asyncio
class TestMemorySystem:
    """Test memory system functionality"""
    @pytest_asyncio.fixture(autouse=True, scope="function")
    async def setup_db(self):
        """Initialize database for testing - runs before each test"""
        # Clean up existing database for test isolation
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        await init_db()
        yield
        # Clean up after tests
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    async def test_memory_system_initialization(self):
        """Test memory system initializes correctly"""
        mem_system = MemorySystem()
        assert mem_system.memory_strength == 1.0
        assert mem_system.summarization_interval == 120
        assert isinstance(mem_system.target_memories, dict)
        assert mem_system.target_memories == {}

    async def test_calculate_memory_strength(self):
        """Test memory strength calculation"""
        mem_system = MemorySystem()
        # Test with no prediction error and low arousal
        strength = mem_system.calculate_memory_strength(0.0, 0.3)
        assert abs(strength - 1.09) < 0.01  # 1.0 + 0.0*0.5 + 0.3*0.3 = 1.09
        # Test with prediction error
        strength = mem_system.calculate_memory_strength(0.5, 0.3)
        assert abs(strength - 1.34) < 0.01  # 1.0 + 0.5*0.5 + 0.3*0.3 = 1.34
        # Test with high arousal
        strength = mem_system.calculate_memory_strength(0.0, 0.8)
        assert abs(strength - 1.24) < 0.01  # 1.0 + 0.0*0.5 + 0.8*0.3 = 1.24
        # Test with both prediction error and high arousal
        strength = mem_system.calculate_memory_strength(0.5, 0.8)
        assert abs(strength - 1.49) < 0.01  # 1.0 + 0.5*0.5 + 0.8*0.3 = 1.49
        # Test maximum strength
        strength = mem_system.calculate_memory_strength(3.0, 1.0)
        assert abs(strength - 2.8) < 0.01  # 1.0 + 3.0*0.5 + 1.0*0.3 = 2.8

    async def test_get_memory_impact_on_relationship_no_memory(self):
        """Test memory impact when no memory exists for target"""
        mem_system = MemorySystem()
        impact = mem_system.get_memory_impact_on_relationship("unknown_target")
        assert impact["bond_modifier"] == 0.0
        assert impact["grudge_modifier"] == 0.0

    async def test_get_target_memory_summary_no_events(self):
        """Test getting memory summary for target with no events"""
        mem_system = MemorySystem()
        summary = await mem_system.get_target_memory_summary("new_target")
        assert summary["event_count"] == 0
        assert summary["positive_count"] == 0
        assert summary["negative_count"] == 0

    async def test_memory_summarization_with_events(self):
        """Test memory summarization with actual events"""
        # Add test events
        events = [
            Event(type="user_message", actor="user1", target="target1", text="hello, this is great!"),
            Event(type="user_message", actor="user1", target="target1", text="I hate this!"),
            Event(type="assistant_reply", actor="assistant", target="target1", text="I understand"),
            Event(type="user_message", actor="user2", target="target2", text="good job!"),
        ]
        for event in events:
            await add_event(event.model_dump())

        # Test memory summarization
        mem_system = MemorySystem()
        result = await mem_system.summarize_memories()
        assert result["status"] == "completed"
        assert len(result["target_summaries"]) >= 2  # At least target1 and target2
        assert result["total_events"] >= 4

        # Check target1 summary
        if "target1" in result["target_summaries"]:
            target1_summary = result["target_summaries"]["target1"]
            assert target1_summary["event_count"] >= 3
            assert target1_summary["positive_count"] >= 1
            assert target1_summary["negative_count"] >= 1

        # Check target2 summary
        if "target2" in result["target_summaries"]:
            target2_summary = result["target_summaries"]["target2"]
            assert target2_summary["event_count"] >= 1
            assert target2_summary["positive_count"] >= 1
            assert target2_summary["negative_count"] == 0

    async def test_get_target_memory_summary_with_events(self):
        """Test getting memory summary for specific target with events"""
        # Add test events for target
        events = [
            Event(type="user_message", actor="user1", target="test_target", text="this is wonderful!"),
            Event(type="user_message", actor="user1", target="test_target", text="terrible experience"),
            Event(type="assistant_reply", actor="assistant", target="test_target", text="I see"),
        ]
        for event in events:
            await add_event(event.model_dump())

        mem_system = MemorySystem()
        summary = await mem_system.get_target_memory_summary("test_target")
        assert summary["event_count"] >= 3
        assert summary["positive_count"] >= 1
        assert summary["negative_count"] >= 1
        assert summary["recent_interaction"] == "assistant_reply"

    async def test_memory_impact_on_relationships(self):
        """Test how memory affects relationship updates"""
        # Add positive events for target
        positive_events = [
            Event(type="user_message", actor="user1", target="positive_target", text="great work!"),
            Event(type="user_message", actor="user1", target="positive_target", text="amazing job!"),
            Event(type="user_message", actor="user1", target="positive_target", text="thank you so much!"),
        ]
        for event in positive_events:
            await add_event(event.model_dump())

        # Add negative events for target
        negative_events = [
            Event(type="user_message", actor="user1", target="negative_target", text="this is awful!"),
            Event(type="user_message", actor="user1", target="negative_target", text="terrible service!"),
        ]
        for event in negative_events:
            await add_event(event.model_dump())

        mem_system = MemorySystem()
        await mem_system.summarize_memories()

        # Test positive target impact
        positive_impact = mem_system.get_memory_impact_on_relationship("positive_target")
        assert positive_impact["bond_modifier"] > 0
        assert positive_impact["grudge_modifier"] < 0

        # Test negative target impact
        negative_impact = mem_system.get_memory_impact_on_relationship("negative_target")
        assert negative_impact["bond_modifier"] < 0
        assert negative_impact["grudge_modifier"] > 0

    async def test_memory_summarization_timing(self):
        """Test memory summarization timing logic"""
        mem_system = MemorySystem()
        # First summarization should run immediately (interval check uses 0 initialization)
        result = await mem_system.summarize_memories()
        assert result["status"] == "completed"
        
        # Second call should be "not_due" (within interval)
        result2 = await mem_system.summarize_memories()
        assert result2["status"] == "not_due"

    async def test_global_memory_system(self):
        """Test global memory system instance"""
        # Ensure global instance exists
        assert isinstance(memory_system, MemorySystem)
        # Test global instance functionality
        strength = memory_system.calculate_memory_strength(0.2, 0.5)
        assert strength > 1.0


@pytest.mark.asyncio
class TestEventStorage:
    """Test event storage and retrieval functionality"""
    @pytest_asyncio.fixture(autouse=True, scope="function")
    async def setup_db(self):
        """Initialize database for testing - runs before each test"""
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        await init_db()
        yield
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    async def test_add_event(self):
        """Test adding events to database"""
        event = Event(
            type="user_message",
            actor="test_user",
            target="test_target",
            text="Hello world!",
            meta={"test": "value"}
        )
        await add_event(event.model_dump())
        # Verify event was stored
        recent_events = await get_recent_events(limit=10)
        assert len(recent_events) >= 1
        stored_event = recent_events[0]
        assert stored_event["type"] == "user_message"
        assert stored_event["actor"] == "test_user"
        assert stored_event["target"] == "test_target"
        assert stored_event["text"] == "Hello world!"
        assert stored_event["meta"]["test"] == "value"

    async def test_get_events_by_target(self):
        """Test retrieving events by target"""
        # Add events for different targets
        events = [
            Event(type="user_message", actor="user1", target="target_a", text="message for target a"),
            Event(type="user_message", actor="user1", target="target_b", text="message for target b"),
            Event(type="user_message", actor="user1", target="target_a", text="another message for target a"),
        ]
        for event in events:
            await add_event(event.model_dump())

        # Get events for target_a
        target_a_events = await get_events_by_target("target_a")
        assert len(target_a_events) >= 2
        for event in target_a_events:
            assert event["target"] == "target_a"

        # Get events for target_b
        target_b_events = await get_events_by_target("target_b")
        assert len(target_b_events) >= 1
        for event in target_b_events:
            assert event["target"] == "target_b"

    async def test_event_order(self):
        """Test that events are returned in correct order"""
        # Add events with slight delay
        events = [
            Event(type="user_message", actor="user1", target="test_target", text="first message"),
            Event(type="user_message", actor="user1", target="test_target", text="second message"),
            Event(type="user_message", actor="user1", target="test_target", text="third message"),
        ]
        for event in events:
            await add_event(event.model_dump())
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get recent events - should be in reverse chronological order
        recent_events = await get_recent_events(limit=10)
        # Check that most recent event is first
        assert recent_events[0]["text"] == "third message"
        assert recent_events[1]["text"] == "second message"
        assert recent_events[2]["text"] == "first message"

    async def test_event_meta_storage(self):
        """Test that event metadata is properly stored and retrieved"""
        complex_meta = {
            "emotion": "positive",
            "intensity": 0.8,
            "tags": ["important", "feedback"],
            "nested": {"key": "value"}
        }
        event = Event(
            type="world_event",
            actor="system",
            target="all",
            text="Complex event with metadata",
            meta=complex_meta
        )
        await add_event(event.model_dump())
        # Verify metadata was stored and retrieved correctly
        recent_events = await get_recent_events(limit=10)
        stored_event = recent_events[0]
        assert stored_event["meta"]["emotion"] == "positive"
        assert stored_event["meta"]["intensity"] == 0.8
        assert stored_event["meta"]["tags"] == ["important", "feedback"]
        assert stored_event["meta"]["nested"]["key"] == "value"
