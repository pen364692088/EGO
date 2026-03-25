# Embedding Provider Contracts

## Overview

This module defines the embedding provider abstraction for OpenEmotion.
All embedding providers must implement the `EmbeddingProvider` interface.

## Capability Ownership

Embedding capability belongs to **OpenEmotion**, not EgoCore/OpenClaw.
- Provider selection authority: OpenEmotion
- Semantic interpretation authority: OpenEmotion
- Retrieval hit semantics: OpenEmotion

## Interface

```python
class EmbeddingProvider(Protocol):
    async def embed_one(self, text: str) -> List[float]
    async def embed_batch(self, texts: List[str]) -> List[List[float]]
    async def healthcheck(self) -> HealthCheckResult
    def get_metadata(self) -> ProviderMetadata
```

## Failure Taxonomy

| Category | Description | Example |
|----------|-------------|---------|
| `config_error` | Invalid configuration | Missing baseUrl, invalid model |
| `connection_error` | Cannot reach provider | Network timeout, host unreachable |
| `provider_error` | Provider returned error | 500 Internal Error, rate limit |
| `dimension_mismatch` | Vector dimension unexpected | Expected 1024, got 512 |
| `timeout` | Request exceeded timeout | > 10s for single embedding |
| `degraded_to_fallback` | Fell back to backup provider | Ollama down, using TF-IDF |

## Version History

- v1.0.0 (v6a): Initial abstraction with TF-IDF and Ollama providers
