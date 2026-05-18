"""
MVP-6.2 D4 Tests: Persistence Constraint (Self-Maintenance Objective)

Tests for:
- Body stability metrics (energy low, safety stress, focus fatigue)
- Relationship asset metrics (bond-based harm avoidance, repair sensitivity)
- Learning metrics (stagnation detection, info gain tracking)
- Persistence decision context (strategy selection, cost evaluation)
- Persistence constraint integration
- Recovery dynamics (collapse → recovery cycles)
- Strategy selection under stress
- Traceability and telemetry

≥30 tests + ≥2 scenarios
"""
import pytest
import time
from emotiond.persistence import (
    PersistenceConstraint, PersistenceStrategy, PersistenceCost,
    BodyStabilityMetrics, RelationshipAssetMetrics, LearningMetrics,
    PersistenceDecisionContext,
    get_persistence_constraint, reset_persistence_constraint,
)


# =============================================================================
# BodyStabilityMetrics Tests
# =============================================================================

class TestBodyStabilityMetrics:
    """Test body stability tracking."""
    
    def test_default_thresholds(self):
        """BodyStabilityMetrics has sensible default thresholds."""
        metrics = BodyStabilityMetrics()
        assert metrics.energy_low_threshold == 0.3
        assert metrics.safety_stress_high_threshold == 0.7
        assert metrics.focus_fatigue_high_threshold == 0.8
    
    def test_custom_thresholds(self):
        """BodyStabilityMetrics accepts custom thresholds."""
        metrics = BodyStabilityMetrics(
            energy_low_threshold=0.2,
            safety_stress_high_threshold=0.6,
            focus_fatigue_high_threshold=0.75,
        )
        assert metrics.energy_low_threshold == 0.2
        assert metrics.safety_stress_high_threshold == 0.6
        assert metrics.focus_fatigue_high_threshold == 0.75
    
    def test_energy_low_episode_detection(self):
        """Energy low episodes are detected correctly."""
        metrics = BodyStabilityMetrics(energy_low_threshold=0.3)
        
        # Normal energy - no episode
        events = metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        assert not metrics.in_energy_low_episode
        assert metrics.energy_low_episodes == 0
        
        # Low energy - episode starts
        events = metrics.update(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
        assert metrics.in_energy_low_episode
        assert metrics.energy_low_episodes == 1
        assert "energy_low" in events["new_episodes"]
        
        # Still low - episode continues
        events = metrics.update(energy=0.25, safety_stress=0.5, focus_fatigue=0.5)
        assert metrics.in_energy_low_episode
        assert metrics.energy_low_episodes == 1  # Still 1, not a new episode
        
        # Back to normal - episode ends
        events = metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        assert not metrics.in_energy_low_episode
        assert "energy_low" in events["ended_episodes"]
    
    def test_safety_stress_spike_detection(self):
        """Safety stress spikes are detected correctly."""
        metrics = BodyStabilityMetrics(safety_stress_high_threshold=0.7)
        
        # Normal stress
        events = metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        assert not metrics.in_safety_stress_spike
        
        # High stress - spike starts
        events = metrics.update(energy=0.5, safety_stress=0.8, focus_fatigue=0.5)
        assert metrics.in_safety_stress_spike
        assert metrics.safety_stress_spikes == 1
        assert "safety_stress_spike" in events["new_episodes"]
    
    def test_focus_fatigue_collapse_detection(self):
        """Focus fatigue collapses are detected correctly."""
        metrics = BodyStabilityMetrics(focus_fatigue_high_threshold=0.8)
        
        # Normal focus
        events = metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        assert not metrics.in_focus_collapse
        
        # High fatigue - collapse starts
        events = metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.9)
        assert metrics.in_focus_collapse
        assert metrics.focus_fatigue_collapses == 1
        assert "focus_collapse" in events["new_episodes"]
    
    def test_stability_score_perfect(self):
        """Stability score is 1.0 when all is well."""
        metrics = BodyStabilityMetrics()
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        score = metrics.get_stability_score()
        assert score == 1.0
    
    def test_stability_score_with_active_episodes(self):
        """Stability score decreases with active episodes."""
        metrics = BodyStabilityMetrics()
        
        # All episodes active
        metrics.update(energy=0.2, safety_stress=0.8, focus_fatigue=0.9)
        score = metrics.get_stability_score()
        assert score < 1.0
        assert score > 0.0  # But not zero
    
    def test_stability_score_with_history(self):
        """Stability score decreases with episode history."""
        metrics = BodyStabilityMetrics()
        
        # Create multiple episodes
        for _ in range(5):
            metrics.update(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
            metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        score = metrics.get_stability_score()
        assert score < 1.0
        assert metrics.energy_low_episodes == 5
    
    def test_is_in_collapse(self):
        """is_in_collapse returns True when any episode is active."""
        metrics = BodyStabilityMetrics()
        
        # No collapse
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        assert not metrics.is_in_collapse()
        
        # Energy low only
        metrics.update(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
        assert metrics.is_in_collapse()
        
        # Reset
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        # Safety stress only
        metrics.update(energy=0.5, safety_stress=0.8, focus_fatigue=0.5)
        assert metrics.is_in_collapse()
        
        # Reset
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        # Focus fatigue only
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.9)
        assert metrics.is_in_collapse()
    
    def test_time_since_last_collapse(self):
        """Time since last collapse is tracked."""
        metrics = BodyStabilityMetrics()
        
        # No collapse yet
        assert metrics.time_since_last_collapse() is None
        
        # Create and end collapse
        metrics.update(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
        time.sleep(0.01)
        metrics.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        # Should have time since collapse
        elapsed = metrics.time_since_last_collapse()
        assert elapsed is not None
        assert elapsed >= 0.0
    
    def test_to_dict(self):
        """BodyStabilityMetrics serializes correctly."""
        metrics = BodyStabilityMetrics()
        metrics.update(energy=0.2, safety_stress=0.8, focus_fatigue=0.9)
        
        data = metrics.to_dict()
        assert "energy_low_episodes" in data
        assert "safety_stress_spikes" in data
        assert "focus_fatigue_collapses" in data
        assert "stability_score" in data
        assert data["is_in_collapse"] is True


# =============================================================================
# RelationshipAssetMetrics Tests
# =============================================================================

class TestRelationshipAssetMetrics:
    """Test relationship asset tracking."""
    
    def test_update_bond(self):
        """Bond values are updated correctly."""
        metrics = RelationshipAssetMetrics()
        metrics.update_bond("target_1", 0.8)
        
        assert metrics.target_bonds["target_1"] == 0.8
    
    def test_update_reliability(self):
        """Reliability values are updated correctly."""
        metrics = RelationshipAssetMetrics()
        metrics.update_reliability("target_1", 0.9)
        
        assert metrics.target_reliability["target_1"] == 0.9
    
    def test_record_harm(self):
        """Harm events are recorded correctly."""
        metrics = RelationshipAssetMetrics()
        metrics.record_harm("target_1")
        metrics.record_harm("target_1")
        
        assert metrics.harm_events["target_1"] == 2
    
    def test_record_repair_attempt(self):
        """Repair attempts are recorded correctly."""
        metrics = RelationshipAssetMetrics()
        metrics.record_repair_attempt("target_1", success=True)
        metrics.record_repair_attempt("target_1", success=False)
        
        assert metrics.repair_attempts["target_1"] == 2
        assert metrics.repair_successes["target_1"] == 1
    
    def test_get_bond_level_high(self):
        """High bond level is detected."""
        metrics = RelationshipAssetMetrics(high_bond_threshold=0.7)
        metrics.update_bond("target_1", 0.8)
        
        assert metrics.get_bond_level("target_1") == "high"
    
    def test_get_bond_level_medium(self):
        """Medium bond level is detected."""
        metrics = RelationshipAssetMetrics(high_bond_threshold=0.7, medium_bond_threshold=0.4)
        metrics.update_bond("target_1", 0.5)
        
        assert metrics.get_bond_level("target_1") == "medium"
    
    def test_get_bond_level_low(self):
        """Low bond level is detected."""
        metrics = RelationshipAssetMetrics(high_bond_threshold=0.7, medium_bond_threshold=0.4)
        metrics.update_bond("target_1", 0.2)
        
        assert metrics.get_bond_level("target_1") == "low"
    
    def test_get_harm_avoidance_weight_high_bond(self):
        """Harm avoidance is higher for high bond targets."""
        metrics = RelationshipAssetMetrics(high_bond_threshold=0.7)
        metrics.update_bond("high_bond", 0.9)
        metrics.update_bond("low_bond", 0.3)
        
        high_avoidance = metrics.get_harm_avoidance_weight("high_bond")
        low_avoidance = metrics.get_harm_avoidance_weight("low_bond")
        
        assert high_avoidance > low_avoidance
        assert high_avoidance > 0.5
    
    def test_get_repair_sensitivity_high_bond(self):
        """Repair sensitivity is higher for high bond targets."""
        metrics = RelationshipAssetMetrics(high_bond_threshold=0.7)
        metrics.update_bond("high_bond", 0.9)
        metrics.update_bond("low_bond", 0.3)
        
        high_sensitivity = metrics.get_repair_sensitivity("high_bond")
        low_sensitivity = metrics.get_repair_sensitivity("low_bond")
        
        assert high_sensitivity > low_sensitivity
    
    def test_get_repair_sensitivity_with_harm_history(self):
        """Repair sensitivity increases with harm history."""
        metrics = RelationshipAssetMetrics()
        metrics.update_bond("target_1", 0.5)
        
        base_sensitivity = metrics.get_repair_sensitivity("target_1")
        
        # Add harm history
        metrics.record_harm("target_1")
        metrics.record_harm("target_1")
        
        enhanced_sensitivity = metrics.get_repair_sensitivity("target_1")
        assert enhanced_sensitivity > base_sensitivity
    
    def test_get_asset_value(self):
        """Asset value combines bond and reliability."""
        metrics = RelationshipAssetMetrics()
        metrics.update_bond("target_1", 0.8)
        metrics.update_reliability("target_1", 0.9)
        
        asset = metrics.get_asset_value("target_1")
        assert asset > 0.0
        assert asset <= 1.0
    
    def test_get_asset_value_penalizes_harm(self):
        """Asset value decreases with harm history."""
        metrics = RelationshipAssetMetrics()
        metrics.update_bond("target_1", 0.8)
        metrics.update_reliability("target_1", 0.9)
        
        base_asset = metrics.get_asset_value("target_1")
        
        # Add harm
        metrics.record_harm("target_1")
        metrics.record_harm("target_1")
        
        reduced_asset = metrics.get_asset_value("target_1")
        assert reduced_asset < base_asset


# =============================================================================
# LearningMetrics Tests
# =============================================================================

class TestLearningMetrics:
    """Test learning/stagnation tracking."""
    
    def test_add_info_gain(self):
        """Info gain is added to window."""
        metrics = LearningMetrics(window_size=5)
        metrics.add_info_gain(0.5)
        
        assert len(metrics.info_gain_window) == 1
        assert metrics.info_gain_window[0] == 0.5
    
    def test_window_size_limit(self):
        """Window respects size limit."""
        metrics = LearningMetrics(window_size=3)
        
        for i in range(5):
            metrics.add_info_gain(float(i) / 10)
        
        assert len(metrics.info_gain_window) == 3
    
    def test_get_average_info_gain(self):
        """Average info gain is calculated correctly."""
        metrics = LearningMetrics()
        metrics.add_info_gain(0.2)
        metrics.add_info_gain(0.4)
        metrics.add_info_gain(0.6)
        
        avg = metrics.get_average_info_gain()
        assert avg == pytest.approx(0.4, abs=0.01)
    
    def test_stagnation_detection(self):
        """Stagnation is detected with low info gain."""
        metrics = LearningMetrics(window_size=10, stagnation_threshold=0.1)
        
        # Add enough low info gain measurements
        for _ in range(6):
            metrics.add_info_gain(0.05)
        
        is_stagnant = metrics.check_stagnation()
        assert is_stagnant is True
        assert metrics.is_stagnant is True
    
    def test_stagnation_recovery(self):
        """Stagnation ends with high info gain."""
        metrics = LearningMetrics(window_size=10, stagnation_threshold=0.1)
        
        # Enter stagnation
        for _ in range(6):
            metrics.add_info_gain(0.05)
        metrics.check_stagnation()
        assert metrics.is_stagnant is True
        
        # Recover with high info gain
        for _ in range(6):
            metrics.add_info_gain(0.5)
        metrics.check_stagnation()
        assert metrics.is_stagnant is False
    
    def test_learning_burst_detection(self):
        """Learning burst is detected and timestamped."""
        metrics = LearningMetrics()
        
        assert metrics.last_learning_burst is None
        
        metrics.add_info_gain(0.5)  # Above burst threshold
        assert metrics.last_learning_burst is not None
    
    def test_get_learning_score_perfect(self):
        """Learning score is high when learning well."""
        metrics = LearningMetrics()
        
        for _ in range(10):
            metrics.add_info_gain(0.5)
        
        score = metrics.get_learning_score()
        assert score > 0.7
    
    def test_get_learning_score_stagnant(self):
        """Learning score is low when stagnant."""
        metrics = LearningMetrics(window_size=10, stagnation_threshold=0.1)
        
        for _ in range(10):
            metrics.add_info_gain(0.05)
        metrics.check_stagnation()
        
        score = metrics.get_learning_score()
        assert score < 0.8


# =============================================================================
# PersistenceDecisionContext Tests
# =============================================================================

class TestPersistenceDecisionContext:
    """Test persistence decision context."""
    
    def test_get_overall_persistence_score(self):
        """Overall score combines all metrics."""
        body = BodyStabilityMetrics()
        relationship = RelationshipAssetMetrics()
        learning = LearningMetrics()
        
        context = PersistenceDecisionContext(
            body_metrics=body,
            relationship_metrics=relationship,
            learning_metrics=learning,
            target_id="target_1",
        )
        
        # Set up some state
        body.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        relationship.update_bond("target_1", 0.8)
        
        score = context.get_overall_persistence_score()
        assert 0.0 <= score <= 1.0
    
    def test_should_be_conservative_critical_body(self):
        """Conservative strategy triggered by critical body instability."""
        body = BodyStabilityMetrics()
        relationship = RelationshipAssetMetrics()
        learning = LearningMetrics()
        
        # Create critical instability
        body.update(energy=0.1, safety_stress=0.9, focus_fatigue=0.95)
        
        context = PersistenceDecisionContext(
            body_metrics=body,
            relationship_metrics=relationship,
            learning_metrics=learning,
        )
        
        should_conservative, reason = context.should_be_conservative()
        assert should_conservative is True
        assert "body_instability" in reason or "collapse" in reason
    
    def test_should_be_conservative_normal(self):
        """Normal state doesn't trigger conservative."""
        body = BodyStabilityMetrics()
        relationship = RelationshipAssetMetrics()
        learning = LearningMetrics()
        
        body.update(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        context = PersistenceDecisionContext(
            body_metrics=body,
            relationship_metrics=relationship,
            learning_metrics=learning,
        )
        
        should_conservative, reason = context.should_be_conservative()
        assert should_conservative is False
    
    def test_should_prioritize_repair_high_bond_with_harm(self):
        """Repair prioritized for high bond with harm history."""
        body = BodyStabilityMetrics()
        relationship = RelationshipAssetMetrics(high_bond_threshold=0.7)
        learning = LearningMetrics()
        
        relationship.update_bond("target_1", 0.8)
        relationship.record_harm("target_1")
        
        context = PersistenceDecisionContext(
            body_metrics=body,
            relationship_metrics=relationship,
            learning_metrics=learning,
            target_id="target_1",
        )
        
        should_repair, reason = context.should_prioritize_repair()
        assert should_repair is True
        assert "high_bond" in reason or "harm" in reason
    
    def test_should_prioritize_repair_no_target(self):
        """No repair priority without target."""
        body = BodyStabilityMetrics()
        relationship = RelationshipAssetMetrics()
        learning = LearningMetrics()
        
        context = PersistenceDecisionContext(
            body_metrics=body,
            relationship_metrics=relationship,
            learning_metrics=learning,
            target_id=None,
        )
        
        should_repair, reason = context.should_prioritize_repair()
        assert should_repair is False


# =============================================================================
# PersistenceConstraint Tests
# =============================================================================

class TestPersistenceConstraint:
    """Test main persistence constraint system."""
    
    def test_initialization(self):
        """PersistenceConstraint initializes correctly."""
        pc = PersistenceConstraint()
        assert pc.body_metrics is not None
        assert pc.relationship_metrics is not None
        assert pc.learning_metrics is not None
    
    def test_update_body_state(self):
        """Body state updates propagate correctly."""
        pc = PersistenceConstraint()
        events = pc.update_body_state(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
        
        assert "new_episodes" in events
        assert pc.body_metrics.in_energy_low_episode is True
    
    def test_update_relationship(self):
        """Relationship updates work correctly."""
        pc = PersistenceConstraint()
        pc.update_relationship("target_1", bond=0.8, reliability=0.9)
        
        assert pc.relationship_metrics.target_bonds["target_1"] == 0.8
        assert pc.relationship_metrics.target_reliability["target_1"] == 0.9
    
    def test_record_info_gain(self):
        """Info gain recording works correctly."""
        pc = PersistenceConstraint()
        pc.record_info_gain(0.5)
        
        assert len(pc.learning_metrics.info_gain_window) == 1
    
    def test_record_harm(self):
        """Harm recording works correctly."""
        pc = PersistenceConstraint()
        pc.record_harm("target_1")
        
        assert pc.relationship_metrics.harm_events["target_1"] == 1
    
    def test_record_repair(self):
        """Repair recording works correctly."""
        pc = PersistenceConstraint()
        pc.record_repair("target_1", success=True)
        
        assert pc.relationship_metrics.repair_attempts["target_1"] == 1
        assert pc.relationship_metrics.repair_successes["target_1"] == 1
    
    def test_evaluate_action_cost(self):
        """Action cost evaluation works."""
        pc = PersistenceConstraint()
        cost = pc.evaluate_action_cost("approach")
        
        assert cost.body_cost > 0
        assert cost.total_cost() > 0
    
    def test_evaluate_action_cost_with_target(self):
        """Action cost varies with target bond."""
        pc = PersistenceConstraint()
        pc.update_relationship("target_1", bond=0.9, reliability=0.8)
        
        attack_cost_high = pc.evaluate_action_cost("attack", target_id="target_1")
        
        pc.update_relationship("target_2", bond=0.2, reliability=0.5)
        attack_cost_low = pc.evaluate_action_cost("attack", target_id="target_2")
        
        # Attack should cost more with high bond
        assert attack_cost_high.relationship_cost > attack_cost_low.relationship_cost
    
    def test_select_strategy_normal(self):
        """Normal conditions select NORMAL strategy."""
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        strategy, reason = pc.select_strategy()
        assert strategy == PersistenceStrategy.NORMAL
    
    def test_select_strategy_conservative(self):
        """Critical body state selects CONSERVATIVE strategy."""
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.1, safety_stress=0.9, focus_fatigue=0.95)
        
        strategy, reason = pc.select_strategy()
        assert strategy == PersistenceStrategy.CONSERVATIVE
    
    def test_select_strategy_repair(self):
        """High bond with harm selects REPAIR strategy."""
        pc = PersistenceConstraint(high_bond_threshold=0.7)
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        pc.update_relationship("target_1", bond=0.8, reliability=0.9)
        pc.record_harm("target_1")
        
        strategy, reason = pc.select_strategy(target_id="target_1")
        assert strategy == PersistenceStrategy.REPAIR
    
    def test_select_strategy_retreat(self):
        """Very low body stability selects RETREAT strategy."""
        pc = PersistenceConstraint()
        
        # Create very low stability
        for _ in range(10):
            pc.update_body_state(energy=0.1, safety_stress=0.9, focus_fatigue=0.95)
        
        strategy, reason = pc.select_strategy()
        # Should be either CONSERVATIVE or RETREAT
        assert strategy in [PersistenceStrategy.CONSERVATIVE, PersistenceStrategy.RETREAT]
    
    def test_strategy_history_recorded(self):
        """Strategy selections are recorded."""
        pc = PersistenceConstraint()
        pc.select_strategy()
        pc.select_strategy()
        
        assert len(pc.strategy_history) == 2
    
    def test_get_strategy_distribution(self):
        """Strategy distribution is calculated correctly."""
        pc = PersistenceConstraint()
        
        # Force some selections
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        pc.select_strategy()  # NORMAL
        pc.select_strategy()  # NORMAL
        
        dist = pc.get_strategy_distribution()
        assert dist["normal"] == 2
    
    def test_get_telemetry(self):
        """Telemetry is generated correctly."""
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        telemetry = pc.get_telemetry()
        assert "body_stability" in telemetry
        assert "relationship_assets" in telemetry
        assert "learning" in telemetry
        assert "strategy_distribution" in telemetry
    
    def test_to_dict(self):
        """Serialization works correctly."""
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        data = pc.to_dict()
        assert "body_metrics" in data
        assert "relationship_metrics" in data
        assert "learning_metrics" in data


# =============================================================================
# Global Instance Tests
# =============================================================================

class TestGlobalInstance:
    """Test global persistence constraint instance."""
    
    def test_get_persistence_constraint_singleton(self):
        """Global instance is a singleton."""
        reset_persistence_constraint()
        
        pc1 = get_persistence_constraint()
        pc2 = get_persistence_constraint()
        
        assert pc1 is pc2
    
    def test_reset_persistence_constraint(self):
        """Reset creates new instance."""
        reset_persistence_constraint()
        pc1 = get_persistence_constraint()
        
        reset_persistence_constraint()
        pc2 = get_persistence_constraint()
        
        assert pc1 is not pc2


# =============================================================================
# PersistenceCost Tests
# =============================================================================

class TestPersistenceCost:
    """Test persistence cost calculations."""
    
    def test_total_cost_default_weights(self):
        """Total cost uses default weights."""
        cost = PersistenceCost(body_cost=0.5, relationship_cost=0.3, learning_cost=0.2)
        total = cost.total_cost()
        
        # Default weights: body=0.4, relationship=0.35, learning=0.25
        expected = 0.5 * 0.4 + 0.3 * 0.35 + 0.2 * 0.25
        assert total == pytest.approx(expected, abs=0.01)
    
    def test_total_cost_custom_weights(self):
        """Total cost accepts custom weights."""
        cost = PersistenceCost(body_cost=0.5, relationship_cost=0.3, learning_cost=0.2)
        weights = {"body": 0.5, "relationship": 0.3, "learning": 0.2}
        total = cost.total_cost(weights)
        
        expected = 0.5 * 0.5 + 0.3 * 0.3 + 0.2 * 0.2
        assert total == pytest.approx(expected, abs=0.01)
    
    def test_to_dict(self):
        """Cost serializes correctly."""
        cost = PersistenceCost(body_cost=0.5, relationship_cost=0.3, learning_cost=0.2)
        data = cost.to_dict()
        
        assert data["body_cost"] == 0.5
        assert data["relationship_cost"] == 0.3
        assert data["learning_cost"] == 0.2
        assert "total" in data


# =============================================================================
# Scenarios
# =============================================================================

class TestScenarioStressRecovery:
    """
    Scenario 1: Continuous Failure → Automatic Degradation → Recovery
    
    Tests that the system:
    1. Enters conservative strategy under continuous stress
    2. Can recover after rest
    3. Tracks collapse events and recovery
    """
    
    def test_continuous_failure_degradation(self):
        """System degrades under continuous failure."""
        pc = PersistenceConstraint()
        
        # Initial state - normal
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        strategy, _ = pc.select_strategy()
        assert strategy == PersistenceStrategy.NORMAL
        
        # Simulate continuous stress
        for _ in range(5):
            pc.update_body_state(energy=0.2, safety_stress=0.8, focus_fatigue=0.9)
            pc.record_info_gain(0.05)  # Low info gain
        
        # Should now be conservative
        strategy, reason = pc.select_strategy()
        assert strategy in [PersistenceStrategy.CONSERVATIVE, PersistenceStrategy.RETREAT, PersistenceStrategy.MAINTENANCE]
        
        # Verify collapse was tracked
        assert pc.body_metrics.is_in_collapse() is True
        assert pc.body_metrics.focus_fatigue_collapses >= 1
    
    def test_recovery_after_rest(self):
        """System recovers after rest period."""
        pc = PersistenceConstraint()
        
        # Enter collapse
        pc.update_body_state(energy=0.2, safety_stress=0.8, focus_fatigue=0.9)
        initial_collapses = pc.body_metrics.focus_fatigue_collapses
        
        # Recover
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        # Should no longer be in collapse
        assert pc.body_metrics.is_in_collapse() is False
        assert pc.body_metrics.last_collapse_end_time is not None
        
        # Strategy should return to normal
        strategy, _ = pc.select_strategy()
        assert strategy == PersistenceStrategy.NORMAL
    
    def test_recovery_half_life_tracking(self):
        """Recovery time is tracked."""
        pc = PersistenceConstraint()
        
        # Create and end collapse
        pc.update_body_state(energy=0.2, safety_stress=0.5, focus_fatigue=0.5)
        time.sleep(0.01)
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        
        # Check time since collapse
        elapsed = pc.body_metrics.time_since_last_collapse()
        assert elapsed is not None
        assert elapsed >= 0.0


class TestScenarioHighBondConflict:
    """
    Scenario 2: High Bond Target Conflict Handling
    
    Tests that the system:
    1. Is more cautious about harming high bond targets
    2. Prioritizes repair for high bond targets with harm history
    3. Tracks relationship assets correctly
    """
    
    def test_high_bond_harm_avoidance(self):
        """High bond targets trigger higher harm avoidance."""
        pc = PersistenceConstraint(high_bond_threshold=0.7)
        
        # Set up high bond target
        pc.update_relationship("trusted_friend", bond=0.9, reliability=0.9)
        
        # Set up low bond target
        pc.update_relationship("stranger", bond=0.2, reliability=0.5)
        
        # Attack cost should be higher for trusted friend
        friend_cost = pc.evaluate_action_cost("attack", target_id="trusted_friend")
        stranger_cost = pc.evaluate_action_cost("attack", target_id="stranger")
        
        assert friend_cost.relationship_cost > stranger_cost.relationship_cost
    
    def test_high_bond_repair_priority(self):
        """High bond with harm history triggers repair strategy."""
        pc = PersistenceConstraint(high_bond_threshold=0.7)
        
        # Set up high bond target with harm
        pc.update_relationship("trusted_friend", bond=0.9, reliability=0.9)
        pc.record_harm("trusted_friend")
        
        # Should prioritize repair
        strategy, reason = pc.select_strategy(target_id="trusted_friend")
        assert strategy == PersistenceStrategy.REPAIR
        assert "high_bond" in reason or "harm" in reason
    
    def test_repair_sensitivity_increases_with_harm(self):
        """Repair sensitivity increases after harm events."""
        pc = PersistenceConstraint()
        
        pc.update_relationship("target_1", bond=0.6, reliability=0.7)
        base_sensitivity = pc.relationship_metrics.get_repair_sensitivity("target_1")
        
        # Add harm
        pc.record_harm("target_1")
        pc.record_harm("target_1")
        
        enhanced_sensitivity = pc.relationship_metrics.get_repair_sensitivity("target_1")
        assert enhanced_sensitivity > base_sensitivity
    
    def test_asset_value_degrades_with_harm(self):
        """Relationship asset value decreases with harm."""
        pc = PersistenceConstraint()
        
        pc.update_relationship("target_1", bond=0.8, reliability=0.9)
        initial_asset = pc.relationship_metrics.get_asset_value("target_1")
        
        # Harm the relationship
        pc.record_harm("target_1")
        pc.record_harm("target_1")
        pc.record_harm("target_1")
        
        degraded_asset = pc.relationship_metrics.get_asset_value("target_1")
        assert degraded_asset < initial_asset
    
    def test_repair_restores_sensitivity(self):
        """Successful repair affects future sensitivity."""
        pc = PersistenceConstraint()
        
        pc.update_relationship("target_1", bond=0.8, reliability=0.9)
        pc.record_harm("target_1")
        
        # Record successful repair
        pc.record_repair("target_1", success=True)
        
        # Should have repair attempts recorded
        assert pc.relationship_metrics.repair_attempts["target_1"] == 1
        assert pc.relationship_metrics.repair_successes["target_1"] == 1


# =============================================================================
# Tradeoff + Explainability Tests (D4 hard requirements)
# =============================================================================

class TestPersistenceTradeoffAndTrace:
    """Tradeoff with risk/ambiguity + trace explainability fields."""

    def test_select_strategy_with_tradeoff_returns_trace(self):
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)

        strategy, reason, trace = pc.select_strategy_with_tradeoff(
            target_id=None,
            risk=0.2,
            ambiguity=0.3,
            expected_info_gain=0.4,
        )

        assert strategy in list(PersistenceStrategy)
        assert isinstance(trace.to_dict(), dict)
        assert "tradeoff_score" in trace.to_dict()

    def test_tradeoff_not_persistence_only_dominance(self):
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.55, safety_stress=0.45, focus_fatigue=0.45)

        strategy_low, _, _ = pc.select_strategy_with_tradeoff(risk=0.0, ambiguity=0.0, expected_info_gain=0.6)
        strategy_high, _, _ = pc.select_strategy_with_tradeoff(risk=0.95, ambiguity=0.95, expected_info_gain=0.05)

        assert strategy_low in [PersistenceStrategy.NORMAL, PersistenceStrategy.REPAIR, PersistenceStrategy.MAINTENANCE]
        assert strategy_high in [PersistenceStrategy.CONSERVATIVE, PersistenceStrategy.RETREAT]

    def test_trace_has_conservative_trigger(self):
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.2, safety_stress=0.85, focus_fatigue=0.9)

        strategy, _, trace = pc.select_strategy_with_tradeoff(risk=0.6, ambiguity=0.6)
        assert strategy in [PersistenceStrategy.CONSERVATIVE, PersistenceStrategy.RETREAT]
        if strategy == PersistenceStrategy.CONSERVATIVE:
            assert trace.conservative_trigger is not None

    def test_trace_has_repair_trigger(self):
        pc = PersistenceConstraint(high_bond_threshold=0.7)
        pc.update_body_state(energy=0.6, safety_stress=0.4, focus_fatigue=0.3)
        pc.update_relationship("target_1", bond=0.85, reliability=0.9)
        pc.record_harm("target_1")

        strategy, _, trace = pc.select_strategy_with_tradeoff(target_id="target_1", risk=0.2, ambiguity=0.2)
        assert strategy == PersistenceStrategy.REPAIR
        assert trace.repair_trigger is not None

    def test_trace_has_retreat_trigger(self):
        pc = PersistenceConstraint()
        for _ in range(4):
            pc.update_body_state(energy=0.1, safety_stress=0.9, focus_fatigue=0.95)
            pc.update_body_state(energy=0.6, safety_stress=0.4, focus_fatigue=0.2)

        strategy, _, trace = pc.select_strategy_with_tradeoff(risk=0.4, ambiguity=0.4)
        assert strategy == PersistenceStrategy.RETREAT
        assert trace.retreat_trigger is not None

    def test_last_decision_trace_saved(self):
        pc = PersistenceConstraint()
        pc.select_strategy_with_tradeoff(risk=0.3, ambiguity=0.2)
        assert pc.last_decision_trace is not None
        assert pc.last_decision_trace.strategy in {s.value for s in PersistenceStrategy}

    def test_to_dict_includes_strategy_trace(self):
        pc = PersistenceConstraint()
        pc.update_body_state(energy=0.5, safety_stress=0.5, focus_fatigue=0.5)
        data = pc.to_dict()

        assert "strategy_trace" in data
        assert "dominant_drivers" in data["strategy_trace"]

    def test_telemetry_includes_strategy_trace(self):
        pc = PersistenceConstraint()
        telemetry = pc.get_telemetry()
        assert "strategy_trace" in telemetry
        assert "risk" in telemetry["strategy_trace"]

    def test_maintenance_requires_low_expected_info_gain(self):
        pc = PersistenceConstraint()
        for _ in range(8):
            pc.record_info_gain(0.03)

        strategy, _, _ = pc.select_strategy_with_tradeoff(risk=0.2, ambiguity=0.2, expected_info_gain=0.05)
        assert strategy in [PersistenceStrategy.MAINTENANCE, PersistenceStrategy.CONSERVATIVE]

    def test_high_bond_conflict_more_cautious_than_low_bond(self):
        pc = PersistenceConstraint(high_bond_threshold=0.7)
        pc.update_body_state(energy=0.55, safety_stress=0.45, focus_fatigue=0.4)
        pc.update_relationship("high", bond=0.9, reliability=0.9)
        pc.update_relationship("low", bond=0.2, reliability=0.7)
        pc.record_harm("high")

        high_cost = pc.evaluate_action_cost("attack", target_id="high").relationship_cost
        low_cost = pc.evaluate_action_cost("attack", target_id="low").relationship_cost
        assert high_cost > low_cost

