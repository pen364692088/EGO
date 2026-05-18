"""
Plan Injection - Injection Gate

Determines if plan injection should be allowed for a given message context.
Gate logic: only inject for chat paths, skip commands/control/tool paths.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from enum import Enum


logger = logging.getLogger(__name__)


class GateResult(Enum):
    """Result of gate evaluation."""
    ALLOWED = "allowed"
    SKIPPED = "skipped"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class GateDecision:
    """Gate decision with reason."""
    result: GateResult
    reason: Optional[str] = None


# Command keywords that indicate task control
TASK_CONTROL_COMMANDS = {
    "/approve", "/deny", "/cancel", "/pause", "/resume",
    "/status", "/reset", "/new", "/wrap", "/tasks", "/task",
    "/retry", "/abort", "/report", "/run", "/memory", "/help", "/start"
}


class InjectionGate:
    """
    Determines if plan injection should proceed.
    
    Gate rules:
    - Normal chat: ALLOW
    - Slash commands: SKIP
    - Task control: SKIP
    - Tool execution path: SKIP
    - Feature disabled: DISABLED
    """
    
    def __init__(
        self,
        inject_plan_into_reply: bool = True,
        plan_injection_for_chat_only: bool = True,
        skip_plan_for_commands: bool = True,
        skip_plan_for_task_control: bool = True,
        skip_plan_for_tool_paths: bool = True,
    ):
        self.inject_plan_into_reply = inject_plan_into_reply
        self.plan_injection_for_chat_only = plan_injection_for_chat_only
        self.skip_plan_for_commands = skip_plan_for_commands
        self.skip_plan_for_task_control = skip_plan_for_task_control
        self.skip_plan_for_tool_paths = skip_plan_for_tool_paths
    
    def _is_command(self, message_text: str) -> bool:
        """Check if message is a slash command."""
        if not message_text:
            return False
        text = message_text.strip()
        return text.startswith('/') and not text.startswith('//')
    
    def _is_task_control(self, message_text: str) -> bool:
        """Check if message is a task control command."""
        if not message_text:
            return False
        text = message_text.strip().lower()
        return any(text.startswith(cmd) for cmd in TASK_CONTROL_COMMANDS)
    
    def _is_tool_path(self, context: dict) -> bool:
        """Check if context indicates tool execution path."""
        return bool(context.get('tool_result') or context.get('tool_call_pending'))
    
    def evaluate(self, message_text: str, context: Optional[dict] = None) -> GateDecision:
        """
        Evaluate if plan injection should proceed.
        
        Args:
            message_text: The user's message text
            context: Optional context with tool execution state
        
        Returns:
            GateDecision with result and reason
        """
        # Feature disabled
        if not self.inject_plan_into_reply:
            logger.debug("Plan injection disabled by config")
            return GateDecision(result=GateResult.DISABLED, reason="feature_disabled")
        
        # Chat-only mode checks
        if self.plan_injection_for_chat_only:
            # Skip commands
            if self.skip_plan_for_commands and self._is_command(message_text):
                logger.debug(f"Skipping plan injection: is_command")
                return GateDecision(result=GateResult.SKIPPED, reason="is_command")
            
            # Skip task control
            if self.skip_plan_for_task_control and self._is_task_control(message_text):
                logger.debug(f"Skipping plan injection: is_task_control")
                return GateDecision(result=GateResult.SKIPPED, reason="is_task_control")
            
            # Skip tool paths
            if self.skip_plan_for_tool_paths and context:
                if self._is_tool_path(context):
                    logger.debug("Skipping plan injection: is_tool_path")
                    return GateDecision(result=GateResult.SKIPPED, reason="is_tool_path")
        
        # All checks passed - allow injection
        logger.debug("Plan injection allowed")
        return GateDecision(result=GateResult.ALLOWED, reason="chat_path")
    
    def should_inject(self, message_text: str, context: Optional[dict] = None) -> bool:
        """
        Simple boolean check if injection should proceed.
        
        Args:
            message_text: The user's message text
            context: Optional context with tool execution state
        
        Returns:
            True if injection should proceed
        """
        decision = self.evaluate(message_text, context)
        return decision.result == GateResult.ALLOWED


# Global gate instance
_gate: Optional[InjectionGate] = None


def get_injection_gate() -> InjectionGate:
    """Get the global injection gate instance."""
    global _gate
    if _gate is None:
        # Default configuration
        _gate = InjectionGate()
    return _gate


def configure_injection_gate(
    inject_plan_into_reply: bool = True,
    plan_injection_for_chat_only: bool = True,
    skip_plan_for_commands: bool = True,
    skip_plan_for_task_control: bool = True,
    skip_plan_for_tool_paths: bool = True,
) -> InjectionGate:
    """
    Configure the global injection gate.
    
    Args:
        inject_plan_into_reply: Master switch for plan injection
        plan_injection_for_chat_only: Only inject for chat paths
        skip_plan_for_commands: Skip slash commands
        skip_plan_for_task_control: Skip task control commands
        skip_plan_for_tool_paths: Skip tool execution paths
    
    Returns:
        Configured InjectionGate instance
    """
    global _gate
    _gate = InjectionGate(
        inject_plan_into_reply=inject_plan_into_reply,
        plan_injection_for_chat_only=plan_injection_for_chat_only,
        skip_plan_for_commands=skip_plan_for_commands,
        skip_plan_for_task_control=skip_plan_for_task_control,
        skip_plan_for_tool_paths=skip_plan_for_tool_paths,
    )
    return _gate
