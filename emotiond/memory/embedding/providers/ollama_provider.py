"""
Ollama Embedding Provider.

Uses Ollama's OpenAI-compatible `/v1/embeddings` endpoint.
Preferred model: mxbai-embed-large

Host URL should be configurable via EMBEDDING_OLLAMA_BASE_URL env var.
Default: http://192.168.79.1:11434/v1 (VM accessing host Ollama)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from emotiond.memory.embedding.contracts import (
    EmbeddingConfig,
    EmbeddingResult,
    FailureCategory,
    HealthCheckResult,
    ProviderMetadata,
)


class OllamaEmbeddingProvider:
    """Ollama embedding provider using OpenAI-compatible API.
    
    Endpoint: /v1/embeddings
    Model: mxbai-embed-large (configurable)
    
    This provider belongs to OpenEmotion, not EgoCore/OpenClaw.
    """
    
    PROVIDER_NAME = "ollama"
    VERSION = "1.0.0"
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig(
            provider="ollama",
            ollama_base_url=os.getenv("EMBEDDING_OLLAMA_BASE_URL", "http://192.168.79.1:11434/v1"),
            ollama_model=os.getenv("EMBEDDING_OLLAMA_MODEL", "mxbai-embed-large"),
        )
        self._base_url = self.config.ollama_base_url.rstrip("/")
        self._model = self.config.ollama_model
        self._timeout = self.config.timeout_ms / 1000.0
        self._vector_dim: Optional[int] = None
        self._latency_samples: List[float] = []
        self._healthy: bool = False
        
    async def _make_request(
        self, 
        endpoint: str, 
        payload: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[FailureCategory]]:
        """Make HTTP request to Ollama.
        
        Returns:
            (response_json, error_message, error_category)
        """
        url = f"{self._base_url}{endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    return response.json(), None, None
                elif response.status_code == 401:
                    return None, f"Authentication error: {response.text}", FailureCategory.CONFIG_ERROR
                elif response.status_code == 404:
                    return None, f"Endpoint not found: {endpoint}", FailureCategory.CONFIG_ERROR
                elif response.status_code >= 500:
                    return None, f"Provider error: {response.status_code}", FailureCategory.PROVIDER_ERROR
                else:
                    return None, f"Unexpected status: {response.status_code}", FailureCategory.PROVIDER_ERROR
                    
        except httpx.ConnectError as e:
            return None, f"Connection error: {str(e)}", FailureCategory.CONNECTION_ERROR
        except httpx.TimeoutException as e:
            return None, f"Timeout after {self._timeout}s", FailureCategory.TIMEOUT
        except Exception as e:
            return None, f"Unexpected error: {str(e)}", FailureCategory.PROVIDER_ERROR
    
    async def embed_one(self, text: str) -> EmbeddingResult:
        """Embed a single text."""
        start = time.time()
        
        payload = {
            "model": self._model,
            "input": text,
        }
        
        # Only include dimensions if specified
        if self.config.dimensions:
            payload["dimensions"] = self.config.dimensions
        
        data, error, error_cat = await self._make_request("/embeddings", payload)
        latency = (time.time() - start) * 1000
        
        if error:
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=error,
                error_category=error_cat,
            )
        
        try:
            # OpenAI-compatible response format
            embedding = data["data"][0]["embedding"]  # type: ignore
            vector = [float(x) for x in embedding]
            
            if self._vector_dim is None:
                self._vector_dim = len(vector)
            
            self._latency_samples.append(latency)
            if len(self._latency_samples) > 100:
                self._latency_samples = self._latency_samples[-100:]
            
            return EmbeddingResult(
                success=True,
                vectors=[vector],
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                vector_dim=len(vector),
            )
        except (KeyError, IndexError, TypeError) as e:
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=f"Failed to parse response: {str(e)}",
                error_category=FailureCategory.PROVIDER_ERROR,
            )
    
    async def embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """Embed multiple texts.
        
        Ollama OpenAI-compatible API supports batch input.
        """
        start = time.time()
        
        payload = {
            "model": self._model,
            "input": texts,
        }
        
        if self.config.dimensions:
            payload["dimensions"] = self.config.dimensions
        
        data, error, error_cat = await self._make_request("/embeddings", payload)
        latency = (time.time() - start) * 1000
        
        if error:
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=error,
                error_category=error_cat,
            )
        
        try:
            # OpenAI-compatible batch response
            vectors = []
            for item in data["data"]:  # type: ignore
                embedding = item["embedding"]
                vectors.append([float(x) for x in embedding])
            
            if self._vector_dim is None and vectors:
                self._vector_dim = len(vectors[0])
            
            self._latency_samples.append(latency / len(texts) if texts else 0)
            
            return EmbeddingResult(
                success=True,
                vectors=vectors,
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                vector_dim=self._vector_dim,
            )
        except (KeyError, IndexError, TypeError) as e:
            return EmbeddingResult(
                success=False,
                vectors=[],
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=f"Failed to parse batch response: {str(e)}",
                error_category=FailureCategory.PROVIDER_ERROR,
            )
    
    async def healthcheck(self) -> HealthCheckResult:
        """Check provider health by hitting /v1/models."""
        start = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}/models")
                latency = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    model_available = self._model in models or f"{self._model}:latest" in models
                    
                    self._healthy = model_available
                    
                    if not model_available:
                        return HealthCheckResult(
                            healthy=False,
                            provider=self.PROVIDER_NAME,
                            model=self._model,
                            latency_ms=latency,
                            error=f"Model {self._model} not found. Available: {models[:5]}...",
                            error_category=FailureCategory.CONFIG_ERROR,
                        )
                    
                    return HealthCheckResult(
                        healthy=True,
                        provider=self.PROVIDER_NAME,
                        model=self._model,
                        latency_ms=latency,
                    )
                else:
                    self._healthy = False
                    return HealthCheckResult(
                        healthy=False,
                        provider=self.PROVIDER_NAME,
                        model=self._model,
                        latency_ms=latency,
                        error=f"Health check failed: {response.status_code}",
                        error_category=FailureCategory.CONNECTION_ERROR,
                    )
                    
        except httpx.ConnectError as e:
            self._healthy = False
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                healthy=False,
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=f"Cannot connect to {self._base_url}: {str(e)}",
                error_category=FailureCategory.CONNECTION_ERROR,
            )
        except Exception as e:
            self._healthy = False
            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                healthy=False,
                provider=self.PROVIDER_NAME,
                model=self._model,
                latency_ms=latency,
                error=f"Health check error: {str(e)}",
                error_category=FailureCategory.PROVIDER_ERROR,
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
            model=self._model,
            vector_dim=self._vector_dim,
            max_batch_size=self.config.max_batch_size,
            supports_batch=True,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
        )
