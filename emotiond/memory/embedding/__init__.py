"""Embedding provider module for OpenEmotion."""

from emotiond.memory.embedding.contracts import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    FailureCategory,
    HealthCheckResult,
    ProviderMetadata,
)

__all__ = [
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "FailureCategory",
    "HealthCheckResult",
    "ProviderMetadata",
]
