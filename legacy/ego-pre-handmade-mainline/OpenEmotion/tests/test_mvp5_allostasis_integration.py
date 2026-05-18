"""
MVP-5 D2: Allostasis Budget Integration Tests

Tests for integration of energy budget with emotiond core system.
"""
import os
import sys
import pytest
import asyncio
import tempfile
import json
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond.core import (
    EmotionState, RelationshipManager, process_event, generate_plan,
    get_allostasis_budget, reset_allostasis_budget, load_initial_state
)
from emotiond.models import Event, PlanRequest
from emotiond.allostasis import BudgetChangeReason


@pytest_asyncio.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        temp_db_path = tmp.name
    
    os.environ["EMOTIOND_DB_PATH"] = temp_db_path
    
    # Reload modules to pick up new DB path
    import importlib
    import emotiond.db
    import emotiond.config
    importlib.reload(emotiond.config)
    importlib.reload(emotiond.db)
    
    await emotiond.db.init_db()
    
    yield temp_db_path
    
    # Cleanup
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)
    if "EMOTIOND_DB_PATH" in os.environ:
        del os.environ["EMOTIOND_DB_PATH"]


@pytest_asyncio.fixture
def fresh_state():
    """Reset state for each test."""
    reset_allostasis_budget()
    yield
    reset_allostasis_budget()


class TestAllostasisIntegration:
    """Test allostasis integration with core system."""

    @pytest.mark.asyncio
    async def test_energy_budget_in_response(self, temp_db, fresh_state):
        """Test that energy_budget is included in process_event response."""
        event = Event(
            type="user_message",
            actor="user1",
            target="agent",
            text="Hello"
        )
        
        result = await process_event(event)
        
        assert "energy_budget" in result
        assert 0 <= result["energy_budget"] <= 1
        assert "fatigue_level" in result
        assert "budget_deltas" in result

    @pytest.mark.asyncio
    async def test_budget_depletion_on_negative_message(self, temp_db, fresh_state):
        """Test budget depletes on negative user message."""
        budget_before = get_allostasis_budget().budget
        
        event = Event(
            type="user_message",
            actor="user1",
            target="agent",
            text="This is terrible and awful!"
        )
        
        result = await process_event(event)
        
        # Should have depleted from negative words
        budget_after = result["energy_budget"]
        assert budget_after < budget_before or any(
            d["reason"] == BudgetChangeReason.USER_NEGATIVE.value 
            for d in result["budget_deltas"]
        )

    @pytest.mark.asyncio
    async def test_budget_recovery_on_time_passed(self, temp_db, fresh_state):
        """Test budget recovers on time_passed event."""
        # First deplete budget
        budget = get_allostasis_budget()
        budget.deplete(0.5, "test")
        budget_before = budget.budget
        
        event = Event(
            type="world_event",
            actor="system",
            target="agent",
            meta={"subtype": "time_passed", "seconds": 300}  # 5 minutes
        )
        
        result = await process_event(event)
        
        # Should have recovered
        budget_after = result["energy_budget"]
        assert budget_after > budget_before
        assert any(
            d["reason"] == BudgetChangeReason.TIME_PASSED.value 
            for d in result["budget_deltas"]
        )

    @pytest.mark.asyncio
    async def test_budget_depletion_on_betrayal(self, temp_db, fresh_state):
        """Test budget depletes on betrayal event."""
        budget_before = get_allostasis_budget().budget
        
        event = Event(
            type="world_event",
            actor="user1",
            target="agent",
            meta={"subtype": "betrayal", "source": "system"}
        )
        
        result = await process_event(event)
        
        # Should have depleted
        budget_after = result["energy_budget"]
        assert budget_after < budget_before
        assert any(
            d["reason"] == BudgetChangeReason.BETRAYAL.value 
            for d in result["budget_deltas"]
        )

    @pytest.mark.asyncio
    async def test_budget_replenish_on_care(self, temp_db, fresh_state):
        """Test budget replenishes on care event."""
        # First deplete
        budget = get_allostasis_budget()
        budget.deplete(0.3, "test")
        budget_before = budget.budget
        
        event = Event(
            type="world_event",
            actor="user1",
            target="agent",
            meta={"subtype": "care", "source": "system"}
        )
        
        result = await process_event(event)
        
        # Should have replenished
        budget_after = result["energy_budget"]
        assert budget_after > budget_before
        assert any(
            d["reason"] == BudgetChangeReason.CARE.value 
            for d in result["budget_deltas"]
        )

    @pytest.mark.asyncio
    async def test_prediction_error_depletion(self, temp_db, fresh_state):
        """Test budget depletes on prediction error."""
        # Create event that will cause prediction error
        event = Event(
            type="user_message",
            actor="user1",
            target="agent",
            text="good great thanks"  # Positive words
        )
        
        result = await process_event(event)
        
        # Check for prediction error tracking
        assert "prediction_error" in result
        if result["prediction_error"] > 0.1:
            assert any(
                "prediction" in d["reason"] 
                for d in result["budget_deltas"]
            )


class TestAllostasisPlanIntegration:
    """Test allostasis integration with plan generation."""

    @pytest.mark.asyncio
    async def test_energy_budget_in_plan(self, temp_db, fresh_state):
        """Test that energy_budget is included in plan response."""
        request = PlanRequest(user_id="user1", user_text="Hello")
        
        plan = await generate_plan(request)
        
        assert plan.energy_budget is not None
        assert 0 <= plan.energy_budget <= 1

    @pytest.mark.asyncio
    async def test_language_guidance_in_plan(self, temp_db, fresh_state):
        """Test that language guidance is included in plan."""
        request = PlanRequest(user_id="user1", user_text="Hello")
        
        plan = await generate_plan(request)
        
        assert plan.language_guidance is not None
        assert "intensity_cap" in plan.language_guidance
        assert "length_cap" in plan.language_guidance
        assert "tone_guidance" in plan.language_guidance

    @pytest.mark.asyncio
    async def test_w_explore_in_plan(self, temp_db, fresh_state):
        """Test that w_explore is included in plan."""
        request = PlanRequest(user_id="user1", user_text="Hello")
        
        plan = await generate_plan(request)
        
        assert plan.w_explore is not None
        assert 0 <= plan.w_explore <= 1

    @pytest.mark.asyncio
    async def test_learning_rate_multiplier_in_plan(self, temp_db, fresh_state):
        """Test that learning_rate_multiplier is included in plan."""
        request = PlanRequest(user_id="user1", user_text="Hello")
        
        plan = await generate_plan(request)
        
        assert plan.learning_rate_multiplier is not None
        assert 0 < plan.learning_rate_multiplier <= 1

    @pytest.mark.asyncio
    async def test_low_budget_plan_adjustments(self, temp_db, fresh_state):
        """Test plan adjustments when budget is low."""
        # The plan will check the global budget state
        # Deplete budget to trigger low energy guidance
        budget = get_allostasis_budget()
        budget.deplete(0.8, "test")  # Leave only 0.2
        
        request = PlanRequest(user_id="user1", user_text="Hello")
        plan = await generate_plan(request)
        
        # Should have language guidance
        assert plan.language_guidance is not None
        
        # If budget is low, should have concise/minimal guidance
        if plan.energy_budget < 0.3:
            assert plan.language_guidance["tone_guidance"] in ["concise", "minimal"]
            # Should have fatigue note in key_points
            assert any("Low energy" in kp for kp in plan.key_points)


class TestAllostasisScenario:
    """Test scenario-based allostasis behavior."""

    @pytest.mark.asyncio
    async def test_fatigue_in_high_conflict_dialogue(self, temp_db, fresh_state):
        """Test fatigue buildup in long high-conflict dialogue."""
        budgets = []
        
        # Simulate 8 turns of conflict
        for i in range(8):
            event = Event(
                type="world_event",
                actor="user1",
                target="agent",
                meta={"subtype": "rejection", "source": "system"}
            )
            result = await process_event(event)
            budgets.append(result["energy_budget"])
        
        # Budget should trend downward
        assert budgets[-1] < budgets[0]
        
        # Should be fatigued
        assert budgets[-1] < 0.5

    @pytest.mark.asyncio
    async def test_recovery_after_rest_period(self, temp_db, fresh_state):
        """Test recovery after a rest period."""
        # First create fatigue
        budget = get_allostasis_budget()
        for _ in range(5):
            budget.on_high_conflict(conflict_intensity=0.8)
        
        fatigued_budget = budget.budget
        assert fatigued_budget < 0.5
        
        # Now rest
        event = Event(
            type="world_event",
            actor="system",
            target="agent",
            meta={"subtype": "time_passed", "seconds": 600}  # 10 minutes
        )
        
        result = await process_event(event)
        recovered_budget = result["energy_budget"]
        
        # Should have recovered
        assert recovered_budget > fatigued_budget

    @pytest.mark.asyncio
    async def test_mixed_interaction_pattern(self, temp_db, fresh_state):
        """Test mixed positive/negative interaction pattern."""
        budgets = []
        
        # Pattern: negative, negative, positive, rest
        events = [
            ("user_message", "This is terrible!", None),
            ("world_event", None, "rejection"),
            ("world_event", None, "care"),
            ("world_event", None, "time_passed"),
        ]
        
        for event_type, text, subtype in events:
            if event_type == "user_message":
                event = Event(type=event_type, actor="user1", target="agent", text=text)
            else:
                meta = {"subtype": subtype, "source": "system"}
                if subtype == "time_passed":
                    meta["seconds"] = 300
                event = Event(type=event_type, actor="system", target="agent", meta=meta)
            
            result = await process_event(event)
            budgets.append(result["energy_budget"])
        
        # Budget should have gone down then up
        assert budgets[1] < budgets[0]  # After rejection
        assert budgets[2] > budgets[1]  # After care
        # After rest, budget should be stable or recovered
        # (may not always increase depending on recovery rate)
        assert budgets[3] >= budgets[2] * 0.95  # Allow small variance


class TestAllostasisTraceRecording:
    """Test budget trace recording to database."""

    @pytest.mark.asyncio
    async def test_budget_trace_recorded(self, temp_db, fresh_state):
        """Test that budget changes are recorded to trace table."""
        from emotiond.db import get_recent_budget_trace
        
        # Process event that changes budget
        event = Event(
            type="world_event",
            actor="user1",
            target="agent",
            meta={"subtype": "betrayal", "source": "system"}
        )
        
        await process_event(event)
        
        # Check trace was recorded
        trace = await get_recent_budget_trace(limit=10)
        
        # Should have at least one entry
        assert len(trace) >= 1
        
        # Check structure
        entry = trace[0]
        assert "budget_value" in entry
        assert "delta" in entry
        assert "reason" in entry

    @pytest.mark.asyncio
    async def test_budget_trace_reason_filtering(self, temp_db, fresh_state):
        """Test filtering budget trace by reason."""
        from emotiond.db import get_budget_trace_by_reason
        
        # Create betrayal event
        event = Event(
            type="world_event",
            actor="user1",
            target="agent",
            meta={"subtype": "betrayal", "source": "system"}
        )
        await process_event(event)
        
        # Get betrayal traces
        betrayal_traces = await get_budget_trace_by_reason(
            BudgetChangeReason.BETRAYAL.value
        )
        
        assert len(betrayal_traces) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
