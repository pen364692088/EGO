"""
Tests for Expansion Governance (v6e).

Validates:
- Expansion verdicts
- Observation window
- Threshold checking
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.observation_window import (
    ObservationWindow,
    ObservationThresholds,
    ScenarioObservation,
)
from emotiond.memory.embedding.expansion_governance import (
    ExpansionGovernor,
    ExpansionVerdict,
    ExpansionBlocker,
    ExpansionDecision,
)


class TestObservationThresholds:
    """Test observation thresholds."""
    
    def test_default_thresholds(self):
        """Should have sensible defaults."""
        thresholds = ObservationThresholds()
        assert thresholds.min_total_sample_size == 60
        assert thresholds.min_sample_size_per_scenario == 15
        assert thresholds.min_observation_rounds == 3
        assert thresholds.max_fallback_rate == 0.05
        assert thresholds.max_wrong_user_guard_trigger == 0


class TestScenarioObservation:
    """Test scenario observation."""
    
    def test_fallback_rate_calculation(self):
        """Should calculate fallback rate."""
        obs = ScenarioObservation(
            scenario_name="test",
            request_count=100,
            fallback_count=5,
        )
        assert obs.fallback_rate == 0.05
    
    def test_latency_calculations(self):
        """Should calculate latency metrics."""
        obs = ScenarioObservation(
            scenario_name="test",
            latencies=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )
        assert obs.avg_latency_ms == 55
        assert obs.p95_latency_ms == 100


class TestObservationWindow:
    """Test observation window."""
    
    def test_start_and_end_round(self):
        """Should start and end rounds."""
        window = ObservationWindow()
        
        round_data = window.start_round()
        assert round_data.round_id == 1
        
        completed = window.end_round()
        assert completed.verdict == "observed"
        assert len(window.rounds) == 1
    
    def test_record_observation(self):
        """Should record observations."""
        window = ObservationWindow()
        window.start_round()
        
        window.record_observation(
            scenario_name="memory_search_hard_query",
            success=True,
            latency_ms=50.0,
            fallback=False,
        )
        
        metrics = window.get_aggregated_metrics()
        assert metrics["total_sample_size"] == 0  # Round not ended yet
    
    def test_aggregate_metrics(self):
        """Should aggregate metrics across rounds."""
        window = ObservationWindow()
        
        # Round 1
        window.start_round()
        for _ in range(20):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=50.0,
                fallback=False,
            )
        window.end_round()
        
        # Round 2
        window.start_round()
        for _ in range(20):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=60.0,
                fallback=False,
            )
        window.end_round()
        
        metrics = window.get_aggregated_metrics()
        assert metrics["total_sample_size"] == 40
        assert metrics["rounds_observed"] == 2
    
    def test_check_readiness(self):
        """Should check readiness for expansion."""
        window = ObservationWindow()
        
        # Add enough data
        for round_id in range(1, 4):
            window.start_round()
            for scenario in window.WHITELIST_SCENARIOS:
                for _ in range(20):
                    window.record_observation(
                        scenario_name=scenario,
                        success=True,
                        latency_ms=50.0,
                        fallback=False,
                    )
            window.end_round()
        
        readiness = window.check_readiness()
        assert readiness["all_passed"] is True


class TestExpansionGovernor:
    """Test expansion governor."""
    
    def test_keep_same_scope_insufficient_samples(self):
        """Should keep same scope with insufficient samples."""
        window = ObservationWindow()
        
        window.start_round()
        for _ in range(10):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=50.0,
                fallback=False,
                wrong_user_trigger=False,
            )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        # With low sample and 0 rounds meeting threshold, should be keep_same_scope
        assert decision.verdict in [ExpansionVerdict.KEEP_SAME_SCOPE, ExpansionVerdict.SHRINK_OR_ROLLBACK]
    
    def test_shrink_on_high_fallback(self):
        """Should shrink on high fallback rate."""
        thresholds = ObservationThresholds()
        window = ObservationWindow(thresholds)
        
        window.start_round()
        for _ in range(100):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=50.0,
                fallback=True,  # All fallbacks
            )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        assert decision.verdict == ExpansionVerdict.SHRINK_OR_ROLLBACK
    
    def test_shrink_on_high_latency(self):
        """Should shrink on high latency."""
        thresholds = ObservationThresholds()
        window = ObservationWindow(thresholds)
        
        window.start_round()
        for _ in range(100):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=500.0,  # Very high latency
                fallback=False,
            )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        assert decision.verdict == ExpansionVerdict.SHRINK_OR_ROLLBACK
    
    def test_expand_when_ready(self):
        """Should allow expansion when ready."""
        thresholds = ObservationThresholds()
        window = ObservationWindow(thresholds)
        
        # Add 3 rounds with enough data
        for _ in range(3):
            window.start_round()
            for scenario in window.WHITELIST_SCENARIOS:
                for _ in range(25):
                    window.record_observation(
                        scenario_name=scenario,
                        success=True,
                        latency_ms=50.0,
                        fallback=False,
                        quality_gain=0.2,
                        provider_healthy=True,
                    )
            window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        assert decision.verdict == ExpansionVerdict.EXPAND_ONE_MORE_SCENARIO
        assert len(decision.blockers) == 0
    
    def test_fixed_whitelist(self):
        """Should return fixed whitelist."""
        governor = ExpansionGovernor()
        whitelist = governor.get_current_whitelist()
        
        assert "memory_search_hard_query" in whitelist
        assert len(whitelist) == 3
    
    def test_candidate_scenarios(self):
        """Should return candidate scenarios."""
        governor = ExpansionGovernor()
        candidates = governor.get_candidate_scenarios()
        
        assert len(candidates) > 0


class TestExpansionDecision:
    """Test expansion decision."""
    
    def test_to_dict(self):
        """Should serialize to dict."""
        decision = ExpansionDecision(
            verdict=ExpansionVerdict.KEEP_SAME_SCOPE,
            rationale="Test",
            next_allowed_action="Continue",
        )
        
        d = decision.to_dict()
        
        assert d["verdict"] == "keep_same_scope"
        assert d["rationale"] == "Test"
        assert "timestamp" in d


class TestCapabilityOwnership:
    """Test capability ownership."""
    
    def test_observation_window_in_openemotion(self):
        """Observation window must be in OpenEmotion."""
        from emotiond.memory.embedding import observation_window
        
        assert "emotiond" in observation_window.__file__
    
    def test_expansion_governance_in_openemotion(self):
        """Expansion governance must be in OpenEmotion."""
        from emotiond.memory.embedding import expansion_governance
        
        assert "emotiond" in expansion_governance.__file__
