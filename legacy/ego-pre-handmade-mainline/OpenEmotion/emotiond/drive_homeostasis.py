"""
US-651: Homeostasis Drive v0 (drive_error)
Engineering version of homeostasis/free-energy principle
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import math
import hashlib


@dataclass
class DriveComponent:
    """Individual drive component with setpoint and current value"""
    name: str
    setpoint: float  # Optimal value (0-1)
    current: float = 0.5  # Current value (0-1)
    weight: float = 1.0  # Importance weight
    last_updated: datetime = field(default_factory=datetime.now)


class DriveState:
    """Homeostatic drive state management"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.components: Dict[str, DriveComponent] = {}
        self.history: List[Dict] = []
        
        # Initialize core drive components
        self.setpoints = {
            "energy": 0.75,      # Physical/mental energy
            "uncertainty": 0.25,  # Cognitive uncertainty (lower is better)
            "social": 0.5,       # Social connection
            "safety": 0.75,      # Safety/security
            "fatigue": 0.15,     # Fatigue (lower is better)
        }
        
        for name, setpoint in self.setpoints.items():
            self.components[name] = DriveComponent(name=name, setpoint=setpoint)
    
    def update_component(self, name: str, value: float) -> None:
        """Update a drive component value"""
        if name not in self.components:
            raise ValueError(f"Unknown drive component: {name}")
        
        # Clamp to valid range
        value = max(0.0, min(1.0, value))
        
        self.components[name].current = value
        self.components[name].last_updated = datetime.now()
        
        # Add to history
        self._add_to_history()
    
    def get_deviation(self, name: str) -> float:
        """Get deviation from setpoint for a component"""
        if name not in self.components:
            raise ValueError(f"Unknown drive component: {name}")
        
        component = self.components[name]
        return component.current - component.setpoint
    
    def get_component(self, name: str) -> DriveComponent:
        """Get a drive component"""
        return self.components.get(name)
    
    def _add_to_history(self) -> None:
        """Add current state to history"""
        # Flatten components for direct access
        snapshot = {
            "timestamp": datetime.now().isoformat(),
        }
        snapshot.update({name: comp.current for name, comp in self.components.items()})
        
        self.history.append(snapshot)
        
        # Trim history if needed
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
    
    def get_summary(self) -> Dict:
        """Get summary of current drive state"""
        return {
            "timestamp": datetime.now().isoformat(),
            "components": {
                name: {
                    "current": comp.current,
                    "setpoint": comp.setpoint,
                    "deviation": self.get_deviation(name),
                    "weight": comp.weight
                }
                for name, comp in self.components.items()
            }
        }


def huber_loss(deviation: float, delta: float = 0.1) -> float:
    """Huber loss for robust deviation handling"""
    if abs(deviation) <= delta:
        return 0.5 * deviation ** 2
    else:
        return delta * (abs(deviation) - 0.5 * delta)


def drive_error(state: DriveState) -> float:
    """
    Compute overall drive error (homeostatic deviation)
    Lower is better (0 = perfect homeostasis)
    """
    total_error = 0.0
    total_weight = 0.0
    
    for name, component in state.components.items():
        deviation = state.get_deviation(name)
        
        # Use Huber loss for robustness
        component_error = huber_loss(deviation)
        
        # Weight by component importance
        weighted_error = component_error * component.weight
        total_error += weighted_error
        total_weight += component.weight
    
    return total_error / total_weight if total_weight > 0 else 0.0


def emotion_from_drive(state: DriveState) -> str:
    """
    Map drive state to interpretable emotion description
    Provides explainable layer between drive and behavior
    """
    components = state.components
    
    # Analyze key drivers
    high_uncertainty = components["uncertainty"].current > 0.7
    low_safety = components["safety"].current < 0.3
    low_energy = components["energy"].current < 0.3
    high_fatigue = components["fatigue"].current > 0.7
    low_social = components["social"].current < 0.3
    
    # Generate emotion description
    if high_uncertainty and low_safety:
        return "anxious_fear"
    elif low_energy and high_fatigue:
        return "exhausted_withdrawn"
    elif low_social and low_safety:
        return "isolated_vulnerable"
    elif high_uncertainty and low_energy:
        return "overwhelmed_confused"
    elif not high_uncertainty and components["energy"].current > 0.7:
        return "engaged_approach"
    elif components["social"].current > 0.7 and components["safety"].current > 0.7:
        return "socially_connected_secure"
    else:
        return "neutral_balanced"


def get_drive_modulation_params(state: DriveState) -> Dict:
    """
    Convert drive state into modulation parameters for decision making
    """
    error = drive_error(state)
    
    # Base modulation from drive error
    base_modulation = {
        "risk_aversion": min(1.0, error * 2.0),  # Higher error = more risk aversion
        "clarification_need": min(1.0, error * 1.5),  # Higher error = more clarification
        "initiative_level": max(0.0, 1.0 - error),  # Higher error = less initiative
    }
    
    # Component-specific modulations
    components = state.components
    
    # Fatigue affects response length/complexity
    if components["fatigue"].current > 0.6:
        base_modulation["response_brevity"] = components["fatigue"].current
        base_modulation["complexity_preference"] = 1.0 - components["fatigue"].current
    
    # Uncertainty affects need for clarification
    if components["uncertainty"].current > 0.5:
        base_modulation["clarification_need"] = max(
            base_modulation["clarification_need"],
            components["uncertainty"].current
        )
    
    # Energy affects initiative
    if components["energy"].current < 0.3:
        base_modulation["initiative_level"] = min(
            base_modulation["initiative_level"],
            components["energy"].current
        )
    
    return base_modulation


def get_state_hash(state: DriveState) -> str:
    """Get hash of current drive state for tracking"""
    summary = state.get_summary()
    state_str = str(sorted(summary["components"].items()))
    return hashlib.sha256(state_str.encode()).hexdigest()[:16]