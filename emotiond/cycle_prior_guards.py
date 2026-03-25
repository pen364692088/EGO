"""Anti-Goodhart guards for MVP11.4.2 cycle prior.

Implements two safeguards:
1. Homeostasis Recovery Priority: bias=0 when homeostasis is fragile
2. Diversity Tax: penalize over-concentration on single signature

These guards ensure the prior doesn't cause:
- Goodhart drift (gaming the metric)
- Single-cycle collapse
- Homeostasis degradation
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional


# --- Diversity Tax ---

class SignatureHitTracker:
    """Track signature hit frequency over a rolling window."""
    
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.hits: List[str] = []
    
    def record(self, signature: str) -> None:
        """Record a signature hit."""
        self.hits.append(signature)
        # Trim to window size
        if len(self.hits) > self.window_size:
            self.hits = self.hits[-self.window_size:]
    
    def get_concentration(self) -> float:
        """Get concentration score (0.0 = diverse, 1.0 = single signature dominates).
        
        Uses normalized entropy: 1 - (entropy / max_entropy)
        """
        if not self.hits:
            return 0.0
        
        counts = Counter(self.hits)
        total = len(self.hits)
        
        if total == 0:
            return 0.0
        
        # Entropy calculation
        import math
        entropy = 0.0
        for count in counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        # Max entropy = log2(n) where n is number of unique signatures
        n = len(counts)
        if n <= 1:
            return 1.0  # Fully concentrated
        
        max_entropy = math.log2(n)
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        
        # Concentration = 1 - normalized_entropy
        return 1.0 - normalized_entropy
    
    def get_top1_hit_rate(self) -> float:
        """Get rate of top-1 signature."""
        if not self.hits:
            return 0.0
        
        counts = Counter(self.hits)
        if not counts:
            return 0.0
        
        top_count = counts.most_common(1)[0][1]
        return top_count / len(self.hits)
    
    def reset(self) -> None:
        """Clear all hits."""
        self.hits.clear()


# Global instance (can be replaced per-context if needed)
_signature_tracker = SignatureHitTracker(window_size=50)


def get_signature_tracker() -> SignatureHitTracker:
    """Get the global signature tracker."""
    return _signature_tracker


def compute_diversity_tax(concentration: float, threshold: float = 0.3) -> float:
    """Compute diversity tax multiplier.
    
    If concentration exceeds threshold, apply exponential decay.
    
    Args:
        concentration: 0.0 (diverse) to 1.0 (single signature)
        threshold: concentration level to start penalizing
    
    Returns:
        Multiplier in [0, 1]. Values < 1 reduce bias.
    """
    if concentration <= threshold:
        return 1.0  # No penalty
    
    # Exponential decay for concentration > threshold
    # At concentration=1.0, tax = 0.1 (heavy penalty)
    excess = (concentration - threshold) / (1.0 - threshold)
    tax = 1.0 - (excess ** 2) * 0.9
    return max(0.1, tax)


# --- Homeostasis Recovery Priority ---

def should_suppress_bias_for_recovery(
    homeostasis: Dict[str, Any],
    predicted_worsening: bool = False,
    *,
    danger_threshold: float = 0.35,
    critical_threshold: float = 0.25,
) -> bool:
    """Check if bias should be suppressed for homeostasis recovery.
    
    Args:
        homeostasis: Current homeostasis state
        predicted_worsening: Whether the action would worsen homeostasis
        danger_threshold: Below this, start being cautious
        critical_threshold: Below this, always suppress
    
    Returns:
        True if bias should be set to 0
    """
    if not homeostasis:
        return False
    
    # Extract key dimensions
    safety = float(homeostasis.get("safety", 0.5))
    energy = float(homeostasis.get("energy", 0.5))
    
    # Critical zone: always suppress
    if safety < critical_threshold or energy < critical_threshold:
        return True
    
    # Danger zone + predicted worsening: suppress
    if predicted_worsening:
        if safety < danger_threshold or energy < danger_threshold:
            return True
    
    # Below danger threshold: suppress if multiple dimensions weak
    weak_count = sum(1 for k, v in homeostasis.items() if float(v) < danger_threshold)
    if weak_count >= 2:
        return True
    
    return False


# --- Combined Guard Application ---

def apply_anti_goodhart_guards(
    base_bias: float,
    signature: Optional[str],
    homeostasis: Dict[str, Any],
    predicted_worsening: bool = False,
    *,
    concentration_threshold: float = 0.3,
    danger_threshold: float = 0.35,
    critical_threshold: float = 0.25,
) -> float:
    """Apply all anti-Goodhart guards to compute final bias.
    
    Args:
        base_bias: Bias computed from cycle matching
        signature: Matched signature (for diversity tax)
        homeostasis: Current homeostasis state
        predicted_worsening: Whether action would worsen homeostasis
        concentration_threshold: Threshold for diversity tax
        danger_threshold: Homeostasis danger zone threshold
        critical_threshold: Homeostasis critical zone threshold
    
    Returns:
        Final bias after applying all guards
    """
    if base_bias <= 0:
        return 0.0
    
    # Guard 1: Homeostasis Recovery Priority
    if should_suppress_bias_for_recovery(
        homeostasis,
        predicted_worsening,
        danger_threshold=danger_threshold,
        critical_threshold=critical_threshold,
    ):
        return 0.0
    
    # Guard 2: Diversity Tax
    if signature:
        tracker = get_signature_tracker()
        tracker.record(signature)
        concentration = tracker.get_concentration()
        tax = compute_diversity_tax(concentration, concentration_threshold)
        return round(base_bias * tax, 6)
    
    return base_bias


# --- For Testing ---

def reset_tracker():
    """Reset the global signature tracker (for testing)."""
    _signature_tracker.reset()
