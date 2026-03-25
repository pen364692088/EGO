"""
Simple tests for the memory system and event storage
"""
import pytest
import pytest_asyncio
import os
import asyncio
import tempfile
import shutil
from emotiond.memory import MemorySystem
from emotiond.db import add_event, init_db, get_recent_events, get_events_by_target
from emotiond.models import Event
from emotiond import config, db, core


def reset_all_global_state():
    """Reset all global state to ensure test isolation"""
    core.emotion_state.valence = 0.0
    core.emotion_state.arousal = 0.3
    core.emotion_state.subjective_time = 0
    core.emotion_state.prediction_error = 0.0
    core.relationship_manager.relationships = {}


@pytest_asyncio.fixture(scope="function")
async def isolated_test_db():
    """Setup isolated database for each test with proper cleanup"""
    # Reset global state FIRST
    reset_all_global_state()
    
    # Create temp directory for this test
    test_data_dir = tempfile.mkdtemp(prefix="emotiond_test_")
    
    # Override DB_PATH for this test
    original_db_path = os.environ.get("EMOTIOND_DB_PATH")
    os.environ["EMOTIOND_DB_PATH"] = os.path.join(test_data_dir, "test_emotiond.db")
    
    # Reimport config to pick up new DB path
    import importlib
    importlib.reload(config)
    importlib.reload(db)
    
    # Reset again after reload
    reset_all_global_state()
    
    # Initialize database
    await db.init_db()
    
    yield
    
    # Cleanup
    if original_db_path:
        os.environ["EMOTIOND_DB_PATH"] = original_db_path
    else:
        os.environ.pop("EMOTIOND_DB_PATH", None)
    
    # Remove temp directory
    shutil.rmtree(test_data_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_memory_system_initialization(isolated_test_db):
    """Test memory system initializes correctly"""
    mem_system = MemorySystem()
    assert mem_system.memory_strength == 1.0
    assert mem_system.summarization_interval == 120
    assert isinstance(mem_system.target_memories, dict)
    assert mem_system.target_memories == {}


@pytest.mark.asyncio
async def test_calculate_memory_strength(isolated_test_db):
    """Test memory strength calculation"""
    mem_system = MemorySystem()
    
    # Test with different prediction errors and arousal
    strength_low = mem_system.calculate_memory_strength(0.0, 0.3)
    strength_high = mem_system.calculate_memory_strength(0.5, 0.8)
    
    assert 0 <= strength_low
    assert 0 <= strength_high
    assert strength_high > strength_low  # Higher prediction error + arousal = stronger memory


@pytest.mark.asyncio
async def test_add_event(isolated_test_db):
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


@pytest.mark.asyncio
async def test_get_events_by_target(isolated_test_db):
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


@pytest.mark.asyncio
async def test_memory_summarization_with_events(isolated_test_db):
    """Test memory summarization with events"""
    mem_system = MemorySystem()
    
    # Add some events
    events = [
        Event(type="user_message", actor="user1", target="assistant", text="hello, this is great!"),
        Event(type="assistant_reply", actor="assistant", target="user1", text="glad you like it!"),
        Event(type="user_message", actor="user1", target="assistant", text="thanks!"),
    ]
    
    for event in events:
        await add_event(event.model_dump())
    
    # Test summarization (should work with events)
    result = await mem_system.summarize_memories()
    assert result["status"] in ["completed", "not_due"]
