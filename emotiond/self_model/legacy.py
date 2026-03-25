"""
MVP-5 D4: Self-Model System

Structured self-model that participates as a first-class decision input.
Includes:
- Values weights (connection, honesty, safety, growth)
- Capability beliefs with confidence
- Current goals with priority
- Identity stability metric

Features:
- Gradual updates with evidence logging
- Conflict resolution (avoids abrupt flips)
- Deterministic updates
- Trace/explanation visibility
"""
import time
import math
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class ValueWeights(BaseModel):
    """
    Core values with weights [0, 1].
    
    These values guide decision-making and action selection.
    """
    connection: float = Field(default=0.7, ge=0.0, le=1.0, description="Value of social connection")
    honesty: float = Field(default=0.8, ge=0.0, le=1.0, description="Value of truthfulness")
    safety: float = Field(default=0.6, ge=0.0, le=1.0, description="Value of personal safety")
    growth: float = Field(default=0.5, ge=0.0, le=1.0, description="Value of learning/growth")
    
    def get_dominant(self) -> Tuple[str, float]:
        """Get the dominant value and its weight."""
        values = {
            "connection": self.connection,
            "honesty": self.honesty,
            "safety": self.safety,
            "growth": self.growth
        }
        return max(values.items(), key=lambda x: x[1])
    
    def normalize(self) -> "ValueWeights":
        """Normalize weights to sum to 1.0 (for weighted decision making)."""
        total = self.connection + self.honesty + self.safety + self.growth
        if total == 0:
            return ValueWeights(connection=0.25, honesty=0.25, safety=0.25, growth=0.25)
        return ValueWeights(
            connection=self.connection / total,
            honesty=self.honesty / total,
            safety=self.safety / total,
            growth=self.growth / total
        )


class CapabilityBelief(BaseModel):
    """
    Belief about a specific capability with confidence.
    
    - capability: What can be done [0, 1]
    - confidence: How certain about this belief [0, 1]
    - evidence_count: Number of supporting evidence samples
    """
    capability: float = Field(default=0.5, ge=0.0, le=1.0, description="Capability level")
    confidence: float = Field(default=0.3, ge=0.0, le=1.0, description="Confidence in belief")
    evidence_count: int = Field(default=0, ge=0, description="Number of evidence samples")
    last_updated: float = Field(default_factory=time.time, description="Last update timestamp")
    
    def effective_capability(self) -> float:
        """
        Effective capability weighted by confidence.
        
        Low confidence beliefs have less impact on decisions.
        """
        return self.capability * self.confidence


class CapabilityBeliefs(BaseModel):
    """
    Collection of capability beliefs.
    
    Tracks what the system believes it can/cannot do.
    """
    clarify: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.7, confidence=0.5))
    repair: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.6, confidence=0.4))
    set_boundary: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.8, confidence=0.6))
    approach: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.7, confidence=0.5))
    withdraw: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.9, confidence=0.7))
    reflect: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.6, confidence=0.4))
    learn: CapabilityBelief = Field(default_factory=lambda: CapabilityBelief(capability=0.5, confidence=0.3))
    
    def get(self, name: str) -> Optional[CapabilityBelief]:
        """Get a capability belief by name."""
        return getattr(self, name, None)
    
    def get_action_bias(self, action: str) -> float:
        """
        Get action bias based on capability beliefs.
        
        Returns a bias value [-1, 1] where:
        - Positive = favor this action (high capability + confidence)
        - Negative = avoid this action (low capability or confidence)
        """
        belief = self.get(action)
        if belief is None:
            return 0.0
        
        # Combine capability and confidence
        # High capability + high confidence = strong positive bias
        # Low capability OR low confidence = negative bias
        return (belief.capability * 2 - 1) * belief.confidence


class Goal(BaseModel):
    """
    A goal with priority and progress tracking.
    
    Goals compete for attention based on priority and context.
    """
    id: str = Field(..., description="Unique goal identifier")
    description: str = Field(..., description="Goal description")
    priority: float = Field(default=0.5, ge=0.0, le=1.0, description="Goal priority [0, 1]")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress toward goal [0, 1]")
    created_at: float = Field(default_factory=time.time, description="Creation timestamp")
    deadline: Optional[float] = Field(default=None, description="Optional deadline timestamp")
    active: bool = Field(default=True, description="Whether goal is currently active")
    
    def is_urgent(self, current_time: Optional[float] = None) -> bool:
        """Check if goal is urgent (near deadline or high priority)."""
        if not self.active:
            return False
        
        if self.priority > 0.8:
            return True
        
        if self.deadline:
            current = current_time or time.time()
            time_left = self.deadline - current
            if time_left < 3600:  # Less than 1 hour
                return True
        
        return False
    
    def effective_priority(self) -> float:
        """
        Calculate effective priority considering progress.
        
        Nearly complete goals get slight priority boost.
        Stalled goals get slight priority reduction.
        """
        if not self.active:
            return 0.0
        
        # Progress modifier: nearly done = slight boost, stalled = slight reduction
        progress_modifier = 0.1 * (self.progress - 0.5)
        
        return max(0.0, min(1.0, self.priority + progress_modifier))


class CurrentGoals(BaseModel):
    """
    Active goals with management methods.
    
    Manages goal lifecycle and priority-based selection.
    """
    goals: List[Goal] = Field(default_factory=list, description="List of active goals")
    max_goals: int = Field(default=5, ge=1, le=10, description="Maximum number of concurrent goals")
    
    def add_goal(self, goal: Goal) -> bool:
        """
        Add a new goal if under limit.
        
        Returns True if added, False if at capacity.
        """
        if len(self.goals) >= self.max_goals:
            # Try to remove completed or inactive goals
            self._prune_goals()
        
        if len(self.goals) < self.max_goals:
            self.goals.append(goal)
            return True
        
        return False
    
    def _prune_goals(self) -> None:
        """Remove completed or inactive goals."""
        self.goals = [g for g in self.goals if g.active and g.progress < 1.0]
    
    def get_top_priority(self, n: int = 3) -> List[Goal]:
        """Get top N goals by effective priority."""
        active = [g for g in self.goals if g.active]
        sorted_goals = sorted(active, key=lambda g: g.effective_priority(), reverse=True)
        return sorted_goals[:n]
    
    def get_urgent(self) -> List[Goal]:
        """Get all urgent goals."""
        return [g for g in self.goals if g.is_urgent()]
    
    def update_progress(self, goal_id: str, progress: float) -> bool:
        """Update progress for a goal."""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.progress = max(0.0, min(1.0, progress))
                return True
        return False
    
    def deactivate(self, goal_id: str) -> bool:
        """Deactivate a goal."""
        for goal in self.goals:
            if goal.id == goal_id:
                goal.active = False
                return True
        return False


class EvidenceEntry(BaseModel):
    """
    A single evidence entry for belief updates.
    
    Tracks what evidence led to belief changes.
    """
    timestamp: float = Field(default_factory=time.time)
    source: str = Field(..., description="Source of evidence (e.g., 'event', 'feedback', 'reflection')")
    value: float = Field(..., description="Evidence value")
    weight: float = Field(default=1.0, ge=0.0, description="Evidence weight")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class UpdateLog(BaseModel):
    """
    Log of belief updates for auditability.
    
    Tracks how beliefs evolved over time.
    """
    field_name: str = Field(..., description="Which field was updated")
    old_value: float = Field(..., description="Previous value")
    new_value: float = Field(..., description="New value")
    timestamp: float = Field(default_factory=time.time)
    evidence: List[EvidenceEntry] = Field(default_factory=list, description="Supporting evidence")
    reason: str = Field(default="", description="Reason for update")


class SelfModel(BaseModel):
    """
    Complete self-model for decision-making.
    
    The self-model is a first-class input to decisions, influencing:
    - Action bias (which actions to prefer)
    - Repair/boundary strategy
    - Reflection/clarification choices
    - Goal prioritization
    """
    # Core components
    values: ValueWeights = Field(default_factory=ValueWeights)
    capabilities: CapabilityBeliefs = Field(default_factory=CapabilityBeliefs)
    goals: CurrentGoals = Field(default_factory=CurrentGoals)
    
    # Identity stability
    identity_stability: float = Field(default=0.5, ge=0.0, le=1.0, description="How stable the self-model is")
    
    # Update tracking
    update_count: int = Field(default=0, description="Number of updates applied")
    last_update: float = Field(default_factory=time.time, description="Last update timestamp")
    update_history: List[UpdateLog] = Field(default_factory=list, description="History of updates")
    
    # Configuration
    max_history: int = Field(default=100, description="Maximum update history entries")
    update_rate_limit: float = Field(default=60.0, description="Minimum seconds between updates")
    
    def get_action_bias(self, action: str) -> float:
        """
        Get bias for an action based on self-model.
        
        Combines capability beliefs with value alignment.
        """
        # Capability bias
        capability_bias = self.capabilities.get_action_bias(action)
        
        # Value alignment bias
        value_bias = self._get_value_alignment_bias(action)
        
        # Weight by identity stability (stable identity = stronger biases)
        stability_weight = 0.5 + 0.5 * self.identity_stability
        
        combined = (capability_bias * 0.6 + value_bias * 0.4) * stability_weight
        
        return max(-1.0, min(1.0, combined))
    
    def _get_value_alignment_bias(self, action: str) -> float:
        """
        Calculate how well an action aligns with values.
        
        Returns [-1, 1] where positive = aligns with values.
        """
        action_value_alignment = {
            "clarify": {"honesty": 0.8, "connection": 0.4, "safety": 0.2, "growth": 0.3},
            "repair": {"honesty": 0.6, "connection": 0.8, "safety": 0.1, "growth": 0.2},
            "set_boundary": {"honesty": 0.5, "connection": -0.2, "safety": 0.9, "growth": 0.1},
            "approach": {"honesty": 0.3, "connection": 0.9, "safety": -0.1, "growth": 0.2},
            "withdraw": {"honesty": 0.1, "connection": -0.3, "safety": 0.7, "growth": 0.0},
            "reflect": {"honesty": 0.7, "connection": 0.2, "safety": 0.3, "growth": 0.8},
            "learn": {"honesty": 0.4, "connection": 0.2, "safety": 0.1, "growth": 0.9},
        }
        
        if action not in action_value_alignment:
            return 0.0
        
        alignment = action_value_alignment[action]
        normalized = self.values.normalize()
        
        score = (
            alignment["honesty"] * normalized.honesty +
            alignment["connection"] * normalized.connection +
            alignment["safety"] * normalized.safety +
            alignment["growth"] * normalized.growth
        )
        
        return score
    
    def should_reflect(self, uncertainty: float, prediction_error: float) -> bool:
        """
        Decide whether to reflect based on self-model.
        
        Considers:
        - Current uncertainty
        - Prediction error
        - Capability belief for reflection
        - Growth value
        """
        # Base threshold from uncertainty
        threshold = 0.7 - (self.values.growth * 0.2)  # Higher growth = lower threshold
        
        # Adjust by reflection capability
        reflect_cap = self.capabilities.reflect
        threshold -= reflect_cap.confidence * 0.1  # Higher confidence = lower threshold
        
        # Check conditions
        if uncertainty > threshold:
            return True
        
        if prediction_error > 0.3 and reflect_cap.confidence > 0.3:
            return True
        
        return False
    
    def should_clarify(self, uncertainty: float, social_threat: float) -> bool:
        """
        Decide whether to ask for clarification.
        
        Considers:
        - Uncertainty
        - Social threat (avoid clarification in high threat)
        - Honesty value (higher = more willing to admit uncertainty)
        - Clarify capability
        """
        # High social threat = avoid clarification (may escalate)
        if social_threat > 0.6:
            return False
        
        # Base threshold
        threshold = 0.6 - (self.values.honesty * 0.15)
        
        # Adjust by clarify capability
        clarify_cap = self.capabilities.clarify
        threshold -= clarify_cap.confidence * 0.1
        
        return uncertainty > threshold
    
    def get_repair_strategy(self, relationship_bond: float, relationship_grudge: float) -> str:
        """
        Get repair strategy based on self-model and relationship state.
        
        Strategies:
        - "direct": Direct apology/acknowledgment
        - "indirect": Gradual repair through positive actions
        - "boundary_first": Establish safety before repair
        - "withdraw": Not safe to repair now
        """
        # Check safety value
        if self.values.safety > 0.7 and relationship_grudge > 0.6:
            return "boundary_first"
        
        # Check connection value
        if self.values.connection > 0.7 and relationship_bond > 0.4:
            return "direct"
        
        # Check repair capability
        repair_cap = self.capabilities.repair
        if repair_cap.confidence < 0.3:
            return "indirect"
        
        # Default based on relationship state
        if relationship_grudge > 0.7:
            return "withdraw"
        elif relationship_grudge > 0.4:
            return "indirect"
        else:
            return "direct"
    
    def get_boundary_strategy(self, social_threat: float, relationship_trust: float) -> str:
        """
        Get boundary strategy based on self-model and context.
        
        Strategies:
        - "firm": Clear, assertive boundary
        - "soft": Gentle boundary with explanation
        - "gradual": Escalating boundary over time
        - "immediate": Urgent boundary (high threat)
        """
        # High threat = immediate action
        if social_threat > 0.7:
            return "immediate"
        
        # Low trust + high safety value = firm boundary
        if relationship_trust < 0.3 and self.values.safety > 0.7:
            return "firm"
        
        # High connection value = soft boundary
        if self.values.connection > 0.7:
            return "soft"
        
        # Check boundary capability
        boundary_cap = self.capabilities.set_boundary
        if boundary_cap.confidence < 0.4:
            return "gradual"
        
        return "firm"
    
    def update_values(
        self,
        connection: Optional[float] = None,
        honesty: Optional[float] = None,
        safety: Optional[float] = None,
        growth: Optional[float] = None,
        evidence: Optional[EvidenceEntry] = None,
        reason: str = ""
    ) -> bool:
        """
        Gradually update value weights.
        
        Uses gradual update formula to avoid abrupt flips.
        Returns True if updated, False if rate limited.
        """
        if not self._check_rate_limit():
            return False
        
        updates = {
            "connection": connection,
            "honesty": honesty,
            "safety": safety,
            "growth": growth
        }
        
        for field, new_value in updates.items():
            if new_value is not None:
                self._gradual_update_field(field, new_value, evidence, reason)
        
        self._post_update()
        return True
    
    def update_capability(
        self,
        name: str,
        capability: Optional[float] = None,
        confidence: Optional[float] = None,
        evidence: Optional[EvidenceEntry] = None,
        reason: str = ""
    ) -> bool:
        """
        Gradually update a capability belief.
        
        Updates both capability and confidence separately.
        """
        if not self._check_rate_limit():
            return False
        
        belief = self.capabilities.get(name)
        if belief is None:
            return False
        
        # Update capability
        if capability is not None:
            old_value = belief.capability
            new_value = self._compute_gradual_value(
                old_value, capability, belief.evidence_count
            )
            belief.capability = new_value
            
            if evidence:
                self._log_update(
                    f"capabilities.{name}.capability",
                    old_value, new_value, [evidence], reason
                )
        
        # Update confidence
        if confidence is not None:
            old_value = belief.confidence
            new_value = self._compute_gradual_value(
                old_value, confidence, belief.evidence_count
            )
            belief.confidence = new_value
            
            if evidence:
                self._log_update(
                    f"capabilities.{name}.confidence",
                    old_value, new_value, [evidence], reason
                )
        
        # Increment evidence count
        if evidence:
            belief.evidence_count += 1
        belief.last_updated = time.time()
        
        self._post_update()
        return True
    
    def _gradual_update_field(
        self,
        field: str,
        new_value: float,
        evidence: Optional[EvidenceEntry],
        reason: str
    ) -> None:
        """Gradually update a single field."""
        old_value = getattr(self.values, field)
        
        # Compute gradual update
        updated_value = self._compute_gradual_value(old_value, new_value, self.update_count)
        
        # Apply update
        setattr(self.values, field, updated_value)
        
        # Log
        if evidence:
            self._log_update(f"values.{field}", old_value, updated_value, [evidence], reason)
    
    def _compute_gradual_value(
        self,
        current: float,
        target: float,
        evidence_count: int,
        min_step: float = 0.05,
        max_step: float = 0.2
    ) -> float:
        """
        Compute gradual update value.
        
        Formula: new = current + sign(target - current) * step_size
        
        Step size decreases with more evidence (more stable beliefs).
        """
        diff = target - current
        
        if abs(diff) < 0.01:
            return current
        
        # Step size: more evidence = smaller steps (more stable)
        # evidence_count=0 -> max_step, evidence_count=100 -> min_step
        stability_factor = min(1.0, evidence_count / 50.0)
        step_size = max_step - (max_step - min_step) * stability_factor
        
        # Direction
        direction = 1 if diff > 0 else -1
        
        # Apply step, but don't overshoot
        step = direction * min(step_size, abs(diff))
        
        return max(0.0, min(1.0, current + step))
    
    def _check_rate_limit(self) -> bool:
        """Check if update is rate limited."""
        current_time = time.time()
        if current_time - self.last_update < self.update_rate_limit:
            return False
        return True
    
    def _post_update(self) -> None:
        """Post-update housekeeping."""
        self.update_count += 1
        self.last_update = time.time()
        
        # Update identity stability based on update frequency
        # Frequent updates = lower stability
        time_since_last = time.time() - self.last_update
        if time_since_last < 300:  # Less than 5 minutes
            self.identity_stability = max(0.0, self.identity_stability - 0.01)
        else:
            self.identity_stability = min(1.0, self.identity_stability + 0.001)
        
        # Prune history
        if len(self.update_history) > self.max_history:
            self.update_history = self.update_history[-self.max_history:]
    
    def _log_update(
        self,
        field_name: str,
        old_value: float,
        new_value: float,
        evidence: List[EvidenceEntry],
        reason: str
    ) -> None:
        """Log an update."""
        log = UpdateLog(
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            evidence=evidence,
            reason=reason
        )
        self.update_history.append(log)
    
    def resolve_conflict(
        self,
        field: str,
        evidence_a: EvidenceEntry,
        evidence_b: EvidenceEntry
    ) -> float:
        """
        Resolve conflicting evidence.
        
        Returns the resolved value based on:
        - Evidence weight
        - Evidence recency
        - Consistency with existing beliefs
        """
        # Weight by evidence weight
        weight_a = evidence_a.weight
        weight_b = evidence_b.weight
        
        # Recency bonus (within last hour)
        current_time = time.time()
        if current_time - evidence_a.timestamp < 3600:
            weight_a *= 1.2
        if current_time - evidence_b.timestamp < 3600:
            weight_b *= 1.2
        
        # Weighted average
        total_weight = weight_a + weight_b
        if total_weight == 0:
            return (evidence_a.value + evidence_b.value) / 2
        
        resolved = (evidence_a.value * weight_a + evidence_b.value * weight_b) / total_weight
        
        # Log conflict resolution
        self._log_update(
            field,
            evidence_a.value,
            resolved,
            [evidence_a, evidence_b],
            f"Conflict resolution: weighted average"
        )
        
        return resolved
    
    def get_explanation(self) -> Dict[str, Any]:
        """
        Get explanation of self-model influence.
        
        Returns structured explanation for trace visibility.
        """
        dominant_value, value_weight = self.values.get_dominant()
        
        # Top capabilities
        cap_scores = {
            "clarify": self.capabilities.clarify.effective_capability(),
            "repair": self.capabilities.repair.effective_capability(),
            "set_boundary": self.capabilities.set_boundary.effective_capability(),
            "approach": self.capabilities.approach.effective_capability(),
            "withdraw": self.capabilities.withdraw.effective_capability(),
            "reflect": self.capabilities.reflect.effective_capability(),
            "learn": self.capabilities.learn.effective_capability(),
        }
        top_capabilities = sorted(cap_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Top goals
        top_goals = self.goals.get_top_priority(3)
        
        return {
            "dominant_value": {
                "name": dominant_value,
                "weight": value_weight,
                "all_values": self.values.model_dump()
            },
            "top_capabilities": [
                {"name": name, "effective": score}
                for name, score in top_capabilities
            ],
            "top_goals": [
                {"id": g.id, "priority": g.priority, "progress": g.progress}
                for g in top_goals
            ],
            "identity_stability": self.identity_stability,
            "update_count": self.update_count,
            "recent_updates": len([u for u in self.update_history if time.time() - u.timestamp < 3600])
        }
    
    def to_trace_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for trace/logging."""
        return {
            "values": self.values.model_dump(),
            "capabilities": {
                "clarify": {
                    "capability": self.capabilities.clarify.capability,
                    "confidence": self.capabilities.clarify.confidence,
                    "evidence_count": self.capabilities.clarify.evidence_count
                },
                "repair": {
                    "capability": self.capabilities.repair.capability,
                    "confidence": self.capabilities.repair.confidence,
                    "evidence_count": self.capabilities.repair.evidence_count
                },
                "set_boundary": {
                    "capability": self.capabilities.set_boundary.capability,
                    "confidence": self.capabilities.set_boundary.confidence,
                    "evidence_count": self.capabilities.set_boundary.evidence_count
                },
                "approach": {
                    "capability": self.capabilities.approach.capability,
                    "confidence": self.capabilities.approach.confidence,
                    "evidence_count": self.capabilities.approach.evidence_count
                },
                "withdraw": {
                    "capability": self.capabilities.withdraw.capability,
                    "confidence": self.capabilities.withdraw.confidence,
                    "evidence_count": self.capabilities.withdraw.evidence_count
                },
                "reflect": {
                    "capability": self.capabilities.reflect.capability,
                    "confidence": self.capabilities.reflect.confidence,
                    "evidence_count": self.capabilities.reflect.evidence_count
                },
                "learn": {
                    "capability": self.capabilities.learn.capability,
                    "confidence": self.capabilities.learn.confidence,
                    "evidence_count": self.capabilities.learn.evidence_count
                },
            },
            "goals": {
                "count": len(self.goals.goals),
                "top": [
                    {"id": g.id, "priority": g.priority}
                    for g in self.goals.get_top_priority(3)
                ]
            },
            "identity_stability": self.identity_stability,
            "explanation": self.get_explanation()
        }


# Global instance
_self_model: Optional[SelfModel] = None


def get_self_model() -> SelfModel:
    """Get or create the global self-model."""
    global _self_model
    if _self_model is None:
        _self_model = SelfModel()
    return _self_model


def reset_self_model():
    """Reset the global self-model (for testing)."""
    global _self_model
    _self_model = None


# MVP-7.6: Global SelfModelV0 instance for per-target tracking
_self_model_v0_instances: Dict[str, "SelfModelV0"] = {}


def get_self_model_v0(target: Optional[str] = None) -> "SelfModelV0":
    """
    Get or create a SelfModelV0 instance for a specific target.
    
    Args:
        target: Target identifier (e.g., "user", "telegram:12345")
                If None, returns a default instance
    
    Returns:
        SelfModelV0 instance for the target
    """
    global _self_model_v0_instances
    
    key = target or "default"
    
    if key not in _self_model_v0_instances:
        _self_model_v0_instances[key] = SelfModelV0()
        # Set the focus target
        _self_model_v0_instances[key].relational.focus_target = key
    
    return _self_model_v0_instances[key]


def reset_self_model_v0(target: Optional[str] = None):
    """
    Reset SelfModelV0 instance(s) (for testing).
    
    Args:
        target: Specific target to reset, or None to reset all
    """
    global _self_model_v0_instances
    
    if target is None:
        _self_model_v0_instances = {}
    elif target in _self_model_v0_instances:
        del _self_model_v0_instances[target]


def apply_self_model_to_decision(
    decision: Dict[str, Any],
    self_model: Optional[SelfModel] = None
) -> Dict[str, Any]:
    """
    Apply self-model influence to a decision.
    
    Modifies decision based on self-model biases and strategies.
    """
    if self_model is None:
        self_model = get_self_model()
    
    # Get action from decision
    action = decision.get("action") or decision.get("selected")
    
    if action:
        # Add action bias
        bias = self_model.get_action_bias(action)
        decision["self_model_bias"] = bias
        
        # Add explanation
        decision["self_model_explanation"] = self_model.get_explanation()
    
    # Apply strategy if applicable
    if "relationship" in decision:
        rel = decision["relationship"]
        bond = rel.get("bond", 0.0)
        grudge = rel.get("grudge", 0.0)
        trust = rel.get("trust", 0.0)
        
        if decision.get("intent") == "repair":
            strategy = self_model.get_repair_strategy(bond, grudge)
            decision["repair_strategy"] = strategy
        
        if decision.get("intent") in ["set_boundary", "boundary"]:
            social_threat = decision.get("social_threat", 0.0)
            strategy = self_model.get_boundary_strategy(social_threat, trust)
            decision["boundary_strategy"] = strategy
    
    return decision

# ========================= MVP-7 Self-Model v0 =========================
class BodilySnapshot(BaseModel):
    energy: float = Field(default=0.7, ge=0.0, le=1.0)
    social_safety: float = Field(default=0.6, ge=0.0, le=1.0)
    focus_fatigue: float = Field(default=0.0, ge=0.0, le=1.0)


class RelationalSnapshot(BaseModel):
    focus_target: str = "user"
    bond: float = Field(default=0.5, ge=0.0, le=1.0)
    grudge: float = Field(default=0.0, ge=0.0, le=1.0)
    trust: float = Field(default=0.5, ge=0.0, le=1.0)
    repair_bank: float = Field(default=0.0, ge=0.0, le=1.0)
    ledger_summary: Dict[str, int] = Field(default_factory=dict)


class CognitiveSnapshot(BaseModel):
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: float = Field(default=0.5, ge=0.0, le=1.0)
    regulation_budget: float = Field(default=1.0, ge=0.0, le=1.0)


class IdentitySnapshot(BaseModel):
    traits: List[str] = Field(default_factory=lambda: ["calm", "direct", "pragmatic"])
    value_weights: Dict[str, float] = Field(default_factory=dict)


class SelfModelV0(BaseModel):
    bodily: BodilySnapshot = Field(default_factory=BodilySnapshot)
    relational: RelationalSnapshot = Field(default_factory=RelationalSnapshot)
    cognitive: CognitiveSnapshot = Field(default_factory=CognitiveSnapshot)
    identity: IdentitySnapshot = Field(default_factory=IdentitySnapshot)
    updated_at: float = Field(default_factory=time.time)


    # ========================= MVP-7.6 Phase 1: Self-Conflict & Manifest/Replay =========================
    
    def compute_self_conflict(
        self,
        event_type: str,
        meta: Optional[Dict[str, Any]] = None,
        relationship_state: Optional[Dict[str, float]] = None,
    ) -> float:
        """Calculate self_conflict based on three types of prediction errors."""
        meta = meta or {}
        relationship_state = relationship_state or {}
        
        value_conflict = self._compute_value_conflict(event_type, meta)
        capability_conflict = self._compute_capability_conflict(event_type, meta)
        identity_conflict = self._compute_identity_conflict(event_type, meta, relationship_state)
        
        weights = {"value": 0.4, "capability": 0.3, "identity": 0.3}
        self_conflict = (
            weights["value"] * value_conflict +
            weights["capability"] * capability_conflict +
            weights["identity"] * identity_conflict
        )
        
        return max(0.0, min(1.0, self_conflict))
    
    def _compute_value_conflict(self, event_type: str, meta: Optional[Dict[str, Any]]) -> float:
        """Compute value conflict component (0-1)."""
        if meta is None:
            meta = {}
        value_alignment = meta.get("value_alignment", None)
        if value_alignment is not None:
            return 1.0 - value_alignment
        
        event_lower = event_type.lower()
        if any(kw in event_lower for kw in ["deception", "betrayal", "harm", "threat", "rejection"]):
            return 0.9
        if any(kw in event_lower for kw in ["conflict", "disagreement", "failure", "mistake"]):
            return 0.6
        if any(kw in event_lower for kw in ["neutral", "routine", "information"]):
            return 0.2
        return 0.3
    
    def _compute_capability_conflict(self, event_type: str, meta: Optional[Dict[str, Any]]) -> float:
        """Compute capability failure component (0-1)."""
        if meta is None:
            meta = {}
        success = meta.get("success", None)
        if success is not None:
            capability_name = meta.get("capability", None)
            if capability_name:
                belief = self._get_capability_belief(capability_name)
                if belief:
                    expected = belief["capability"] * belief["confidence"]
                    actual = 1.0 if success else 0.0
                    return abs(expected - actual)
            return 0.0 if success else 0.7
        
        event_lower = event_type.lower()
        if any(kw in event_lower for kw in ["failure", "error", "unable", "cannot"]):
            return 0.8
        if any(kw in event_lower for kw in ["success", "achieved", "completed"]):
            return 0.1
        return 0.3
    
    def _compute_identity_conflict(
        self, event_type: str, meta: Optional[Dict[str, Any]], relationship_state: Dict[str, float]
    ) -> float:
        """Compute identity threat component (0-1)."""
        if meta is None:
            meta = {}
        identity_threat = meta.get("identity_threat", 0.0)
        if identity_threat > 0:
            return min(1.0, identity_threat)
        
        bond = relationship_state.get("bond", 0.5)
        trust = relationship_state.get("trust", 0.5)
        
        connection_value = self.identity.value_weights.get("connection", 0.7)
        if connection_value > 0.6 and (bond < 0.3 or trust < 0.3):
            return 0.7
        
        event_lower = event_type.lower()
        if any(kw in event_lower for kw in ["rejection", "betrayal", "abandonment", "exclusion"]):
            return 0.9
        if any(kw in event_lower for kw in ["criticism", "blame", "accusation"]):
            return 0.6
        return 0.2
    
    def _get_capability_belief(self, name: str) -> Optional[Dict[str, float]]:
        """Get capability belief by name."""
        return None
    
    def apply_event(self, event: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update self_model state based on an event and return conflict information."""
        ctx = ctx or {}
        event_type = event.get("type", "unknown")
        meta = event.get("meta") or {}
        relationship_state = ctx.get("relationship_state", {})
        
        self_conflict = self.compute_self_conflict(event_type, meta, relationship_state)
        old_state = self.snapshot()
        delta = self._apply_event_updates(event, ctx, self_conflict)
        self.updated_at = time.time()
        
        evidence = {
            "event_type": event_type,
            "event_meta": meta,
            "relationship_state": relationship_state,
            "conflict_components": {
                "value_conflict": self._compute_value_conflict(event_type, meta),
                "capability_conflict": self._compute_capability_conflict(event_type, meta),
                "identity_conflict": self._compute_identity_conflict(event_type, meta, relationship_state),
            },
        }
        
        return {
            "delta": delta,
            "self_conflict": self_conflict,
            "evidence": evidence,
            "old_state": old_state,
            "new_state": self.snapshot(),
        }
    
    def _apply_event_updates(self, event: Dict[str, Any], ctx: Dict[str, Any], self_conflict: float) -> Dict[str, Any]:
        """Apply state updates based on event."""
        delta = {}
        meta = event.get("meta") or {}
        event_type = event.get("type", "unknown")
        
        if self_conflict > 0.5:
            old_uncertainty = self.cognitive.uncertainty
            self.cognitive.uncertainty = min(1.0, self.cognitive.uncertainty + 0.1)
            if self.cognitive.uncertainty != old_uncertainty:
                delta["cognitive.uncertainty"] = {"old": old_uncertainty, "new": self.cognitive.uncertainty}
        
        if "feedback" in event_type.lower():
            success = meta.get("success", None)
            old_confidence = self.cognitive.confidence
            if success is True:
                self.cognitive.confidence = min(1.0, self.cognitive.confidence + 0.05)
            elif success is False:
                self.cognitive.confidence = max(0.0, self.cognitive.confidence - 0.05)
            if self.cognitive.confidence != old_confidence:
                delta["cognitive.confidence"] = {"old": old_confidence, "new": self.cognitive.confidence}
        
        if meta and "relationship" in meta:
            rel_meta = meta["relationship"]
            if "bond_delta" in rel_meta:
                old_bond = self.relational.bond
                self.relational.bond = max(0.0, min(1.0, self.relational.bond + rel_meta["bond_delta"]))
                delta["relational.bond"] = {"old": old_bond, "new": self.relational.bond}
        
        return delta
    
    def get_action_bias(self, action: str) -> float:
        """
        Get bias for an action based on self-model.
        
        Returns a bias value [-1, 1] where:
        - Positive = favor this action
        - Negative = avoid this action
        
        Based on cognitive confidence and value weights.
        """
        # Action value alignment map
        action_value_alignment = {
            "clarify": {"honesty": 0.8, "connection": 0.4, "safety": 0.2, "growth": 0.3},
            "repair": {"honesty": 0.6, "connection": 0.8, "safety": 0.1, "growth": 0.2},
            "set_boundary": {"honesty": 0.5, "connection": -0.2, "safety": 0.9, "growth": 0.1},
            "approach": {"honesty": 0.3, "connection": 0.9, "safety": -0.1, "growth": 0.2},
            "withdraw": {"honesty": 0.1, "connection": -0.3, "safety": 0.7, "growth": 0.0},
            "reflect": {"honesty": 0.7, "connection": 0.2, "safety": 0.3, "growth": 0.8},
            "learn": {"honesty": 0.4, "connection": 0.2, "safety": 0.1, "growth": 0.9},
            "repair_offer": {"honesty": 0.6, "connection": 0.8, "safety": 0.1, "growth": 0.2},
            "boundary": {"honesty": 0.5, "connection": -0.2, "safety": 0.9, "growth": 0.1},
        }
        
        # Normalize value weights
        value_weights = self.identity.value_weights
        total = sum(value_weights.values()) if value_weights else 1.0
        if total == 0:
            total = 1.0
        
        # Get alignment score for the action
        if action not in action_value_alignment:
            return 0.0
        
        alignment = action_value_alignment[action]
        score = sum(
            alignment.get(key, 0.0) * (value_weights.get(key, 0.5) / total)
            for key in ["honesty", "connection", "safety", "growth"]
        )
        
        # Weight by cognitive confidence
        confidence_weight = self.cognitive.confidence
        weighted_score = score * confidence_weight
        
        # Scale to [-1, 1] range
        return max(-1.0, min(1.0, weighted_score * 2 - 1))


    def compute_hash(self) -> str:
        """Compute deterministic hash of self_model state for manifest/replay."""
        import hashlib
        import json
        
        state_dict = {
            "bodily": {
                "energy": self.bodily.energy,
                "social_safety": self.bodily.social_safety,
                "focus_fatigue": self.bodily.focus_fatigue,
            },
            "relational": {
                "focus_target": self.relational.focus_target,
                "bond": self.relational.bond,
                "grudge": self.relational.grudge,
                "trust": self.relational.trust,
                "repair_bank": self.relational.repair_bank,
                "ledger_summary": json.dumps(self.relational.ledger_summary, sort_keys=True),
            },
            "cognitive": {
                "confidence": self.cognitive.confidence,
                "uncertainty": self.cognitive.uncertainty,
                "regulation_budget": self.cognitive.regulation_budget,
            },
            "identity": {
                "traits": sorted(self.identity.traits),
                "value_weights": json.dumps(self.identity.value_weights, sort_keys=True),
            },
        }
        
        canonical = json.dumps(state_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    
    def snapshot(self) -> Dict[str, Any]:
        """Return serializable state snapshot for persistence/replay."""
        return {
            "bodily": {
                "energy": self.bodily.energy,
                "social_safety": self.bodily.social_safety,
                "focus_fatigue": self.bodily.focus_fatigue,
            },
            "relational": {
                "focus_target": self.relational.focus_target,
                "bond": self.relational.bond,
                "grudge": self.relational.grudge,
                "trust": self.relational.trust,
                "repair_bank": self.relational.repair_bank,
                "ledger_summary": dict(self.relational.ledger_summary),
            },
            "cognitive": {
                "confidence": self.cognitive.confidence,
                "uncertainty": self.cognitive.uncertainty,
                "regulation_budget": self.cognitive.regulation_budget,
            },
            "identity": {
                "traits": list(self.identity.traits),
                "value_weights": dict(self.identity.value_weights),
            },
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "SelfModelV0":
        """Reconstruct SelfModelV0 from snapshot."""
        bodily = BodilySnapshot(**snapshot.get("bodily", {}))
        relational = RelationalSnapshot(**snapshot.get("relational", {}))
        cognitive = CognitiveSnapshot(**snapshot.get("cognitive", {}))
        identity = IdentitySnapshot(**snapshot.get("identity", {}))
        
        return cls(
            bodily=bodily,
            relational=relational,
            cognitive=cognitive,
            identity=identity,
            updated_at=snapshot.get("updated_at", time.time()),
        )


def build_self_model_v0(*, focus_target: str, emotion_state: Any, relationship: Dict[str, Any], ledger_summary: Optional[Dict[str, int]] = None, values: Optional[Dict[str, float]] = None) -> SelfModelV0:
    uncertainty = float(getattr(emotion_state, "uncertainty", 0.5))
    confidence = max(0.0, min(1.0, 1.0 - uncertainty))
    return SelfModelV0(
        bodily=BodilySnapshot(
            energy=float(getattr(emotion_state, "energy", 0.7)),
            social_safety=float(getattr(emotion_state, "social_safety", 0.6)),
            focus_fatigue=max(0.0, min(1.0, 1.0 - float(getattr(emotion_state, "energy_budget", 1.0)))),
        ),
        relational=RelationalSnapshot(
            focus_target=focus_target,
            bond=float(relationship.get("bond", 0.5)),
            grudge=float(relationship.get("grudge", 0.0)),
            trust=float(relationship.get("trust", 0.5)),
            repair_bank=float(relationship.get("repair_bank", 0.0)),
            ledger_summary=ledger_summary or {},
        ),
        cognitive=CognitiveSnapshot(
            confidence=confidence,
            uncertainty=uncertainty,
            regulation_budget=float(getattr(emotion_state, "regulation_budget", 1.0)),
        ),
        identity=IdentitySnapshot(value_weights=values or {"connection": 0.7, "honesty": 0.8, "safety": 0.6, "growth": 0.5}),
    )


def render_self_report(self_state: SelfModelV0, *, evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    evidence = evidence or {}
    return {
        "summary": {
            "state": "stable" if self_state.cognitive.uncertainty < 0.5 else "uncertain",
            "focus_target": self_state.relational.focus_target,
            "confidence": round(self_state.cognitive.confidence, 3),
        },
        "self_model": self_state.model_dump(),
        "evidence": {
            "self_model_fields": [
                "bodily.energy",
                "bodily.social_safety",
                "relational.bond",
                "relational.grudge",
                "cognitive.uncertainty",
            ],
            "ledger": evidence.get("ledger", {}),
            "episode_refs": evidence.get("episode_refs", []),
        },
    }


# ========================= MVP-Bugfix: Three-Layer State Reporting =========================
# 三层状态报告：Self / Relation / Other
# 解决混淆问题：
# - Self: agent 自己的情绪/驱动/体征
# - Relation: agent 对某个对象的关系账本
# - Other: 对方情绪的"估计"（带置信度/证据）

def render_three_layer_state(
    *,
    agent_id: str,
    counterparty_id: str,
    self_state,
    relationship: dict,
    other_estimate: Optional[dict] = None,
) -> dict:
    """
    Render the three-layer state report with clear semantics.
    
    三层状态清晰区分：
    - Self: agent 的自身状态（能量、安全感、认知确定度）
    - Relation: agent 对 counterparty 的关系指标（信任、连接、怨恨）
    - Other: agent 对 counterparty 情绪的推断（带置信度）
    
    Args:
        agent_id: Who is the agent (e.g., "testbot")
        counterparty_id: Who the relationship is with (e.g., "user")
        self_state: SelfModelV0 or similar with bodily/relational/cognitive
        relationship: Dict with bond/grudge/trust/repair_bank
        other_estimate: Optional dict with estimated_other_state and confidence
    
    Returns:
        Dict with three clear layers
    """
    # Layer 1: Self (agent's own state)
    self_layer = {
        "agent_id": agent_id,
        "summary": {
            "state": "stable" if getattr(self_state.cognitive, "uncertainty", 0.5) < 0.5 else "uncertain",
            "tendency": _infer_tendency(self_state),
            "evidence_fields": [
                "bodily.energy",
                "bodily.social_safety",
                "cognitive.uncertainty",
            ],
        },
        "bodily": {
            "energy": round(getattr(self_state.bodily, "energy", 0.7), 3),
            "social_safety": round(getattr(self_state.bodily, "social_safety", 0.6), 3),
        },
        "cognitive": {
            "confidence": round(getattr(self_state.cognitive, "confidence", 0.5), 3),
            "uncertainty": round(getattr(self_state.cognitive, "uncertainty", 0.5), 3),
        },
    }
    
    # Layer 2: Relation (agent's relationship with counterparty)
    relation_layer = {
        "agent_id": agent_id,
        "counterparty_id": counterparty_id,
        "summary": {
            "bond_level": _classify_bond(relationship.get("bond", 0.5)),
            "trust_level": _classify_trust(relationship.get("trust", 0.5)),
            "repair_status": _classify_repair(relationship.get("repair_bank", 0.0), relationship.get("grudge", 0.0)),
        },
        "metrics": {
            "bond": round(relationship.get("bond", 0.5), 3),
            "grudge": round(relationship.get("grudge", 0.0), 3),
            "trust": round(relationship.get("trust", 0.5), 3),
            "repair_bank": round(relationship.get("repair_bank", 0.0), 3),
        },
        "note": f"我对{counterparty_id}的关系指标（不是{counterparty_id}自己的情绪）",
    }
    
    # Layer 3: Other (inference about counterparty - with confidence)
    other_layer = None
    if other_estimate:
        other_layer = {
            "agent_id": agent_id,
            "counterparty_id": counterparty_id,
            "estimated_state": other_estimate.get("state", "unknown"),
            "confidence": round(other_estimate.get("confidence", 0.0), 3),
            "evidence": other_estimate.get("evidence", []),
            "note": f"我对{counterparty_id}情绪状态的推断（带置信度）",
        }
    
    return {
        "three_layer_state": {
            "self": self_layer,
            "relation": relation_layer,
            "other": other_layer,
        },
        "agent_id": agent_id,
        "counterparty_id": counterparty_id,
        "timestamp": time.time(),
    }


def _infer_tendency(self_state) -> str:
    """从 self state 推断 agent 的倾向"""
    energy = getattr(self_state.bodily, "energy", 0.7)
    social_safety = getattr(self_state.bodily, "social_safety", 0.6)
    uncertainty = getattr(self_state.cognitive, "uncertainty", 0.5)
    
    if social_safety < 0.3:
        return "防御/撤退"
    elif uncertainty > 0.7:
        return "澄清/反思"
    elif energy > 0.7 and social_safety > 0.6:
        return "修复/连接"
    else:
        return "稳态维护"


def _classify_bond(bond: float) -> str:
    """分类连接等级"""
    if bond >= 0.7:
        return "强连接"
    elif bond >= 0.4:
        return "中等连接"
    else:
        return "弱连接"


def _classify_trust(trust: float) -> str:
    """分类信任等级"""
    if trust >= 0.7:
        return "高信任"
    elif trust >= 0.4:
        return "中等信任"
    else:
        return "低信任"


def _classify_repair(repair_bank: float, grudge: float) -> str:
    """分类修复状态"""
    if grudge > 0.7:
        return "需要修复（高怨恨）"
    elif repair_bank > 0.5:
        return "修复进行中"
    elif grudge > 0.3:
        return "轻微张力"
    else:
        return "健康"


def render_self_report_v2(
    self_state,
    *,
    counterparty_id: str = "user",
    agent_id: str = "agent",
    relationship: Optional[dict] = None,
    other_estimate: Optional[dict] = None,
    evidence: Optional[dict] = None,
) -> dict:
    """
    Enhanced self report with three-layer separation.
    
    新版状态报告，清晰区分三层：
    - Self: agent 自身状态
    - Relation: agent 与 counterparty 的关系
    - Other: agent 对 counterparty 情绪的推断
    
    Args:
        self_state: SelfModelV0 instance
        counterparty_id: Who the relationship is with
        agent_id: Who is the agent
        relationship: Relationship dict (bond/grudge/trust/repair_bank)
        other_estimate: Inference about counterparty's state
        evidence: Additional evidence dict
    
    Returns:
        Dict with three-layer state report
    """
    evidence = evidence or {}
    relationship = relationship or {}
    
    # Render three-layer state
    three_layer = render_three_layer_state(
        agent_id=agent_id,
        counterparty_id=counterparty_id,
        self_state=self_state,
        relationship=relationship,
        other_estimate=other_estimate,
    )
    
    # Build full report
    return {
        "three_layer_state": three_layer["three_layer_state"],
        "summary": three_layer["three_layer_state"]["self"]["summary"],
        "agent_id": agent_id,
        "counterparty_id": counterparty_id,
        "evidence": {
            "self_model_fields": [
                "bodily.energy",
                "bodily.social_safety",
                "relational.bond",
                "relational.grudge",
                "cognitive.uncertainty",
            ],
            "ledger": evidence.get("ledger", {}),
            "episode_refs": evidence.get("episode_refs", []),
        },
        "timestamp": time.time(),
    }


def render_three_layer_text(
    *,
    agent_id: str,
    counterparty_id: str,
    self_state,
    relationship: dict,
    other_estimate: Optional[dict] = None,
) -> str:
    """
    Render three-layer state as human-readable text.
    
    用于向用户展示状态的文本格式。
    """
    three_layer = render_three_layer_state(
        agent_id=agent_id,
        counterparty_id=counterparty_id,
        self_state=self_state,
        relationship=relationship,
        other_estimate=other_estimate,
    )
    
    lines = []
    
    # Layer 1: Self
    self_data = three_layer["three_layer_state"]["self"]
    lines.append(f"【我的状态】({agent_id})")
    lines.append(f"  倾向: {self_data['summary']['tendency']}")
    lines.append(f"  能量: {self_data['bodily']['energy']:.2f}")
    lines.append(f"  社交安全感: {self_data['bodily']['social_safety']:.2f}")
    lines.append(f"  认知确定度: {self_data['cognitive']['confidence']:.2f}")
    
    # Layer 2: Relation
    rel_data = three_layer["three_layer_state"]["relation"]
    lines.append(f"\n【我对{counterparty_id}的关系】")
    lines.append(f"  连接: {rel_data['summary']['bond_level']} ({rel_data['metrics']['bond']:.3f})")
    lines.append(f"  信任: {rel_data['summary']['trust_level']} ({rel_data['metrics']['trust']:.3f})")
    lines.append(f"  怨恨: {rel_data['metrics']['grudge']:.3f}")
    lines.append(f"  修复账本: {rel_data['metrics']['repair_bank']:.3f}")
    lines.append(f"  状态: {rel_data['summary']['repair_status']}")
    
    # Layer 3: Other (if available)
    other_data = three_layer["three_layer_state"]["other"]
    if other_data:
        lines.append(f"\n【我对{counterparty_id}情绪的推断】")
        lines.append(f"  推断状态: {other_data['estimated_state']}")
        lines.append(f"  置信度: {other_data['confidence']:.2f}")
        if other_data['evidence']:
            lines.append(f"  依据: {', '.join(other_data['evidence'][:3])}")
    
    return "\n".join(lines)
