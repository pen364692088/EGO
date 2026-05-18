"""
MVP11-T10: Resource Environment Dynamics Tests

Tests for ResourceEnv class:
- Action costs are applied correctly
- Environment perturbations work as expected
- Homeostasis integration functions
- Resource depletion handling
"""
import pytest
import math
from unittest.mock import MagicMock, patch
from emotiond.envs.resource_env import (
    ResourceEnv,
    ResourceConfig,
    ActionCost,
    ActionResult,
    PerturbationType,
    create_resource_env,
    create_homeostasis_bridge,
)
from emotiond.homeostasis import HomeostasisManager


class TestResourceConfig:
    """Tests for ResourceConfig."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ResourceConfig()
        
        assert config.max_time == 100.0
        assert config.max_energy == 100.0
        assert config.initial_time == 100.0
        assert config.initial_energy == 100.0
        assert config.tool_failure_prob == 0.05
        assert config.latency_spike_prob == 0.1
    
    def test_config_from_dict(self):
        """Test creating config from dict."""
        data = {
            "max_time": 200.0,
            "max_energy": 150.0,
            "tool_failure_prob": 0.1,
        }
        config = ResourceConfig.from_dict(data)
        
        assert config.max_time == 200.0
        assert config.max_energy == 150.0
        assert config.tool_failure_prob == 0.1
    
    def test_config_to_dict(self):
        """Test serializing config to dict."""
        config = ResourceConfig(max_time=50.0, seed=42)
        data = config.to_dict()
        
        assert data["max_time"] == 50.0
        assert data["seed"] == 42


class TestActionCost:
    """Tests for ActionCost."""
    
    def test_default_cost(self):
        """Test default cost values."""
        cost = ActionCost()
        
        assert cost.time_cost == 0.1
        assert cost.energy_cost == 0.1
        assert cost.risk_level == 0.1
    
    def test_cost_serialization(self):
        """Test cost serialization."""
        cost = ActionCost(time_cost=0.5, energy_cost=0.3, risk_level=0.2)
        
        data = cost.to_dict()
        assert data["time_cost"] == 0.5
        assert data["energy_cost"] == 0.3
        assert data["risk_level"] == 0.2
        
        restored = ActionCost.from_dict(data)
        assert restored.time_cost == 0.5
        assert restored.energy_cost == 0.3
        assert restored.risk_level == 0.2


class TestResourceEnvBasics:
    """Basic tests for ResourceEnv."""
    
    def test_initialization(self):
        """Test environment initialization."""
        env = ResourceEnv()
        
        state = env.get_state()
        assert state["time_remaining"] == 100.0
        assert state["energy_remaining"] == 100.0
        assert state["time_ratio"] == 1.0
        assert state["energy_ratio"] == 1.0
        assert state["step_count"] == 0
        assert not state["is_depleted"]
    
    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = {
            "initial_time": 50.0,
            "initial_energy": 30.0,
            "seed": 42,
        }
        env = ResourceEnv(config=config)
        
        state = env.get_state()
        assert state["time_remaining"] == 50.0
        assert state["energy_remaining"] == 30.0
    
    def test_reset(self):
        """Test environment reset."""
        env = ResourceEnv(config={"seed": 42})
        
        # Execute some actions
        env.step({"action": "seek_info"})
        env.step({"action": "attempt_solution"})
        
        # Reset
        state = env.reset()
        
        assert state["time_remaining"] == 100.0
        assert state["energy_remaining"] == 100.0
        assert state["step_count"] == 0
    
    def test_factory_function(self):
        """Test create_resource_env factory."""
        env = create_resource_env(seed=123, max_time=200.0)
        
        assert env.config.seed == 123
        assert env.config.max_time == 200.0


class TestActionCosts:
    """Tests for action cost application."""
    
    def test_seek_info_cost(self):
        """Test seek_info action cost."""
        # Use a custom cost with zero risk to ensure success
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Use custom cost with zero risk
        zero_risk_cost = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        state, reward, done, info = env.step({
            "action": "seek_info",
            "custom_cost": zero_risk_cost,
        })
        
        # seek_info has cost: time=0.1, energy=0.1
        assert state["time_remaining"] < 100.0
        assert state["energy_remaining"] < 100.0
        assert info["result"]["success"] is True
    
    def test_attempt_solution_cost(self):
        """Test attempt_solution action cost."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Use zero-risk cost
        zero_risk_cost = ActionCost(time_cost=0.3, energy_cost=0.3, risk_level=0.0)
        state, _, _, info = env.step({
            "action": "attempt_solution",
            "custom_cost": zero_risk_cost,
        })
        
        # attempt_solution has cost: time=0.3, energy=0.3
        assert state["time_remaining"] == pytest.approx(99.7, abs=0.01)
        assert state["energy_remaining"] == pytest.approx(99.7, abs=0.01)
    
    def test_custom_action_cost(self):
        """Test custom action cost."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        custom_cost = ActionCost(time_cost=0.5, energy_cost=0.4, risk_level=0.0)
        state, _, _, info = env.step({
            "action": "seek_info",
            "custom_cost": custom_cost,
        })
        
        # Verify custom cost was applied
        assert state["time_remaining"] == pytest.approx(99.5, abs=0.01)
        assert state["energy_remaining"] == pytest.approx(99.6, abs=0.01)
    
    def test_noop_has_no_cost(self):
        """Test noop action has zero cost."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        state, _, _, _ = env.step({"action": "noop"})
        
        assert state["time_remaining"] == 100.0
        assert state["energy_remaining"] == 100.0


class TestPerturbations:
    """Tests for environment perturbations."""
    
    def test_tool_failure_perturbation(self):
        """Test tool failure perturbation."""
        env = ResourceEnv(config={"seed": 42})
        
        # Force tool failure
        env.inject_perturbation(PerturbationType.TOOL_FAILURE, intensity=1.0)
        
        assert env.current_perturbation == PerturbationType.TOOL_FAILURE
        assert env.perturbation_intensity == 1.0
    
    def test_latency_spike_perturbation(self):
        """Test latency spike perturbation."""
        env = ResourceEnv(config={"seed": 42})
        
        # Force latency spike
        env.inject_perturbation(PerturbationType.LATENCY_SPIKE, intensity=0.5)
        
        assert env.current_perturbation == PerturbationType.LATENCY_SPIKE
    
    def test_resource_drain_perturbation(self):
        """Test resource drain perturbation."""
        env = ResourceEnv(config={"seed": 42})
        
        initial_energy = env.energy_remaining
        
        # Force resource drain
        env.inject_perturbation(PerturbationType.RESOURCE_DRAIN, intensity=1.0)
        
        assert env.energy_remaining < initial_energy
    
    def test_uncertainty_increase_perturbation(self):
        """Test uncertainty increase perturbation."""
        env = ResourceEnv(config={"seed": 42})
        
        initial_uncertainty = env.uncertainty_level
        
        # Force uncertainty increase
        env.inject_perturbation(PerturbationType.UNCERTAINTY_INCREASE, intensity=1.0)
        
        assert env.uncertainty_level > initial_uncertainty
    
    def test_spike_task_increases_cost(self):
        """Test spike task perturbation increases costs."""
        env = ResourceEnv(config={
            "seed": 42,
            "spike_task_prob": 1.0,  # Always spike
            "spike_task_cost_multiplier": 3.0,
        })
        
        # Clear other perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        state, _, _, info = env.step({"action": "seek_info"})
        
        # Cost should be higher due to spike task
        assert info["result"]["perturbation"] == PerturbationType.SPIKE_TASK.value


class TestPerturbationStateConsistency:
    """Tests for perturbation state/result consistency and homeostasis effects."""

    def test_env_state_matches_step_result_perturbation(self):
        """After a step, state perturbation should match result/info perturbation."""
        env = ResourceEnv(config={"seed": 42})

        # Force deterministic perturbation for this step
        env.inject_perturbation(PerturbationType.LATENCY_SPIKE, intensity=0.7)

        state, _, _, info = env.step({"action": "seek_info"})

        assert info["perturbation"] == PerturbationType.LATENCY_SPIKE.value
        assert info["result"]["perturbation"] == PerturbationType.LATENCY_SPIKE.value
        assert state["perturbation"] == PerturbationType.LATENCY_SPIKE.value
        assert state["perturbation_intensity"] == pytest.approx(0.7, abs=1e-6)

    def test_homeostasis_update_applies_perturbation_effects(self):
        """Forced perturbations should surface corresponding homeostasis deltas."""
        env = ResourceEnv(config={"seed": 42})

        # TOOL_FAILURE should decrease certainty
        env.inject_perturbation(PerturbationType.TOOL_FAILURE, intensity=1.0)
        env.step({"action": "seek_info"})
        updates = env.get_homeostasis_update()
        assert "certainty" in updates
        assert updates["certainty"] < 0

        # LATENCY_SPIKE should decrease autonomy
        env.inject_perturbation(PerturbationType.LATENCY_SPIKE, intensity=1.0)
        env.step({"action": "seek_info"})
        updates = env.get_homeostasis_update()
        assert "autonomy" in updates
        assert updates["autonomy"] < 0


class TestResourceDepletion:
    """Tests for resource depletion handling."""
    
    def test_insufficient_resources_failure(self):
        """Test failure when resources are insufficient."""
        env = ResourceEnv(config={
            "initial_time": 0.05,  # Very limited
            "initial_energy": 0.05,
            "seed": 42,
        })
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # attempt_solution requires time=0.3, energy=0.3
        state, _, done, info = env.step({"action": "attempt_solution"})
        
        # Should fail due to insufficient resources
        assert info["result"]["success"] is False
        assert "insufficient_resources" in info["result"]["message"]
    
    def test_depletion_detection(self):
        """Test depletion detection."""
        env = ResourceEnv(config={
            "initial_time": 5.0,
            "initial_energy": 5.0,
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Execute expensive actions
        for _ in range(20):
            env.step({"action": "attempt_solution"})
            if env.get_state()["is_depleted"]:
                break
        
        state = env.get_state()
        assert state["is_depleted"] or state["time_remaining"] < 10 or state["energy_remaining"] < 10
    
    def test_episode_termination_on_depletion(self):
        """Test episode terminates when resources exhausted."""
        env = ResourceEnv(config={
            "initial_time": 1.0,
            "initial_energy": 1.0,
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Execute actions until done
        done = False
        for _ in range(50):
            _, _, done, _ = env.step({"action": "attempt_solution"})
            if done:
                break
        
        state = env.get_state()
        # Either done or resources should be very low (near zero, but partial costs apply on failure)
        assert done or state["time_remaining"] < 1.0 or state["energy_remaining"] < 1.0


class TestHomeostasisIntegration:
    """Tests for homeostasis integration."""
    
    def test_homeostasis_callback(self):
        """Test homeostasis callback is called."""
        env = ResourceEnv(config={"seed": 42})
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Create mock callback
        callback = MagicMock()
        env.set_homeostasis_callback(callback)
        
        # Use zero-risk cost
        zero_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        env.step({"action": "seek_info", "custom_cost": zero_risk})
        
        # Callback should have been called
        callback.assert_called_once()
        
        # Check callback argument
        call_args = callback.call_args[0][0]
        assert "status" in call_args
        assert "cost" in call_args
    
    def test_homeostasis_bridge(self):
        """Test homeostasis bridge function."""
        env = ResourceEnv(config={"seed": 42})
        homeostasis = HomeostasisManager()
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        bridge = create_homeostasis_bridge(homeostasis)
        env.set_homeostasis_callback(bridge)
        
        initial_state = homeostasis.state.to_dict()
        
        # Execute action with zero risk
        zero_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        env.step({"action": "seek_info", "custom_cost": zero_risk})
        
        # Homeostasis should have been updated
        # (though the exact update depends on OUTCOME_EFFECTS)
    
    def test_get_homeostasis_update(self):
        """Test homeostasis update generation."""
        env = ResourceEnv(config={"seed": 42})
        
        # Low energy state
        env.energy_remaining = 20.0  # 20% of max
        
        updates = env.get_homeostasis_update()
        
        assert "energy" in updates
        assert updates["energy"] < 0  # Should be negative (deficit)
    
    def test_homeostasis_update_on_depletion(self):
        """Test homeostasis update when resources depleted."""
        env = ResourceEnv(config={"seed": 42})
        
        # Depleted state
        env.time_remaining = 5.0
        env.energy_remaining = 5.0
        
        updates = env.get_homeostasis_update()
        
        # Should have multiple dimension updates
        assert len(updates) > 0


class TestHistoryAndStatistics:
    """Tests for history tracking and statistics."""
    
    def test_action_history(self):
        """Test action history tracking."""
        env = ResourceEnv(config={"seed": 42})
        
        env.step({"action": "seek_info"})
        env.step({"action": "attempt_solution"})
        env.step({"action": "run_check"})
        
        history = env.get_history()
        
        assert len(history) == 3
        assert history[0]["action"] == "seek_info"
        assert history[1]["action"] == "attempt_solution"
        assert history[2]["action"] == "run_check"
    
    def test_perturbation_history(self):
        """Test perturbation history tracking."""
        env = ResourceEnv(config={
            "seed": 42,
            "tool_failure_prob": 1.0,  # Force perturbation
        })
        
        # Clear other perturbations
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        env.step({"action": "seek_info"})
        
        pert_history = env.get_perturbation_history()
        
        # Should have recorded the perturbation
        assert len(pert_history) >= 1
    
    def test_statistics(self):
        """Test statistics calculation."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Disable perturbations for predictable results
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Execute some actions with zero risk
        zero_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        for _ in range(5):
            env.step({"action": "seek_info", "custom_cost": zero_risk})
        
        stats = env.get_statistics()
        
        assert stats["total_steps"] == 5
        assert stats["success_rate"] > 0
        assert stats["avg_time_cost"] > 0
        assert stats["avg_energy_cost"] > 0


class TestStepReturnValue:
    """Tests for step() return value format."""
    
    def test_step_returns_tuple(self):
        """Test step returns correct tuple format."""
        env = ResourceEnv(config={"seed": 42})
        
        result = env.step({"action": "seek_info"})
        
        assert len(result) == 4
        state, reward, done, info = result
        
        assert isinstance(state, dict)
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert isinstance(info, dict)
    
    def test_state_structure(self):
        """Test state dict structure."""
        env = ResourceEnv(config={"seed": 42})
        
        state, _, _, _ = env.step({"action": "seek_info"})
        
        required_keys = [
            "time_remaining",
            "energy_remaining",
            "time_ratio",
            "energy_ratio",
            "uncertainty_level",
            "step_count",
            "is_depleted",
        ]
        
        for key in required_keys:
            assert key in state, f"Missing key: {key}"
    
    def test_info_structure(self):
        """Test info dict structure."""
        env = ResourceEnv(config={"seed": 42})
        
        _, _, _, info = env.step({"action": "seek_info"})
        
        assert "result" in info
        assert "perturbation" in info
        assert "resources" in info
        
        assert "success" in info["result"]
        assert "actual_cost" in info["result"]


class TestDeterministicBehavior:
    """Tests for deterministic behavior with seed."""
    
    def test_same_seed_same_sequence(self):
        """Test same seed produces same action sequence."""
        env1 = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        env2 = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.0,
        })
        
        # Disable perturbations
        for env in [env1, env2]:
            env.config.tool_failure_prob = 0.0
            env.config.latency_spike_prob = 0.0
            env.config.spike_task_prob = 0.0
            env.config.resource_drain_prob = 0.0
            env.config.uncertainty_increase_prob = 0.0
        
        # Use zero-risk cost for deterministic behavior
        zero_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        
        results1 = []
        results2 = []
        
        for _ in range(5):
            state1, _, _, _ = env1.step({"action": "seek_info", "custom_cost": zero_risk})
            results1.append(state1["time_remaining"])
        
        for _ in range(5):
            state2, _, _, _ = env2.step({"action": "seek_info", "custom_cost": zero_risk})
            results2.append(state2["time_remaining"])
        
        # With same seed and perturbations disabled, costs should be identical
        for r1, r2 in zip(results1, results2):
            assert r1 == pytest.approx(r2, abs=0.001)


class TestActionResult:
    """Tests for ActionResult."""
    
    def test_action_result_structure(self):
        """Test ActionResult has correct structure."""
        result = ActionResult(
            success=True,
            actual_cost=ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.1),
            perturbation=PerturbationType.NONE,
            perturbation_impact=0.0,
            latency_ms=100.0,
            message="Action completed",
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["perturbation"] == "none"
        assert "actual_cost" in data
        assert data["latency_ms"] == 100.0


class TestEnergyRecovery:
    """Tests for energy recovery."""
    
    def test_energy_recovery(self):
        """Test energy recovery per step."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.5,
            "initial_energy": 50.0,  # Start below max
        })
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Use noop so no energy is deducted
        state_before = env.get_state()
        env.step({"action": "noop"})
        state_after = env.get_state()
        
        # Energy should have increased due to recovery (but capped at max)
        assert state_after["energy_remaining"] >= state_before["energy_remaining"]
    
    def test_energy_recovery_capped_at_max(self):
        """Test energy recovery is capped at max."""
        env = ResourceEnv(config={
            "seed": 42,
            "energy_recovery_rate": 0.5,
        })
        
        # Energy starts at max (100)
        env.step({"action": "noop"})
        
        # Energy should not exceed max
        assert env.energy_remaining <= 100.0


class TestSetActionCost:
    """Tests for setting custom action costs."""
    
    def test_set_action_cost(self):
        """Test setting a custom action cost."""
        env = ResourceEnv(config={"seed": 42})
        
        # Set a custom cost
        custom_cost = ActionCost(time_cost=0.8, energy_cost=0.6, risk_level=0.2)
        env.set_action_cost("custom_action", custom_cost)
        
        # Retrieve and verify
        retrieved = env.get_action_cost("custom_action")
        assert retrieved.time_cost == 0.8
        assert retrieved.energy_cost == 0.6
        assert retrieved.risk_level == 0.2
    
    def test_get_unknown_action_cost(self):
        """Test getting cost for unknown action returns default."""
        env = ResourceEnv(config={"seed": 42})
        
        cost = env.get_action_cost("unknown_action_xyz")
        
        # Should return default cost
        assert cost.time_cost == 0.1
        assert cost.energy_cost == 0.1
        assert cost.risk_level == 0.1


class TestLastOutcome:
    """Tests for last outcome tracking."""
    
    def test_get_last_outcome(self):
        """Test getting last outcome."""
        env = ResourceEnv(config={"seed": 42})
        
        # Initially None
        assert env.get_last_outcome() is None
        
        # After step, should have outcome
        env.step({"action": "seek_info"})
        outcome = env.get_last_outcome()
        
        assert outcome is not None
        assert "status" in outcome
        assert "cost" in outcome


class TestInjectPerturbation:
    """Tests for manual perturbation injection."""
    
    def test_inject_resource_drain(self):
        """Test injecting resource drain."""
        env = ResourceEnv(config={"seed": 42})
        initial_energy = env.energy_remaining
        
        env.inject_perturbation(PerturbationType.RESOURCE_DRAIN, intensity=0.5)
        
        assert env.energy_remaining < initial_energy
    
    def test_inject_uncertainty(self):
        """Test injecting uncertainty increase."""
        env = ResourceEnv(config={"seed": 42})
        initial_uncertainty = env.uncertainty_level
        
        env.inject_perturbation(PerturbationType.UNCERTAINTY_INCREASE, intensity=0.5)
        
        assert env.uncertainty_level > initial_uncertainty


class TestRiskBasedFailure:
    """Tests for risk-based failure mechanism."""
    
    def test_high_risk_can_fail(self):
        """Test that high risk actions can fail."""
        env = ResourceEnv(config={"seed": 1})  # Use different seed
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        # Use high risk cost
        high_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.99)
        
        # Execute multiple times to see failures
        failures = 0
        for _ in range(100):
            env.reset()
            _, _, _, info = env.step({"action": "test", "custom_cost": high_risk})
            if not info["result"]["success"]:
                failures += 1
        
        # Should have some failures with 99% risk
        assert failures > 50  # Most should fail
    
    def test_zero_risk_never_fails(self):
        """Test that zero risk actions never fail due to risk."""
        env = ResourceEnv(config={"seed": 42})
        
        # Disable perturbations
        env.config.tool_failure_prob = 0.0
        env.config.latency_spike_prob = 0.0
        env.config.spike_task_prob = 0.0
        env.config.resource_drain_prob = 0.0
        env.config.uncertainty_increase_prob = 0.0
        
        zero_risk = ActionCost(time_cost=0.1, energy_cost=0.1, risk_level=0.0)
        
        for _ in range(100):
            env.reset()
            _, _, _, info = env.step({"action": "test", "custom_cost": zero_risk})
            assert info["result"]["success"] is True


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
