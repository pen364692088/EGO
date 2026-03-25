"""
Test core emotion state management functionality
"""
import os
import pytest
import pytest_asyncio
import asyncio
from emotiond.core import EmotionState, RelationshipManager, process_event, generate_plan
from emotiond.models import Event, PlanRequest
from emotiond.db import init_db, get_state, get_relationships
from emotiond.config import DB_PATH


class TestEmotionState:
    """Test EmotionState class"""
    
    def test_initial_state(self):
        """Test initial emotion state"""
        state = EmotionState()
        assert state.valence == 0.0
        assert state.arousal == 0.3
        assert state.subjective_time == 0
    
    def test_update_from_positive_user_message(self):
        """Test state update from positive user message"""
        state = EmotionState()
        event = Event(
            type="user_message",
            actor="assistant",
            target="assistant",
            text="This is great, thanks!"
        )
        
        state.update_from_event(event)
        assert state.valence > 0.0
        assert state.arousal > 0.3
    
    def test_update_from_negative_user_message(self):
        """Test state update from negative user message"""
        state = EmotionState()
        event = Event(
            type="user_message",
            actor="assistant",
            target="assistant",
            text="This is bad and wrong!"
        )
        
        state.update_from_event(event)
        assert state.valence < 0.0
        assert state.arousal > 0.3
    
    def test_update_from_assistant_reply(self):
        """Test state update from assistant reply"""
        state = EmotionState()
        state.valence = 0.5
        state.arousal = 0.8
        
        event = Event(
            type="assistant_reply",
            actor="assistant",
            target="user",
            text="I understand"
        )
        
        state.update_from_event(event)
        # Should stabilize emotions (decrease slightly)
        assert state.valence < 0.5
        assert state.arousal < 0.8
    
    def test_homeostasis_drift(self):
        """Test homeostasis drift toward neutral"""
        state = EmotionState()
        state.valence = 0.5
        state.arousal = 0.8
        
        state.apply_homeostasis_drift()
        
        # Should drift toward neutral
        assert state.valence < 0.5
        assert state.arousal < 0.8
        # Subjective time should increase (using subjective time calculation)
        assert state.subjective_time > 0


class TestRelationshipManager:
    """Test RelationshipManager class"""
    
    def test_initial_state(self):
        """Test initial relationship manager state"""
        manager = RelationshipManager()
        assert manager.relationships == {}
    
    def test_update_from_positive_interaction(self):
        """Test relationship update from positive interaction"""
        manager = RelationshipManager()
        event = Event(
            type="user_message",
            actor="A",
            target="assistant",
            text="You're doing great work!"
        )
        
        manager.update_from_event(event)
        assert "A" in manager.relationships
        assert manager.relationships["A"]["bond"] > 0.0
        assert manager.relationships["A"]["grudge"] == 0.0
    
    def test_update_from_negative_interaction(self):
        """Test relationship update from negative interaction"""
        manager = RelationshipManager()
        event = Event(
            type="user_message",
            actor="B",
            target="assistant",
            text="This is terrible!"
        )
        
        manager.update_from_event(event)
        assert "B" in manager.relationships
        assert manager.relationships["B"]["grudge"] > 0.0
    
    def test_consolidation_drift(self):
        """Test relationship consolidation drift"""
        manager = RelationshipManager()
        manager.relationships["A"] = {"bond": 0.8, "grudge": 0.6}
        
        manager.apply_consolidation_drift()
        
        # Both bond and grudge should decay
        assert manager.relationships["A"]["bond"] < 0.8
        assert manager.relationships["A"]["grudge"] < 0.6


class TestCoreIntegration:
    """Test core integration with database"""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self):
        """Setup database for tests"""
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Initialize database
        await init_db()
        
        # Reset global state
        from emotiond.core import emotion_state, relationship_manager
        emotion_state.valence = 0.0
        emotion_state.arousal = 0.3
        emotion_state.subjective_time = 0
        relationship_manager.relationships = {}
        
        # Clean up after tests
        yield
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
    
    @pytest.mark.asyncio
    async def test_event_processing_updates_state(self):
        """Test that event processing updates emotional state"""
        event = Event(
            type="user_message",
            actor="assistant",
            target="assistant",
            text="I love this!"
        )
        
        result = await process_event(event)
        
        # Should return processed status with valence/arousal
        assert result["status"] == "processed"
        assert "valence" in result
        assert "arousal" in result
        
        # State should be updated in database
        state = await get_state()
        assert state["valence"] > 0.0
        assert state["valence"] == result["valence"]
        assert state["arousal"] == result["arousal"]
    
    @pytest.mark.asyncio
    async def test_event_processing_updates_relationships(self):
        """Test that event processing updates relationships"""
        event = Event(
            type="user_message",
            actor="A",
            target="assistant",
            text="Great job!"
        )
        
        await process_event(event)
        
        # Relationship should be updated in database
        relationships = await get_relationships()
        target_a_relationships = [r for r in relationships if r["target"] == "A"]
        assert len(target_a_relationships) == 1
        assert target_a_relationships[0]["bond"] > 0.0
    
    @pytest.mark.asyncio
    async def test_plan_generation_with_emotional_state(self):
        """Test plan generation based on emotional state"""
        # First create some emotional state
        event = Event(
            type="user_message",
            actor="assistant",
            target="assistant",
            text="You're amazing!"
        )
        await process_event(event)
        
        # Generate plan
        request = PlanRequest(user_id="user", user_text="How are you?")
        plan = await generate_plan(request)
        
        # Should return valid plan with all required fields
        assert plan.tone in ["soft", "warm", "guarded", "cold"]
        assert plan.intent in ["repair", "distance", "seek", "set_boundary", "retaliate"]
        assert plan.focus_target == "user"
        assert len(plan.key_points) > 0
        assert len(plan.constraints) > 0
        assert "valence" in plan.emotion
        assert "arousal" in plan.emotion
        assert "bond" in plan.relationship
        assert "grudge" in plan.relationship
    
    @pytest.mark.asyncio
    async def test_sadness_persistence(self):
        """Test that sadness persists over time"""
        # Create negative event
        event = Event(
            type="user_message",
            actor="assistant",
            target="assistant",
            text="This is terrible and I hate it!"
        )
        
        result = await process_event(event)
        initial_valence = result["valence"]
        
        # Apply homeostasis drift multiple times
        from emotiond.core import emotion_state
        for _ in range(5):
            emotion_state.apply_homeostasis_drift()
            await asyncio.sleep(0.1)
        
        # Valence should remain negative (sadness persists)
        assert emotion_state.valence < 0.0
        assert emotion_state.valence > initial_valence  # Should drift toward neutral (less negative)
    
    @pytest.mark.asyncio
    async def test_grudge_decay_slowly(self):
        """Test that grudge decays slowly"""
        # Create negative interaction to build grudge
        event = Event(
            type="user_message",
            actor="A",
            target="assistant",
            text="I hate you!"
        )
        
        await process_event(event)
        
        # Get initial grudge level
        from emotiond.core import relationship_manager
        initial_grudge = relationship_manager.relationships["A"]["grudge"]
        
        # Apply consolidation drift multiple times
        for _ in range(3):
            relationship_manager.apply_consolidation_drift()
            await asyncio.sleep(0.1)
        
        # Grudge should decay slowly (still present)
        final_grudge = relationship_manager.relationships["A"]["grudge"]
        assert final_grudge < initial_grudge
        assert final_grudge > 0.0  # Should still have some grudge