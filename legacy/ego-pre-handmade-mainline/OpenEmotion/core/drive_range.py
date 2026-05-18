"""
Drive range definition for homeostasis system.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class DriveRange:
    """Range specification for drive setpoints."""
    min: float
    max: float
    
    def __post_init__(self):
        if not 0.0 <= self.min <= 1.0:
            raise ValueError(f"DriveRange min must be in [0,1], got {self.min}")
        if not 0.0 <= self.max <= 1.0:
            raise ValueError(f"DriveRange max must be in [0,1], got {self.max}")
        if self.min > self.max:
            raise ValueError(f"DriveRange min ({self.min}) cannot be greater than max ({self.max})")
    
    def contains(self, value: float) -> bool:
        """Check if value is within range."""
        return self.min <= value <= self.max
    
    def distance_to_range(self, value: float) -> float:
        """Compute distance from value to nearest range bound."""
        if self.contains(value):
            return 0.0
        elif value < self.min:
            return self.min - value
        else:
            return value - self.max
    
    def normalize_value(self, value: float) -> float:
        """Normalize value relative to range (0=at min, 1=at max)."""
        if self.max == self.min:
            return 0.5  # Center of degenerate range
        return (value - self.min) / (self.max - self.min)
    
    @classmethod
    def from_tuple(cls, range_tuple: Tuple[float, float]) -> "DriveRange":
        """Create DriveRange from tuple."""
        return cls(min=range_tuple[0], max=range_tuple[1])
    
    def to_tuple(self) -> Tuple[float, float]:
        """Convert to tuple."""
        return (self.min, self.max)
