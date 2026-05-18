"""
Tests for Ollama Embedding Provider.

v6a gate validation.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.contracts import EmbeddingConfig, EmbeddingResult
from emotiond.memory.embedding.providers.ollama_provider import OllamaEmbeddingProvider


class TestOllamaProviderInit:
    """Test Ollama provider initialization."""
    
    def test_init_with_defaults(self):
        """Provider should initialize with default config."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        assert provider.PROVIDER_NAME == "ollama"
    
    def test_init_with_custom_url(self):
        """Provider should accept custom base URL."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://localhost:11434/v1"
        )
        provider = OllamaEmbeddingProvider(config)
        assert "localhost:11434" in provider._base_url


class TestOllamaProviderHealthcheck:
    """Test Ollama provider healthcheck."""
    
    @pytest.mark.asyncio
    async def test_healthcheck_reachable(self):
        """Healthcheck should pass if Ollama is reachable."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://192.168.79.1:11434/v1",
            ollama_model="mxbai-embed-large",
            timeout_ms=15000
        )
        provider = OllamaEmbeddingProvider(config)
        result = await provider.healthcheck()
        
        # If Ollama is not running, skip instead of fail
        if not result.healthy:
            pytest.skip(f"Ollama not reachable: {result.error}")
        
        assert result.healthy is True
        assert result.provider == "ollama"
    
    @pytest.mark.asyncio
    async def test_healthcheck_returns_latency(self):
        """Healthcheck should return latency measurement."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://192.168.79.1:11434/v1",
            timeout_ms=15000
        )
        provider = OllamaEmbeddingProvider(config)
        result = await provider.healthcheck()
        
        assert result.latency_ms >= 0


class TestOllamaProviderEmbedding:
    """Test Ollama provider embedding operations."""
    
    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        """Provider should embed a single text."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://192.168.79.1:11434/v1",
            ollama_model="mxbai-embed-large",
            timeout_ms=15000
        )
        provider = OllamaEmbeddingProvider(config)
        
        # Skip if not healthy
        health = await provider.healthcheck()
        if not health.healthy:
            pytest.skip(f"Ollama not reachable: {health.error}")
        
        result = await provider.embed_one("Hello world")
        
        assert result.success is True
        assert len(result.vectors) == 1
        assert result.vector_dim == 1024
        assert result.provider == "ollama"
    
    @pytest.mark.asyncio
    async def test_embed_batch_texts(self):
        """Provider should embed multiple texts."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://192.168.79.1:11434/v1",
            ollama_model="mxbai-embed-large",
            timeout_ms=15000
        )
        provider = OllamaEmbeddingProvider(config)
        
        # Skip if not healthy
        health = await provider.healthcheck()
        if not health.healthy:
            pytest.skip(f"Ollama not reachable: {health.error}")
        
        texts = ["Hello", "World", "Test"]
        result = await provider.embed_batch(texts)
        
        assert result.success is True
        assert len(result.vectors) == 3
        assert result.vector_dim == 1024
    
    @pytest.mark.asyncio
    async def test_vector_dimension_is_1024(self):
        """mxbai-embed-large should produce 1024-dimensional vectors."""
        config = EmbeddingConfig(
            provider="ollama",
            ollama_base_url="http://192.168.79.1:11434/v1",
            ollama_model="mxbai-embed-large",
            timeout_ms=15000
        )
        provider = OllamaEmbeddingProvider(config)
        
        health = await provider.healthcheck()
        if not health.healthy:
            pytest.skip(f"Ollama not reachable: {health.error}")
        
        result = await provider.embed_one("Test dimension")
        
        assert result.success is True
        assert result.vector_dim == 1024
        assert len(result.vectors[0]) == 1024


class TestOllamaProviderMetadata:
    """Test Ollama provider metadata."""
    
    def test_get_metadata(self):
        """Provider should return metadata."""
        config = EmbeddingConfig(provider="ollama")
        provider = OllamaEmbeddingProvider(config)
        metadata = provider.get_metadata()
        
        assert metadata.provider == "ollama"
        assert metadata.supports_batch is True
        assert metadata.max_batch_size > 0
