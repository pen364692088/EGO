"""
Pilot Evaluator.

Evaluates pilot scenarios for promotion to whitelist.
Capability Owner: OpenEmotion

v6f: Candidate Scenario Pilot + Quality Signal Calibration
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
    PilotScenario,
    ScenarioStatus,
)
from emotiond.memory.embedding.quality_signal import (
    QualitySignalCalculator,
    QualitySignalResult,
    QualitySignalSource,
)


class PilotVerdict(str, Enum):
    """Verdict for pilot evaluation."""
    PROMOTE = "promote"  # Ready for whitelist
    KEEP_PILOT = "keep_pilot"  # Continue pilot
    ROLLBACK = "rollback"  # Remove from pilot


@dataclass
class PilotBlocker:
    """A blocker preventing promotion."""
    category: str
    message: str
    threshold: Any
    actual: Any
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "threshold": self.threshold,
            "actual": self.actual,
        }


@dataclass
class PilotDecision:
    """Full pilot evaluation decision."""
    scenario_name: str
    verdict: PilotVerdict
    blockers: List[PilotBlocker] = field(default_factory=list)
    rationale: str = ""
    next_allowed_action: str = ""
    quality_signal_result: Optional[QualitySignalResult] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "verdict": self.verdict.value,
            "blockers": [b.to_dict() for b in self.blockers],
            "rationale": self.rationale,
            "next_allowed_action": self.next_allowed_action,
            "quality_signal": self.quality_signal_result.to_dict() if self.quality_signal_result else None,
            "metrics_summary": self.metrics_summary,
            "timestamp": self.timestamp,
        }


class PilotEvaluator:
    """Evaluates pilot scenarios for promotion.
    
    Capability Owner: OpenEmotion
    
    Decision logic:
    1. Check for rollback conditions (highest priority)
    2. Check for promotion conditions
    3. Default to keep_pilot
    """
    
    def __init__(
        self,
        registry: Optional[PilotRegistry] = None,
        config: Optional[PilotConfig] = None,
    ):
        self.registry = registry or PilotRegistry(config)
        self.config = self.registry.config
        self.quality_calculator = QualitySignalCalculator()
    
    def evaluate_pilot(self, scenario_name: str) -> PilotDecision:
        """Evaluate a pilot scenario.
        
        Args:
            scenario_name: Scenario to evaluate
            
        Returns:
            PilotDecision with verdict and details
        """
        # Get scenario metrics
        metrics = self.registry.get_pilot_metrics(scenario_name)
        
        if not metrics:
            return PilotDecision(
                scenario_name=scenario_name,
                verdict=PilotVerdict.KEEP_PILOT,
                blockers=[PilotBlocker(
                    category="unknown_scenario",
                    message=f"Scenario {scenario_name} not found in registry",
                    threshold="valid_scenario",
                    actual="not_found",
                )],
                rationale="Scenario not found",
                next_allowed_action="Register scenario before pilot",
            )
        
        # Check rollback conditions first
        rollback_blockers = self._check_rollback_conditions(metrics)
        if rollback_blockers:
            return PilotDecision(
                scenario_name=scenario_name,
                verdict=PilotVerdict.ROLLBACK,
                blockers=rollback_blockers,
                rationale="Critical issues detected - rollback required",
                next_allowed_action="Investigate and fix issues before continuing pilot",
                metrics_summary=metrics,
            )
        
        # Compute quality signal
        quality_signal = self._compute_quality_signal(metrics)
        
        # Check promotion conditions
        promotion_blockers = self._check_promotion_conditions(metrics, quality_signal)
        
        if promotion_blockers:
            return PilotDecision(
                scenario_name=scenario_name,
                verdict=PilotVerdict.KEEP_PILOT,
                blockers=promotion_blockers,
                rationale="Promotion criteria not met - continue pilot",
                next_allowed_action="Continue collecting data and monitoring quality signal",
                quality_signal_result=quality_signal,
                metrics_summary=metrics,
            )
        
        # All conditions met - ready for promotion
        return PilotDecision(
            scenario_name=scenario_name,
            verdict=PilotVerdict.PROMOTE,
            blockers=[],
            rationale="All promotion criteria met - ready for whitelist",
            next_allowed_action="Add scenario to production whitelist (requires explicit approval)",
            quality_signal_result=quality_signal,
            metrics_summary=metrics,
        )
    
    def _compute_quality_signal(self, metrics: Dict[str, Any]) -> QualitySignalResult:
        """Compute quality signal for the scenario."""
        # Try to get existing signal
        avg_signal = metrics.get("avg_quality_signal")
        
        if avg_signal is not None and avg_signal > 0:
            # Signal already computed
            return QualitySignalResult(
                signal_value=avg_signal,
                source=QualitySignalSource.SHADOW_COMPARE,
                interpretable=True,
                confidence=0.7,
                explanation=f"Computed from {len(metrics.get('quality_signal_samples', []))} samples",
            )
        
        # No signal available - return placeholder
        return self.quality_calculator.compute_placeholder_signal(
            reason="Quality signal not yet computed - no shadow compare or proxy data available"
        )
    
    def _check_rollback_conditions(self, metrics: Dict[str, Any]) -> List[PilotBlocker]:
        """Check conditions that require rollback."""
        blockers = []
        
        # Check fallback rate
        fallback_rate = metrics.get("fallback_rate", 0)
        if fallback_rate > self.config.rollback_fallback_rate:
            blockers.append(PilotBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} exceeds rollback threshold {self.config.rollback_fallback_rate:.1%}",
                threshold=self.config.rollback_fallback_rate,
                actual=fallback_rate,
            ))
        
        # Check p95 latency
        p95 = metrics.get("p95_latency_ms")
        if p95 and p95 > self.config.rollback_p95_latency_ms:
            blockers.append(PilotBlocker(
                category="latency",
                message=f"P95 latency {p95:.1f}ms exceeds rollback threshold {self.config.rollback_p95_latency_ms:.1f}ms",
                threshold=self.config.rollback_p95_latency_ms,
                actual=p95,
            ))
        
        # Check provider health
        health_rate = metrics.get("provider_health_rate", 1.0)
        if health_rate < self.config.rollback_min_provider_health_rate:
            blockers.append(PilotBlocker(
                category="provider_health",
                message=f"Provider health rate {health_rate:.1%} below rollback threshold {self.config.rollback_min_provider_health_rate:.1%}",
                threshold=self.config.rollback_min_provider_health_rate,
                actual=health_rate,
            ))
        
        return blockers
    
    def _check_promotion_conditions(
        self,
        metrics: Dict[str, Any],
        quality_signal: QualitySignalResult,
    ) -> List[PilotBlocker]:
        """Check conditions for promotion."""
        blockers = []
        
        # Check sample size
        sample_size = metrics.get("pilot_sample_size", 0)
        if sample_size < self.config.min_pilot_sample_size:
            blockers.append(PilotBlocker(
                category="sample_size",
                message=f"Pilot sample size {sample_size} below threshold {self.config.min_pilot_sample_size}",
                threshold=self.config.min_pilot_sample_size,
                actual=sample_size,
            ))
        
        # Check fallback rate
        fallback_rate = metrics.get("fallback_rate", 0)
        if fallback_rate > self.config.max_fallback_rate:
            blockers.append(PilotBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} exceeds threshold {self.config.max_fallback_rate:.1%}",
                threshold=self.config.max_fallback_rate,
                actual=fallback_rate,
            ))
        
        # Check wrong user triggers
        wrong_user = metrics.get("wrong_user_guard_trigger_count", 0)
        if wrong_user > self.config.max_wrong_user_guard_trigger:
            blockers.append(PilotBlocker(
                category="wrong_user",
                message=f"Wrong user triggers: {wrong_user} > {self.config.max_wrong_user_guard_trigger}",
                threshold=self.config.max_wrong_user_guard_trigger,
                actual=wrong_user,
            ))
        
        # Check provider health
        health_rate = metrics.get("provider_health_rate", 0)
        if health_rate < self.config.min_provider_health_rate:
            blockers.append(PilotBlocker(
                category="provider_health",
                message=f"Provider health rate {health_rate:.1%} below threshold {self.config.min_provider_health_rate:.1%}",
                threshold=self.config.min_provider_health_rate,
                actual=health_rate,
            ))
        
        # Check p95 latency
        p95 = metrics.get("p95_latency_ms")
        if p95 and p95 > self.config.max_p95_latency_ms:
            blockers.append(PilotBlocker(
                category="latency",
                message=f"P95 latency {p95:.1f}ms exceeds threshold {self.config.max_p95_latency_ms:.1f}ms",
                threshold=self.config.max_p95_latency_ms,
                actual=p95,
            ))
        
        # Check pilot rounds
        pilot_rounds = metrics.get("pilot_rounds", 0)
        if pilot_rounds < self.config.min_pilot_rounds:
            blockers.append(PilotBlocker(
                category="pilot_rounds",
                message=f"Pilot rounds {pilot_rounds} below threshold {self.config.min_pilot_rounds}",
                threshold=self.config.min_pilot_rounds,
                actual=pilot_rounds,
            ))
        
        # Check quality signal (CRITICAL)
        if not quality_signal.interpretable:
            blockers.append(PilotBlocker(
                category="quality_signal",
                message=f"Quality signal not interpretable: {quality_signal.explanation}",
                threshold="interpretable signal",
                actual=f"source={quality_signal.source.value}, interpretable={quality_signal.interpretable}",
            ))
        elif quality_signal.signal_value <= self.config.min_quality_signal:
            blockers.append(PilotBlocker(
                category="quality_signal",
                message=f"Quality signal {quality_signal.signal_value:.4f} not positive (threshold: > {self.config.min_quality_signal})",
                threshold=f">{self.config.min_quality_signal}",
                actual=quality_signal.signal_value,
            ))
        
        return blockers
    
    def explain_decision(self, decision: PilotDecision) -> str:
        """Generate human-readable explanation of decision.
        
        Args:
            decision: PilotDecision to explain
            
        Returns:
            Explanation string
        """
        lines = [
            f"Scenario: {decision.scenario_name}",
            f"Verdict: {decision.verdict.value.upper()}",
            "",
            f"Rationale: {decision.rationale}",
            "",
        ]
        
        if decision.blockers:
            lines.append("Blockers:")
            for b in decision.blockers:
                lines.append(f"  - [{b.category}] {b.message}")
            lines.append("")
        
        if decision.quality_signal_result:
            lines.append("Quality Signal:")
            lines.append(f"  Value: {decision.quality_signal_result.signal_value:.4f}")
            lines.append(f"  Source: {decision.quality_signal_result.source.value}")
            lines.append(f"  Interpretable: {decision.quality_signal_result.interpretable}")
            lines.append(f"  Explanation: {decision.quality_signal_result.explanation}")
            lines.append("")
        
        lines.append(f"Next Action: {decision.next_allowed_action}")
        
        return "\n".join(lines)
    
    def export_decision(self, decision: PilotDecision, path: Optional[str] = None) -> str:
        """Export decision to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision.to_dict(),
            "config": self.config.to_dict(),
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"pilot_decision_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)


def evaluate_pilot_promotion(
    scenario_name: str,
    registry: Optional[PilotRegistry] = None,
) -> PilotDecision:
    """Convenience function to evaluate pilot promotion."""
    evaluator = PilotEvaluator(registry)
    return evaluator.evaluate_pilot(scenario_name)
