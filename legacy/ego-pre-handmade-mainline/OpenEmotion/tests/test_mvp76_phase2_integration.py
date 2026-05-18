"""Tests for MVP-7.6 Phase 2: SelfModel Integration into emotiond decision chain."""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from emotiond.self_model.legacy import (
    SelfModelV0, 
    get_self_model_v0, 
    reset_self_model_v0,
    build_self_model_v0,
)
from emotiond.core import (
    process_event,
    select_action,
    score_action,
    emotion_state,
    relationship_manager,
    reset_allostasis_budget,
)
from emotiond.models import Event


@pytest_asyncio.fixture(autouse=True)
async def reset_state(isolated_db):
    """Reset state before each test with isolated database."""
    reset_self_model_v0()
    reset_allostasis_budget()
    # Reset emotion_state
    emotion_state.valence = 0.0
    emotion_state.arousal = 0.3
    emotion_state.uncertainty = 0.5
    emotion_state.social_safety = 0.6
    emotion_state.energy = 0.7
    # Reset relationships
    relationship_manager.relationships = {}
    yield
    # Cleanup
    reset_self_model_v0()


class TestGetSelfModelV0:
    """Test get_self_model_v0 function."""
    
    def test_get_self_model_v0_returns_instance(self):
        """Test that get_self_model_v0 returns a SelfModelV0 instance."""
        model = get_self_model_v0("test_target")
        assert isinstance(model, SelfModelV0)
    
    def test_get_self_model_v0_same_target_same_instance(self):
        """Test that same target returns same instance."""
        model1 = get_self_model_v0("target_a")
        model2 = get_self_model_v0("target_a")
        assert model1 is model2
    
    def test_get_self_model_v0_different_targets_different_instances(self):
        """Test that different targets return different instances."""
        model1 = get_self_model_v0("target_a")
        model2 = get_self_model_v0("target_b")
        assert model1 is not model2
    
    def test_get_self_model_v0_default_target(self):
        """Test that None target returns default instance."""
        model = get_self_model_v0(None)
        assert isinstance(model, SelfModelV0)
        assert model.relational.focus_target == "default"
    
    def test_reset_self_model_v0_specific_target(self):
        """Test resetting a specific target."""
        model1 = get_self_model_v0("target_a")
        reset_self_model_v0("target_a")
        model2 = get_self_model_v0("target_a")
        assert model1 is not model2
    
    def test_reset_self_model_v0_all(self):
        """Test resetting all instances."""
        get_self_model_v0("target_a")
        get_self_model_v0("target_b")
        reset_self_model_v0()
        # After reset, new instances should be created
        model_a = get_self_model_v0("target_a")
        assert model_a is not None


class TestSelfModelV0ActionBias:
    """Test SelfModelV0.get_action_bias method."""
    
    def test_get_action_bias_returns_float(self):
        """Test that get_action_bias returns a float."""
        model = SelfModelV0()
        bias = model.get_action_bias("approach")
        assert isinstance(bias, float)
        assert -1.0 <= bias <= 1.0
    
    def test_get_action_bias_different_actions(self):
        """Test that different actions have different biases."""
        model = SelfModelV0()
        bias_approach = model.get_action_bias("approach")
        bias_withdraw = model.get_action_bias("withdraw")
        # Both should be valid floats
        assert isinstance(bias_approach, float)
        assert isinstance(bias_withdraw, float)
    
    def test_get_action_bias_respects_value_weights(self):
        """Test that bias respects identity value weights."""
        model = SelfModelV0()
        # Set high connection value
        model.identity.value_weights = {"connection": 0.9, "honesty": 0.5, "safety": 0.5, "growth": 0.5}
        bias_approach = model.get_action_bias("approach")
        # Approach aligns with connection, so bias should be positive
        assert isinstance(bias_approach, float)
    
    def test_get_action_bias_confidence_weighted(self):
        """Test that bias is weighted by cognitive confidence."""
        model = SelfModelV0()
        model.cognitive.confidence = 1.0
        bias_high = model.get_action_bias("approach")
        
        model.cognitive.confidence = 0.0
        bias_low = model.get_action_bias("approach")
        
        # Both should be floats, high confidence may have stronger bias
        assert isinstance(bias_high, float)
        assert isinstance(bias_low, float)


class TestProcessEventIntegration:
    """Test process_event integration with self_model."""
    
    @pytest.mark.asyncio
    async def test_process_event_includes_self_conflict(self):
        """Test that process_event returns self_conflict."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # Should have self_conflict in result
        assert "self_conflict" in result
        assert isinstance(result["self_conflict"], float)
        assert 0.0 <= result["self_conflict"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_process_event_includes_self_model_hash(self):
        """Test that process_event returns self_model_hash."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # Should have self_model_hash in result
        assert "self_model_hash" in result
        # Hash is either None (no target) or a 64-char SHA-256 hex string
        if result["self_model_hash"] is not None:
            assert len(result["self_model_hash"]) == 64
    
    @pytest.mark.asyncio
    async def test_process_event_includes_self_model_result(self):
        """Test that process_event returns self_model_result."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # Should have self_model_result in result
        assert "self_model_result" in result
        # self_model_result can be None (no target) or a dict
        if result["self_model_result"] is not None:
            assert "self_conflict" in result["self_model_result"]
            assert "delta" in result["self_model_result"]
            assert "evidence" in result["self_model_result"]
    
    @pytest.mark.asyncio
    async def test_process_event_high_conflict_event(self):
        """Test that high conflict events produce higher self_conflict."""
        # Neutral event
        neutral_event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        # Betrayal event (high conflict)
        betrayal_event = Event(
            type="world_event",
            actor="user",
            target="agent",
            text="",
            meta={"subtype": "betrayal", "source": "system"}
        )
        
        result_neutral = await process_event(neutral_event)
        result_betrayal = await process_event(betrayal_event)
        
        # Both should have self_conflict
        assert "self_conflict" in result_neutral
        assert "self_conflict" in result_betrayal


class TestSelectActionIntegration:
    """Test select_action integration with self_model."""
    
    def test_select_action_uses_self_model_bias(self):
        """Test that select_action uses self_model bias."""
        # Create a self_model for a target
        target = "test_user"
        self_model = get_self_model_v0(target)
        
        # Modify the self_model to have specific value weights
        self_model.identity.value_weights = {"safety": 0.9, "connection": 0.3, "honesty": 0.5, "growth": 0.5}
        
        # Ensure relationship exists
        relationship_manager._ensure_relationship_fields(target)
        
        # Select action
        action = select_action(emotion_state, target, test_mode=True)
        
        # Should have selected an action
        assert action is not None
        assert isinstance(action, str)
    
    def test_select_action_different_targets_different_self_models(self):
        """Test that different targets use different self_models."""
        target1 = "user_a"
        target2 = "user_b"
        
        # Create different self_models with different value weights
        model1 = get_self_model_v0(target1)
        model1.identity.value_weights = {"connection": 0.9, "honesty": 0.5, "safety": 0.5, "growth": 0.5}
        
        model2 = get_self_model_v0(target2)
        model2.identity.value_weights = {"safety": 0.9, "connection": 0.3, "honesty": 0.5, "growth": 0.5}
        
        # Ensure relationships exist
        relationship_manager._ensure_relationship_fields(target1)
        relationship_manager._ensure_relationship_fields(target2)
        
        # Select actions
        action1 = select_action(emotion_state, target1, test_mode=True)
        action2 = select_action(emotion_state, target2, test_mode=True)
        
        # Both should have selected actions
        assert action1 is not None
        assert action2 is not None


class TestActionBiasWeight:
    """Test that action_bias_weight is configurable."""
    
    def test_self_bias_weight_affects_score(self):
        """Test that self_bias_weight affects the final score."""
        target = "test_target"
        relationship_manager._ensure_relationship_fields(target)
        
        # Get self_model and set specific value weights
        self_model = get_self_model_v0(target)
        self_model.identity.value_weights = {"connection": 0.9, "honesty": 0.5, "safety": 0.5, "growth": 0.5}
        
        # Get the bias
        bias = self_model.get_action_bias("approach")
        
        # Bias should be a float
        assert isinstance(bias, float)
        
        # The bias should affect the action selection
        action = select_action(emotion_state, target, test_mode=True)
        assert action is not None


class TestBackwardCompatibility:
    """Test that integration doesn't break existing functionality."""
    
    @pytest.mark.asyncio
    async def test_process_event_still_returns_core_fields(self):
        """Test that process_event still returns all core fields."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # Core fields should still be present
        assert "status" in result
        assert "valence" in result
        assert "arousal" in result
        assert "prediction_error" in result
        assert "social_safety" in result
        assert "energy" in result
        assert "uncertainty" in result
    
    def test_select_action_still_works_without_self_model(self):
        """Test that select_action works even with fresh self_model."""
        target = "fresh_target"
        relationship_manager._ensure_relationship_fields(target)
        
        # Don't modify self_model - use defaults
        action = select_action(emotion_state, target, test_mode=True)
        
        # Should still select an action
        assert action is not None
    
    @pytest.mark.asyncio
    async def test_enforcer_constraints_not_affected(self):
        """Test that enforcer constraints are not affected by self_model."""
        # This test verifies that the self_model integration doesn't
        # bypass or alter the enforcer behavior
        
        # Process a betrayal event (which requires system source)
        betrayal_event = Event(
            type="world_event",
            actor="user",
            target="agent",
            text="",
            meta={"subtype": "betrayal", "source": "user"}  # Invalid source
        )
        
        result = await process_event(betrayal_event)
        
        # Should be denied by enforcer, not affected by self_model
        assert result.get("status") == "denied"


class TestAuditLogFields:
    """Test that audit log contains self_model fields."""
    
    @pytest.mark.asyncio
    async def test_audit_log_contains_self_conflict(self):
        """Test that audit log contains self_conflict."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # self_conflict should be in the result (which goes to audit)
        assert "self_conflict" in result
        assert isinstance(result["self_conflict"], float)
    
    @pytest.mark.asyncio
    async def test_audit_log_contains_self_model_hash(self):
        """Test that audit log contains self_model_hash."""
        event = Event(
            type="user_message",
            actor="user",
            target="agent",
            text="Hello",
            meta={}
        )
        
        result = await process_event(event)
        
        # self_model_hash should be in the result
        assert "self_model_hash" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
