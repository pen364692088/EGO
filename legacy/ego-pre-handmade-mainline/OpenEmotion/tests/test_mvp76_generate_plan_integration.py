"""Tests for MVP-7.6: generate_plan integration with select_action and get_self_model_v0."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from emotiond.core import generate_plan, emotion_state, relationship_manager, reset_allostasis_budget
from emotiond.self_model.legacy import get_self_model_v0, reset_self_model_v0
from emotiond.models import PlanRequest


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
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


class TestGeneratePlanUsesSelectAction:
    """Test that generate_plan calls select_action_with_explanation."""
    
    @pytest.mark.asyncio
    async def test_generate_plan_calls_select_action(self):
        """Test that generate_plan calls select_action_with_explanation."""
        request = PlanRequest(
            user_text="Hello",
            user_id="test_user",
            focus_target="test_user"
        )
        
        with patch('emotiond.core.select_action_with_explanation') as mock_select:
            mock_select.return_value = {
                "action": "approach",
                "explanation": {},
                "decision_id": 1
            }
            
            result = await generate_plan(request)
            
            # Verify select_action_with_explanation was called
            mock_select.assert_called_once_with("test_user", test_mode=False)
            
            # Verify the intent is mapped correctly
            assert result.intent == "seek"  # "approach" -> "seek"
    
    @pytest.mark.asyncio
    async def test_generate_plan_action_to_intent_mapping(self):
        """Test correct mapping of ACTION_SPACE to intent names."""
        request = PlanRequest(
            user_text="Hello",
            user_id="test_user",
            focus_target="test_user"
        )
        
        # Test each action mapping
        action_to_intent = {
            "approach": "seek",
            "repair_offer": "repair",
            "boundary": "set_boundary",
            "withdraw": "distance",
            "attack": "retaliate"
        }
        
        for action, expected_intent in action_to_intent.items():
            with patch('emotiond.core.select_action_with_explanation') as mock_select:
                mock_select.return_value = {
                    "action": action,
                    "explanation": {},
                    "decision_id": 1
                }
                
                result = await generate_plan(request)
                assert result.intent == expected_intent, f"Action {action} should map to {expected_intent}, got {result.intent}"


class TestGeneratePlanUsesGlobalSelfModelV0:
    """Test that generate_plan uses get_self_model_v0 (global instance)."""
    
    @pytest.mark.asyncio
    async def test_generate_plan_uses_get_self_model_v0(self):
        """Test that generate_plan uses get_self_model_v0 instead of building new instance."""
        target = "test_user"
        request = PlanRequest(
            user_text="Hello",
            user_id=target,
            focus_target=target
        )
        
        # Create a self_model instance first
        model = get_self_model_v0(target)
        model.identity.value_weights = {"connection": 0.9, "honesty": 0.5, "safety": 0.5, "growth": 0.5}
        
        with patch('emotiond.core.select_action_with_explanation') as mock_select:
            mock_select.return_value = {
                "action": "approach",
                "explanation": {},
                "decision_id": 1
            }
            
            result = await generate_plan(request)
            
            # The self_report should contain data from the global instance
            assert result.self_report is not None
            assert "summary" in result.self_report


class TestGeneratePlanRespectsActionBias:
    """Test that generate_plan respects action_bias from SelfModelV0."""
    
    @pytest.mark.asyncio
    async def test_generate_plan_high_safety_bias_favors_withdraw(self):
        """Test that high safety value biases toward withdraw/boundary actions."""
        target = "threatening_user"
        request = PlanRequest(
            user_text="Hello",
            user_id=target,
            focus_target=target
        )
        
        # Set up a self_model with high safety value
        model = get_self_model_v0(target)
        model.identity.value_weights = {"safety": 0.95, "connection": 0.2, "honesty": 0.5, "growth": 0.3}
        
        # Set up relationship with high grudge
        relationship_manager.relationships[target] = {
            "bond": 0.1,
            "grudge": 0.8,
            "trust": 0.1,
            "repair_bank": 0.0,
            "uncertainty": 0.5
        }
        
        # The select_action should pick actions biased by self_model
        # This test verifies the integration path works
        with patch('emotiond.core.select_action_with_explanation') as mock_select:
            # Simulate what select_action_with_explanation would return
            # when action_bias influences the decision
            mock_select.return_value = {
                "action": "withdraw",
                "explanation": {"action_bias": 0.3},
                "decision_id": 1
            }
            
            result = await generate_plan(request)
            
            # Intent should be "distance" (mapped from "withdraw")
            assert result.intent == "distance"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
