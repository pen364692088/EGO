"""
Tests for Provider Fallback at Runtime (v6b).

Validates fallback behavior when Ollama fails.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
)
from emotiond.memory.embedding.contracts import FailureCategory


class TestProviderFallbackRuntime:
    """Test provider fallback at runtime."""
    
    @pytest.mark.asyncio
    async def test_fallback_on_invalid_url(self):
        """Should fallback when Ollama URL is invalid."""
        config = RetrievalConfig(
            mode="tfidf",
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        assert trace.fallback_triggered is True
        assert trace.provider_used == "tfidf"
        assert trace.resolved_mode == "ollama"  # Requested was ollama
    
    @pytest.mark.asyncio
    async def test_fallback_records_reason(self):
        """Should record fallback reason."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        assert trace.fallback_reason is not None
        assert trace.fallback_category in [
            FailureCategory.CONNECTION_ERROR,
            FailureCategory.PROVIDER_ERROR,
        ]
    
    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self):
        """Should not fallback when disabled."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=False,  # Disabled
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("ollama")
        
        # Should still try ollama (will fail later on use)
        assert trace.fallback_triggered is False
        assert trace.provider_used == "ollama"
    
    @pytest.mark.asyncio
    async def test_fallback_increments_count(self):
        """Fallback should increment fallback count."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        await selector.select_provider("ollama")
        await selector.select_provider("ollama")
        
        stats = selector.get_stats()
        assert stats["fallback_count"] >= 2
    
    @pytest.mark.asyncio
    async def test_tfidf_always_works(self):
        """TF-IDF should always work regardless of Ollama state."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        provider, trace = await selector.select_provider("tfidf")
        
        assert trace.fallback_triggered is False
        assert trace.provider_used == "tfidf"
    
    @pytest.mark.asyncio
    async def test_multiple_fallbacks_tracked(self):
        """Multiple fallbacks should be tracked in traces."""
        config = RetrievalConfig(
            allow_high_quality_mode=True,
            fallback_on_provider_failure=True,
            ollama_base_url="http://invalid-host-99999:11434/v1",
        )
        selector = ProviderSelector(config)
        
        await selector.select_provider("ollama")
        await selector.select_provider("tfidf")
        await selector.select_provider("ollama")
        
        traces = selector.get_traces(limit=10)
        
        # Count fallbacks in traces
        fallback_count = sum(1 for t in traces if t["fallback_triggered"])
        assert fallback_count == 2
