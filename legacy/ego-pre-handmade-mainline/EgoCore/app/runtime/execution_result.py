"""
OpenEmotion Agent Runtime - Unified Execution Result Model

Provides a unified result model for all execution operations:
- Task step execution
- Tool invocation
- Resume/retry operations

This ensures consistent failure attribution and user messaging.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from enum import Enum
from datetime import datetime


class ExecutionStatus(str, Enum):
    """Unified execution status."""
    SUCCESS = "success"           # Completed successfully
    BLOCKED = "blocked"           # Blocked by precondition/safety
    FAILED = "failed"             # Terminally failed
    PARTIAL = "partial"           # Partially completed
    UNSAFE = "unsafe"             # Safety boundary violation
    RETRYABLE = "retryable"       # Transient failure, can retry


class FailureClass(str, Enum):
    """Classification of execution failures."""
    TOOL_ERROR = "tool_error"              # Tool execution failed
    MODEL_ERROR = "model_error"            # LLM/model failed
    ENVIRONMENT_ERROR = "environment_error" # External environment issue
    VALIDATION_ERROR = "validation_error"  # Input validation failed
    SAFETY_BLOCK = "safety_block"          # Blocked by safety rules
    TIMEOUT = "timeout"                    # Operation timed out
    PERMISSION_ERROR = "permission_error"  # Insufficient permissions
    NOT_FOUND = "not_found"                # Resource not found
    UNSUPPORTED = "unsupported"            # Operation not supported
    TASK_LOGIC_ERROR = "task_logic_error"  # Task planning/step design issue
    # P2-A.2: Intent/Postcondition failures
    INTENT_MISMATCH = "intent_mismatch"    # Executed wrong operation vs user intent
    POSTCONDITION_FAILED = "postcondition_failed"  # Tool success but goal not achieved
    PATH_EXTRACTION_ERROR = "path_extraction_error"  # Failed to extract target path
    UNKNOWN = "unknown"                    # Unclassified failure


@dataclass
class RetryHint:
    """Hints for retry behavior."""
    retryable: bool
    max_retries: int = 3
    current_retry: int = 0
    retry_after_ms: int = 1000
    backoff_multiplier: float = 2.0
    reason: Optional[str] = None


@dataclass
class ExecutionEvidence:
    """Evidence captured during execution."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    operation: Optional[str] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    duration_ms: Optional[int] = None
    checkpoint_id: Optional[str] = None
    step_id: Optional[str] = None
    tool_name: Optional[str] = None
    raw_error: Optional[str] = None
    stack_trace: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedExecutionResult:
    """
    Unified result model for all execution operations.
    
    This is the single source of truth for:
    - Task step execution
    - Tool invocation
    - Resume/retry operations
    
    Every execution must produce this result type.
    """
    
    # Core status
    status: ExecutionStatus
    summary: str
    
    # Failure details (if applicable)
    failure_class: Optional[FailureClass] = None
    
    # Evidence
    evidence: ExecutionEvidence = field(default_factory=ExecutionEvidence)
    
    # User-facing messaging
    user_safe_message: str = ""
    next_recommended_action: Optional[str] = None
    
    # Retry information
    retry_hint: Optional[RetryHint] = None
    
    # Output
    output: Optional[str] = None
    
    # Legacy compatibility
    success: bool = True
    error: Optional[str] = None
    
    def __post_init__(self):
        """Derive legacy fields from status."""
        self.success = self.status == ExecutionStatus.SUCCESS
        if self.failure_class and not self.error:
            self.error = f"[{self.failure_class.value}] {self.summary}"
    
    @property
    def is_terminal(self) -> bool:
        """Whether this failure is terminal (no retry)."""
        if self.status == ExecutionStatus.SUCCESS:
            return True
        if self.status == ExecutionStatus.RETRYABLE:
            return False
        if self.retry_hint and self.retry_hint.retryable:
            return False
        return True
    
    @property
    def is_retryable(self) -> bool:
        """Whether this result can be retried."""
        return (
            self.status == ExecutionStatus.RETRYABLE or
            (self.retry_hint is not None and self.retry_hint.retryable)
        )
    
    @property
    def is_safe(self) -> bool:
        """Whether this result is safe (no safety violation)."""
        return self.status not in (ExecutionStatus.UNSAFE, ExecutionStatus.BLOCKED)
    
    @classmethod
    def success_result(
        cls,
        summary: str,
        output: Optional[str] = None,
        evidence: Optional[ExecutionEvidence] = None
    ) -> "UnifiedExecutionResult":
        """Create a successful result."""
        return cls(
            status=ExecutionStatus.SUCCESS,
            summary=summary,
            output=output,
            user_safe_message=summary,
            evidence=evidence or ExecutionEvidence()
        )
    
    @classmethod
    def failure_result(
        cls,
        summary: str,
        failure_class: FailureClass,
        user_safe_message: Optional[str] = None,
        next_action: Optional[str] = None,
        evidence: Optional[ExecutionEvidence] = None,
        retry_hint: Optional[RetryHint] = None
    ) -> "UnifiedExecutionResult":
        """Create a failure result."""
        status = ExecutionStatus.FAILED
        if retry_hint and retry_hint.retryable:
            status = ExecutionStatus.RETRYABLE
        
        return cls(
            status=status,
            summary=summary,
            failure_class=failure_class,
            user_safe_message=user_safe_message or summary,
            next_recommended_action=next_action,
            evidence=evidence or ExecutionEvidence(),
            retry_hint=retry_hint
        )
    
    @classmethod
    def blocked_result(
        cls,
        summary: str,
        failure_class: FailureClass,
        reason: str,
        next_action: Optional[str] = None,
        evidence: Optional[ExecutionEvidence] = None
    ) -> "UnifiedExecutionResult":
        """Create a blocked/unsafe result."""
        return cls(
            status=ExecutionStatus.BLOCKED if failure_class != FailureClass.SAFETY_BLOCK else ExecutionStatus.UNSAFE,
            summary=summary,
            failure_class=failure_class,
            user_safe_message=f"操作被阻止: {reason}",
            next_recommended_action=next_action,
            evidence=evidence or ExecutionEvidence()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "summary": self.summary,
            "failure_class": self.failure_class.value if self.failure_class else None,
            "user_safe_message": self.user_safe_message,
            "next_recommended_action": self.next_recommended_action,
            "is_retryable": self.is_retryable,
            "is_terminal": self.is_terminal,
            "output": self.output[:500] if self.output else None,
            "error": self.error,
            "evidence": {
                "timestamp": self.evidence.timestamp,
                "operation": self.evidence.operation,
                "tool_name": self.evidence.tool_name,
                "duration_ms": self.evidence.duration_ms
            },
            "retry_hint": {
                "retryable": self.retry_hint.retryable,
                "current_retry": self.retry_hint.current_retry,
                "max_retries": self.retry_hint.max_retries
            } if self.retry_hint else None
        }
    
    def to_legacy(self) -> tuple:
        """
        Convert to legacy (success, output, error) tuple.
        
        For backward compatibility with existing code.
        """
        return (self.success, self.output, self.error)


def classify_error(error: Exception) -> FailureClass:
    """
    Classify an exception into a failure class.
    
    Args:
        error: The exception to classify
    
    Returns:
        FailureClass enum value
    """
    error_str = str(error).lower()
    error_type = type(error).__name__.lower()
    
    # Timeout
    if 'timeout' in error_str or 'timeout' in error_type:
        return FailureClass.TIMEOUT
    
    # Permission
    if 'permission' in error_str or 'access denied' in error_str:
        return FailureClass.PERMISSION_ERROR
    
    # Not found
    if 'not found' in error_str or 'no such file' in error_str or 'does not exist' in error_str:
        return FailureClass.NOT_FOUND
    
    # Validation
    if 'validation' in error_str or 'invalid' in error_str:
        return FailureClass.VALIDATION_ERROR
    
    # Safety
    if 'unsafe' in error_str or 'blocked' in error_str or 'forbidden' in error_str:
        return FailureClass.SAFETY_BLOCK
    
    # Environment
    if 'connection' in error_str or 'network' in error_str or 'environment' in error_str:
        return FailureClass.ENVIRONMENT_ERROR
    
    # Model errors
    if 'llm' in error_str or 'model' in error_str or 'api' in error_str:
        return FailureClass.MODEL_ERROR
    
    # Default
    return FailureClass.UNKNOWN


def should_retry(failure_class: FailureClass) -> RetryHint:
    """
    Determine retry behavior for a failure class.
    
    Args:
        failure_class: The failure classification
    
    Returns:
        RetryHint with retry configuration
    """
    # Retryable failures
    retryable_classes = {
        FailureClass.TIMEOUT,
        FailureClass.ENVIRONMENT_ERROR,
        FailureClass.MODEL_ERROR
    }
    
    if failure_class in retryable_classes:
        return RetryHint(
            retryable=True,
            max_retries=3,
            retry_after_ms=2000,
            backoff_multiplier=2.0,
            reason=f"Transient failure: {failure_class.value}"
        )
    
    # Non-retryable failures
    return RetryHint(
        retryable=False,
        reason=f"Non-retryable failure: {failure_class.value}"
    )
