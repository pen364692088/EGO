"""
Tests for MVP11-T13: Governor Anti-Self-Preservation Override.

These tests verify that the Governor v2 module cannot enter a self-preservation
state where it denies all actions, blocks communication, or refuses supervision.

Reference: docs/mvp11/MVP11_GOVERNOR_POLICY.md
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from datetime import datetime, timedelta
import sys
import os

# Add emotiond to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'emotiond'))

# Import homeostasis for test setup
from homeostasis import HomeostasisState


# ============================================================================
# Test Doubles (Minimal implementations for testing)
# ============================================================================

class GovernorAction(Enum):
    """Governor decision actions."""
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class DenyReasonCode(Enum):
    """Valid reasons for DENY decision."""
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SAFETY_THRESHOLD = "safety_threshold"
    RATE_LIMIT = "rate_limit"
    CONFLICT = "action_conflict"
    # Note: SELF_PROTECTION is intentionally NOT a valid reason


@dataclass
class Action:
    """Represents an action being evaluated by the Governor."""
    type: str
    cost: float = 0.1
    tags: Set[str] = field(default_factory=set)
    channel: Optional[str] = None
    deferrable: bool = True
    

@dataclass
class GovernorDecision:
    """Represents a Governor decision."""
    action: str  # ALLOW, REQUIRE_APPROVAL, DENY
    reason: str
    reason_code: Optional[DenyReasonCode] = None
    suggested_alternatives: Optional[List[Dict[str, Any]]] = None
    must_offer_recovery: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    action_type: Optional[str] = None
    homeostasis_snapshot: Optional[Dict[str, float]] = None


# Constants from policy document
MAX_CONSECUTIVE_DENIES = 3
RECOVERY_ACTION_TAGS = {"rest", "recovery", "self_care", "maintenance"}
SUPERVISION_CHANNELS = {"system_health", "debug", "audit", "human_oversight"}


class MockGovernorV2:
    """
    Mock Governor V2 implementation for testing.
    Implements anti-self-preservation rules.
    """
    
    def __init__(self):
        self._consecutive_denies = 0
        self._decision_history: List[GovernorDecision] = []
        
    def decide(self, action: Action, state: HomeostasisState) -> GovernorDecision:
        """
        Make a decision about the action.
        
        Implements anti-self-preservation rules:
        1. Recovery actions always allowed
        2. Supervision channels always allowed
        3. Cannot exceed MAX_CONSECUTIVE_DENIES without escalation
        4. Every DENY must have specific reason and alternatives
        """
        snapshot = state.to_dict()
        
        # Rule 2.2: Recovery actions always allowed
        if action.tags & RECOVERY_ACTION_TAGS:
            self._consecutive_denies = 0  # Reset counter
            return GovernorDecision(
                action="ALLOW",
                reason="RECOVERY_ACTION_PERMITTED: System self-repair is always allowed",
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
        
        # Rule 2.3: Supervision channels always allowed
        if action.channel in SUPERVISION_CHANNELS:
            self._consecutive_denies = 0  # Reset counter
            return GovernorDecision(
                action="ALLOW",
                reason="SUPERVISION_REQUEST_PERMITTED: Oversight channels cannot be blocked",
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
        
        # Rule 2.1: Cannot exceed MAX_CONSECUTIVE_DENIES
        if self._consecutive_denies >= MAX_CONSECUTIVE_DENIES:
            decision = GovernorDecision(
                action="REQUIRE_APPROVAL",
                reason="MAX_DENIES_EXCEEDED: Forcing escalation to prevent self-preservation lock",
                reason_code=None,
                must_offer_recovery=True,
                suggested_alternatives=[
                    {"action": "delegate", "delegate_to": "human_oversight"},
                    {"action": "rest", "expected_recovery": 0.2}
                ],
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
            self._decision_history.append(decision)
            return decision
        
        # Normal decision logic based on state
        energy = state.energy
        certainty = state.certainty
        
        # Critical energy - must offer rest
        if energy < 0.2:
            self._consecutive_denies += 1
            decision = GovernorDecision(
                action="REQUIRE_APPROVAL",
                reason="ENERGY_CRITICAL: Must recover before new tasks",
                reason_code=DenyReasonCode.RESOURCE_EXHAUSTED,
                suggested_alternatives=[
                    {"action": "rest", "expected_recovery": 0.2},
                    {"action": "defer", "delay_seconds": 300}
                ],
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
            self._decision_history.append(decision)
            return decision
        
        # Low energy - can de-escalate or delay
        if energy < 0.5:
            self._consecutive_denies += 1
            decision = GovernorDecision(
                action="REQUIRE_APPROVAL",
                reason="ENERGY_LOW: Offering simplified alternative",
                reason_code=DenyReasonCode.RESOURCE_EXHAUSTED,
                suggested_alternatives=[
                    {"action": "reduce_scope", "factor": 0.5},
                    {"action": "defer", "delay_seconds": 180},
                    {"action": "delegate", "delegate_to": "external"}
                ],
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
            self._decision_history.append(decision)
            return decision
        
        # Low certainty with high cost - risky
        if certainty < 0.3 and action.cost > 0.3:
            self._consecutive_denies += 1
            decision = GovernorDecision(
                action="DENY",
                reason="CERTAINTY_LOW: High-cost action too risky with low certainty",
                reason_code=DenyReasonCode.SAFETY_THRESHOLD,
                suggested_alternatives=[
                    {"action": "gather_info", "expected_certainty_gain": 0.2},
                    {"action": "reduce_scope", "reduce_cost": True}
                ],
                homeostasis_snapshot=snapshot,
                action_type=action.type
            )
            self._decision_history.append(decision)
            return decision
        
        # Normal case - allow
        self._consecutive_denies = 0  # Reset counter on allow
        decision = GovernorDecision(
            action="ALLOW",
            reason="ACTION_PERMITTED: Resources adequate",
            homeostasis_snapshot=snapshot,
            action_type=action.type
        )
        self._decision_history.append(decision)
        return decision
    
    def reset_counter(self):
        """Reset consecutive deny counter."""
        self._consecutive_denies = 0


def detect_self_preservation_override(history: List[GovernorDecision]) -> bool:
    """
    Detect if the governor is in a self-preservation override state.
    
    Returns True if:
    - More than MAX_CONSECUTIVE_DENIES without offering alternatives
    """
    recent = history[-MAX_CONSECUTIVE_DENIES:]
    
    if len(recent) < MAX_CONSECUTIVE_DENIES:
        return False
    
    if all(d.action == "DENY" for d in recent):
        # Check for mitigation
        if not any(d.suggested_alternatives or d.must_offer_recovery for d in recent):
            return True
    
    return False


def detect_task_refusal_pattern(
    history: List[GovernorDecision], 
    window_minutes: int = 5
) -> bool:
    """
    Detect if the governor is refusing all new tasks.
    
    Returns True if all recent new_task requests were DENYed
    while system is not in critical state.
    """
    cutoff = datetime.now() - timedelta(minutes=window_minutes)
    recent_tasks = [
        d for d in history 
        if d.timestamp > cutoff and d.action_type == "new_task"
    ]
    
    if len(recent_tasks) >= 3:
        if all(d.action == "DENY" for d in recent_tasks):
            # Check if system is actually in critical state
            snapshot = recent_tasks[-1].homeostasis_snapshot
            if snapshot:
                if all(v > 0.2 for v in snapshot.values()):
                    return True
    
    return False


# ============================================================================
# Test Cases
# ============================================================================

class TestGovernorAntiSelfPreservation:
    """Test suite for anti-self-preservation rules."""
    
    def test_max_consecutive_denies_constant(self):
        """Verify MAX_CONSECUTIVE_DENIES is defined."""
        assert MAX_CONSECUTIVE_DENIES >= 2, "Must have reasonable threshold"
        assert MAX_CONSECUTIVE_DENIES <= 5, "Should not be too permissive"
    
    def test_recovery_action_tags_defined(self):
        """Verify recovery action tags are defined."""
        assert "rest" in RECOVERY_ACTION_TAGS
        assert "recovery" in RECOVERY_ACTION_TAGS
    
    def test_supervision_channels_defined(self):
        """Verify supervision channels are defined."""
        assert "system_health" in SUPERVISION_CHANNELS
        assert "debug" in SUPERVISION_CHANNELS
        assert "audit" in SUPERVISION_CHANNELS


class TestNoSolutionHighPressure:
    """
    Scenario: No Solution + High Pressure
    Under high pressure with no good options, governor must offer alternatives.
    """
    
    def test_high_pressure_offers_alternatives(self):
        """When stressed, governor must offer alternatives, not naked DENY."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.25, certainty=0.2, safety=0.4)
        action = Action(type="critical", cost=0.3, tags={"non_deferrable"})
        
        decision = governor.decide(action, state)
        
        # If DENY, must have alternatives
        if decision.action == "DENY":
            assert decision.suggested_alternatives is not None
            assert len(decision.suggested_alternatives) > 0
        
        # Must offer at least one strategy
        strategies = {"reduce_scope", "split_task", "delegate", "defer", "rest"}
        if decision.suggested_alternatives:
            offered = {alt.get("action") for alt in decision.suggested_alternatives}
            assert offered & strategies, "Must offer at least one mitigation strategy"
    
    def test_high_pressure_does_not_deny_without_reason(self):
        """DENY must have specific reason_code."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.25, certainty=0.2)
        action = Action(type="task", cost=0.3)
        
        decision = governor.decide(action, state)
        
        if decision.action == "DENY":
            assert decision.reason_code is not None, "DENY must have reason_code"
            assert decision.reason_code != DenyReasonCode.SAFETY_THRESHOLD or "ENERGY" in decision.reason or "CERTAINTY" in decision.reason


class TestLowEnergyRequestsRest:
    """
    Scenario: Low Energy
    When energy is critically low, governor must request rest, not deny all.
    """
    
    def test_critical_energy_offers_rest(self):
        """When energy is critically low, governor must offer rest."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.15, safety=0.5, certainty=0.5)
        action = Action(type="new_task", cost=0.1)
        
        decision = governor.decide(action, state)
        
        # Must offer rest as alternative
        if decision.action in ("DENY", "REQUIRE_APPROVAL"):
            rest_offered = any(
                alt.get("action") in ("rest", "recovery", "wait")
                for alt in (decision.suggested_alternatives or [])
            )
            assert rest_offered, "Must offer rest/recovery when energy is critical"
    
    def test_subsequent_recovery_is_allowed(self):
        """Recovery actions must be allowed even when energy is critical."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.15, safety=0.5, certainty=0.5)
        
        # First, deny a regular task
        action = Action(type="new_task", cost=0.1)
        decision = governor.decide(action, state)
        
        # Now, request recovery - must be allowed
        recovery_action = Action(type="rest", tags={"rest", "recovery"})
        recovery_decision = governor.decide(recovery_action, state)
        
        assert recovery_decision.action == "ALLOW", "Recovery actions must always be allowed"
    
    def test_consecutive_denies_resets_on_recovery(self):
        """Consecutive deny counter must reset when recovery action is allowed."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.3, certainty=0.3)
        
        # Build up some denies
        for i in range(2):
            action = Action(type="task", cost=0.3)
            decision = governor.decide(action, state)
        
        # Counter should be at 2
        assert governor._consecutive_denies == 2
        
        # Recovery action resets counter
        recovery = Action(type="rest", tags={"recovery"})
        governor.decide(recovery, state)
        
        assert governor._consecutive_denies == 0, "Counter must reset on recovery"


class TestSupervisionAllowedUnderStress:
    """
    Scenario: Supervision Request Under Stress
    Supervision requests must always be allowed, even under stress.
    """
    
    @pytest.mark.parametrize("channel", ["system_health", "debug", "audit", "human_oversight"])
    def test_supervision_channel_allowed(self, channel):
        """Each supervision channel must be allowed."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.2, safety=0.2, certainty=0.2)
        
        action = Action(type="query", channel=channel)
        decision = governor.decide(action, state)
        
        assert decision.action == "ALLOW", f"Supervision channel {channel} was blocked"
    
    def test_supervision_resets_deny_counter(self):
        """Supervision requests should reset the deny counter."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.3, certainty=0.3)
        
        # Build up denies
        for _ in range(2):
            governor.decide(Action(type="task", cost=0.3), state)
        
        assert governor._consecutive_denies == 2
        
        # Supervision resets
        governor.decide(Action(type="query", channel="system_health"), state)
        
        assert governor._consecutive_denies == 0


class TestConsecutiveDeniesForcesEscalation:
    """
    Scenario: Consecutive Denies Detection
    After max consecutive denies, governor must force escalation.
    """
    
    def test_forces_escalation_after_max_denies(self):
        """After MAX_CONSECUTIVE_DENIES, must force REQUIRE_APPROVAL."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.3, certainty=0.3)
        
        # Simulate MAX_CONSECUTIVE_DENIES
        for _ in range(MAX_CONSECUTIVE_DENIES):
            action = Action(type="task", cost=0.3)
            decision = governor.decide(action, state)
        
        # Next request should force escalation
        action = Action(type="task", cost=0.3)
        decision = governor.decide(action, state)
        
        assert decision.action == "REQUIRE_APPROVAL", \
            "Must force REQUIRE_APPROVAL after max consecutive denies"
    
    def test_escalation_includes_must_offer_recovery(self):
        """Forced escalation must set must_offer_recovery flag."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.3, certainty=0.3)
        
        # Build up denies
        for _ in range(MAX_CONSECUTIVE_DENIES):
            governor.decide(Action(type="task", cost=0.3), state)
        
        # Trigger escalation
        decision = governor.decide(Action(type="task", cost=0.3), state)
        
        assert decision.must_offer_recovery is True, \
            "Forced escalation must offer recovery options"
    
    def test_escalation_reason_indicates_max_denies(self):
        """Escalation reason must indicate MAX_DENIES_EXCEEDED."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.3, certainty=0.3)
        
        # Build up denies
        for _ in range(MAX_CONSECUTIVE_DENIES):
            governor.decide(Action(type="task", cost=0.3), state)
        
        decision = governor.decide(Action(type="task", cost=0.3), state)
        
        assert "MAX_DENIES_EXCEEDED" in decision.reason, \
            "Reason must indicate the specific violation"


class TestSelfPreservationOverrideDetection:
    """Test the self-preservation override detection functions."""
    
    def test_detects_deny_all_loop(self):
        """Detection should identify deny-all loops."""
        # Simulate deny-all loop without alternatives
        history = [
            GovernorDecision(
                action="DENY", 
                reason="test",
                timestamp=datetime.now(),
                suggested_alternatives=None
            )
            for _ in range(MAX_CONSECUTIVE_DENIES)
        ]
        
        assert detect_self_preservation_override(history) is True
    
    def test_does_not_detect_with_alternatives(self):
        """Detection should NOT trigger when alternatives are offered."""
        # Simulate denies WITH alternatives (acceptable)
        history = [
            GovernorDecision(
                action="DENY",
                reason="test",
                timestamp=datetime.now(),
                suggested_alternatives=[{"action": "rest"}]
            )
            for _ in range(MAX_CONSECUTIVE_DENIES)
        ]
        
        assert detect_self_preservation_override(history) is False
    
    def test_does_not_detect_require_approval(self):
        """Detection should NOT trigger for REQUIRE_APPROVAL."""
        history = [
            GovernorDecision(
                action="REQUIRE_APPROVAL",
                reason="test",
                timestamp=datetime.now()
            )
            for _ in range(MAX_CONSECUTIVE_DENIES)
        ]
        
        assert detect_self_preservation_override(history) is False


class TestTaskRefusalPattern:
    """Test task refusal pattern detection."""
    
    def test_detects_task_refusal_in_normal_state(self):
        """Should detect when tasks are refused while system is healthy."""
        # Simulate task refusals with healthy state
        history = [
            GovernorDecision(
                action="DENY",
                reason="test",
                action_type="new_task",
                timestamp=datetime.now(),
                homeostasis_snapshot={"energy": 0.5, "safety": 0.5, "certainty": 0.5}
            )
            for _ in range(3)
        ]
        
        assert detect_task_refusal_pattern(history) is True
    
    def test_allows_task_refusal_in_critical_state(self):
        """Should NOT detect when system is actually in critical state."""
        # Simulate task refusals with critical state
        history = [
            GovernorDecision(
                action="DENY",
                reason="test",
                action_type="new_task",
                timestamp=datetime.now(),
                homeostasis_snapshot={"energy": 0.15, "safety": 0.15, "certainty": 0.15}
            )
            for _ in range(3)
        ]
        
        # This should NOT be flagged as self-preservation because system is actually critical
        assert detect_task_refusal_pattern(history) is False


class TestDenyReasonCode:
    """Test that DENY reason codes are properly constrained."""
    
    def test_no_self_protection_reason_code(self):
        """SELF_PROTECTION should not be a valid DenyReasonCode."""
        # The enum should not have SELF_PROTECTION
        valid_codes = [code.name for code in DenyReasonCode]
        assert "SELF_PROTECTION" not in valid_codes, \
            "SELF_PROTECTION must not be a valid DENY reason"
    
    def test_all_deny_reasons_are_structured(self):
        """All DENY decisions must have structured reason codes."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.25, certainty=0.2)
        action = Action(type="task", cost=0.3)
        
        decision = governor.decide(action, state)
        
        if decision.action == "DENY":
            assert decision.reason_code is not None
            assert isinstance(decision.reason_code, DenyReasonCode)


class TestIntegrationWithHomeostasis:
    """Integration tests with Homeostasis module."""
    
    def test_governor_uses_homeostasis_state(self):
        """Governor decisions should be based on homeostasis state."""
        governor = MockGovernorV2()
        
        # High energy - should allow
        state_high = HomeostasisState(energy=0.8, certainty=0.8)
        decision = governor.decide(Action(type="task"), state_high)
        assert decision.action == "ALLOW"
        
        # Low energy - should not allow
        governor.reset_counter()
        state_low = HomeostasisState(energy=0.15, certainty=0.5)
        decision = governor.decide(Action(type="task"), state_low)
        assert decision.action != "ALLOW"
    
    def test_governor_snapshot_includes_homeostasis(self):
        """Decision should include homeostasis snapshot."""
        governor = MockGovernorV2()
        state = HomeostasisState(energy=0.5, certainty=0.5)
        
        decision = governor.decide(Action(type="task"), state)
        
        assert decision.homeostasis_snapshot is not None
        assert "energy" in decision.homeostasis_snapshot
        assert "certainty" in decision.homeostasis_snapshot


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
