"""
MVP-10 T16: Outcome Attribution Module

Attributes failures to actionable causes that can update learning signals.
Attribution categories:
- knowledge_gap: Missing information needed to succeed
- planning_bug: Plan was flawed (wrong steps, wrong order, missing steps)
- execution_bug: Plan was good but execution failed
- external_constraint: External factors prevented success

All attributions must update capability stats and strategy preferences.
"""
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math


class AttributionCategory(Enum):
    """Categories for failure attribution."""
    KNOWLEDGE_GAP = "knowledge_gap"
    PLANNING_BUG = "planning_bug"
    EXECUTION_BUG = "execution_bug"
    EXTERNAL_CONSTRAINT = "external_constraint"


@dataclass
class AttributionResult:
    """
    Result of an attribution analysis.
    
    Records what caused the failure and what should be updated.
    """
    category: AttributionCategory
    confidence: float  # How confident in this attribution [0, 1]
    affected_capabilities: List[str]  # Which capabilities were involved
    strategy_adjustments: Dict[str, float]  # Strategy preference adjustments
    evidence: Dict[str, Any]  # Evidence supporting this attribution
    suggested_action: str  # What to do differently
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": round(self.confidence, 4),
            "affected_capabilities": self.affected_capabilities,
            "strategy_adjustments": self.strategy_adjustments,
            "evidence": self.evidence,
            "suggested_action": self.suggested_action,
            "ts": self.ts,
        }


@dataclass
class CapabilityStats:
    """
    Statistics for a single capability.
    
    Tracks success rate, confidence, and sample count.
    """
    name: str
    success_count: int = 0
    failure_count: int = 0
    total_attempts: int = 0
    confidence: float = 0.5
    last_updated: float = field(default_factory=time.time)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_attempts == 0:
            return 0.5  # Default when no data
        return self.success_count / self.total_attempts
    
    def record_outcome(self, success: bool, weight: float = 1.0) -> None:
        """Record an outcome and update stats."""
        self.total_attempts += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        # Update confidence using Bayesian-like update
        # Prior confidence is weighted by sample count
        prior_weight = min(1.0, self.total_attempts / 10.0)  # Ramp up over 10 samples
        
        # New observation
        observation = 1.0 if success else 0.0
        
        # Blend: more samples = less impact per sample
        alpha = 1.0 - prior_weight * 0.9  # Range 1.0 to 0.1
        self.confidence = self.confidence * (1 - alpha) + observation * alpha
        
        self.last_updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "total_attempts": self.total_attempts,
            "success_rate": round(self.success_rate, 4),
            "confidence": round(self.confidence, 4),
            "last_updated": self.last_updated,
        }


class OutcomeAttributor:
    """
    T16: Outcome Attribution for MVP-10.
    
    Analyzes failures and attributes them to actionable causes.
    Updates capability stats and strategy preferences.
    
    Usage:
        attributor = OutcomeAttributor()
        
        # Analyze a failure
        result = attributor.attribute(
            plan={"steps": [...]},
            execution_log=[...],
            outcome={"status": "fail", "reason": "..."},
        )
        
        # Apply updates to capabilities
        attributor.apply_capability_updates(result)
    """
    
    # Weights for attribution scoring
    KNOWLEDGE_GAP_INDICATORS = {
        "missing_info": 0.8,
        "unclear_context": 0.7,
        "unknown_dependency": 0.75,
        "insufficient_data": 0.85,
    }
    
    PLANNING_BUG_INDICATORS = {
        "wrong_step": 0.85,
        "missing_step": 0.8,
        "wrong_order": 0.75,
        "invalid_assumption": 0.7,
    }
    
    EXECUTION_BUG_INDICATORS = {
        "step_failed": 0.8,
        "timeout": 0.6,
        "resource_unavailable": 0.5,
        "wrong_parameters": 0.75,
    }
    
    EXTERNAL_CONSTRAINT_INDICATORS = {
        "external_error": 0.85,
        "system_down": 0.9,
        "permission_denied": 0.8,
        "resource_limit": 0.75,
    }
    
    def __init__(self):
        """Initialize the outcome attributor."""
        self.capability_stats: Dict[str, CapabilityStats] = {}
        self.strategy_preferences: Dict[str, float] = {}
        self.attribution_history: List[AttributionResult] = []
        self._initialize_default_capabilities()
    
    def _initialize_default_capabilities(self) -> None:
        """Initialize default capability tracking."""
        default_capabilities = [
            "seek_info",
            "attempt_solution",
            "run_check",
            "apply_fix",
            "commit_progress",
            "plan_generation",
            "validation",
        ]
        
        for cap in default_capabilities:
            self.capability_stats[cap] = CapabilityStats(name=cap)
    
    def attribute(
        self,
        plan: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        outcome: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AttributionResult:
        """
        Analyze a failure and determine its cause.
        
        Args:
            plan: The plan that was executed
            execution_log: Log of execution steps
            outcome: Final outcome with status and reason
            context: Additional context (optional)
        
        Returns:
            AttributionResult with category, confidence, and updates
        """
        context = context or {}
        
        # Skip if outcome was successful
        if outcome.get("status") == "success":
            # Record success for involved capabilities
            involved = self._extract_involved_capabilities(plan, execution_log)
            for cap in involved:
                if cap in self.capability_stats:
                    self.capability_stats[cap].record_outcome(success=True)
            
            # Return empty attribution for success
            return AttributionResult(
                category=AttributionCategory.EXTERNAL_CONSTRAINT,  # Placeholder
                confidence=0.0,
                affected_capabilities=involved,
                strategy_adjustments={},
                evidence={"success": True},
                suggested_action="No action needed - success",
            )
        
        # Analyze failure
        reason = outcome.get("reason", "").lower()
        failure_step = self._find_failure_step(execution_log)
        
        # Score each category
        scores = self._score_attribution_categories(
            reason=reason,
            plan=plan,
            execution_log=execution_log,
            failure_step=failure_step,
            context=context,
        )
        
        # Select highest scoring category
        best_category = max(scores, key=scores.get)
        confidence = scores[best_category]
        
        # Extract affected capabilities
        affected = self._extract_affected_capabilities(
            category=best_category,
            plan=plan,
            execution_log=execution_log,
            failure_step=failure_step,
        )
        
        # Generate strategy adjustments
        adjustments = self._generate_strategy_adjustments(
            category=best_category,
            affected_capabilities=affected,
            confidence=confidence,
        )
        
        # Generate suggested action
        suggested = self._generate_suggested_action(
            category=best_category,
            reason=reason,
            affected=affected,
        )
        
        # Build evidence
        evidence = {
            "failure_reason": reason,
            "failure_step": failure_step,
            "plan_steps": len(plan.get("steps", [])),
            "executed_steps": len(execution_log),
            "scores": {k.value: round(v, 4) for k, v in scores.items()},
        }
        
        result = AttributionResult(
            category=best_category,
            confidence=confidence,
            affected_capabilities=affected,
            strategy_adjustments=adjustments,
            evidence=evidence,
            suggested_action=suggested,
        )
        
        # Record in history
        self.attribution_history.append(result)
        
        # Record failure for capabilities
        for cap in affected:
            if cap in self.capability_stats:
                self.capability_stats[cap].record_outcome(success=False)
        
        return result
    
    def _score_attribution_categories(
        self,
        reason: str,
        plan: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        failure_step: Optional[int],
        context: Dict[str, Any],
    ) -> Dict[AttributionCategory, float]:
        """Score each attribution category based on evidence."""
        scores = {
            AttributionCategory.KNOWLEDGE_GAP: 0.0,
            AttributionCategory.PLANNING_BUG: 0.0,
            AttributionCategory.EXECUTION_BUG: 0.0,
            AttributionCategory.EXTERNAL_CONSTRAINT: 0.0,
        }
        
        # Check for knowledge gap indicators
        for indicator, weight in self.KNOWLEDGE_GAP_INDICATORS.items():
            if indicator in reason:
                scores[AttributionCategory.KNOWLEDGE_GAP] = max(
                    scores[AttributionCategory.KNOWLEDGE_GAP], weight
                )
        
        # Check for planning bug indicators
        for indicator, weight in self.PLANNING_BUG_INDICATORS.items():
            if indicator in reason:
                scores[AttributionCategory.PLANNING_BUG] = max(
                    scores[AttributionCategory.PLANNING_BUG], weight
                )
        
        # Check for execution bug indicators
        for indicator, weight in self.EXECUTION_BUG_INDICATORS.items():
            if indicator in reason:
                scores[AttributionCategory.EXECUTION_BUG] = max(
                    scores[AttributionCategory.EXECUTION_BUG], weight
                )
        
        # Check for external constraint indicators
        for indicator, weight in self.EXTERNAL_CONSTRAINT_INDICATORS.items():
            if indicator in reason:
                scores[AttributionCategory.EXTERNAL_CONSTRAINT] = max(
                    scores[AttributionCategory.EXTERNAL_CONSTRAINT], weight
                )
        
        # Additional heuristics based on execution log
        if failure_step is not None:
            total_steps = len(plan.get("steps", []))
            if total_steps > 0:
                failure_position = failure_step / total_steps
                
                # Early failure might indicate planning issue
                if failure_position < 0.3:
                    scores[AttributionCategory.PLANNING_BUG] = max(
                        scores[AttributionCategory.PLANNING_BUG], 0.6
                    )
                
                # Late failure might indicate execution issue
                if failure_position > 0.7:
                    scores[AttributionCategory.EXECUTION_BUG] = max(
                        scores[AttributionCategory.EXECUTION_BUG], 0.5
                    )
        
        # Check for plan validity
        if not plan.get("steps"):
            scores[AttributionCategory.PLANNING_BUG] = max(
                scores[AttributionCategory.PLANNING_BUG], 0.9
            )
        
        # Default to external constraint if no strong signals
        max_score = max(scores.values())
        if max_score < 0.3:
            scores[AttributionCategory.EXTERNAL_CONSTRAINT] = 0.5
        
        return scores
    
    def _find_failure_step(self, execution_log: List[Dict[str, Any]]) -> Optional[int]:
        """Find which step failed in the execution log."""
        for i, entry in enumerate(execution_log):
            if entry.get("status") == "fail":
                return i
        return None
    
    def _extract_involved_capabilities(
        self,
        plan: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
    ) -> List[str]:
        """Extract capabilities involved in the plan/execution."""
        capabilities = set()
        
        # From plan steps
        for step in plan.get("steps", []):
            action = step.get("action", "")
            if action:
                capabilities.add(action)
        
        # From execution log
        for entry in execution_log:
            action = entry.get("action", "")
            if action:
                capabilities.add(action)
        
        return list(capabilities)
    
    def _extract_affected_capabilities(
        self,
        category: AttributionCategory,
        plan: Dict[str, Any],
        execution_log: List[Dict[str, Any]],
        failure_step: Optional[int],
    ) -> List[str]:
        """Extract capabilities affected by this failure."""
        capabilities = set()
        
        if category == AttributionCategory.PLANNING_BUG:
            # Planning bugs affect plan_generation
            capabilities.add("plan_generation")
            capabilities.add("validation")
        elif category == AttributionCategory.EXECUTION_BUG:
            # Execution bugs affect the specific failed action
            if failure_step is not None and execution_log:
                if failure_step < len(execution_log):
                    action = execution_log[failure_step].get("action", "")
                    if action:
                        capabilities.add(action)
        elif category == AttributionCategory.KNOWLEDGE_GAP:
            # Knowledge gaps affect seek_info
            capabilities.add("seek_info")
        else:
            # External constraints - no capability to blame
            pass
        
        # Also add capabilities from plan
        capabilities.update(self._extract_involved_capabilities(plan, execution_log))
        
        return list(capabilities)
    
    def _generate_strategy_adjustments(
        self,
        category: AttributionCategory,
        affected_capabilities: List[str],
        confidence: float,
    ) -> Dict[str, float]:
        """Generate strategy preference adjustments."""
        adjustments = {}
        
        # Base adjustment magnitude
        magnitude = confidence * 0.1  # Max 10% adjustment
        
        if category == AttributionCategory.KNOWLEDGE_GAP:
            adjustments["seek_info_priority"] = magnitude
            adjustments["exploration_temp"] = magnitude * 0.5
        
        elif category == AttributionCategory.PLANNING_BUG:
            adjustments["plan_validation_strength"] = magnitude
            adjustments["alternative_plan_count"] = magnitude * 0.5
        
        elif category == AttributionCategory.EXECUTION_BUG:
            adjustments["execution_care"] = magnitude
            adjustments["retry_count"] = magnitude * 0.5
        
        elif category == AttributionCategory.EXTERNAL_CONSTRAINT:
            adjustments["external_retry_delay"] = magnitude
            adjustments["fallback_enabled"] = magnitude * 0.5
        
        return adjustments
    
    def _generate_suggested_action(
        self,
        category: AttributionCategory,
        reason: str,
        affected: List[str],
    ) -> str:
        """Generate a suggested action based on attribution."""
        if category == AttributionCategory.KNOWLEDGE_GAP:
            return f"Gather more information before proceeding. Issue: {reason}"
        elif category == AttributionCategory.PLANNING_BUG:
            return f"Revise plan with additional validation. Issue: {reason}"
        elif category == AttributionCategory.EXECUTION_BUG:
            return f"Review execution approach for {', '.join(affected)}. Issue: {reason}"
        else:
            return f"Wait or use fallback strategy. External issue: {reason}"
    
    def apply_strategy_updates(self, result: AttributionResult) -> None:
        """Apply strategy preference updates from an attribution."""
        for key, adjustment in result.strategy_adjustments.items():
            current = self.strategy_preferences.get(key, 0.5)
            # Gradual adjustment with momentum
            new_value = current * 0.9 + adjustment * 0.1
            self.strategy_preferences[key] = max(0.0, min(1.0, new_value))
    
    def get_capability_stats(self, name: str) -> Optional[CapabilityStats]:
        """Get stats for a specific capability."""
        return self.capability_stats.get(name)
    
    def get_all_capability_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get all capability stats."""
        return {name: stats.to_dict() for name, stats in self.capability_stats.items()}
    
    def get_strategy_preferences(self) -> Dict[str, float]:
        """Get current strategy preferences."""
        return self.strategy_preferences.copy()
    
    def get_attribution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent attribution history."""
        recent = self.attribution_history[-limit:]
        return [r.to_dict() for r in recent]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize attributor state."""
        return {
            "capability_stats": self.get_all_capability_stats(),
            "strategy_preferences": self.strategy_preferences,
            "attribution_count": len(self.attribution_history),
        }


# === Global Instance ===

_attributor_instance: Optional[OutcomeAttributor] = None


def get_outcome_attributor() -> OutcomeAttributor:
    """Get or create the global outcome attributor."""
    global _attributor_instance
    if _attributor_instance is None:
        _attributor_instance = OutcomeAttributor()
    return _attributor_instance


def reset_outcome_attributor() -> None:
    """Reset the global outcome attributor."""
    global _attributor_instance
    _attributor_instance = None
