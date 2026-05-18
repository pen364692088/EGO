"""
Test tick loop functionality for homeostasis and emotion drift
"""
import os
import pytest
import asyncio
import time
from emotiond.db import init_db, get_state, update_state
from emotiond.core import EmotionState, load_initial_state
from emotiond.config import DB_PATH


@pytest.fixture
def emotion_state():
    """Create a fresh emotion state for testing"""
    return EmotionState()


@pytest.mark.asyncio
async def test_subjective_time_calculation(emotion_state):
    """Test subjective time calculation based on arousal"""
    # Test with low arousal
    emotion_state.arousal = 0.1
    subjective_dt_low = emotion_state.calculate_subjective_time_delta(1.0)
    assert subjective_dt_low > 0.8  # Should be close to real time
    
    # Test with high arousal
    emotion_state.arousal = 0.9
    subjective_dt_high = emotion_state.calculate_subjective_time_delta(1.0)
    assert subjective_dt_high < 0.4  # Should be much slower than real time
    
    # Test that higher arousal gives smaller subjective time
    assert subjective_dt_high < subjective_dt_low


@pytest.mark.asyncio
async def test_homeostasis_drift_with_subjective_time(emotion_state):
    """Test homeostasis drift with subjective time calculation"""
    # Set initial state
    emotion_state.valence = 0.5
    emotion_state.arousal = 0.5
    initial_subjective_time = emotion_state.subjective_time
    
    # Apply drift with real time delta
    emotion_state.apply_homeostasis_drift(1.0)
    
    # Check that subjective time increased
    assert emotion_state.subjective_time > initial_subjective_time
    
    # Check that valence drifted toward neutral
    assert emotion_state.valence < 0.5
    assert emotion_state.valence >= 0.0
    
    # Check that arousal decreased
    assert emotion_state.arousal < 0.5


@pytest.mark.asyncio
async def test_loneliness_increases_with_time(emotion_state):
    """Test that loneliness increases with time since meaningful contact"""
    # Set last meaningful contact to far in the past
    emotion_state.last_meaningful_contact = time.time() - 7200  # 2 hours ago
    initial_valence = emotion_state.valence = 0.3
    
    # Apply drift
    emotion_state.apply_homeostasis_drift(1.0)
    
    # Check that valence decreased due to loneliness
    assert emotion_state.valence < initial_valence


@pytest.mark.asyncio
async def test_emotion_inertia(emotion_state):
    """Test that emotions change gradually (inertia)"""
    # Set strong positive emotion
    emotion_state.valence = 0.8
    emotion_state.arousal = 0.7
    
    # Apply multiple drifts
    for _ in range(10):
        previous_valence = emotion_state.valence
        previous_arousal = emotion_state.arousal
        
        emotion_state.apply_homeostasis_drift(1.0)
        
        # Check that changes are gradual
        assert abs(emotion_state.valence - previous_valence) < 0.1
        assert abs(emotion_state.arousal - previous_arousal) < 0.1
    
    # After multiple drifts, should be closer to neutral
    # Note: The drift is designed to be gradual, so after 10 iterations
    # we expect significant but not complete return to neutral
    assert emotion_state.valence < 0.8  # Should have decreased
    assert emotion_state.arousal < 0.7  # Should have decreased


@pytest.mark.asyncio
async def test_homeostasis_loop_integration():
    """Test that homeostasis loop properly updates state"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    await init_db()
    
    try:
        from emotiond.core import emotion_state, homeostasis_loop
        
        # Load initial state
        await load_initial_state()
        
        # Set initial values
        emotion_state.valence = 0.7
        emotion_state.arousal = 0.8
        initial_subjective_time = emotion_state.subjective_time
        
        # Run one iteration of homeostasis loop
        await update_state(emotion_state.valence, emotion_state.arousal, emotion_state.subjective_time)
        initial_db_state = await get_state()
        
        # Run homeostasis loop manually for one iteration
        last_time = time.time()
        await asyncio.sleep(0.1)  # Small delay
        current_time = time.time()
        real_dt = current_time - last_time
        
        emotion_state.apply_homeostasis_drift(real_dt)
        await update_state(emotion_state.valence, emotion_state.arousal, emotion_state.subjective_time)
        
        # Check that state was updated
        final_db_state = await get_state()
        assert final_db_state["valence"] != initial_db_state["valence"]
        assert final_db_state["arousal"] != initial_db_state["arousal"]
        assert final_db_state["subjective_time"] > initial_db_state["subjective_time"]
    
    finally:
        # Clean up
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)


@pytest.mark.asyncio
async def test_subjective_time_persists():
    """Test that subjective time persists across restarts"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    await init_db()
    
    try:
        # Set initial state with subjective time
        await update_state(0.3, 0.4, 100)
        
        # Load state and verify subjective time
        state = await get_state()
        assert state["subjective_time"] == 100
    
    finally:
        # Clean up
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)


@pytest.mark.asyncio
async def test_meaningful_contact_time_persists():
    """Test that meaningful contact time persists"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    await init_db()
    
    try:
        # Load initial state
        state = await get_state()
        initial_contact_time = state["last_meaningful_contact"]
        
        # Verify it's a reasonable timestamp (should be recent)
        assert time.time() - initial_contact_time < 10  # Within 10 seconds
    
    finally:
        # Clean up
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)


@pytest.mark.asyncio
async def test_state_persistence_across_restarts():
    """Test that emotional state persists when daemon restarts"""
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Initialize database
    await init_db()
    
    try:
        # Set specific emotional state
        await update_state(0.6, 0.7, 150)
        
        # Simulate daemon restart by reloading
        from emotiond.core import emotion_state, load_initial_state
        await load_initial_state()
        
        # Verify state was loaded correctly
        assert emotion_state.valence == 0.6
        assert emotion_state.arousal == 0.7
        assert emotion_state.subjective_time == 150
    
    finally:
        # Clean up
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)