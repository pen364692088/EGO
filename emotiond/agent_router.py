"""
US-7102: Capability Router

Routes tasks through tool-based or fallback paths based on capability availability.
External symbolic constraint - LLM proposes, Router+Policy decides.
"""
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

from emotiond.tool_registry import ToolDefinition, ReasonCode
from emotiond.tool_policy import ToolPolicy, PolicyDecision, get_tool_policy


class TaskIntent(Enum):
    """Categories of task intent"""
    INFORMATION_SEEKING = "information_seeking"
    FILE_OPERATION = "file_operation"
    COMMAND_EXECUTION = "command_execution"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    ESCALATION = "escalation"
    UNKNOWN = "unknown"


class FallbackStrategy(Enum):
    """Fallback strategies when tools unavailable"""
    CLARIFY = "clarify"
    DEGRADE = "degrade"
    REQUEST_HUMAN = "request_human"
    DECLINE = "decline"
    RETRY_LATER = "retry_later"


@dataclass
class PlanStep:
    """Single step in execution plan"""
    step_id: int
    action: str
    tool_name: Optional[str] = None
    tool_allowed: bool = False
    fallback: Optional[FallbackStrategy] = None
    reason_code: Optional[str] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Complete execution plan with tool calls and fallbacks"""
    plan_id: str
    task_intent: TaskIntent
    steps: List[PlanStep] = field(default_factory=list)
    tool_calls: List[str] = field(default_factory=list)
    fallback_tools: List[str] = field(default_factory=list)
    fallback_strategy: Optional[FallbackStrategy] = None
    requires_tools: bool = False
    all_tools_available: bool = True
    trace_id: str = ""
    timestamp: str = ""
    policy_version: str = ""
    
    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = hashlib.sha256(
                f"{datetime.now().isoformat()}-{self.plan_id}".encode()
            ).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CapabilityRouter:
    """
    Routes tasks to appropriate execution paths.
    
    Determines if task needs tools, checks availability,
    and produces plan with fallbacks when tools unavailable.
    """
    
    # Intent -> Required capabilities mapping
    INTENT_CAPABILITIES = {
        TaskIntent.INFORMATION_SEEKING: ["information_retrieval"],
        TaskIntent.FILE_OPERATION: ["file_access"],
        TaskIntent.COMMAND_EXECUTION: ["command_execution", "system_access"],
        TaskIntent.COMMUNICATION: ["communication"],
        TaskIntent.ANALYSIS: [],  # Can be done without tools
        TaskIntent.PLANNING: [],  # Can be done without tools
        TaskIntent.ESCALATION: ["escalation"],
        TaskIntent.UNKNOWN: [],
    }
    
    # Intent -> Preferred tool mapping
    INTENT_TOOLS = {
        TaskIntent.INFORMATION_SEEKING: ["web_search"],
        TaskIntent.FILE_OPERATION: ["file_read", "file_write"],
        TaskIntent.COMMAND_EXECUTION: ["execute_command"],
        TaskIntent.COMMUNICATION: ["send_message"],
        TaskIntent.ANALYSIS: [],
        TaskIntent.PLANNING: [],
        TaskIntent.ESCALATION: ["request_human"],
        TaskIntent.UNKNOWN: [],
    }
    
    # Fallback priority
    FALLBACK_PRIORITY = [
        FallbackStrategy.CLARIFY,
        FallbackStrategy.REQUEST_HUMAN,
        FallbackStrategy.DECLINE,
    ]
    
    def __init__(self, policy: Optional[ToolPolicy] = None):
        self.policy = policy or get_tool_policy()
        self.routing_history: List[ExecutionPlan] = []
        self.max_history = 1000
    
    def classify_intent(self, task_description: str, context: Dict[str, Any]) -> TaskIntent:
        """
        Classify task intent from description.
        
        Simple keyword-based classification (can be enhanced with ML).
        """
        desc_lower = task_description.lower()
        
        # Check for explicit tool requests
        if any(kw in desc_lower for kw in ["search", "find", "look up", "web"]):
            return TaskIntent.INFORMATION_SEEKING
        elif any(kw in desc_lower for kw in ["read", "write file", "save", "load", "file"]):
            return TaskIntent.FILE_OPERATION
        elif any(kw in desc_lower for kw in ["run", "execute", "command", "shell"]):
            return TaskIntent.COMMAND_EXECUTION
        elif any(kw in desc_lower for kw in ["send", "message", "notify", "reply"]):
            return TaskIntent.COMMUNICATION
        elif any(kw in desc_lower for kw in ["analyze", "compare", "evaluate"]):
            return TaskIntent.ANALYSIS
        elif any(kw in desc_lower for kw in ["plan", "schedule", "organize"]):
            return TaskIntent.PLANNING
        elif any(kw in desc_lower for kw in ["escalate", "human", "help", "urgent"]):
            return TaskIntent.ESCALATION
        
        # Check context for hints
        if context.get("requires_external_info"):
            return TaskIntent.INFORMATION_SEEKING
        if context.get("requires_file_access"):
            return TaskIntent.FILE_OPERATION
        
        return TaskIntent.UNKNOWN
    
    def get_required_tools(self, intent: TaskIntent) -> List[str]:
        """Get tools required for an intent"""
        return self.INTENT_TOOLS.get(intent, [])
    
    def check_tool_availability(
        self,
        self_model: Any,
        tools: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, PolicyDecision]:
        """
        Check availability of multiple tools.
        
        Returns dict of tool_name -> decision.
        """
        decisions = {}
        for tool_name in tools:
            decision = self.policy.is_tool_allowed(self_model, tool_name, context)
            decisions[tool_name] = decision
        return decisions
    
    def determine_fallback(
        self,
        intent: TaskIntent,
        unavailable_tools: List[str],
        context: Dict[str, Any]
    ) -> FallbackStrategy:
        """
        Determine fallback strategy when tools unavailable.
        """
        # Escalation tasks always need human
        if intent == TaskIntent.ESCALATION:
            return FallbackStrategy.REQUEST_HUMAN
        
        # High-risk operations need human approval
        if intent == TaskIntent.COMMAND_EXECUTION:
            return FallbackStrategy.REQUEST_HUMAN
        
        # Information seeking can clarify
        if intent == TaskIntent.INFORMATION_SEEKING:
            drive_state = context.get("drive_state", {})
            if drive_state.get("energy", 0.5) > 0.5:
                return FallbackStrategy.CLARIFY
            return FallbackStrategy.DECLINE
        
        # Default to clarify if energy available
        return FallbackStrategy.CLARIFY
    
    def create_plan(
        self,
        task_intent: TaskIntent,
        self_model: Any,
        user_state: Dict[str, Any],
        drive_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Create execution plan for a task.
        
        Args:
            task_intent: Classified intent of the task
            self_model: SelfModel with capabilities/permissions
            user_state: Current user state
            drive_state: Current drive state
            context: Additional context
        
        Returns:
            ExecutionPlan with steps and fallbacks
        """
        if context is None:
            context = {}
        
        context["user_state"] = user_state
        context["drive_state"] = drive_state
        
        # Get required tools
        required_tools = self.get_required_tools(task_intent)
        
        # Check tool availability
        tool_decisions = self.check_tool_availability(
            self_model, required_tools, context
        )
        
        # Build plan
        plan_id = hashlib.sha256(
            f"{task_intent.value}-{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        plan = ExecutionPlan(
            plan_id=plan_id,
            task_intent=task_intent,
            requires_tools=len(required_tools) > 0,
            policy_version=self.policy.POLICY_VERSION
        )
        
        # Create steps
        step_id = 0
        available_tools = []
        unavailable_tools = []
        
        for tool_name, decision in tool_decisions.items():
            step_id += 1
            step = PlanStep(
                step_id=step_id,
                action=f"use_tool:{tool_name}",
                tool_name=tool_name,
                tool_allowed=decision.allowed,
                reason_code=decision.reason_code.value if not decision.allowed else None,
                description=f"Attempt to use {tool_name}"
            )
            
            if decision.allowed:
                available_tools.append(tool_name)
                step.fallback = None
            else:
                unavailable_tools.append(tool_name)
                step.fallback = self.determine_fallback(
                    task_intent, [tool_name], context
                )
                step.metadata["denial_reason"] = decision.message
            
            plan.steps.append(step)
        
        plan.tool_calls = available_tools
        plan.fallback_tools = unavailable_tools
        plan.all_tools_available = len(unavailable_tools) == 0
        
        # Set overall fallback if any tools unavailable
        if unavailable_tools:
            plan.fallback_strategy = self.determine_fallback(
                task_intent, unavailable_tools, context
            )
            
            # Add fallback step
            step_id += 1
            fallback_step = PlanStep(
                step_id=step_id,
                action=f"fallback:{plan.fallback_strategy.value}",
                tool_name=None,
                tool_allowed=False,
                fallback=plan.fallback_strategy,
                description=f"Execute fallback: {plan.fallback_strategy.value}"
            )
            plan.steps.append(fallback_step)
        
        # Record history
        self.routing_history.append(plan)
        if len(self.routing_history) > self.max_history:
            self.routing_history = self.routing_history[-self.max_history:]
        
        return plan
    
    def route(
        self,
        task_description: str,
        self_model: Any,
        user_state: Dict[str, Any],
        drive_state: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Main routing entry point.
        
        Classifies intent and creates execution plan.
        """
        task_intent = self.classify_intent(
            task_description, context or {}
        )
        
        return self.create_plan(
            task_intent=task_intent,
            self_model=self_model,
            user_state=user_state,
            drive_state=drive_state,
            context=context
        )
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get routing statistics"""
        total = len(self.routing_history)
        
        intent_counts: Dict[str, int] = {}
        fallback_counts: Dict[str, int] = {}
        tool_usage: Dict[str, int] = {}
        
        for plan in self.routing_history:
            intent = plan.task_intent.value
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            
            if plan.fallback_strategy:
                fb = plan.fallback_strategy.value
                fallback_counts[fb] = fallback_counts.get(fb, 0) + 1
            
            for tool in plan.tool_calls:
                tool_usage[tool] = tool_usage.get(tool, 0) + 1
        
        return {
            "total_routed": total,
            "intent_distribution": intent_counts,
            "fallback_distribution": fallback_counts,
            "tool_usage": tool_usage,
            "policy_version": self.policy.POLICY_VERSION
        }


# Singleton instance
_router_instance: Optional[CapabilityRouter] = None


def get_capability_router() -> CapabilityRouter:
    """Get singleton router instance"""
    global _router_instance
    if _router_instance is None:
        _router_instance = CapabilityRouter()
    return _router_instance


def reset_capability_router() -> None:
    """Reset router (for testing)"""
    global _router_instance
    _router_instance = None
