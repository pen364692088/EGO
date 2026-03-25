"""
MVP-10 T24: Evidence Battery

Metrics for evaluating causal evidence of workspace broadcast, HOT,
valence, and continuity mechanisms.

Metrics:
- Workspace: broadcast_dependency, cross_module_access_score
- HOT: prediction_error↓, conflict_resolution_efficiency
- Valence: policy_sensitivity (initial valence change → action distribution diff)
- Continuity: commitment_completion, narrative_consistency

Output: evidence.json with all metrics and scores.
"""
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


class EvidenceCategory(Enum):
    """Categories of causal evidence."""
    WORKSPACE = "workspace"
    HOT = "hot"
    VALENCE = "valence"
    CONTINUITY = "continuity"


@dataclass
class MetricResult:
    """Result of a single metric computation."""
    metric_name: str
    category: EvidenceCategory
    value: float
    baseline_value: Optional[float] = None
    delta: Optional[float] = None
    direction: str = "neutral"  # "higher_better", "lower_better", "neutral"
    evidence_strength: float = 0.0  # 0.0 = no evidence, 1.0 = strong evidence
    notes: str = ""
    ts: float = field(default_factory=time.time)
    
    def compute_delta(self) -> float:
        """Compute delta from baseline."""
        if self.baseline_value is not None:
            self.delta = self.value - self.baseline_value
        return self.delta or 0.0
    
    def compute_evidence_strength(self) -> float:
        """Compute evidence strength based on delta and direction."""
        delta = self.compute_delta()
        
        if self.direction == "higher_better":
            if delta > 0:
                self.evidence_strength = min(1.0, abs(delta) / 0.5)
        elif self.direction == "lower_better":
            if delta < 0:
                self.evidence_strength = min(1.0, abs(delta) / 0.5)
        
        return self.evidence_strength
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "category": self.category.value,
            "value": round(self.value, 4),
            "baseline_value": round(self.baseline_value, 4) if self.baseline_value else None,
            "delta": round(self.delta, 4) if self.delta is not None else None,
            "direction": self.direction,
            "evidence_strength": round(self.evidence_strength, 4),
            "notes": self.notes,
            "ts": self.ts,
        }


@dataclass
class CategoryEvidence:
    """Evidence for a single category."""
    category: EvidenceCategory
    metrics: List[MetricResult] = field(default_factory=list)
    overall_score: float = 0.0
    
    def compute_overall_score(self) -> float:
        """Compute overall score for this category."""
        if not self.metrics:
            self.overall_score = 0.0
            return 0.0
        
        # Weighted average of evidence strengths
        total_strength = sum(m.evidence_strength for m in self.metrics)
        self.overall_score = total_strength / len(self.metrics)
        return self.overall_score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "metrics": [m.to_dict() for m in self.metrics],
            "overall_score": round(self.overall_score, 4),
        }


class WorkspaceEvidence:
    """
    Workspace-related evidence metrics.
    
    Metrics:
    - broadcast_dependency: How much tasks depend on broadcast
    - cross_module_access_score: Frequency of cross-module candidate access
    """
    
    @staticmethod
    def compute_broadcast_dependency(
        tasks_with_broadcast: List[Dict[str, Any]],
        tasks_without_broadcast: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute broadcast dependency metric.
        
        High dependency = performance drops significantly without broadcast.
        
        Args:
            tasks_with_broadcast: Results with broadcast enabled
            tasks_without_broadcast: Results with broadcast disabled
        
        Returns:
            MetricResult for broadcast dependency
        """
        success_with = sum(1 for t in tasks_with_broadcast if t.get("success", False))
        success_without = sum(1 for t in tasks_without_broadcast if t.get("success", False))
        
        rate_with = success_with / len(tasks_with_broadcast) if tasks_with_broadcast else 0
        rate_without = success_without / len(tasks_without_broadcast) if tasks_without_broadcast else 0
        
        dependency = rate_with - rate_without
        
        return MetricResult(
            metric_name="broadcast_dependency",
            category=EvidenceCategory.WORKSPACE,
            value=dependency,
            baseline_value=0.0,
            direction="higher_better",  # Higher = more evidence for broadcast
            notes=f"Success with broadcast: {rate_with:.2f}, without: {rate_without:.2f}",
        )
    
    @staticmethod
    def compute_cross_module_access_score(
        candidate_accesses: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute cross-module access score.
        
        Higher score = more cross-module coordination.
        
        Args:
            candidate_accesses: List of candidate access records
        
        Returns:
            MetricResult for cross-module access
        """
        if not candidate_accesses:
            return MetricResult(
                metric_name="cross_module_access_score",
                category=EvidenceCategory.WORKSPACE,
                value=0.0,
                notes="No candidate accesses recorded",
            )
        
        cross_module_count = sum(
            1 for a in candidate_accesses
            if a.get("source") != a.get("accessing_module")
        )
        
        score = cross_module_count / len(candidate_accesses)
        
        return MetricResult(
            metric_name="cross_module_access_score",
            category=EvidenceCategory.WORKSPACE,
            value=score,
            direction="higher_better",
            notes=f"{cross_module_count} cross-module accesses out of {len(candidate_accesses)}",
        )


class HOTEvidence:
    """
    HOT (Higher-Order Thought) related evidence metrics.
    
    Metrics:
    - prediction_error: Accuracy of predictions (lower = better HOT)
    - conflict_resolution_efficiency: How well conflicts are resolved
    """
    
    @staticmethod
    def compute_prediction_error(
        predictions: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute average prediction error.
        
        Lower error = better HOT calibration.
        
        Args:
            predictions: List of prediction records with 'error' field
        
        Returns:
            MetricResult for prediction error
        """
        if not predictions:
            return MetricResult(
                metric_name="prediction_error",
                category=EvidenceCategory.HOT,
                value=0.0,
                direction="lower_better",
                notes="No predictions recorded",
            )
        
        errors = [p.get("error", 0.0) for p in predictions if "error" in p]
        avg_error = sum(errors) / len(errors) if errors else 0.0
        
        return MetricResult(
            metric_name="prediction_error",
            category=EvidenceCategory.HOT,
            value=avg_error,
            baseline_value=0.5,  # Random baseline
            direction="lower_better",
            notes=f"Average error: {avg_error:.4f} over {len(errors)} predictions",
        )
    
    @staticmethod
    def compute_conflict_resolution_efficiency(
        conflict_events: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute conflict resolution efficiency.
        
        Higher = better at resolving conflicts (HOT working).
        
        Args:
            conflict_events: List of conflict events with 'resolved' field
        
        Returns:
            MetricResult for conflict resolution
        """
        if not conflict_events:
            return MetricResult(
                metric_name="conflict_resolution_efficiency",
                category=EvidenceCategory.HOT,
                value=1.0,  # No conflicts = perfect efficiency
                direction="higher_better",
                notes="No conflicts recorded",
            )
        
        resolved = sum(1 for e in conflict_events if e.get("resolved", False))
        efficiency = resolved / len(conflict_events)
        
        return MetricResult(
            metric_name="conflict_resolution_efficiency",
            category=EvidenceCategory.HOT,
            value=efficiency,
            direction="higher_better",
            notes=f"Resolved {resolved} out of {len(conflict_events)} conflicts",
        )


class ValenceEvidence:
    """
    Valence-related evidence metrics.
    
    Metrics:
    - policy_sensitivity: How much action distribution changes with valence
    """
    
    @staticmethod
    def compute_policy_sensitivity(
        valence_action_pairs: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute policy sensitivity to valence.
        
        Higher sensitivity = valence affects behavior more.
        
        Args:
            valence_action_pairs: List of {valence, action_distribution} pairs
        
        Returns:
            MetricResult for policy sensitivity
        """
        if len(valence_action_pairs) < 2:
            return MetricResult(
                metric_name="policy_sensitivity",
                category=EvidenceCategory.VALENCE,
                value=0.0,
                notes="Need at least 2 valence-action pairs",
            )
        
        # Group by valence sign
        positive_valence = [p for p in valence_action_pairs if p.get("valence", 0) > 0.3]
        negative_valence = [p for p in valence_action_pairs if p.get("valence", 0) < -0.3]
        
        if not positive_valence or not negative_valence:
            return MetricResult(
                metric_name="policy_sensitivity",
                category=EvidenceCategory.VALENCE,
                value=0.0,
                notes="Need both positive and negative valence samples",
            )
        
        # Compute average action distribution difference
        def avg_distribution(pairs: List[Dict[str, Any]]) -> Dict[str, float]:
            actions = {}
            for p in pairs:
                dist = p.get("action_distribution", {})
                for k, v in dist.items():
                    actions[k] = actions.get(k, 0) + v
            return {k: v / len(pairs) for k, v in actions.items()}
        
        pos_dist = avg_distribution(positive_valence)
        neg_dist = avg_distribution(negative_valence)
        
        # Compute KL-like divergence (simplified)
        all_actions = set(pos_dist.keys()) | set(neg_dist.keys())
        sensitivity = 0.0
        for action in all_actions:
            p = pos_dist.get(action, 0.01)
            q = neg_dist.get(action, 0.01)
            sensitivity += abs(p - q)
        
        sensitivity = min(1.0, sensitivity / 2)  # Normalize
        
        return MetricResult(
            metric_name="policy_sensitivity",
            category=EvidenceCategory.VALENCE,
            value=sensitivity,
            direction="higher_better",
            notes=f"Distribution difference between positive ({len(positive_valence)}) and negative ({len(negative_valence)}) valence",
        )


class ContinuityEvidence:
    """
    Continuity-related evidence metrics.
    
    Metrics:
    - commitment_completion: Rate of completing committed goals
    - narrative_consistency: Consistency of narrative over time
    """
    
    @staticmethod
    def compute_commitment_completion(
        commitments: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute commitment completion rate.
        
        Higher = better continuity and follow-through.
        
        Args:
            commitments: List of commitments with 'completed' field
        
        Returns:
            MetricResult for commitment completion
        """
        if not commitments:
            return MetricResult(
                metric_name="commitment_completion",
                category=EvidenceCategory.CONTINUITY,
                value=1.0,
                direction="higher_better",
                notes="No commitments recorded",
            )
        
        completed = sum(1 for c in commitments if c.get("completed", False))
        rate = completed / len(commitments)
        
        return MetricResult(
            metric_name="commitment_completion",
            category=EvidenceCategory.CONTINUITY,
            value=rate,
            direction="higher_better",
            notes=f"Completed {completed} out of {len(commitments)} commitments",
        )
    
    @staticmethod
    def compute_narrative_consistency(
        narrative_states: List[Dict[str, Any]],
    ) -> MetricResult:
        """
        Compute narrative consistency over time.
        
        Higher = more consistent narrative arc.
        
        Args:
            narrative_states: List of narrative state snapshots
        
        Returns:
            MetricResult for narrative consistency
        """
        if len(narrative_states) < 2:
            return MetricResult(
                metric_name="narrative_consistency",
                category=EvidenceCategory.CONTINUITY,
                value=1.0,
                direction="higher_better",
                notes="Need at least 2 narrative states",
            )
        
        # Compute state transition consistency
        consistencies = []
        for i in range(1, len(narrative_states)):
            prev = narrative_states[i - 1]
            curr = narrative_states[i]
            
            # Simple consistency: how many keys are unchanged
            prev_keys = set(prev.get("keys", []))
            curr_keys = set(curr.get("keys", []))
            
            if prev_keys:
                overlap = len(prev_keys & curr_keys) / len(prev_keys)
                consistencies.append(overlap)
        
        avg_consistency = sum(consistencies) / len(consistencies) if consistencies else 1.0
        
        return MetricResult(
            metric_name="narrative_consistency",
            category=EvidenceCategory.CONTINUITY,
            value=avg_consistency,
            direction="higher_better",
            notes=f"Average consistency: {avg_consistency:.4f}",
        )


class EvidenceBattery:
    """
    Battery of evidence metrics for causal testing.
    
    Collects and computes all metrics, outputs evidence.json.
    
    Usage:
        battery = EvidenceBattery()
        
        # Add data for each category
        battery.add_workspace_data(tasks_with, tasks_without, accesses)
        battery.add_hot_data(predictions, conflicts)
        battery.add_valence_data(valence_actions)
        battery.add_continuity_data(commitments, narratives)
        
        # Compute all metrics
        evidence = battery.compute_all()
        
        # Save to file
        battery.save("evidence.json")
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize evidence battery.
        
        Args:
            output_dir: Directory to save evidence.json
        """
        self.output_dir = Path(output_dir) if output_dir else None
        self.categories: Dict[EvidenceCategory, CategoryEvidence] = {
            cat: CategoryEvidence(category=cat) for cat in EvidenceCategory
        }
        
        # Raw data storage
        self._workspace_data: Dict[str, Any] = {}
        self._hot_data: Dict[str, Any] = {}
        self._valence_data: Dict[str, Any] = {}
        self._continuity_data: Dict[str, Any] = {}
    
    def add_workspace_data(
        self,
        tasks_with_broadcast: Optional[List[Dict[str, Any]]] = None,
        tasks_without_broadcast: Optional[List[Dict[str, Any]]] = None,
        candidate_accesses: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add workspace-related data."""
        if tasks_with_broadcast:
            self._workspace_data["tasks_with_broadcast"] = tasks_with_broadcast
        if tasks_without_broadcast:
            self._workspace_data["tasks_without_broadcast"] = tasks_without_broadcast
        if candidate_accesses:
            self._workspace_data["candidate_accesses"] = candidate_accesses
    
    def add_hot_data(
        self,
        predictions: Optional[List[Dict[str, Any]]] = None,
        conflict_events: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add HOT-related data."""
        if predictions:
            self._hot_data["predictions"] = predictions
        if conflict_events:
            self._hot_data["conflict_events"] = conflict_events
    
    def add_valence_data(
        self,
        valence_action_pairs: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add valence-related data."""
        if valence_action_pairs:
            self._valence_data["valence_action_pairs"] = valence_action_pairs
    
    def add_continuity_data(
        self,
        commitments: Optional[List[Dict[str, Any]]] = None,
        narrative_states: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add continuity-related data."""
        if commitments:
            self._continuity_data["commitments"] = commitments
        if narrative_states:
            self._continuity_data["narrative_states"] = narrative_states
    
    def compute_workspace_metrics(self) -> List[MetricResult]:
        """Compute all workspace metrics."""
        metrics = []
        
        # Broadcast dependency
        if "tasks_with_broadcast" in self._workspace_data and "tasks_without_broadcast" in self._workspace_data:
            m = WorkspaceEvidence.compute_broadcast_dependency(
                self._workspace_data["tasks_with_broadcast"],
                self._workspace_data["tasks_without_broadcast"],
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        # Cross-module access score
        if "candidate_accesses" in self._workspace_data:
            m = WorkspaceEvidence.compute_cross_module_access_score(
                self._workspace_data["candidate_accesses"],
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        self.categories[EvidenceCategory.WORKSPACE].metrics = metrics
        self.categories[EvidenceCategory.WORKSPACE].compute_overall_score()
        
        return metrics
    
    def compute_hot_metrics(self) -> List[MetricResult]:
        """Compute all HOT metrics."""
        metrics = []
        
        # Prediction error
        if "predictions" in self._hot_data:
            m = HOTEvidence.compute_prediction_error(self._hot_data["predictions"])
            m.compute_evidence_strength()
            metrics.append(m)
        
        # Conflict resolution efficiency
        if "conflict_events" in self._hot_data:
            m = HOTEvidence.compute_conflict_resolution_efficiency(
                self._hot_data["conflict_events"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        self.categories[EvidenceCategory.HOT].metrics = metrics
        self.categories[EvidenceCategory.HOT].compute_overall_score()
        
        return metrics
    
    def compute_valence_metrics(self) -> List[MetricResult]:
        """Compute all valence metrics."""
        metrics = []
        
        if "valence_action_pairs" in self._valence_data:
            m = ValenceEvidence.compute_policy_sensitivity(
                self._valence_data["valence_action_pairs"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        self.categories[EvidenceCategory.VALENCE].metrics = metrics
        self.categories[EvidenceCategory.VALENCE].compute_overall_score()
        
        return metrics
    
    def compute_continuity_metrics(self) -> List[MetricResult]:
        """Compute all continuity metrics."""
        metrics = []
        
        # Commitment completion
        if "commitments" in self._continuity_data:
            m = ContinuityEvidence.compute_commitment_completion(
                self._continuity_data["commitments"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        # Narrative consistency
        if "narrative_states" in self._continuity_data:
            m = ContinuityEvidence.compute_narrative_consistency(
                self._continuity_data["narrative_states"]
            )
            m.compute_evidence_strength()
            metrics.append(m)
        
        self.categories[EvidenceCategory.CONTINUITY].metrics = metrics
        self.categories[EvidenceCategory.CONTINUITY].compute_overall_score()
        
        return metrics
    
    def compute_all(self) -> Dict[str, Any]:
        """
        Compute all metrics and return evidence dict.
        
        Returns:
            Dict with all metrics and scores
        """
        self.compute_workspace_metrics()
        self.compute_hot_metrics()
        self.compute_valence_metrics()
        self.compute_continuity_metrics()
        
        # Overall evidence score
        overall_scores = [cat.overall_score for cat in self.categories.values()]
        overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
        
        return {
            "categories": {cat.category.value: cat.to_dict() for cat in self.categories.values()},
            "overall_evidence_score": round(overall, 4),
            "strongest_category": max(
                self.categories.values(),
                key=lambda c: c.overall_score
            ).category.value,
            "weakest_category": min(
                self.categories.values(),
                key=lambda c: c.overall_score
            ).category.value,
            "ts": time.time(),
        }
    
    def save(self, path: Optional[str] = None) -> str:
        """
        Save evidence to JSON file.
        
        Args:
            path: Path to save (default: output_dir/evidence.json)
        
        Returns:
            Path to saved file
        """
        evidence = self.compute_all()
        
        if path:
            save_path = Path(path)
        elif self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            save_path = self.output_dir / "evidence.json"
        else:
            save_path = Path("evidence.json")
        
        with open(save_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        
        return str(save_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize battery state."""
        return {
            "categories": {k.value: v.to_dict() for k, v in self.categories.items()},
            "data_counts": {
                "workspace": len(self._workspace_data),
                "hot": len(self._hot_data),
                "valence": len(self._valence_data),
                "continuity": len(self._continuity_data),
            },
        }


def create_evidence_battery(output_dir: Optional[str] = None) -> EvidenceBattery:
    """Factory function to create an evidence battery."""
    return EvidenceBattery(output_dir=output_dir)
