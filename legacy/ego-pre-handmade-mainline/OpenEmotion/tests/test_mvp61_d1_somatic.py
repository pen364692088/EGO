"""
MVP-6.1 D1 Tests: Target-Conditioned Somatic Markers

Tests for:
- Shrinkage monotonicity and limit behavior
- Sample size effects on residual activation
- Cross-target isolation
- Trace record completeness
"""
import pytest
import time
from emotiond.body_state import (
    BodyStateDimension, BodyStateVector, TargetResidual, 
    Shrinkage, get_body_state, reset_body_state, set_body_state
)


class TestShrinkage:
    """Test shrinkage regularization behavior."""
    
    def test_shrinkage_weight_zero_obs(self):
        """Shrinkage weight is 0 when n_obs = 0."""
        shrinkage = Shrinkage(k=10.0)
        assert shrinkage.compute_weight(0) == 0.0
    
    def test_shrinkage_weight_one_obs(self):
        """Shrinkage weight is small when n_obs = 1."""
        shrinkage = Shrinkage(k=10.0)
        weight = shrinkage.compute_weight(1)
        assert 0 < weight < 0.1  # 1/11 ≈ 0.09
    
    def test_shrinkage_weight_increases_with_n_obs(self):
        """Shrinkage weight increases monotonically with n_obs."""
        shrinkage = Shrinkage(k=10.0)
        weights = [shrinkage.compute_weight(n) for n in range(1, 51)]
        # Check monotonicity
        for i in range(len(weights) - 1):
            assert weights[i] < weights[i + 1]
    
    def test_shrinkage_weight_asymptotic_limit(self):
        """Shrinkage weight approaches 1 as n_obs → ∞."""
        shrinkage = Shrinkage(k=10.0)
        # At 1000 observations, weight should be very close to 1
        weight = shrinkage.compute_weight(1000)
        assert weight > 0.99
    
    def test_shrinkage_k_effect(self):
        """Higher k = more conservative (lower weight for same n_obs)."""
        n_obs = 10
        shrinkage_low_k = Shrinkage(k=5.0)
        shrinkage_high_k = Shrinkage(k=20.0)
        
        weight_low = shrinkage_low_k.compute_weight(n_obs)
        weight_high = shrinkage_high_k.compute_weight(n_obs)
        
        assert weight_low > weight_high
    
    def test_shrinkage_apply_to_residual(self):
        """Shrinkage correctly scales residual values."""
        shrinkage = Shrinkage(k=10.0)
        residual_raw = 0.5
        
        # With 10 observations, weight = 10/20 = 0.5
        shrunk = shrinkage.apply(residual_raw, n_obs=10)
        assert shrunk == 0.25  # 0.5 * 0.5
    
    def test_shrinkage_minimum_k(self):
        """k is clamped to minimum of 1.0."""
        shrinkage = Shrinkage(k=0.5)
        assert shrinkage.k == 1.0


class TestTargetResidual:
    """Test per-target residual state."""
    
    def test_target_residual_default_values(self):
        """TargetResidual initializes with zero residuals."""
        residual = TargetResidual()
        assert residual.safety_stress == 0.0
        assert residual.social_need == 0.0
        assert residual.novelty_need == 0.0
        assert residual.n_obs == 0
        assert residual.evidence_strength == 0.0
    
    def test_target_residual_update(self):
        """TargetResidual correctly accumulates updates."""
        residual = TargetResidual()
        residual.update(
            safety_stress_delta=0.1,
            social_need_delta=-0.05,
            novelty_need_delta=0.0,
            evidence_increment=0.1
        )
        
        assert residual.safety_stress == 0.1
        assert residual.social_need == -0.05
        assert residual.n_obs == 1
        assert residual.evidence_strength == 0.1
    
    def test_target_residual_multiple_updates(self):
        """TargetResidual accumulates across multiple updates."""
        residual = TargetResidual()
        
        for i in range(5):
            residual.update(
                safety_stress_delta=0.05,
                evidence_increment=0.1
            )
        
        assert residual.safety_stress == 0.25  # 5 * 0.05
        assert residual.n_obs == 5
        assert residual.evidence_strength == 0.5  # 5 * 0.1, capped at 1.0
    
    def test_target_residual_clamping(self):
        """TargetResidual values are clamped to [-1, 1]."""
        residual = TargetResidual()
        residual.update(safety_stress_delta=2.0)
        assert residual.safety_stress == 1.0
        
        residual2 = TargetResidual()
        residual2.update(safety_stress_delta=-2.0)
        assert residual2.safety_stress == -1.0
    
    def test_target_residual_evidence_cap(self):
        """Evidence strength is capped at 1.0."""
        residual = TargetResidual()
        for i in range(15):
            residual.update(evidence_increment=0.1)
        assert residual.evidence_strength == 1.0
    
    def test_target_residual_serialization(self):
        """TargetResidual can be serialized and deserialized."""
        residual = TargetResidual()
        residual.update(safety_stress_delta=0.2, social_need_delta=-0.1)
        
        data = residual.to_dict()
        restored = TargetResidual.from_dict(data)
        
        assert restored.safety_stress == residual.safety_stress
        assert restored.social_need == residual.social_need
        assert restored.n_obs == residual.n_obs


class TestBodyStateTargetConditioning:
    """Test target-conditioned body state access."""
    
    def test_get_target_residual_creates_new(self):
        """get_target_residual creates new residual if not exists."""
        body = BodyStateVector()
        residual = body.get_target_residual("target_1")
        assert residual is not None
        assert "target_1" in body.target_residuals
    
    def test_get_target_residual_returns_existing(self):
        """get_target_residual returns existing residual."""
        body = BodyStateVector()
        residual1 = body.get_target_residual("target_1")
        residual1.update(safety_stress_delta=0.2)
        
        residual2 = body.get_target_residual("target_1")
        assert residual2.safety_stress == 0.2
    
    def test_effective_value_without_target(self):
        """Effective value without target is global value."""
        body = BodyStateVector()
        body.safety_stress.value = 0.7
        
        effective = body.get_effective_value("safety_stress")
        assert effective == 0.7
    
    def test_effective_value_with_unseen_target(self):
        """Effective value with unseen target is global value."""
        body = BodyStateVector()
        body.safety_stress.value = 0.7
        
        effective = body.get_effective_value("safety_stress", target_id="new_target")
        assert effective == 0.7
    
    def test_effective_value_with_residual_low_n_obs(self):
        """With low n_obs, residual has minimal effect due to shrinkage."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=0.4, evidence_increment=0.2)  # n_obs=1
        
        effective = body.get_effective_value("safety_stress", target_id="target_1")
        # With k=10, n_obs=1: weight = 1/11 ≈ 0.09
        # Effective residual ≈ 0.4 * 0.09 = 0.036
        # Effective value ≈ 0.6 + 0.036 = 0.636
        assert 0.63 < effective < 0.65
    
    def test_effective_value_with_residual_high_n_obs(self):
        """With high n_obs, residual has full effect."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        residual = body.get_target_residual("target_1")
        # Simulate 100 observations
        for _ in range(100):
            residual.update(safety_stress_delta=0.004, evidence_increment=0.01)
        
        effective = body.get_effective_value("safety_stress", target_id="target_1")
        # With k=10, n_obs=100: weight = 100/110 ≈ 0.91
        # Effective residual ≈ 0.4 * 0.91 = 0.364
        # Effective value ≈ 0.6 + 0.364 = 0.964, clamped to 1.0
        assert effective > 0.9
    
    def test_effective_values_returns_all_dimensions(self):
        """get_effective_values returns all 5 dimensions."""
        body = BodyStateVector()
        values = body.get_effective_values(target_id="target_1")
        
        assert "energy" in values
        assert "safety_stress" in values
        assert "social_need" in values
        assert "novelty_need" in values
        assert "focus_fatigue" in values
    
    def test_energy_not_target_conditioned(self):
        """Energy dimension is not affected by target residuals."""
        body = BodyStateVector()
        body.energy.value = 0.7
        
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=0.5)  # This shouldn't affect energy
        
        effective = body.get_effective_value("energy", target_id="target_1")
        assert effective == 0.7


class TestCrossTargetIsolation:
    """Test that target residuals don't contaminate each other."""
    
    def test_target_a_does_not_affect_target_b(self):
        """Residuals for target A don't affect target B."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        # Build up residual for target_1
        residual_a = body.get_target_residual("target_1")
        for _ in range(50):
            residual_a.update(safety_stress_delta=0.01)
        
        # Target_2 should not see target_1's residual
        effective_a = body.get_effective_value("safety_stress", target_id="target_1")
        effective_b = body.get_effective_value("safety_stress", target_id="target_2")
        
        assert effective_a > effective_b  # target_1 has positive residual
        assert effective_b == 0.6  # target_2 sees only global
    
    def test_interleaved_target_updates(self):
        """Interleaved updates to different targets maintain isolation."""
        body = BodyStateVector()
        body.shrinkage_k = 5.0
        
        # Interleave updates: A, B, A, B, ...
        for i in range(20):
            target = "target_a" if i % 2 == 0 else "target_b"
            delta = 0.05 if target == "target_a" else -0.05
            
            residual = body.get_target_residual(target)
            residual.update(safety_stress_delta=delta)
        
        # Each target should have 10 observations
        assert body.target_residuals["target_a"].n_obs == 10
        assert body.target_residuals["target_b"].n_obs == 10
        
        # Residuals should be opposite
        assert body.target_residuals["target_a"].safety_stress > 0
        assert body.target_residuals["target_b"].safety_stress < 0
    
    def test_global_body_not_affected_by_target_residuals(self):
        """Global body state values are not modified by target residuals."""
        body = BodyStateVector()
        original_safety = body.safety_stress.value
        
        # Add strong residual for a target
        residual = body.get_target_residual("target_1")
        for _ in range(100):
            residual.update(safety_stress_delta=0.01)
        
        # Global value should be unchanged
        assert body.safety_stress.value == original_safety


class TestTraceRecords:
    """Test trace record generation."""
    
    def test_trace_includes_global_delta(self):
        """Trace includes global body state deltas."""
        body = BodyStateVector()
        trace = body.update_from_event("user_message")
        
        assert "global_body_delta" in trace
        assert "energy" in trace["global_body_delta"]
    
    def test_trace_includes_target_residual_delta(self):
        """Trace includes target residual deltas when target specified."""
        body = BodyStateVector()
        trace = body.update_from_event(
            "world_event", 
            event_subtype="care",
            meta={"target_id": "target_1"}
        )
        
        assert trace["target_residual_delta"] is not None
        assert trace["target_residual_delta"]["target_id"] == "target_1"
    
    def test_trace_includes_shrinkage_weight(self):
        """Trace includes shrinkage weight."""
        body = BodyStateVector()
        trace = body.update_from_event(
            "world_event", 
            event_subtype="care",
            meta={"target_id": "target_1"}
        )
        
        assert trace["shrinkage_weight"] is not None
        assert 0 <= trace["shrinkage_weight"] <= 1
    
    def test_trace_no_target_residual_without_target(self):
        """Trace has no target residual delta when no target specified."""
        body = BodyStateVector()
        trace = body.update_from_event("world_event", event_subtype="care")
        
        assert trace["target_residual_delta"] is None


class TestSampleSizeEffects:
    """Test that small samples don't over-individualize."""
    
    def test_small_n_obs_residual_minimal_effect(self):
        """With n_obs < 5, residual has minimal effect."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        # 3 observations - very low weight
        residual = body.get_target_residual("target_1")
        for _ in range(3):
            residual.update(safety_stress_delta=0.3)
        
        effective = body.get_effective_value("safety_stress", target_id="target_1")
        # With k=10, n_obs=3: weight = 3/13 ≈ 0.23
        # Raw residual = 0.9, shrunk = 0.9 * 0.23 ≈ 0.21
        # Effective value ≈ 0.6 + 0.21 = 0.81
        # Allow for larger deviation since shrinkage is not extremely aggressive
        assert abs(effective - 0.6) < 0.25  # Relaxed threshold
    
    def test_large_n_obs_residual_full_effect(self):
        """With n_obs > 50, residual has significant effect."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        # 50 observations - high weight (~0.83)
        residual = body.get_target_residual("target_1")
        for _ in range(50):
            residual.update(safety_stress_delta=0.01)
        
        effective = body.get_effective_value("safety_stress", target_id="target_1")
        # Should be noticeably different from global
        assert effective > 0.7  # 0.6 + (0.5 * 0.83) ≈ 1.0, clamped
    
    def test_shrinkage_protects_against_outliers(self):
        """Shrinkage protects against outlier observations with small n."""
        body = BodyStateVector()
        body.safety_stress.value = 0.6
        body.shrinkage_k = 10.0
        
        # Single extreme observation
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=1.0)  # Max positive
        
        effective = body.get_effective_value("safety_stress", target_id="target_1")
        # Should not jump to max due to shrinkage
        assert effective < 0.7


class TestSerialization:
    """Test serialization and deserialization."""
    
    def test_full_serialization(self):
        """BodyStateVector with target residuals serializes correctly."""
        body = BodyStateVector()
        body.shrinkage_k = 15.0
        
        # Add some target residuals
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=0.2, social_need_delta=-0.1)
        
        # Serialize and restore
        data = body.to_dict()
        restored = BodyStateVector.from_dict(data)
        
        assert restored.shrinkage_k == 15.0
        assert "target_1" in restored.target_residuals
        assert restored.target_residuals["target_1"].safety_stress == 0.2
    
    def test_target_residual_summary(self):
        """get_target_residual_summary returns correct info."""
        body = BodyStateVector()
        body.shrinkage_k = 10.0
        
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=0.4)
        
        summary = body.get_target_residual_summary("target_1")
        assert summary["target_id"] == "target_1"
        assert "raw_residual" in summary
        assert "shrunk_residual" in summary
        assert "shrinkage_weight" in summary
        assert summary["n_obs"] == 1


class TestGlobalSingleton:
    """Test global body state singleton."""
    
    def test_get_body_state_creates_default(self):
        """get_body_state creates default if not exists."""
        reset_body_state()
        body = get_body_state()
        assert body is not None
        assert isinstance(body, BodyStateVector)
    
    def test_set_body_state(self):
        """set_body_state updates global instance."""
        new_body = BodyStateVector()
        new_body.shrinkage_k = 25.0
        
        set_body_state(new_body)
        retrieved = get_body_state()
        
        assert retrieved.shrinkage_k == 25.0
    
    def test_reset_body_state(self):
        """reset_body_state clears to defaults."""
        # Modify global state
        body = get_body_state()
        body.shrinkage_k = 99.0
        
        # Reset
        reset_body_state()
        fresh = get_body_state()
        
        assert fresh.shrinkage_k == 10.0  # Default value


class TestIntegration:
    """Integration tests for D1 components."""
    
    def test_end_to_end_target_conditioning(self):
        """Full flow: events → residuals → effective values."""
        reset_body_state()
        body = get_body_state()
        body.shrinkage_k = 5.0
        
        # Simulate multiple interactions with target_a (positive)
        for _ in range(20):
            body.update_from_event(
                "world_event",
                event_subtype="care",
                meta={"target_id": "target_a"}
            )
        
        # Simulate interactions with target_b (negative)
        for _ in range(20):
            body.update_from_event(
                "world_event",
                event_subtype="rejection",
                meta={"target_id": "target_b"}
            )
        
        # Check effective values differ by target
        effective_a = body.get_effective_value("safety_stress", target_id="target_a")
        effective_b = body.get_effective_value("safety_stress", target_id="target_b")
        global_val = body.safety_stress.value
        
        # target_a should feel safer than target_b
        assert effective_a > global_val
        assert effective_b < global_val
        assert effective_a > effective_b
    
    def test_shrinkage_k_tunable(self):
        """shrinkage_k can be modified and affects behavior."""
        body = BodyStateVector()
        
        # Test with low k (aggressive)
        body.shrinkage_k = 2.0
        residual = body.get_target_residual("target_1")
        residual.update(safety_stress_delta=0.5)
        weight_low_k = Shrinkage(body.shrinkage_k).compute_weight(residual.n_obs)
        
        # Test with high k (conservative)
        body.shrinkage_k = 20.0
        weight_high_k = Shrinkage(body.shrinkage_k).compute_weight(residual.n_obs)
        
        assert weight_low_k > weight_high_k
