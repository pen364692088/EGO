"""
MVP-10 T16: Test Outcome Attribution Updates Strategy

Tests:
1. Attribution categories are correctly identified
2. Capability stats are updated on failure
3. Strategy preferences are adjusted based on attribution
4. Attribution history is maintained
"""
import pytest
import time

# Import from the actual project location
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.attribution_mvp10 import (
    AttributionCategory,
    AttributionResult,
    CapabilityStats,
    OutcomeAttributor,
    get_outcome_attributor,
    reset_outcome_attributor,
)


class TestCapabilityStats:
    """Tests for CapabilityStats."""
    
    def test_default_stats(self):
        """Test default capability stats."""
        stats = CapabilityStats(name="test_cap")
        
        assert stats.name == "test_cap"
        assert stats.success_count == 0
        assert stats.failure_count == 0
        assert stats.total_attempts == 0
        assert stats.success_rate == 0.5  # Default when no data
    
    def test_record_success(self):
        """Test recording success."""
        stats = CapabilityStats(name="test_cap")
        
        stats.record_outcome(success=True)
        
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.total_attempts == 1
        assert stats.success_rate == 1.0
    
    def test_record_failure(self):
        """Test recording failure."""
        stats = CapabilityStats(name="test_cap")
        
        stats.record_outcome(success=False)
        
        assert stats.success_count == 0
        assert stats.failure_count == 1
        assert stats.total_attempts == 1
        assert stats.success_rate == 0.0
    
    def test_mixed_outcomes(self):
        """Test recording mixed outcomes."""
        stats = CapabilityStats(name="test_cap")
        
        stats.record_outcome(success=True)
        stats.record_outcome(success=True)
        stats.record_outcome(success=False)
        
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.total_attempts == 3
        assert abs(stats.success_rate - 0.667) < 0.01
    
    def test_confidence_updates_with_samples(self):
        """Test that confidence updates as samples accumulate."""
        stats = CapabilityStats(name="test_cap", confidence=0.5)
        
        # Record several successes
        for _ in range(5):
            stats.record_outcome(success=True)
        
        # Confidence should be higher after successes
        assert stats.confidence > 0.5
        
        # Record several failures
        for _ in range(5):
            stats.record_outcome(success=False)
        
        # Confidence should decrease
        assert stats.confidence < 0.9  # Should not be too high


class TestOutcomeAttributor:
    """Tests for OutcomeAttributor."""
    
    def setup_method(self):
        """Reset attributor before each test."""
        reset_outcome_attributor()
    
    def test_initialization(self):
        """Test attributor initialization."""
        attributor = OutcomeAttributor()
        
        # Should have default capabilities
        assert "seek_info" in attributor.capability_stats
        assert "attempt_solution" in attributor.capability_stats
        assert "plan_generation" in attributor.capability_stats
    
    def test_attribute_knowledge_gap(self):
        """Test attributing failure to knowledge gap."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "seek_info", "params": {"query": "test"}},
            ]
        }
        execution_log = [
            {"action": "seek_info", "status": "fail", "reason": "missing_info"},
        ]
        outcome = {
            "status": "fail",
            "reason": "missing_info prevented success",
        }
        
        result = attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        assert result.category == AttributionCategory.KNOWLEDGE_GAP
        assert result.confidence > 0
        assert "seek_info" in result.affected_capabilities
    
    def test_attribute_planning_bug(self):
        """Test attributing failure to planning bug."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "attempt_solution", "params": {}},
            ]
        }
        execution_log = [
            {"action": "attempt_solution", "status": "fail", "reason": "wrong_step"},
        ]
        outcome = {
            "status": "fail",
            "reason": "wrong_step in plan",
        }
        
        result = attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        assert result.category == AttributionCategory.PLANNING_BUG
        assert "plan_generation" in result.affected_capabilities
    
    def test_attribute_execution_bug(self):
        """Test attributing failure to execution bug."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "run_check", "params": {}},
            ]
        }
        execution_log = [
            {"action": "run_check", "status": "fail", "reason": "step_failed"},
        ]
        outcome = {
            "status": "fail",
            "reason": "step_failed during execution",
        }
        
        result = attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        assert result.category == AttributionCategory.EXECUTION_BUG
        assert len(result.affected_capabilities) > 0
    
    def test_attribute_external_constraint(self):
        """Test attributing failure to external constraint."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "apply_fix", "params": {}},
            ]
        }
        execution_log = [
            {"action": "apply_fix", "status": "fail", "reason": "external_error"},
        ]
        outcome = {
            "status": "fail",
            "reason": "external_error occurred",
        }
        
        result = attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        assert result.category == AttributionCategory.EXTERNAL_CONSTRAINT
        assert result.confidence > 0
    
    def test_success_updates_capability_stats(self):
        """Test that success updates capability stats."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "seek_info", "params": {}},
            ]
        }
        execution_log = [
            {"action": "seek_info", "status": "success"},
        ]
        outcome = {
            "status": "success",
            "reason": "Found information",
        }
        
        attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        # Check capability stats updated
        stats = attributor.get_capability_stats("seek_info")
        assert stats is not None
        assert stats.success_count == 1
    
    def test_failure_updates_capability_stats(self):
        """Test that failure updates capability stats."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "attempt_solution", "params": {}},
            ]
        }
        execution_log = [
            {"action": "attempt_solution", "status": "fail", "reason": "execution bug"},
        ]
        outcome = {
            "status": "fail",
            "reason": "execution_bug",
        }
        
        attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        # Check capability stats updated
        stats = attributor.get_capability_stats("attempt_solution")
        assert stats is not None
        assert stats.failure_count == 1
    
    def test_strategy_adjustments_generated(self):
        """Test that strategy adjustments are generated."""
        attributor = OutcomeAttributor()
        
        plan = {
            "steps": [
                {"action": "seek_info", "params": {}},
            ]
        }
        execution_log = [
            {"action": "seek_info", "status": "fail"},
        ]
        outcome = {
            "status": "fail",
            "reason": "missing_info prevented success",
        }
        
        result = attributor.attribute(
            plan=plan,
            execution_log=execution_log,
            outcome=outcome,
        )
        
        # Should have strategy adjustments for knowledge gap
        assert "seek_info_priority" in result.strategy_adjustments
    
    def test_apply_strategy_updates(self):
        """Test applying strategy updates."""
        attributor = OutcomeAttributor()
        
        result = AttributionResult(
            category=AttributionCategory.KNOWLEDGE_GAP,
            confidence=0.8,
            affected_capabilities=["seek_info"],
            strategy_adjustments={"seek_info_priority": 0.1},
            evidence={},
            suggested_action="Gather more information",
        )
        
        attributor.apply_strategy_updates(result)
        
        preferences = attributor.get_strategy_preferences()
        assert "seek_info_priority" in preferences
        # Should be close to the adjustment (with momentum)
        assert preferences["seek_info_priority"] > 0


class TestAttributionIntegration:
    """Integration tests for attribution affecting strategy."""
    
    def setup_method(self):
        """Reset attributor before each test."""
        reset_outcome_attributor()
    
    def test_repeated_failures_reduce_capability_confidence(self):
        """Test that repeated failures reduce capability confidence."""
        attributor = OutcomeAttributor()
        
        # Initial confidence
        initial_stats = attributor.get_capability_stats("seek_info")
        initial_confidence = initial_stats.confidence
        
        # Record multiple failures
        for i in range(5):
            plan = {"steps": [{"action": "seek_info", "params": {}}]}
            execution_log = [{"action": "seek_info", "status": "fail"}]
            outcome = {"status": "fail", "reason": "missing_info"}
            
            attributor.attribute(
                plan=plan,
                execution_log=execution_log,
                outcome=outcome,
            )
        
        # Final confidence should be lower
        final_stats = attributor.get_capability_stats("seek_info")
        assert final_stats.confidence < initial_confidence
        assert final_stats.failure_count == 5
    
    def test_mixed_outcomes_affect_strategy_preferences(self):
        """Test that outcomes affect strategy preferences over time."""
        attributor = OutcomeAttributor()
        
        # Record knowledge gap failures
        for _ in range(3):
            plan = {"steps": [{"action": "seek_info", "params": {}}]}
            execution_log = [{"action": "seek_info", "status": "fail"}]
            outcome = {"status": "fail", "reason": "missing_info"}
            result = attributor.attribute(plan, execution_log, outcome)
            attributor.apply_strategy_updates(result)
        
        # Strategy preference for seek_info should increase
        preferences = attributor.get_strategy_preferences()
        assert "seek_info_priority" in preferences
        assert preferences["seek_info_priority"] > 0
    
    def test_attribution_history_maintained(self):
        """Test that attribution history is maintained."""
        attributor = OutcomeAttributor()
        
        # Record several attributions
        for i in range(3):
            plan = {"steps": [{"action": "attempt_solution", "params": {}}]}
            execution_log = [{"action": "attempt_solution", "status": "fail"}]
            outcome = {"status": "fail", "reason": f"bug_{i}"}
            attributor.attribute(plan, execution_log, outcome)
        
        history = attributor.get_attribution_history()
        assert len(history) == 3
    
    def test_global_instance(self):
        """Test global instance management."""
        reset_outcome_attributor()
        
        attr1 = get_outcome_attributor()
        attr2 = get_outcome_attributor()
        
        assert attr1 is attr2
        
        reset_outcome_attributor()
        attr3 = get_outcome_attributor()
        
        assert attr3 is not attr1


class TestAttributionCategories:
    """Tests for all attribution categories."""
    
    def setup_method(self):
        """Reset attributor before each test."""
        reset_outcome_attributor()
    
    def test_all_categories_identifiable(self):
        """Test that all four categories can be identified."""
        attributor = OutcomeAttributor()
        
        test_cases = [
            ("missing_info", AttributionCategory.KNOWLEDGE_GAP),
            ("wrong_step", AttributionCategory.PLANNING_BUG),
            ("step_failed", AttributionCategory.EXECUTION_BUG),
            ("external_error", AttributionCategory.EXTERNAL_CONSTRAINT),
        ]
        
        for reason, expected_category in test_cases:
            reset_outcome_attributor()
            attributor = OutcomeAttributor()
            
            plan = {"steps": [{"action": "test", "params": {}}]}
            execution_log = [{"action": "test", "status": "fail"}]
            outcome = {"status": "fail", "reason": reason}
            
            result = attributor.attribute(plan, execution_log, outcome)
            
            assert result.category == expected_category, \
                f"Expected {expected_category} for reason '{reason}', got {result.category}"
    
    def test_suggested_action_generated(self):
        """Test that suggested actions are generated."""
        attributor = OutcomeAttributor()
        
        plan = {"steps": [{"action": "seek_info", "params": {}}]}
        execution_log = [{"action": "seek_info", "status": "fail"}]
        outcome = {"status": "fail", "reason": "missing_info"}
        
        result = attributor.attribute(plan, execution_log, outcome)
        
        assert result.suggested_action != ""
        assert "information" in result.suggested_action.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
