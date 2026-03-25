"""
US-7101: Tool Registry v0

Tool whitelist with permissions, capabilities, and audit.
External symbolic constraint - LLM proposes, ToolPolicy decides.
"""
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import copy
from datetime import datetime
from enum import Enum
import hashlib
import json


class ToolPermission(Enum):
    """Permission levels for tool access"""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3
    ADMIN = 4


class ReasonCode(Enum):
    """Structured reason codes for tool refusal (aggregatable)"""
    ALLOWED = "allowed"
    INSUFFICIENT_PERMISSION = "insufficient_permission"
    CAPABILITY_NOT_AVAILABLE = "capability_not_available"
    COOLDOWN_ACTIVE = "cooldown_active"
    COST_EXCEEDED = "cost_exceeded"
    TOOL_DISABLED = "tool_disabled"
    CONTEXT_MISMATCH = "context_mismatch"
    SELF_MODEL_CONFLICT = "self_model_conflict"
    DRIVE_STATE_INSUFFICIENT = "drive_state_insufficient"


@dataclass
class IOSchema:
    """Input/Output schema for tool"""
    inputs: Dict[str, str]  # name -> type
    outputs: Dict[str, str]  # name -> type
    required_inputs: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        if not self.required_inputs:
            self.required_inputs = set(self.inputs.keys())


@dataclass
class CostModel:
    """Cost model for tool usage"""
    base_cost: float = 0.0
    per_call_cost: float = 0.0
    budget_limit: float = 100.0
    current_spend: float = 0.0
    
    def can_afford(self) -> bool:
        return self.current_spend + self.per_call_cost <= self.budget_limit
    
    def record_usage(self) -> float:
        self.current_spend += self.per_call_cost
        return self.current_spend


@dataclass
class ToolDefinition:
    """Complete tool definition with capabilities and constraints"""
    name: str
    capabilities: List[str]  # Required capabilities from self_model
    required_permission: ToolPermission
    cost_model: CostModel
    io_schema: IOSchema
    cooldown_seconds: float = 0.0
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.required_permission, int):
            self.required_permission = ToolPermission(self.required_permission)


class ToolRegistry:
    """
    Registry of available tools with permission checking.
    
    This is the single source of truth for what tools exist
    and what permissions/capabilities they require.
    """
    
    # Default tool definitions
    DEFAULT_TOOLS = {
        "web_search": ToolDefinition(
            name="web_search",
            capabilities=["information_retrieval"],
            required_permission=ToolPermission.READ,
            cost_model=CostModel(base_cost=0.0, per_call_cost=0.1, budget_limit=10.0),
            io_schema=IOSchema(
                inputs={"query": "string", "limit": "int"},
                outputs={"results": "list", "summary": "string"},
                required_inputs={"query"}
            ),
            cooldown_seconds=5.0,
            description="Search the web for information"
        ),
        "file_read": ToolDefinition(
            name="file_read",
            capabilities=["file_access"],
            required_permission=ToolPermission.READ,
            cost_model=CostModel(per_call_cost=0.05),
            io_schema=IOSchema(
                inputs={"path": "string"},
                outputs={"content": "string", "metadata": "dict"},
                required_inputs={"path"}
            ),
            cooldown_seconds=0.0,
            description="Read file contents"
        ),
        "file_write": ToolDefinition(
            name="file_write",
            capabilities=["file_access", "write_permission"],
            required_permission=ToolPermission.WRITE,
            cost_model=CostModel(per_call_cost=0.1),
            io_schema=IOSchema(
                inputs={"path": "string", "content": "string"},
                outputs={"success": "bool", "bytes_written": "int"},
                required_inputs={"path", "content"}
            ),
            cooldown_seconds=1.0,
            description="Write content to file"
        ),
        "execute_command": ToolDefinition(
            name="execute_command",
            capabilities=["command_execution", "system_access"],
            required_permission=ToolPermission.EXECUTE,
            cost_model=CostModel(per_call_cost=0.2, budget_limit=5.0),
            io_schema=IOSchema(
                inputs={"command": "string", "timeout": "int"},
                outputs={"stdout": "string", "stderr": "string", "exit_code": "int"},
                required_inputs={"command"}
            ),
            cooldown_seconds=10.0,
            description="Execute shell command"
        ),
        "send_message": ToolDefinition(
            name="send_message",
            capabilities=["communication"],
            required_permission=ToolPermission.WRITE,
            cost_model=CostModel(per_call_cost=0.01),
            io_schema=IOSchema(
                inputs={"recipient": "string", "message": "string"},
                outputs={"success": "bool", "message_id": "string"},
                required_inputs={"recipient", "message"}
            ),
            cooldown_seconds=1.0,
            description="Send message to user or channel"
        ),
        "request_human": ToolDefinition(
            name="request_human",
            capabilities=["escalation"],
            required_permission=ToolPermission.READ,
            cost_model=CostModel(per_call_cost=0.0),
            io_schema=IOSchema(
                inputs={"reason": "string", "context": "dict"},
                outputs={"approved": "bool", "response": "string"},
                required_inputs={"reason"}
            ),
            cooldown_seconds=30.0,
            description="Request human intervention"
        ),
    }
    
    def __init__(self, custom_tools: Optional[Dict[str, ToolDefinition]] = None):
        self.tools: Dict[str, ToolDefinition] = {}
        self.last_usage: Dict[str, datetime] = {}
        self.audit_log: List[Dict] = []
        self.max_audit_log = 1000
        
        # Load default tools
        self.tools.update({k: copy.deepcopy(v) for k, v in self.DEFAULT_TOOLS.items()})
        
        # Add custom tools
        if custom_tools:
            self.tools.update(custom_tools)
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool definition by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self.tools.keys())
    
    def list_tools_by_capability(self, capability: str) -> List[str]:
        """List tools that require a specific capability"""
        return [
            name for name, tool in self.tools.items()
            if capability in tool.capabilities
        ]
    
    def list_tools_by_permission(self, permission: ToolPermission) -> List[str]:
        """List tools that require a specific permission level"""
        return [
            name for name, tool in self.tools.items()
            if tool.required_permission.value <= permission.value
        ]
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a new tool"""
        self.tools[tool.name] = tool
    
    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self.tools:
            del self.tools[name]
            return True
        return False
    
    def update_tool_cooldown(self, name: str) -> None:
        """Update last usage time for cooldown tracking"""
        self.last_usage[name] = datetime.now()
    
    def is_cooldown_active(self, name: str) -> bool:
        """Check if tool is on cooldown"""
        if name not in self.last_usage:
            return False
        
        tool = self.get_tool(name)
        if not tool:
            return False
        
        elapsed = (datetime.now() - self.last_usage[name]).total_seconds()
        return elapsed < tool.cooldown_seconds
    
    def get_cooldown_remaining(self, name: str) -> float:
        """Get remaining cooldown seconds"""
        if name not in self.last_usage:
            return 0.0
        
        tool = self.get_tool(name)
        if not tool:
            return 0.0
        
        elapsed = (datetime.now() - self.last_usage[name]).total_seconds()
        remaining = tool.cooldown_seconds - elapsed
        return max(0.0, remaining)
    
    def record_audit(
        self,
        tool_name: str,
        allowed: bool,
        reason_code: ReasonCode,
        context: Dict[str, Any]
    ) -> None:
        """Record tool access decision in audit log"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "allowed": allowed,
            "reason_code": reason_code.value,
            "context_keys": list(context.keys()),
            "trace_id": context.get("trace_id", "")
        }
        
        self.audit_log.append(entry)
        
        # Trim old entries
        if len(self.audit_log) > self.max_audit_log:
            self.audit_log = self.audit_log[-self.max_audit_log:]
    
    def get_audit_log(self, tool_name: Optional[str] = None) -> List[Dict]:
        """Get audit log, optionally filtered by tool"""
        if tool_name:
            return [e for e in self.audit_log if e["tool_name"] == tool_name]
        return self.audit_log.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics"""
        allowed_count = sum(1 for e in self.audit_log if e["allowed"])
        denied_count = len(self.audit_log) - allowed_count
        
        reason_counts: Dict[str, int] = {}
        for entry in self.audit_log:
            reason = entry["reason_code"]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            "total_requests": len(self.audit_log),
            "allowed": allowed_count,
            "denied": denied_count,
            "allow_rate": allowed_count / len(self.audit_log) if self.audit_log else 1.0,
            "reason_distribution": reason_counts,
            "registered_tools": len(self.tools),
            "tools_on_cooldown": sum(1 for t in self.tools if self.is_cooldown_active(t))
        }
    
    def get_version_hash(self) -> str:
        """Get hash of current tool registry state for traceability"""
        state = {
            "tools": sorted(self.tools.keys()),
            "version": "1.0.0"
        }
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


# Singleton instance
_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get singleton tool registry instance"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance


def reset_tool_registry() -> None:
    """Reset tool registry (for testing)"""
    global _registry_instance
    _registry_instance = None
