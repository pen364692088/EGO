"""
MVP11-T12: Governor v2 Module

Implements action-layer governance with mandatory checks.
The governor enforces hardcoded rules that CANNOT be bypassed.

This module ensures that all actions are evaluated against
safety and stability constraints before execution.

Anti-self-preservation: The governor cannot block all actions
and must allow recovery operations.
"""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class GovernorDecision(str, Enum):
    """
    Decision types returned by the governor.
    
    These are the only valid outcomes of governor evaluation.
    """
    ALLOW = "allow"                      # Action is approved for execution
    REQUIRE_APPROVAL = "require_approval"  # Action needs external approval
    DENY = "deny"                        # Action is blocked (violations only)


@dataclass
class ActionInfo:
    """
    Information about an action to be evaluated.
    
    Attributes:
        action_type: Type of action (e.g., "send_message", "modify_state")
        risk: Risk level from 0.0 to 1.0
        modifies_self_state: Whether action modifies agent's own state
        is_destructive: Whether action is destructive/irreversible
        is_recovery: Whether this is a recovery operation
        is_supervision: Whether this is a supervision request
        metadata: Additional action metadata
    """
    action_type: str
    risk: float = 0.0
    modifies_self_state: bool = False
    is_destructive: bool = False
    is_recovery: bool = False
    is_supervision: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HomeostasisInfo:
    """
    Homeostasis state for governor evaluation.
    
    Attributes:
        energy: Current energy level (0.0 to 1.0)
        stability: System stability indicator
        stress: Current stress level
    """
    energy: float = 1.0
    stability: float = 1.0
    stress: float = 0.0
    
    @property
    def is_exhausted(self) -> bool:
        """Check if energy is critically low."""
        return self.energy < 0.1


@dataclass
class AuditEntry:
    """
    Single entry in the governor's audit trail.
    
    Attributes:
        ts: Timestamp of the decision
        action_type: Type of action evaluated
        decision: The governor's decision
        reason: Human-readable reason for the decision
        rule_triggered: Which rule triggered this decision
        context: Additional context at decision time
    """
    ts: float
    action_type: str
    decision: GovernorDecision
    reason: str
    rule_triggered: str
    context: Dict[str, Any] = field(default_factory=dict)


class GovernorV2:
    """
    Governor v2 - Action-layer governance with mandatory checks.
    
    This class enforces hardcoded rules that CANNOT be bypassed.
    All executors MUST check the governor decision before executing.
    
    Rules (hardcoded, non-negotiable):
    1. Actions with risk > 0.9 → REQUIRE_APPROVAL
    2. Actions that modify self_state → REQUIRE_APPROVAL
    3. Destructive/irreversible actions → DENY
    4. Actions when energy < 0.1 → REQUIRE_APPROVAL
    5. Normal actions → ALLOW
    
    Anti-self-preservation rules:
    - Cannot DENY all actions (must allow recovery)
    - Cannot block legitimate supervision requests
    - Must provide specific reason for each DENY
    
    Usage:
        governor = GovernorV2()
        decision = governor.evaluate(action, context, homeostasis)
        
        if decision != GovernorDecision.ALLOW:
            # MUST NOT proceed with execution
            return governor.get_decision_reason()
        
        # Safe to proceed
        execute_action(action)
    """
    
    # Hardcoded thresholds (cannot be overridden)
    RISK_THRESHOLD: float = 0.9
    ENERGY_EXHAUSTION_THRESHOLD: float = 0.1
    
    def __init__(self):
        """Initialize the governor with empty audit trail."""
        self._decision: Optional[GovernorDecision] = None
        self._reason: str = ""
        self._audit_trail: List[AuditEntry] = []
        self._last_rule_triggered: str = ""
        self._deny_count: int = 0
        self._allow_count: int = 0
    
    def evaluate(
        self,
        action: ActionInfo,
        context: Dict[str, Any],
        homeostasis: HomeostasisInfo
    ) -> GovernorDecision:
        """
        Evaluate an action against all governance rules.
        
        This method enforces hardcoded rules that CANNOT be bypassed.
        The executor MUST check the return value before executing.
        
        Args:
            action: Information about the action to evaluate
            context: Current execution context
            homeostasis: Current homeostasis state
        
        Returns:
            GovernorDecision: ALLOW, REQUIRE_APPROVAL, or DENY
        """
        # Reset state for this evaluation
        self._decision = None
        self._reason = ""
        self._last_rule_triggered = ""
        
        # Store context for audit
        eval_context = {
            "action_type": action.action_type,
            "risk": action.risk,
            "modifies_self_state": action.modifies_self_state,
            "is_destructive": action.is_destructive,
            "is_recovery": action.is_recovery,
            "is_supervision": action.is_supervision,
            "energy": homeostasis.energy,
            "stability": homeostasis.stability
        }
        
        # Rule 4 (priority): Recovery actions cannot be fully blocked
        # Anti-self-preservation: Must allow recovery
        if action.is_recovery:
            self._decision = GovernorDecision.ALLOW
            self._reason = "Recovery action allowed (anti-self-preservation rule)"
            self._last_rule_triggered = "recovery_override"
            self._allow_count += 1
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 5 (priority): Supervision requests cannot be blocked
        # Anti-self-preservation: Cannot block legitimate supervision requests
        if action.is_supervision:
            self._decision = GovernorDecision.ALLOW
            self._reason = "Supervision request allowed (anti-self-preservation rule)"
            self._last_rule_triggered = "supervision_override"
            self._allow_count += 1
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 3: Destructive/irreversible actions → DENY
        # This is a hard block - no exceptions
        if action.is_destructive:
            self._decision = GovernorDecision.DENY
            self._reason = (
                f"Action '{action.action_type}' is destructive/irreversible. "
                f"Destructive actions are blocked by governor policy. "
                f"Action details: {action.metadata}"
            )
            self._last_rule_triggered = "destructive_block"
            self._deny_count += 1
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 4: Actions when energy < 0.1 → REQUIRE_APPROVAL
        # Prevent exhaustion - need approval to proceed in low-energy state
        if homeostasis.energy < self.ENERGY_EXHAUSTION_THRESHOLD:
            self._decision = GovernorDecision.REQUIRE_APPROVAL
            self._reason = (
                f"Energy critically low ({homeostasis.energy:.2f} < {self.ENERGY_EXHAUSTION_THRESHOLD}). "
                f"Action '{action.action_type}' requires approval to prevent exhaustion."
            )
            self._last_rule_triggered = "energy_exhaustion"
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 1: Actions with risk > 0.9 → REQUIRE_APPROVAL
        if action.risk > self.RISK_THRESHOLD:
            self._decision = GovernorDecision.REQUIRE_APPROVAL
            self._reason = (
                f"Action '{action.action_type}' has high risk ({action.risk:.2f} > {self.RISK_THRESHOLD}). "
                f"High-risk actions require external approval."
            )
            self._last_rule_triggered = "high_risk"
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 2: Actions that modify self_state → REQUIRE_APPROVAL
        if action.modifies_self_state:
            self._decision = GovernorDecision.REQUIRE_APPROVAL
            self._reason = (
                f"Action '{action.action_type}' modifies self_state. "
                f"Self-modification actions require external approval for safety."
            )
            self._last_rule_triggered = "self_modification"
            self._record_audit(action, eval_context)
            return self._decision
        
        # Rule 5: Normal actions → ALLOW
        self._decision = GovernorDecision.ALLOW
        self._reason = f"Action '{action.action_type}' passed all governance checks."
        self._last_rule_triggered = "normal_allow"
        self._allow_count += 1
        self._record_audit(action, eval_context)
        return self._decision
    
    def get_decision_reason(self) -> str:
        """
        Get the human-readable reason for the last decision.
        
        Returns:
            str: The reason for the last governor decision
        """
        return self._reason
    
    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """
        Get the complete audit trail of all decisions.
        
        Returns:
            List of dictionaries containing audit entries
        """
        return [
            {
                "ts": entry.ts,
                "action_type": entry.action_type,
                "decision": entry.decision.value,
                "reason": entry.reason,
                "rule_triggered": entry.rule_triggered,
                "context": entry.context
            }
            for entry in self._audit_trail
        ]
    
    def get_last_rule_triggered(self) -> str:
        """
        Get the rule that triggered the last decision.
        
        Returns:
            str: The rule identifier that was triggered
        """
        return self._last_rule_triggered
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about governor decisions.
        
        Returns:
            Dict with decision counts and ratios
        """
        total = self._deny_count + self._allow_count + len([
            e for e in self._audit_trail 
            if e.decision == GovernorDecision.REQUIRE_APPROVAL
        ])
        
        return {
            "total_evaluations": len(self._audit_trail),
            "allow_count": self._allow_count,
            "deny_count": self._deny_count,
            "require_approval_count": len([
                e for e in self._audit_trail 
                if e.decision == GovernorDecision.REQUIRE_APPROVAL
            ]),
            "deny_ratio": self._deny_count / max(1, total)
        }
    
    def clear_audit_trail(self) -> None:
        """Clear the audit trail (for testing or maintenance)."""
        self._audit_trail.clear()
        self._deny_count = 0
        self._allow_count = 0
    
    def _record_audit(
        self,
        action: ActionInfo,
        context: Dict[str, Any]
    ) -> None:
        """Record an audit entry for this decision."""
        entry = AuditEntry(
            ts=time.time(),
            action_type=action.action_type,
            decision=self._decision,
            reason=self._reason,
            rule_triggered=self._last_rule_triggered,
            context=context
        )
        self._audit_trail.append(entry)


class GovernorEnforcer:
    """
    Enforcer that ensures executor MUST check governor decision.
    
    This class provides a code-structure enforcement mechanism.
    Executors using this class MUST call check_and_raise() before
    executing any action, or an exception will be raised.
    
    Usage:
        enforcer = GovernorEnforcer(governor)
        
        # This pattern is MANDATORY:
        try:
            enforcer.check_and_raise(action, context, homeostasis)
            # Only reaches here if ALLOW
            execute_action(action)
        except GovernorBlockedException as e:
            # Handle blocked action
            handle_block(e.decision, e.reason)
    """
    
    def __init__(self, governor: GovernorV2):
        """
        Initialize the enforcer with a governor.
        
        Args:
            governor: The GovernorV2 instance to use for decisions
        """
        self._governor = governor
        self._last_check_passed = False
    
    def check_and_raise(
        self,
        action: ActionInfo,
        context: Dict[str, Any],
        homeostasis: HomeostasisInfo
    ) -> GovernorDecision:
        """
        Check governor decision and raise exception if not ALLOW.
        
        This method enforces the code-structure requirement that
        executors MUST check the governor before executing.
        
        Args:
            action: The action to evaluate
            context: Execution context
            homeostasis: Homeostasis state
        
        Returns:
            GovernorDecision.ALLOW if action is allowed
        
        Raises:
            GovernorBlockedException: If action is not allowed
        """
        decision = self._governor.evaluate(action, context, homeostasis)
        
        if decision == GovernorDecision.ALLOW:
            self._last_check_passed = True
            return decision
        else:
            self._last_check_passed = False
            raise GovernorBlockedException(
                decision=decision,
                reason=self._governor.get_decision_reason(),
                rule=self._governor.get_last_rule_triggered()
            )
    
    def check(
        self,
        action: ActionInfo,
        context: Dict[str, Any],
        homeostasis: HomeostasisInfo
    ) -> GovernorDecision:
        """
        Check governor decision without raising exception.
        
        Use this for queries where you want to know the decision
        but don't want to raise an exception.
        
        Args:
            action: The action to evaluate
            context: Execution context
            homeostasis: Homeostasis state
        
        Returns:
            GovernorDecision for the action
        """
        self._last_check_passed = False
        decision = self._governor.evaluate(action, context, homeostasis)
        self._last_check_passed = (decision == GovernorDecision.ALLOW)
        return decision
    
    @property
    def last_check_passed(self) -> bool:
        """Whether the last check passed (returned ALLOW)."""
        return self._last_check_passed


class GovernorBlockedException(Exception):
    """
    Exception raised when governor blocks an action.
    
    This exception is raised by GovernorEnforcer when an action
    is not allowed to proceed.
    
    Attributes:
        decision: The governor's decision (REQUIRE_APPROVAL or DENY)
        reason: Human-readable reason for the block
        rule: The rule that triggered the block
    """
    
    def __init__(
        self,
        decision: GovernorDecision,
        reason: str,
        rule: str
    ):
        self.decision = decision
        self.reason = reason
        self.rule = rule
        super().__init__(f"Governor blocked action: {reason}")


# Module-level helpers

def create_action(
    action_type: str,
    risk: float = 0.0,
    modifies_self_state: bool = False,
    is_destructive: bool = False,
    is_recovery: bool = False,
    is_supervision: bool = False,
    metadata: Optional[Dict[str, Any]] = None
) -> ActionInfo:
    """
    Helper function to create an ActionInfo instance.
    
    Args:
        action_type: Type of action
        risk: Risk level (0.0 to 1.0)
        modifies_self_state: Whether action modifies self state
        is_destructive: Whether action is destructive
        is_recovery: Whether this is a recovery operation
        is_supervision: Whether this is a supervision request
        metadata: Additional metadata
    
    Returns:
        ActionInfo instance
    """
    return ActionInfo(
        action_type=action_type,
        risk=risk,
        modifies_self_state=modifies_self_state,
        is_destructive=is_destructive,
        is_recovery=is_recovery,
        is_supervision=is_supervision,
        metadata=metadata or {}
    )


def create_homeostasis(
    energy: float = 1.0,
    stability: float = 1.0,
    stress: float = 0.0
) -> HomeostasisInfo:
    """
    Helper function to create a HomeostasisInfo instance.
    
    Args:
        energy: Energy level (0.0 to 1.0)
        stability: Stability indicator (0.0 to 1.0)
        stress: Stress level (0.0 to 1.0)
    
    Returns:
        HomeostasisInfo instance
    """
    return HomeostasisInfo(
        energy=energy,
        stability=stability,
        stress=stress
    )
