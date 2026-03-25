"""
Embedding provider contracts and schemas.

Capability Ownership: OpenEmotion
- Provider selection authority: OpenEmotion
- Semantic interpretation authority: OpenEmotion
- Retrieval hit semantics: OpenEmotion

This module is owned by OpenEmotion and must NOT be moved to EgoCore/OpenClaw.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


class FailureCategory(str, Enum):
    """Failure taxonomy for embedding operations."""
    CONFIG_ERROR = "config_error"
    CONNECTION_ERROR = "connection_error"
    PROVIDER_ERROR = "provider_error"
    DIMENSION_MISMATCH = "dimension_mismatch"
    TIMEOUT = "timeout"
    DEGRADED_TO_FALLBACK = "degraded_to_fallback"


@dataclass
class HealthCheckResult:
    """Result of a provider health check."""
    healthy: bool
    provider: str
    model: str
    latency_ms: float
    error: Optional[str] = None
    error_category: Optional[FailureCategory] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "error_category": self.error_category.value if self.error_category else None,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderMetadata:
    """Metadata about an embedding provider."""
    provider: str
    model: str
    vector_dim: Optional[int]
    max_batch_size: int
    supports_batch: bool
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "vector_dim": self.vector_dim,
            "max_batch_size": self.max_batch_size,
            "supports_batch": self.supports_batch,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
        }


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""
    success: bool
    vectors: List[List[float]]
    provider: str
    model: str
    latency_ms: float
    vector_dim: Optional[int] = None
    error: Optional[str] = None
    error_category: Optional[FailureCategory] = None
    fallback_used: bool = False
    fallback_provider: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "vectors": self.vectors,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "vector_dim": self.vector_dim,
            "error": self.error,
            "error_category": self.error_category.value if self.error_category else None,
            "fallback_used": self.fallback_used,
            "fallback_provider": self.fallback_provider,
        }


@dataclass
class EmbeddingConfig:
    """Configuration for embedding providers."""
    enabled: bool = True
    provider: str = "tfidf"  # Default: TF-IDF
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    dimensions: Optional[int] = None
    timeout_ms: int = 10000
    max_batch_size: int = 32
    max_retries: int = 2
    fallback_provider: str = "tfidf"
    
    # Ollama-specific defaults
    ollama_base_url: str = "http://192.168.79.1:11434/v1"
    ollama_model: str = "mxbai-embed-large"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "dimensions": self.dimensions,
            "timeout_ms": self.timeout_ms,
            "max_batch_size": self.max_batch_size,
            "max_retries": self.max_retries,
            "fallback_provider": self.fallback_provider,
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.ollama_model,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmbeddingConfig":
        return cls(
            enabled=data.get("enabled", True),
            provider=data.get("provider", "tfidf"),
            model=data.get("model", ""),
            base_url=data.get("base_url", ""),
            api_key=data.get("api_key", ""),
            dimensions=data.get("dimensions"),
            timeout_ms=data.get("timeout_ms", 10000),
            max_batch_size=data.get("max_batch_size", 32),
            max_retries=data.get("max_retries", 2),
            fallback_provider=data.get("fallback_provider", "tfidf"),
            ollama_base_url=data.get("ollama_base_url", "http://192.168.79.1:11434/v1"),
            ollama_model=data.get("ollama_model", "mxbai-embed-large"),
        )


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.
    
    All embedding providers must implement this interface.
    """
    
    async def embed_one(self, text: str) -> EmbeddingResult:
        """Embed a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResult with vector and metadata
        """
        ...
    
    async def embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """Embed multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            EmbeddingResult with vectors and metadata
        """
        ...
    
    async def healthcheck(self) -> HealthCheckResult:
        """Check provider health.
        
        Returns:
            HealthCheckResult with health status
        """
        ...
    
    def get_metadata(self) -> ProviderMetadata:
        """Get provider metadata.
        
        Returns:
            ProviderMetadata with provider info
        """
        ...
