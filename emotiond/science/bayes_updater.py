"""
MVP-10 T25: Bayes Updater

Bayesian evidence aggregation for causal hypotheses.
Uses conservative priors and likelihood models per evidence type.

Features:
- Conservative prior (default: 0.5 probability)
- Likelihood model per evidence type (naive Bayes / log-likelihood)
- Output: posterior + uncertainty report (weakest evidence source)
- Monotonicity: More consistent evidence should increase posterior

Usage:
    updater = BayesUpdater()
    
    # Add evidence
    updater.add_evidence("workspace", 0.7, strength=0.8)
    updater.add_evidence("hot", 0.6, strength=0.9)
    
    # Compute posterior
    result = updater.compute_posterior()
    
    # Get uncertainty report
    report = updater.get_uncertainty_report()
"""
import math
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class EvidenceType(Enum):
    """Types of evidence for Bayesian updating."""
    WORKSPACE = "workspace"
    HOT = "hot"
    VALENCE = "valence"
    CONTINUITY = "continuity"


@dataclass
class EvidenceItem:
    """A single piece of evidence."""
    evidence_type: EvidenceType
    value: float  # 0.0 to 1.0
    strength: float = 0.5  # How strong this evidence is
    likelihood: float = 0.5  # P(evidence|hypothesis)
    ts: float = field(default_factory=time.time)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "value": round(self.value, 4),
            "strength": round(self.strength, 4),
            "likelihood": round(self.likelihood, 4),
            "ts": self.ts,
            "notes": self.notes,
        }


@dataclass
class BayesResult:
    """Result of Bayesian update."""
    prior: float
    posterior: float
    log_likelihood: float
    evidence_count: int
    evidence_types: List[str]
    uncertainty: float
    weakest_source: Optional[str]
    strongest_source: Optional[str]
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "prior": round(self.prior, 4),
            "posterior": round(self.posterior, 4),
            "log_likelihood": round(self.log_likelihood, 4),
            "evidence_count": self.evidence_count,
            "evidence_types": self.evidence_types,
            "uncertainty": round(self.uncertainty, 4),
            "weakest_source": self.weakest_source,
            "strongest_source": self.strongest_source,
            "ts": self.ts,
        }


class LikelihoodModel:
    """
    Likelihood model for computing P(evidence|hypothesis).
    
    Uses simple naive Bayes-style likelihood estimation.
    Each evidence type has its own likelihood function.
    """
    
    # Default likelihood parameters per evidence type
    DEFAULT_PARAMS = {
        EvidenceType.WORKSPACE: {
            "sensitivity": 0.7,  # P(evidence|hypothesis true)
            "specificity": 0.8,  # P(no evidence|hypothesis false)
        },
        EvidenceType.HOT: {
            "sensitivity": 0.75,
            "specificity": 0.85,
        },
        EvidenceType.VALENCE: {
            "sensitivity": 0.6,
            "specificity": 0.7,
        },
        EvidenceType.CONTINUITY: {
            "sensitivity": 0.65,
            "specificity": 0.75,
        },
    }
    
    @classmethod
    def compute_likelihood(
        cls,
        evidence_type: EvidenceType,
        value: float,
        strength: float,
    ) -> float:
        """
        Compute likelihood P(evidence|hypothesis).
        
        Args:
            evidence_type: Type of evidence
            value: Evidence value (0.0 to 1.0)
            strength: How strong the evidence is
        
        Returns:
            Likelihood probability
        """
        params = cls.DEFAULT_PARAMS.get(evidence_type, {
            "sensitivity": 0.5,
            "specificity": 0.5,
        })
        
        sensitivity = params["sensitivity"]
        
        # Simple model: likelihood = sensitivity * (value * strength)
        # Higher value and strength -> higher likelihood
        weighted_value = value * strength
        likelihood = 0.5 + sensitivity * weighted_value * 0.5
        
        return max(0.01, min(0.99, likelihood))  # Clamp to avoid 0/1
    
    @classmethod
    def compute_log_likelihood(
        cls,
        evidence_type: EvidenceType,
        value: float,
        strength: float,
    ) -> float:
        """
        Compute log-likelihood for numerical stability.
        
        Args:
            evidence_type: Type of evidence
            value: Evidence value
            strength: Evidence strength
        
        Returns:
            Log-likelihood
        """
        likelihood = cls.compute_likelihood(evidence_type, value, strength)
        return math.log(likelihood)


class BayesUpdater:
    """
    Bayesian updater for aggregating causal evidence.
    
    Uses conservative priors and likelihood models per evidence type.
    Outputs posterior probability with uncertainty report.
    
    Key properties:
    - Monotonicity: Consistent evidence should increase posterior
    - Conservative: Prior defaults to 0.5
    - Uncertainty: Tracks weakest evidence source
    """
    
    def __init__(self, prior: float = 0.5):
        """
        Initialize Bayesian updater.
        
        Args:
            prior: Prior probability (default: 0.5, conservative)
        """
        self.prior = prior
        self.evidence: List[EvidenceItem] = []
        self._evidence_by_type: Dict[EvidenceType, List[EvidenceItem]] = {
            t: [] for t in EvidenceType
        }
    
    def add_evidence(
        self,
        evidence_type: EvidenceType,
        value: float,
        strength: float = 0.5,
        notes: str = "",
    ) -> EvidenceItem:
        """
        Add a piece of evidence.
        
        Args:
            evidence_type: Type of evidence
            value: Evidence value (0.0 to 1.0)
            strength: How strong this evidence is (0.0 to 1.0)
            notes: Optional notes
        
        Returns:
            The created EvidenceItem
        """
        # Compute likelihood
        likelihood = LikelihoodModel.compute_likelihood(evidence_type, value, strength)
        
        item = EvidenceItem(
            evidence_type=evidence_type,
            value=value,
            strength=strength,
            likelihood=likelihood,
            notes=notes,
        )
        
        self.evidence.append(item)
        self._evidence_by_type[evidence_type].append(item)
        
        return item
    
    def compute_posterior(self) -> BayesResult:
        """
        Compute posterior probability using simple Bayesian update.
        
        Uses a simplified model for monotonicity:
        - Evidence with value > 0.5 supports the hypothesis
        - Evidence with value < 0.5 opposes the hypothesis
        - Strength modulates the effect
        
        Returns:
            BayesResult with posterior and uncertainty info
        """
        if not self.evidence:
            return BayesResult(
                prior=self.prior,
                posterior=self.prior,
                log_likelihood=0.0,
                evidence_count=0,
                evidence_types=[],
                uncertainty=1.0,  # Maximum uncertainty with no evidence
                weakest_source=None,
                strongest_source=None,
            )
        
        # Compute weighted evidence score
        # Each piece of evidence contributes: (value - 0.5) * strength
        # Positive = supports hypothesis, Negative = opposes
        total_weight = 0.0
        weighted_sum = 0.0
        log_likelihoods = []
        
        for item in self.evidence:
            # Compute contribution
            contribution = (item.value - 0.5) * item.strength
            weighted_sum += contribution
            total_weight += item.strength
            
            # Compute log-likelihood for reporting
            ll = LikelihoodModel.compute_log_likelihood(
                item.evidence_type, item.value, item.strength
            )
            log_likelihoods.append(ll)
        
        total_log_likelihood = sum(log_likelihoods)
        
        # Compute posterior using simple additive model
        # Start from prior and adjust based on evidence
        if total_weight > 0:
            # Average contribution (ranges from -0.5 to 0.5)
            avg_contribution = weighted_sum / total_weight
            
            # Scale to posterior adjustment
            # Maximum adjustment is bounded
            adjustment = avg_contribution * 0.8  # Scale factor for smoothness
            
            posterior = self.prior + adjustment
        else:
            posterior = self.prior
        
        # Clamp to [0.01, 0.99]
        posterior = max(0.01, min(0.99, posterior))
        
        # Compute uncertainty (based on evidence quality)
        uncertainty = self._compute_uncertainty()
        
        # Find weakest and strongest sources
        weakest, strongest = self._find_extreme_sources()
        
        return BayesResult(
            prior=self.prior,
            posterior=posterior,
            log_likelihood=total_log_likelihood,
            evidence_count=len(self.evidence),
            evidence_types=list(set(e.evidence_type.value for e in self.evidence)),
            uncertainty=uncertainty,
            weakest_source=weakest,
            strongest_source=strongest,
        )
    
    def _compute_uncertainty(self) -> float:
        """
        Compute uncertainty based on evidence quality.
        
        Higher uncertainty when:
        - Few evidence items
        - Low strength evidence
        - Conflicting evidence values
        
        Returns:
            Uncertainty score (0.0 = certain, 1.0 = very uncertain)
        """
        if not self.evidence:
            return 1.0
        
        # Factor 1: Evidence count (more = lower uncertainty)
        count_factor = max(0.0, 1.0 - len(self.evidence) / 10.0)
        
        # Factor 2: Average strength (higher = lower uncertainty)
        avg_strength = sum(e.strength for e in self.evidence) / len(self.evidence)
        strength_factor = 1.0 - avg_strength
        
        # Factor 3: Value variance (higher variance = higher uncertainty)
        values = [e.value for e in self.evidence]
        if len(values) > 1:
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            variance_factor = min(1.0, variance * 4)  # Scale variance
        else:
            variance_factor = 0.5
        
        # Combine factors
        uncertainty = (count_factor * 0.3 + strength_factor * 0.4 + variance_factor * 0.3)
        
        return max(0.0, min(1.0, uncertainty))
    
    def _find_extreme_sources(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Find weakest and strongest evidence sources.
        
        Returns:
            Tuple of (weakest_type, strongest_type)
        """
        if not self.evidence:
            return None, None
        
        # Compute average value*strength per type
        type_scores: Dict[EvidenceType, float] = {}
        type_counts: Dict[EvidenceType, int] = {}
        
        for e in self.evidence:
            score = e.value * e.strength
            type_scores[e.evidence_type] = type_scores.get(e.evidence_type, 0) + score
            type_counts[e.evidence_type] = type_counts.get(e.evidence_type, 0) + 1
        
        # Average scores
        avg_scores = {
            t: type_scores[t] / type_counts[t]
            for t in type_scores
        }
        
        if not avg_scores:
            return None, None
        
        # Find extremes
        sorted_types = sorted(avg_scores.items(), key=lambda x: x[1])
        
        weakest = sorted_types[0][0].value if sorted_types else None
        strongest = sorted_types[-1][0].value if sorted_types else None
        
        return weakest, strongest
    
    def get_uncertainty_report(self) -> Dict[str, Any]:
        """
        Get detailed uncertainty report.
        
        Returns:
            Dict with uncertainty analysis
        """
        result = self.compute_posterior()
        
        # Analyze by evidence type
        type_analysis = {}
        for et in EvidenceType:
            items = self._evidence_by_type[et]
            if items:
                avg_value = sum(e.value for e in items) / len(items)
                avg_strength = sum(e.strength for e in items) / len(items)
                avg_likelihood = sum(e.likelihood for e in items) / len(items)
                
                type_analysis[et.value] = {
                    "count": len(items),
                    "avg_value": round(avg_value, 4),
                    "avg_strength": round(avg_strength, 4),
                    "avg_likelihood": round(avg_likelihood, 4),
                }
        
        return {
            "posterior": result.posterior,
            "uncertainty": result.uncertainty,
            "weakest_source": result.weakest_source,
            "strongest_source": result.strongest_source,
            "evidence_by_type": type_analysis,
            "recommendations": self._generate_recommendations(result),
        }
    
    def _generate_recommendations(self, result: BayesResult) -> List[str]:
        """Generate recommendations based on uncertainty analysis."""
        recommendations = []
        
        if result.uncertainty > 0.7:
            recommendations.append("High uncertainty - collect more evidence")
        
        if result.weakest_source:
            recommendations.append(f"Strengthen {result.weakest_source} evidence")
        
        if result.evidence_count < 3:
            recommendations.append("Need more evidence items for reliable inference")
        
        # Check for type coverage
        missing_types = [
            t.value for t in EvidenceType
            if not self._evidence_by_type[t]
        ]
        if missing_types:
            recommendations.append(f"Missing evidence types: {', '.join(missing_types)}")
        
        return recommendations
    
    def reset(self, prior: Optional[float] = None) -> None:
        """
        Reset the updater.
        
        Args:
            prior: New prior (keeps existing if not provided)
        """
        if prior is not None:
            self.prior = prior
        self.evidence = []
        self._evidence_by_type = {t: [] for t in EvidenceType}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize updater state."""
        return {
            "prior": self.prior,
            "evidence_count": len(self.evidence),
            "evidence": [e.to_dict() for e in self.evidence],
            "evidence_types_present": list(set(
                e.evidence_type.value for e in self.evidence
            )),
        }


def create_bayes_updater(prior: float = 0.5) -> BayesUpdater:
    """Factory function to create a BayesUpdater."""
    return BayesUpdater(prior=prior)


def aggregate_evidence(
    evidence_items: List[Dict[str, Any]],
    prior: float = 0.5,
) -> Dict[str, Any]:
    """
    Convenience function to aggregate multiple evidence items.
    
    Args:
        evidence_items: List of {type, value, strength} dicts
        prior: Prior probability
    
    Returns:
        Dict with posterior and uncertainty report
    """
    updater = create_bayes_updater(prior=prior)
    
    for item in evidence_items:
        evidence_type = EvidenceType(item.get("type", "workspace"))
        value = item.get("value", 0.5)
        strength = item.get("strength", 0.5)
        notes = item.get("notes", "")
        
        updater.add_evidence(evidence_type, value, strength, notes)
    
    result = updater.compute_posterior()
    uncertainty_report = updater.get_uncertainty_report()
    
    return {
        "bayes_result": result.to_dict(),
        "uncertainty_report": uncertainty_report,
    }
