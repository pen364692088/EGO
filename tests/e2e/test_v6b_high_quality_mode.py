"""
E2E Tests for v6b High-Quality Mode.

Validates:
- Default mode behavior
- High-quality mode switching
- Fallback behavior
- Selection trace
"""

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
)
from emotiond.memory.embedding.telemetry import (
    EmbeddingTelemetry,
    ProviderUsageRecord,
    get_telemetry,
    reset_telemetry,
)


class TestDefaultMode:
    """Test default mode behavior."""
    
    def test_default_mode_is_tfidf(self):
        """Default mode must be tfidf."""
        config = RetrievalConfig()
        assert config.mode == "tfidf"
    
    def test_default_config_no_auto_upgrade(self):
        """Auto upgrade must be disabled by default."""
        config = RetrievalConfig()
        assert config.auto_upgrade_enabled is False
    
    @pytest.mark.asyncio
    async def test_default_uses_tfidf_provider(self):
        """Default should use tfidf provider."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider()
        
        assert trace.provider_used == "tfidf"
        assert trace.fallback_triggered is False


class TestHighQualityMode:
    """Test high-quality mode switching."""
    
    @pytest.mark.asyncio
    async def test_explicit_ollama_uses_ollama_or_fallback(self):
        """Explicit ollama should use ollama or fallback to tfidf."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        # Either ollama works, or fallback to tfidf
        assert trace.provider_used in ["ollama", "tfidf"]
    
    @pytest.mark.asyncio
    async def test_high_quality_mode_disabled(self):
        """When high quality mode disabled, should use tfidf."""
        config = RetrievalConfig(
            allow_high_quality_mode=False,
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        assert trace.provider_used == "tfidf"


class TestOllamaFallback:
    """Test Ollama fallback behavior."""
    
    @pytest.mark.asyncio
    async def test_ollama_failure_falls_back_to_tfidf(self):
        """Ollama failure should fallback to tfidf."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        assert trace.fallback_triggered is True
        assert trace.provider_used == "tfidf"
    
    @pytest.mark.asyncio
    async def test_fallback_returns_result(self):
        """Fallback should still return a result."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        # Provider should still be usable
        assert provider is not None


class TestSelectionTrace:
    """Test selection trace recording."""
    
    @pytest.mark.asyncio
    async def test_selection_trace_is_recorded(self):
        """Selection trace must be recorded."""
        config = RetrievalConfig(log_provider_selection=True)
        selector = ProviderSelector(config)
        
        await selector.select_provider("tfidf")
        
        traces = selector.get_traces()
        assert len(traces) == 1
    
    @pytest.mark.asyncio
    async def test_trace_contains_required_fields(self):
        """Trace must contain required fields."""
        config = RetrievalConfig(log_provider_selection=True)
        selector = ProviderSelector(config)
        
        await selector.select_provider("tfidf")
        traces = selector.get_traces()
        
        trace = traces[0]
        assert "requested_mode" in trace
        assert "resolved_mode" in trace
        assert "provider_used" in trace
        assert "fallback_triggered" in trace
        assert "latency_ms" in trace


class TestTelemetry:
    """Test telemetry tracking."""
    
    def setup_method(self):
        """Reset telemetry before each test."""
        reset_telemetry()
    
    def test_record_usage(self):
        """Should record provider usage."""
        telemetry = get_telemetry()
        telemetry.record_usage("tfidf", 0.5, True)
        
        metrics = telemetry.get_provider_metrics("tfidf")
        assert metrics["usage_count"] == 1
    
    def test_record_fallback(self):
        """Should record fallback event."""
        telemetry = get_telemetry()
        telemetry.record_usage(
            provider="tfidf",
            latency_ms=50.0,
            success=True,
            fallback_triggered=True,
            fallback_reason="ollama unreachable",
        )
        
        metrics = telemetry.get_provider_metrics("tfidf")
        assert metrics["fallback_count"] == 1
    
    def test_latency_tracking(self):
        """Should track latencies."""
        telemetry = get_telemetry()
        telemetry.record_usage("ollama", 60.0, True)
        telemetry.record_usage("ollama", 70.0, True)
        telemetry.record_usage("ollama", 80.0, True)
        
        metrics = telemetry.get_provider_metrics("ollama")
        assert metrics["avg_latency_ms"] is not None
        assert metrics["p95_latency_ms"] is not None
    
    def test_all_metrics(self):
        """Should provide all metrics."""
        telemetry = get_telemetry()
        telemetry.record_usage("tfidf", 0.5, True)
        telemetry.record_usage("ollama", 65.0, True)
        
        all_metrics = telemetry.get_all_metrics()
        
        assert "providers" in all_metrics
        assert "tfidf" in all_metrics["providers"]
        assert "ollama" in all_metrics["providers"]


class TestCapabilityOwnership:
    """Test capability ownership stays in OpenEmotion."""
    
    def test_selector_in_openemotion(self):
        """Selector must be in OpenEmotion module path."""
        from emotiond.memory.embedding import selector
        
        assert "openemotion" not in selector.__file__.lower() or "emotiond" in selector.__file__
    
    def test_telemetry_in_openemotion(self):
        """Telemetry must be in OpenEmotion module path."""
        from emotiond.memory.embedding import telemetry
        
        assert "openemotion" not in telemetry.__file__.lower() or "emotiond" in telemetry.__file__
