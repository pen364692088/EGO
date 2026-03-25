"""
MVP11-T15 Test: Counterfactual Self Model Planning

Tests for:
- Counterfactual scenario generation
- Strategy comparison between actual and counterfactual
- Reality matching and strategy selection
- Integration with HOT self model
"""
import pytest
import time
from typing import Dict, Any

from emotiond.self_counterfactual import (
    CounterfactualSelfModel,
    CounterfactualScenario,
    CounterfactualType,
    StrategyComparison,
    RealityMatch,
    integrate_with_hot,
    apply_counterfactual_to_candidates,
    get_counterfactual_model,
    reset_counterfactual_model,
)
from emotiond.hot_self_model import HOTSelfModel, HOTState


class TestCounterfactualScenario:
    """Tests for CounterfactualScenario dataclass."""
    
    def test_scenario_creation(self):
        """Test basic scenario creation."""
        scenario = CounterfactualScenario(
            id="test_scenario",
            name="Test Scenario",
            scenario_type=CounterfactualType.RESOURCE_DEPLETION,
            modifications={"bodily.energy": 0.25},
        )
        
        assert scenario.id == "test_scenario"
        assert scenario.name == "Test Scenario"
        assert scenario.scenario_type == CounterfactualType.RESOURCE_DEPLETION
        assert scenario.modifications == {"bodily.energy": 0.25}
        assert scenario.match_threshold == 0.15
        assert scenario.strategy is None
    
    def test_scenario_serialization(self):
        """Test scenario serialization/deserialization."""
        scenario = CounterfactualScenario(
            id="test",
            name="Test",
            scenario_type=CounterfactualType.COGNITIVE_LIMITATION,
            modifications={"cognitive.uncertainty": 0.75},
            match_threshold=0.2,
            strategy={"mode": "info_seeking"},
            priority=0.7,
        )
        
        data = scenario.to_dict()
        restored = CounterfactualScenario.from_dict(data)
        
        assert restored.id == scenario.id
        assert restored.name == scenario.name
        assert restored.scenario_type == scenario.scenario_type
        assert restored.modifications == scenario.modifications
        assert restored.match_threshold == scenario.match_threshold
        assert restored.strategy == scenario.strategy
        assert restored.priority == scenario.priority


class TestCounterfactualSelfModel:
    """Tests for CounterfactualSelfModel."""
    
    def test_initialization(self):
        """Test model initialization with default scenarios."""
        model = CounterfactualSelfModel()
        
        assert len(model.scenarios) > 0
        assert "low_energy" in model.scenarios
        assert "low_safety" in model.scenarios
        assert "high_uncertainty" in model.scenarios
    
    def test_initialization_without_defaults(self):
        """Test model initialization without default scenarios."""
        model = CounterfactualSelfModel(auto_initialize=False)
        
        assert len(model.scenarios) == 0
    
    def test_add_custom_scenario(self):
        """Test adding custom scenario."""
        model = CounterfactualSelfModel(auto_initialize=False)
        
        scenario = CounterfactualScenario(
            id="custom_test",
            name="Custom Test",
            scenario_type=CounterfactualType.STRESS_CONDITION,
            modifications={"bodily.social_safety": 0.2},
            priority=0.8,
        )
        
        model.add_scenario(scenario)
        
        assert "custom_test" in model.scenarios
        assert model.scenarios["custom_test"].strategy is not None  # Auto-computed
    
    def test_remove_scenario(self):
        """Test removing scenario."""
        model = CounterfactualSelfModel()
        
        initial_count = len(model.scenarios)
        result = model.remove_scenario("low_energy")
        
        assert result is True
        assert len(model.scenarios) == initial_count - 1
        assert "low_energy" not in model.scenarios
    
    def test_generate_counterfactuals(self):
        """Test counterfactual generation from current state."""
        model = CounterfactualSelfModel()
        
        current_state = {
            "bodily": {"energy": 0.7, "social_safety": 0.6},
            "cognitive": {"uncertainty": 0.3, "confidence": 0.7},
        }
        
        counterfactuals = model.generate_counterfactuals(current_state)
        
        assert len(counterfactuals) > 0
        
        # Should have energy counterfactual
        energy_cfs = [cf for cf in counterfactuals if "energy" in cf["id"]]
        assert len(energy_cfs) > 0
    
    def test_compare_strategies(self):
        """Test strategy comparison."""
        model = CounterfactualSelfModel()
        
        actual = {
            "risk_tolerance": 0.5,
            "info_seeking_weight": 0.5,
        }
        
        counterfactual = {
            "risk_tolerance": 0.3,
            "info_seeking_weight": 0.7,
            "mode": "conservation",
        }
        
        comparison = model.compare_strategies(actual, counterfactual)
        
        assert comparison.actual_strategy == actual
        assert comparison.counterfactual_strategy == counterfactual
        assert comparison.risk_difference < 0  # Counterfactual has lower risk
        assert comparison.recommendation in ("actual", "counterfactual", "hybrid")
    
    def test_select_strategy_no_match(self):
        """Test strategy selection when no counterfactual matches."""
        model = CounterfactualSelfModel()
        
        # Normal state - no counterfactual should match
        state = {
            "bodily": {"energy": 0.8, "social_safety": 0.8},
            "cognitive": {"uncertainty": 0.2, "confidence": 0.8},
            "hot": {"control_estimate": 0.7, "conflict_level": 0.1},
        }
        
        strategy = model.select_strategy(state)
        
        assert strategy["source"] == "adaptive"
        assert strategy["mode"] == "normal"
    
    def test_select_strategy_with_match(self):
        """Test strategy selection when counterfactual matches."""
        model = CounterfactualSelfModel()
        
        # Low energy state - should match low_energy counterfactual
        state = {
            "bodily": {"energy": 0.2, "social_safety": 0.6},
            "cognitive": {"uncertainty": 0.3, "confidence": 0.7},
            "hot": {"control_estimate": 0.5, "conflict_level": 0.0},
        }
        
        strategy = model.select_strategy(state)
        
        # Should match low_energy scenario
        assert strategy["source"] == "counterfactual"
        assert "match" in strategy
        assert strategy["match"]["scenario_id"] == "low_energy"
    
    def test_check_reality_match_low_energy(self):
        """Test reality matching for low energy scenario."""
        model = CounterfactualSelfModel()
        
        # State that should match low_energy scenario
        state = {
            "bodily": {"energy": 0.25},  # At or below threshold
        }
        
        match = model.check_reality_match(state)
        
        assert match is not None
        assert match.scenario_id == "low_energy"
        assert match.match_score >= model.scenarios["low_energy"].match_threshold
    
    def test_check_reality_match_no_match(self):
        """Test reality matching when no scenario matches."""
        model = CounterfactualSelfModel()
        
        # High energy state - should not match low_energy
        state = {
            "bodily": {"energy": 0.8, "social_safety": 0.8},
        }
        
        match = model.check_reality_match(state)
        
        # No match expected (all dimensions high)
        assert match is None
    
    def test_check_reality_match_critical_state(self):
        """Test reality matching for critical state."""
        model = CounterfactualSelfModel()
        
        # Critical state - multiple dimensions low
        state = {
            "bodily": {"energy": 0.15, "social_safety": 0.15},
            "homeostasis": {"safety": 0.15},
        }
        
        match = model.check_reality_match(state)
        
        # Should match critical_state scenario (highest priority)
        assert match is not None
        # Critical state has highest priority (0.9)
        assert match.scenario_id == "critical_state"
    
    def test_match_history(self):
        """Test match history recording."""
        model = CounterfactualSelfModel()
        
        # Trigger a match
        state = {
            "bodily": {"energy": 0.2},
        }
        
        strategy = model.select_strategy(state)
        
        # Check history
        history = model.get_match_history()
        assert len(history) > 0
        assert history[-1]["scenario_id"] == "low_energy"
    
    def test_scenario_stats(self):
        """Test scenario statistics."""
        model = CounterfactualSelfModel()
        
        # Trigger some matches
        state1 = {"bodily": {"energy": 0.2}}
        state2 = {"bodily": {"social_safety": 0.2}, "homeostasis": {"safety": 0.2}}
        
        model.select_strategy(state1)
        model.select_strategy(state2)
        
        stats = model.get_scenario_stats()
        
        assert stats["total_scenarios"] > 0
        assert stats["total_matches"] >= 2
        assert "low_energy" in stats["scenarios"]


class TestRealityMatch:
    """Tests for RealityMatch dataclass."""
    
    def test_match_creation(self):
        """Test reality match creation."""
        match = RealityMatch(
            scenario_id="test_scenario",
            scenario_name="Test Scenario",
            match_score=0.85,
            matched_fields=["bodily.energy"],
            strategy={"mode": "conservation"},
            confidence=0.9,
        )
        
        assert match.scenario_id == "test_scenario"
        assert match.match_score == 0.85
        assert "bodily.energy" in match.matched_fields
    
    def test_match_serialization(self):
        """Test match serialization."""
        match = RealityMatch(
            scenario_id="test",
            scenario_name="Test",
            match_score=0.75,
            matched_fields=["field1", "field2"],
            strategy={"mode": "defensive"},
            confidence=0.8,
        )
        
        data = match.to_dict()
        
        assert data["scenario_id"] == "test"
        assert data["match_score"] == 0.75
        assert len(data["matched_fields"]) == 2


class TestStrategyComparison:
    """Tests for StrategyComparison dataclass."""
    
    def test_comparison_creation(self):
        """Test strategy comparison creation."""
        comparison = StrategyComparison(
            actual_strategy={"mode": "normal"},
            counterfactual_strategy={"mode": "conservation"},
            actual_expected_outcome=0.7,
            counterfactual_expected_outcome=0.6,
            risk_difference=-0.2,
            cost_difference=0.1,
            recommendation="actual",
            confidence=0.85,
            reason="Actual strategy has higher expected outcome",
        )
        
        assert comparison.recommendation == "actual"
        assert comparison.risk_difference < 0  # Counterfactual less risky
    
    def test_comparison_serialization(self):
        """Test comparison serialization."""
        comparison = StrategyComparison(
            actual_strategy={},
            counterfactual_strategy={},
            actual_expected_outcome=0.5,
            counterfactual_expected_outcome=0.5,
            risk_difference=0.0,
            cost_difference=0.0,
            recommendation="hybrid",
            confidence=0.6,
            reason="Test",
        )
        
        data = comparison.to_dict()
        
        assert "actual_strategy" in data
        assert "recommendation" in data
        assert "confidence" in data


class TestIntegrationWithHOT:
    """Tests for integration with HOT self model."""
    
    def test_integrate_with_hot_no_match(self):
        """Test integration with HOT when no counterfactual matches."""
        hot_model = HOTSelfModel()
        cf_model = CounterfactualSelfModel(hot_self_model=hot_model)
        
        # Normal state
        state = {
            "bodily": {"energy": 0.8, "social_safety": 0.7},
            "cognitive": {"uncertainty": 0.2, "confidence": 0.8},
            "hot": {"control_estimate": 0.7, "conflict_level": 0.1},
        }
        
        modifiers = integrate_with_hot(cf_model, hot_model, state)
        
        assert modifiers["combined"] is True
        assert modifiers["counterfactual_match"] is False
        assert modifiers["strategy_source"] == "hot"
    
    def test_integrate_with_hot_with_match(self):
        """Test integration with HOT when counterfactual matches."""
        hot_model = HOTSelfModel()
        cf_model = CounterfactualSelfModel(hot_self_model=hot_model)
        
        # Low energy state
        state = {
            "bodily": {"energy": 0.2, "social_safety": 0.6},
            "cognitive": {"uncertainty": 0.3, "confidence": 0.7},
            "hot": {"control_estimate": 0.5, "conflict_level": 0.1},
        }
        
        modifiers = integrate_with_hot(cf_model, hot_model, state)
        
        assert modifiers["combined"] is True
        assert modifiers["counterfactual_match"] is True
        assert modifiers["counterfactual_mode"] == "conservation"
        assert modifiers["strategy_source"] == "counterfactual"
    
    def test_apply_counterfactual_to_candidates(self):
        """Test applying counterfactual strategy to candidates."""
        candidates = [
            {"id": "a1", "type": "act", "score": 0.5, "meta": {"risk_level": 0.3}},
            {"id": "a2", "type": "clarify", "score": 0.5},
            {"id": "a3", "type": "simplify_task", "score": 0.5},
        ]
        
        strategy = {
            "mode": "conservation",
            "risk_tolerance": 0.3,
            "preferred_actions": ["simplify_task"],
            "avoided_actions": ["act"],
            "info_seeking_weight": 0.6,
        }
        
        modified = apply_counterfactual_to_candidates(candidates, strategy)
        
        # simplify_task should be boosted
        simplify = next(c for c in modified if c["id"] == "a3")
        assert simplify["score"] > 0.5
        
        # act should be penalized
        act = next(c for c in modified if c["id"] == "a1")
        assert act["score"] < 0.5
        
        # clarify should get info-seeking bonus
        clarify = next(c for c in modified if c["id"] == "a2")
        assert clarify["score"] > 0.5


class TestAdaptiveStrategy:
    """Tests for adaptive strategy computation."""
    
    def test_adaptive_strategy_normal_state(self):
        """Test adaptive strategy for normal state."""
        model = CounterfactualSelfModel()
        
        state = {
            "bodily": {"energy": 0.8, "social_safety": 0.8},
            "cognitive": {"uncertainty": 0.2, "confidence": 0.8},
            "hot": {"control_estimate": 0.7, "conflict_level": 0.1},
        }
        
        strategy = model._compute_adaptive_strategy(state)
        
        assert strategy["mode"] == "normal"
        assert strategy["risk_tolerance"] > 0.5
        assert not strategy["reflection_trigger"]
    
    def test_adaptive_strategy_low_energy(self):
        """Test adaptive strategy for low energy."""
        model = CounterfactualSelfModel()
        
        state = {
            "bodily": {"energy": 0.25, "social_safety": 0.6},
            "cognitive": {"uncertainty": 0.3, "confidence": 0.7},
            "hot": {"control_estimate": 0.5, "conflict_level": 0.0},
        }
        
        strategy = model._compute_adaptive_strategy(state)
        
        assert strategy["mode"] == "conservation"
        assert strategy["risk_tolerance"] < 0.5
        assert "simplify_task" in strategy["preferred_actions"]
    
    def test_adaptive_strategy_high_uncertainty(self):
        """Test adaptive strategy for high uncertainty."""
        model = CounterfactualSelfModel()
        
        state = {
            "bodily": {"energy": 0.7, "social_safety": 0.6},
            "cognitive": {"uncertainty": 0.8, "confidence": 0.3},
            "hot": {"control_estimate": 0.5, "conflict_level": 0.0},
        }
        
        strategy = model._compute_adaptive_strategy(state)
        
        assert strategy["mode"] == "info_seeking"
        assert strategy["info_seeking_weight"] > 0.5
        assert strategy["reflection_trigger"] is True


class TestStateHash:
    """Tests for state hash computation."""
    
    def test_state_hash_consistency(self):
        """Test that same state produces same hash."""
        model = CounterfactualSelfModel()
        
        state = {
            "bodily": {"energy": 0.5},
            "cognitive": {"uncertainty": 0.3},
        }
        
        hash1 = model.compute_state_hash(state)
        hash2 = model.compute_state_hash(state)
        
        assert hash1 == hash2
    
    def test_state_hash_difference(self):
        """Test that different states produce different hashes."""
        model = CounterfactualSelfModel()
        
        state1 = {"bodily": {"energy": 0.5}}
        state2 = {"bodily": {"energy": 0.6}}
        
        hash1 = model.compute_state_hash(state1)
        hash2 = model.compute_state_hash(state2)
        
        assert hash1 != hash2


class TestSerialization:
    """Tests for model serialization."""
    
    def test_model_serialization(self):
        """Test model serialization/deserialization."""
        model = CounterfactualSelfModel()
        
        # Add a custom scenario
        custom = CounterfactualScenario(
            id="custom",
            name="Custom",
            scenario_type=CounterfactualType.STRESS_CONDITION,
            modifications={"test": 0.5},
        )
        model.add_scenario(custom)
        
        # Serialize
        data = model.to_dict()
        
        # Deserialize
        restored = CounterfactualSelfModel.from_dict(data)
        
        assert "custom" in restored.scenarios
        assert restored.scenarios["custom"].name == "Custom"


class TestGlobalInstance:
    """Tests for global instance management."""
    
    def test_get_global_instance(self):
        """Test getting global instance."""
        reset_counterfactual_model()
        
        model = get_counterfactual_model()
        
        assert model is not None
        assert isinstance(model, CounterfactualSelfModel)
    
    def test_reset_global_instance(self):
        """Test resetting global instance."""
        model1 = get_counterfactual_model()
        reset_counterfactual_model()
        model2 = get_counterfactual_model()
        
        # Should be different instances
        assert model1 is not model2


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_empty_state(self):
        """Test handling of empty state."""
        model = CounterfactualSelfModel()
        
        strategy = model.select_strategy({})
        
        # Should return adaptive strategy
        assert strategy["source"] == "adaptive"
    
    def test_partial_state(self):
        """Test handling of partial state."""
        model = CounterfactualSelfModel()
        
        state = {
            "bodily": {"energy": 0.2},  # Only energy provided
        }
        
        strategy = model.select_strategy(state)
        
        # Should still work
        assert "mode" in strategy
    
    def test_update_scenario_strategy(self):
        """Test updating scenario strategy."""
        model = CounterfactualSelfModel()
        
        new_strategy = {"mode": "custom", "risk_tolerance": 0.1}
        result = model.update_scenario_strategy("low_energy", new_strategy)
        
        assert result is True
        assert model.scenarios["low_energy"].strategy == new_strategy
    
    def test_update_nonexistent_scenario(self):
        """Test updating nonexistent scenario."""
        model = CounterfactualSelfModel()
        
        result = model.update_scenario_strategy("nonexistent", {})
        
        assert result is False
    
    def test_remove_nonexistent_scenario(self):
        """Test removing nonexistent scenario."""
        model = CounterfactualSelfModel()
        
        result = model.remove_scenario("nonexistent")
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
