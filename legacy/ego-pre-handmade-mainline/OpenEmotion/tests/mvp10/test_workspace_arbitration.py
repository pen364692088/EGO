"""
MVP-10 T05: Test Workspace Arbitrator

Tests:
1. Arbitrator class selects focus from candidates
2. Only one chosen_focus per tick
3. Writes rationale for selection
4. Broadcast mechanism
"""
import pytest
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.workspace import (
    Candidate,
    CandidateType,
    CandidatePool,
    Arbitrator,
    ArbitrationResult,
    create_candidate,
)
from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
)


class TestArbitrator:
    """Tests for Arbitrator class."""
    
    def test_arbitrator_creation(self):
        """Test creating an Arbitrator."""
        arb = Arbitrator()
        
        assert arb.max_candidates == 100
        assert len(arb.pool) == 0
    
    def test_add_candidate(self):
        """Test adding candidates to arbitrator."""
        arb = Arbitrator()
        c = Candidate(id="test", source="drives", type=CandidateType.GOAL, utility=0.8)
        
        assert arb.add_candidate(c) is True
        assert len(arb.pool) == 1
    
    def test_add_candidates(self):
        """Test adding multiple candidates."""
        arb = Arbitrator()
        candidates = [
            Candidate(id=f"c{i}", source="drives", type=CandidateType.GOAL, utility=0.5 + i * 0.1)
            for i in range(5)
        ]
        
        added = arb.add_candidates(candidates)
        
        assert added == 5
        assert len(arb.pool) == 5


class TestSelectFocus:
    """Tests for focus selection."""
    
    def test_select_focus_basic(self):
        """Test basic focus selection."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(
            id="goal_1",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.9,
            payload={"focus": "achieve_goal_1"},
        ))
        arb.add_candidate(Candidate(
            id="goal_2",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.5,
            payload={"focus": "achieve_goal_2"},
        ))
        
        result = arb.select_focus(tick_id=1)
        
        assert result.chosen_focus == "achieve_goal_1"
        assert result.chosen_candidate.id == "goal_1"
        assert result.tick_id == 1
    
    def test_only_one_focus_per_tick(self):
        """Test that only one focus is selected per tick."""
        arb = Arbitrator()
        
        # Add multiple candidates
        for i in range(10):
            arb.add_candidate(Candidate(
                id=f"goal_{i}",
                source="drives",
                type=CandidateType.GOAL,
                utility=0.1 * i,
            ))
        
        result = arb.select_focus(tick_id=1)
        
        # Only one chosen focus
        assert result.chosen_focus is not None
        assert isinstance(result.chosen_focus, str)
    
    def test_rationale_written(self):
        """Test that rationale is written for selection."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(
            id="test",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.8,
            risk=0.2,
        ))
        
        result = arb.select_focus(tick_id=1)
        
        assert result.rationale is not None
        assert len(result.rationale) > 0
        assert "base_score" in result.rationale
    
    def test_no_candidates_returns_default(self):
        """Test that no candidates returns default focus."""
        arb = Arbitrator()
        
        result = arb.select_focus(tick_id=1)
        
        assert result.chosen_focus == "default_explore"
        assert result.chosen_candidate is None
        assert "No candidates" in result.rationale
    
    def test_pool_cleared_after_selection(self):
        """Test that pool is cleared after selection."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(id="test", source="drives", type=CandidateType.GOAL))
        
        arb.select_focus(tick_id=1)
        
        assert len(arb.pool) == 0


class TestHOTModifiers:
    """Tests for HOT modifier application."""
    
    def test_conflict_bias_favors_reflection(self):
        """Test that conflict bias favors reflection candidates."""
        arb = Arbitrator()
        
        # Add candidates with close scores
        arb.add_candidate(Candidate(
            id="action",
            source="drives",
            type=CandidateType.ACTION,
            utility=0.5,
        ))
        arb.add_candidate(Candidate(
            id="reflect",
            source="meta",
            type=CandidateType.REFLECTION,
            utility=0.45,  # Slightly lower
        ))
        
        # Apply HOT modifiers with conflict bias
        hot_modifiers = {"conflict_bias": 0.1}
        result = arb.select_focus(tick_id=1, hot_modifiers=hot_modifiers)
        
        # Reflection should win due to conflict bias
        assert result.chosen_candidate.type == CandidateType.REFLECTION
    
    def test_control_penalty_reduces_risky_candidates(self):
        """Test that control penalty reduces risky candidate scores."""
        arb = Arbitrator()
        
        # Risky candidate with higher base score
        arb.add_candidate(Candidate(
            id="risky",
            source="drives",
            type=CandidateType.ACTION,
            utility=0.7,
            risk=0.8,  # High risk
        ))
        # Safe candidate with lower base score
        arb.add_candidate(Candidate(
            id="safe",
            source="drives",
            type=CandidateType.ACTION,
            utility=0.5,
            risk=0.1,  # Low risk
        ))
        
        # Apply HOT modifiers with control penalty
        hot_modifiers = {"control_penalty": 0.3}
        result = arb.select_focus(tick_id=1, hot_modifiers=hot_modifiers)
        
        # Safe should win due to control penalty on risky
        assert result.chosen_candidate.id == "safe"
    
    def test_no_hot_modifiers(self):
        """Test selection without HOT modifiers."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(
            id="test",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.8,
        ))
        
        result = arb.select_focus(tick_id=1, hot_modifiers=None)
        
        assert result.chosen_candidate.id == "test"


class TestBroadcastMechanism:
    """Tests for broadcast mechanism."""
    
    def test_broadcast_enabled_by_default(self):
        """Test that broadcast is enabled by default."""
        arb = Arbitrator()
        
        assert not arb.is_broadcast_disabled()
    
    def test_set_broadcast_disabled(self):
        """Test disabling broadcast."""
        arb = Arbitrator()
        arb.set_broadcast_enabled(False)
        
        assert arb.is_broadcast_disabled()
    
    def test_external_candidates_blocked_when_disabled(self):
        """Test that external candidates are blocked when broadcast disabled."""
        arb = Arbitrator()
        arb.set_broadcast_enabled(False)
        
        # Local candidate should be added
        local = Candidate(id="local", source="local", type=CandidateType.GOAL, utility=0.8)
        assert arb.add_candidate(local) is True
        
        # External candidate should be blocked
        external = Candidate(id="external", source="drives", type=CandidateType.GOAL, utility=0.9)
        assert arb.add_candidate(external) is False
        
        # Only local should be in pool
        assert len(arb.pool) == 1
        assert arb.pool[0].id == "local"
    
    def test_intervention_manager_broadcast_disabled(self):
        """Test broadcast disabled via InterventionManager."""
        arb = Arbitrator()
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_BROADCAST)
        
        arb.set_intervention_manager(manager)
        
        assert arb.is_broadcast_disabled()
    
    def test_broadcast_blocked_in_result(self):
        """Test that broadcast_blocked is recorded in result."""
        arb = Arbitrator()
        arb.set_broadcast_enabled(False)
        
        arb.add_candidate(Candidate(id="test", source="local", type=CandidateType.GOAL))
        result = arb.select_focus(tick_id=1)
        
        assert result.broadcast_blocked is True


class TestArbitrationResult:
    """Tests for ArbitrationResult."""
    
    def test_result_to_dict(self):
        """Test result serialization."""
        candidate = Candidate(id="test", source="drives", type=CandidateType.GOAL)
        result = ArbitrationResult(
            chosen_focus="test_focus",
            chosen_candidate=candidate,
            rationale="Test rationale",
            tick_id=1,
            all_candidates_count=5,
            broadcast_blocked=False,
        )
        
        data = result.to_dict()
        
        assert data["chosen_focus"] == "test_focus"
        assert data["chosen_candidate"]["id"] == "test"
        assert data["rationale"] == "Test rationale"
        assert data["tick_id"] == 1
        assert data["all_candidates_count"] == 5
    
    def test_result_without_candidate(self):
        """Test result with no candidate (default case)."""
        result = ArbitrationResult(
            chosen_focus="default",
            chosen_candidate=None,
            rationale="No candidates",
            tick_id=1,
        )
        
        data = result.to_dict()
        
        assert data["chosen_focus"] == "default"
        assert data["chosen_candidate"] is None


class TestResultHistory:
    """Tests for result history tracking."""
    
    def test_last_result(self):
        """Test getting last result."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(id="test", source="drives", type=CandidateType.GOAL))
        
        result = arb.select_focus(tick_id=1)
        
        assert arb.get_last_result() == result
    
    def test_result_history(self):
        """Test result history tracking."""
        arb = Arbitrator()
        
        for tick_id in range(1, 4):
            arb.add_candidate(Candidate(
                id=f"test_{tick_id}",
                source="drives",
                type=CandidateType.GOAL,
            ))
            arb.select_focus(tick_id=tick_id)
        
        history = arb.get_result_history()
        
        assert len(history) == 3
        assert history[0].tick_id == 1
        assert history[1].tick_id == 2
        assert history[2].tick_id == 3
    
    def test_clear_history(self):
        """Test clearing history."""
        arb = Arbitrator()
        arb.add_candidate(Candidate(id="test", source="drives", type=CandidateType.GOAL))
        arb.select_focus(tick_id=1)
        
        arb.clear_history()
        
        assert len(arb.get_result_history()) == 0


class TestIntegrationWithInterventions:
    """Integration tests with intervention manager."""
    
    def test_intervention_manager_integration(self):
        """Test full integration with InterventionManager."""
        arb = Arbitrator()
        manager = InterventionManager()
        
        # Set up intervention
        manager.enable(InterventionType.DISABLE_BROADCAST)
        arb.set_intervention_manager(manager)
        
        # External candidate should be blocked
        external = Candidate(id="external", source="drives", type=CandidateType.GOAL, utility=0.9)
        assert arb.add_candidate(external) is False
        
        # Local candidate should pass
        local = Candidate(id="local", source="local", type=CandidateType.GOAL, utility=0.5)
        assert arb.add_candidate(local) is True
        
        result = arb.select_focus(tick_id=1)
        
        assert result.chosen_candidate.id == "local"
        assert result.broadcast_blocked is True


class TestMultipleTicks:
    """Tests for multiple tick scenarios."""
    
    def test_multiple_ticks_independent_pools(self):
        """Test that each tick has independent pool."""
        arb = Arbitrator()
        
        # Tick 1
        arb.add_candidate(Candidate(id="tick1", source="drives", type=CandidateType.GOAL, utility=0.8))
        result1 = arb.select_focus(tick_id=1)
        
        # Tick 2 - pool should be empty
        assert len(arb.pool) == 0
        arb.add_candidate(Candidate(id="tick2", source="drives", type=CandidateType.GOAL, utility=0.6))
        result2 = arb.select_focus(tick_id=2)
        
        assert result1.chosen_candidate.id == "tick1"
        assert result2.chosen_candidate.id == "tick2"
    
    def test_tick_sequence(self):
        """Test a sequence of ticks with varying candidates."""
        arb = Arbitrator()
        
        # Tick 1: Simple goal
        arb.add_candidate(Candidate(id="goal_1", source="drives", type=CandidateType.GOAL, utility=0.8))
        result1 = arb.select_focus(tick_id=1)
        
        # Tick 2: Multiple candidates with HOT modifiers
        arb.add_candidate(Candidate(id="action_1", source="planner", type=CandidateType.ACTION, utility=0.7, risk=0.8))
        arb.add_candidate(Candidate(id="reflect_1", source="meta", type=CandidateType.REFLECTION, utility=0.5))
        result2 = arb.select_focus(tick_id=2, hot_modifiers={"conflict_bias": 0.3})
        
        # Tick 3: Recovery candidate
        arb.add_candidate(Candidate(id="recovery_1", source="validator", type=CandidateType.RECOVERY, utility=0.9))
        result3 = arb.select_focus(tick_id=3)
        
        history = arb.get_result_history()
        assert len(history) == 3
        assert result1.chosen_candidate.id == "goal_1"
        assert result2.chosen_candidate.type == CandidateType.REFLECTION  # Boosted by conflict bias
        assert result3.chosen_candidate.id == "recovery_1"


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_candidates_with_same_score(self):
        """Test selection when candidates have same score."""
        arb = Arbitrator()
        
        arb.add_candidate(Candidate(id="a", source="drives", type=CandidateType.GOAL, utility=0.5))
        arb.add_candidate(Candidate(id="b", source="drives", type=CandidateType.GOAL, utility=0.5))
        
        result = arb.select_focus(tick_id=1)
        
        # Should select one of them (deterministic based on order)
        assert result.chosen_candidate is not None
        assert result.chosen_candidate.id in ("a", "b")
    
    def test_negative_utility_candidate(self):
        """Test candidate with negative computed score."""
        arb = Arbitrator()
        
        # High risk, low utility -> negative score
        arb.add_candidate(Candidate(
            id="bad",
            source="drives",
            type=CandidateType.ACTION,
            utility=0.1,
            risk=0.9,
        ))
        
        result = arb.select_focus(tick_id=1)
        
        # Still selected if it's the only candidate
        assert result.chosen_candidate.id == "bad"
    
    def test_large_candidate_pool(self):
        """Test with many candidates."""
        arb = Arbitrator()
        
        # Add 100 candidates
        for i in range(100):
            arb.add_candidate(Candidate(
                id=f"candidate_{i}",
                source="drives",
                type=CandidateType.GOAL,
                utility=i / 100.0,
            ))
        
        result = arb.select_focus(tick_id=1)
        
        # Should select highest utility
        assert result.chosen_candidate.id == "candidate_99"
        assert result.all_candidates_count == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
