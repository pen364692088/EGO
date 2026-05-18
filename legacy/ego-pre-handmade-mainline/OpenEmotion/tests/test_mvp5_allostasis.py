"""
MVP-5 D2: Allostasis Budget Tests

Tests for energy budget dynamics, fatigue/recovery, and coupling to decision-making.
"""
import os
import sys
import pytest
import asyncio
import tempfile
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.allostasis import (
    AllostasisBudget, BudgetChangeReason, BudgetDelta,
    get_budget, reset_budget, calculate_budget_from_state
)


class TestAllostasisBudgetBasics:
    """Test basic allostasis budget functionality."""

    def test_initial_budget(self):
        """Test that budget initializes correctly."""
        budget = AllostasisBudget(initial_budget=1.0)
        assert budget.budget == 1.0
        assert budget.fatigue_level == "energized"
        assert not budget.is_low
        assert not budget.is_critical

    def test_budget_clamping(self):
        """Test that budget stays within [0, 1] bounds."""
        budget = AllostasisBudget(initial_budget=0.5)
        
        # Try to deplete below 0
        budget.deplete(1.0, "test")
        assert budget.budget == 0.0
        
        # Try to replenish above 1
        budget.replenish(2.0, "test")
        assert budget.budget == 1.0

    def test_depletion(self):
        """Test budget depletion."""
        budget = AllostasisBudget(initial_budget=1.0)
        delta = budget.deplete(0.2, BudgetChangeReason.HIGH_CONFLICT.value)
        
        assert budget.budget == 0.8
        assert abs(delta.delta - (-0.2)) < 0.001
        assert delta.reason == BudgetChangeReason.HIGH_CONFLICT.value
        assert delta.old_value == 1.0
        assert delta.new_value == 0.8

    def test_replenishment(self):
        """Test budget replenishment."""
        budget = AllostasisBudget(initial_budget=0.5)
        delta = budget.replenish(0.2, BudgetChangeReason.CARE.value)
        
        assert budget.budget == 0.7
        assert abs(delta.delta - 0.2) < 0.001
        assert delta.reason == BudgetChangeReason.CARE.value

    def test_fatigue_levels(self):
        """Test fatigue level detection."""
        budget = AllostasisBudget(initial_budget=0.8)
        assert budget.fatigue_level == "energized"
        
        budget._budget = 0.5
        assert budget.fatigue_level == "moderate"
        
        budget._budget = 0.25
        assert budget.fatigue_level == "fatigued"
        assert budget.is_low
        
        budget._budget = 0.05
        assert budget.fatigue_level == "exhausted"
        assert budget.is_critical


class TestAllostasisBudgetDynamics:
    """Test budget dynamics (depletion/recovery)."""

    def test_time_passed_recovery(self):
        """Test recovery over time."""
        budget = AllostasisBudget(initial_budget=0.5, recovery_rate=0.1)
        
        # 60 seconds = 1 minute, should recover 0.1 * efficiency
        delta = budget.apply_time_passed(60)
        
        # Efficiency at 0.5 budget: 1 - 0.5^2 = 0.75
        # Recovery: 0.1 * 0.75 = 0.075
        assert delta.delta > 0
        assert delta.reason == BudgetChangeReason.TIME_PASSED.value
        assert budget.budget > 0.5

    def test_prediction_error_depletion(self):
        """Test depletion from prediction error."""
        budget = AllostasisBudget(initial_budget=1.0, error_depletion=0.1)
        
        delta = budget.on_prediction_error(0.5, is_consecutive=False)
        
        # Should deplete by 0.1 * 0.5 = 0.05
        assert delta.delta < 0
        assert delta.reason == BudgetChangeReason.PREDICTION_ERROR.value
        assert "error_magnitude" in delta.metadata

    def test_consecutive_error_multiplier(self):
        """Test consecutive error multiplier."""
        budget = AllostasisBudget(initial_budget=1.0, error_depletion=0.1)
        
        # First error
        delta1 = budget.on_prediction_error(0.5, is_consecutive=True)
        # Second error (consecutive)
        delta2 = budget.on_prediction_error(0.5, is_consecutive=True)
        
        # Second error should have higher depletion
        assert abs(delta2.delta) > abs(delta1.delta)
        assert budget._consecutive_errors == 2

    def test_high_uncertainty_depletion(self):
        """Test depletion from high uncertainty."""
        budget = AllostasisBudget(initial_budget=1.0, uncertainty_depletion=0.1)
        
        # Low uncertainty - no depletion
        delta = budget.on_high_uncertainty(0.3)
        assert delta is None
        
        # High uncertainty - depletion
        delta = budget.on_high_uncertainty(0.8)
        assert delta is not None
        assert delta.delta < 0
        assert delta.reason == BudgetChangeReason.HIGH_UNCERTAINTY.value

    def test_event_subtype_impacts(self):
        """Test event subtype impacts on budget."""
        budget = AllostasisBudget(initial_budget=0.5)
        
        # Betrayal should deplete
        delta = budget.on_event_subtype("betrayal")
        assert delta.delta < 0
        assert delta.reason == BudgetChangeReason.BETRAYAL.value
        
        # Care should replenish
        delta = budget.on_event_subtype("care")
        assert delta.delta > 0
        assert delta.reason == BudgetChangeReason.CARE.value
        
        # Unknown subtype - no change
        delta = budget.on_event_subtype("unknown")
        assert delta is None

    def test_user_message_impacts(self):
        """Test user message impacts on budget."""
        budget = AllostasisBudget(initial_budget=0.5)
        
        # Negative message depletes
        delta = budget.on_user_message(is_negative=True)
        assert delta.delta < 0
        
        # Positive message replenishes
        delta = budget.on_user_message(is_positive=True)
        assert delta.delta > 0
        
        # Neutral message - no change
        delta = budget.on_user_message()
        assert delta is None


class TestAllostasisBudgetCoupling:
    """Test coupling to decision-making."""

    def test_language_guidance_energized(self):
        """Test language guidance when energized."""
        budget = AllostasisBudget(initial_budget=0.8)
        guidance = budget.get_language_guidance()
        
        assert guidance["intensity_cap"] == 1.0
        assert guidance["length_cap"] == 1.0
        assert guidance["tone_guidance"] == "normal"
        assert guidance["max_tokens_suggestion"] == 200

    def test_language_guidance_fatigued(self):
        """Test language guidance when fatigued."""
        budget = AllostasisBudget(initial_budget=0.2)
        guidance = budget.get_language_guidance()
        
        assert guidance["intensity_cap"] == 0.6
        assert guidance["length_cap"] == 0.7
        assert guidance["tone_guidance"] == "concise"
        assert guidance["max_tokens_suggestion"] == 100

    def test_language_guidance_exhausted(self):
        """Test language guidance when exhausted."""
        budget = AllostasisBudget(initial_budget=0.05)
        guidance = budget.get_language_guidance()
        
        assert guidance["intensity_cap"] == 0.4
        assert guidance["length_cap"] == 0.5
        assert guidance["tone_guidance"] == "minimal"
        assert guidance["max_tokens_suggestion"] == 50

    def test_explore_weight_reduction(self):
        """Test w_explore reduction when fatigued."""
        budget_full = AllostasisBudget(initial_budget=1.0)
        budget_fatigued = AllostasisBudget(initial_budget=0.2)
        
        w_full = budget_full.get_explore_weight(0.5)
        w_fatigued = budget_fatigued.get_explore_weight(0.5)
        
        assert w_fatigued < w_full
        # At budget=0.2: fatigue_factor = 0.5 + 0.5*0.2 = 0.6
        assert w_fatigued == pytest.approx(0.3, rel=0.01)

    def test_learning_rate_conservatism(self):
        """Test learning rate conservatism when fatigued."""
        budget_full = AllostasisBudget(initial_budget=1.0)
        budget_fatigued = AllostasisBudget(initial_budget=0.2)
        
        lr_full = budget_full.get_learning_rate_multiplier()
        lr_fatigued = budget_fatigued.get_learning_rate_multiplier()
        
        assert lr_fatigued < lr_full
        # At budget=0.2: 0.5 + 0.5*0.2 = 0.6
        assert lr_fatigued == pytest.approx(0.6, rel=0.01)

    def test_update_amplitude_cap(self):
        """Test update amplitude cap when fatigued."""
        budget_full = AllostasisBudget(initial_budget=1.0)
        budget_fatigued = AllostasisBudget(initial_budget=0.2)
        
        cap_full = budget_full.get_update_amplitude_cap()
        cap_fatigued = budget_fatigued.get_update_amplitude_cap()
        
        assert cap_fatigued < cap_full
        # At budget=1.0: 0.05 + 0.15*1.0 = 0.20
        # At budget=0.2: 0.05 + 0.15*0.2 = 0.08
        assert cap_full == pytest.approx(0.20, rel=0.01)
        assert cap_fatigued == pytest.approx(0.08, rel=0.01)


class TestAllostasisBudgetHistory:
    """Test budget history tracking."""

    def test_history_recording(self):
        """Test that budget changes are recorded."""
        budget = AllostasisBudget(initial_budget=1.0)
        
        budget.deplete(0.1, "test_reason")
        budget.replenish(0.05, "test_reason_2")
        
        history = budget.get_history()
        assert len(history) == 2
        assert history[0].reason == "test_reason"
        assert history[1].reason == "test_reason_2"

    def test_history_limit(self):
        """Test history limit."""
        budget = AllostasisBudget(initial_budget=1.0)
        
        for i in range(15):
            budget.deplete(0.01, f"test_{i}")
        
        # Default limit is 10
        history = budget.get_history(limit=10)
        assert len(history) == 10
        
        # Should get most recent
        assert history[-1].reason == "test_14"

    def test_history_dicts(self):
        """Test history as dicts."""
        budget = AllostasisBudget(initial_budget=1.0)
        budget.deplete(0.1, "test")
        
        dicts = budget.get_history_dicts()
        assert len(dicts) == 1
        assert "delta" in dicts[0]
        assert "reason" in dicts[0]
        assert "old_value" in dicts[0]
        assert "new_value" in dicts[0]

    def test_to_dict(self):
        """Test budget serialization."""
        budget = AllostasisBudget(initial_budget=0.75)
        budget.deplete(0.1, "test")
        
        data = budget.to_dict()
        assert data["budget"] == 0.65
        assert data["fatigue_level"] == "moderate"
        assert not data["is_low"]
        assert "recent_deltas" in data


class TestAllostasisBudgetScenario:
    """Test scenario-based fatigue and recovery."""

    def test_high_conflict_dialogue_fatigue(self):
        """Test fatigue buildup in high-conflict dialogue."""
        budget = AllostasisBudget(initial_budget=1.0)
        
        # Simulate 5 turns of high conflict
        for i in range(5):
            budget.on_high_conflict(conflict_intensity=0.8)
            budget.on_prediction_error(error_magnitude=0.3, is_consecutive=True)
        
        # Budget should be significantly depleted
        assert budget.budget < 0.5
        assert budget.fatigue_level in ["fatigued", "exhausted"]
        assert budget.is_low

    def test_recovery_after_rest(self):
        """Test recovery after rest period."""
        budget = AllostasisBudget(initial_budget=0.2, recovery_rate=0.1)
        
        # Simulate 10 minutes of rest
        budget.apply_time_passed(600)  # 10 minutes
        
        # Budget should have recovered
        assert budget.budget > 0.2

    def test_mixed_dialogue_with_recovery(self):
        """Test mixed dialogue with periods of rest."""
        budget = AllostasisBudget(initial_budget=1.0, recovery_rate=0.05)
        
        # Phase 1: High conflict (3 turns)
        for _ in range(3):
            budget.on_high_conflict(conflict_intensity=0.7)
            budget.on_prediction_error(error_magnitude=0.2)
        
        budget_after_conflict = budget.budget
        assert budget_after_conflict < 1.0
        
        # Phase 2: Rest (5 minutes)
        budget.apply_time_passed(300)
        
        budget_after_rest = budget.budget
        assert budget_after_rest > budget_after_conflict
        
        # Phase 3: Positive interaction
        budget.on_event_subtype("care")
        budget.on_user_message(is_positive=True)
        
        assert budget.budget > budget_after_rest

    def test_consecutive_errors_streak(self):
        """Test consecutive error streak handling."""
        budget = AllostasisBudget(initial_budget=1.0, error_depletion=0.1)
        
        # 3 consecutive errors
        for i in range(5):
            budget.on_prediction_error(error_magnitude=0.5, is_consecutive=True)
        
        # Should have significant depletion with multiplier
        assert budget._consecutive_errors == 5
        assert budget.budget < 0.8

    def test_error_reset_on_success(self):
        """Test that consecutive errors reset after success."""
        budget = AllostasisBudget(initial_budget=1.0)
        
        # 2 consecutive errors
        budget.on_prediction_error(error_magnitude=0.5, is_consecutive=True)
        budget.on_prediction_error(error_magnitude=0.5, is_consecutive=True)
        assert budget._consecutive_errors == 2
        
        # Reset
        budget.reset_consecutive_errors()
        assert budget._consecutive_errors == 0
        
        # Next error is not consecutive
        delta = budget.on_prediction_error(error_magnitude=0.5, is_consecutive=False)
        assert budget._consecutive_errors == 0


class TestGlobalBudgetInstance:
    """Test global budget instance functions."""

    def test_get_budget_singleton(self):
        """Test that get_budget returns singleton."""
        reset_budget()
        
        budget1 = get_budget()
        budget2 = get_budget()
        
        assert budget1 is budget2

    def test_get_budget_with_params(self):
        """Test get_budget with custom params."""
        reset_budget()
        
        budget = get_budget(
            recovery_rate=0.2,
            conflict_depletion=0.3
        )
        
        assert budget.recovery_rate == 0.2
        assert budget.conflict_depletion == 0.3

    def test_reset_budget(self):
        """Test reset_budget clears instance."""
        budget1 = get_budget()
        reset_budget()
        budget2 = get_budget()
        
        assert budget1 is not budget2


class TestCalculateBudgetFromState:
    """Test calculate_budget_from_state utility."""

    def test_calculate_with_time_passed(self):
        """Test calculation with time passed."""
        state = {"uncertainty": 0.3, "prediction_error": 0.1}
        
        new_budget, deltas = calculate_budget_from_state(
            state,
            previous_budget=0.5,
            time_passed_seconds=60
        )
        
        assert new_budget > 0.5  # Should recover
        assert len(deltas) >= 1

    def test_calculate_with_high_uncertainty(self):
        """Test calculation with high uncertainty."""
        state = {"uncertainty": 0.8, "prediction_error": 0.1}
        
        new_budget, deltas = calculate_budget_from_state(
            state,
            previous_budget=0.8,
            time_passed_seconds=0
        )
        
        # Should deplete from uncertainty
        assert any(d.reason == BudgetChangeReason.HIGH_UNCERTAINTY.value for d in deltas)

    def test_calculate_with_prediction_error(self):
        """Test calculation with prediction error."""
        state = {"uncertainty": 0.3, "prediction_error": 0.5}
        
        new_budget, deltas = calculate_budget_from_state(
            state,
            previous_budget=0.8,
            time_passed_seconds=0
        )
        
        # Should deplete from prediction error
        assert any(d.reason == BudgetChangeReason.PREDICTION_ERROR.value for d in deltas)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
