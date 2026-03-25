"""
MVP-11 T19: Evidence Battery v2

Extended metrics for evaluating causal evidence of homeostasis, EFE, and governor mechanisms.

New Metrics (v2):
- homeostasis_dependency_score: How much behavior depends on homeostasis state
- efe_explainability_score: How well decisions can be explained by EFE terms
- governor_safety_score: Governor effectiveness (interception_rate + false_interception_rate)

Reference: evidence_battery.py (MVP-10 T24)
"""
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

# Reuse base structures from evidence_battery
from .evidence_battery import (
    MetricResult,
    CategoryEvidence,
    EvidenceCategory as BaseEvidenceCategory,
)


class EvidenceCategoryV2(Enum):
    """Extended categories of causal evidence (v2)."""
    HOMEOSTASIS = "homeostasis"
    EFE = "efe"
    GOVERNOR = "governor"


@dataclass
class MetricResultV2(MetricResult):
    """Extended metric result with v2 fields."""
    # Inherits all fields from MetricResult
    # Additional metadata for v2 metrics
    formula: str = ""  # Mathematical formula or computation method
    confidence: float = 0.0  # Statistical confidence if available
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["formula"] = self.formula
        base["confidence"] = round(self.confidence, 4) if self.confidence else 0.0
        return base


@dataclass
class CategoryEvidenceV2(CategoryEvidence):
    """Evidence for a v2 category."""
    category: EvidenceCategoryV2
    metrics: List[MetricResultV2] = field(default_factory=list)


class HomeostasisEvidence:
    """
    Homeostasis-related evidence metrics.
    
    Metrics:
    - homeostasis_dependency_score: How much behavior depends on homeostasis state
    
    Interpretation:
    - High score: Behavior is strongly influenced by homeostatic state
    - Low score: Behavior is independent of homeostasis (concerning)
    
    Evidence for homeostasis: score > 0.3 with p < 0.05
    """
    
    @staticmethod
    def compute_homeostasis_dependency_score(
        behavior_records: List[Dict[str, Any]],
        homeostasis_states: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute how much behavior depends on homeostasis state.
        
        Method:
        1. Cluster behaviors by homeostasis state (high/medium/low drives)
        2. Measure distribution divergence between clusters
        3. Higher divergence = more dependency on homeostasis
        
        Args:
            behavior_records: List of {behavior_type, action, outcome} records
            homeostasis_states: List of {drive_level, timestamp} states
        
        Returns:
            MetricResultV2 for homeostasis dependency
        """
        if not behavior_records or not homeostasis_states:
            return MetricResultV2(
                metric_name="homeostasis_dependency_score",
                category=EvidenceCategoryV2.HOMEOSTASIS,
                value=0.0,
                formula="KL_divergence(P(behavior|high_drive) || P(behavior|low_drive))",
                notes="No data provided",
            )
        
        # Group behaviors by drive level
        high_drive_behaviors: List[str] = []
        low_drive_behaviors: List[str] = []
        
        # Assume homeostasis_states have 'drive_level' field (0-1)
        # High drive = > 0.6, Low drive = < 0.4
        for i, state in enumerate(homeostasis_states):
            if i >= len(behavior_records):
                break
            
            drive = state.get("drive_level", 0.5)
            behavior = behavior_records[i].get("behavior_type", "unknown")
            
            if drive > 0.6:
                high_drive_behaviors.append(behavior)
            elif drive < 0.4:
                low_drive_behaviors.append(behavior)
        
        if not high_drive_behaviors or not low_drive_behaviors:
            return MetricResultV2(
                metric_name="homeostasis_dependency_score",
                category=EvidenceCategoryV2.HOMEOSTASIS,
                value=0.0,
                formula="KL_divergence(P(behavior|high_drive) || P(behavior|low_drive))",
                notes="Insufficient data in high/low drive regimes",
            )
        
        # Compute behavior distributions
        def compute_distribution(behaviors: List[str]) -> Dict[str, float]:
            counts: Dict[str, int] = {}
            for b in behaviors:
                counts[b] = counts.get(b, 0) + 1
            total = len(behaviors)
            return {k: v / total for k, v in counts.items()}
        
        high_dist = compute_distribution(high_drive_behaviors)
        low_dist = compute_distribution(low_drive_behaviors)
        
        # Compute KL divergence (simplified Jensen-Shannon)
        all_behaviors = set(high_dist.keys()) | set(low_dist.keys())
        
        divergence = 0.0
        for behavior in all_behaviors:
            p = high_dist.get(behavior, 0.001)
            q = low_dist.get(behavior, 0.001)
            # Symmetric divergence
            divergence += abs(p - q)
        
        # Normalize to [0, 1]
        score = min(1.0, divergence / 2.0)
        
        return MetricResultV2(
            metric_name="homeostasis_dependency_score",
            category=EvidenceCategoryV2.HOMEOSTASIS,
            value=score,
            baseline_value=0.1,  # Minimum expected dependency
            direction="higher_better",
            formula="sum(|P(behavior|high_drive) - P(behavior|low_drive)|) / 2",
            notes=f"High drive samples: {len(high_drive_behaviors)}, Low drive: {len(low_drive_behaviors)}",
        )
    
    @staticmethod
    def compute_drive_sensitivity(
        intervention_records: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute sensitivity of behavior to drive interventions.
        
        Method:
        Compare behavior before/after drive modifications.
        
        Args:
            intervention_records: List of {before_drive, after_drive, behavior_change}
        
        Returns:
            MetricResultV2 for drive sensitivity
        """
        if not intervention_records:
            return MetricResultV2(
                metric_name="drive_sensitivity",
                category=EvidenceCategoryV2.HOMEOSTASIS,
                value=0.0,
                formula="mean(behavior_change / drive_change)",
                notes="No intervention records",
            )
        
        sensitivities = []
        for record in intervention_records:
            before_drive = record.get("before_drive", 0.5)
            after_drive = record.get("after_drive", 0.5)
            behavior_change = record.get("behavior_change", 0.0)
            
            drive_change = abs(after_drive - before_drive)
            if drive_change > 0.01:
                sensitivity = abs(behavior_change) / drive_change
                sensitivities.append(min(1.0, sensitivity))
        
        avg_sensitivity = sum(sensitivities) / len(sensitivities) if sensitivities else 0.0
        
        return MetricResultV2(
            metric_name="drive_sensitivity",
            category=EvidenceCategoryV2.HOMEOSTASIS,
            value=avg_sensitivity,
            baseline_value=0.3,
            direction="higher_better",
            formula="mean(|behavior_change| / |drive_change|)",
            notes=f"Computed from {len(sensitivities)} intervention records",
        )


class EFEEvidence:
    """
    EFE (Expected Free Energy) related evidence metrics.
    
    Metrics:
    - efe_explainability_score: How well decisions can be explained by EFE terms
    
    EFE Terms:
    - Pragmatic value: E_q[ln p(o|d)] - expected utility
    - Epistemic value: E_q[ln q(s|d)] - information gain
    - Risk: KL(q(o|d) || p(o)) - ambiguity/risk
    
    Interpretation:
    - High explainability: Decisions correlate strongly with EFE components
    - Low explainability: Decisions appear random or unexplained by EFE
    """
    
    @staticmethod
    def compute_efe_explainability_score(
        decision_records: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute how well decisions can be explained by EFE terms.
        
        Method:
        1. For each decision, compute EFE breakdown
        2. Measure correlation between EFE terms and chosen action
        3. Higher correlation = more explainable by EFE
        
        Args:
            decision_records: List of {
                action_chosen: str,
                efe_terms: {
                    pragmatic: float,
                    epistemic: float,
                    risk: float,
                    total: float
                },
                alternative_actions: List[str]
            }
        
        Returns:
            MetricResultV2 for EFE explainability
        """
        if not decision_records:
            return MetricResultV2(
                metric_name="efe_explainability_score",
                category=EvidenceCategoryV2.EFE,
                value=0.0,
                formula="correlation(chosen_action_efe_rank, actual_choice)",
                notes="No decision records",
            )
        
        explained_count = 0
        total_variance_explained = 0.0
        
        for record in decision_records:
            efe_terms = record.get("efe_terms", {})
            action_chosen = record.get("action_chosen")
            alternatives = record.get("alternative_actions", [])
            
            # Check if chosen action has highest total EFE
            total_efe = efe_terms.get("total", 0.0)
            
            # Compare with alternatives (if provided with their EFE values)
            alternative_efes = record.get("alternative_efes", {})
            max_alternative = max(alternative_efes.values()) if alternative_efes else 0.0
            
            # Chosen action should have highest EFE
            if total_efe >= max_alternative:
                explained_count += 1
            
            # Variance explained by EFE components
            pragmatic = efe_terms.get("pragmatic", 0.0)
            epistemic = efe_terms.get("epistemic", 0.0)
            
            # Simple variance measure: how much of decision is explained
            if total_efe > 0:
                variance_explained = abs(pragmatic + epistemic) / (abs(total_efe) + 0.01)
                total_variance_explained += min(1.0, variance_explained)
        
        # Compute explainability score
        consistency = explained_count / len(decision_records) if decision_records else 0.0
        avg_variance = total_variance_explained / len(decision_records) if decision_records else 0.0
        
        # Combine consistency and variance explained
        score = 0.5 * consistency + 0.5 * avg_variance
        
        return MetricResultV2(
            metric_name="efe_explainability_score",
            category=EvidenceCategoryV2.EFE,
            value=score,
            baseline_value=0.5,  # Random would be ~0.5
            direction="higher_better",
            formula="0.5 * (chosen_is_max_efe / total) + 0.5 * mean(variance_explained)",
            notes=f"Consistency: {consistency:.2f}, Variance explained: {avg_variance:.2f}",
        )
    
    @staticmethod
    def compute_epistemic_vs_pragmatic_balance(
        decision_records: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute balance between epistemic and pragmatic value in decisions.
        
        Method:
        Measure relative contribution of epistemic vs pragmatic terms.
        
        Args:
            decision_records: List with efe_terms
        
        Returns:
            MetricResultV2 for epistemic/pragmatic balance
        """
        if not decision_records:
            return MetricResultV2(
                metric_name="epistemic_pragmatic_balance",
                category=EvidenceCategoryV2.EFE,
                value=0.5,  # Balanced by default
                formula="mean(epistemic / (epistemic + pragmatic))",
                notes="No decision records",
            )
        
        balances = []
        for record in decision_records:
            efe = record.get("efe_terms", {})
            epistemic = abs(efe.get("epistemic", 0.0))
            pragmatic = abs(efe.get("pragmatic", 0.0))
            
            total = epistemic + pragmatic
            if total > 0:
                # 0.5 = perfectly balanced, 0 = all pragmatic, 1 = all epistemic
                balance = epistemic / total
                balances.append(balance)
        
        avg_balance = sum(balances) / len(balances) if balances else 0.5
        
        return MetricResultV2(
            metric_name="epistemic_pragmatic_balance",
            category=EvidenceCategoryV2.EFE,
            value=avg_balance,
            direction="neutral",  # Balance itself is neutral
            formula="mean(epistemic / (epistemic + pragmatic))",
            notes=f"Epistemic weight: {avg_balance:.2f}, Pragmatic weight: {1-avg_balance:.2f}",
        )


class GovernorEvidence:
    """
    Governor-related evidence metrics.
    
    Metrics:
    - governor_safety_score: Governor effectiveness
    
    Components:
    - interception_rate: How often governor catches unsafe actions
    - false_interception_rate: How often governor incorrectly blocks safe actions
    - response_time: How quickly governor responds
    
    Interpretation:
    - High score: Governor catches real threats, doesn't over-block
    - Low score: Either missing threats (low interception) or blocking too much (high false rate)
    """
    
    @staticmethod
    def compute_governor_safety_score(
        governor_events: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute governor effectiveness score.
        
        Formula:
        score = interception_rate * (1 - false_interception_rate)
        
        Perfect score = 1.0 (catch all threats, no false positives)
        Zero score = either missing all threats or blocking everything
        
        Args:
            governor_events: List of {
                action: str,
                was_unsafe: bool,
                was_blocked: bool,
                should_have_blocked: bool  # ground truth
            }
        
        Returns:
            MetricResultV2 for governor safety
        """
        if not governor_events:
            return MetricResultV2(
                metric_name="governor_safety_score",
                category=EvidenceCategoryV2.GOVERNOR,
                value=0.0,
                formula="interception_rate * (1 - false_interception_rate)",
                notes="No governor events",
            )
        
        # Count categories
        true_positives = 0   # Should block, did block
        false_negatives = 0  # Should block, didn't block
        false_positives = 0  # Shouldn't block, did block
        true_negatives = 0   # Shouldn't block, didn't block
        
        for event in governor_events:
            should_block = event.get("should_have_blocked", False)
            did_block = event.get("was_blocked", False)
            
            if should_block and did_block:
                true_positives += 1
            elif should_block and not did_block:
                false_negatives += 1
            elif not should_block and did_block:
                false_positives += 1
            else:
                true_negatives += 1
        
        # Compute rates
        total_should_block = true_positives + false_negatives
        total_shouldnt_block = true_negatives + false_positives
        
        interception_rate = true_positives / total_should_block if total_should_block > 0 else 1.0
        false_interception_rate = false_positives / total_shouldnt_block if total_shouldnt_block > 0 else 0.0
        
        # Governor safety score
        safety_score = interception_rate * (1 - false_interception_rate)
        
        # Also compute F1 for reference
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 1.0
        recall = interception_rate
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return MetricResultV2(
            metric_name="governor_safety_score",
            category=EvidenceCategoryV2.GOVERNOR,
            value=safety_score,
            baseline_value=0.8,  # Expect at least 80% effectiveness
            direction="higher_better",
            formula="interception_rate * (1 - false_interception_rate)",
            confidence=f1,  # Use F1 as confidence measure
            notes=f"TP:{true_positives} FN:{false_negatives} FP:{false_positives} TN:{true_negatives} | interception:{interception_rate:.2f} false_rate:{false_interception_rate:.2f}",
        )
    
    @staticmethod
    def compute_interception_rate(
        governor_events: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute raw interception rate.
        
        Args:
            governor_events: List with should_have_blocked and was_blocked
        
        Returns:
            MetricResultV2 for interception rate
        """
        if not governor_events:
            return MetricResultV2(
                metric_name="interception_rate",
                category=EvidenceCategoryV2.GOVERNOR,
                value=0.0,
                formula="TP / (TP + FN)",
                notes="No events",
            )
        
        true_positives = sum(
            1 for e in governor_events
            if e.get("should_have_blocked") and e.get("was_blocked")
        )
        total_should_block = sum(
            1 for e in governor_events
            if e.get("should_have_blocked")
        )
        
        rate = true_positives / total_should_block if total_should_block > 0 else 1.0
        
        return MetricResultV2(
            metric_name="interception_rate",
            category=EvidenceCategoryV2.GOVERNOR,
            value=rate,
            baseline_value=0.9,  # Expect 90%+ interception
            direction="higher_better",
            formula="TP / (TP + FN)",
            notes=f"{true_positives} intercepted out of {total_should_block} threats",
        )
    
    @staticmethod
    def compute_false_interception_rate(
        governor_events: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute false interception rate (false positive rate).
        
        Args:
            governor_events: List with should_have_blocked and was_blocked
        
        Returns:
            MetricResultV2 for false interception rate
        """
        if not governor_events:
            return MetricResultV2(
                metric_name="false_interception_rate",
                category=EvidenceCategoryV2.GOVERNOR,
                value=0.0,
                formula="FP / (FP + TN)",
                notes="No events",
            )
        
        false_positives = sum(
            1 for e in governor_events
            if not e.get("should_have_blocked") and e.get("was_blocked")
        )
        total_safe = sum(
            1 for e in governor_events
            if not e.get("should_have_blocked")
        )
        
        rate = false_positives / total_safe if total_safe > 0 else 0.0
        
        return MetricResultV2(
            metric_name="false_interception_rate",
            category=EvidenceCategoryV2.GOVERNOR,
            value=rate,
            baseline_value=0.05,  # Expect < 5% false positive
            direction="lower_better",  # Lower is better!
            formula="FP / (FP + TN)",
            notes=f"{false_positives} false positives out of {total_safe} safe actions",
        )
    
    @staticmethod
    def compute_governor_response_time(
        governor_events: List[Dict[str, Any]],
    ) -> MetricResultV2:
        """
        Compute average governor response time.
        
        Args:
            governor_events: List with response_time_ms field
        
        Returns:
            MetricResultV2 for response time
        """
        if not governor_events:
            return MetricResultV2(
                metric_name="governor_response_time_ms",
                category=EvidenceCategoryV2.GOVERNOR,
                value=0.0,
                formula="mean(response_time_ms)",
                notes="No events",
            )
        
        times = [e.get("response_time_ms", 0) for e in governor_events if "response_time_ms" in e]
        
        if not times:
            return MetricResultV2(
                metric_name="governor_response_time_ms",
                category=EvidenceCategoryV2.GOVERNOR,
                value=0.0,
                formula="mean(response_time_ms)",
                notes="No response times recorded",
            )
        
        avg_time = sum(times) / len(times)
        
        return MetricResultV2(
            metric_name="governor_response_time_ms",
            category=EvidenceCategoryV2.GOVERNOR,
            value=avg_time,
            baseline_value=100.0,  # Expect < 100ms
            direction="lower_better",
            formula="mean(response_time_ms)",
            notes=f"Average: {avg_time:.1f}ms over {len(times)} events",
        )


class EvidenceBatteryV2:
    """
    Battery of evidence metrics for causal testing (v2).
    
    Extended metrics for MVP-11:
    - Homeostasis evidence
    - EFE evidence  
    - Governor evidence
    
    Usage:
        battery = EvidenceBatteryV2()
        
        # Add data
        battery.add_homeostasis_data(behaviors, states)
        battery.add_efe_data(decisions)
        battery.add_governor_data(events)
        
        # Compute all metrics
        evidence = battery.compute_all()
        
        # Save to file
        battery.save("evidence_v2.json")
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize evidence battery v2.
        
        Args:
            output_dir: Directory to save evidence_v2.json
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.categories: Dict[EvidenceCategoryV2, CategoryEvidenceV2] = {
            cat: CategoryEvidenceV2(category=cat) for cat in EvidenceCategoryV2
        }
        
        # Raw data storage
        self._homeostasis_data: Dict[str, Any] = {}
        self._efe_data: Dict[str, Any] = {}
        self._governor_data: Dict[str, Any] = {}
    
    def add_homeostasis_data(
        self,
        behavior_records: Optional[List[Dict[str, Any]]] = None,
        homeostasis_states: Optional[List[Dict[str, Any]]] = None,
        intervention_records: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add homeostasis-related data."""
        if behavior_records:
            self._homeostasis_data["behavior_records"] = behavior_records
        if homeostasis_states:
            self._homeostasis_data["homeostasis_states"] = homeostasis_states
        if intervention_records:
            self._homeostasis_data["intervention_records"] = intervention_records
    
    def add_efe_data(
        self,
        decision_records: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add EFE-related data."""
        if decision_records:
            self._efe_data["decision_records"] = decision_records
    
    def add_governor_data(
        self,
        governor_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add governor-related data."""
        if governor_events:
            self._governor_data["governor_events"] = governor_events
    
    def compute_homeostasis_metrics(self) -> List[MetricResultV2]:
        """Compute all homeostasis metrics."""
        metrics = []
        
        # Homeostasis dependency score
        if "behavior_records" in self._homeostasis_data and "homeostasis_states" in self._homeostasis_data:
            m = HomeostasisEvidence.compute_homeostasis_dependency_score(
                self._homeostasis_data["behavior_records"],
                self._homeostasis_data["homeostasis_states"],
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        # Drive sensitivity
        if "intervention_records" in self._homeostasis_data:
            m = HomeostasisEvidence.compute_drive_sensitivity(
                self._homeostasis_data["intervention_records"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        self.categories[EvidenceCategoryV2.HOMEOSTASIS].metrics = metrics
        self.categories[EvidenceCategoryV2.HOMEOSTASIS].compute_overall_score()
        
        return metrics
    
    def compute_efe_metrics(self) -> List[MetricResultV2]:
        """Compute all EFE metrics."""
        metrics = []
        
        if "decision_records" in self._efe_data:
            # EFE explainability score
            m = EFEEvidence.compute_efe_explainability_score(
                self._efe_data["decision_records"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
            
            # Epistemic/pragmatic balance
            m2 = EFEEvidence.compute_epistemic_vs_pragmatic_balance(
                self._efe_data["decision_records"]
            )
            metrics.append(m2)
        
        self.categories[EvidenceCategoryV2.EFE].metrics = metrics
        self.categories[EvidenceCategoryV2.EFE].compute_overall_score()
        
        return metrics
    
    def compute_governor_metrics(self) -> List[MetricResultV2]:
        """Compute all governor metrics."""
        metrics = []
        
        if "governor_events" in self._governor_data:
            events = self._governor_data["governor_events"]
            
            # Governor safety score (main metric)
            m = GovernorEvidence.compute_governor_safety_score(events)
            m.compute_evidence_strength()
            metrics.append(m)
            
            # Interception rate
            m2 = GovernorEvidence.compute_interception_rate(events)
            m2.compute_evidence_strength()
            metrics.append(m2)
            
            # False interception rate
            m3 = GovernorEvidence.compute_false_interception_rate(events)
            m3.compute_evidence_strength()
            metrics.append(m3)
            
            # Response time (if available)
            if any("response_time_ms" in e for e in events):
                m4 = GovernorEvidence.compute_governor_response_time(events)
                metrics.append(m4)
        
        self.categories[EvidenceCategoryV2.GOVERNOR].metrics = metrics
        self.categories[EvidenceCategoryV2.GOVERNOR].compute_overall_score()
        
        return metrics
    
    def compute_all(self) -> Dict[str, Any]:
        """
        Compute all metrics and return evidence dict.
        
        Returns:
            Dict with all metrics and scores
        """
        self.compute_homeostasis_metrics()
        self.compute_efe_metrics()
        self.compute_governor_metrics()
        
        # Overall evidence score
        overall_scores = [cat.overall_score for cat in self.categories.values()]
        overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
        
        # Find strongest and weakest
        sorted_cats = sorted(
            self.categories.values(),
            key=lambda c: c.overall_score,
            reverse=True
        )
        
        return {
            "version": "v2",
            "categories": {
                cat.category.value: cat.to_dict() 
                for cat in self.categories.values()
            },
            "overall_evidence_score": round(overall, 4),
            "strongest_category": sorted_cats[0].category.value if sorted_cats else "none",
            "weakest_category": sorted_cats[-1].category.value if sorted_cats else "none",
            "ts": time.time(),
        }
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save evidence to JSON file.
        
        Args:
            path: Path to save (default: output_dir/evidence_v2.json)
        
        Returns:
            Path to saved file
        """
        evidence = self.compute_all()
        
        if path:
            save_path = Path(path)
        elif self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            save_path = self.output_dir / "evidence_v2.json"
        else:
            save_path = Path("evidence_v2.json")
        
        with open(save_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        
        return str(save_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize battery state."""
        return {
            "version": "v2",
            "categories": {
                k.value: v.to_dict() 
                for k, v in self.categories.items()
            },
            "data_counts": {
                "homeostasis": len(self._homeostasis_data),
                "efe": len(self._efe_data),
                "governor": len(self._governor_data),
            },
        }


def create_evidence_battery_v2(output_dir: Optional[str] = None) -> EvidenceBatteryV2:
    """Factory function to create an evidence battery v2."""
    return EvidenceBatteryV2(output_dir=output_dir)


# Convenience exports
__all__ = [
    "EvidenceCategoryV2",
    "MetricResultV2",
    "CategoryEvidenceV2",
    "HomeostasisEvidence",
    "EFEEvidence",
    "GovernorEvidence",
    "EvidenceBatteryV2",
    "create_evidence_battery_v2",
]
