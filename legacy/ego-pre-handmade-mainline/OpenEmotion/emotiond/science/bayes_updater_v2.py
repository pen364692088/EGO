"""
MVP11-T20: Bayes Updater v2

Extended Bayesian evidence aggregation with MVP11 fields:
- Homeostasis state integration (6-dimensional)
- EFE (Expected Free Energy) terms
- Governor context for safety constraints

Key Features:
- Conservative prior (default: 0.5 probability)
- Likelihood model per evidence type (naive Bayes / log-likelihood)
- Homeostasis-weighted posterior calculation
- EFE-informed uncertainty estimation
- Governor-aware action safety scoring
- Output: posterior + uncertainty_report (identify largest uncertainty source)

Monotonicity: More consistent evidence should increase posterior

Usage:
    updater = BayesUpdaterV2()
    
    # Add evidence
    updater.add_evidence("workspace", 0.7, strength=0.8)
    updater.add_evidence("hot", 0.6, strength=0.9)
    
    # Set MVP11 context
    updater.set_homeostasis(homeostasis_state)
    updater.set_efe_terms(risk=0.3, ambiguity=0.2, info_gain=0.5, cost=0.1)
    updater.set_governor_context(action_risk=0.1, is_destructive=False)
    
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

# Import existing MVP10 components
from .bayes_updater import (
    EvidenceType,
    EvidenceItem,
    BayesResult,
    LikelihoodModel,
)

# Import MVP11 components
try:
    from ..homeostasis import HomeostasisState, HomeostasisManager
    HOMEOSTASIS_AVAILABLE = True
except ImportError:
    HOMEOSTASIS_AVAILABLE = False
    HomeostasisState = None
    HomeostasisManager = None

try:
    from ..efe_policy import EFETerms, EFEPolicy
    EFE_AVAILABLE = True
except ImportError:
    EFE_AVAILABLE = False
    EFETerms = None
    EFEPolicy = None

try:
    from ..governor_v2 import GovernorDecision, GovernorV2, HomeostasisInfo
    GOVERNOR_AVAILABLE = True
except ImportError:
    GOVERNOR_AVAILABLE = False
    GovernorDecision = None
    GovernorV2 = None
    HomeostasisInfo = None


class UncertaintySource(str, Enum):
    """
    Types of uncertainty sources that can affect Bayesian inference.
    
    Used to identify the largest source of uncertainty in the uncertainty report.
    """
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    WEAK_EVIDENCE = "weak_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    MISSING_EVIDENCE_TYPE = "missing_evidence_type"
    HOMEOSTASIS_IMBALANCE = "homeostasis_imbalance"
    HIGH_AMBIGUITY = "high_ambiguity"
    HIGH_RISK = "high_risk"
    GOVERNOR_CONSTRAINT = "governor_constraint"
    LOW_INFORMATION_GAIN = "low_information_gain"
    HIGH_COST = "high_cost"


@dataclass
class MVP11Context:
    """
    MVP11 context for Bayesian updating.
    
    Contains homeostasis state, EFE terms, and governor context.
    """
    # Homeostasis state (6-dimensional)
    homeostasis: Optional[Any] = None  # HomeostasisState if available
    
    # EFE terms
    efe_terms: Optional[Any] = None  # EFETerms if available
    
    # Governor context
    governor_decision: Optional[str] = None  # GovernorDecision.value
    action_risk: float = 0.0
    is_destructive: bool = False
    is_recovery: bool = False
    
    # Computed weights
    homeostasis_weight: float = 1.0
    efe_weight: float = 1.0
    safety_weight: float = 1.0
    
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "homeostasis_weight": self.homeostasis_weight,
            "efe_weight": self.efe_weight,
            "safety_weight": self.safety_weight,
            "action_risk": self.action_risk,
            "is_destructive": self.is_destructive,
            "is_recovery": self.is_recovery,
            "governor_decision": self.governor_decision,
            "ts": self.ts,
        }
        
        if self.homeostasis is not None and hasattr(self.homeostasis, 'to_dict'):
            result["homeostasis"] = self.homeostasis.to_dict()
        
        if self.efe_terms is not None and hasattr(self.efe_terms, 'to_dict'):
            result["efe_terms"] = self.efe_terms.to_dict()
        
        return result


@dataclass
class UncertaintyReport:
    """
    Detailed uncertainty report for Bayesian inference.
    
    Identifies the largest uncertainty source and provides recommendations.
    """
    overall_uncertainty: float
    largest_source: UncertaintySource
    source_contribution: float  # How much this source contributes to uncertainty
    secondary_sources: List[Tuple[UncertaintySource, float]]
    
    # Component breakdown
    evidence_uncertainty: float
    homeostasis_uncertainty: float
    efe_uncertainty: float
    governor_uncertainty: float
    
    # Recommendations
    recommendations: List[str]
    
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_uncertainty": round(self.overall_uncertainty, 4),
            "largest_source": self.largest_source.value,
            "source_contribution": round(self.source_contribution, 4),
            "secondary_sources": [
                (s.value, round(c, 4)) for s, c in self.secondary_sources
            ],
            "evidence_uncertainty": round(self.evidence_uncertainty, 4),
            "homeostasis_uncertainty": round(self.homeostasis_uncertainty, 4),
            "efe_uncertainty": round(self.efe_uncertainty, 4),
            "governor_uncertainty": round(self.governor_uncertainty, 4),
            "recommendations": self.recommendations,
            "ts": self.ts,
        }


@dataclass
class BayesResultV2:
    """
    Extended Bayesian result with MVP11 fields.
    
    Includes posterior, uncertainty report, and MVP11 context.
    """
    # Base fields from BayesResult
    prior: float
    posterior: float
    log_likelihood: float
    evidence_count: int
    evidence_types: List[str]
    uncertainty: float
    weakest_source: Optional[str]
    strongest_source: Optional[str]
    
    # MVP11 extensions
    homeostasis_modulation: float = 0.0
    efe_modulation: float = 0.0
    governor_safe: bool = True
    largest_uncertainty_source: str = "insufficient_evidence"
    
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
            "homeostasis_modulation": round(self.homeostasis_modulation, 4),
            "efe_modulation": round(self.efe_modulation, 4),
            "governor_safe": self.governor_safe,
            "largest_uncertainty_source": self.largest_uncertainty_source,
            "ts": self.ts,
        }


class BayesUpdaterV2:
    """
    Extended Bayesian updater with MVP11 fields.
    
    Features:
    - Standard Bayesian evidence aggregation from v1
    - Homeostasis-weighted posterior (homeostasis state affects prior confidence)
    - EFE-informed uncertainty (ambiguity, risk, info_gain, cost)
    - Governor-aware safety (destructive actions penalized)
    - Detailed uncertainty report with largest source identification
    
    Monotonicity: Consistent evidence + good homeostasis + low EFE → higher posterior
    
    Integration:
    - Homeostasis: Low energy/safety/certainty increases uncertainty
    - EFE: High risk/ambiguity/cost increases uncertainty, high info_gain decreases
    - Governor: Destructive actions get prior penalty
    """
    
    # Weight multipliers for MVP11 components
    HOMEOSTASIS_WEIGHT_FACTOR = 0.15  # How much homeostasis affects posterior
    EFE_WEIGHT_FACTOR = 0.20  # How much EFE affects posterior
    GOVERNOR_PENALTY = 0.3  # Penalty for destructive/blocked actions
    
    # Thresholds for uncertainty source identification
    LOW_EVIDENCE_THRESHOLD = 3
    WEAK_EVIDENCE_THRESHOLD = 0.4
    CONFLICT_THRESHOLD = 0.3
    HOMEOSTASIS_STRESS_THRESHOLD = 0.3
    HIGH_AMBIGUITY_THRESHOLD = 0.6
    HIGH_RISK_THRESHOLD = 0.7
    LOW_INFO_GAIN_THRESHOLD = 0.3
    
    def __init__(self, prior: float = 0.5):
        """
        Initialize Bayesian updater v2.
        
        Args:
            prior: Prior probability (default: 0.5, conservative)
        """
        self.prior = prior
        self.evidence: List[EvidenceItem] = []
        self._evidence_by_type: Dict[EvidenceType, List[EvidenceItem]] = {
            t: [] for t in EvidenceType
        }
        
        # MVP11 context
        self._mvp11_context: Optional[MVP11Context] = None
        
        # Cached results
        self._last_result: Optional[BayesResultV2] = None
        self._last_uncertainty_report: Optional[UncertaintyReport] = None
    
    def set_homeostasis(self, homeostasis_state: Any) -> None:
        """
        Set homeostasis state for posterior modulation.
        
        Args:
            homeostasis_state: HomeostasisState instance (6-dimensional)
        """
        if self._mvp11_context is None:
            self._mvp11_context = MVP11Context()
        
        self._mvp11_context.homeostasis = homeostasis_state
        
        # Compute homeostasis weight based on overall state
        if homeostasis_state is not None and hasattr(homeostasis_state, 'energy'):
            # Average of key dimensions for overall homeostatic health
            overall = (
                getattr(homeostasis_state, 'energy', 0.5) +
                getattr(homeostasis_state, 'safety', 0.5) +
                getattr(homeostasis_state, 'certainty', 0.5)
            ) / 3.0
            
            # Weight modulation: healthier state → higher weight on evidence
            self._mvp11_context.homeostasis_weight = 0.5 + overall * 0.5
    
    def set_efe_terms(
        self,
        risk: float = 0.5,
        ambiguity: float = 0.5,
        info_gain: float = 0.5,
        cost: float = 0.5,
    ) -> None:
        """
        Set EFE terms for uncertainty estimation.
        
        Args:
            risk: Risk level (0-1)
            ambiguity: Ambiguity level (0-1)
            info_gain: Information gain potential (0-1)
            cost: Resource cost (0-1)
        """
        if self._mvp11_context is None:
            self._mvp11_context = MVP11Context()
        
        if EFE_AVAILABLE and EFETerms is not None:
            self._mvp11_context.efe_terms = EFETerms(
                risk=risk,
                ambiguity=ambiguity,
                info_gain=info_gain,
                cost=cost,
            )
        else:
            # Store as dict if EFE module not available
            self._mvp11_context.efe_terms = {
                "risk": risk,
                "ambiguity": ambiguity,
                "info_gain": info_gain,
                "cost": cost,
            }
        
        # Compute EFE weight based on terms
        # Lower risk/ambiguity/cost + higher info_gain → higher weight
        if isinstance(self._mvp11_context.efe_terms, dict):
            terms = self._mvp11_context.efe_terms
        else:
            terms = self._mvp11_context.efe_terms.to_dict()
        
        efe_score = (
            (1 - terms["risk"]) * 0.3 +
            (1 - terms["ambiguity"]) * 0.25 +
            terms["info_gain"] * 0.25 +
            (1 - terms["cost"]) * 0.2
        )
        
        self._mvp11_context.efe_weight = 0.5 + efe_score * 0.5
    
    def set_governor_context(
        self,
        action_risk: float = 0.0,
        is_destructive: bool = False,
        is_recovery: bool = False,
        governor_decision: Optional[str] = None,
    ) -> None:
        """
        Set governor context for safety evaluation.
        
        Args:
            action_risk: Risk level of the action (0-1)
            is_destructive: Whether action is destructive/irreversible
            is_recovery: Whether this is a recovery operation
            governor_decision: Pre-computed governor decision
        """
        if self._mvp11_context is None:
            self._mvp11_context = MVP11Context()
        
        self._mvp11_context.action_risk = action_risk
        self._mvp11_context.is_destructive = is_destructive
        self._mvp11_context.is_recovery = is_recovery
        self._mvp11_context.governor_decision = governor_decision
        
        # Compute safety weight
        if is_recovery:
            # Recovery actions are safe by definition
            self._mvp11_context.safety_weight = 1.0
        elif is_destructive:
            # Destructive actions get penalty
            self._mvp11_context.safety_weight = 1.0 - self.GOVERNOR_PENALTY
        elif action_risk > 0.9:
            # High risk requires approval
            self._mvp11_context.safety_weight = 0.7
        else:
            self._mvp11_context.safety_weight = 1.0
    
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
        # Compute likelihood using existing LikelihoodModel
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
    
    def compute_posterior(self) -> BayesResultV2:
        """
        Compute posterior probability with MVP11 extensions.
        
        Formula:
        posterior = base_posterior * homeostasis_modulation * efe_modulation * safety_weight
        
        Where:
        - base_posterior: Standard Bayesian update from v1
        - homeostasis_modulation: Adjustment based on homeostatic state
        - efe_modulation: Adjustment based on EFE terms
        - safety_weight: Adjustment based on governor context
        
        Returns:
            BayesResultV2 with posterior and MVP11 extensions
        """
        # Compute base posterior using v1 logic
        base_result = self._compute_base_posterior()
        
        # Get MVP11 modulations
        homeostasis_mod = self._compute_homeostasis_modulation()
        efe_mod = self._compute_efe_modulation()
        safety_weight = self._compute_safety_weight()
        
        # Compute final posterior
        # posterior = base * homeostasis * efe * safety
        posterior = base_result["posterior"]
        posterior *= homeostasis_mod
        posterior *= efe_mod
        posterior *= safety_weight
        
        # Clamp to [0.01, 0.99]
        posterior = max(0.01, min(0.99, posterior))
        
        # Identify largest uncertainty source
        uncertainty_report = self._compute_uncertainty_report(
            base_result, homeostasis_mod, efe_mod, safety_weight
        )
        
        # Build result
        result = BayesResultV2(
            prior=self.prior,
            posterior=posterior,
            log_likelihood=base_result["log_likelihood"],
            evidence_count=base_result["evidence_count"],
            evidence_types=base_result["evidence_types"],
            uncertainty=uncertainty_report.overall_uncertainty,
            weakest_source=base_result["weakest_source"],
            strongest_source=base_result["strongest_source"],
            homeostasis_modulation=homeostasis_mod,
            efe_modulation=efe_mod,
            governor_safe=(safety_weight >= 0.9),
            largest_uncertainty_source=uncertainty_report.largest_source.value,
        )
        
        self._last_result = result
        self._last_uncertainty_report = uncertainty_report
        
        return result
    
    def _compute_base_posterior(self) -> Dict[str, Any]:
        """
        Compute base posterior using v1 logic.
        
        Returns:
            Dict with posterior, log_likelihood, etc.
        """
        if not self.evidence:
            return {
                "posterior": self.prior,
                "log_likelihood": 0.0,
                "evidence_count": 0,
                "evidence_types": [],
                "uncertainty": 1.0,
                "weakest_source": None,
                "strongest_source": None,
            }
        
        # Compute weighted evidence score (same as v1)
        total_weight = 0.0
        weighted_sum = 0.0
        log_likelihoods = []
        
        for item in self.evidence:
            contribution = (item.value - 0.5) * item.strength
            weighted_sum += contribution
            total_weight += item.strength
            
            ll = LikelihoodModel.compute_log_likelihood(
                item.evidence_type, item.value, item.strength
            )
            log_likelihoods.append(ll)
        
        total_log_likelihood = sum(log_likelihoods)
        
        # Compute posterior
        if total_weight > 0:
            avg_contribution = weighted_sum / total_weight
            adjustment = avg_contribution * 0.8
            posterior = self.prior + adjustment
        else:
            posterior = self.prior
        
        posterior = max(0.01, min(0.99, posterior))
        
        # Find weakest and strongest sources
        weakest, strongest = self._find_extreme_sources()
        
        return {
            "posterior": posterior,
            "log_likelihood": total_log_likelihood,
            "evidence_count": len(self.evidence),
            "evidence_types": list(set(e.evidence_type.value for e in self.evidence)),
            "uncertainty": self._compute_evidence_uncertainty(),
            "weakest_source": weakest,
            "strongest_source": strongest,
        }
    
    def _compute_homeostasis_modulation(self) -> float:
        """
        Compute homeostasis-based modulation factor.
        
        Lower homeostatic health → lower modulation (more conservative)
        
        Returns:
            Modulation factor (0.0 to 1.0+)
        """
        if self._mvp11_context is None or self._mvp11_context.homeostasis is None:
            return 1.0
        
        homeostasis = self._mvp11_context.homeostasis
        
        # Get key dimensions
        if hasattr(homeostasis, 'energy'):
            energy = getattr(homeostasis, 'energy', 0.5)
            safety = getattr(homeostasis, 'safety', 0.5)
            certainty = getattr(homeostasis, 'certainty', 0.5)
        elif hasattr(homeostasis, 'to_dict'):
            state_dict = homeostasis.to_dict()
            energy = state_dict.get('energy', 0.5)
            safety = state_dict.get('safety', 0.5)
            certainty = state_dict.get('certainty', 0.5)
        else:
            return 1.0
        
        # Compute modulation: good state supports evidence, bad state penalizes
        # Using geometric mean for balanced effect
        modulation = (energy * safety * certainty) ** (1/3)
        
        # Scale: 0.5-1.5 range (0.5 = very stressed, 1.0 = neutral, 1.5 = optimal)
        modulation = 0.5 + modulation
        
        return modulation
    
    def _compute_efe_modulation(self) -> float:
        """
        Compute EFE-based modulation factor.
        
        Lower EFE (lower risk/ambiguity/cost, higher info_gain) → higher modulation
        
        Returns:
            Modulation factor (0.5 to 1.5)
        """
        if self._mvp11_context is None or self._mvp11_context.efe_terms is None:
            return 1.0
        
        efe_terms = self._mvp11_context.efe_terms
        
        if isinstance(efe_terms, dict):
            terms = efe_terms
        else:
            terms = efe_terms.to_dict()
        
        risk = terms.get("risk", 0.5)
        ambiguity = terms.get("ambiguity", 0.5)
        info_gain = terms.get("info_gain", 0.5)
        cost = terms.get("cost", 0.5)
        
        # EFE score: higher is better (lower risk/ambiguity/cost, higher info_gain)
        efe_score = (
            (1 - risk) * 0.3 +
            (1 - ambiguity) * 0.25 +
            info_gain * 0.25 +
            (1 - cost) * 0.2
        )
        
        # Modulation: 0.5 to 1.5 range
        modulation = 0.5 + efe_score
        
        return modulation
    
    def _compute_safety_weight(self) -> float:
        """
        Compute safety weight from governor context.
        
        Returns:
            Safety weight (0.7 to 1.0)
        """
        if self._mvp11_context is None:
            return 1.0
        
        return self._mvp11_context.safety_weight
    
    def _compute_uncertainty_report(
        self,
        base_result: Dict[str, Any],
        homeostasis_mod: float,
        efe_mod: float,
        safety_weight: float,
    ) -> UncertaintyReport:
        """
        Compute detailed uncertainty report with largest source identification.
        
        Returns:
            UncertaintyReport with component breakdown and recommendations
        """
        # Compute component uncertainties
        evidence_unc = self._compute_evidence_uncertainty()
        homeostasis_unc = self._compute_homeostasis_uncertainty()
        efe_unc = self._compute_efe_uncertainty()
        governor_unc = self._compute_governor_uncertainty()
        
        # Identify largest source
        sources = [
            (UncertaintySource.INSUFFICIENT_EVIDENCE, evidence_unc * 0.5),
            (UncertaintySource.WEAK_EVIDENCE, evidence_unc * 0.3),
            (UncertaintySource.HOMEOSTASIS_IMBALANCE, homeostasis_unc),
            (UncertaintySource.HIGH_AMBIGUITY, efe_unc * 0.4),
            (UncertaintySource.HIGH_RISK, efe_unc * 0.3),
            (UncertaintySource.GOVERNOR_CONSTRAINT, governor_unc),
        ]
        
        # Sort by contribution
        sources.sort(key=lambda x: x[1], reverse=True)
        
        largest_source = sources[0][0]
        largest_contribution = sources[0][1]
        
        # Secondary sources (excluding largest)
        secondary = sources[1:4]
        
        # Overall uncertainty (weighted combination)
        overall = (
            evidence_unc * 0.3 +
            homeostasis_unc * 0.25 +
            efe_unc * 0.25 +
            governor_unc * 0.2
        )
        
        # Generate recommendations
        recommendations = self._generate_uncertainty_recommendations(
            largest_source, evidence_unc, homeostasis_unc, efe_unc, governor_unc
        )
        
        return UncertaintyReport(
            overall_uncertainty=overall,
            largest_source=largest_source,
            source_contribution=largest_contribution,
            secondary_sources=secondary,
            evidence_uncertainty=evidence_unc,
            homeostasis_uncertainty=homeostasis_unc,
            efe_uncertainty=efe_unc,
            governor_uncertainty=governor_unc,
            recommendations=recommendations,
        )
    
    def _compute_evidence_uncertainty(self) -> float:
        """Compute uncertainty from evidence quality."""
        if not self.evidence:
            return 1.0
        
        # Factor 1: Count
        count_factor = max(0.0, 1.0 - len(self.evidence) / 10.0)
        
        # Factor 2: Strength
        avg_strength = sum(e.strength for e in self.evidence) / len(self.evidence)
        strength_factor = 1.0 - avg_strength
        
        # Factor 3: Variance
        values = [e.value for e in self.evidence]
        if len(values) > 1:
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            variance_factor = min(1.0, variance * 4)
        else:
            variance_factor = 0.5
        
        return (count_factor * 0.3 + strength_factor * 0.4 + variance_factor * 0.3)
    
    def _compute_homeostasis_uncertainty(self) -> float:
        """Compute uncertainty from homeostasis state."""
        if self._mvp11_context is None or self._mvp11_context.homeostasis is None:
            return 0.0
        
        homeostasis = self._mvp11_context.homeostasis
        
        if hasattr(homeostasis, 'to_dict'):
            state = homeostasis.to_dict()
        elif isinstance(homeostasis, dict):
            state = homeostasis
        else:
            return 0.0
        
        # Compute deviations from healthy values (0.75)
        deviations = []
        for dim in ['energy', 'safety', 'certainty']:
            value = state.get(dim, 0.5)
            deviation = abs(value - 0.75)
            deviations.append(deviation)
        
        return sum(deviations) / len(deviations) if deviations else 0.0
    
    def _compute_efe_uncertainty(self) -> float:
        """Compute uncertainty from EFE terms."""
        if self._mvp11_context is None or self._mvp11_context.efe_terms is None:
            return 0.0
        
        efe_terms = self._mvp11_context.efe_terms
        
        if isinstance(efe_terms, dict):
            terms = efe_terms
        else:
            terms = efe_terms.to_dict()
        
        # High risk + high ambiguity + low info_gain = high uncertainty
        risk = terms.get("risk", 0.5)
        ambiguity = terms.get("ambiguity", 0.5)
        info_gain = terms.get("info_gain", 0.5)
        
        return (risk * 0.4 + ambiguity * 0.4 + (1 - info_gain) * 0.2)
    
    def _compute_governor_uncertainty(self) -> float:
        """Compute uncertainty from governor constraints."""
        if self._mvp11_context is None:
            return 0.0
        
        # Destructive or blocked actions increase uncertainty
        if self._mvp11_context.is_destructive:
            return 0.8
        
        if self._mvp11_context.action_risk > 0.9:
            return 0.5
        
        return 0.0
    
    def _generate_uncertainty_recommendations(
        self,
        largest_source: UncertaintySource,
        evidence_unc: float,
        homeostasis_unc: float,
        efe_unc: float,
        governor_unc: float,
    ) -> List[str]:
        """Generate recommendations based on uncertainty analysis."""
        recommendations = []
        
        if largest_source == UncertaintySource.INSUFFICIENT_EVIDENCE:
            recommendations.append("Collect more evidence for reliable inference")
        
        elif largest_source == UncertaintySource.WEAK_EVIDENCE:
            recommendations.append("Strengthen existing evidence sources")
        
        elif largest_source == UncertaintySource.CONFLICTING_EVIDENCE:
            recommendations.append("Resolve conflicting evidence before proceeding")
        
        elif largest_source == UncertaintySource.MISSING_EVIDENCE_TYPE:
            recommendations.append("Gather evidence from missing categories")
        
        elif largest_source == UncertaintySource.HOMEOSTASIS_IMBALANCE:
            recommendations.append("Address homeostatic imbalance before action")
            if homeostasis_unc > 0.3:
                recommendations.append("Consider recovery actions to restore balance")
        
        elif largest_source == UncertaintySource.HIGH_AMBIGUITY:
            recommendations.append("Reduce ambiguity through information gathering")
        
        elif largest_source == UncertaintySource.HIGH_RISK:
            recommendations.append("Seek safer alternatives or mitigation strategies")
        
        elif largest_source == UncertaintySource.GOVERNOR_CONSTRAINT:
            recommendations.append("Action blocked by governor - review safety constraints")
        
        elif largest_source == UncertaintySource.LOW_INFORMATION_GAIN:
            recommendations.append("Seek actions with higher information value")
        
        elif largest_source == UncertaintySource.HIGH_COST:
            recommendations.append("Consider lower-cost alternatives")
        
        # Add secondary recommendations
        if evidence_unc > 0.5:
            recommendations.append("Improve evidence quality and coverage")
        
        if homeostasis_unc > 0.3:
            recommendations.append("Monitor homeostatic state during action")
        
        return recommendations[:5]  # Limit to 5 recommendations
    
    def _find_extreme_sources(self) -> Tuple[Optional[str], Optional[str]]:
        """Find weakest and strongest evidence sources."""
        if not self.evidence:
            return None, None
        
        type_scores: Dict[EvidenceType, float] = {}
        type_counts: Dict[EvidenceType, int] = {}
        
        for e in self.evidence:
            score = e.value * e.strength
            type_scores[e.evidence_type] = type_scores.get(e.evidence_type, 0) + score
            type_counts[e.evidence_type] = type_counts.get(e.evidence_type, 0) + 1
        
        avg_scores = {
            t: type_scores[t] / type_counts[t]
            for t in type_scores
        }
        
        if not avg_scores:
            return None, None
        
        sorted_types = sorted(avg_scores.items(), key=lambda x: x[1])
        
        weakest = sorted_types[0][0].value if sorted_types else None
        strongest = sorted_types[-1][0].value if sorted_types else None
        
        return weakest, strongest
    
    def get_uncertainty_report(self) -> UncertaintyReport:
        """
        Get detailed uncertainty report.
        
        Returns:
            UncertaintyReport with largest source identification
        """
        if self._last_uncertainty_report is not None:
            return self._last_uncertainty_report
        
        # Compute if not cached
        result = self.compute_posterior()
        return self._last_uncertainty_report
    
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
        self._mvp11_context = None
        self._last_result = None
        self._last_uncertainty_report = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize updater state."""
        result = {
            "prior": self.prior,
            "evidence_count": len(self.evidence),
            "evidence": [e.to_dict() for e in self.evidence],
            "evidence_types_present": list(set(
                e.evidence_type.value for e in self.evidence
            )),
            "mvp11_context": self._mvp11_context.to_dict() if self._mvp11_context else None,
        }
        
        if self._last_result is not None:
            result["last_result"] = self._last_result.to_dict()
        
        return result


# Convenience functions

def create_bayes_updater_v2(prior: float = 0.5) -> BayesUpdaterV2:
    """Factory function to create a BayesUpdaterV2."""
    return BayesUpdaterV2(prior=prior)


def aggregate_evidence_v2(
    evidence_items: List[Dict[str, Any]],
    prior: float = 0.5,
    homeostasis_state: Optional[Any] = None,
    efe_terms: Optional[Dict[str, float]] = None,
    governor_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to aggregate evidence with MVP11 context.
    
    Args:
        evidence_items: List of {type, value, strength} dicts
        prior: Prior probability
        homeostasis_state: HomeostasisState instance
        efe_terms: Dict with risk, ambiguity, info_gain, cost
        governor_context: Dict with action_risk, is_destructive, is_recovery
    
    Returns:
        Dict with posterior and uncertainty report
    """
    updater = create_bayes_updater_v2(prior=prior)
    
    # Set MVP11 context
    if homeostasis_state is not None:
        updater.set_homeostasis(homeostasis_state)
    
    if efe_terms is not None:
        updater.set_efe_terms(
            risk=efe_terms.get("risk", 0.5),
            ambiguity=efe_terms.get("ambiguity", 0.5),
            info_gain=efe_terms.get("info_gain", 0.5),
            cost=efe_terms.get("cost", 0.5),
        )
    
    if governor_context is not None:
        updater.set_governor_context(
            action_risk=governor_context.get("action_risk", 0.0),
            is_destructive=governor_context.get("is_destructive", False),
            is_recovery=governor_context.get("is_recovery", False),
        )
    
    # Add evidence
    for item in evidence_items:
        evidence_type = EvidenceType(item.get("type", "workspace"))
        value = item.get("value", 0.5)
        strength = item.get("strength", 0.5)
        notes = item.get("notes", "")
        
        updater.add_evidence(evidence_type, value, strength, notes)
    
    # Compute results
    result = updater.compute_posterior()
    uncertainty_report = updater.get_uncertainty_report()
    
    return {
        "bayes_result": result.to_dict(),
        "uncertainty_report": uncertainty_report.to_dict(),
    }
