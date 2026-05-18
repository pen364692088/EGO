"""
Plan Injection - Metrics

Minimal metrics collection for plan injection monitoring.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional
from datetime import datetime
import json
import os


logger = logging.getLogger(__name__)


@dataclass
class InjectionMetrics:
    """
    Metrics for plan injection monitoring.
    
    Counters:
    - attempt_total: Total injection attempts
    - allowed_total: Allowed injections
    - skipped_total: Skipped injections
    - fallback_total: Fallback triggered
    - error_total: Errors
    
    Histogram:
    - latency_ms: Injection latency
    """
    attempt_total: int = 0
    allowed_total: int = 0
    skipped_total: int = 0
    fallback_total: int = 0
    error_total: int = 0
    
    # By reason
    skipped_by_reason: Dict[str, int] = field(default_factory=dict)
    fallback_by_reason: Dict[str, int] = field(default_factory=dict)
    
    # Latency tracking
    latency_samples: list = field(default_factory=list)
    
    def record_attempt(self):
        """Record an injection attempt."""
        self.attempt_total += 1
    
    def record_allowed(self, latency_ms: float):
        """Record a successful injection."""
        self.allowed_total += 1
        self.latency_samples.append(latency_ms)
    
    def record_skipped(self, reason: str):
        """Record a skipped injection."""
        self.skipped_total += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1
    
    def record_fallback(self, reason: str):
        """Record a fallback."""
        self.fallback_total += 1
        self.fallback_by_reason[reason] = self.fallback_by_reason.get(reason, 0) + 1
    
    def record_error(self):
        """Record an error."""
        self.error_total += 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "attempt_total": self.attempt_total,
            "allowed_total": self.allowed_total,
            "skipped_total": self.skipped_total,
            "fallback_total": self.fallback_total,
            "error_total": self.error_total,
            "skipped_by_reason": self.skipped_by_reason,
            "fallback_by_reason": self.fallback_by_reason,
            "avg_latency_ms": sum(self.latency_samples) / len(self.latency_samples) if self.latency_samples else 0,
            "sample_count": len(self.latency_samples),
        }
    
    def save(self, path: str):
        """Save metrics to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


# Global metrics instance
_metrics: Optional[InjectionMetrics] = None


def get_injection_metrics() -> InjectionMetrics:
    """Get the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = InjectionMetrics()
    return _metrics


def record_injection_attempt():
    """Record an injection attempt."""
    get_injection_metrics().record_attempt()


def record_injection_allowed(latency_ms: float):
    """Record a successful injection."""
    get_injection_metrics().record_allowed(latency_ms)


def record_injection_skipped(reason: str):
    """Record a skipped injection."""
    get_injection_metrics().record_skipped(reason)


def record_injection_fallback(reason: str):
    """Record a fallback."""
    get_injection_metrics().record_fallback(reason)


def record_injection_error():
    """Record an error."""
    get_injection_metrics().record_error()
