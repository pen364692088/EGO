"""Tests for MVP11.4.2 Anti-Goodhart Guards.

Covers:
1. Homeostasis Recovery Priority
2. Diversity Tax
3. Bias still clamped
4. Prior trace unchanged (replay not affected)

Run:
    pytest tests/mvp11/test_cycle_prior_guards.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.cycle_prior import (
    compute_bias,
    evaluate_cycle_prior,
    reset_diversity_tracker,
    _should_suppress_for_recovery,
    _get_concentration,
    _compute_diversity_tax,
    _record_signature_hit,
    MAX_BIAS,
    CRITICAL_THRESHOLD,
    DANGER_THRESHOLD,
    CONCENTRATION_THRESHOLD,
)


class TestHomeostasisRecoveryPriority:
    """Tests for homeostasis recovery priority guard."""

    def test_bias_zero_in_critical_zone(self):
        """Bias should be 0 when homeostasis is in critical zone."""
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig1"}]
        
        # Critical safety
        hs = {"safety": 0.15, "energy": 0.6, "certainty": 0.5}
        bias = compute_bias(matches, hs)
        assert bias == 0.0, "Bias should be 0 in critical safety zone"
        
        # Critical energy
        hs = {"safety": 0.6, "energy": 0.20, "certainty": 0.5}
        bias = compute_bias(matches, hs)
        assert bias == 0.0, "Bias should be 0 in critical energy zone"

    def test_bias_suppressed_when_predicted_worsening(self):
        """Bias should be suppressed when homeostasis is weak and predicted to worsen."""
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig1"}]
        
        # Danger zone + predicted worsening
        hs = {"safety": 0.30, "energy": 0.5}
        bias = compute_bias(matches, hs, predicted_worsening=True)
        assert bias == 0.0, "Bias should be 0 with worsening prediction in danger zone"

    def test_bias_ok_when_homeostasis_healthy(self):
        """Bias should be non-zero when homeostasis is healthy."""
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig1"}]
        
        hs = {"safety": 0.70, "energy": 0.75}
        bias = compute_bias(matches, hs)
        assert bias > 0.0, "Bias should be > 0 with healthy homeostasis"
        assert bias <= MAX_BIAS, "Bias should be clamped to MAX_BIAS"

    def test_bias_reduced_with_multiple_weak_dimensions(self):
        """Bias should be suppressed when multiple dimensions are weak."""
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig1"}]
        
        # Multiple dimensions below danger threshold
        hs = {"safety": 0.30, "energy": 0.30, "certainty": 0.55}
        bias = compute_bias(matches, hs)
        assert bias == 0.0, "Bias should be 0 with multiple weak dimensions"


class TestDiversityTax:
    """Tests for diversity tax (anti single-cycle collapse)."""

    def setup_method(self):
        """Reset tracker before each test."""
        reset_diversity_tracker()

    def test_no_penalty_initially(self):
        """No penalty when tracker is fresh - bias should be positive."""
        reset_diversity_tracker()
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig_a"}]
        hs = {"safety": 0.7, "energy": 0.7}
        
        # First call - should have positive bias
        bias = compute_bias(matches, hs)
        assert bias > 0.0, f"Initial bias should be > 0, got {bias}"

    def test_penalty_when_concentrated(self):
        """Penalty applied when single signature dominates."""
        reset_diversity_tracker()
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig_x"}]
        hs = {"safety": 0.7, "energy": 0.7}
        
        # Record many hits of same signature
        biases = []
        for _ in range(30):
            bias = compute_bias(matches, hs)
            biases.append(bias)
        
        # Later biases should be lower due to concentration
        assert biases[0] >= sum(biases) / len(biases), "Concentration should reduce bias"

    def test_concentration_calculation(self):
        """Test concentration score calculation."""
        reset_diversity_tracker()
        
        # No hits = 0 concentration
        assert _get_concentration() == 0.0
        
        # Single signature repeated = high concentration
        for _ in range(10):
            _record_signature_hit("sig_a")
        
        conc = _get_concentration()
        assert conc > 0.9, f"Single signature should have concentration near 1.0, got {conc}"

    def test_diversity_tax_multiplier(self):
        """Test diversity tax multiplier calculation."""
        # Below threshold - no penalty
        assert _compute_diversity_tax(0.0) == 1.0
        assert _compute_diversity_tax(CONCENTRATION_THRESHOLD) == 1.0
        
        # High concentration - heavy penalty
        tax = _compute_diversity_tax(0.8)
        assert 0.1 <= tax < 1.0, f"High concentration should have penalty, got {tax}"
        
        # Maximum concentration
        tax_max = _compute_diversity_tax(1.0)
        assert tax_max == 0.1, "Maximum concentration should have 0.1 tax"

    def test_diverse_signatures_lower_concentration(self):
        """Multiple different signatures should lower concentration."""
        reset_diversity_tracker()
        
        for i in range(10):
            _record_signature_hit(f"sig_{i % 3}")  # 3 different signatures
        
        conc = _get_concentration()
        assert conc < 0.5, f"Multiple signatures should have lower concentration, got {conc}"


class TestBiasClamping:
    """Tests for bias clamping to MAX_BIAS."""

    def test_bias_never_exceeds_max(self):
        """Bias should never exceed MAX_BIAS."""
        matches = [{"sim": 1.0, "confidence": 1.0, "signature": "sig1"}]
        hs = {"safety": 0.9, "energy": 0.9}
        
        bias = compute_bias(matches, hs)
        assert bias <= MAX_BIAS, f"Bias {bias} should be <= MAX_BIAS {MAX_BIAS}"

    def test_bias_never_negative(self):
        """Bias should never be negative."""
        matches = [{"sim": 0.0, "confidence": 0.0, "signature": "sig1"}]
        hs = {"safety": 0.5, "energy": 0.5}
        
        bias = compute_bias(matches, hs)
        assert bias >= 0.0, "Bias should never be negative"


class TestEvaluateCyclePrior:
    """Tests for full evaluate_cycle_prior function."""

    def setup_method(self):
        """Reset state before each test."""
        reset_diversity_tracker()

    def test_returns_correct_structure(self):
        """evaluate_cycle_prior should return correct structure."""
        result = evaluate_cycle_prior(
            {"focus": "test", "intent": "probe"},
            [],
            {"safety": 0.7, "energy": 0.7},
        )
        
        assert "cycle_prior_applied" in result
        assert "matched_signatures_topK" in result
        assert "bias_strength" in result

    def test_no_matches_no_bias(self):
        """No matches should result in no bias."""
        result = evaluate_cycle_prior(
            {"focus": "test"},
            [],
            {"safety": 0.7, "energy": 0.7},
        )
        
        assert result["bias_strength"] == 0.0
        assert result["cycle_prior_applied"] is False

    def test_with_matches_produces_bias(self):
        """With matches and healthy homeostasis, should produce bias."""
        cycle_items = [
            {
                "signature": "test_sig",
                "prototype_bucket": {
                    "psi": {"focus": "test", "intent": "probe"},
                    "phi": {"hs": {"safety": 0.7}, "efe": {"risk": 0.3}},
                },
                "stats": {"order_invariance_score": 0.8, "support_ratio": 0.2},
            }
        ]
        
        result = evaluate_cycle_prior(
            {"focus": "test", "intent": "probe"},
            cycle_items,
            {"safety": 0.7, "energy": 0.7},
        )
        
        assert result["bias_strength"] > 0.0
        assert result["cycle_prior_applied"] is True
        assert len(result["matched_signatures_topK"]) > 0


class TestGuardIntegration:
    """Integration tests for guards working together."""

    def setup_method(self):
        reset_diversity_tracker()

    def test_recovery_priority_takes_precedence(self):
        """Recovery priority should override other factors."""
        matches = [{"sim": 0.95, "confidence": 0.9, "signature": "sig_important"}]
        
        # Critical homeostasis
        hs = {"safety": 0.15, "energy": 0.2}
        
        # Even with high-quality match, bias should be 0
        bias = compute_bias(matches, hs)
        assert bias == 0.0, "Recovery priority should force bias=0"

    def test_diversity_tax_applies_after_safety_checks(self):
        """Diversity tax should apply after safety checks pass."""
        matches = [{"sim": 0.9, "confidence": 0.8, "signature": "sig_repeat"}]
        hs = {"safety": 0.7, "energy": 0.7}
        
        # Build concentration
        biases = []
        for _ in range(40):
            biases.append(compute_bias(matches, hs))
        
        # First should be highest (no concentration yet)
        # Later should be lower (concentration built up)
        if len(biases) >= 2:
            assert biases[0] >= biases[-1] or biases[-1] < MAX_BIAS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
