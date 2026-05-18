"""
OpenEmotion Agent Runtime - Tool Base Classes

Defines base classes and interfaces for tool system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import uuid


class ToolStatus(str, Enum):
    """Tool execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DENIED = "denied"  # Security denial


@dataclass
class ToolResult:
    """
    Result of tool execution.
    
    Attributes:
        success: Whether execution succeeded
        output: Output from the tool
        error: Error message if failed
        status: Detailed status (success/failed/timeout/denied)
        metadata: Additional metadata about execution
        execution_time_ms: Execution time in milliseconds
    """
    success: bool
    output: str = ""
    error: Optional[str] = None
    status: ToolStatus = ToolStatus.SUCCESS
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'success': self.success,
            'output': self.output,
            'error': self.error,
            'status': self.status.value,
            'metadata': self.metadata,
            'execution_time_ms': self.execution_time_ms
        }
    
    @classmethod
    def success_result(cls, output: str, metadata: Optional[Dict] = None) -> 'ToolResult':
        """Create a success result."""
        return cls(
            success=True,
            output=output,
            status=ToolStatus.SUCCESS,
            metadata=metadata or {}
        )
    
    @classmethod
    def failure_result(cls, error: str, status: ToolStatus = ToolStatus.FAILED) -> 'ToolResult':
        """Create a failure result."""
        return cls(
            success=False,
            error=error,
            status=status
        )
    
    @classmethod
    def timeout_result(cls, error: str = "Execution timed out") -> 'ToolResult':
        """Create a timeout result."""
        return cls(
            success=False,
            error=error,
            status=ToolStatus.TIMEOUT
        )
    
    @classmethod
    def denied_result(cls, reason: str) -> 'ToolResult':
        """Create a denied result (security block)."""
        return cls(
            success=False,
            error=f"Security denial: {reason}",
            status=ToolStatus.DENIED
        )


@dataclass
class ToolExecution:
    """
    Record of a tool execution for event logging.
    
    Attributes:
        id: Unique execution identifier
        tool_name: Name of the tool executed
        params: Parameters passed to the tool
        result: Execution result
        timestamp: When the execution occurred
        task_id: Optional task ID if part of a task
        step_id: Optional step ID if part of a step
    """
    id: str
    tool_name: str
    params: Dict[str, Any]
    result: ToolResult
    timestamp: datetime = field(default_factory=datetime.now)
    task_id: Optional[str] = None
    step_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'tool_name': self.tool_name,
            'params': self.params,
            'result': self.result.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'task_id': self.task_id,
            'step_id': self.step_id
        }
    
    @classmethod
    def create(cls, tool_name: str, params: Dict[str, Any], 
               result: ToolResult, task_id: Optional[str] = None,
               step_id: Optional[str] = None) -> 'ToolExecution':
        """Factory method to create an execution record."""
        return cls(
            id=f"tool_exec_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            params=params,
            result=result,
            task_id=task_id,
            step_id=step_id
        )


class Tool(ABC):
    """
    Abstract base class for all tools.
    
    Tools are the execution primitives that the agent uses to
    interact with the environment (files, shell, code, etc.).
    
    Each tool must:
    1. Define its name and description
    2. Implement the execute() method
    3. Handle errors gracefully (never crash)
    4. Respect security boundaries
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the tool name (e.g., 'file_read', 'shell_exec')."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a human-readable description of the tool."""
        pass
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """
        Return JSON schema for tool parameters.
        
        Override this to define expected parameters.
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given parameters.
        
        Args:
            params: Tool parameters
        
        Returns:
            ToolResult with success/failure and output
        
        Note: This method should NEVER raise exceptions.
              All errors should be returned in ToolResult.
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Validate parameters before execution.
        
        Args:
            params: Parameters to validate
        
        Returns:
            Error message if validation fails, None if valid
        """
        # Default: no validation
        return None


class ToolError(Exception):
    """Base exception for tool errors."""
    pass


class ToolSecurityError(ToolError):
    """Raised when a tool execution violates security policy."""
    pass


class ToolTimeoutError(ToolError):
    """Raised when a tool execution times out."""
    pass


class ToolValidationError(ToolError):
    """Raised when tool parameters fail validation."""
    pass
