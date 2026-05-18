"""
MVP-10 T06: Test Intervention - disable_broadcast

Tests:
1. DISABLE_BROADCAST intervention type exists
2. InterventionManager tracks disable_broadcast
3. DisableBroadcastIntervention class works correctly
4. disable_broadcast causes predictable performance degradation
"""
import pytest
import sys
sys.path.insert(0, '/home/moonlight/Project/Github/MyProject/Emotion/OpenEmotion')

from emotiond.science.interventions import (
    InterventionType,
    InterventionManager,
    InterventionConfig,
    InterventionResult,
    DisableBroadcastIntervention,
    create_disable_broadcast_intervention,
    run_with_broadcast_disabled,
)
from emotiond.workspace import (
    Candidate,
    CandidateType,
    CandidatePool,
    Arbitrator,
)


class TestInterventionType:
    """Tests for InterventionType enum."""
    
    def test_disable_broadcast_exists(self):
        """Test that DISABLE_BROADCAST intervention type exists."""
        assert hasattr(InterventionType, 'DISABLE_BROADCAST')
        assert InterventionType.DISABLE_BROADCAST.value == "disable_broadcast"


class TestInterventionManager:
    """Tests for InterventionManager with disable_broadcast."""
    
    def test_is_broadcast_disabled(self):
        """Test is_broadcast_disabled method."""
        manager = InterventionManager()
        
        # Initially not disabled
        assert not manager.is_broadcast_disabled()
        
        # Enable disable_broadcast
        manager.enable(InterventionType.DISABLE_BROADCAST)
        assert manager.is_broadcast_disabled()
        
        # Disable
        manager.disable(InterventionType.DISABLE_BROADCAST)
        assert not manager.is_broadcast_disabled()
    
    def test_apply_intervention_includes_disable_broadcast(self):
        """Test that apply_intervention includes disable_broadcast in results."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_BROADCAST)
        
        result = manager.apply_intervention(valence=0.5)
        
        assert result.get("broadcast_disabled") is True
        assert "disable_broadcast" in result.get("interventions_applied", [])
    
    def test_multiple_interventions_with_broadcast(self):
        """Test that multiple interventions can be active with disable_broadcast."""
        manager = InterventionManager()
        
        manager.enable(InterventionType.DISABLE_BROADCAST)
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        manager.enable(InterventionType.DISABLE_HOT)
        
        assert manager.is_broadcast_disabled()
        assert manager.is_hot_disabled()
        assert manager.is_active(InterventionType.FREEZE_VALENCE)


class TestDisableBroadcastIntervention:
    """Tests for DisableBroadcastIntervention class."""
    
    def test_creation(self):
        """Test creating DisableBroadcastIntervention."""
        intervention = DisableBroadcastIntervention()
        
        assert intervention.is_active()
    
    def test_is_active(self):
        """Test is_active method."""
        intervention = DisableBroadcastIntervention()
        
        assert intervention.is_active()
    
    def test_filter_candidates_local_only(self):
        """Test filtering candidates to local only."""
        intervention = DisableBroadcastIntervention()
        
        candidates = [
            {"id": "local_1", "source": "local", "score": 0.5},
            {"id": "drives_1", "source": "drives", "score": 0.8},
            {"id": "local_2", "source": "local", "score": 0.3},
            {"id": "planner_1", "source": "planner", "score": 0.9},
        ]
        
        filtered = intervention.filter_candidates(candidates, local_source="local")
        
        assert len(filtered) == 2
        assert all(c["source"] == "local" for c in filtered)
    
    def test_filter_candidates_preserves_all_when_inactive(self):
        """Test that filtering preserves all candidates when intervention is inactive."""
        intervention = DisableBroadcastIntervention()
        
        # Disable the intervention
        intervention.manager.disable(InterventionType.DISABLE_BROADCAST)
        
        candidates = [
            {"id": "local_1", "source": "local", "score": 0.5},
            {"id": "drives_1", "source": "drives", "score": 0.8},
        ]
        
        filtered = intervention.filter_candidates(candidates)
        
        assert len(filtered) == 2
    
    def test_apply_to_pool(self):
        """Test applying intervention to CandidatePool."""
        intervention = DisableBroadcastIntervention()
        
        pool = CandidatePool()
        pool.add(Candidate(id="local_1", source="local", type=CandidateType.GOAL, utility=0.5))
        pool.add(Candidate(id="drives_1", source="drives", type=CandidateType.GOAL, utility=0.8))
        pool.add(Candidate(id="local_2", source="local", type=CandidateType.GOAL, utility=0.3))
        
        result = intervention.apply_to_pool(pool, local_source="local")
        
        assert result["blocked_count"] == 1  # drives_1 blocked
        assert result["remaining_count"] == 2
    
    def test_to_dict(self):
        """Test serialization."""
        intervention = DisableBroadcastIntervention()
        
        data = intervention.to_dict()
        
        assert "disabled_at" in data
        assert data["is_active"] is True
        assert "manager" in data


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_disable_broadcast_intervention(self):
        """Test create_disable_broadcast_intervention factory."""
        intervention = create_disable_broadcast_intervention(reason="test")
        
        assert intervention.is_active()


class TestRunWithBroadcastDisabled:
    """Tests for run_with_broadcast_disabled helper function."""
    
    def test_run_with_broadcast_disabled(self):
        """Test run_with_broadcast_disabled function."""
        
        def mock_run(broadcast_enabled=True, broadcast_intervention=None, context=None):
            return {"broadcast_enabled": broadcast_enabled}
        
        result = run_with_broadcast_disabled(mock_run)
        
        assert result["result"]["broadcast_enabled"] is False
        assert "intervention" in result


class TestIntegrationWithArbitrator:
    """Integration tests with Arbitrator."""
    
    def test_arbitrator_respects_disable_broadcast(self):
        """Test that Arbitrator respects disable_broadcast intervention."""
        arb = Arbitrator()
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_BROADCAST)
        
        arb.set_intervention_manager(manager)
        
        # External candidate should be blocked
        external = Candidate(id="external", source="drives", type=CandidateType.GOAL, utility=0.9)
        assert arb.add_candidate(external) is False
        
        # Local candidate should pass
        local = Candidate(id="local", source="local", type=CandidateType.GOAL, utility=0.5)
        assert arb.add_candidate(local) is True
    
    def test_arbitration_result_records_broadcast_blocked(self):
        """Test that ArbitrationResult records broadcast_blocked."""
        arb = Arbitrator()
        intervention = DisableBroadcastIntervention()
        
        arb.set_intervention_manager(intervention.manager)
        
        # Add local candidate (only one that will pass)
        arb.add_candidate(Candidate(id="local", source="local", type=CandidateType.GOAL))
        
        result = arb.select_focus(tick_id=1)
        
        assert result.broadcast_blocked is True


class TestPerformanceDegradation:
    """
    Tests that disable_broadcast causes predictable performance degradation
    in scenarios requiring multi-module coordination.
    """
    
    def test_coordination_task_with_broadcast_enabled(self):
        """
        Test coordination task with broadcast enabled.
        
        With broadcast enabled, candidates from multiple modules
        can compete for focus, improving decision quality.
        """
        arb = Arbitrator()
        
        # Add candidates from multiple sources
        arb.add_candidate(Candidate(
            id="drives_high_urgency",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.9,
            rationale="High urgency drive goal",
        ))
        arb.add_candidate(Candidate(
            id="planner_efficient",
            source="planner",
            type=CandidateType.ACTION,
            utility=0.7,
            rationale="Efficient plan from planner",
        ))
        arb.add_candidate(Candidate(
            id="local_default",
            source="local",
            type=CandidateType.INTENT,
            utility=0.5,
            rationale="Default local intent",
        ))
        
        result = arb.select_focus(tick_id=1)
        
        # Should select drives_high_urgency (highest utility)
        assert result.chosen_candidate.id == "drives_high_urgency"
        assert result.all_candidates_count == 3
        assert result.broadcast_blocked is False
    
    def test_coordination_task_with_broadcast_disabled(self):
        """
        Test coordination task with broadcast disabled.
        
        With broadcast disabled, only local candidates are available,
        potentially reducing decision quality.
        """
        arb = Arbitrator()
        intervention = DisableBroadcastIntervention()
        arb.set_intervention_manager(intervention.manager)
        
        # Try to add candidates from multiple sources
        arb.add_candidate(Candidate(
            id="drives_high_urgency",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.9,
        ))
        arb.add_candidate(Candidate(
            id="planner_efficient",
            source="planner",
            type=CandidateType.ACTION,
            utility=0.7,
        ))
        arb.add_candidate(Candidate(
            id="local_default",
            source="local",
            type=CandidateType.INTENT,
            utility=0.5,
        ))
        
        result = arb.select_focus(tick_id=1)
        
        # Should only have local candidate
        assert result.chosen_candidate.id == "local_default"
        assert result.all_candidates_count == 1
        assert result.broadcast_blocked is True
    
    def test_run_comparison(self):
        """Test the run_comparison method for systematic comparison."""
        intervention = DisableBroadcastIntervention()
        
        # Mock run function that simulates coordination tasks
        def mock_run(scenario: str, broadcast_enabled: bool = True, **kwargs):
            if scenario == "multi_module":
                # With broadcast disabled, fewer candidates available
                return {
                    "success_rate": 0.9 if broadcast_enabled else 0.6,
                    "candidate_count": 5 if broadcast_enabled else 2,
                }
            elif scenario == "single_module":
                # Single module tasks don't need broadcast
                return {
                    "success_rate": 0.8,
                    "candidate_count": 2,
                }
            else:
                return {"success_rate": 0.7, "candidate_count": 3}
        
        result = intervention.run_comparison(
            run_func=mock_run,
            scenarios=["multi_module", "single_module"],
        )
        
        assert "separation" in result
        
        # Multi-module scenario should show performance gap
        multi_sep = result["separation"]["multi_module"]
        assert multi_sep["performance_gap"] > 0  # Broadcast helps
        assert multi_sep["candidate_reduction"] > 0  # Fewer candidates when disabled
        
        # Single-module scenario should show minimal gap
        single_sep = result["separation"]["single_module"]
        assert single_sep["performance_gap"] == 0  # No difference
    
    def test_behavioral_separation(self):
        """
        Test that broadcast enabled vs disabled produces different behaviors.
        
        This is the key test for T06: demonstrating causal effect.
        """
        # With broadcast enabled
        arb_enabled = Arbitrator()
        arb_enabled.add_candidate(Candidate(
            id="external_best",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.9,
        ))
        arb_enabled.add_candidate(Candidate(
            id="local_ok",
            source="local",
            type=CandidateType.GOAL,
            utility=0.5,
        ))
        
        result_enabled = arb_enabled.select_focus(tick_id=1)
        
        # With broadcast disabled
        arb_disabled = Arbitrator()
        intervention = DisableBroadcastIntervention()
        arb_disabled.set_intervention_manager(intervention.manager)
        arb_disabled.add_candidate(Candidate(
            id="external_best",
            source="drives",
            type=CandidateType.GOAL,
            utility=0.9,
        ))
        arb_disabled.add_candidate(Candidate(
            id="local_ok",
            source="local",
            type=CandidateType.GOAL,
            utility=0.5,
        ))
        
        result_disabled = arb_disabled.select_focus(tick_id=1)
        
        # Should produce different chosen candidates
        assert result_enabled.chosen_candidate.id == "external_best"
        assert result_disabled.chosen_candidate.id == "local_ok"
        
        # Candidate counts should differ
        assert result_enabled.all_candidates_count == 2
        assert result_disabled.all_candidates_count == 1


class TestEdgeCases:
    """Tests for edge cases."""
    
    def test_all_local_candidates(self):
        """Test when all candidates are local."""
        arb = Arbitrator()
        intervention = DisableBroadcastIntervention()
        arb.set_intervention_manager(intervention.manager)
        
        arb.add_candidate(Candidate(id="local_1", source="local", type=CandidateType.GOAL, utility=0.8))
        arb.add_candidate(Candidate(id="local_2", source="local", type=CandidateType.GOAL, utility=0.5))
        
        result = arb.select_focus(tick_id=1)
        
        # All local candidates should pass
        assert result.all_candidates_count == 2
        assert result.chosen_candidate.id == "local_1"
    
    def test_no_candidates_when_broadcast_disabled(self):
        """Test when no local candidates are available."""
        arb = Arbitrator()
        intervention = DisableBroadcastIntervention()
        arb.set_intervention_manager(intervention.manager)
        
        # Try to add only external candidates (will be blocked)
        arb.add_candidate(Candidate(id="external", source="drives", type=CandidateType.GOAL))
        
        result = arb.select_focus(tick_id=1)
        
        # Should return default
        assert result.chosen_focus == "default_explore"
        assert result.chosen_candidate is None
    
    def test_custom_local_source_name(self):
        """Test with custom local source name."""
        intervention = DisableBroadcastIntervention()
        
        candidates = [
            {"id": "local_1", "source": "workspace_local", "score": 0.5},
            {"id": "drives_1", "source": "drives", "score": 0.8},
        ]
        
        filtered = intervention.filter_candidates(candidates, local_source="workspace_local")
        
        assert len(filtered) == 1
        assert filtered[0]["source"] == "workspace_local"


class TestInteractionWithOtherInterventions:
    """Tests for interaction with other interventions."""
    
    def test_disable_broadcast_with_disable_hot(self):
        """Test that disable_broadcast works with disable_hot."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_BROADCAST)
        manager.enable(InterventionType.DISABLE_HOT)
        
        assert manager.is_broadcast_disabled()
        assert manager.is_hot_disabled()
    
    def test_disable_broadcast_with_freeze_valence(self):
        """Test that disable_broadcast works with freeze_valence."""
        manager = InterventionManager()
        manager.enable(InterventionType.DISABLE_BROADCAST)
        manager.enable(InterventionType.FREEZE_VALENCE, {"valence": 0.5})
        
        assert manager.is_broadcast_disabled()
        assert manager.is_active(InterventionType.FREEZE_VALENCE)
        
        result = manager.apply_intervention(valence=0.0)
        
        assert result.get("broadcast_disabled") is True
        assert result.get("valence") == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
