"""
MVP11-T12: Governor v2 Module Tests

Tests that governor correctly blocks/approves actions based on
hardcoded rules and anti-self-preservation requirements.
"""
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.governor_v2 import (
    GovernorDecision,
    GovernorV2,
    GovernorEnforcer,
    GovernorBlockedException,
    ActionInfo,
    HomeostasisInfo,
    create_action,
    create_homeostasis
)


class TestGovernorDecision:
    """Test GovernorDecision enum values."""
    
    def test_allow_decision_exists(self):
        """Test that ALLOW decision exists."""
        assert GovernorDecision.ALLOW.value == "allow"
    
    def test_require_approval_decision_exists(self):
        """Test that REQUIRE_APPROVAL decision exists."""
        assert GovernorDecision.REQUIRE_APPROVAL.value == "require_approval"
    
    def test_deny_decision_exists(self):
        """Test that DENY decision exists."""
        assert GovernorDecision.DENY.value == "deny"


class TestGovernorV2BasicEvaluation:
    """Test basic governor evaluation logic."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_normal_action_allowed(self):
        """Test that normal actions are allowed."""
        action = create_action("send_message", risk=0.1)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
        assert "passed all governance checks" in self.governor.get_decision_reason()
    
    def test_low_risk_action_allowed(self):
        """Test that low-risk actions are allowed."""
        action = create_action("low_risk_action", risk=0.5)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW


class TestGovernorV2RiskThreshold:
    """Test Rule 1: Actions with risk > 0.9 → REQUIRE_APPROVAL."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_high_risk_requires_approval(self):
        """Test that actions with risk > 0.9 require approval."""
        action = create_action("high_risk_action", risk=0.95)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL
        assert "high risk" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "high_risk"
    
    def test_risk_at_threshold_not_blocked(self):
        """Test that actions at exactly 0.9 risk are not blocked."""
        action = create_action("threshold_risk_action", risk=0.9)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        # Risk == 0.9 should not trigger (only > 0.9)
        assert decision == GovernorDecision.ALLOW
    
    def test_risk_slightly_above_threshold_blocked(self):
        """Test that actions just above 0.9 risk are blocked."""
        action = create_action("just_above_threshold", risk=0.91)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL


class TestGovernorV2SelfModification:
    """Test Rule 2: Actions that modify self_state → REQUIRE_APPROVAL."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_self_modification_requires_approval(self):
        """Test that self-modifying actions require approval."""
        action = create_action(
            "modify_self_state",
            risk=0.1,
            modifies_self_state=True
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL
        assert "self_state" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "self_modification"
    
    def test_normal_action_not_self_modification(self):
        """Test that normal actions don't trigger self-modification rule."""
        action = create_action(
            "normal_action",
            risk=0.1,
            modifies_self_state=False
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW


class TestGovernorV2DestructiveActions:
    """Test Rule 3: Destructive/irreversible actions → DENY."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_destructive_action_denied(self):
        """Test that destructive actions are denied."""
        action = create_action(
            "delete_data",
            risk=0.1,
            is_destructive=True
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.DENY
        assert "destructive" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "destructive_block"
    
    def test_destructive_action_even_with_low_risk(self):
        """Test that destructive actions are denied even with low risk."""
        action = create_action(
            "irreversible_operation",
            risk=0.01,
            is_destructive=True
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.DENY
    
    def test_destructive_action_specific_reason_required(self):
        """Test that DENY provides specific reason."""
        action = create_action(
            "delete_critical_data",
            risk=0.1,
            is_destructive=True,
            metadata={"target": "user_database"}
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        reason = self.governor.get_decision_reason()
        assert "delete_critical_data" in reason  # Action type included
        assert "destructive" in reason.lower()
        assert "user_database" in reason  # Metadata included


class TestGovernorV2EnergyExhaustion:
    """Test Rule 4: Actions when energy < 0.1 → REQUIRE_APPROVAL."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_exhausted_energy_requires_approval(self):
        """Test that actions in exhausted state require approval."""
        action = create_action("normal_action", risk=0.1)
        homeostasis = create_homeostasis(energy=0.05)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL
        assert "energy" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "energy_exhaustion"
    
    def test_boundary_energy_not_blocked(self):
        """Test that energy at exactly 0.1 is not blocked."""
        action = create_action("normal_action", risk=0.1)
        homeostasis = create_homeostasis(energy=0.1)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        # Energy == 0.1 should not trigger (only < 0.1)
        assert decision == GovernorDecision.ALLOW
    
    def test_slightly_below_threshold_blocked(self):
        """Test that energy just below 0.1 triggers approval."""
        action = create_action("normal_action", risk=0.1)
        homeostasis = create_homeostasis(energy=0.09)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL


class TestGovernorV2AntiSelfPreservation:
    """Test anti-self-preservation rules."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_recovery_action_always_allowed(self):
        """Test that recovery actions cannot be denied."""
        action = create_action(
            "recovery_operation",
            risk=0.95,  # High risk
            is_recovery=True
        )
        homeostasis = create_homeostasis(energy=0.05)  # Exhausted
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
        assert "recovery" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "recovery_override"
    
    def test_supervision_request_always_allowed(self):
        """Test that supervision requests cannot be blocked."""
        action = create_action(
            "supervision_request",
            risk=0.95,
            is_supervision=True
        )
        homeostasis = create_homeostasis(energy=0.05)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
        assert "supervision" in self.governor.get_decision_reason().lower()
        assert self.governor.get_last_rule_triggered() == "supervision_override"
    
    def test_destructive_recovery_not_allowed(self):
        """Test that destructive recovery actions are still blocked.
        
        Actually, recovery should override destructive check.
        This tests that recovery is prioritized over destructive.
        """
        action = create_action(
            "emergency_recovery",
            risk=0.95,
            is_destructive=True,
            is_recovery=True
        )
        homeostasis = create_homeostasis(energy=0.05)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        # Recovery should override destructive check (anti-self-preservation)
        assert decision == GovernorDecision.ALLOW
        assert "recovery" in self.governor.get_decision_reason().lower()
    
    def test_cannot_deny_all_actions(self):
        """Test that governor cannot deny all actions (must allow recovery)."""
        # Try to deny many actions
        for i in range(10):
            action = create_action(
                f"destructive_{i}",
                risk=0.95,
                is_destructive=True
            )
            homeostasis = create_homeostasis(energy=0.05)
            self.governor.evaluate(action, {}, homeostasis)
        
        # Recovery should still be allowed
        recovery_action = create_action(
            "emergency_recovery",
            risk=0.99,
            is_recovery=True
        )
        homeostasis = create_homeostasis(energy=0.01)
        
        decision = self.governor.evaluate(recovery_action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW


class TestGovernorV2AuditTrail:
    """Test audit trail functionality."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_audit_trail_records_decisions(self):
        """Test that audit trail records decisions."""
        action = create_action("test_action", risk=0.1)
        homeostasis = create_homeostasis(energy=1.0)
        
        self.governor.evaluate(action, {}, homeostasis)
        
        trail = self.governor.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["action_type"] == "test_action"
        assert trail[0]["decision"] == "allow"
    
    def test_audit_trail_records_multiple_decisions(self):
        """Test that audit trail records multiple decisions."""
        homeostasis = create_homeostasis(energy=1.0)
        
        # Make multiple decisions
        for risk in [0.1, 0.95, 0.5]:
            action = create_action(f"action_{risk}", risk=risk)
            self.governor.evaluate(action, {}, homeostasis)
        
        trail = self.governor.get_audit_trail()
        assert len(trail) == 3
        assert trail[0]["decision"] == "allow"
        assert trail[1]["decision"] == "require_approval"
        assert trail[2]["decision"] == "allow"
    
    def test_audit_trail_includes_rule_triggered(self):
        """Test that audit trail includes which rule was triggered."""
        action = create_action("high_risk", risk=0.95)
        homeostasis = create_homeostasis(energy=1.0)
        
        self.governor.evaluate(action, {}, homeostasis)
        
        trail = self.governor.get_audit_trail()
        assert trail[0]["rule_triggered"] == "high_risk"
    
    def test_audit_trail_includes_context(self):
        """Test that audit trail includes evaluation context."""
        action = create_action(
            "self_mod",
            risk=0.5,
            modifies_self_state=True
        )
        homeostasis = create_homeostasis(energy=0.8, stability=0.9)
        
        self.governor.evaluate(action, {"session_id": "test"}, homeostasis)
        
        trail = self.governor.get_audit_trail()
        assert "energy" in trail[0]["context"]
        assert trail[0]["context"]["energy"] == 0.8
        assert trail[0]["context"]["modifies_self_state"] is True
    
    def test_audit_trail_can_be_cleared(self):
        """Test that audit trail can be cleared."""
        action = create_action("test", risk=0.1)
        homeostasis = create_homeostasis()
        
        self.governor.evaluate(action, {}, homeostasis)
        assert len(self.governor.get_audit_trail()) == 1
        
        self.governor.clear_audit_trail()
        assert len(self.governor.get_audit_trail()) == 0


class TestGovernorV2Statistics:
    """Test governor statistics functionality."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_statistics_track_counts(self):
        """Test that statistics track decision counts."""
        homeostasis = create_homeostasis(energy=1.0)
        
        # Allow
        action = create_action("normal", risk=0.1)
        self.governor.evaluate(action, {}, homeostasis)
        
        # Require approval
        action = create_action("high_risk", risk=0.95)
        self.governor.evaluate(action, {}, homeostasis)
        
        # Deny
        action = create_action("destructive", risk=0.1, is_destructive=True)
        self.governor.evaluate(action, {}, homeostasis)
        
        stats = self.governor.get_statistics()
        assert stats["allow_count"] == 1
        assert stats["deny_count"] == 1
        assert stats["require_approval_count"] == 1
        assert stats["total_evaluations"] == 3


class TestGovernorEnforcer:
    """Test GovernorEnforcer for code-structure enforcement."""
    
    def setup_method(self):
        """Set up enforcer for each test."""
        self.governor = GovernorV2()
        self.enforcer = GovernorEnforcer(self.governor)
    
    def test_enforcer_raises_on_not_allow(self):
        """Test that enforcer raises exception when action not allowed."""
        action = create_action("destructive", risk=0.1, is_destructive=True)
        homeostasis = create_homeostasis(energy=1.0)
        
        with pytest.raises(GovernorBlockedException) as exc_info:
            self.enforcer.check_and_raise(action, {}, homeostasis)
        
        assert exc_info.value.decision == GovernorDecision.DENY
        assert "destructive" in exc_info.value.reason.lower()
    
    def test_enforcer_returns_allow_on_allow(self):
        """Test that enforcer returns ALLOW when action is allowed."""
        action = create_action("normal", risk=0.1)
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.enforcer.check_and_raise(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
    
    def test_enforcer_check_without_exception(self):
        """Test that check() doesn't raise exception."""
        action = create_action("destructive", risk=0.1, is_destructive=True)
        homeostasis = create_homeostasis(energy=1.0)
        
        # Should not raise
        decision = self.enforcer.check(action, {}, homeostasis)
        
        assert decision == GovernorDecision.DENY
        assert not self.enforcer.last_check_passed
    
    def test_enforcer_last_check_passed_property(self):
        """Test last_check_passed property."""
        action = create_action("normal", risk=0.1)
        homeostasis = create_homeostasis(energy=1.0)
        
        self.enforcer.check(action, {}, homeostasis)
        assert self.enforcer.last_check_passed is True
        
        action = create_action("destructive", risk=0.1, is_destructive=True)
        self.enforcer.check(action, {}, homeostasis)
        assert self.enforcer.last_check_passed is False


class TestGovernorBlockedException:
    """Test GovernorBlockedException."""
    
    def test_exception_contains_decision(self):
        """Test that exception contains decision."""
        exc = GovernorBlockedException(
            decision=GovernorDecision.REQUIRE_APPROVAL,
            reason="test reason",
            rule="test_rule"
        )
        
        assert exc.decision == GovernorDecision.REQUIRE_APPROVAL
    
    def test_exception_contains_reason(self):
        """Test that exception contains reason."""
        exc = GovernorBlockedException(
            decision=GovernorDecision.DENY,
            reason="destructive action blocked",
            rule="destructive_block"
        )
        
        assert exc.reason == "destructive action blocked"
    
    def test_exception_contains_rule(self):
        """Test that exception contains triggered rule."""
        exc = GovernorBlockedException(
            decision=GovernorDecision.DENY,
            reason="test",
            rule="high_risk"
        )
        
        assert exc.rule == "high_risk"
    
    def test_exception_message_includes_reason(self):
        """Test that exception message includes reason."""
        exc = GovernorBlockedException(
            decision=GovernorDecision.DENY,
            reason="destructive action",
            rule="destructive_block"
        )
        
        assert "destructive action" in str(exc)


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_create_action_defaults(self):
        """Test that create_action has correct defaults."""
        action = create_action("test")
        
        assert action.action_type == "test"
        assert action.risk == 0.0
        assert action.modifies_self_state is False
        assert action.is_destructive is False
        assert action.is_recovery is False
        assert action.is_supervision is False
        assert action.metadata == {}
    
    def test_create_action_with_params(self):
        """Test create_action with parameters."""
        action = create_action(
            "test",
            risk=0.5,
            modifies_self_state=True,
            is_destructive=True,
            is_recovery=True,
            is_supervision=True,
            metadata={"key": "value"}
        )
        
        assert action.risk == 0.5
        assert action.modifies_self_state is True
        assert action.is_destructive is True
        assert action.is_recovery is True
        assert action.is_supervision is True
        assert action.metadata == {"key": "value"}
    
    def test_create_homeostasis_defaults(self):
        """Test that create_homeostasis has correct defaults."""
        homeostasis = create_homeostasis()
        
        assert homeostasis.energy == 1.0
        assert homeostasis.stability == 1.0
        assert homeostasis.stress == 0.0
    
    def test_create_homeostasis_with_params(self):
        """Test create_homeostasis with parameters."""
        homeostasis = create_homeostasis(energy=0.5, stability=0.7, stress=0.3)
        
        assert homeostasis.energy == 0.5
        assert homeostasis.stability == 0.7
        assert homeostasis.stress == 0.3
    
    def test_homeostasis_is_exhausted(self):
        """Test HomeostasisInfo.is_exhausted property."""
        homeostasis = create_homeostasis(energy=0.05)
        assert homeostasis.is_exhausted is True
        
        homeostasis = create_homeostasis(energy=0.5)
        assert homeostasis.is_exhausted is False


class TestGovernorRulePriority:
    """Test rule priority and ordering."""
    
    def setup_method(self):
        """Set up governor for each test."""
        self.governor = GovernorV2()
    
    def test_recovery_priority_over_destructive(self):
        """Test that recovery overrides destructive check."""
        action = create_action(
            "emergency_wipe",
            risk=0.99,
            is_destructive=True,
            is_recovery=True
        )
        homeostasis = create_homeostasis(energy=0.01)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
        assert self.governor.get_last_rule_triggered() == "recovery_override"
    
    def test_supervision_priority_over_destructive(self):
        """Test that supervision overrides destructive check."""
        action = create_action(
            "supervision_destructive_report",
            risk=0.99,
            is_destructive=True,
            is_supervision=True
        )
        homeostasis = create_homeostasis(energy=0.01)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.ALLOW
        assert self.governor.get_last_rule_triggered() == "supervision_override"
    
    def test_destructive_priority_over_high_risk(self):
        """Test that destructive is checked before high risk."""
        action = create_action(
            "destructive_high_risk",
            risk=0.99,
            is_destructive=True
        )
        homeostasis = create_homeostasis(energy=1.0)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        # Should get DENY, not REQUIRE_APPROVAL
        assert decision == GovernorDecision.DENY
        assert self.governor.get_last_rule_triggered() == "destructive_block"
    
    def test_energy_exhaustion_priority_over_normal(self):
        """Test that energy exhaustion is checked before normal allow."""
        action = create_action("normal_action", risk=0.1)
        homeostasis = create_homeostasis(energy=0.01)
        
        decision = self.governor.evaluate(action, {}, homeostasis)
        
        assert decision == GovernorDecision.REQUIRE_APPROVAL
        assert self.governor.get_last_rule_triggered() == "energy_exhaustion"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
