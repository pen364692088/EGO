"""
E2E Tests for v6f Candidate Scenario Pilot.

Validates:
- Pilot activation
- Quality signal computation
- Promotion/rollback decisions
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
    ScenarioStatus,
)
from emotiond.memory.embedding.pilot_evaluator import (
    PilotEvaluator,
    PilotVerdict,
)
from emotiond.memory.embedding.quality_signal import (
    QualitySignalCalculator,
    QualitySignalSource,
)


class TestPilotActivation:
    """Test pilot activation flow."""
    
    def test_activate_candidate(self):
        """Should activate pilot candidate."""
        registry = PilotRegistry()
        
        result = registry.activate_pilot("complex_semantic_reasoning")
        
        assert result is True
        assert "complex_semantic_reasoning" in registry.get_active_pilot_scenarios()
    
    def test_deactivate_pilot(self):
        """Should deactivate pilot."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        result = registry.deactivate_pilot("complex_semantic_reasoning")
        
        assert result is True
        assert registry.pilot_scenarios["complex_semantic_reasoning"].status == ScenarioStatus.ROLLED_BACK


class TestQualitySignalInPilot:
    """Test quality signal integration in pilot."""
    
    def test_record_quality_signal(self):
        """Should record quality signal in pilot."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        registry.record_pilot_observation(
            scenario_name="complex_semantic_reasoning",
            success=True,
            latency_ms=50.0,
            fallback=False,
            quality_signal=0.25,
        )
        
        metrics = registry.get_pilot_metrics("complex_semantic_reasoning")
        assert metrics["avg_quality_signal"] == 0.25
    
    def test_multiple_signal_samples(self):
        """Should average multiple signal samples."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        for signal in [0.1, 0.2, 0.3]:
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                quality_signal=signal,
            )
        
        metrics = registry.get_pilot_metrics("complex_semantic_reasoning")
        assert abs(metrics["avg_quality_signal"] - 0.2) < 0.01


class TestPilotEvaluation:
    """Test pilot evaluation decisions."""
    
    def test_insufficient_samples_keep_pilot(self):
        """Insufficient samples should keep in pilot."""
        registry = PilotRegistry()
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Only a few samples
        for _ in range(5):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                quality_signal=0.2,
            )
        
        evaluator = PilotEvaluator(registry)
        decision = evaluator.evaluate_pilot("complex_semantic_reasoning")
        
        assert decision.verdict == PilotVerdict.KEEP_PILOT
    
    def test_rollback_on_high_fallback(self):
        """High fallback should trigger rollback."""
        config = PilotConfig()
        registry = PilotRegistry(config)
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Many observations with high fallback
        for _ in range(50):
            registry.record_pilot_observation(
                scenario_name="complex_semantic_reasoning",
                success=True,
                latency_ms=50.0,
                fallback=True,  # All fallbacks
                quality_signal=0.2,
            )
        
        evaluator = PilotEvaluator(registry)
        decision = evaluator.evaluate_pilot("complex_semantic_reasoning")
        
        assert decision.verdict == PilotVerdict.ROLLBACK
    
    def test_promote_when_ready(self):
        """Should promote when all criteria met."""
        config = PilotConfig()
        registry = PilotRegistry(config)
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Sufficient samples with good metrics
        for round_id in range(2):
            for _ in range(20):
                registry.record_pilot_observation(
                    scenario_name="complex_semantic_reasoning",
                    success=True,
                    latency_ms=60.0,
                    fallback=False,
                    wrong_user_trigger=False,
                    quality_signal=0.2,
                    provider_healthy=True,
                )
            registry.increment_pilot_round("complex_semantic_reasoning")
        
        evaluator = PilotEvaluator(registry)
        decision = evaluator.evaluate_pilot("complex_semantic_reasoning")
        
        assert decision.verdict == PilotVerdict.PROMOTE


class TestQualitySignalDecisionImpact:
    """Test quality signal impact on decisions."""
    
    def test_no_quality_signal_blocks_promotion(self):
        """Missing quality signal should block promotion."""
        config = PilotConfig()
        registry = PilotRegistry(config)
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Good metrics but no quality signal
        for round_id in range(2):
            for _ in range(20):
                registry.record_pilot_observation(
                    scenario_name="complex_semantic_reasoning",
                    success=True,
                    latency_ms=60.0,
                    # No quality signal
                )
            registry.increment_pilot_round("complex_semantic_reasoning")
        
        evaluator = PilotEvaluator(registry)
        decision = evaluator.evaluate_pilot("complex_semantic_reasoning")
        
        # Should not promote without quality signal
        assert decision.verdict == PilotVerdict.KEEP_PILOT
        assert any(b.category == "quality_signal" for b in decision.blockers)
    
    def test_negative_quality_signal_blocks_promotion(self):
        """Negative quality signal should block promotion."""
        config = PilotConfig()
        registry = PilotRegistry(config)
        registry.activate_pilot("complex_semantic_reasoning")
        
        # Good metrics but negative signal
        for round_id in range(2):
            for _ in range(20):
                registry.record_pilot_observation(
                    scenario_name="complex_semotic_reasoning",
                    success=True,
                    latency_ms=60.0,
                    quality_signal=-0.1,  # Negative
                )
            registry.increment_pilot_round("complex_semantic_reasoning")
        
        evaluator = PilotEvaluator(registry)
        decision = evaluator.evaluate_pilot("complex_semantic_reasoning")
        
        assert decision.verdict in [PilotVerdict.KEEP_PILOT, PilotVerdict.ROLLBACK]


class TestCapabilityOwnership:
    """Test capability ownership."""
    
    def test_pilot_registry_in_openemotion(self):
        """Pilot registry must be in OpenEmotion."""
        from emotiond.memory.embedding import pilot_registry
        
        assert "emotiond" in pilot_registry.__file__
    
    def test_quality_signal_in_openemotion(self):
        """Quality signal must be in OpenEmotion."""
        from emotiond.memory.embedding import quality_signal
        
        assert "emotiond" in quality_signal.__file__
    
    def test_pilot_evaluator_in_openemotion(self):
        """Pilot evaluator must be in OpenEmotion."""
        from emotiond.memory.embedding import pilot_evaluator
        
        assert "emotiond" in pilot_evaluator.__file__
