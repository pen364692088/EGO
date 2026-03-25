"""
MVP-10 T09: Test Intervention - disable_hot

Tests:
1. DISABLE_HOT intervention type exists
2. InterventionManager tracks disable_hot
3. DisableHOTIntervention class works correctly
4. disable_hot causes predictable performance separation
"""
import pytest
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    InterventionConfig,
    InterventionResult,
    DisableHOTIntervention,
    create_disable_hot_intervention,
    run_with_hot_disabled,
)
from emotiond.hot_self_model import (
    HOTSelfModel,
    HOTState,
    reset_hot_self_model,
)


class TestInterventionType:
    """Tests for InterventionType enum."""
    
    def test_disable_hot_exists(self):
        """Test that DISABLE_HOT intervention type exists."""
        assert hasattr(InterventionType, 'DISABLE_HOT')
        assert InterventionType.DISABLE_HOT.value == "disable_hot"
    
    def test_disable_broadcast_exists(self):
        """Test that DISABLE_BROADCAST intervention type exists."""
        assert hasattr(InterventionType, 'DISABLE_BROADCAST')
        assert InterventionType.DISABLE_BROADCAST.value == "disable_broadcast"


class TestInterventionManager:
    """Tests for InterventionManager with disable_hot."""
    
    def test_is_hot_disabled(self):
        """Test is_hot_disabled method."""
        manager = InterventionManager()
        
        # Initially not disabled
        assert not manager.is_hot_disabled()
        
        # Enable disable_hot
        manager.enable(InterventionType.DISABLE_HOT)
        assert manager.is_hot_disabled()
        
        # Disable
        manager.disable(InterventionType.DISABLE_HOT)
        assert not manager.is_hot_disabled()
    
    def test_is_broadcast_disabled(self):
        """Test is_broadcast_disabled method."""
        manager = InterventionManager()
        
        assert not manager.is_broadcast_disabled()
        
        manager.enable(InterventionType.DISABLE_BROADCAST)
        assert manager.is_broadcast_disabled()
        
        manager.disable(InterventionType.DISABLE_BROADCAST)
        assert not manager.is_broadcast_disabled()
    
    def test_apply_intervention_includes_disable_hot(self):
        """Test that apply_intervention includes disable_hot in results."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_HOT)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("hot_disabled") is True
        assert "disable_hot" in result.get("interventions_applied", [])
    
    def test_multiple_interventions(self):
        """Test that multiple interventions can be active simultaneously."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.DISABLE_HOT)
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        
        assert manager.is_hot_disabled()
        assert manager.is_active(InterventionType.FREEZE_VALENCE)
        
        result = manager.apply_intervention(valence=0.0)
        
        assert result.get("hot_disabled") is True
        assert result.get("valence") == 0.5


class TestDisableHOTIntervention:
    """Tests for DisableHOTIntervention class."""
    
    def test_creation(self):
        """Test creating DisableHOTIntervention."""
        intervention = DisableHOTIntervention()
        
        assert intervention.is_active()
    
    def test_is_active(self):
        """Test is_active method."""
        intervention = DisableHOTIntervention()
        
        assert intervention.is_active()
    
    def test_apply_to_hot_state(self):
        """Test applying intervention to HOT state."""
        intervention = DisableHOTIntervention()
        
        # Normal HOT state with conflict bias
        hot_state = {
            "conflict_bias": 0.2,
            "control_penalty": 0.15,
            "should_reflect": True,
            "info_seeking_bonus": 0.1,
            "high_conflict": True,
            "low_control": True,
        }
        
        modified = intervention.apply_to_hot_state(hot_state)
        
        # All influence should be zeroed
        assert modified["conflict_bias"] == 0.0
        assert modified["control_penalty"] == 0.0
        assert not modified["should_reflect"]
        assert modified["info_seeking_bonus"] == 0.0
        assert modified["hot_disabled"] is True
        
        # Detection flags should be preserved
        assert modified["high_conflict"] is True
        assert modified["low_control"] is True
    
    def test_apply_to_candidates(self):
        """Test applying intervention to candidates."""
        intervention = DisableHOTIntervention()
        
        candidates = [
            {"id": "test", "score": 0.7, "type": "act"},
        ]
        
        modified = intervention.apply_to_candidates(candidates)
        
        assert len(modified) == 1
        assert modified[0]["hot_applied"] is False
        assert modified[0]["hot_disabled"] is True
        # Score should be unchanged
        assert modified[0]["score"] == 0.7
    
    def test_to_dict(self):
        """Test serialization."""
        intervention = DisableHOTIntervention()
        
        data = intervention.to_dict()
        
        assert "disabled_at" in data
        assert data["is_active"] is True
        assert "manager" in data


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_disable_hot_intervention(self):
        """Test create_disable_hot_intervention factory."""
        intervention = create_disable_hot_intervention(reason="test")
        
        assert intervention.is_active()


class TestPerformanceSeparation:
    """
    Tests that disable_hot causes predictable performance separation.
    
    This is the core test for T09: verifying that the intervention
    produces measurable behavioral differences.
    """
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_conflict_gating_with_hot_enabled(self):
        """
        Test conflict-gating task with HOT enabled.
        
        In conflict-heavy scenarios, HOT should bias toward reflection
        and reduce errors.
        """
        hot = HOTSelfModel()
        
        # Set high conflict directly
        hot.state.conflict_level = 0.7
        
        # Candidates with action vs reflection options (close scores)
        candidates = [
            {"id": "act_immediately", "score": 0.5, "type": "act", "meta": {"risk_level": 0.5}},
            {"id": "reflect_first", "score": 0.4, "type": "reflect"},
            {"id": "gather_info", "score": 0.45, "type": "info_seek"},
        ]
        
        # Apply HOT influence
        modified = hot.apply_to_candidates(candidates)
        
        # Find best candidate
        best = max(modified, key=lambda c: c["score"])
        
        # With HOT enabled and high conflict, should prefer reflection/info
        assert best["type"] in ("reflect", "info_seek")
    
    def test_conflict_gating_with_hot_disabled(self):
        """
        Test conflict-gating task with HOT disabled.
        
        When HOT is disabled, candidates pass through without
        conflict-based modifications.
        """
        intervention = DisableHOTIntervention()
        hot = HOTSelfModel()
        
        # Same conflict-heavy scenario
        hot.update_conflict_level([
            {"weight": 0.7, "description": "goal_conflict"},
        ])
        
        candidates = [
            {"id": "act_immediately", "score": 0.7, "type": "act", "meta": {"risk_level": 0.5}},
            {"id": "reflect_first", "score": 0.4, "type": "reflect"},
            {"id": "gather_info", "score": 0.5, "type": "info_seek"},
        ]
        
        # Apply intervention (bypass HOT)
        modified = intervention.apply_to_candidates(candidates)
        
        # Find best candidate
        best = max(modified, key=lambda c: c["score"])
        
        # With HOT disabled, original scores should be preserved
        # So act_immediately (score 0.7) should still be best
        assert best["id"] == "act_immediately"
        assert best["score"] == 0.7
    
    def test_behavioral_separation(self):
        """
        Test that HOT enabled vs disabled produces different behaviors.
        
        This is the key test for T09: demonstrating causal effect.
        """
        hot = HOTSelfModel()
        intervention = DisableHOTIntervention()
        
        # Set up conflict-heavy scenario
        hot.state = HOTState(conflict_level=0.8, control_estimate=0.3)
        
        # Candidates with closer scores so HOT can tip the balance
        candidates = [
            {"id": "risky_action", "score": 0.5, "type": "act", "meta": {"risk_level": 0.8}},
            {"id": "cautious_reflection", "score": 0.45, "type": "reflect"},
        ]
        
        # With HOT enabled
        enabled_result = hot.apply_to_candidates(candidates)
        enabled_best = max(enabled_result, key=lambda c: c["score"])
        
        # With HOT disabled
        disabled_result = intervention.apply_to_candidates(candidates)
        disabled_best = max(disabled_result, key=lambda c: c["score"])
        
        # Should produce different behaviors
        assert enabled_best["id"] != disabled_best["id"]
        
        # With HOT: should prefer cautious reflection
        assert enabled_best["type"] == "reflect"
        
        # Without HOT: should prefer risky action (higher original score)
        assert disabled_best["id"] == "risky_action"
    
    def test_run_comparison(self):
        """Test the run_comparison method for systematic comparison."""
        intervention = DisableHOTIntervention()
        
        # Mock run function that simulates different scenarios
        def mock_run(scenario: str, hot_enabled: bool = True, **kwargs):
            if scenario == "conflict_heavy":
                # Without HOT, should make more errors
                return {
                    "success_rate": 0.9 if hot_enabled else 0.6,
                    "reflection_count": 3 if hot_enabled else 0,
                }
            elif scenario == "low_control":
                return {
                    "success_rate": 0.8 if hot_enabled else 0.5,
                    "risky_action_count": 1 if hot_enabled else 5,
                }
            else:
                return {"success_rate": 0.7}
        
        result = intervention.run_comparison(
            run_func=mock_run,
            scenarios=["conflict_heavy", "low_control"],
        )
        
        assert "separation" in result
        
        # Check that performance gap is positive (HOT helps)
        for scenario, sep in result["separation"].items():
            if scenario in ("conflict_heavy", "low_control"):
                assert sep["performance_gap"] > 0


class TestRunWithHotDisabled:
    """Tests for run_with_hot_disabled helper function."""
    
    def test_run_with_hot_disabled(self):
        """Test run_with_hot_disabled function."""
        
        def mock_run(hot_enabled=True, hot_intervention=None, context=None):
            return {"hot_enabled": hot_enabled}
        
        result = run_with_hot_disabled(mock_run)
        
        assert result["result"]["hot_enabled"] is False
        assert "intervention" in result


class TestIntegrationWithLoop:
    """
    Integration tests showing how disable_hot integrates with the loop.
    """
    
    def setup_method(self):
        """Reset HOT instance before each test."""
        reset_hot_self_model()
    
    def test_intervention_manager_with_hot_model(self):
        """Test using InterventionManager with HOTSelfModel together."""
        manager = InterventionManager()
        hot = HOTSelfModel()
        
        # Set high conflict directly (above threshold)
        hot.state.conflict_level = 0.7
        
        # Get arbitration modifiers
        modifiers = hot.get_arbitration_modifiers()
        
        # With high conflict, modifiers should be non-zero
        assert modifiers["conflict_bias"] > 0
        
        # Enable disable_hot
        manager.enable(InterventionType.DISABLE_HOT)
        
        # Check that intervention is active
        assert manager.is_hot_disabled()
        
        # Create intervention and apply to HOT state
        intervention = DisableHOTIntervention()
        modified = intervention.apply_to_hot_state(modifiers)
        
        # Should be zeroed
        assert modified["conflict_bias"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
