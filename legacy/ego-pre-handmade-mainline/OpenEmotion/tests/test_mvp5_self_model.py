"""
Tests for MVP-5 D4: Self-Model System

Tests cover:
1. ValueWeights - core values and normalization
2. CapabilityBeliefs - capability tracking with confidence
3. Goals - goal management and prioritization
4. SelfModel - integration and decision influence
5. Gradual updates - evidence logging and conflict resolution
6. Cross-scenario consistency
7. Trace/explanation visibility
"""
import pytest
import time
from typing import Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.self_model.legacy import (
    ValueWeights,
    CapabilityBelief,
    CapabilityBeliefs,
    Goal,
    CurrentGoals,
    EvidenceEntry,
    UpdateLog,
    SelfModel,
    get_self_model,
    reset_self_model,
    apply_self_model_to_decision
)


# ============================================================================
# ValueWeights Tests
# ============================================================================

class TestValueWeights:
    """Test ValueWeights functionality."""
    
    def test_default_values(self):
        """Test: default values are set correctly."""
        values = ValueWeights()
        assert values.connection == 0.7
        assert values.honesty == 0.8
        assert values.safety == 0.6
        assert values.growth == 0.5
    
    def test_get_dominant(self):
        """Test: dominant value is identified correctly."""
        values = ValueWeights(connection=0.9, honesty=0.3, safety=0.4, growth=0.2)
        name, weight = values.get_dominant()
        assert name == "connection"
        assert weight == 0.9
    
    def test_normalize(self):
        """Test: normalization produces weights summing to 1."""
        values = ValueWeights(connection=0.8, honesty=0.4, safety=0.4, growth=0.4)
        normalized = values.normalize()
        total = normalized.connection + normalized.honesty + normalized.safety + normalized.growth
        assert abs(total - 1.0) < 0.001
    
    def test_normalize_zero_total(self):
        """Test: normalization handles zero total gracefully."""
        values = ValueWeights(connection=0, honesty=0, safety=0, growth=0)
        normalized = values.normalize()
        assert normalized.connection == 0.25
        assert normalized.honesty == 0.25
    
    def test_value_bounds(self):
        """Test: values are clamped to [0, 1]."""
        # Pydantic should handle this, but let's verify
        values = ValueWeights(connection=1.5, honesty=-0.5)
    def test_value_bounds(self):
        """Test: values are validated to [0, 1] by pydantic."""
        # Pydantic validates bounds - values outside range raise error
        with pytest.raises(Exception):
            ValueWeights(connection=1.5)
        with pytest.raises(Exception):
            ValueWeights(honesty=-0.5)
        
        # Valid values work
        values = ValueWeights(connection=1.0, honesty=0.0)
        assert values.connection == 1.0
        assert values.honesty == 0.0
# CapabilityBelief Tests
# ============================================================================

class TestCapabilityBelief:
    """Test CapabilityBelief functionality."""
    
    def test_default_values(self):
        """Test: default capability belief values."""
        belief = CapabilityBelief()
        assert belief.capability == 0.5
        assert belief.confidence == 0.3
        assert belief.evidence_count == 0
    
    def test_effective_capability(self):
        """Test: effective capability combines capability and confidence."""
        belief = CapabilityBelief(capability=0.8, confidence=0.5)
        assert belief.effective_capability() == 0.4  # 0.8 * 0.5
    
    def test_effective_capability_zero_confidence(self):
        """Test: zero confidence means zero effective capability."""
        belief = CapabilityBelief(capability=1.0, confidence=0.0)
        assert belief.effective_capability() == 0.0


class TestCapabilityBeliefs:
    """Test CapabilityBeliefs collection."""
    
    def test_default_capabilities(self):
        """Test: default capabilities are initialized."""
        caps = CapabilityBeliefs()
        assert caps.clarify.capability == 0.7
        assert caps.repair.capability == 0.6
        assert caps.set_boundary.capability == 0.8
    
    def test_get_existing(self):
        """Test: get returns existing capability."""
        caps = CapabilityBeliefs()
        belief = caps.get("clarify")
        assert belief is not None
        assert belief.capability == 0.7
    
    def test_get_nonexistent(self):
        """Test: get returns None for nonexistent capability."""
        caps = CapabilityBeliefs()
        belief = caps.get("nonexistent")
        assert belief is None
    
    def test_get_action_bias_positive(self):
        """Test: action bias is positive for high capability/confidence."""
        caps = CapabilityBeliefs()
        caps.withdraw.capability = 0.9
        caps.withdraw.confidence = 0.8
        bias = caps.get_action_bias("withdraw")
        assert bias > 0
    
    def test_get_action_bias_negative(self):
        """Test: action bias is negative for low capability."""
        caps = CapabilityBeliefs()
        caps.learn.capability = 0.2
        caps.learn.confidence = 0.8
        bias = caps.get_action_bias("learn")
        assert bias < 0
    
    def test_get_action_bias_unknown(self):
        """Test: action bias is zero for unknown action."""
        caps = CapabilityBeliefs()
        bias = caps.get_action_bias("unknown_action")
        assert bias == 0.0


# ============================================================================
# Goal Tests
# ============================================================================

class TestGoal:
    """Test Goal functionality."""
    
    def test_default_values(self):
        """Test: default goal values."""
        goal = Goal(id="test", description="Test goal")
        assert goal.priority == 0.5
        assert goal.progress == 0.0
        assert goal.active is True
    
    def test_is_urgent_high_priority(self):
        """Test: high priority goal is urgent."""
        goal = Goal(id="test", description="Test", priority=0.9)
        assert goal.is_urgent() is True
    
    def test_is_urgent_near_deadline(self):
        """Test: goal near deadline is urgent."""
        goal = Goal(id="test", description="Test", deadline=time.time() + 1800)
        assert goal.is_urgent() is True
    
    def test_is_urgent_inactive(self):
        """Test: inactive goal is not urgent."""
        goal = Goal(id="test", description="Test", priority=0.9, active=False)
        assert goal.is_urgent() is False
    
    def test_effective_priority_progress_boost(self):
        """Test: nearly complete goals get priority boost."""
        goal = Goal(id="test", description="Test", priority=0.5, progress=0.9)
        effective = goal.effective_priority()
        assert effective > 0.5  # Should be boosted
    
    def test_effective_priority_stalled(self):
        """Test: stalled goals get priority reduction."""
        goal = Goal(id="test", description="Test", priority=0.5, progress=0.1)
        effective = goal.effective_priority()
        assert effective < 0.5  # Should be reduced


class TestCurrentGoals:
    """Test CurrentGoals management."""
    
    def test_add_goal(self):
        """Test: can add goal."""
        goals = CurrentGoals()
        goal = Goal(id="test", description="Test")
        assert goals.add_goal(goal) is True
        assert len(goals.goals) == 1
    
    def test_add_goal_at_capacity(self):
        """Test: cannot add goal at capacity."""
        goals = CurrentGoals(max_goals=2)
        goals.add_goal(Goal(id="1", description="One"))
        goals.add_goal(Goal(id="2", description="Two"))
        result = goals.add_goal(Goal(id="3", description="Three"))
        assert result is False
    
    def test_get_top_priority(self):
        """Test: get top priority goals."""
        goals = CurrentGoals()
        goals.add_goal(Goal(id="low", description="Low", priority=0.3))
        goals.add_goal(Goal(id="high", description="High", priority=0.9))
        goals.add_goal(Goal(id="mid", description="Mid", priority=0.6))
        
        top = goals.get_top_priority(2)
        assert len(top) == 2
        assert top[0].id == "high"
        assert top[1].id == "mid"
    
    def test_get_urgent(self):
        """Test: get urgent goals."""
        goals = CurrentGoals()
        goals.add_goal(Goal(id="urgent", description="Urgent", priority=0.9))
        goals.add_goal(Goal(id="normal", description="Normal", priority=0.5))
        
        urgent = goals.get_urgent()
        assert len(urgent) == 1
        assert urgent[0].id == "urgent"
    
    def test_update_progress(self):
        """Test: can update goal progress."""
        goals = CurrentGoals()
        goals.add_goal(Goal(id="test", description="Test"))
        assert goals.update_progress("test", 0.5) is True
        assert goals.goals[0].progress == 0.5
    
    def test_deactivate(self):
        """Test: can deactivate goal."""
        goals = CurrentGoals()
        goals.add_goal(Goal(id="test", description="Test"))
        assert goals.deactivate("test") is True
        assert goals.goals[0].active is False


# ============================================================================
# SelfModel Tests
# ============================================================================

class TestSelfModelInitialization:
    """Test SelfModel initialization."""
    
    def test_default_values(self):
        """Test: default self-model values."""
        model = SelfModel()
        assert model.identity_stability == 0.5
        assert model.update_count == 0
        assert len(model.update_history) == 0
    
    def test_default_values_structure(self):
        """Test: default values structure."""
        model = SelfModel()
        assert model.values.connection == 0.7
        assert model.values.honesty == 0.8
        assert model.capabilities.withdraw.capability == 0.9


class TestSelfModelActionBias:
    """Test SelfModel action bias calculations."""
    
    def test_get_action_bias_withdraw(self):
        """Test: withdraw has positive bias (high capability)."""
        model = SelfModel()
        bias = model.get_action_bias("withdraw")
        assert bias > 0
    
    def test_get_action_bias_learn(self):
        """Test: learn has lower bias (low capability)."""
        model = SelfModel()
        bias = model.get_action_bias("learn")
        assert bias < model.get_action_bias("withdraw")
    
    def test_get_action_bias_stability_effect(self):
        """Test: identity stability affects bias strength."""
        model_low = SelfModel()
        model_low.identity_stability = 0.2
        
        model_high = SelfModel()
        model_high.identity_stability = 0.9
        
        bias_low = model_low.get_action_bias("withdraw")
        bias_high = model_high.get_action_bias("withdraw")
        
        # Higher stability should produce stronger bias
        assert abs(bias_high) > abs(bias_low)


class TestSelfModelDecisionLogic:
    """Test SelfModel decision logic."""
    
    def test_should_reflect_high_uncertainty(self):
        """Test: should reflect when uncertainty is high."""
        model = SelfModel()
        assert model.should_reflect(uncertainty=0.9, prediction_error=0.1) is True
    
    def test_should_reflect_low_uncertainty(self):
        """Test: should not reflect when uncertainty is low."""
        model = SelfModel()
        assert model.should_reflect(uncertainty=0.3, prediction_error=0.1) is False
    
    def test_should_reflect_growth_value(self):
        """Test: growth value affects reflection threshold."""
        model_low = SelfModel()
        model_low.values.growth = 0.2
        
        model_high = SelfModel()
        model_high.values.growth = 0.9
        
        # Higher growth = lower threshold = more likely to reflect
        assert model_high.should_reflect(uncertainty=0.6, prediction_error=0.1) is True
        assert model_low.should_reflect(uncertainty=0.6, prediction_error=0.1) is False
    
    def test_should_clarify_high_uncertainty(self):
        """Test: should clarify when uncertainty is high."""
        model = SelfModel()
        assert model.should_clarify(uncertainty=0.8, social_threat=0.3) is True
    
    def test_should_clarify_high_threat(self):
        """Test: should not clarify when social threat is high."""
        model = SelfModel()
        assert model.should_clarify(uncertainty=0.9, social_threat=0.8) is False
    
    def test_should_clarify_honesty_value(self):
        """Test: honesty value affects clarification threshold."""
        model = SelfModel()
        model.values.honesty = 0.9  # High honesty = more willing to clarify
        
        # Should clarify at lower uncertainty with high honesty
        assert model.should_clarify(uncertainty=0.5, social_threat=0.3) is True


class TestSelfModelStrategies:
    """Test SelfModel strategy selection."""
    
    def test_get_repair_strategy_direct(self):
        """Test: direct repair for high connection + bond."""
        model = SelfModel()
        model.values.connection = 0.9
        strategy = model.get_repair_strategy(relationship_bond=0.6, relationship_grudge=0.2)
        assert strategy == "direct"
    
    def test_get_repair_strategy_boundary_first(self):
        """Test: boundary_first for high safety + grudge."""
        model = SelfModel()
        model.values.safety = 0.9
        strategy = model.get_repair_strategy(relationship_bond=0.6, relationship_grudge=0.7)
        assert strategy == "boundary_first"
    
    def test_get_repair_strategy_withdraw(self):
        """Test: withdraw for very high grudge."""
        model = SelfModel()
        strategy = model.get_repair_strategy(relationship_bond=0.3, relationship_grudge=0.8)
        assert strategy == "withdraw"
    
    def test_get_boundary_strategy_immediate(self):
        """Test: immediate boundary for high threat."""
        model = SelfModel()
        strategy = model.get_boundary_strategy(social_threat=0.8, relationship_trust=0.5)
        assert strategy == "immediate"
    
    def test_get_boundary_strategy_firm(self):
        """Test: firm boundary for low trust + high safety."""
        model = SelfModel()
        model.values.safety = 0.9
        strategy = model.get_boundary_strategy(social_threat=0.4, relationship_trust=0.2)
        assert strategy == "firm"
    
    def test_get_boundary_strategy_soft(self):
        """Test: soft boundary for high connection."""
        model = SelfModel()
        model.values.connection = 0.9
        strategy = model.get_boundary_strategy(social_threat=0.4, relationship_trust=0.5)
        assert strategy == "soft"


# ============================================================================
# Gradual Update Tests
# ============================================================================

class TestGradualUpdates:
    """Test gradual update mechanism."""
    
    def test_gradual_update_small_step(self):
        """Test: update takes small step toward target."""
        model = SelfModel()
        model.last_update = 0  # Bypass rate limit
        
        old_value = model.values.connection
        model.update_values(connection=1.0, reason="test")
        
        new_value = model.values.connection
        assert new_value > old_value  # Moved toward 1.0
        assert new_value < 1.0  # But didn't reach it immediately
    
    def test_gradual_update_step_size_decreases(self):
        """Test: step size decreases with more evidence."""
        model = SelfModel()
        model.last_update = 0
        
        # First update
        model.update_values(connection=1.0, reason="first")
        step1 = model.values.connection - 0.7  # From default 0.7
        
        model.last_update = 0
        # Second update
        old = model.values.connection
        model.update_values(connection=1.0, reason="second")
        step2 = model.values.connection - old
        
        # Second step should be smaller
        assert step2 < step1
    
    def test_rate_limiting(self):
        """Test: updates are rate limited."""
        model = SelfModel()
        model.last_update = time.time()  # Just updated
        
        result = model.update_values(connection=1.0, reason="test")
        assert result is False
    
    def test_update_logging(self):
        """Test: updates are logged."""
        model = SelfModel()
        model.last_update = 0
        
        evidence = EvidenceEntry(source="test", value=1.0)
        model.update_values(connection=0.9, evidence=evidence, reason="test update")
        
        assert len(model.update_history) > 0
        assert model.update_history[0].field_name == "values.connection"


class TestConflictResolution:
    """Test conflict resolution mechanism."""
    
    def test_resolve_conflict_weighted_average(self):
        """Test: conflict resolved via weighted average."""
        model = SelfModel()
        
        evidence_a = EvidenceEntry(source="a", value=0.8, weight=2.0)
        evidence_b = EvidenceEntry(source="b", value=0.4, weight=1.0)
        
        resolved = model.resolve_conflict("test_field", evidence_a, evidence_b)
        
        # Should be closer to evidence_a (higher weight)
        assert resolved > 0.5
        assert resolved < 0.8
    
    def test_resolve_conflict_recency_bonus(self):
        """Test: recent evidence gets bonus."""
        model = SelfModel()
        
        old_time = time.time() - 7200  # 2 hours ago
        new_time = time.time()
        
        evidence_old = EvidenceEntry(source="old", value=0.2, weight=1.0, timestamp=old_time)
        evidence_new = EvidenceEntry(source="new", value=0.8, weight=1.0, timestamp=new_time)
        
        resolved = model.resolve_conflict("test_field", evidence_old, evidence_new)
        
        # Should be closer to new evidence due to recency bonus
        assert resolved > 0.5


# ============================================================================
# Cross-Scenario Consistency Tests
# ============================================================================

class TestCrossScenarioConsistency:
    """Test consistency across different scenarios."""
    
    def test_consistent_repair_strategy_same_input(self):
        """Test: same inputs produce same repair strategy."""
        model1 = SelfModel()
        model2 = SelfModel()
        
        strategy1 = model1.get_repair_strategy(relationship_bond=0.5, relationship_grudge=0.3)
        strategy2 = model2.get_repair_strategy(relationship_bond=0.5, relationship_grudge=0.3)
        
        assert strategy1 == strategy2
    
    def test_consistent_boundary_strategy_same_input(self):
        """Test: same inputs produce same boundary strategy."""
        model1 = SelfModel()
        model2 = SelfModel()
        
        strategy1 = model1.get_boundary_strategy(social_threat=0.4, relationship_trust=0.5)
        strategy2 = model2.get_boundary_strategy(social_threat=0.4, relationship_trust=0.5)
        
        assert strategy1 == strategy2
    
    def test_consistent_action_bias_same_input(self):
        """Test: same inputs produce same action bias."""
        model1 = SelfModel()
        model2 = SelfModel()
        
        bias1 = model1.get_action_bias("withdraw")
        bias2 = model2.get_action_bias("withdraw")
        
        assert bias1 == bias2
    
    def test_gradual_update_consistency(self):
        """Test: gradual updates are deterministic."""
        model1 = SelfModel()
        model2 = SelfModel()
        
        model1.last_update = 0
        model2.last_update = 0
        
        model1.update_values(connection=0.9, reason="test")
        model2.update_values(connection=0.9, reason="test")
        
        assert model1.values.connection == model2.values.connection


# ============================================================================
# Explanation and Trace Tests
# ============================================================================

class TestExplanation:
    """Test explanation generation."""
    
    def test_get_explanation_structure(self):
        """Test: explanation has correct structure."""
        model = SelfModel()
        explanation = model.get_explanation()
        
        assert "dominant_value" in explanation
        assert "top_capabilities" in explanation
        assert "top_goals" in explanation
        assert "identity_stability" in explanation
    
    def test_get_explanation_dominant_value(self):
        """Test: explanation includes dominant value."""
        model = SelfModel()
        model.values.honesty = 0.95  # Make honesty dominant
        
        explanation = model.get_explanation()
        assert explanation["dominant_value"]["name"] == "honesty"
    
    def test_to_trace_dict_structure(self):
        """Test: trace dict has correct structure."""
        model = SelfModel()
        trace = model.to_trace_dict()
        
        assert "values" in trace
        assert "capabilities" in trace
        assert "goals" in trace
        assert "identity_stability" in trace
        assert "explanation" in trace


# ============================================================================
# Integration Tests
# ============================================================================

class TestApplyToDecision:
    """Test applying self-model to decisions."""
    
    def test_apply_adds_bias(self):
        """Test: applying adds self_model_bias."""
        decision = {"action": "withdraw"}
        result = apply_self_model_to_decision(decision)
        
        assert "self_model_bias" in result
        assert "self_model_explanation" in result
    
    def test_apply_adds_repair_strategy(self):
        """Test: applying adds repair strategy for repair intent."""
        decision = {
            "intent": "repair",
            "relationship": {"bond": 0.5, "grudge": 0.3, "trust": 0.5}
        }
        result = apply_self_model_to_decision(decision)
        
        assert "repair_strategy" in result
    
    def test_apply_adds_boundary_strategy(self):
        """Test: applying adds boundary strategy for boundary intent."""
        decision = {
            "intent": "set_boundary",
            "social_threat": 0.4,
            "relationship": {"bond": 0.5, "grudge": 0.3, "trust": 0.5}
        }
        result = apply_self_model_to_decision(decision)
        
        assert "boundary_strategy" in result


# ============================================================================
# Global Instance Tests
# ============================================================================

class TestGlobalInstance:
    """Test global self-model instance."""
    
    def test_get_self_model_creates_instance(self):
        """Test: get_self_model creates instance."""
        reset_self_model()
        model = get_self_model()
        assert model is not None
        assert isinstance(model, SelfModel)
    
    def test_reset_self_model(self):
        """Test: reset clears instance."""
        model1 = get_self_model()
        reset_self_model()
        model2 = get_self_model()
        
        assert model1 is not model2


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_goals(self):
        """Test: empty goals handled gracefully."""
        model = SelfModel()
        top = model.goals.get_top_priority(3)
        assert top == []
    
    def test_extreme_values(self):
        """Test: extreme values handled gracefully."""
        model = SelfModel()
        model.last_update = 0
        
        # Should not crash with extreme values
        model.update_values(connection=1.0, honesty=0.0, safety=1.0, growth=0.0)
        
        assert model.values.connection >= 0.89
    
    def test_rapid_updates(self):
        """Test: rapid updates are rate limited."""
        model = SelfModel()
        model.last_update = 0
        
        # First update should work
        assert model.update_values(connection=0.8, reason="first") is True
        
        # Immediate second update should be rate limited
        assert model.update_values(connection=0.9, reason="second") is False


# Count tests
# ValueWeights: 5 tests
# CapabilityBeliefs: 7 tests
# Goals: 8 tests
# SelfModel initialization: 2 tests
# SelfModel action bias: 3 tests
# SelfModel decision logic: 6 tests
# SelfModel strategies: 6 tests
# Gradual updates: 4 tests
# Conflict resolution: 2 tests
# Cross-scenario consistency: 4 tests
# Explanation: 3 tests
# Integration: 3 tests
# Global instance: 2 tests
# Edge cases: 3 tests
# Total: 58 tests

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
