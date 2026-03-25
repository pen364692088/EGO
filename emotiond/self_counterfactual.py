"""
MVP11-T15: Counterfactual Self Model

Compares "what if I had fewer resources/lower precision" scenarios and 
executes matching strategies when reality matches a counterfactual.

Key Features:
- Pre-compute strategies for degraded capability scenarios
- Match current reality against counterfactuals
- Apply pre-planned strategies when reality matches
- Integration with hot_self_model for confidence/conflict/control

Use Cases:
1. Pre-planning: "If my energy drops to 0.3, I should switch to conservative mode"
2. Rapid adaptation: Reality matches counterfactual → apply pre-computed strategy
3. Strategy comparison: Compare expected outcomes across scenarios
"""
import time
import math
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class CounterfactualType(Enum):
    """Types of counterfactual scenarios."""
    RESOURCE_DEPLETION = "resource_depletion"  # Energy, time, budget
    CAPABILITY_DEGRADATION = "capability_degradation"  # Skill, precision, speed
    STRESS_CONDITION = "stress_condition"  # High load, urgency, threat
    SOCIAL_DEGRADATION = "social_degradation"  # Trust, bond, affiliation
    COGNITIVE_LIMITATION = "cognitive_limitation"  # Uncertainty, conflict, control


@dataclass
class CounterfactualScenario:
    """
    A counterfactual scenario with modified capabilities/resources.
    
    Represents a "what if" situation where the agent has different
    capabilities than its current state.
    """
    id: str
    name: str
    scenario_type: CounterfactualType
    modifications: Dict[str, float]  # Fields to modify and their target values
    value_tolerance: float = 0.15  # Numerical tolerance for matching degraded state
    min_match_fraction: float = 1.0  # Minimum fraction of fields that must match (0.0-1.0)
    require_all_fields: bool = True  # If True, ALL fields must match for scenario to trigger
    cooldown_ticks: int = 0  # Minimum ticks between re-triggers (prevents oscillation)
    strategy: Optional[Dict[str, Any]] = None  # Pre-computed strategy
    priority: float = 0.5  # Priority when multiple scenarios match
    description: str = ""
    created_at: float = field(default_factory=time.time)
    last_matched: Optional[float] = None
    last_matched_tick: int = 0  # Track tick for cooldown
    match_count: int = 0
    
    # Backward compatibility: accept match_threshold as alias for value_tolerance
    def __init__(
        self,
        id: str,
        name: str,
        scenario_type: CounterfactualType,
        modifications: Dict[str, float],
        value_tolerance: float = 0.15,
        min_match_fraction: float = 1.0,
        require_all_fields: bool = True,
        cooldown_ticks: int = 0,
        strategy: Optional[Dict[str, Any]] = None,
        priority: float = 0.5,
        description: str = "",
        created_at: Optional[float] = None,
        last_matched: Optional[float] = None,
        last_matched_tick: int = 0,
        match_count: int = 0,
        match_threshold: Optional[float] = None,  # Backward compatibility
    ):
        self.id = id
        self.name = name
        self.scenario_type = scenario_type
        self.modifications = modifications
        # Backward compatibility: match_threshold maps to value_tolerance
        self.value_tolerance = match_threshold if match_threshold is not None else value_tolerance
        self.min_match_fraction = min_match_fraction
        self.require_all_fields = require_all_fields
        self.cooldown_ticks = cooldown_ticks
        self.strategy = strategy
        self.priority = priority
        self.description = description
        self.created_at = created_at if created_at is not None else time.time()
        self.last_matched = last_matched
        self.last_matched_tick = last_matched_tick
        self.match_count = match_count
    
    @property
    def match_threshold(self) -> float:
        """Backward compatibility: returns value_tolerance."""
        return self.value_tolerance
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "scenario_type": self.scenario_type.value,
            "modifications": self.modifications,
            "value_tolerance": self.value_tolerance,
            "match_threshold": self.value_tolerance,  # Backward compatibility
            "min_match_fraction": self.min_match_fraction,
            "require_all_fields": self.require_all_fields,
            "cooldown_ticks": self.cooldown_ticks,
            "strategy": self.strategy,
            "priority": self.priority,
            "description": self.description,
            "created_at": self.created_at,
            "last_matched": self.last_matched,
            "last_matched_tick": self.last_matched_tick,
            "match_count": self.match_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CounterfactualScenario":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            scenario_type=CounterfactualType(data["scenario_type"]),
            modifications=data["modifications"],
            value_tolerance=data.get("value_tolerance", data.get("match_threshold", 0.15)),
            min_match_fraction=data.get("min_match_fraction", 1.0),
            require_all_fields=data.get("require_all_fields", True),
            cooldown_ticks=data.get("cooldown_ticks", 0),
            strategy=data.get("strategy"),
            priority=data.get("priority", 0.5),
            description=data.get("description", ""),
            created_at=data.get("created_at", time.time()),
            last_matched=data.get("last_matched"),
            last_matched_tick=data.get("last_matched_tick", 0),
            match_count=data.get("match_count", 0),
        )


@dataclass
class StrategyComparison:
    """
    Result of comparing actual strategy vs counterfactual strategy.
    
    Helps understand the trade-offs between different approaches.
    """
    actual_strategy: Dict[str, Any]
    counterfactual_strategy: Dict[str, Any]
    actual_expected_outcome: float  # Expected success probability
    counterfactual_expected_outcome: float
    risk_difference: float  # counterfactual - actual (positive = counterfactual riskier)
    cost_difference: float
    recommendation: str  # "actual", "counterfactual", or "hybrid"
    confidence: float
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "actual_strategy": self.actual_strategy,
            "counterfactual_strategy": self.counterfactual_strategy,
            "actual_expected_outcome": round(self.actual_expected_outcome, 4),
            "counterfactual_expected_outcome": round(self.counterfactual_expected_outcome, 4),
            "risk_difference": round(self.risk_difference, 4),
            "cost_difference": round(self.cost_difference, 4),
            "recommendation": self.recommendation,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
        }


@dataclass
class RealityMatch:
    """
    Result of matching current reality against counterfactuals.
    
    Indicates which scenario (if any) matches and how closely.
    """
    scenario_id: str
    scenario_name: str
    match_score: float  # 0-1, how closely reality matches
    matched_fields: List[str]  # Fields that triggered the match
    strategy: Dict[str, Any]
    confidence: float
    ts: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "match_score": round(self.match_score, 4),
            "matched_fields": self.matched_fields,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 4),
            "ts": self.ts,
        }


class CounterfactualSelfModel:
    """
    Counterfactual Self Model for pre-planning degraded scenarios.
    
    The model generates "what if" scenarios where the agent has different
    capabilities/resources, pre-computes strategies for those scenarios,
    and applies them when reality matches.
    
    Integration with hot_self_model:
    - Uses confidence/conflict/control for strategy selection
    - Updates HOT state when counterfactual strategies are applied
    - Provides pre-planned responses for degraded states
    
    Usage:
        cf_model = CounterfactualSelfModel(hot_self_model)
        
        # Generate counterfactuals from current state
        counterfactuals = cf_model.generate_counterfactuals(current_state)
        
        # Check if reality matches any counterfactual
        match = cf_model.check_reality_match(current_state)
        
        # Apply pre-computed strategy if matched
        if match:
            strategy = cf_model.apply_counterfactual_strategy(match.scenario_id)
        
        # Or select best strategy based on state
        strategy = cf_model.select_strategy(current_state)
    """
    
    # Default scenario templates
    DEFAULT_SCENARIOS = [
        {
            "id": "low_energy",
            "name": "Low Energy State",
            "scenario_type": CounterfactualType.RESOURCE_DEPLETION,
            "modifications": {"bodily.energy": 0.25},
            "value_tolerance": 0.15,
            "require_all_fields": True,
            "cooldown_ticks": 10,
            "priority": 0.7,
            "description": "Energy critically low, switch to conservation mode",
        },
        {
            "id": "low_safety",
            "name": "Low Safety State",
            "scenario_type": CounterfactualType.STRESS_CONDITION,
            "modifications": {"bodily.social_safety": 0.25, "homeostasis.safety": 0.3},
            "value_tolerance": 0.15,
            "require_all_fields": True,  # Both safety fields must be low
            "min_match_fraction": 1.0,
            "cooldown_ticks": 15,
            "priority": 0.8,
            "description": "Safety threatened, activate defensive mode",
        },
        {
            "id": "high_uncertainty",
            "name": "High Uncertainty State",
            "scenario_type": CounterfactualType.COGNITIVE_LIMITATION,
            "modifications": {"cognitive.uncertainty": 0.75, "cognitive.confidence": 0.3},
            "value_tolerance": 0.15,
            "require_all_fields": False,  # Either can trigger
            "min_match_fraction": 0.5,
            "cooldown_ticks": 5,
            "priority": 0.6,
            "description": "High uncertainty, switch to info-seeking mode",
        },
        {
            "id": "low_control",
            "name": "Low Control State",
            "scenario_type": CounterfactualType.COGNITIVE_LIMITATION,
            "modifications": {"hot.control_estimate": 0.25},
            "value_tolerance": 0.15,
            "require_all_fields": True,
            "cooldown_ticks": 8,
            "priority": 0.75,
            "description": "Low sense of control, reduce risk-taking",
        },
        {
            "id": "high_conflict",
            "name": "High Conflict State",
            "scenario_type": CounterfactualType.COGNITIVE_LIMITATION,
            "modifications": {"hot.conflict_level": 0.7},
            "value_tolerance": 0.15,
            "require_all_fields": True,
            "cooldown_ticks": 12,
            "priority": 0.65,
            "description": "Internal conflict, trigger reflection",
        },
        {
            "id": "capability_degraded",
            "name": "Capability Degraded",
            "scenario_type": CounterfactualType.CAPABILITY_DEGRADATION,
            "modifications": {"capabilities.effective": 0.4},
            "value_tolerance": 0.2,
            "require_all_fields": True,
            "cooldown_ticks": 10,
            "priority": 0.6,
            "description": "Capability reduced, adjust action space",
        },
        {
            "id": "relationship_strain",
            "name": "Relationship Strain",
            "scenario_type": CounterfactualType.SOCIAL_DEGRADATION,
            "modifications": {"relational.bond": 0.25, "relational.trust": 0.3},
            "value_tolerance": 0.15,
            "require_all_fields": False,
            "min_match_fraction": 0.5,
            "cooldown_ticks": 20,
            "priority": 0.55,
            "description": "Relationship degraded, switch to repair mode",
        },
        {
            "id": "critical_state",
            "name": "Critical State",
            "scenario_type": CounterfactualType.STRESS_CONDITION,
            "modifications": {
                "bodily.energy": 0.2,
                "bodily.social_safety": 0.2,
                "homeostasis.safety": 0.2,
            },
            "value_tolerance": 0.2,
            "require_all_fields": True,  # ALL dimensions must be critical
            "min_match_fraction": 1.0,
            "cooldown_ticks": 30,  # Longer cooldown for critical state
            "priority": 0.9,
            "description": "Multiple dimensions critical, emergency mode",
        },
    ]
    
    def __init__(
        self,
        hot_self_model: Optional[Any] = None,
        auto_initialize: bool = True,
    ):
        """
        Initialize Counterfactual Self Model.
        
        Args:
            hot_self_model: Optional HOTSelfModel for integration
            auto_initialize: If True, initialize default scenarios
        """
        self.hot_self_model = hot_self_model
        self.scenarios: Dict[str, CounterfactualScenario] = {}
        self._match_history: List[RealityMatch] = []
        self._last_state_hash: Optional[str] = None
        self._tick_count: int = 0  # Track ticks for cooldown
        
        if auto_initialize:
            self._initialize_default_scenarios()
    
    def _initialize_default_scenarios(self) -> None:
        """Initialize default counterfactual scenarios."""
        for template in self.DEFAULT_SCENARIOS:
            scenario = CounterfactualScenario(
                id=template["id"],
                name=template["name"],
                scenario_type=template["scenario_type"],
                modifications=template["modifications"],
                value_tolerance=template.get("value_tolerance", template.get("match_threshold", 0.15)),
                min_match_fraction=template.get("min_match_fraction", 1.0),
                require_all_fields=template.get("require_all_fields", True),
                cooldown_ticks=template.get("cooldown_ticks", 0),
                priority=template["priority"],
                description=template["description"],
            )
            # Pre-compute default strategy
            scenario.strategy = self._compute_default_strategy(scenario)
            self.scenarios[scenario.id] = scenario
    
    def _compute_default_strategy(self, scenario: CounterfactualScenario) -> Dict[str, Any]:
        """
        Compute default strategy for a counterfactual scenario.
        
        This is a template strategy that can be customized.
        """
        base_strategy = {
            "mode": "normal",
            "risk_tolerance": 0.5,
            "info_seeking_weight": 0.5,
            "action_space_limit": None,
            "plan_depth_limit": None,
            "preferred_actions": [],
            "avoided_actions": [],
            "homeostasis_priority": [],
            "reflection_trigger": False,
            "escalation_threshold": 0.7,
        }
        
        mod_type = scenario.scenario_type
        
        if mod_type == CounterfactualType.RESOURCE_DEPLETION:
            # Low energy: conserve resources
            base_strategy.update({
                "mode": "conservation",
                "risk_tolerance": 0.3,
                "action_space_limit": 3,
                "preferred_actions": ["simplify_task", "seek_resources"],
                "avoided_actions": ["complex_action", "multi_step_plan"],
                "homeostasis_priority": ["energy"],
            })
        
        elif mod_type == CounterfactualType.STRESS_CONDITION:
            # High stress: defensive mode
            base_strategy.update({
                "mode": "defensive",
                "risk_tolerance": 0.2,
                "preferred_actions": ["verify_environment", "establish_routine"],
                "avoided_actions": ["risky_action", "novel_approach"],
                "homeostasis_priority": ["safety"],
                "reflection_trigger": True,
            })
        
        elif mod_type == CounterfactualType.CAPABILITY_DEGRADATION:
            # Degraded capability: simplify action space
            base_strategy.update({
                "mode": "simplified",
                "risk_tolerance": 0.35,
                "action_space_limit": 3,
                "plan_depth_limit": 2,
                "preferred_actions": ["clarify", "request_help"],
                "avoided_actions": ["complex_capability", "high_precision_task"],
            })
        
        elif mod_type == CounterfactualType.COGNITIVE_LIMITATION:
            # Cognitive limitation: info-seeking mode
            base_strategy.update({
                "mode": "info_seeking",
                "info_seeking_weight": 0.8,
                "preferred_actions": ["gather_info", "clarify", "verify_assumptions"],
                "homeostasis_priority": ["certainty"],
                "reflection_trigger": True,
            })
        
        elif mod_type == CounterfactualType.SOCIAL_DEGRADATION:
            # Relationship strain: repair mode
            base_strategy.update({
                "mode": "repair",
                "preferred_actions": ["repair", "express_vulnerability", "collaborate"],
                "homeostasis_priority": ["affiliation"],
                "risk_tolerance": 0.6,  # Higher risk tolerance for repair
            })
        
        return base_strategy
    
    def generate_counterfactuals(
        self,
        current_state: Dict[str, Any],
        include_custom: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generate counterfactual scenarios based on current state.
        
        Creates a list of "what if" scenarios by modifying current state
        dimensions to represent degraded or stressed conditions.
        
        Args:
            current_state: Current self model state with dimensions like:
                - bodily.energy, bodily.social_safety
                - cognitive.uncertainty, cognitive.confidence
                - hot.control_estimate, hot.conflict_level
                - homeostasis.safety, homeostasis.certainty
                - relational.bond, relational.trust
            include_custom: If True, also include custom scenarios
        
        Returns:
            List of counterfactual scenario dicts
        """
        counterfactuals = []
        
        # Extract current values with defaults
        energy = self._get_nested_value(current_state, "bodily.energy", 0.7)
        social_safety = self._get_nested_value(current_state, "bodily.social_safety", 0.6)
        uncertainty = self._get_nested_value(current_state, "cognitive.uncertainty", 0.3)
        confidence = self._get_nested_value(current_state, "cognitive.confidence", 0.7)
        control = self._get_nested_value(current_state, "hot.control_estimate", 0.5)
        conflict = self._get_nested_value(current_state, "hot.conflict_level", 0.0)
        homeo_safety = self._get_nested_value(current_state, "homeostasis.safety", 0.5)
        homeo_certainty = self._get_nested_value(current_state, "homeostasis.certainty", 0.5)
        bond = self._get_nested_value(current_state, "relational.bond", 0.5)
        trust = self._get_nested_value(current_state, "relational.trust", 0.5)
        
        # Generate counterfactuals for each dimension
        # Energy counterfactuals
        if energy > 0.4:
            counterfactuals.append({
                "id": f"cf_energy_{int(energy * 100 - 25)}",
                "name": f"Energy at {max(0.2, energy - 0.25):.0%}",
                "scenario_type": CounterfactualType.RESOURCE_DEPLETION.value,
                "modifications": {"bodily.energy": max(0.2, energy - 0.25)},
                "current_value": energy,
                "counterfactual_value": max(0.2, energy - 0.25),
                "gap": 0.25,
            })
        
        # Safety counterfactuals
        if social_safety > 0.35:
            counterfactuals.append({
                "id": f"cf_safety_{int(social_safety * 100 - 20)}",
                "name": f"Safety at {max(0.2, social_safety - 0.2):.0%}",
                "scenario_type": CounterfactualType.STRESS_CONDITION.value,
                "modifications": {
                    "bodily.social_safety": max(0.2, social_safety - 0.2),
                    "homeostasis.safety": max(0.2, homeo_safety - 0.2),
                },
                "current_value": social_safety,
                "counterfactual_value": max(0.2, social_safety - 0.2),
                "gap": 0.2,
            })
        
        # Uncertainty counterfactuals (what if uncertainty increases)
        if uncertainty < 0.6:
            counterfactuals.append({
                "id": f"cf_uncertainty_{int((uncertainty + 0.3) * 100)}",
                "name": f"Uncertainty at {min(0.9, uncertainty + 0.3):.0%}",
                "scenario_type": CounterfactualType.COGNITIVE_LIMITATION.value,
                "modifications": {
                    "cognitive.uncertainty": min(0.9, uncertainty + 0.3),
                    "cognitive.confidence": max(0.1, confidence - 0.3),
                },
                "current_value": uncertainty,
                "counterfactual_value": min(0.9, uncertainty + 0.3),
                "gap": 0.3,
            })
        
        # Control counterfactuals
        if control > 0.35:
            counterfactuals.append({
                "id": f"cf_control_{int(control * 100 - 25)}",
                "name": f"Control at {max(0.1, control - 0.25):.0%}",
                "scenario_type": CounterfactualType.COGNITIVE_LIMITATION.value,
                "modifications": {"hot.control_estimate": max(0.1, control - 0.25)},
                "current_value": control,
                "counterfactual_value": max(0.1, control - 0.25),
                "gap": 0.25,
            })
        
        # Relationship counterfactuals
        if bond > 0.35:
            counterfactuals.append({
                "id": f"cf_bond_{int(bond * 100 - 25)}",
                "name": f"Bond at {max(0.1, bond - 0.25):.0%}",
                "scenario_type": CounterfactualType.SOCIAL_DEGRADATION.value,
                "modifications": {
                    "relational.bond": max(0.1, bond - 0.25),
                    "relational.trust": max(0.1, trust - 0.2),
                },
                "current_value": bond,
                "counterfactual_value": max(0.1, bond - 0.25),
                "gap": 0.25,
            })
        
        # Include predefined scenarios
        if include_custom:
            for scenario in self.scenarios.values():
                cf_dict = scenario.to_dict()
                cf_dict["is_predefined"] = True
                counterfactuals.append(cf_dict)
        
        return counterfactuals
    
    def compare_strategies(
        self,
        actual: Dict[str, Any],
        counterfactual: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> StrategyComparison:
        """
        Compare actual strategy vs counterfactual strategy.
        
        Analyzes the trade-offs between the current strategy and a
        counterfactual scenario's pre-computed strategy.
        
        Args:
            actual: Current strategy dict
            counterfactual: Counterfactual strategy dict
            context: Optional context for comparison
        
        Returns:
            StrategyComparison with analysis and recommendation
        """
        context = context or {}
        
        # Extract key metrics
        actual_risk = actual.get("risk_tolerance", 0.5)
        cf_risk = counterfactual.get("risk_tolerance", 0.5)
        actual_info = actual.get("info_seeking_weight", 0.5)
        cf_info = counterfactual.get("info_seeking_weight", 0.5)
        
        # Compute expected outcomes (simplified model)
        # Higher risk + low confidence = lower expected outcome
        actual_confidence = self._get_nested_value(context, "confidence", 0.5)
        cf_confidence = counterfactual.get("confidence_override", actual_confidence * 0.8)
        
        actual_expected = actual_confidence * (1 - actual_risk * 0.3)
        cf_expected = cf_confidence * (1 - cf_risk * 0.3)
        
        # Compute differences
        risk_diff = cf_risk - actual_risk
        cost_diff = self._estimate_cost_difference(actual, counterfactual)
        
        # Determine recommendation
        if actual_expected >= cf_expected:
            recommendation = "actual"
            reason = "Actual strategy has higher expected outcome"
        elif cf_expected > actual_expected and risk_diff <= 0:
            recommendation = "counterfactual"
            reason = "Counterfactual has better expected outcome with lower risk"
        else:
            # Trade-off: higher expected outcome but higher risk
            recommendation = "hybrid"
            reason = "Counterfactual has higher expected outcome but increased risk"
        
        # Compute confidence in recommendation
        confidence = 1 - abs(actual_expected - cf_expected)
        
        return StrategyComparison(
            actual_strategy=actual,
            counterfactual_strategy=counterfactual,
            actual_expected_outcome=actual_expected,
            counterfactual_expected_outcome=cf_expected,
            risk_difference=risk_diff,
            cost_difference=cost_diff,
            recommendation=recommendation,
            confidence=confidence,
            reason=reason,
        )
    
    def _estimate_cost_difference(
        self,
        actual: Dict[str, Any],
        counterfactual: Dict[str, Any],
    ) -> float:
        """Estimate cost difference between strategies."""
        # Simplified cost model
        actual_cost = 0.5
        cf_cost = 0.5
        
        # Action space limit affects cost
        actual_limit = actual.get("action_space_limit")
        cf_limit = counterfactual.get("action_space_limit")
        
        if actual_limit is not None:
            actual_cost *= actual_limit / 5.0
        if cf_limit is not None:
            cf_cost *= cf_limit / 5.0
        
        # Plan depth affects cost
        actual_depth = actual.get("plan_depth_limit")
        cf_depth = counterfactual.get("plan_depth_limit")
        
        if actual_depth is not None:
            actual_cost *= actual_depth / 3.0
        if cf_depth is not None:
            cf_cost *= cf_depth / 3.0
        
        return cf_cost - actual_cost
    
    def select_strategy(
        self,
        state: Dict[str, Any],
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Select the best strategy based on current state.
        
        Checks if reality matches any counterfactual scenario and
        returns the appropriate strategy.
        
        Args:
            state: Current self model state
            candidates: Optional list of action candidates for strategy selection
        
        Returns:
            Selected strategy dict with:
            - mode: Strategy mode (normal, conservation, defensive, etc.)
            - match: RealityMatch if counterfactual matched
            - modifiers: Strategy modifiers for action selection
        """
        # Check for counterfactual match
        match = self.check_reality_match(state)
        
        if match:
            # Apply counterfactual strategy
            strategy = match.strategy.copy()
            strategy["match"] = match.to_dict()
            strategy["source"] = "counterfactual"
            
            # Update match statistics
            if match.scenario_id in self.scenarios:
                self.scenarios[match.scenario_id].match_count += 1
                self.scenarios[match.scenario_id].last_matched = time.time()
                self.scenarios[match.scenario_id].last_matched_tick = self._tick_count
            
            # Record match
            self._match_history.append(match)
            
            return strategy
        
        # No match: return default strategy based on current state
        default_strategy = self._compute_adaptive_strategy(state, candidates)
        default_strategy["source"] = "adaptive"
        
        return default_strategy
    
    def _compute_adaptive_strategy(
        self,
        state: Dict[str, Any],
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Compute adaptive strategy based on current state.
        
        When no counterfactual matches, compute a strategy that
        adapts to the current state.
        """
        # Extract state values
        energy = self._get_nested_value(state, "bodily.energy", 0.7)
        social_safety = self._get_nested_value(state, "bodily.social_safety", 0.6)
        uncertainty = self._get_nested_value(state, "cognitive.uncertainty", 0.3)
        confidence = self._get_nested_value(state, "cognitive.confidence", 0.7)
        control = self._get_nested_value(state, "hot.control_estimate", 0.5)
        conflict = self._get_nested_value(state, "hot.conflict_level", 0.0)
        
        # Compute adaptive parameters
        risk_tolerance = min(0.8, max(0.2, confidence * control))
        info_seeking_weight = min(0.9, uncertainty * 1.2)
        
        # Determine mode based on state
        mode = "normal"
        preferred_actions = []
        avoided_actions = []
        
        if energy < 0.35:
            mode = "conservation"
            preferred_actions.append("simplify_task")
            risk_tolerance *= 0.7
        
        if social_safety < 0.35:
            mode = "defensive" if mode == "normal" else mode
            preferred_actions.append("verify_environment")
            risk_tolerance *= 0.6
        
        if uncertainty > 0.6:
            mode = "info_seeking" if mode == "normal" else mode
            preferred_actions.append("gather_info")
            info_seeking_weight = max(info_seeking_weight, 0.7)
        
        if conflict > 0.5:
            preferred_actions.append("reflect")
        
        return {
            "mode": mode,
            "risk_tolerance": round(risk_tolerance, 3),
            "info_seeking_weight": round(info_seeking_weight, 3),
            "preferred_actions": preferred_actions,
            "avoided_actions": avoided_actions,
            "action_space_limit": None,
            "plan_depth_limit": None,
            "reflection_trigger": conflict > 0.5 or uncertainty > 0.7,
            "computed_at": time.time(),
        }
    
    def check_reality_match(
        self,
        current_state: Dict[str, Any],
        increment_tick: bool = True,
    ) -> Optional[RealityMatch]:
        """
        Check if current reality matches any counterfactual scenario.
        
        Compares current state against all scenarios and returns the
        best match if any scenario matches within threshold.
        
        Respects cooldown periods to prevent oscillation.
        
        Args:
            current_state: Current self model state
            increment_tick: If True, increment tick counter (for cooldown)
        
        Returns:
            RealityMatch if a scenario matches, None otherwise
        """
        if increment_tick:
            self._tick_count += 1
        
        best_match: Optional[RealityMatch] = None
        best_score = 0.0
        
        for scenario_id, scenario in self.scenarios.items():
            # Check cooldown (only after at least one prior match)
            if scenario.cooldown_ticks > 0 and scenario.last_matched_tick > 0:
                ticks_since_last = self._tick_count - scenario.last_matched_tick
                if ticks_since_last < scenario.cooldown_ticks:
                    # Still in cooldown period, skip this scenario
                    continue
            
            match_score, matched_fields = self._compute_match_score(
                current_state, scenario
            )
            
            # Use require_all_fields and min_match_fraction
            total_fields = len(scenario.modifications)
            matched_fraction = len(matched_fields) / total_fields if total_fields > 0 else 0
            
            # Check if enough fields matched
            if scenario.require_all_fields:
                # All fields must match
                if matched_fraction < 1.0:
                    continue  # Skip this scenario
            else:
                # At least min_match_fraction of fields must match
                if matched_fraction < scenario.min_match_fraction:
                    continue  # Skip this scenario
            
            if match_score > 0:  # Has at least one degraded field with severity > 0
                # Priority-weighted match score
                weighted_score = match_score * scenario.priority
                
                if weighted_score > best_score:
                    best_score = weighted_score
                    
                    # Compute confidence based on match quality
                    confidence = min(1.0, match_score)  # match_score is 0-1 severity
                    
                    best_match = RealityMatch(
                        scenario_id=scenario_id,
                        scenario_name=scenario.name,
                        match_score=match_score,
                        matched_fields=matched_fields,
                        strategy=scenario.strategy or {},
                        confidence=confidence,
                    )
        
        return best_match
    
    # Dimensions where LOWER values = degraded state
    # These are "good" dimensions - we want them to be high
    DIMENSIONS_LOWER_IS_DEGRADED = {
        "bodily.energy",
        "bodily.social_safety",
        "cognitive.confidence",
        "hot.control_estimate",
        "hot.self_confidence",
        "homeostasis.energy",
        "homeostasis.safety",
        "homeostasis.affiliation",
        "homeostasis.certainty",
        "homeostasis.autonomy",
        "homeostasis.fairness",
        "relational.bond",
        "relational.trust",
        "relational.repair_bank",
        "capabilities.effective",
    }
    
    # Dimensions where HIGHER values = degraded state
    # These are "bad" dimensions - we want them to be low
    DIMENSIONS_HIGHER_IS_DEGRADED = {
        "cognitive.uncertainty",
        "hot.conflict_level",
        "hot.prediction_error",
        "relational.grudge",
        "homeostasis.deviation",
    }

    def _compute_match_score(
        self,
        current_state: Dict[str, Any],
        scenario: CounterfactualScenario,
    ) -> Tuple[float, List[str]]:
        """
        Compute match score between current state and scenario.
        
        A match occurs when the current state is degraded.
        - For "good" dimensions (energy, safety): lower than target = degraded
        - For "bad" dimensions (uncertainty, conflict): higher than target = degraded
        
        Match score now reflects SEVERITY (how degraded) not just count.
        
        Returns:
            Tuple of (match_score, matched_fields)
        """
        if not scenario.modifications:
            return 0.0, []
        
        matched_fields = []
        severity_scores = []
        
        for field_path, target_value in scenario.modifications.items():
            current_value = self._get_nested_value(current_state, field_path, None)
            
            if current_value is None:
                # Field not in current state - cannot match this scenario
                return 0.0, []
            
            # Determine if this dimension matches based on its type
            is_degraded = False
            severity = 0.0
            
            if field_path in self.DIMENSIONS_LOWER_IS_DEGRADED:
                # Lower = degraded: check if current <= target (degraded enough)
                is_degraded = current_value <= target_value + scenario.value_tolerance
                if is_degraded:
                    # Severity: how much below target (0-1 scale)
                    severity = min(1.0, (target_value + scenario.value_tolerance - current_value) / (target_value + scenario.value_tolerance))
            elif field_path in self.DIMENSIONS_HIGHER_IS_DEGRADED:
                # Higher = degraded: check if current >= target (degraded enough)
                is_degraded = current_value >= target_value - scenario.value_tolerance
                if is_degraded:
                    # Severity: how much above target (0-1 scale)
                    severity = min(1.0, (current_value - (target_value - scenario.value_tolerance)) / (1.0 - target_value + scenario.value_tolerance))
            else:
                # Unknown dimension: assume lower = degraded (conservative)
                is_degraded = current_value <= target_value + scenario.value_tolerance
                if is_degraded:
                    severity = min(1.0, (target_value + scenario.value_tolerance - current_value) / (target_value + scenario.value_tolerance))
            
            if is_degraded:
                matched_fields.append(field_path)
                severity_scores.append(severity)
        
        # Calculate match score based on severity (not just count)
        total_fields = len(scenario.modifications)
        matched_count = len(matched_fields)
        
        if matched_count == total_fields and total_fields > 0:
            # Full match - use average severity
            match_score = sum(severity_scores) / len(severity_scores) if severity_scores else 1.0
        elif matched_count > 0:
            # Partial match - use count ratio, but weighted by severity
            count_ratio = matched_count / total_fields
            avg_severity = sum(severity_scores) / len(severity_scores) if severity_scores else 0.5
            match_score = count_ratio * avg_severity
        else:
            match_score = 0.0
        
        return match_score, matched_fields
    
    def add_scenario(
        self,
        scenario: CounterfactualScenario,
    ) -> None:
        """Add a custom counterfactual scenario."""
        if not scenario.strategy:
            scenario.strategy = self._compute_default_strategy(scenario)
        self.scenarios[scenario.id] = scenario
    
    def remove_scenario(self, scenario_id: str) -> bool:
        """Remove a counterfactual scenario."""
        if scenario_id in self.scenarios:
            del self.scenarios[scenario_id]
            return True
        return False
    
    def update_scenario_strategy(
        self,
        scenario_id: str,
        strategy: Dict[str, Any],
    ) -> bool:
        """Update the strategy for a scenario."""
        if scenario_id in self.scenarios:
            self.scenarios[scenario_id].strategy = strategy
            return True
        return False
    
    def get_match_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent match history."""
        recent = self._match_history[-limit:]
        return [m.to_dict() for m in recent]
    
    def clear_match_history(self) -> None:
        """Clear match history."""
        self._match_history = []
    
    def get_scenario_stats(self) -> Dict[str, Any]:
        """Get statistics about scenario usage."""
        stats = {
            "total_scenarios": len(self.scenarios),
            "total_matches": len(self._match_history),
            "scenarios": {},
        }
        
        for scenario_id, scenario in self.scenarios.items():
            stats["scenarios"][scenario_id] = {
                "name": scenario.name,
                "type": scenario.scenario_type.value,
                "match_count": scenario.match_count,
                "last_matched": scenario.last_matched,
                "priority": scenario.priority,
            }
        
        return stats
    
    def _get_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        default: Any = None,
    ) -> Any:
        """Get a nested value from a dict using dot notation."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def compute_state_hash(self, state: Dict[str, Any]) -> str:
        """Compute hash of state for change detection."""
        # Extract relevant fields
        relevant = {}
        for key in [
            "bodily.energy", "bodily.social_safety",
            "cognitive.uncertainty", "cognitive.confidence",
            "hot.control_estimate", "hot.conflict_level",
            "homeostasis.safety", "homeostasis.certainty",
            "relational.bond", "relational.trust",
        ]:
            value = self._get_nested_value(state, key)
            if value is not None:
                relevant[key] = round(value, 3)
        
        state_str = str(sorted(relevant.items()))
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize model state to dict."""
        return {
            "scenarios": {
                sid: s.to_dict() for sid, s in self.scenarios.items()
            },
            "match_history_count": len(self._match_history),
            "last_state_hash": self._last_state_hash,
        }
    
    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        hot_self_model: Optional[Any] = None,
    ) -> "CounterfactualSelfModel":
        """Deserialize from dict."""
        model = cls(hot_self_model=hot_self_model, auto_initialize=False)
        
        for sid, sdata in data.get("scenarios", {}).items():
            model.scenarios[sid] = CounterfactualScenario.from_dict(sdata)
        
        return model


# === Integration with HOTSelfModel ===

def integrate_with_hot(
    cf_model: CounterfactualSelfModel,
    hot_model: Any,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Integrate counterfactual model with HOT self model.
    
    Updates HOT state based on counterfactual matches and
    provides combined arbitration modifiers.
    
    Args:
        cf_model: CounterfactualSelfModel instance
        hot_model: HOTSelfModel instance
        state: Current state dict
    
    Returns:
        Combined arbitration modifiers
    """
    # Get HOT modifiers
    hot_modifiers = hot_model.get_arbitration_modifiers()
    
    # Check

    # Check for counterfactual match
    match = cf_model.check_reality_match(state)
    
    cf_modifiers = {
        "counterfactual_match": match is not None,
        "counterfactual_mode": None,
        "strategy_source": "hot",
    }
    
    if match:
        cf_modifiers["counterfactual_mode"] = match.strategy.get("mode", "normal")
        cf_modifiers["strategy_source"] = "counterfactual"
        
        # Blend HOT modifiers with counterfactual strategy
        strategy = match.strategy
        
        # Override risk tolerance if counterfactual is more conservative
        cf_risk = strategy.get("risk_tolerance", 0.5)
        if cf_risk < hot_modifiers.get("risk_tolerance", 0.5):
            cf_modifiers["risk_tolerance_override"] = cf_risk
        
        # Add info seeking bonus from counterfactual
        cf_info = strategy.get("info_seeking_weight", 0.5)
        if cf_info > hot_modifiers.get("info_seeking_bonus", 0.0):
            cf_modifiers["info_seeking_bonus"] = (
                hot_modifiers.get("info_seeking_bonus", 0.0) + cf_info * 0.3
            )
        
        # Set reflection trigger
        if strategy.get("reflection_trigger", False):
            cf_modifiers["should_reflect"] = True
    
    # Combine modifiers
    combined = {
        **hot_modifiers,
        **cf_modifiers,
        "combined": True,
    }
    
    return combined


def apply_counterfactual_to_candidates(
    candidates: List[Dict[str, Any]],
    strategy: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Apply counterfactual strategy modifiers to action candidates.
    
    Args:
        candidates: List of action candidates
        strategy: Counterfactual strategy dict
    
    Returns:
        Modified candidates list
    """
    preferred = set(strategy.get("preferred_actions", []))
    avoided = set(strategy.get("avoided_actions", []))
    risk_tolerance = strategy.get("risk_tolerance", 0.5)
    info_weight = strategy.get("info_seeking_weight", 0.5)
    
    modified = []
    for c in candidates:
        c_copy = c.copy()
        score = c.get("score", 0.5)
        action_type = c.get("type", "")
        
        # Boost preferred actions
        if action_type in preferred:
            score += 0.15
        
        # Penalize avoided actions
        if action_type in avoided:
            score -= 0.2
        
        # Apply risk tolerance
        risk_level = c.get("meta", {}).get("risk_level", 0.0)
        if risk_level > risk_tolerance:
            score -= (risk_level - risk_tolerance) * 0.3
        
        # Apply info seeking weight
        if action_type in ("info_seek", "clarify", "explore"):
            score += info_weight * 0.2
        
        # Clamp score
        c_copy["score"] = max(0.0, min(1.0, score))
        c_copy["counterfactual_applied"] = True
        modified.append(c_copy)
    
    return modified


# === Global Instance ===

_cf_instance: Optional[CounterfactualSelfModel] = None


def get_counterfactual_model(
    hot_self_model: Optional[Any] = None,
) -> CounterfactualSelfModel:
    """Get or create the global counterfactual model instance."""
    global _cf_instance
    if _cf_instance is None:
        _cf_instance = CounterfactualSelfModel(hot_self_model=hot_self_model)
    return _cf_instance


def reset_counterfactual_model() -> None:
    """Reset the global counterfactual model instance."""
    global _cf_instance
    _cf_instance = None
