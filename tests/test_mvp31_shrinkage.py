"""
MVP-3.1: Shrinkage Factor (Alpha) Tests

Tests for alpha monotonicity and correct shrinkage behavior.
"""
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emotiond import core
from emotiond.config import SHRINKAGE_K


class TestShrinkageAlpha:
    """Tests for the shrinkage factor calculation."""
    
    def test_alpha_zero_when_n_zero(self):
        """n=0 should produce alpha=0 (fully trust global)."""
        alpha = core.calculate_shrinkage_alpha(0)
        assert alpha == 0.0, f"Expected alpha=0 for n=0, got {alpha}"
    
    def test_alpha_increases_with_n(self):
        """Alpha should be monotonically increasing with n."""
        previous_alpha = 0.0
        for n in range(0, 100, 5):
            alpha = core.calculate_shrinkage_alpha(n)
            assert alpha >= previous_alpha, f"Alpha not monotonic: {alpha} < {previous_alpha} at n={n}"
            previous_alpha = alpha
    
    def test_alpha_approaches_one_as_n_increases(self):
        """As n -> infinity, alpha should approach 1."""
        alpha_large_n = core.calculate_shrinkage_alpha(1000)
        assert alpha_large_n > 0.98, f"Expected alpha close to 1 for large n, got {alpha_large_n}"
        
        alpha_very_large = core.calculate_shrinkage_alpha(10000)
        assert alpha_very_large > alpha_large_n, "Alpha should keep increasing"
        assert alpha_very_large < 1.0, "Alpha should never reach 1.0"
    
    def test_alpha_at_default_k(self):
        """Test alpha values at default k=20."""
        # α = n / (n + 20)
        test_cases = [
            (0, 0.0),
            (5, 5/25),   # 0.2
            (10, 10/30), # 0.333...
            (20, 20/40), # 0.5
            (40, 40/60), # 0.666...
            (80, 80/100), # 0.8
        ]
        
        for n, expected_alpha in test_cases:
            alpha = core.calculate_shrinkage_alpha(n)
            assert abs(alpha - expected_alpha) < 0.001, \
                f"Expected alpha={expected_alpha} for n={n}, got {alpha}"
    
    def test_alpha_custom_k(self):
        """Test alpha with custom k value."""
        # With k=10
        alpha = core.calculate_shrinkage_alpha(10, k=10)
        expected = 10 / 20  # 0.5
        assert abs(alpha - expected) < 0.001, f"Expected alpha={expected}, got {alpha}"
        
        # With k=100
        alpha = core.calculate_shrinkage_alpha(10, k=100)
        expected = 10 / 110  # ~0.09
        assert abs(alpha - expected) < 0.001, f"Expected alpha={expected}, got {alpha}"
    
    def test_alpha_never_exceeds_one(self):
        """Alpha should always be < 1."""
        for n in [0, 1, 10, 100, 1000, 10000]:
            alpha = core.calculate_shrinkage_alpha(n)
            assert alpha < 1.0, f"Alpha should be < 1 for n={n}, got {alpha}"
            assert alpha >= 0.0, f"Alpha should be >= 0 for n={n}, got {alpha}"


class TestCombinedPrediction:
    """Tests for combined prediction calculation."""
    
    def test_combined_equals_global_when_alpha_zero(self):
        """When alpha=0, combined prediction should equal global."""
        global_pred = {"social_safety_delta": 0.05, "energy_delta": -0.02}
        target_pred = {"social_safety_delta": 0.2, "energy_delta": -0.1, "n": 0}
        
        combined = core.compute_combined_prediction(global_pred, target_pred, alpha=0.0)
        
        assert combined["safety"] == global_pred["social_safety_delta"]
        assert combined["energy"] == global_pred["energy_delta"]
    
    def test_combined_includes_residual_when_alpha_positive(self):
        """When alpha > 0, combined should include residual contribution."""
        global_pred = {"social_safety_delta": 0.05, "energy_delta": -0.02}
        target_pred = {"social_safety_delta": 0.1, "energy_delta": 0.05, "n": 10}
        
        alpha = 0.5  # Equal weight
        combined = core.compute_combined_prediction(global_pred, target_pred, alpha)
        
        expected_safety = 0.05 + 0.5 * 0.1  # 0.1
        expected_energy = -0.02 + 0.5 * 0.05  # 0.005
        
        assert abs(combined["safety"] - expected_safety) < 0.001
        assert abs(combined["energy"] - expected_energy) < 0.001
    
    def test_combined_prediction_clamped(self):
        """Combined prediction should be clamped to valid range."""
        global_pred = {"social_safety_delta": 0.15, "energy_delta": 0.15}
        target_pred = {"social_safety_delta": 0.5, "energy_delta": 0.5, "n": 100}
        
        # With alpha=0.9, this would exceed clamp without protection
        combined = core.compute_combined_prediction(global_pred, target_pred, alpha=0.9)
        
        from emotiond.config import DELTA_CLAMP_MAX
        assert combined["safety"] <= DELTA_CLAMP_MAX
        assert combined["energy"] <= DELTA_CLAMP_MAX
    
    def test_combined_prediction_includes_breakdown(self):
        """Combined prediction should include global/residual breakdown."""
        global_pred = {"social_safety_delta": 0.03, "energy_delta": -0.01}
        target_pred = {"social_safety_delta": 0.05, "energy_delta": 0.02, "n": 20}
        
        combined = core.compute_combined_prediction(global_pred, target_pred, alpha=0.5)
        
        assert "global_safety" in combined
        assert "global_energy" in combined
        assert "residual_safety" in combined
        assert "residual_energy" in combined
        assert "alpha" in combined
        
        assert combined["global_safety"] == 0.03
        assert combined["residual_safety"] == 0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
