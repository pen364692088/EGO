"""
Tests for MVP11-T05: Homeostasis Workspace Integration.

Tests that homeostasis state affects focus selection through:
1. Homeostasis-driven candidate generation
2. Score modification for stressed dimensions
3. Homeostasis state logging in arbitration results
"""

import pytest
import sys
import os

# Add emotiond to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'emotiond'))

from homeostasis import HomeostasisManager, HomeostasisState
from workspace import (
    Arbitrator,
    Candidate,
    CandidatePool,
    CandidateType,
    ArbitrationResult,
    create_candidate,
    ENABLE_HOMEOSTASIS,
)


class TestHomeostasisCandidateGeneration:
    """Test that homeostasis state generates appropriate candidates."""
    
    def test_low_energy_generates_rest_candidate(self):
        """When energy is low, a REST candidate should be generated."""
        # Create manager with low energy
        state = HomeostasisState(energy=0.2, safety=0.7, certainty=0.7)
        manager = HomeostasisManager(initial_state=state)
        
        # Create pool and add homeostasis candidates
        pool = CandidatePool()
        added = pool.add_homeostasis_candidates(manager, stress_threshold=0.3)
        
        # Should have added rest candidate
        rest_candidates = [c for c in added if c.type == CandidateType.REST]
        assert len(rest_candidates) > 0, "Expected REST candidate when energy is low"
        
        # Verify the rest candidate properties
        rest = rest_candidates[0]
        assert rest.source == "homeostasis"
        assert rest.payload["dimension"] == "energy"
        assert rest.payload["focus"] == "rest"
    
    def test_low_certainty_generates_simplify_and_seek_info(self):
        """When certainty is low, both SIMPLIFY and INFO_SEEK candidates should be generated."""
        # Create manager with low certainty
        state = HomeostasisState(energy=0.7, safety=0.7, certainty=0.2)
        manager = HomeostasisManager(initial_state=state)
        
        # Create pool and add homeostasis candidates
        pool = CandidatePool()
        added = pool.add_homeostasis_candidates(manager, stress_threshold=0.3)
        
        # Should have both simplify and seek_info candidates
        simplify_candidates = [c for c in added if c.type == CandidateType.SIMPLIFY]
        info_seek_candidates = [c for c in added if c.type == CandidateType.INFO_SEEK]
        
        assert len(simplify_candidates) > 0, "Expected SIMPLIFY candidate when certainty is low"
        assert len(info_seek_candidates) > 0, "Expected INFO_SEEK candidate when certainty is low"
        
        # Verify they reference certainty dimension
        for c in simplify_candidates + info_seek_candidates:
            assert c.payload["dimension"] == "certainty"
    
    def test_low_safety_generates_defer_candidate(self):
        """When safety is low, a DEFER candidate should be generated."""
        # Create manager with low safety
        state = HomeostasisState(energy=0.7, safety=0.2, certainty=0.7)
        manager = HomeostasisManager(initial_state=state)
        
        # Create pool and add homeostasis candidates
        pool = CandidatePool()
        added = pool.add_homeostasis_candidates(manager, stress_threshold=0.3)
        
        # Should have defer candidate
        defer_candidates = [c for c in added if c.type == CandidateType.DEFER]
        assert len(defer_candidates) > 0, "Expected DEFER candidate when safety is low"
        
        # Verify properties
        defer = defer_candidates[0]
        assert defer.source == "homeostasis"
        assert defer.payload["dimension"] == "safety"
        assert defer.payload["focus"] == "defer_high_risk"
    
    def test_no_candidates_when_stable(self):
        """When all dimensions are stable, no homeostasis candidates should be generated."""
        # Create manager with healthy state
        state = HomeostasisState(
            energy=0.8,
            safety=0.8,
            certainty=0.8,
            affiliation=0.6,
            autonomy=0.7,
            fairness=0.7
        )
        manager = HomeostasisManager(initial_state=state)
        
        # Create pool and add homeostasis candidates
        pool = CandidatePool()
        added = pool.add_homeostasis_candidates(manager, stress_threshold=0.3)
        
        # Should have no candidates
        assert len(added) == 0, "Expected no homeostasis candidates when state is healthy"
    
    def test_multiple_stressed_dimensions(self):
        """When multiple dimensions are stressed, multiple candidates should be generated."""
        # Create manager with multiple stressed dimensions
        state = HomeostasisState(energy=0.2, safety=0.2, certainty=0.7)
        manager = HomeostasisManager(initial_state=state)
        
        # Create pool and add homeostasis candidates
        pool = CandidatePool()
        added = pool.add_homeostasis_candidates(manager, stress_threshold=0.3)
        
        # Should have REST (energy) and DEFER (safety) candidates
        types_added = {c.type for c in added}
        assert CandidateType.REST in types_added
        assert CandidateType.DEFER in types_added


class TestHomeostasisScoreModifier:
    """Test that homeostasis state modifies candidate scores correctly."""
    
    def test_rest_candidate_boosted_when_energy_low(self):
        """REST candidates should get score boost when energy is stressed."""
        arbitrator = Arbitrator()
        
        # Create manager with low energy
        state = HomeostasisState(energy=0.2, certainty=0.7, safety=0.7)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Get homeostasis signal
        hs_signal = manager.signal()
        
        # Create REST candidate
        rest_candidate = Candidate(
            id="test_rest",
            source="homeostasis",
            type=CandidateType.REST,
            utility=0.5
        )
        
        # Compute modifier
        modifier = arbitrator._compute_homeostasis_modifier(rest_candidate, hs_signal)
        
        # Should be positive boost
        assert modifier > 0, f"Expected positive boost for REST when energy low, got {modifier}"
    
    def test_simplify_candidate_boosted_when_certainty_low(self):
        """SIMPLIFY candidates should get score boost when certainty is stressed."""
        arbitrator = Arbitrator()
        
        # Create manager with low certainty
        state = HomeostasisState(energy=0.7, certainty=0.2, safety=0.7)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Get homeostasis signal
        hs_signal = manager.signal()
        
        # Create SIMPLIFY candidate
        simplify_candidate = Candidate(
            id="test_simplify",
            source="homeostasis",
            type=CandidateType.SIMPLIFY,
            utility=0.5
        )
        
        # Compute modifier
        modifier = arbitrator._compute_homeostasis_modifier(simplify_candidate, hs_signal)
        
        # Should be positive boost
        assert modifier > 0, f"Expected positive boost for SIMPLIFY when certainty low, got {modifier}"
    
    def test_defer_candidate_boosted_when_safety_low(self):
        """DEFER candidates should get score boost when safety is stressed."""
        arbitrator = Arbitrator()
        
        # Create manager with low safety
        state = HomeostasisState(energy=0.7, certainty=0.7, safety=0.2)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Get homeostasis signal
        hs_signal = manager.signal()
        
        # Create DEFER candidate
        defer_candidate = Candidate(
            id="test_defer",
            source="homeostasis",
            type=CandidateType.DEFER,
            utility=0.5
        )
        
        # Compute modifier
        modifier = arbitrator._compute_homeostasis_modifier(defer_candidate, hs_signal)
        
        # Should be positive boost
        assert modifier > 0, f"Expected positive boost for DEFER when safety low, got {modifier}"
    
    def test_no_modifier_when_no_stress(self):
        """Candidates should not get boost when no dimensions are stressed."""
        arbitrator = Arbitrator()
        
        # Create manager with healthy state
        state = HomeostasisState(energy=0.8, certainty=0.8, safety=0.8)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Get homeostasis signal
        hs_signal = manager.signal()
        
        # Create candidates
        rest_candidate = Candidate(
            id="test_rest",
            source="homeostasis",
            type=CandidateType.REST,
            utility=0.5
        )
        
        # Compute modifier
        modifier = arbitrator._compute_homeostasis_modifier(rest_candidate, hs_signal)
        
        # Should be zero
        assert modifier == 0, f"Expected zero modifier when no stress, got {modifier}"


class TestHomeostasisInArbitration:
    """Test homeostasis integration in full arbitration flow."""
    
    def test_homeostasis_state_logged_in_result(self):
        """ArbitrationResult should include homeostasis_state."""
        arbitrator = Arbitrator()
        
        # Create manager with specific state
        state = HomeostasisState(energy=0.6, safety=0.7, certainty=0.5)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Add a candidate
        candidate = create_candidate(
            source="test",
            candidate_type="intent",
            utility=0.6
        )
        arbitrator.add_candidate(candidate)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Check homeostasis state is logged
        assert result.homeostasis_state is not None
        assert result.homeostasis_state["energy"] == 0.6
        assert result.homeostasis_state["safety"] == 0.7
        assert result.homeostasis_state["certainty"] == 0.5
    
    def test_homeostasis_candidates_included_in_selection(self):
        """Homeostasis candidates should be included during focus selection."""
        arbitrator = Arbitrator()
        
        # Create manager with low energy
        state = HomeostasisState(energy=0.1, safety=0.8, certainty=0.8)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Add a regular candidate with low utility
        regular_candidate = create_candidate(
            source="test",
            candidate_type="intent",
            utility=0.3,
            rationale="Low utility regular candidate"
        )
        arbitrator.add_candidate(regular_candidate)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Should have considered homeostasis candidates
        assert result.all_candidates_count >= 2, "Should have at least regular + homeostasis candidates"
    
    def test_homeostasis_urgency_in_rationale(self):
        """Arbitration rationale should include homeostasis urgency when present."""
        arbitrator = Arbitrator()
        
        # Create manager with stressed dimensions (will have urgency)
        state = HomeostasisState(energy=0.1, safety=0.1, certainty=0.1)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Add a candidate
        candidate = create_candidate(
            source="test",
            candidate_type="intent",
            utility=0.6
        )
        arbitrator.add_candidate(candidate)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Check rationale includes homeostasis info
        assert "hs_urgency" in result.rationale, "Rationale should include homeostasis urgency"
    
    def test_feature_flag_disables_homeostasis(self, monkeypatch):
        """When ENABLE_HOMEOSTASIS is False, homeostasis should not affect selection."""
        import workspace as ws_module
        
        # Temporarily disable the feature flag
        original_value = ws_module.ENABLE_HOMEOSTASIS
        ws_module.ENABLE_HOMEOSTASIS = False
        
        try:
            arbitrator = Arbitrator()
            
            # Create manager with stressed state
            state = HomeostasisState(energy=0.1, safety=0.1, certainty=0.1)
            manager = HomeostasisManager(initial_state=state)
            arbitrator.set_homeostasis_manager(manager)
            
            # Add a candidate
            candidate = create_candidate(
                source="test",
                candidate_type="intent",
                utility=0.6
            )
            arbitrator.add_candidate(candidate)
            
            # Run arbitration
            result = arbitrator.select_focus(tick_id=1)
            
            # Homeostasis candidates should not have been added
            # Only the one regular candidate
            assert result.all_candidates_count == 1
        finally:
            # Restore the feature flag
            ws_module.ENABLE_HOMEOSTASIS = original_value


class TestArbitrationResultSerialization:
    """Test that ArbitrationResult with homeostasis_state serializes correctly."""
    
    def test_to_dict_includes_homeostasis_state(self):
        """ArbitrationResult.to_dict() should include homeostasis_state."""
        result = ArbitrationResult(
            chosen_focus="rest",
            chosen_candidate=None,
            rationale="Test rationale",
            tick_id=1,
            homeostasis_state={
                "energy": 0.2,
                "safety": 0.7,
                "certainty": 0.5,
                "affiliation": 0.6,
                "autonomy": 0.7,
                "fairness": 0.6
            }
        )
        
        d = result.to_dict()
        
        assert "homeostasis_state" in d
        assert d["homeostasis_state"]["energy"] == 0.2
        assert d["homeostasis_state"]["certainty"] == 0.5
    
    def test_none_homeostasis_state_serializes(self):
        """ArbitrationResult with None homeostasis_state should serialize."""
        result = ArbitrationResult(
            chosen_focus="test",
            chosen_candidate=None,
            rationale="Test",
            tick_id=1,
            homeostasis_state=None
        )
        
        d = result.to_dict()
        
        assert "homeostasis_state" in d
        assert d["homeostasis_state"] is None


class TestIntegrationScenarios:
    """Integration tests for homeostasis affecting focus selection."""
    
    def test_energy_crisis_prioritizes_rest(self):
        """In an energy crisis, rest should be prioritized over other actions."""
        arbitrator = Arbitrator()
        
        # Create manager with critically low energy
        state = HomeostasisState(energy=0.1, safety=0.8, certainty=0.8)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Add a high-utility action candidate
        action_candidate = Candidate(
            id="action_1",
            source="planner",
            type=CandidateType.ACTION,
            utility=0.8,
            risk=0.1,
            cost=0.2,
            rationale="Important action"
        )
        arbitrator.add_candidate(action_candidate)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # REST candidate should have been considered (added by homeostasis)
        # The result should include homeostasis state
        assert result.homeostasis_state is not None
        assert result.homeostasis_state["energy"] == 0.1
        
        # Rationale should mention homeostasis
        assert "homeostasis" in result.rationale.lower() or "hs_" in result.rationale
    
    def test_uncertainty_seeks_info(self):
        """When uncertain, system should seek information."""
        arbitrator = Arbitrator()
        
        # Create manager with low certainty
        state = HomeostasisState(energy=0.8, safety=0.8, certainty=0.1)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Should have generated info_seek and simplify candidates
        assert result.all_candidates_count >= 2, "Should have at least SIMPLIFY and INFO_SEEK candidates"
    
    def test_safety_crisis_defers_risky_actions(self):
        """When safety is low, system should prefer defer over risky actions."""
        arbitrator = Arbitrator()
        
        # Create manager with low safety
        state = HomeostasisState(energy=0.8, certainty=0.8, safety=0.1)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Add a risky action
        risky_action = Candidate(
            id="risky_1",
            source="planner",
            type=CandidateType.ACTION,
            utility=0.7,
            risk=0.8,  # High risk
            cost=0.3,
            rationale="Risky but valuable action"
        )
        arbitrator.add_candidate(risky_action)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Homeostasis should have added defer candidate
        assert result.all_candidates_count >= 2
        assert result.homeostasis_state["safety"] == 0.1


class TestEdgeCases:
    """Edge case tests for homeostasis integration."""
    
    def test_no_homeostasis_manager(self):
        """Arbitrator should work without a homeostasis manager."""
        arbitrator = Arbitrator()
        # Don't set a homeostasis manager
        
        # Add a candidate
        candidate = create_candidate(
            source="test",
            candidate_type="intent",
            utility=0.6
        )
        arbitrator.add_candidate(candidate)
        
        # Run arbitration
        result = arbitrator.select_focus(tick_id=1)
        
        # Should work without error
        assert result.chosen_focus is not None
        assert result.homeostasis_state is None
    
    def test_empty_pool_with_homeostasis(self):
        """Arbitration with no candidates but homeostasis should still generate candidates."""
        arbitrator = Arbitrator()
        
        # Create manager with stressed state
        state = HomeostasisState(energy=0.1, safety=0.1, certainty=0.1)
        manager = HomeostasisManager(initial_state=state)
        arbitrator.set_homeostasis_manager(manager)
        
        # Run arbitration without adding any candidates
        result = arbitrator.select_focus(tick_id=1)
        
        # Homeostasis candidates should have been added
        assert result.all_candidates_count >= 1, "Homeostasis should add candidates to empty pool"
        assert result.homeostasis_state is not None
    
    def test_duplicate_homeostasis_candidates(self):
        """Adding homeostasis candidates multiple times should not create duplicates."""
        pool = CandidatePool()
        
        # Create manager with low energy
        state = HomeostasisState(energy=0.1, safety=0.8, certainty=0.8)
        manager = HomeostasisManager(initial_state=state)
        
        # Add homeostasis candidates twice
        added1 = pool.add_homeostasis_candidates(manager)
        added2 = pool.add_homeostasis_candidates(manager)
        
        # Second time should not add duplicates (same IDs)
        assert len(added1) >= 1
        assert len(added2) == 0, "Second call should not add duplicates"
        assert len(pool) == len(added1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
