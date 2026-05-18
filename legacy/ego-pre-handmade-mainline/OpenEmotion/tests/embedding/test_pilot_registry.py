"""
Tests for Pilot Registry (v6f).

Validates:
- Scenario registration
- Pilot activation
- Metrics tracking
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
    PilotScenario,
    ScenarioStatus,
)


class TestScenarioStatus:
    """Test scenario status enum."""
    
    def test_pilot_candidate_exists(self):
        """PILOT_CANDIDATE should exist."""
        assert ScenarioStatus.PILOT_CANDIDATE.value == "pilot_candidate"
    
    def test_pilot_active_exists(self):
        """PILOT_ACTIVE should exist."""
        assert ScenarioStatus.PILOT_ACTIVE.value == "pilot_active"
    
    def test_promoted_exists(self):
        """PROMOTED should exist."""
        assert ScenarioStatus.PROMOTED.value == "promoted"
    
    def test_rolled_back_exists(self):
        """ROLLED_BACK should exist."""
        assert ScenarioStatus.ROLLED_BACK.value == "rolled_back"


class TestPilotConfig:
    """Test pilot configuration."""
    
    def test_default_config(self):
        """Should have sensible defaults."""
        config = PilotConfig()
        assert config.enabled is True
        assert config.min_pilot_sample_size == 30
        assert config.max_fallback_rate == 0.05
        assert config.min_pilot_rounds == 2
    
    def test_thresholds_defined(self):
        """Should have promotion and rollback thresholds."""
        config = PilotConfig()
        assert config.rollback_fallback_rate > config.max_fallback_rate
        assert config.rollback_p95_latency_ms > config.max_p95_latency_ms


class TestPilotRegistry:
    """Test pilot registry."""
    
    def test_production_whitelist_fixed(self):
        """Production whitelist should be fixed."""
        registry = PilotRegistry()
        whitelist = registry.get_production_whitelist()
        
        assert "memory_search_hard_query" in whitelist
        assert len(whitelist) == 3
    
    def test_pilot_candidates_defined(self):
        """Pilot candidates should be defined."""
        registry = PilotRegistry()
        candidates = registry.get_pilot_candidates()
        
        assert "complex_semantic_reasoning" in candidates
        assert len(candidates) >= 1
    
    def test_activate_pilot(self):
        """Should activate pilot scenario."""
        registry = PilotRegistry()
        
        result = registry.activate_pilot("complex_semantic_reasoning")
        
        assert result is True
        assert registry.pilot_scenarios["complex_semantic_reasoning"].status == ScenarioStatus.PILOT_ACTIVE
    
    def test_activate_unknown_scenario_fails(self):
        """Should fail to activate unknown scenario."""
        registry = PilotRegistry()
        
        result = registry.activate_pilot("unknown_scenario")
        
        assert result is False
    
    def test_deactivate_pilot(self):
        """Should deactivate pilot scenario."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        result = registry.deactivate_pilot("complex_semantic_reasoning")
        
        assert result is True
        assert registry.pilot_scenarios["complex_semantic_reasoning"].status == ScenarioStatus.ROLLED_BACK
    
    def test_promote_pilot(self):
        """Should promote pilot scenario."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        result = registry.promote_pilot("complex_semantic_reasoning")
        
        assert result is True
        assert registry.pilot_scenarios["complex_semantic_reasoning"].status == ScenarioStatus.PROMOTED
    
    def test_record_observation(self):
        """Should record pilot observation."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        registry.record_pilot_observation(
            scenario_name="complex_semantic_reasoning",
            success=True,
            latency_ms=50.0,
            fallback=False,
            quality_signal=0.2,
        )
        
        metrics = registry.get_pilot_metrics("complex_semantic_reasoning")
        assert metrics["pilot_sample_size"] == 1
        assert metrics["avg_quality_signal"] == 0.2
    
    def test_get_active_pilots(self):
        """Should get active pilot scenarios."""
        registry = PilotRegistry()
        
        # Initially no active pilots
        assert len(registry.get_active_pilot_scenarios()) == 0
        
        # Activate one
        registry.activate_pilot("complex_semantic_reasoning")
        
        active = registry.get_active_pilot_scenarios()
        assert len(active) == 1
        assert "complex_semantic_reasoning" in active


class TestPilotScenario:
    """Test pilot scenario metrics."""
    
    def test_fallback_rate(self):
        """Should calculate fallback rate."""
        scenario = PilotScenario(
            scenario_name="test",
            request_count=100,
            fallback_count=5,
        )
        
        assert scenario.fallback_rate == 0.05
    
    def test_latency_metrics(self):
        """Should calculate latency metrics."""
        scenario = PilotScenario(
            scenario_name="test",
            latencies=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )
        
        assert scenario.avg_latency_ms == 55
        assert scenario.p95_latency_ms == 100
    
    def test_quality_signal_average(self):
        """Should calculate quality signal average."""
        scenario = PilotScenario(
            scenario_name="test",
            quality_signal_samples=[0.1, 0.2, 0.3],
        )
        
        assert abs(scenario.avg_quality_signal - 0.2) < 0.0001


class TestWhitelistSeparation:
    """Test separation between whitelist and pilot."""
    
    def test_pilot_not_in_whitelist(self):
        """Pilot scenario should not be in production whitelist."""
        registry = PilotRegistry()
        
        whitelist = registry.get_production_whitelist()
        candidates = registry.get_pilot_candidates()
        
        # No overlap
        for candidate in candidates:
            assert candidate not in whitelist
    
    def test_separate_tracking(self):
        """Pilot metrics should be tracked separately."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        registry.record_pilot_observation(
            scenario_name="complex_semantic_reasoning",
            success=True,
            latency_ms=50.0,
        )
        
        metrics = registry.get_pilot_metrics("complex_semantic_reasoning")
        assert metrics["pilot_sample_size"] == 1
        
        # Production whitelist scenarios should have no data
        for scenario in registry.PRODUCTION_WHITELIST:
            prod_metrics = registry.get_pilot_metrics(scenario)
            assert prod_metrics is None or prod_metrics["pilot_sample_size"] == 0
