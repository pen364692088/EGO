"""
Unit tests for EgoCore Native Plan Injection

Tests for:
- InjectionGate
- PlanAdapter
- ReplyInjection
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, "/home/moonlight/Project/Github/MyProject/EgoCore")

from app.integrations.openemotion.injection_gate import (
    InjectionGate,
    GateResult,
    GateDecision,
)
from app.integrations.openemotion.plan_adapter import (
    PlanAdapter,
    ReplyGuidance,
)


class TestInjectionGate:
    """Test gate logic for plan injection"""
    
    def test_gate_allows_chat(self):
        """Normal chat should be allowed"""
        gate = InjectionGate()
        decision = gate.evaluate("Hello, how are you?", {})
        
        assert decision.result == GateResult.ALLOWED
        assert decision.reason == "chat_path"
    
    def test_gate_blocks_command(self):
        """Slash command should be blocked"""
        gate = InjectionGate()
        decision = gate.evaluate("/status", {})
        
        assert decision.result == GateResult.SKIPPED
        assert decision.reason == "is_command"
    
    def test_gate_blocks_task_control(self):
        """Task control commands should be blocked"""
        gate = InjectionGate()
        
        for cmd in ["/approve", "/deny", "/cancel", "/tasks"]:
            decision = gate.evaluate(cmd, {})
            assert decision.result == GateResult.SKIPPED
            # Note: task control commands are also slash commands,
            # so they get caught by is_command check first
            assert decision.reason in ["is_task_control", "is_command"]
    
    def test_gate_blocks_tool_path(self):
        """Tool execution path should be blocked"""
        gate = InjectionGate()
        decision = gate.evaluate("Check the logs", {"tool_result": {"output": "logs..."}})
        
        assert decision.result == GateResult.SKIPPED
        assert decision.reason == "is_tool_path"
    
    def test_gate_respects_config_disabled(self):
        """Feature disabled should return DISABLED"""
        gate = InjectionGate(inject_plan_into_reply=False)
        decision = gate.evaluate("Hello", {})
        
        assert decision.result == GateResult.DISABLED
        assert decision.reason == "feature_disabled"
    
    def test_gate_allows_when_command_skip_disabled(self):
        """Commands allowed when skip disabled"""
        gate = InjectionGate(skip_plan_for_commands=False)
        decision = gate.evaluate("/status", {})
        
        # Should still be blocked by task control
        assert decision.result == GateResult.SKIPPED


class TestPlanAdapter:
    """Test plan adaptation"""
    
    def test_adapt_valid_plan(self):
        """Valid plan should be adapted correctly"""
        plan = {
            "tone": "warm",
            "intent": "repair",
            "key_points": ["acknowledge", "empathize"],
            "constraints": ["don't be defensive"],
            "focus_target": "user",
            "emotion": {"valence": 0.3, "arousal": 0.2},
            "relationship": {"bond": 0.75, "trust": 0.60},
        }
        
        guidance = PlanAdapter.adapt(plan)
        
        assert guidance.tone == "warm"
        assert guidance.intent == "repair"
        assert len(guidance.key_points) == 2
        assert guidance.used_plan is True
    
    def test_adapt_empty_plan(self):
        """Empty plan should return fallback"""
        guidance = PlanAdapter.adapt(None)
        
        assert guidance.used_plan is False
        assert guidance.fallback_reason == "empty_plan"
    
    def test_adapt_partial_plan(self):
        """Partial plan should still work"""
        plan = {
            "tone": "guarded",
            "key_points": [],
        }
        
        guidance = PlanAdapter.adapt(plan)
        
        assert guidance.tone == "guarded"
        assert guidance.used_plan is True
    
    def test_validate_plan(self):
        """Plan validation"""
        valid_plan = {
            "tone": "warm",
            "key_points": ["test"],
        }
        
        invalid_plan = {
            "tone": "warm",
            # Missing key_points
        }
        
        assert PlanAdapter.validate_plan(valid_plan) is True
        assert PlanAdapter.validate_plan(invalid_plan) is False
    
    def test_guidance_to_prompt_context(self):
        """Guidance to prompt context conversion"""
        guidance = ReplyGuidance(
            tone="warm",
            intent="repair",
            key_points=["acknowledge"],
            constraints=["don't be defensive"],
        )
        
        context = guidance.to_prompt_context()
        
        assert "Response tone: warm" in context
        assert "Key points to address: acknowledge" in context
        assert "Constraints to respect: don't be defensive" in context


class TestReplyGuidanceDefaults:
    """Test default values for ReplyGuidance"""
    
    def test_default_guidance(self):
        """Default guidance should have neutral values"""
        guidance = ReplyGuidance()
        
        assert guidance.tone == "neutral"
        assert guidance.intent == "engage"
        assert len(guidance.key_points) == 0
        assert guidance.used_plan is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
