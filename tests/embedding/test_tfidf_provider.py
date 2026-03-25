"""
Tests for TF-IDF Embedding Provider.

v6a gate validation.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.memory.embedding.contracts import EmbeddingConfig
from emotiond.memory.embedding.providers.tfidf_provider import TfidfProvider


class TestTfidfProviderInit:
    """Test TF-IDF provider initialization."""
    
    def test_init_with_defaults(self):
        """Provider should initialize with default config."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        assert provider.PROVIDER_NAME == "tfidf"
    
    def test_version_defined(self):
        """Provider should have a version."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        assert provider.VERSION is not None


class TestTfidfProviderFit:
    """Test TF-IDF provider fitting."""
    
    def test_fit_on_documents(self):
        """Provider should fit on document corpus."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        
        docs = ["Hello world", "Test document", "Another text"]
        provider.fit(docs)
        
        assert len(provider._vocabulary) > 0
        assert len(provider._idf) > 0
        assert provider._document_count == 3
    
    def test_vocabulary_built(self):
        """Provider should build vocabulary."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        
        docs = ["apple banana", "banana cherry", "cherry date"]
        provider.fit(docs)
        
        vocab = provider._vocabulary
        assert "apple" in vocab
        assert "banana" in vocab
        assert "cherry" in vocab
        assert "date" in vocab


class TestTfidfProviderEmbedding:
    """Test TF-IDF provider embedding operations."""
    
    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        """Provider should embed a single text."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        provider.fit(["Hello world", "Test document"])
        
        result = await provider.embed_one("Hello")
        
        assert result.success is True
        assert len(result.vectors) == 1
        assert result.provider == "tfidf"
    
    @pytest.mark.asyncio
    async def test_embed_batch_texts(self):
        """Provider should embed multiple texts."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        provider.fit(["Hello world", "Test document", "Another text"])
        
        texts = ["Hello", "World"]
        result = await provider.embed_batch(texts)
        
        assert result.success is True
        assert len(result.vectors) == 2
    
    @pytest.mark.asyncio
    async def test_latency_sub_millisecond(self):
        """TF-IDF embedding should be very fast."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        provider.fit(["Hello world"] * 100)
        
        result = await provider.embed_one("Test")
        
        assert result.success is True
        assert result.latency_ms < 10  # Should be sub-ms, but allow some margin


class TestTfidfProviderHealthcheck:
    """Test TF-IDF provider healthcheck."""
    
    @pytest.mark.asyncio
    async def test_healthcheck_always_passes(self):
        """TF-IDF healthcheck should always pass (no external dependencies)."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        
        result = await provider.healthcheck()
        
        assert result.healthy is True
        assert result.provider == "tfidf"


class TestTfidfProviderMetadata:
    """Test TF-IDF provider metadata."""
    
    def test_get_metadata(self):
        """Provider should return metadata."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        provider.fit(["Test document"])
        
        metadata = provider.get_metadata()
        
        assert metadata.provider == "tfidf"
        assert metadata.supports_batch is True
    
    def test_vector_dim_after_fit(self):
        """Vector dimension should reflect vocabulary size."""
        config = EmbeddingConfig(provider="tfidf")
        provider = TfidfProvider(config)
        
        docs = ["apple banana cherry"]
        provider.fit(docs)
        
        metadata = provider.get_metadata()
        assert metadata.vector_dim == 3  # 3 unique words
