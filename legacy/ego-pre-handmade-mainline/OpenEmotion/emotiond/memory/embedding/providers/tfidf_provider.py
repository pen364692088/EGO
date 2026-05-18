"""
TF-IDF Embedding Provider.

Baseline provider using TF-IDF vectorization.
This is the default fallback provider.

Note: TF-IDF produces sparse vectors. For similarity computation,
we use cosine similarity on the sparse representation.
"""

from __future__ import annotations

import math
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from emotiond.memory.embedding.contracts import (
    EmbeddingConfig,
    EmbeddingResult,
    FailureCategory,
    HealthCheckResult,
    ProviderMetadata,
)


class TfidfProvider:
    """TF-IDF embedding provider.
    
    This is a simple, dependency-free TF-IDF implementation.
    It produces sparse vectors (dict of term -> weight).
    
    For dense vector output, we normalize to a fixed vocabulary.
    """
    
    PROVIDER_NAME = "tfidf"
    VERSION = "1.0.0"
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig(provider="tfidf")
        self._vocabulary: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._document_count: int = 0
        self._latency_samples: List[float] = []
        
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        # Lowercase and split on whitespace/punctuation
        text = text.lower()
        # Simple character filtering
        tokens = []
        current = []
        for char in text:
            if char.isalnum():
                current.append(char)
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        return tokens
    
    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """Compute term frequency."""
        counts = Counter(tokens)
        total = len(tokens) if tokens else 1
        return {term: count / total for term, count in counts.items()}
    
    def _compute_tfidf(self, text: str) -> Dict[str, float]:
        """Compute TF-IDF for a single text."""
        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)
        
        tfidf = {}
        for term, tf_val in tf.items():
            idf = self._idf.get(term, math.log(1 + self._document_count))
            tfidf[term] = tf_val * idf
            
        return tfidf
    
    def fit(self, documents: List[str]) -> None:
        """Fit IDF on a corpus of documents."""
        self._document_count = len(documents)
        doc_freq: Counter = Counter()
        
        for doc in documents:
            tokens = set(self._tokenize(doc))
            for token in tokens:
                doc_freq[token] += 1
        
        # Compute IDF
        self._idf = {}
        for term, df in doc_freq.items():
            self._idf[term] = math.log((self._document_count + 1) / (df + 1)) + 1
        
        # Build vocabulary
        self._vocabulary = {term: idx for idx, term in enumerate(sorted(self._idf.keys()))}
    
    def _sparse_to_dense(self, sparse: Dict[str, float]) -> List[float]:
        """Convert sparse TF-IDF to dense vector.
        
        Uses vocabulary indices. Out-of-vocabulary terms are ignored.
        """
        if not self._vocabulary:
            return [0.0]  # No vocabulary fitted
            
        dim = len(self._vocabulary)
        dense = [0.0] * dim
        for term, weight in sparse.items():
            if term in self._vocabulary:
                dense[self._vocabulary[term]] = weight
        return dense
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two dense vectors."""
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
    
    async def embed_one(self, text: str) -> EmbeddingResult:
        """Embed a single text."""
        start = time.time()
        
        try:
            sparse = self._compute_tfidf(text)
            dense = self._sparse_to_dense(sparse)
            latency = (time.time() - start) * 1000
            
            self._latency_samples.append(latency)
            if len(self._latency_samples) > 100:
                self._latency_samples = self._latency_samples[-100:]
            
            return EmbeddingResult(
                success=True,
                vectors=[dense],
                provider=self.PROVIDER_NAME,
                model=f"tfidf-v{self.VERSION}",
                latency_ms=latency,
                vector_dim=len(dense) if dense else 0,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=f"tfidf-v{self.VERSION}",
                latency_ms=latency,
                error=str(e),
                error_category=FailureCategory.PROVIDER_ERROR,
            )
    
    async def embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """Embed multiple texts."""
        start = time.time()
        
        try:
            vectors = []
            for text in texts:
                sparse = self._compute_tfidf(text)
                dense = self._sparse_to_dense(sparse)
                vectors.append(dense)
            
            latency = (time.time() - start) * 1000
            self._latency_samples.append(latency / len(texts) if texts else 0)
            
            return EmbeddingResult(
                success=True,
                vectors=vectors,
                provider=self.PROVIDER_NAME,
                model=f"tfidf-v{self.VERSION}",
                latency_ms=latency,
                vector_dim=len(vectors[0]) if vectors else 0,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=f"tfidf-v{self.VERSION}",
                latency_ms=latency,
                error=str(e),
                error_category=FailureCategory.PROVIDER_ERROR,
            )
    
    async def healthcheck(self) -> HealthCheckResult:
        """Check provider health."""
        start = time.time()
        
        # TF-IDF is always healthy (no external dependencies)
        latency = (time.time() - start) * 1000
        
        return HealthCheckResult(
            healthy=True,
            provider=self.PROVIDER_NAME,
            model=f"tfidf-v{self.VERSION}",
            latency_ms=latency,
        )
    
    def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata."""
        avg_latency = None
        p95_latency = None
        
        if self._latency_samples:
            samples = sorted(self._latency_samples)
            avg_latency = sum(samples) / len(samples)
            p95_idx = int(len(samples) * 0.95)
            p95_latency = samples[p95_idx] if p95_idx < len(samples) else samples[-1]
        
        return ProviderMetadata(
            provider=self.PROVIDER_NAME,
            model=f"tfidf-v{self.VERSION}",
            vector_dim=len(self._vocabulary) if self._vocabulary else 0,
            max_batch_size=self.config.max_batch_size,
            supports_batch=True,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
        )
    
    def similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts."""
        import asyncio
        result1 = asyncio.run(self.embed_one(text1))
        result2 = asyncio.run(self.embed_one(text2))
        
        if not result1.success or not result2.success:
            return 0.0
        
        return self._cosine_similarity(result1.vectors[0], result2.vectors[0])
