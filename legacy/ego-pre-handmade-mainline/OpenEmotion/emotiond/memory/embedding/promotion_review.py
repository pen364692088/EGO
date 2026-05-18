"""
Promotion Review.

Reviews pilot promotion decisions with quality signal provenance validation.
Capability Owner: OpenEmotion

v6g: Quality Signal Provenance + Promotion Review

Ensures promotion decisions are based on valid, traceable quality signals.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from emotiond.memory.embedding.quality_signal_provenance import (
    QualitySignalProvenance,
    QualitySignalProvenanceBuilder,
    SignalSource,
)
from emotiond.memory.embedding.pilot_registry import (
    PilotRegistry,
    PilotConfig,
)


class ReviewVerdict(str, Enum):
    """Verdict for promotion review."""
    PROMOTE = "promote"
    KEEP_PILOT = "keep_pilot"
    ROLLBACK = "rollback"


@dataclass
class ReviewBlocker:
    """A blocker preventing promotion."""
    category: str
    message: str
    severity: str  # "critical", "warning"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class PromotionReview:
    """Complete promotion review result."""
    scenario_name: str
    verdict: ReviewVerdict
    blockers: List[ReviewBlocker] = field(default_factory=list)
    rationale: str = ""
    quality_signal_provenance: Optional[QualitySignalProvenance] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    review_timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "verdict": self.verdict.value,
            "blockers": [b.to_dict() for b in self.blockers],
            "rationale": self.rationale,
            "quality_signal_provenance": self.quality_signal_provenance.to_dict() if self.quality_signal_provenance else None,
            "metrics_summary": self.metrics_summary,
            "review_timestamp": self.review_timestamp,
        }


class PromotionReviewer:
    """Reviews pilot promotion decisions.
    
    Capability Owner: OpenEmotion
    
    Ensures:
    1. Quality signal provenance is valid
    2. All metrics meet thresholds
    3. No contradictions in evidence chain
    """
    
    def __init__(
        self,
        registry: Optional[PilotRegistry] = None,
        config: Optional[PilotConfig] = None,
    ):
        self.registry = registry or PilotRegistry(config)
        self.config = self.registry.config
    
    def review_pilot_promotion(
        self,
        scenario_name: str,
        quality_signal_provenance: Optional[QualitySignalProvenance] = None,
    ) -> PromotionReview:
        """Review a pilot scenario for promotion.
        
        Args:
            scenario_name: Scenario to review
            quality_signal_provenance: Quality signal with provenance
            
        Returns:
            PromotionReview with verdict and details
        """
        # Get metrics
        metrics = self.registry.get_pilot_metrics(scenario_name)
        
        if not metrics:
            return PromotionReview(
                scenario_name=scenario_name,
                verdict=ReviewVerdict.KEEP_PILOT,
                blockers=[ReviewBlocker(
                    category="unknown_scenario",
                    message=f"Scenario {scenario_name} not found",
                    severity="critical",
                )],
                rationale="Scenario not found in pilot registry",
            )
        
        # Step 1: Check rollback conditions (highest priority)
        rollback_blockers = self._check_rollback_conditions(metrics)
        if rollback_blockers:
            return PromotionReview(
                scenario_name=scenario_name,
                verdict=ReviewVerdict.ROLLBACK,
                blockers=rollback_blockers,
                rationale="Critical issues detected - rollback required",
                quality_signal_provenance=quality_signal_provenance,
                metrics_summary=metrics,
            )
        
        # Step 2: Validate quality signal provenance
        provenance_blockers = self._validate_provenance(quality_signal_provenance, metrics)
        
        if provenance_blockers:
            return PromotionReview(
                scenario_name=scenario_name,
                verdict=ReviewVerdict.KEEP_PILOT,
                blockers=provenance_blockers,
                rationale="Quality signal provenance validation failed",
                quality_signal_provenance=quality_signal_provenance,
                metrics_summary=metrics,
            )
        
        # Step 3: Check promotion conditions
        promotion_blockers = self._check_promotion_conditions(metrics, quality_signal_provenance)
        
        if promotion_blockers:
            return PromotionReview(
                scenario_name=scenario_name,
                verdict=ReviewVerdict.KEEP_PILOT,
                blockers=promotion_blockers,
                rationale="Promotion criteria not met",
                quality_signal_provenance=quality_signal_provenance,
                metrics_summary=metrics,
            )
        
        # All checks passed
        return PromotionReview(
            scenario_name=scenario_name,
            verdict=ReviewVerdict.PROMOTE,
            blockers=[],
            rationale="All promotion criteria met with valid quality signal provenance",
            quality_signal_provenance=quality_signal_provenance,
            metrics_summary=metrics,
        )
    
    def _check_rollback_conditions(self, metrics: Dict[str, Any]) -> List[ReviewBlocker]:
        """Check conditions that require rollback."""
        blockers = []
        
        # Fallback rate
        fallback_rate = metrics.get("fallback_rate", 0)
        if fallback_rate > self.config.rollback_fallback_rate:
            blockers.append(ReviewBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} > {self.config.rollback_fallback_rate:.1%}",
                severity="critical",
            ))
        
        # P95 latency
        p95 = metrics.get("p95_latency_ms")
        if p95 and p95 > self.config.rollback_p95_latency_ms:
            blockers.append(ReviewBlocker(
                category="latency",
                message=f"P95 latency {p95:.1f}ms > {self.config.rollback_p95_latency_ms:.1f}ms",
                severity="critical",
            ))
        
        # Provider health
        health_rate = metrics.get("provider_health_rate", 1.0)
        if health_rate < self.config.rollback_min_provider_health_rate:
            blockers.append(ReviewBlocker(
                category="provider_health",
                message=f"Provider health {health_rate:.1%} < {self.config.rollback_min_provider_health_rate:.1%}",
                severity="critical",
            ))
        
        return blockers
    
    def _validate_provenance(
        self,
        provenance: Optional[QualitySignalProvenance],
        metrics: Dict[str, Any],
    ) -> List[ReviewBlocker]:
        """Validate quality signal provenance.
        
        CRITICAL: This is the core fix for v6g.
        """
        blockers = []
        
        if provenance is None:
            blockers.append(ReviewBlocker(
                category="provenance_missing",
                message="Quality signal provenance not provided",
                severity="critical",
            ))
            return blockers
        
        # Rule 1: interpretable check
        if not provenance.interpretable:
            blockers.append(ReviewBlocker(
                category="not_interpretable",
                message="Quality signal is not interpretable",
                severity="critical",
            ))
            return blockers  # Can't proceed without interpretable signal
        
        # Rule 2: sample_count_used must be > 0
        if provenance.sample_count_used == 0:
            blockers.append(ReviewBlocker(
                category="no_samples",
                message="sample_count_used=0 but signal marked interpretable",
                severity="critical",
            ))
        
        # Rule 3: Validate consistency
        consistency_errors = provenance.validate_consistency()
        for error in consistency_errors:
            blockers.append(ReviewBlocker(
                category="provenance_consistency",
                message=error,
                severity="critical",
            ))
        
        # Rule 4: Check explanation vs sample count
        if provenance.sample_count_used > 0:
            if str(provenance.sample_count_used) not in provenance.explanation:
                blockers.append(ReviewBlocker(
                    category="explanation_mismatch",
                    message=f"Explanation '{provenance.explanation}' doesn't mention {provenance.sample_count_used} samples",
                    severity="critical",
                ))
        
        # Rule 5: source-specific validation
        if provenance.source == SignalSource.SHADOW_COMPARE:
            if not provenance.baseline_provider or not provenance.candidate_provider:
                blockers.append(ReviewBlocker(
                    category="missing_providers",
                    message="shadow_compare requires baseline_provider and candidate_provider",
                    severity="critical",
                ))
        
        # Rule 6: Cross-validate with pilot sample count
        pilot_sample_count = metrics.get("pilot_sample_size", 0)
        if provenance.sample_count_used > pilot_sample_count:
            blockers.append(ReviewBlocker(
                category="sample_count_mismatch",
                message=f"provenance sample_count ({provenance.sample_count_used}) > pilot_sample_size ({pilot_sample_count})",
                severity="warning",  # Warning, not critical
            ))
        
        return blockers
    
    def _check_promotion_conditions(
        self,
        metrics: Dict[str, Any],
        provenance: Optional[QualitySignalProvenance],
    ) -> List[ReviewBlocker]:
        """Check promotion conditions."""
        blockers = []
        
        # Sample size
        sample_size = metrics.get("pilot_sample_size", 0)
        if sample_size < self.config.min_pilot_sample_size:
            blockers.append(ReviewBlocker(
                category="sample_size",
                message=f"Pilot sample size {sample_size} < {self.config.min_pilot_sample_size}",
                severity="warning",
            ))
        
        # Fallback rate
        fallback_rate = metrics.get("fallback_rate", 0)
        if fallback_rate > self.config.max_fallback_rate:
            blockers.append(ReviewBlocker(
                category="fallback_rate",
                message=f"Fallback rate {fallback_rate:.1%} > {self.config.max_fallback_rate:.1%}",
                severity="warning",
            ))
        
        # Wrong user triggers
        wrong_user = metrics.get("wrong_user_guard_trigger_count", 0)
        if wrong_user > self.config.max_wrong_user_guard_trigger:
            blockers.append(ReviewBlocker(
                category="wrong_user",
                message=f"Wrong user triggers: {wrong_user} > {self.config.max_wrong_user_guard_trigger}",
                severity="warning",
            ))
        
        # Provider health
        health_rate = metrics.get("provider_health_rate", 0)
        if health_rate < self.config.min_provider_health_rate:
            blockers.append(ReviewBlocker(
                category="provider_health",
                message=f"Provider health {health_rate:.1%} < {self.config.min_provider_health_rate:.1%}",
                severity="warning",
            ))
        
        # P95 latency
        p95 = metrics.get("p95_latency_ms")
        if p95 and p95 > self.config.max_p95_latency_ms:
            blockers.append(ReviewBlocker(
                category="latency",
                message=f"P95 latency {p95:.1f}ms > {self.config.max_p95_latency_ms:.1f}ms",
                severity="warning",
            ))
        
        # Pilot rounds
        pilot_rounds = metrics.get("pilot_rounds", 0)
        if pilot_rounds < self.config.min_pilot_rounds:
            blockers.append(ReviewBlocker(
                category="pilot_rounds",
                message=f"Pilot rounds {pilot_rounds} < {self.config.min_pilot_rounds}",
                severity="warning",
            ))
        
        # Quality signal value (using provenance)
        if provenance and provenance.signal_value <= self.config.min_quality_signal:
            blockers.append(ReviewBlocker(
                category="quality_signal_value",
                message=f"Quality signal {provenance.signal_value:.4f} <= {self.config.min_quality_signal}",
                severity="warning",
            ))
        
        return blockers
    
    def explain_review(self, review: PromotionReview) -> str:
        """Generate explanation of review."""
        lines = [
            f"Promotion Review: {review.scenario_name}",
            f"Verdict: {review.verdict.value.upper()}",
            "",
            f"Rationale: {review.rationale}",
            "",
        ]
        
        if review.blockers:
            lines.append("Blockers:")
            for b in review.blockers:
                lines.append(f"  [{b.severity.upper()}] {b.category}: {b.message}")
            lines.append("")
        
        if review.quality_signal_provenance:
            prov = review.quality_signal_provenance
            lines.append("Quality Signal Provenance:")
            lines.append(f"  Signal value: {prov.signal_value:.4f}")
            lines.append(f"  Source: {prov.source.value}")
            lines.append(f"  Interpretable: {prov.interpretable}")
            lines.append(f"  Sample count: {prov.sample_count_used}")
            lines.append(f"  Computation: {prov.computation_method.value}")
            lines.append(f"  Explanation: {prov.explanation}")
            
            if prov.baseline_provider:
                lines.append(f"  Baseline: {prov.baseline_provider}")
                lines.append(f"  Candidate: {prov.candidate_provider}")
            
            if not prov.is_valid_for_promotion():
                lines.append("  ⚠️ NOT VALID FOR PROMOTION")
        
        return "\n".join(lines)
    
    def export_review(self, review: PromotionReview, path: Optional[str] = None) -> str:
        """Export review to JSON."""
        data = {
            "review_timestamp": datetime.now().isoformat(),
            "review": review.to_dict(),
        }
        
        output_path = Path(path) if path else None
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"promotion_review_{timestamp}.json")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        
        return str(output_path)


def review_pilot_promotion(
    scenario_name: str,
    provenance: Optional[QualitySignalProvenance] = None,
) -> PromotionReview:
    """Convenience function to review promotion."""
    reviewer = PromotionReviewer()
    return reviewer.review_pilot_promotion(scenario_name, provenance)
