"""
Tests for the memory system and event storage
"""
import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
from emotiond.memory import MemorySystem
from emotiond.db import add_event, init_db, get_recent_events, get_events_by_target
from emotiond.models import Event
from emotiond.config import DB_PATH



@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Clean database before each test"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    await init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@pytest.mark.asyncio
async def test_memory_system_initialization():
    """Test memory system initializes correctly"""
    mem_system = MemorySystem()
    assert mem_system.memory_strength == 1.0
    assert mem_system.summarization_interval == 120
    assert isinstance(mem_system.target_memories, dict)
    assert mem_system.target_memories == {}


@pytest.mark.asyncio
async def test_calculate_memory_strength():
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


@pytest.mark.asyncio
async def test_add_event():
    """Test adding events to database"""
    await init_db()
    
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


@pytest.mark.asyncio
async def test_get_events_by_target():
    """Test retrieving events by target"""
    await init_db()
    
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


@pytest.mark.asyncio
async def test_memory_summarization_with_events():
    """Test memory summarization with actual events"""
    # Use a temporary database for this test
    original_db_path = DB_PATH
    
    try:
        # Create a temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            temp_db_path = tmp.name
        
        # Set the temporary database path
        import emotiond.config
        emotiond.config.DB_PATH = temp_db_path
        
        await init_db()
        
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
        
        # Force summarization by setting last_summarization far in the past
        mem_system.last_summarization = 0
        result = await mem_system.summarize_memories()
        
        assert result["status"] == "completed"
        assert result["total_events"] >= 4
        
        # Check that our specific targets are included
        assert "target1" in result["target_summaries"]
        assert "target2" in result["target_summaries"]
        
        # Check target1 summary
        target1_summary = result["target_summaries"]["target1"]
        assert target1_summary["event_count"] >= 3
        assert target1_summary["positive_count"] >= 1
        assert target1_summary["negative_count"] >= 1
        
        # Check target2 summary
        target2_summary = result["target_summaries"]["target2"]
        assert target2_summary["event_count"] >= 1
        assert target2_summary["positive_count"] >= 1
        assert target2_summary["negative_count"] == 0
        
    finally:
        # Restore original database path and clean up
        emotiond.config.DB_PATH = original_db_path
        if os.path.exists(temp_db_path):
            os.unlink(temp_db_path)