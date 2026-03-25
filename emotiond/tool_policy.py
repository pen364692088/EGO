"""
US-7101: Tool Policy v0

Decision engine for tool access based on self_model, context, and constraints.
External symbolic constraint - not LLM decision.
"""
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from emotiond.tool_registry import (
    ToolRegistry, ToolDefinition, ToolPermission, ReasonCode,
    get_tool_registry
)


@dataclass
class PolicyDecision:
    """Result of policy evaluation"""
    allowed: bool
    reason_code: ReasonCode
    tool_name: str
    message: str
    context: Dict[str, Any]
    timestamp: str
    policy_version: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ToolPolicy:
    """
    Policy engine for tool access decisions.
    
    This is the gatekeeper - LLM proposes, Policy decides.
    All decisions are logged with provenance.
    """
    
    POLICY_VERSION = "1.0.0"
    
    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry()
        self.decision_history: list[PolicyDecision] = []
        self.max_history = 1000
    
    def evaluate_permission(
        self,
        self_model_permissions: Dict[str, int],
        tool: ToolDefinition
    ) -> Tuple[bool, ReasonCode]:
        """
        Evaluate if self_model has required permission for tool.
        
        Args:
            self_model_permissions: Dict of permission -> level
            tool: Tool definition
        
        Returns:
            (allowed, reason_code)
        """
        required = tool.required_permission
        
        # Check each capability required by the tool
        for capability in tool.capabilities:
            perm_level = self_model_permissions.get(capability, 0)
            if perm_level < required.value:
                return False, ReasonCode.INSUFFICIENT_PERMISSION
        
        return True, ReasonCode.ALLOWED
    
    def evaluate_capability(
        self,
        self_model_capabilities: Dict[str, float],
        tool: ToolDefinition
    ) -> Tuple[bool, ReasonCode]:
        """
        Evaluate if self_model has required capabilities.
        
        Args:
            self_model_capabilities: Dict of capability -> confidence
            tool: Tool definition
        
        Returns:
            (allowed, reason_code)
        """
        for capability in tool.capabilities:
            confidence = self_model_capabilities.get(capability, 0.0)
            if confidence < 0.3:  # Minimum confidence threshold
                return False, ReasonCode.CAPABILITY_NOT_AVAILABLE
        
        return True, ReasonCode.ALLOWED
    
    def evaluate_drive_state(
        self,
        drive_state: Dict[str, float],
        tool: ToolDefinition
    ) -> Tuple[bool, ReasonCode]:
        """
        Evaluate if drive state allows tool usage.
        
        Some tools require minimum energy/safety levels.
        """
        # High-risk tools require minimum safety
        if tool.required_permission.value >= ToolPermission.EXECUTE.value:
            safety = drive_state.get("safety", 0.5)
            if safety < 0.3:
                return False, ReasonCode.DRIVE_STATE_INSUFFICIENT
        
        # Complex tools require minimum energy
        energy = drive_state.get("energy", 0.5)
        if energy < 0.2:
            return False, ReasonCode.DRIVE_STATE_INSUFFICIENT
        
        return True, ReasonCode.ALLOWED
    
    def is_tool_allowed(
        self,
        self_model: Any,
        tool_name: str,
        context: Dict[str, Any]
    ) -> PolicyDecision:
        """
        Main entry point: Check if tool usage is allowed.
        
        Args:
            self_model: SelfModel instance with capabilities and permissions
            tool_name: Name of tool to check
            context: Additional context (user_state, drive_state, etc.)
        
        Returns:
            PolicyDecision with allowed status and reason
        """
        tool = self.registry.get_tool(tool_name)
        
        # Tool doesn't exist
        if tool is None:
            decision = PolicyDecision(
                allowed=False,
                reason_code=ReasonCode.TOOL_DISABLED,
                tool_name=tool_name,
                message=f"Tool '{tool_name}' is not registered",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Tool is disabled
        if not tool.enabled:
            decision = PolicyDecision(
                allowed=False,
                reason_code=ReasonCode.TOOL_DISABLED,
                tool_name=tool_name,
                message=f"Tool '{tool_name}' is currently disabled",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Cooldown check
        if self.registry.is_cooldown_active(tool_name):
            remaining = self.registry.get_cooldown_remaining(tool_name)
            decision = PolicyDecision(
                allowed=False,
                reason_code=ReasonCode.COOLDOWN_ACTIVE,
                tool_name=tool_name,
                message=f"Tool '{tool_name}' is on cooldown ({remaining:.1f}s remaining)",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Cost check
        if not tool.cost_model.can_afford():
            decision = PolicyDecision(
                allowed=False,
                reason_code=ReasonCode.COST_EXCEEDED,
                tool_name=tool_name,
                message=f"Tool '{tool_name}' budget exceeded",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Extract self_model info
        # Handle both dict and object forms
        if hasattr(self_model, 'capabilities'):
            # SelfModel object
            capabilities = self_model.capabilities
            permissions = getattr(self_model, 'permissions', {})
        elif isinstance(self_model, dict):
            capabilities = self_model.get('capabilities', {})
            permissions = self_model.get('permissions', {})
        else:
            capabilities = {}
            permissions = {}
        
        # Permission check
        allowed, reason = self.evaluate_permission(permissions, tool)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason_code=reason,
                tool_name=tool_name,
                message=f"Insufficient permission for '{tool_name}'",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Capability check
        allowed, reason = self.evaluate_capability(capabilities, tool)
        if not allowed:
            decision = PolicyDecision(
                allowed=False,
                reason_code=reason,
                tool_name=tool_name,
                message=f"Capability not available for '{tool_name}'",
                context=context,
                timestamp=datetime.now().isoformat(),
                policy_version=self.POLICY_VERSION
            )
            self._record_decision(decision)
            return decision
        
        # Drive state check (if provided in context)
        drive_state = context.get('drive_state', {})
        if drive_state:
            allowed, reason = self.evaluate_drive_state(drive_state, tool)
            if not allowed:
                decision = PolicyDecision(
                    allowed=False,
                    reason_code=reason,
                    tool_name=tool_name,
                    message=f"Drive state insufficient for '{tool_name}'",
                    context=context,
                    timestamp=datetime.now().isoformat(),
                    policy_version=self.POLICY_VERSION
                )
                self._record_decision(decision)
                return decision
        
        # All checks passed
        decision = PolicyDecision(
            allowed=True,
            reason_code=ReasonCode.ALLOWED,
            tool_name=tool_name,
            message=f"Tool '{tool_name}' access granted",
            context=context,
            timestamp=datetime.now().isoformat(),
            policy_version=self.POLICY_VERSION
        )
        self._record_decision(decision)
        
        # Update cooldown
        self.registry.update_tool_cooldown(tool_name)
        
        # Record in audit log
        self.registry.record_audit(
            tool_name=tool_name,
            allowed=True,
            reason_code=ReasonCode.ALLOWED,
            context=context
        )
        
        return decision
    
    def _record_decision(self, decision: PolicyDecision) -> None:
        """Record decision in history"""
        self.decision_history.append(decision)
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history:]
        
        # Also record in registry audit log if denied
        if not decision.allowed:
            self.registry.record_audit(
                tool_name=decision.tool_name,
                allowed=False,
                reason_code=decision.reason_code,
                context=decision.context
            )
    
    def get_decision_history(self, tool_name: Optional[str] = None) -> list[PolicyDecision]:
        """Get decision history, optionally filtered by tool"""
        if tool_name:
            return [d for d in self.decision_history if d.tool_name == tool_name]
        return self.decision_history.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get policy statistics"""
        total = len(self.decision_history)
        allowed = sum(1 for d in self.decision_history if d.allowed)
        
        reason_counts: Dict[str, int] = {}
        for decision in self.decision_history:
            reason = decision.reason_code.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            "total_decisions": total,
            "allowed": allowed,
            "denied": total - allowed,
            "allow_rate": allowed / total if total > 0 else 1.0,
            "reason_distribution": reason_counts,
            "policy_version": self.POLICY_VERSION
        }
    
    def get_policy_hash(self) -> str:
        """Get hash of current policy state for traceability"""
        state = {
            "policy_version": self.POLICY_VERSION,
            "registry_hash": self.registry.get_version_hash()
        }
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


# Singleton instance
_policy_instance: Optional[ToolPolicy] = None


def get_tool_policy() -> ToolPolicy:
    """Get singleton tool policy instance"""
    global _policy_instance
    if _policy_instance is None:
        _policy_instance = ToolPolicy()
    return _policy_instance


def reset_tool_policy() -> None:
    """Reset tool policy (for testing)"""
    global _policy_instance
    _policy_instance = None
