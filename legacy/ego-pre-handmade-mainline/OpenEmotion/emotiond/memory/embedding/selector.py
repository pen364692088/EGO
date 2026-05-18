"""
Embedding Provider Selector.

Handles mode selection between tfidf / ollama / auto.
Ensures capability ownership stays within OpenEmotion.

v6b: High-Quality Retrieval Mode Controlled Landing
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from emotiond.memory.embedding.contracts import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    FailureCategory,
    HealthCheckResult,
)
from emotiond.memory.embedding.providers.tfidf_provider import TfidfProvider
from emotiond.memory.embedding.providers.ollama_provider import OllamaEmbeddingProvider


class RetrievalMode(str, Enum):
    """Retrieval mode options."""
    TFIDF = "tfidf"
    OLLAMA = "ollama"
    AUTO = "auto"


@dataclass
class ProviderSelectionTrace:
    """Trace record for provider selection."""
    requested_mode: str
    resolved_mode: str
    provider_used: str
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    fallback_category: Optional[FailureCategory] = None
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_mode": self.requested_mode,
            "resolved_mode": self.resolved_mode,
            "provider_used": self.provider_used,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "fallback_category": self.fallback_category.value if self.fallback_category else None,
            "latency_ms": round(self.latency_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class RetrievalConfig:
    """Configuration for retrieval mode selection."""
    mode: str = "tfidf"  # Default: tfidf
    allow_high_quality_mode: bool = True
    auto_upgrade_enabled: bool = False  # Default: disabled
    fallback_on_provider_failure: bool = True
    log_provider_selection: bool = True
    
    # Ollama-specific config
    ollama_enabled: bool = True
    ollama_model: str = "mxbai-embed-large"
    ollama_base_url: str = "http://192.168.79.1:11434/v1"
    ollama_timeout_ms: int = 10000
    ollama_max_batch_size: int = 32
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_high_quality_mode": self.allow_high_quality_mode,
            "auto_upgrade_enabled": self.auto_upgrade_enabled,
            "fallback_on_provider_failure": self.fallback_on_provider_failure,
            "log_provider_selection": self.log_provider_selection,
            "ollama_enabled": self.ollama_enabled,
            "ollama_model": self.ollama_model,
            "ollama_base_url": self.ollama_base_url,
            "ollama_timeout_ms": self.ollama_timeout_ms,
            "ollama_max_batch_size": self.ollama_max_batch_size,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RetrievalConfig":
        return cls(
            mode=data.get("mode", "tfidf"),
            allow_high_quality_mode=data.get("allow_high_quality_mode", True),
            auto_upgrade_enabled=data.get("auto_upgrade_enabled", False),
            fallback_on_provider_failure=data.get("fallback_on_provider_failure", True),
            log_provider_selection=data.get("log_provider_selection", True),
            ollama_enabled=data.get("ollama_enabled", True),
            ollama_model=data.get("ollama_model", "mxbai-embed-large"),
            ollama_base_url=data.get("ollama_base_url", "http://192.168.79.1:11434/v1"),
            ollama_timeout_ms=data.get("ollama_timeout_ms", 10000),
            ollama_max_batch_size=data.get("ollama_max_batch_size", 32),
        )


class ProviderSelector:
    """Selects and manages embedding providers based on mode.
    
    Capability Owner: OpenEmotion
    
    Supported modes:
    - tfidf: Default, fast, zero-cost
    - ollama: High-quality, ~70ms latency
    - auto: Currently alias for tfidf (reserved for future)
    """
    
    def __init__(self, config: Optional[RetrievalConfig] = None):
        self.config = config or RetrievalConfig()
        self._tfidf_provider: Optional[TfidfProvider] = None
        self._ollama_provider: Optional[OllamaEmbeddingProvider] = None
        self._selection_traces: list[ProviderSelectionTrace] = []
        self._fallback_count: int = 0
        
    def _get_tfidf_provider(self) -> TfidfProvider:
        """Get or create TF-IDF provider."""
        if self._tfidf_provider is None:
            embedding_config = EmbeddingConfig(provider="tfidf")
            self._tfidf_provider = TfidfProvider(embedding_config)
        return self._tfidf_provider
    
    def _get_ollama_provider(self) -> OllamaEmbeddingProvider:
        """Get or create Ollama provider."""
        if self._ollama_provider is None:
            embedding_config = EmbeddingConfig(
                provider="ollama",
                ollama_base_url=self.config.ollama_base_url,
                ollama_model=self.config.ollama_model,
                timeout_ms=self.config.ollama_timeout_ms,
                max_batch_size=self.config.ollama_max_batch_size,
            )
            self._ollama_provider = OllamaEmbeddingProvider(embedding_config)
        return self._ollama_provider
    
    def resolve_mode(self, requested_mode: Optional[str] = None) -> str:
        """Resolve the actual mode to use.
        
        Args:
            requested_mode: Explicitly requested mode, or None for default
            
        Returns:
            Resolved mode string
        """
        if requested_mode is None:
            return self.config.mode  # Default from config
        
        mode = requested_mode.lower()
        
        # Handle auto mode (currently alias for tfidf)
        if mode == RetrievalMode.AUTO.value:
            if self.config.auto_upgrade_enabled:
                # Future: logic to decide when to upgrade
                return RetrievalMode.TFIDF.value
            return RetrievalMode.TFIDF.value
        
        # Validate mode
        if mode not in [m.value for m in RetrievalMode]:
            return RetrievalMode.TFIDF.value  # Fallback to default
        
        # Check if ollama is allowed
        if mode == RetrievalMode.OLLAMA.value and not self.config.allow_high_quality_mode:
            return RetrievalMode.TFIDF.value
        
        return mode
    
    async def select_provider(
        self, 
        requested_mode: Optional[str] = None
    ) -> tuple[EmbeddingProvider, ProviderSelectionTrace]:
        """Select appropriate provider based on mode.
        
        Args:
            requested_mode: Explicitly requested mode, or None for default
            
        Returns:
            Tuple of (provider, selection_trace)
        """
        start = time.time()
        trace = ProviderSelectionTrace(
            requested_mode=requested_mode or self.config.mode,
            resolved_mode="",
            provider_used="",
        )
        
        resolved_mode = self.resolve_mode(requested_mode)
        trace.resolved_mode = resolved_mode
        
        # Direct TF-IDF selection
        if resolved_mode == RetrievalMode.TFIDF.value:
            provider = self._get_tfidf_provider()
            trace.provider_used = "tfidf"
            trace.latency_ms = (time.time() - start) * 1000
            self._record_trace(trace)
            return provider, trace
        
        # Ollama selection with optional fallback
        if resolved_mode == RetrievalMode.OLLAMA.value:
            ollama_provider = self._get_ollama_provider()
            
            # Check health before using
            try:
                health = await ollama_provider.healthcheck()
                if health.healthy:
                    trace.provider_used = "ollama"
                    trace.latency_ms = (time.time() - start) * 1000
                    self._record_trace(trace)
                    return ollama_provider, trace
                else:
                    # Health check failed - fallback to tfidf
                    if self.config.fallback_on_provider_failure:
                        trace.fallback_triggered = True
                        trace.fallback_reason = health.error
                        trace.fallback_category = health.error_category
                        trace.provider_used = "tfidf"
                        trace.latency_ms = (time.time() - start) * 1000
                        self._fallback_count += 1
                        self._record_trace(trace)
                        return self._get_tfidf_provider(), trace
                    else:
                        # No fallback - return ollama anyway (will fail on use)
                        trace.provider_used = "ollama"
                        trace.latency_ms = (time.time() - start) * 1000
                        self._record_trace(trace)
                        return ollama_provider, trace
            except Exception as e:
                # Exception during health check - fallback
                if self.config.fallback_on_provider_failure:
                    trace.fallback_triggered = True
                    trace.fallback_reason = str(e)
                    trace.fallback_category = FailureCategory.PROVIDER_ERROR
                    trace.provider_used = "tfidf"
                    trace.latency_ms = (time.time() - start) * 1000
                    self._fallback_count += 1
                    self._record_trace(trace)
                    return self._get_tfidf_provider(), trace
                raise
        
        # Should not reach here
        trace.provider_used = "tfidf"
        trace.latency_ms = (time.time() - start) * 1000
        self._record_trace(trace)
        return self._get_tfidf_provider(), trace
    
    def _record_trace(self, trace: ProviderSelectionTrace) -> None:
        """Record selection trace."""
        if self.config.log_provider_selection:
            self._selection_traces.append(trace)
            # Keep only last 100 traces
            if len(self._selection_traces) > 100:
                self._selection_traces = self._selection_traces[-100:]
    
    def get_traces(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent selection traces."""
        traces = self._selection_traces[-limit:]
        return [t.to_dict() for t in traces]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider selection statistics."""
        if not self._selection_traces:
            return {
                "total_selections": 0,
                "tfidf_count": 0,
                "ollama_count": 0,
                "fallback_count": self._fallback_count,
            }
        
        tfidf_count = sum(1 for t in self._selection_traces if t.provider_used == "tfidf")
        ollama_count = sum(1 for t in self._selection_traces if t.provider_used == "ollama")
        
        return {
            "total_selections": len(self._selection_traces),
            "tfidf_count": tfidf_count,
            "ollama_count": ollama_count,
            "fallback_count": self._fallback_count,
            "fallback_rate": self._fallback_count / len(self._selection_traces) if self._selection_traces else 0,
        }


def select_retrieval_mode(
    config: Optional[RetrievalConfig] = None,
    requested_mode: Optional[str] = None
) -> str:
    """Convenience function to resolve retrieval mode.
    
    Args:
        config: Retrieval configuration
        requested_mode: Explicitly requested mode
        
    Returns:
        Resolved mode string
    """
    selector = ProviderSelector(config)
    return selector.resolve_mode(requested_mode)
