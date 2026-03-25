"""
Tests for Provider Selection (v6b).

Validates:
- Default mode is tfidf
- Explicit tfidf/ollama selection
- Fallback mechanism
- Selection trace recording
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
    RetrievalMode,
    ProviderSelectionTrace,
    select_retrieval_mode,
)
from emotiond.memory.embedding.contracts import FailureCategory


class TestRetrievalMode:
    """Test retrieval mode enum."""
    
    def test_tfidf_mode_exists(self):
        """TFIDF mode should exist."""
        assert RetrievalMode.TFIDF.value == "tfidf"
    
    def test_ollama_mode_exists(self):
        """Ollama mode should exist."""
        assert RetrievalMode.OLLAMA.value == "ollama"
    
    def test_auto_mode_exists(self):
        """Auto mode should exist."""
        assert RetrievalMode.AUTO.value == "auto"


class TestRetrievalConfig:
    """Test retrieval configuration."""
    
    def test_default_mode_is_tfidf(self):
        """Default mode should be tfidf."""
        config = RetrievalConfig()
        assert config.mode == "tfidf"
    
    def test_auto_upgrade_disabled_by_default(self):
        """Auto upgrade should be disabled by default."""
        config = RetrievalConfig()
        assert config.auto_upgrade_enabled is False
    
    def test_fallback_enabled_by_default(self):
        """Fallback should be enabled by default."""
        config = RetrievalConfig()
        assert config.fallback_on_provider_failure is True
    
    def test_high_quality_mode_allowed_by_default(self):
        """High quality mode should be allowed by default."""
        config = RetrievalConfig()
        assert config.allow_high_quality_mode is True


class TestProviderSelector:
    """Test provider selector."""
    
    def test_resolve_default_mode(self):
        """Should resolve to default mode when none specified."""
        config = RetrievalConfig(mode="tfidf")
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode()
        assert resolved == "tfidf"
    
    def test_resolve_explicit_tfidf(self):
        """Should resolve explicit tfidf request."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode("tfidf")
        assert resolved == "tfidf"
    
    def test_resolve_explicit_ollama(self):
        """Should resolve explicit ollama request."""
        config = RetrievalConfig(allow_high_quality_mode=True)
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode("ollama")
        assert resolved == "ollama"
    
    def test_resolve_ollama_not_allowed(self):
        """Should fallback to tfidf when ollama not allowed."""
        config = RetrievalConfig(allow_high_quality_mode=False)
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode("ollama")
        assert resolved == "tfidf"
    
    def test_resolve_auto_mode(self):
        """Auto mode should resolve to tfidf (current behavior)."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode("auto")
        assert resolved == "tfidf"
    
    def test_resolve_invalid_mode(self):
        """Invalid mode should fallback to tfidf."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        resolved = selector.resolve_mode("invalid_mode")
        assert resolved == "tfidf"
    
    @pytest.mark.asyncio
    async def test_select_tfidf_provider(self):
        """Should select tfidf provider correctly."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("tfidf")
        
        assert trace.provider_used == "tfidf"
        assert trace.fallback_triggered is False
    
    @pytest.mark.asyncio
    async def test_selection_trace_recorded(self):
        """Should record selection trace."""
        config = RetrievalConfig(log_provider_selection=True)
        selector = ProviderSelector(config)
        
        await selector.select_provider("tfidf")
        
        traces = selector.get_traces()
        assert len(traces) == 1
        assert traces[0]["provider_used"] == "tfidf"
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Should track provider stats."""
        config = RetrievalConfig()
        selector = ProviderSelector(config)
        
        await selector.select_provider("tfidf")
        await selector.select_provider("tfidf")
        
        stats = selector.get_stats()
        assert stats["tfidf_count"] == 2


class TestProviderSelectionTrace:
    """Test selection trace."""
    
    def test_trace_to_dict(self):
        """Should convert trace to dict."""
        trace = ProviderSelectionTrace(
            requested_mode="ollama",
            resolved_mode="tfidf",
            provider_used="tfidf",
            fallback_triggered=True,
            fallback_reason="Health check failed",
            latency_ms=50.0,
        )
        
        d = trace.to_dict()
        
        assert d["requested_mode"] == "ollama"
        assert d["resolved_mode"] == "tfidf"
        assert d["provider_used"] == "tfidf"
        assert d["fallback_triggered"] is True
        assert d["latency_ms"] == 50.0


class TestSelectRetrievalModeFunction:
    """Test convenience function."""
    
    def test_select_default_mode(self):
        """Should select default mode."""
        mode = select_retrieval_mode()
        assert mode == "tfidf"
    
    def test_select_explicit_mode(self):
        """Should select explicit mode."""
        mode = select_retrieval_mode(requested_mode="ollama")
        assert mode == "ollama"
