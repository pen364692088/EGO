"""
Embedding Provider Telemetry.

Tracks provider usage, latency, fallback events.
Ensures capability ownership stays within OpenEmotion.

v6b: High-Quality Retrieval Mode Controlled Landing
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import statistics


@dataclass
class ProviderUsageRecord:
    """Record of a single provider usage."""
    provider: str
    latency_ms: float
    success: bool
    fallback_triggered: bool = False
    fallback_reason: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderMetrics:
    """Aggregated metrics for a provider."""
    provider: str
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    fallback_count: int = 0
    latencies: List[float] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        return statistics.mean(self.latencies)
    
    @property
    def p95_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "fallback_count": self.fallback_count,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "p95_latency_ms": round(self.p95_latency_ms, 2) if self.p95_latency_ms else None,
        }


class EmbeddingTelemetry:
    """Tracks embedding provider telemetry.
    
    Capability Owner: OpenEmotion
    
    Tracks:
    - Provider usage count
    - Fallback events
    - Latency by provider
    - Success/failure rates
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else None
        self._records: List[ProviderUsageRecord] = []
        self._metrics: Dict[str, ProviderMetrics] = defaultdict(lambda: ProviderMetrics(provider=""))
        self._session_start = time.time()
        
    def record_usage(
        self,
        provider: str,
        latency_ms: float,
        success: bool,
        fallback_triggered: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> None:
        """Record a provider usage event."""
        record = ProviderUsageRecord(
            provider=provider,
            latency_ms=latency_ms,
            success=success,
            fallback_triggered=fallback_triggered,
            fallback_reason=fallback_reason,
        )
        self._records.append(record)
        
        # Update metrics
        metrics = self._metrics[provider]
        metrics.provider = provider
        metrics.usage_count += 1
        if success:
            metrics.success_count += 1
        else:
            metrics.failure_count += 1
        metrics.latencies.append(latency_ms)
        if fallback_triggered:
            metrics.fallback_count += 1
        
        # Keep records bounded
        if len(self._records) > 1000:
            self._records = self._records[-1000:]
    
    def get_provider_metrics(self, provider: str) -> Dict[str, Any]:
        """Get metrics for a specific provider."""
        if provider in self._metrics:
            return self._metrics[provider].to_dict()
        return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all provider metrics."""
        return {
            "session_start": self._session_start,
            "session_duration_s": round(time.time() - self._session_start, 2),
            "total_records": len(self._records),
            "providers": {
                provider: metrics.to_dict()
                for provider, metrics in self._metrics.items()
            },
            "summary": self._get_summary(),
        }
    
    def _get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        tfidf_metrics = self._metrics.get("tfidf", ProviderMetrics(provider="tfidf"))
        ollama_metrics = self._metrics.get("ollama", ProviderMetrics(provider="ollama"))
        
        total_fallbacks = sum(m.fallback_count for m in self._metrics.values())
        
        return {
            "tfidf_usage_count": tfidf_metrics.usage_count,
            "ollama_usage_count": ollama_metrics.usage_count,
            "total_fallback_count": total_fallbacks,
            "tfidf_avg_latency_ms": round(tfidf_metrics.avg_latency_ms, 2) if tfidf_metrics.avg_latency_ms else None,
            "ollama_avg_latency_ms": round(ollama_metrics.avg_latency_ms, 2) if ollama_metrics.avg_latency_ms else None,
        }
    
    def export(self, path: Optional[str] = None) -> str:
        """Export telemetry to JSON file."""
        output_path = Path(path) if path else None
        if output_path is None and self.output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"telemetry_{timestamp}.json"
        elif output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"telemetry_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(self.get_all_metrics(), f, indent=2)
        
        return str(output_path)
    
    def get_recent_records(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent usage records."""
        records = self._records[-limit:]
        return [r.to_dict() for r in records]


# Global telemetry instance (lazy init)
_telemetry: Optional[EmbeddingTelemetry] = None


def get_telemetry() -> EmbeddingTelemetry:
    """Get global telemetry instance."""
    global _telemetry
    if _telemetry is None:
        _telemetry = EmbeddingTelemetry()
    return _telemetry


def reset_telemetry() -> None:
    """Reset global telemetry instance."""
    global _telemetry
    _telemetry = None
