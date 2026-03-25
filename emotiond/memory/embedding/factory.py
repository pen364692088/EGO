"""
Embedding Provider Factory.

Creates and manages embedding provider instances.
Ensures capability ownership stays within OpenEmotion.
"""

from __future__ import annotations

from typing import Optional, Type

from emotiond.memory.embedding.contracts import EmbeddingConfig, EmbeddingProvider
from emotiond.memory.embedding.providers.tfidf_provider import TfidfProvider
from emotiond.memory.embedding.providers.ollama_provider import OllamaEmbeddingProvider


# Provider registry
_PROVIDER_REGISTRY: dict[str, Type[EmbeddingProvider]] = {
    "tfidf": TfidfProvider,
    "ollama": OllamaEmbeddingProvider,
}


def get_provider(config: Optional[EmbeddingConfig] = None) -> EmbeddingProvider:
    """Get an embedding provider instance.
    
    Args:
        config: Embedding configuration. Uses defaults if not provided.
        
    Returns:
        EmbeddingProvider instance
        
    Raises:
        ValueError: If provider name is unknown
    """
    config = config or EmbeddingConfig()
    provider_name = config.provider.lower()
    
    if provider_name not in _PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown embedding provider: {provider_name}. "
            f"Available: {list(_PROVIDER_REGISTRY.keys())}"
        )
    
    provider_class = _PROVIDER_REGISTRY[provider_name]
    return provider_class(config)


def get_available_providers() -> list[str]:
    """Get list of available provider names."""
    return list(_PROVIDER_REGISTRY.keys())


def register_provider(name: str, provider_class: Type[EmbeddingProvider]) -> None:
    """Register a new embedding provider.
    
    Args:
        name: Provider name
        provider_class: Provider class (must implement EmbeddingProvider)
    """
    _PROVIDER_REGISTRY[name.lower()] = provider_class
