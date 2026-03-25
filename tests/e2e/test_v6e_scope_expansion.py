"""
E2E Tests for v6e Scope Expansion.

Validates:
- Observation window flow
- Expansion decision flow
- Verdict logic
"""

import json
import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.observation_window import (
    ObservationWindow,
    ObservationThresholds,
)
from emotiond.memory.embedding.expansion_governance import (
    ExpansionGovernor,
    ExpansionVerdict,
)


class TestObservationWindowFlow:
    """Test observation window flow."""
    
    def test_multi_round_observation(self):
        """Should support multiple observation rounds."""
        window = ObservationWindow()
        
        for round_id in range(1, 4):
            window.start_round()
            for _ in range(20):
                window.record_observation(
                    scenario_name="memory_search_hard_query",
                    success=True,
                    latency_ms=50.0,
                    fallback=False,
                )
            window.end_round()
        
        metrics = window.get_aggregated_metrics()
        assert metrics["rounds_observed"] == 3
        assert metrics["total_sample_size"] == 60
    
    def test_metrics_by_scenario(self):
        """Should track metrics per scenario."""
        window = ObservationWindow()
        
        window.start_round()
        
        window.record_observation(
            scenario_name="memory_search_hard_query",
            success=True,
            latency_ms=50.0,
            fallback=False,
        )
        window.record_observation(
            scenario_name="narrative_recall_ambiguous_query",
            success=True,
            latency_ms=60.0,
            fallback=True,
        )
        
        window.end_round()
        
        metrics = window.get_aggregated_metrics()
        assert "memory_search_hard_query" in metrics["scenario_metrics"]
        assert "narrative_recall_ambiguous_query" in metrics["scenario_metrics"]


class TestExpansionDecisionFlow:
    """Test expansion decision flow."""
    
    def test_insufficient_data_verdict(self):
        """Should return keep_same_scope with insufficient data."""
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
        
        assert decision.verdict in [ExpansionVerdict.KEEP_SAME_SCOPE, ExpansionVerdict.SHRINK_OR_ROLLBACK]
    
    def test_rollback_on_critical_issue(self):
        """Should return shrink_or_rollback on critical issue."""
        window = ObservationWindow()
        
        window.start_round()
        for _ in range(100):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=500.0,  # Critical: very high latency
                fallback=False,
            )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        assert decision.verdict == ExpansionVerdict.SHRINK_OR_ROLLBACK
    
    def test_expansion_when_ready(self):
        """Should return expand when all criteria met."""
        thresholds = ObservationThresholds()
        window = ObservationWindow(thresholds)
        
        # Add sufficient data across all scenarios
        for _ in range(3):
            window.start_round()
            for scenario in window.WHITELIST_SCENARIOS:
                for _ in range(20):
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


class TestExpansionReport:
    """Test expansion report generation."""
    
    def test_report_serialization(self):
        """Should serialize report to JSON."""
        window = ObservationWindow()
        
        window.start_round()
        window.record_observation(
            scenario_name="memory_search_hard_query",
            success=True,
            latency_ms=50.0,
            fallback=False,
        )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision.to_dict(),
        }
        
        json_str = json.dumps(report)
        assert json_str is not None
        
        parsed = json.loads(json_str)
        assert "decision" in parsed
        assert "verdict" in parsed["decision"]


class TestWhitelistFixed:
    """Test that whitelist is fixed."""
    
    def test_whitelist_unchangeable(self):
        """Whitelist should be fixed for v6e."""
        governor = ExpansionGovernor()
        whitelist = governor.get_current_whitelist()
        
        # Should have exactly 3 scenarios
        assert len(whitelist) == 3
        assert "memory_search_hard_query" in whitelist
        assert "narrative_recall_ambiguous_query" in whitelist
        assert "long_context_semantic_lookup" in whitelist
    
    def test_candidates_available(self):
        """Candidate scenarios should be available for future."""
        governor = ExpansionGovernor()
        candidates = governor.get_candidate_scenarios()
        
        # Should have candidates for expansion
        assert len(candidates) >= 1


class TestVerdictScenarios:
    """Test various verdict scenarios."""
    
    def test_scenario_keep_same_scope_few_rounds(self):
        """Few rounds should keep same scope."""
        window = ObservationWindow()
        
        # Only 1 round
        window.start_round()
        for scenario in window.WHITELIST_SCENARIOS:
            for _ in range(25):
                window.record_observation(
                    scenario_name=scenario,
                    success=True,
                    latency_ms=50.0,
                    fallback=False,
                )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        assert decision.verdict == ExpansionVerdict.KEEP_SAME_SCOPE
        assert any("round" in b.message.lower() for b in decision.blockers)
    
    def test_scenario_shrink_wrong_user(self):
        """Wrong user triggers should cause shrink or keep."""
        window = ObservationWindow()
        
        window.start_round()
        for _ in range(100):
            window.record_observation(
                scenario_name="memory_search_hard_query",
                success=True,
                latency_ms=50.0,
                fallback=False,
                wrong_user_trigger=True,  # Critical issue - causes fallback check
            )
        window.end_round()
        
        governor = ExpansionGovernor(window)
        decision = governor.evaluate_scope_expansion()
        
        # Wrong user trigger > 0 should cause issues
        assert decision.verdict in [ExpansionVerdict.KEEP_SAME_SCOPE, ExpansionVerdict.SHRINK_OR_ROLLBACK]
