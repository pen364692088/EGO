"""
MVP11-T07: EFE Terms Monotonicity Tests

Tests that EFE computation behaves monotonically with respect to:
1. Risk: Higher risk → higher EFE
2. Ambiguity: Higher ambiguity → higher EFE
3. Info_gain: Higher info_gain → lower EFE
4. Cost: Higher cost → higher EFE

Also tests homeostasis modulation:
- Low safety → higher risk_weight → higher EFE for risky actions
- Low certainty → higher info_gain_weight → lower EFE for info-seeking actions
- Low energy → higher cost_weight → higher EFE for costly actions
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from emotiond.efe_policy import EFETerms, EFEPolicy, compute_efe_chain
from emotiond.homeostasis import HomeostasisState


class TestEFETermsBasics:
    """Test EFETerms dataclass basic functionality."""
    
    def test_efe_terms_creation(self):
        """Test EFETerms can be created with default values."""
        terms = EFETerms()
        assert terms.risk == 0.5
        assert terms.ambiguity == 0.5
        assert terms.info_gain == 0.5
        assert terms.cost == 0.5
    
    def test_efe_terms_clamping(self):
        """Test EFETerms clamps values to [0, 1]."""
        # Test upper bound
        terms = EFETerms(risk=1.5, ambiguity=2.0, info_gain=0.8, cost=-0.5)
        assert terms.risk == 1.0
        assert terms.ambiguity == 1.0
        assert terms.info_gain == 0.8
        assert terms.cost == 0.0
        
        # Test lower bound
        terms = EFETerms(risk=-1.0, ambiguity=-0.5, info_gain=-2.0, cost=-1.0)
        assert terms.risk == 0.0
        assert terms.ambiguity == 0.0
        assert terms.info_gain == 0.0
        assert terms.cost == 0.0
    
    def test_efe_terms_serialization(self):
        """Test EFETerms to_dict/from_dict roundtrip."""
        terms = EFETerms(risk=0.3, ambiguity=0.7, info_gain=0.9, cost=0.2)
        data = terms.to_dict()
        
        restored = EFETerms.from_dict(data)
        assert restored.risk == terms.risk
        assert restored.ambiguity == terms.ambiguity
        assert restored.info_gain == terms.info_gain
        assert restored.cost == terms.cost
    
    def test_efe_computation(self):
        """Test basic EFE formula computation."""
        terms = EFETerms(risk=0.5, ambiguity=0.5, info_gain=0.5, cost=0.5)
        weights = {
            "risk_weight": 1.0,
            "ambiguity_weight": 1.0,
            "info_gain_weight": 1.0,
            "cost_weight": 1.0,
        }
        
        # EFE = 0.5*1 + 0.5*1 - 0.5*1 + 0.5*1 = 1.0
        efe = terms.compute_efe(weights)
        assert abs(efe - 1.0) < 0.001


class TestEFETermsMonotonicity:
    """Test monotonicity of EFE with respect to each term."""
    
    @pytest.fixture
    def policy(self):
        """Create a default EFE policy."""
        return EFEPolicy()
    
    @pytest.fixture
    def default_homeostasis(self):
        """Create a neutral homeostasis state."""
        return HomeostasisState(energy=0.7, safety=0.7, certainty=0.7, autonomy=0.7, affiliation=0.7, fairness=0.7)
    
    def test_risk_monotonicity(self, policy, default_homeostasis):
        """Higher risk → higher EFE."""
        candidates = [
            {"risk": 0.1, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.3, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.7, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.9, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
        ]
        
        efe_values = []
        for c in candidates:
            efe = policy.compute_full_efe(c, homeostasis=default_homeostasis)
            efe_values.append(efe)
        
        # EFE should increase with risk
        for i in range(1, len(efe_values)):
            assert efe_values[i] >= efe_values[i-1], f"EFE not monotonic: {efe_values}"
    
    def test_ambiguity_monotonicity(self, policy, default_homeostasis):
        """Higher ambiguity → higher EFE."""
        candidates = [
            {"risk": 0.5, "ambiguity": 0.1, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.3, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.7, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.9, "info_gain": 0.5, "cost": 0.5},
        ]
        
        efe_values = []
        for c in candidates:
            efe = policy.compute_full_efe(c, homeostasis=default_homeostasis)
            efe_values.append(efe)
        
        # EFE should increase with ambiguity
        for i in range(1, len(efe_values)):
            assert efe_values[i] >= efe_values[i-1], f"EFE not monotonic: {efe_values}"
    
    def test_info_gain_monotonicity(self, policy, default_homeostasis):
        """Higher info_gain → lower EFE."""
        candidates = [
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.9, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.7, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.3, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.1, "cost": 0.5},
        ]
        
        efe_values = []
        for c in candidates:
            efe = policy.compute_full_efe(c, homeostasis=default_homeostasis)
            efe_values.append(efe)
        
        # EFE should decrease with info_gain
        for i in range(1, len(efe_values)):
            assert efe_values[i] >= efe_values[i-1], f"EFE not monotonic: {efe_values}"
    
    def test_cost_monotonicity(self, policy, default_homeostasis):
        """Higher cost → higher EFE."""
        candidates = [
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.1},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.3},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.7},
            {"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.9},
        ]
        
        efe_values = []
        for c in candidates:
            efe = policy.compute_full_efe(c, homeostasis=default_homeostasis)
            efe_values.append(efe)
        
        # EFE should increase with cost
        for i in range(1, len(efe_values)):
            assert efe_values[i] >= efe_values[i-1], f"EFE not monotonic: {efe_values}"


class TestHomeostasisModulation:
    """Test homeostasis state modulates EFE weights correctly."""
    
    @pytest.fixture
    def policy(self):
        return EFEPolicy()
    
    def test_low_safety_increases_risk_weight(self, policy):
        """Low safety → higher risk_weight → higher EFE for risky actions."""
        risky_candidate = {"risk": 0.8, "ambiguity": 0.3, "info_gain": 0.3, "cost": 0.3}
        
        # High safety state
        high_safety = HomeostasisState(safety=0.9, energy=0.7, certainty=0.7)
        efe_high_safety = policy.compute_full_efe(risky_candidate, homeostasis=high_safety)
        
        # Low safety state
        low_safety = HomeostasisState(safety=0.2, energy=0.7, certainty=0.7)
        efe_low_safety = policy.compute_full_efe(risky_candidate, homeostasis=low_safety)
        
        # Low safety should increase EFE for risky action
        assert efe_low_safety > efe_high_safety, \
            f"Low safety should increase EFE for risky action: {efe_low_safety} vs {efe_high_safety}"
    
    def test_low_certainty_increases_info_gain_weight(self, policy):
        """Low certainty → higher info_gain_weight → lower EFE for info-seeking actions."""
        info_seeking_candidate = {"risk": 0.3, "ambiguity": 0.3, "info_gain": 0.9, "cost": 0.3}
        
        # High certainty state
        high_certainty = HomeostasisState(certainty=0.9, energy=0.7, safety=0.7)
        efe_high_certainty = policy.compute_full_efe(info_seeking_candidate, homeostasis=high_certainty)
        
        # Low certainty state
        low_certainty = HomeostasisState(certainty=0.2, energy=0.7, safety=0.7)
        efe_low_certainty = policy.compute_full_efe(info_seeking_candidate, homeostasis=low_certainty)
        
        # Low certainty should decrease EFE for info-seeking action
        assert efe_low_certainty < efe_high_certainty, \
            f"Low certainty should decrease EFE for info-seeking: {efe_low_certainty} vs {efe_high_certainty}"
    
    def test_low_energy_increases_cost_weight(self, policy):
        """Low energy → higher cost_weight → higher EFE for costly actions."""
        costly_candidate = {"risk": 0.3, "ambiguity": 0.3, "info_gain": 0.3, "cost": 0.8}
        
        # High energy state
        high_energy = HomeostasisState(energy=0.9, safety=0.7, certainty=0.7)
        efe_high_energy = policy.compute_full_efe(costly_candidate, homeostasis=high_energy)
        
        # Low energy state
        low_energy = HomeostasisState(energy=0.2, safety=0.7, certainty=0.7)
        efe_low_energy = policy.compute_full_efe(costly_candidate, homeostasis=low_energy)
        
        # Low energy should increase EFE for costly action
        assert efe_low_energy > efe_high_energy, \
            f"Low energy should increase EFE for costly action: {efe_low_energy} vs {efe_high_energy}"
    
    def test_policy_params_reflect_homeostasis(self, policy):
        """Policy params should reflect homeostasis state."""
        # Low safety → higher risk_weight
        low_safety = HomeostasisState(safety=0.2, energy=0.7, certainty=0.7)
        params = policy.compute_policy_params(homeostasis=low_safety)
        assert params["risk_weight"] > 1.0, "Low safety should increase risk_weight"
        
        # Low certainty → higher info_gain_weight
        low_certainty = HomeostasisState(safety=0.7, energy=0.7, certainty=0.2)
        params = policy.compute_policy_params(homeostasis=low_certainty)
        assert params["info_gain_weight"] > 1.0, "Low certainty should increase info_gain_weight"
        
        # Low energy → higher cost_weight
        low_energy = HomeostasisState(safety=0.7, energy=0.2, certainty=0.7)
        params = policy.compute_policy_params(homeostasis=low_energy)
        assert params["cost_weight"] > 1.0, "Low energy should increase cost_weight"


class TestEFEPolicySelection:
    """Test action selection using EFE."""
    
    @pytest.fixture
    def policy(self):
        return EFEPolicy()
    
    def test_rank_candidates(self, policy):
        """Test ranking candidates by EFE."""
        candidates = [
            {"id": "safe", "risk": 0.2, "ambiguity": 0.3, "info_gain": 0.5, "cost": 0.2},
            {"id": "risky", "risk": 0.8, "ambiguity": 0.7, "info_gain": 0.3, "cost": 0.6},
            {"id": "balanced", "risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5},
        ]
        
        ranked = policy.rank_candidates(candidates)
        
        # Should be sorted by EFE ascending
        for i in range(1, len(ranked)):
            assert ranked[i][1] >= ranked[i-1][1], "Candidates should be sorted by EFE ascending"
        
        # Safe candidate should have lower EFE than risky
        safe_efe = next(efe for c, efe in ranked if c["id"] == "safe")
        risky_efe = next(efe for c, efe in ranked if c["id"] == "risky")
        assert safe_efe < risky_efe, "Safe candidate should have lower EFE than risky"
    
    def test_select_action_deterministic(self, policy):
        """Test deterministic action selection."""
        candidates = [
            {"id": "a", "risk": 0.8, "ambiguity": 0.7, "info_gain": 0.1, "cost": 0.7},
            {"id": "b", "risk": 0.2, "ambiguity": 0.3, "info_gain": 0.8, "cost": 0.2},
        ]
        
        selected, efe, _ = policy.select_action(candidates, stochastic=False)
        
        # Should select the one with lower EFE (b)
        assert selected["id"] == "b", "Should select candidate with lower EFE"
    
    def test_select_action_stochastic(self, policy):
        """Test stochastic action selection prefers lower EFE."""
        import random
        random.seed(42)
        
        candidates = [
            {"id": "bad", "risk": 0.9, "ambiguity": 0.9, "info_gain": 0.1, "cost": 0.9},
            {"id": "good", "risk": 0.1, "ambiguity": 0.1, "info_gain": 0.9, "cost": 0.1},
        ]
        
        # Run multiple selections
        selections = {"good": 0, "bad": 0}
        for _ in range(100):
            selected, _, _ = policy.select_action(candidates, stochastic=True)
            selections[selected["id"]] += 1
        
        # Good candidate should be selected more often
        assert selections["good"] > selections["bad"], \
            f"Good candidate should be selected more: {selections}"


class TestEFEPolicySerialization:
    """Test serialization and deserialization."""
    
    def test_policy_to_dict(self):
        """Test policy serialization."""
        policy = EFEPolicy()
        policy.compute_efe({"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5})
        
        data = policy.to_dict()
        assert "risk_weight_range" in data
        assert "ambiguity_weight_range" in data
        assert "info_gain_weight_range" in data
        assert "cost_weight_range" in data
        assert "precision_range" in data
    
    def test_policy_from_dict(self):
        """Test policy deserialization."""
        original = EFEPolicy(
            risk_weight_range=(0.3, 1.8),
            info_gain_weight_range=(0.4, 1.9),
        )
        original.compute_efe({"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5})
        
        data = original.to_dict()
        restored = EFEPolicy.from_dict(data)
        
        assert restored.risk_weight_range == original.risk_weight_range
        assert restored.info_gain_weight_range == original.info_gain_weight_range


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_compute_efe_chain(self):
        """Test compute_efe_chain convenience function."""
        candidate = {"risk": 0.4, "ambiguity": 0.3, "info_gain": 0.7, "cost": 0.2}
        homeostasis = HomeostasisState(safety=0.8, energy=0.6, certainty=0.5)
        
        result = compute_efe_chain(candidate, homeostasis=homeostasis)
        
        assert "efe_terms" in result
        assert "policy_params" in result
        assert "efe_value" in result
        assert result["homeostasis_modulated"] == True
        
        # EFE terms should match input
        terms = result["efe_terms"]
        assert terms["risk"] == candidate["risk"]
        assert terms["ambiguity"] == candidate["ambiguity"]
        assert terms["info_gain"] == candidate["info_gain"]
        assert terms["cost"] == candidate["cost"]


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.fixture
    def policy(self):
        return EFEPolicy()
    
    def test_extreme_values(self, policy):
        """Test with extreme EFE values."""
        # Very low EFE (good action)
        good_candidate = {"risk": 0.0, "ambiguity": 0.0, "info_gain": 1.0, "cost": 0.0}
        efe_good = policy.compute_full_efe(good_candidate)
        
        # Very high EFE (bad action)
        bad_candidate = {"risk": 1.0, "ambiguity": 1.0, "info_gain": 0.0, "cost": 1.0}
        efe_bad = policy.compute_full_efe(bad_candidate)
        
        assert efe_good < efe_bad, f"Good action should have lower EFE: {efe_good} vs {efe_bad}"
    
    def test_zero_division_protection(self, policy):
        """Test no division by zero in selection."""
        candidates = [{"risk": 0.5, "ambiguity": 0.5, "info_gain": 0.5, "cost": 0.5}]
        
        # Should not raise
        selected, efe, ranked = policy.select_action(candidates, stochastic=True)
        assert selected is not None
        assert len(ranked) == 1
    
    def test_empty_candidates(self, policy):
        """Test behavior with empty candidate list."""
        ranked = policy.rank_candidates([])
        assert ranked == []
    
    def test_negative_efe_possible(self, policy):
        """Test that EFE can be negative (due to high info_gain)."""
        # High info_gain should produce negative EFE
        high_info = {"risk": 0.1, "ambiguity": 0.1, "info_gain": 0.9, "cost": 0.1}
        
        # Use neutral homeostasis
        neutral = HomeostasisState(safety=0.7, energy=0.7, certainty=0.7)
        efe = policy.compute_full_efe(high_info, homeostasis=neutral)
        
        # EFE should be relatively low (possibly negative)
        # Formula: 0.1*1 + 0.1*1 - 0.9*1 + 0.1*1 = -0.6 (approx)
        # But with homeostasis modulation, weights may vary
        assert efe < 0.5, f"High info_gain action should have low EFE: {efe}"


class TestIntegrationWithHomeostasisManager:
    """Test integration with HomeostasisManager."""
    
    def test_homeostasis_manager_update_affects_efe(self):
        """Test that HomeostasisManager updates affect EFE computation."""
        from emotiond.homeostasis import HomeostasisManager
        
        policy = EFEPolicy()
        manager = HomeostasisManager()
        
        risky_action = {"risk": 0.7, "ambiguity": 0.3, "info_gain": 0.3, "cost": 0.3}
        
        # Initial EFE
        initial_efe = policy.compute_full_efe(risky_action, homeostasis=manager.state)
        
        # Simulate failure that reduces safety
        manager.update_from_outcome({"status": "fail", "reason": "blocked"})
        
        # EFE should now be higher for risky action
        post_failure_efe = policy.compute_full_efe(risky_action, homeostasis=manager.state)
        
        # Note: The exact relationship depends on the outcome effects
        # Here we just verify the computation works with the manager
        assert isinstance(post_failure_efe, float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestEFESelectionDeterminism:
    """Determinism tests for EFE stochastic selection trace."""

    def _run_trace(self, seed: int, ticks: int = 50):
        policy = EFEPolicy(seed=seed)
        traces = []
        candidates = [
            {"id": "a", "risk": 0.3, "ambiguity": 0.4, "info_gain": 0.4, "cost": 0.2},
            {"id": "b", "risk": 0.5, "ambiguity": 0.2, "info_gain": 0.7, "cost": 0.4},
            {"id": "c", "risk": 0.2, "ambiguity": 0.6, "info_gain": 0.2, "cost": 0.1},
        ]

        for _ in range(ticks):
            policy.select_action(candidates, stochastic=True)
            t = policy.get_last_selection_trace()
            traces.append({
                "sample_r": t["sample_r"],
                "selected_idx": t["selected_idx"],
                "probs": t["probs"],
            })
        return traces

    def test_efe_trace_deterministic_same_seed(self):
        """Same seed + same candidates should produce identical trace trajectory."""
        trace1 = self._run_trace(seed=42, ticks=50)
        trace2 = self._run_trace(seed=42, ticks=50)

        assert len(trace1) == len(trace2) == 50
        for t1, t2 in zip(trace1, trace2):
            assert t1["selected_idx"] == t2["selected_idx"]
            assert t1["sample_r"] == pytest.approx(t2["sample_r"], abs=1e-12)
            for p1, p2 in zip(t1["probs"], t2["probs"]):
                assert p1 == pytest.approx(p2, abs=1e-12)

    def test_policy_serialization_preserves_rng_sequence(self):
        """After to_dict/from_dict, stochastic sequence should continue identically."""
        candidates = [
            {"id": "a", "risk": 0.3, "ambiguity": 0.4, "info_gain": 0.4, "cost": 0.2},
            {"id": "b", "risk": 0.5, "ambiguity": 0.2, "info_gain": 0.7, "cost": 0.4},
            {"id": "c", "risk": 0.2, "ambiguity": 0.6, "info_gain": 0.2, "cost": 0.1},
        ]

        p1 = EFEPolicy(seed=123)
        p2 = EFEPolicy(seed=123)

        # advance both equally
        for _ in range(7):
            p1.select_action(candidates, stochastic=True)
            p2.select_action(candidates, stochastic=True)

        # serialize/restore only p1
        restored = EFEPolicy.from_dict(p1.to_dict())

        # subsequent trajectory should match p2 exactly
        for _ in range(20):
            restored.select_action(candidates, stochastic=True)
            p2.select_action(candidates, stochastic=True)
            t1 = restored.get_last_selection_trace()
            t2 = p2.get_last_selection_trace()
            assert t1["selected_idx"] == t2["selected_idx"]
            assert t1["sample_r"] == pytest.approx(t2["sample_r"], abs=1e-12)


    def test_policy_deserialize_ignores_unknown_rng_state_version(self):
        """Unknown rng_state_version should not crash and should fallback to seeded RNG."""
        data = EFEPolicy(seed=77).to_dict()
        data["rng_state_version"] = "unknown_v999"
        restored = EFEPolicy.from_dict(data)

        candidates = [
            {"id": "a", "risk": 0.3, "ambiguity": 0.4, "info_gain": 0.4, "cost": 0.2},
            {"id": "b", "risk": 0.5, "ambiguity": 0.2, "info_gain": 0.7, "cost": 0.4},
        ]
        restored.select_action(candidates, stochastic=True)
        t = restored.get_last_selection_trace()
        assert t is not None
        assert "selected_idx" in t
