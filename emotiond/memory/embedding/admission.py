"""
Admission Governance for High-Quality Retrieval Mode.

Defines admission states, thresholds, and decision logic.
Capability Owner: OpenEmotion

v6c: High-Quality Retrieval Mode Admission Governance
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class AdmissionState(str, Enum):
    """Admission states for high-quality retrieval mode."""
    MANUAL_ONLY = "manual_only"
    LIMITED_ROLLOUT_CANDIDATE = "limited_rollout_candidate"
    AUTO_MODE_CANDIDATE = "auto_mode_candidate"
    ROLLBACK_REQUIRED = "rollback_required"


class AdmissionGateStatus(str, Enum):
    """Status of individual admission gates."""
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class AdmissionThresholds:
    """Thresholds for admission decisions."""
    # Sample size
    min_sample_size: int = 20
    
    # Wrong user recall
    max_wrong_user_recall_count: int = 0
    
    # Fallback rate
    max_fallback_rate: float = 0.10  # 10%
    
    # Provider health
    min_provider_health_rate: float = 0.95  # 95%
    
    # Latency
    max_p95_latency_ms: float = 300.0
    
    # Quality gain
    min_quality_gain_threshold: float = 0.10  # 10% improvement
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_sample_size": self.min_sample_size,
            "max_wrong_user_recall_count": self.max_wrong_user_recall_count,
            "max_fallback_rate": self.max_fallback_rate,
            "min_provider_health_rate": self.min_provider_health_rate,
            "max_p95_latency_ms": self.max_p95_latency_ms,
            "min_quality_gain_threshold": self.min_quality_gain_threshold,
        }


@dataclass
class AdmissionMetrics:
    """Metrics for admission decision."""
    sample_size: int = 0
    request_count: int = 0
    success_count: int = 0
    fallback_count: int = 0
    timeout_count: int = 0
    wrong_user_recall_count: int = 0
    wrong_user_guard_trigger_count: int = 0
    
    # Latency
    latencies: List[float] = field(default_factory=list)
    
    # Quality metrics
    tfidf_hit_at_1: float = 0.0
    ollama_hit_at_1: float = 0.0
    quality_gain: float = 0.0
    
    # Provider health
    health_check_success_count: int = 0
    health_check_total_count: int = 0
    
    @property
    def fallback_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.fallback_count / self.request_count
    
    @property
    def provider_health_rate(self) -> float:
        if self.health_check_total_count == 0:
            return 0.0
        return self.health_check_success_count / self.health_check_total_count
    
    @property
    def success_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    @property
    def avg_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def p95_latency_ms(self) -> Optional[float]:
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_size": self.sample_size,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "fallback_count": self.fallback_count,
            "fallback_rate": round(self.fallback_rate, 4),
            "timeout_count": self.timeout_count,
            "wrong_user_recall_count": self.wrong_user_recall_count,
            "wrong_user_guard_trigger_count": self.wrong_user_guard_trigger_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2) if self.avg_latency_ms else None,
            "p95_latency_ms": round(self.p95_latency_ms, 2) if self.p95_latency_ms else None,
            "provider_health_rate": round(self.provider_health_rate, 4),
            "quality_gain": round(self.quality_gain, 4),
            "tfidf_hit_at_1": round(self.tfidf_hit_at_1, 4),
            "ollama_hit_at_1": round(self.ollama_hit_at_1, 4),
        }


@dataclass
class AdmissionGateResult:
    """Result of a single admission gate check."""
    gate_name: str
    status: AdmissionGateStatus
    threshold: Any
    actual: Any
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "threshold": self.threshold,
            "actual": self.actual,
            "message": self.message,
        }


@dataclass
class AdmissionDecision:
    """Full admission decision."""
    state: AdmissionState
    gates: List[AdmissionGateResult] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metrics: Optional[AdmissionMetrics] = None
    
    @property
    def all_gates_passed(self) -> bool:
        return all(
            g.status == AdmissionGateStatus.PASS 
            for g in self.gates
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "all_gates_passed": self.all_gates_passed,
            "gates": [g.to_dict() for g in self.gates],
            "blockers": self.blockers,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


class AdmissionGovernor:
    """Governor for high-quality mode admission decisions.
    
    Capability Owner: OpenEmotion
    
    Determines when Ollama mode can expand beyond manual-only usage.
    """
    
    def __init__(
        self, 
        thresholds: Optional[AdmissionThresholds] = None,
        metrics: Optional[AdmissionMetrics] = None,
    ):
        self.thresholds = thresholds or AdmissionThresholds()
        self.metrics = metrics or AdmissionMetrics()
        
    def evaluate_gate(
        self,
        gate_name: str,
        threshold: Any,
        actual: Any,
        comparison: str = "lte",  # less than or equal
        insufficient_data: bool = False,
    ) -> AdmissionGateResult:
        """Evaluate a single admission gate."""
        
        if insufficient_data:
            return AdmissionGateResult(
                gate_name=gate_name,
                status=AdmissionGateStatus.INSUFFICIENT_DATA,
                threshold=threshold,
                actual=actual,
                message=f"Insufficient data for {gate_name}",
            )
        
        if comparison == "lte":
            passed = actual <= threshold
        elif comparison == "gte":
            passed = actual >= threshold
        elif comparison == "eq":
            passed = actual == threshold
        else:
            passed = actual <= threshold
        
        status = AdmissionGateStatus.PASS if passed else AdmissionGateStatus.FAIL
        message = f"{gate_name}: {actual} {'<=' if comparison == 'lte' else '>=' if comparison == 'gte' else '=='} {threshold} → {'PASS' if passed else 'FAIL'}"
        
        return AdmissionGateResult(
            gate_name=gate_name,
            status=status,
            threshold=threshold,
            actual=actual,
            message=message,
        )
    
    def decide(self) -> AdmissionDecision:
        """Make admission decision based on current metrics."""
        gates: List[AdmissionGateResult] = []
        blockers: List[str] = []
        recommendations: List[str] = []
        
        # Gate 1: Sample size
        sample_gate = self.evaluate_gate(
            gate_name="sample_size",
            threshold=self.thresholds.min_sample_size,
            actual=self.metrics.sample_size,
            comparison="gte",
            insufficient_data=self.metrics.sample_size == 0,
        )
        gates.append(sample_gate)
        
        if sample_gate.status == AdmissionGateStatus.INSUFFICIENT_DATA:
            blockers.append("No samples collected yet")
            recommendations.append("Collect at least 20 real usage samples")
        elif sample_gate.status == AdmissionGateStatus.FAIL:
            blockers.append(f"Insufficient sample size: {self.metrics.sample_size} < {self.thresholds.min_sample_size}")
            recommendations.append(f"Collect at least {self.thresholds.min_sample_size} samples before admission review")
        
        # Gate 2: Wrong user recall
        wrong_user_gate = self.evaluate_gate(
            gate_name="wrong_user_recall",
            threshold=self.thresholds.max_wrong_user_recall_count,
            actual=self.metrics.wrong_user_recall_count,
            comparison="lte",
        )
        gates.append(wrong_user_gate)
        
        if wrong_user_gate.status == AdmissionGateStatus.FAIL:
            blockers.append(f"Wrong user recall risk: {self.metrics.wrong_user_recall_count} > {self.thresholds.max_wrong_user_recall_count}")
            recommendations.append("Investigate wrong_user_recall cases before expanding usage")
        
        # Gate 3: Fallback rate
        fallback_gate = self.evaluate_gate(
            gate_name="fallback_rate",
            threshold=self.thresholds.max_fallback_rate,
            actual=self.metrics.fallback_rate,
            comparison="lte",
        )
        gates.append(fallback_gate)
        
        if fallback_gate.status == AdmissionGateStatus.FAIL:
            blockers.append(f"Fallback rate too high: {self.metrics.fallback_rate:.1%} > {self.thresholds.max_fallback_rate:.1%}")
            recommendations.append("Improve provider stability before expanding usage")
        
        # Gate 4: Provider health
        health_gate = self.evaluate_gate(
            gate_name="provider_health_rate",
            threshold=self.thresholds.min_provider_health_rate,
            actual=self.metrics.provider_health_rate,
            comparison="gte",
            insufficient_data=self.metrics.health_check_total_count == 0,
        )
        gates.append(health_gate)
        
        if health_gate.status == AdmissionGateStatus.FAIL:
            blockers.append(f"Provider health rate too low: {self.metrics.provider_health_rate:.1%} < {self.thresholds.min_provider_health_rate:.1%}")
            recommendations.append("Improve provider reliability before expanding usage")
        
        # Gate 5: P95 latency
        p95_latency = self.metrics.p95_latency_ms or 0
        latency_gate = self.evaluate_gate(
            gate_name="p95_latency_ms",
            threshold=self.thresholds.max_p95_latency_ms,
            actual=p95_latency,
            comparison="lte",
            insufficient_data=len(self.metrics.latencies) < 5,
        )
        gates.append(latency_gate)
        
        if latency_gate.status == AdmissionGateStatus.FAIL:
            blockers.append(f"P95 latency too high: {p95_latency:.1f}ms > {self.thresholds.max_p95_latency_ms:.1f}ms")
            recommendations.append("Optimize latency or accept current mode")
        
        # Gate 6: Quality gain
        quality_gate = self.evaluate_gate(
            gate_name="quality_gain",
            threshold=self.thresholds.min_quality_gain_threshold,
            actual=self.metrics.quality_gain,
            comparison="gte",
            insufficient_data=self.metrics.quality_gain == 0,
        )
        gates.append(quality_gate)
        
        if quality_gate.status == AdmissionGateStatus.FAIL:
            recommendations.append("Quality gain not sufficient for mode upgrade")
        
        # Determine state
        state = self._determine_state(gates, blockers)
        
        # Additional recommendations
        if state == AdmissionState.MANUAL_ONLY:
            recommendations.append("Continue using explicit ollama requests only")
        elif state == AdmissionState.LIMITED_ROLLOUT_CANDIDATE:
            recommendations.append("Consider limited rollout to specific scenarios")
        elif state == AdmissionState.AUTO_MODE_CANDIDATE:
            recommendations.append("Auto mode may be considered after extended observation")
        elif state == AdmissionState.ROLLBACK_REQUIRED:
            recommendations.append("Investigate and fix issues before any expansion")
        
        return AdmissionDecision(
            state=state,
            gates=gates,
            blockers=blockers,
            recommendations=recommendations,
            metrics=self.metrics,
        )
    
    def _determine_state(
        self, 
        gates: List[AdmissionGateResult],
        blockers: List[str],
    ) -> AdmissionState:
        """Determine admission state from gate results."""
        
        # Check for critical blockers
        for gate in gates:
            if gate.gate_name == "wrong_user_recall" and gate.status == AdmissionGateStatus.FAIL:
                return AdmissionState.ROLLBACK_REQUIRED
        
        # Check for insufficient data
        has_insufficient_data = any(
            g.status == AdmissionGateStatus.INSUFFICIENT_DATA for g in gates
        )
        if has_insufficient_data:
            return AdmissionState.MANUAL_ONLY
        
        # Check for any failures
        has_failures = any(
            g.status == AdmissionGateStatus.FAIL for g in gates
        )
        if has_failures:
            return AdmissionState.MANUAL_ONLY
        
        # All gates passed
        # Distinguish between limited_rollout and auto_mode based on stability
        # For now, be conservative: only allow limited_rollout
        return AdmissionState.LIMITED_ROLLOUT_CANDIDATE
    
    def export_decision(self, path: Optional[str] = None) -> str:
        """Export decision to JSON."""
        decision = self.decide()
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"admission_decision_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(decision.to_dict(), f, indent=2)
        
        return str(output_path)
