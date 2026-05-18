"""
Homeostasis Drive v0 - MVP-7 US-651

Drive system that maintains setpoints and influences decision-making.
Provides engineering version of homeostasis/free-energy principle.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import time
from enum import Enum
from collections import deque
from datetime import datetime

from .drive_range import DriveRange


class DriveType(Enum):
    ENERGY = "energy"
    UNCERTAINTY = "uncertainty"
    SOCIAL = "social"
    SAFETY = "safety"
    FATIGUE = "fatigue"


@dataclass
class DriveState:
    """Current state of all drives with their setpoints and values."""
    
    # Current values (0-1 normalized)
    energy: float = 0.8
    uncertainty: float = 0.3
    social: float = 0.7
    safety: float = 0.9
    fatigue: float = 0.2
    
    # Setpoints (optimal ranges)
    energy_setpoint: Tuple[float, float] = (0.7, 0.9)
    uncertainty_setpoint: Tuple[float, float] = (0.1, 0.3)
    social_setpoint: Tuple[float, float] = (0.6, 0.8)
    safety_setpoint: Tuple[float, float] = (0.8, 1.0)
    fatigue_setpoint: Tuple[float, float] = (0.0, 0.3)
    
    # Weights for combining drive errors
    weights: Dict[DriveType, float] = field(default_factory=lambda: {
        DriveType.ENERGY: 0.3,
        DriveType.UNCERTAINTY: 0.25,
        DriveType.SOCIAL: 0.2,
        DriveType.SAFETY: 0.15,
        DriveType.FATIGUE: 0.1
    })
    
    # Last update timestamp
    last_update: float = field(default_factory=time.time)
    
    def update_value(self, drive_type: DriveType, value: float) -> None:
        """Update a drive value with validation."""
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Drive value must be in [0,1], got {value}")
        
        setattr(self, drive_type.value, value)
        self.last_update = time.time()
    
    def get_value(self, drive_type: DriveType) -> float:
        """Get current value of a drive."""
        return getattr(self, drive_type.value)
    
    def get_setpoint(self, drive_type: DriveType) -> Tuple[float, float]:
        """Get setpoint range for a drive."""
        return getattr(self, f"{drive_type.value}_setpoint")

    def to_dict(self) -> Dict[str, float]:
        """Serialize current drive values for compatibility callers."""
        return {
            "energy": self.energy,
            "uncertainty": self.uncertainty,
            "social": self.social,
            "safety": self.safety,
            "fatigue": self.fatigue,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "DriveState":
        """Construct DriveState from serialized dict."""
        return cls(
            energy=float(data.get("energy", 0.8)),
            uncertainty=float(data.get("uncertainty", 0.3)),
            social=float(data.get("social", 0.7)),
            safety=float(data.get("safety", 0.9)),
            fatigue=float(data.get("fatigue", 0.2)),
        )


class HomeostasisDrive:
    """Main homeostasis drive system."""
    
    def __init__(self, initial_state: Optional[DriveState] = None):
        """Initialize with optional starting values."""
        self.state = initial_state if initial_state else DriveState()
        
        # History for trend analysis (last N updates)
        self.history = deque(maxlen=50)
        self.drive_history = deque(maxlen=100)
        self.last_update = time.time()
        
        # Huber loss delta for robust error computation
        self._huber_delta = 0.1
    
    def update_state(self, updates: Dict[str, float]) -> None:
        """Update multiple drive values at once."""
        for drive_name, value in updates.items():
            # Map legacy field names to current DriveType
            if drive_name == 'social_connection':
                drive_name = 'social'
            elif drive_name == 'clarity':
                drive_name = 'fatigue'
            
            try:
                drive_type = DriveType(drive_name)
                # Apply delta change for feedback
                current = self.state.get_value(drive_type)
                new_value = max(0.0, min(1.0, current + value))
                self.state.update_value(drive_type, new_value)
            except ValueError:
                continue
    
    def update_from_feedback(self, feedback: Dict[str, float]) -> None:
        """Update drives based on feedback (delta values)."""
        self.update_state(feedback)
    
    def _compute_drive_component(self, current: float, optimal: float, tolerance: float) -> float:
        """
        Compute individual drive component error.
        
        Args:
            current: Current drive value
            optimal: Optimal drive value  
            tolerance: Acceptable tolerance around optimal
            
        Returns:
            Error component in [0, 1]
        """
        deviation = abs(current - optimal)
        
        if deviation <= tolerance:
            # Within tolerance: quadratic penalty
            return (deviation / tolerance) ** 2
        else:
            # Outside tolerance: exponential penalty for large deviations
            excess = deviation - tolerance
            return 0.3 + 0.7 * (excess / (1.0 - tolerance))
    
    def _compute_drive_error(self, drive_type: DriveType) -> float:
        """
        Compute deviation from setpoint using Huber loss for robustness.
        
        Returns error in [0, 1], where 0 = perfect, 1 = maximum deviation.
        """
        value = self.state.get_value(drive_type)
        setpoint_min, setpoint_max = self.state.get_setpoint(drive_type)
        
        # If within setpoint, no error
        if setpoint_min <= value <= setpoint_max:
            return 0.0
        
        # Compute deviation from nearest setpoint bound
        if value < setpoint_min:
            deviation = setpoint_min - value
        else:
            deviation = value - setpoint_max
        
        # Normalize by maximum possible deviation (0 to 1 range)
        max_deviation = max(setpoint_min, 1.0 - setpoint_max)
        normalized_deviation = min(deviation / max_deviation, 1.0)
        
        # Apply Huber loss for robustness
        if normalized_deviation <= self._huber_delta:
            # Quadratic for small errors
            return (normalized_deviation ** 2) / (2 * self._huber_delta)
        else:
            # Linear for large errors
            return normalized_deviation - self._huber_delta / 2
    
    def drive_error(self) -> float:
        """
        Compute overall drive error as weighted sum of individual drive errors.
        
        Returns:
            Overall drive error in [0, 1]
        """
        total_error = 0.0
        total_weight = 0.0
        
        components = {}
        
        for drive_type in DriveType:
            error = self._compute_drive_error(drive_type)
            weight = self.state.weights[drive_type]
            total_error += error * weight
            total_weight += weight
            components[drive_type.value] = error
        
        overall_error = total_error / total_weight if total_weight > 0 else 0.0
        
        # Store in history
        self.drive_history.append({
            'timestamp': datetime.now(),
            'total_error': overall_error,
            'components': components
        })
        
        return overall_error
    
    def emotion_from_drive(self) -> Dict[str, float]:
        """
        Map drive states to interpretable emotion-like signals.
        
        Returns:
            Dictionary of emotion-like signals with explainable mappings.
        """
        energy = self.state.get_value(DriveType.ENERGY)
        uncertainty = self.state.get_value(DriveType.UNCERTAINTY)
        social = self.state.get_value(DriveType.SOCIAL)
        safety = self.state.get_value(DriveType.SAFETY)
        fatigue = self.state.get_value(DriveType.FATIGUE)
        
        # Explainable mappings from drives to emotion-like signals
        return {
            "confidence": energy * safety * (1 - uncertainty),  # High energy + safety + low uncertainty
            "curiosity": (1 - fatigue) * uncertainty,  # Low fatigue + high uncertainty
            "affiliation": social * energy * (1 - fatigue),  # Social + energy + not tired
            "caution": uncertainty * (1 - safety),  # High uncertainty + low safety
            "rest_need": fatigue * (1 - energy),  # Tired + low energy
        }
    
    def get_drive_modulations(self) -> Dict[str, float]:
        """
        Compute modulation factors for decision-making based on drive states.
        
        Returns:
            Dictionary of modulation factors for different cognitive processes.
        """
        energy = self.state.get_value(DriveType.ENERGY)
        uncertainty = self.state.get_value(DriveType.UNCERTAINTY)
        social = self.state.get_value(DriveType.SOCIAL)
        safety = self.state.get_value(DriveType.SAFETY)
        fatigue = self.state.get_value(DriveType.FATIGUE)
        
        return {
            # Test-compatible names with stronger effects
            "rollout_drive_bias": (1 - fatigue) * uncertainty * 0.8,
            "conservatism_factor": fatigue * (2 - safety) * 0.8,  # Stronger conservatism
            "clarification倾向": uncertainty * (1.5 - fatigue) * 0.8,  # Stronger clarification
            "social_engagement": social * energy * (1 - fatigue) * 0.6,
            "response_length_factor": energy * (1.5 - fatigue) * 0.7,
            "risk_tolerance": safety * energy * 0.8,
            "temperature_modulation": 0.7 + fatigue * 0.3,  # Higher temp when tired
            "top_p_modulation": 0.8 + uncertainty * 0.2,  # Higher top_p when uncertain
            
            # Internal names
            "exploration_bias": (1 - fatigue) * uncertainty * 0.5,
            "information_seeking": uncertainty * (1 - fatigue) * 0.7,
            "resource_conservation": fatigue * (1 - energy) * 0.9,
            "response_urgency": (1 - safety) + fatigue * 0.5,
        }
    
    def apply_drive_to_decision(self, base_strategy: str, context: Dict[str, any]) -> Dict[str, any]:
        """
        Apply drive-based modulations to a decision-making strategy.
        
        Args:
            base_strategy: The base strategy being modulated
            context: Current decision context
            
        Returns:
            Modified context with drive-based adjustments
        """
        modulations = self.get_drive_modulations()
        emotions = self.emotion_from_drive()
        
        # Add drive state to context
        context["drive_state"] = {
            "overall_error": self.drive_error(),
            "modulations": modulations,
            "emotions": emotions,
            "timestamp": self.state.last_update
        }
        
        # Apply specific modulations based on strategy
        if base_strategy == "rollout_selection" or base_strategy == "rollout_scoring":
            # Lower drive error should increase rollout scores
            drive_bonus = 1.0 - self.drive_error()
            context["drive_bias"] = drive_bonus
            context["drive_bonus"] = drive_bonus
            
        elif base_strategy == "risk_assessment":
            # Modulate risk tolerance based on drive state
            context["risk_factor"] = modulations["risk_tolerance"]
            
        elif base_strategy == "clarification":
            # Higher uncertainty should increase clarification need
            context["clarification_need"] = modulations["clarification倾向"]
            
        elif base_strategy == "response_generation":
            # Add response factors for generation
            context["response_factors"] = {
                "length_bias": modulations["response_length_factor"],
                "temperature": modulations["temperature_modulation"],
                "top_p": modulations["top_p_modulation"],
                "social": modulations["social_engagement"],
            }
        
        return context
    
    def get_state_summary(self) -> Dict[str, any]:
        """
        Get comprehensive summary of current drive state.
        
        Returns:
            Dictionary with all drive information
        """
        return {
            "drives": {
                drive_type.value: {
                    "value": self.state.get_value(drive_type),
                    "setpoint": self.state.get_setpoint(drive_type),
                    "error": self._compute_drive_error(drive_type)
                }
                for drive_type in DriveType
            },
            "emotions": self.emotion_from_drive(),
            "modulations": self.get_drive_modulations(),
            "last_update": self.state.last_update
        }
    
    def get_drive_summary(self) -> Dict[str, any]:
        """Test-compatible summary format."""
        return {
            "overall_error": self.drive_error(),
            "individual_drives": {
                drive_type.value: {
                    "value": self.state.get_value(drive_type),
                    "setpoint": self.state.get_setpoint(drive_type),
                    "error": self._compute_drive_error(drive_type)
                }
                for drive_type in DriveType
            },
            "emotions": self.emotion_from_drive(),
            "modulations": self.get_drive_modulations(),
            "last_update": self.state.last_update
        }


# Global instance for use across the system
_drive_instance: Optional[HomeostasisDrive] = None


def get_drive() -> HomeostasisDrive:
    """Get or create the global drive instance."""
    global _drive_instance
    if _drive_instance is None:
        _drive_instance = HomeostasisDrive()
    return _drive_instance


def reset_drive() -> None:
    """Reset the global drive instance (mainly for testing)."""
    global _drive_instance
    _drive_instance = None


# Legacy function for test compatibility
def drive_error(drive_state: DriveState) -> float:
    """Compute drive error for a given state (legacy function)."""
    temp_drive = HomeostasisDrive(drive_state)
    return temp_drive.drive_error()


def modulate_strategy(state: DriveState, base_strategy: str, candidates: List[str]):
    """Legacy compatibility helper for US-652/653 tests."""
    drive = HomeostasisDrive(state)
    mods = drive.get_drive_modulations()
    reasons = []

    chosen = base_strategy if base_strategy in candidates else (candidates[0] if candidates else base_strategy)

    if 'clarify' in candidates and state.uncertainty >= 0.6:
        chosen = 'clarify'
        reasons.append({'reason': 'high_uncertainty', 'value': state.uncertainty})

    if 'conservative' in candidates and state.fatigue >= 0.7 and chosen == base_strategy:
        chosen = 'conservative'
        reasons.append({'reason': 'high_fatigue', 'value': state.fatigue})

    if 'cautious' in candidates and state.safety <= 0.3 and chosen == base_strategy:
        chosen = 'cautious'
        reasons.append({'reason': 'low_safety', 'value': state.safety})

    info = {
        'drive_error': drive.drive_error(),
        'modulations': reasons,
        'raw_modulations': mods,
    }
    return chosen, info
