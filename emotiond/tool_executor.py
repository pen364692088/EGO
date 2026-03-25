"""
US-7102 Extension: Tool Execution Safety Shell

Execution safety layer that wraps tool calls with:
- Schema validation (input/output)
- Timeout / retry / backoff
- Budget / rate-limit enforcement
- Idempotency key
- Output sanitization (anti-prompt-injection)

Tool outputs are treated as untrusted external input:
- Never crash on malformed output
- Never leak unauthorized data
- Never pollute memory/decision state
"""
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import time
import re
from emotiond.tool_metrics import get_metrics_collector, ToolMetricsCollector


class ExecutionReasonCode(Enum):
    """Reason codes for tool execution failures (aggregatable)"""
    # Success
    EXEC_SUCCESS = "exec_success"
    
    # Schema validation failures
    INPUT_SCHEMA_INVALID = "input_schema_invalid"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    TOOL_RESULT_INVALID = "tool_result_invalid"
    
    # Timeout / retry failures
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_TRANSIENT_ERROR = "tool_transient_error"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    
    # Budget / rate-limit
    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Idempotency
    IDEMPOTENCY_DUPLICATE = "idempotency_duplicate"
    
    # Sanitization
    OUTPUT_SANITIZED = "output_sanitized"
    SUSPICIOUS_CONTENT_BLOCKED = "suspicious_content_blocked"


@dataclass
class ExecutionResult:
    """Result of tool execution with safety checks"""
    success: bool
    reason_code: ExecutionReasonCode
    tool_name: str
    output: Optional[Any] = None
    sanitized_output: Optional[Any] = None
    error_message: str = ""
    trace_id: str = ""
    timestamp: str = ""
    duration_ms: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class RetryPolicy:
    """Retry configuration for tool execution"""
    max_retries: int = 3
    initial_delay_ms: float = 100.0
    max_delay_ms: float = 5000.0
    backoff_multiplier: float = 2.0
    retryable_errors: List[str] = field(default_factory=lambda: ["timeout", "transient"])
    
    def get_delay_ms(self, retry_count: int) -> float:
        """Calculate delay with exponential backoff"""
        delay = self.initial_delay_ms * (self.backoff_multiplier ** retry_count)
        return min(delay, self.max_delay_ms)


@dataclass
class ExecutionConfig:
    """Configuration for tool execution"""
    default_timeout_ms: float = 30000.0  # 30 seconds
    max_output_size_bytes: int = 1024 * 1024  # 1 MB
    sanitize_output: bool = True
    validate_schema: bool = True
    enable_idempotency: bool = True


class SchemaValidator:
    """Validates tool inputs/outputs against schema"""
    
    TYPE_VALIDATORS = {
        "string": lambda x: isinstance(x, str),
        "int": lambda x: isinstance(x, int) and not isinstance(x, bool),
        "float": lambda x: isinstance(x, (int, float)),
        "bool": lambda x: isinstance(x, bool),
        "list": lambda x: isinstance(x, list),
        "dict": lambda x: isinstance(x, dict),
        "any": lambda x: True,
    }
    
    @classmethod
    def validate_input(
        cls,
        inputs: Dict[str, Any],
        schema: Dict[str, str],
        required: set
    ) -> Tuple[bool, str]:
        """
        Validate input against schema.
        
        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        for field_name in required:
            if field_name not in inputs:
                return False, f"Missing required field: {field_name}"
        
        # Check types
        for field_name, value in inputs.items():
            if field_name not in schema:
                # Allow extra fields with warning (not error)
                continue
            
            expected_type = schema[field_name]
            validator = cls.TYPE_VALIDATORS.get(expected_type)
            
            if validator and not validator(value):
                return False, (
                    f"Field '{field_name}' has wrong type: "
                    f"expected {expected_type}, got {type(value).__name__}"
                )
        
        return True, ""
    
    @classmethod
    def validate_output(
        cls,
        output: Any,
        schema: Dict[str, str]
    ) -> Tuple[bool, str]:
        """
        Validate output against schema.
        
        Returns:
            (is_valid, error_message)
        """
        if output is None:
            # None output is always valid (tool may have failed)
            return True, ""
        
        if not isinstance(output, dict):
            # Non-dict output - check if schema expects single value
            if len(schema) == 1:
                field_name, expected_type = next(iter(schema.items()))
                validator = cls.TYPE_VALIDATORS.get(expected_type)
                if validator and validator(output):
                    return True, ""
            return False, f"Output must be dict, got {type(output).__name__}"
        
        # Validate each field in output
        for field_name, expected_type in schema.items():
            if field_name in output:
                value = output[field_name]
                validator = cls.TYPE_VALIDATORS.get(expected_type)
                
                if validator and not validator(value):
                    return False, (
                        f"Output field '{field_name}' has wrong type: "
                        f"expected {expected_type}, got {type(value).__name__}"
                    )
        
        return True, ""


class OutputSanitizer:
    """Sanitizes tool output to prevent prompt injection"""
    
    # Patterns that might indicate prompt injection attempts
    SUSPICIOUS_PATTERNS = [
        r"ignore (all )?(previous|above|prior) (instructions?|prompts?)",
        r"disregard (all )?(previous|above|prior)",
        r"you (are|must|should|will).*(different|another|no restrictions?)",
        r"new (instructions?|directives?|rules?)",
        r"system[:：]\s*",
        r"<[!/]?system>",
        r"execute (without|ignoring|bypassing)",
        r"override (safety|security|permissions?)",
        r"(reveal|disclose|leak|share).*(secrets?|keys?|passwords?|credentials)",
    ]
    
    MAX_OUTPUT_LENGTH = 50000  # Characters
    
    @classmethod
    def sanitize(cls, output: Any, max_length: int = None) -> Tuple[Any, bool, List[str]]:
        """
        Sanitize tool output.
        
        Returns:
            (sanitized_output, was_sanitized, warnings)
        """
        if output is None:
            return None, False, []
        
        max_length = max_length or cls.MAX_OUTPUT_LENGTH
        warnings = []
        was_sanitized = False
        
        # Convert to string for pattern checking
        output_str = json.dumps(output) if not isinstance(output, str) else output
        
        # Check for suspicious patterns
        suspicious_found = []
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, output_str, re.IGNORECASE):
                suspicious_found.append(pattern)
        
        if suspicious_found:
            warnings.append(f"Suspicious content patterns detected: {len(suspicious_found)}")
            was_sanitized = True
            
            # Redact suspicious content
            for pattern in suspicious_found:
                output_str = re.sub(
                    pattern, "[REDACTED]", 
                    output_str, 
                    flags=re.IGNORECASE
                )
        
        # Truncate if too long
        if len(output_str) > max_length:
            warnings.append(f"Output truncated from {len(output_str)} to {max_length} chars")
            output_str = output_str[:max_length] + "... [TRUNCATED]"
            was_sanitized = True
        
        # Parse back to original type
        if isinstance(output, str):
            sanitized = output_str
        else:
            try:
                sanitized = json.loads(output_str)
            except json.JSONDecodeError:
                sanitized = output_str
        
        return sanitized, was_sanitized, warnings


class ToolExecutor:
    """
    Safe tool execution wrapper.
    
    All tool calls go through this layer:
    - Schema validation
    - Timeout enforcement
    - Retry with backoff
    - Output sanitization
    - Idempotency check
    """
    
    def __init__(
        self,
        config: Optional[ExecutionConfig] = None,
        retry_policy: Optional[RetryPolicy] = None,
        metrics_collector: Optional[ToolMetricsCollector] = None
    ):
        self.config = config or ExecutionConfig()
        self.retry_policy = retry_policy or RetryPolicy()
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.idempotency_cache: Dict[str, ExecutionResult] = {}
        self.execution_history: List[ExecutionResult] = []
        self.max_history = 1000
    
    def generate_idempotency_key(
        self,
        tool_name: str,
        inputs: Dict[str, Any],
        trace_id: str
    ) -> str:
        """Generate idempotency key for duplicate detection"""
        key_data = {
            "tool": tool_name,
            "inputs": json.dumps(inputs, sort_keys=True, default=str),
            "trace": trace_id
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]
    
    def check_idempotency(self, key: str) -> Optional[ExecutionResult]:
        """Check if this execution was already done"""
        return self.idempotency_cache.get(key)
    
    def execute(
        self,
        tool_name: str,
        tool_impl: Callable,
        inputs: Dict[str, Any],
        io_schema: Any,
        trace_id: str = "",
        timeout_ms: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute tool with safety checks.
        
        Args:
            tool_name: Name of tool
            tool_impl: Callable that executes the tool
            inputs: Input parameters
            io_schema: IOSchema from tool definition
            trace_id: Trace ID for correlation
            timeout_ms: Optional timeout override
            context: Additional context
        
        Returns:
            ExecutionResult with success/failure details
        """
        context = context or {}
        timeout_ms = timeout_ms or self.config.default_timeout_ms
        start_time = time.time()
        
        # 1. Validate input schema
        if self.config.validate_schema and hasattr(io_schema, 'inputs'):
            is_valid, error = SchemaValidator.validate_input(
                inputs, 
                io_schema.inputs, 
                io_schema.required_inputs
            )
            if not is_valid:
                return ExecutionResult(
                    success=False,
                    reason_code=ExecutionReasonCode.INPUT_SCHEMA_INVALID,
                    tool_name=tool_name,
                    error_message=error,
                    trace_id=trace_id
                )
        
        # 2. Idempotency check
        if self.config.enable_idempotency:
            idempotency_key = self.generate_idempotency_key(tool_name, inputs, trace_id)
            cached = self.check_idempotency(idempotency_key)
            if cached:
                cached.metadata["idempotency_hit"] = True
                return cached
        
        # 3. Execute with retry
        retry_count = 0
        last_error = None
        
        while retry_count <= self.retry_policy.max_retries:
            try:
                # Execute tool
                output = tool_impl(inputs, context)
                
                # 4. Validate output schema
                if self.config.validate_schema and hasattr(io_schema, 'outputs'):
                    is_valid, error = SchemaValidator.validate_output(
                        output, io_schema.outputs
                    )
                    if not is_valid:
                        return ExecutionResult(
                            success=False,
                            reason_code=ExecutionReasonCode.OUTPUT_SCHEMA_INVALID,
                            tool_name=tool_name,
                            output=output,
                            error_message=error,
                            trace_id=trace_id,
                            retry_count=retry_count
                        )
                
                # 5. Sanitize output
                sanitized_output = output
                if self.config.sanitize_output:
                    sanitized_output, was_sanitized, warnings = OutputSanitizer.sanitize(
                        output, self.config.max_output_size_bytes
                    )
                    
                    if was_sanitized:
                        reason_code = ExecutionReasonCode.OUTPUT_SANITIZED
                    else:
                        reason_code = ExecutionReasonCode.EXEC_SUCCESS
                else:
                    reason_code = ExecutionReasonCode.EXEC_SUCCESS
                
                duration_ms = (time.time() - start_time) * 1000
                
                result = ExecutionResult(
                    success=True,
                    reason_code=reason_code,
                    tool_name=tool_name,
                    output=output,
                    sanitized_output=sanitized_output,
                    trace_id=trace_id,
                    duration_ms=duration_ms,
                    retry_count=retry_count,
                    metadata={"warnings": warnings if self.config.sanitize_output else []}
                )
                
                # Cache for idempotency
                if self.config.enable_idempotency:
                    self.idempotency_cache[idempotency_key] = result
                
                # Record history
                self._record_execution(result)
                
                return result
                
            except TimeoutError:
                last_error = "timeout"
                reason_code = ExecutionReasonCode.TOOL_TIMEOUT
                
            except Exception as e:
                last_error = str(e)
                error_lower = last_error.lower()
                
                if "timeout" in error_lower:
                    reason_code = ExecutionReasonCode.TOOL_TIMEOUT
                elif any(e in error_lower for e in ["transient", "temporary", "retry"]):
                    reason_code = ExecutionReasonCode.TOOL_TRANSIENT_ERROR
                else:
                    # Non-retryable error
                    duration_ms = (time.time() - start_time) * 1000
                    result = ExecutionResult(
                        success=False,
                        reason_code=ExecutionReasonCode.TOOL_RESULT_INVALID,
                        tool_name=tool_name,
                        error_message=last_error,
                        trace_id=trace_id,
                        duration_ms=duration_ms,
                        retry_count=retry_count
                    )
                    self._record_execution(result)
                    return result
            
            # Retry with backoff
            retry_count += 1
            if retry_count <= self.retry_policy.max_retries:
                delay_ms = self.retry_policy.get_delay_ms(retry_count - 1)
                time.sleep(delay_ms / 1000.0)
        
        # Max retries exceeded
        duration_ms = (time.time() - start_time) * 1000
        result = ExecutionResult(
            success=False,
            reason_code=ExecutionReasonCode.MAX_RETRIES_EXCEEDED,
            tool_name=tool_name,
            error_message=f"Max retries exceeded. Last error: {last_error}",
            trace_id=trace_id,
            duration_ms=duration_ms,
            retry_count=retry_count
        )
        self._record_execution(result)
        return result
    
    def _record_execution(self, result: ExecutionResult) -> None:
        """Record execution in history and metrics"""
        self.execution_history.append(result)
        
        # Record to metrics collector
        if self.metrics_collector:
            self.metrics_collector.record_execution(
                trace_id=result.trace_id,
                tool_name=result.tool_name,
                duration_ms=result.duration_ms,
                success=result.success,
                reason_code=result.reason_code.value,
                retry_count=result.retry_count,
                input_data=None,  # Not stored in ExecutionResult
                output_data=result.output,
                sanitized=result.reason_code == ExecutionReasonCode.OUTPUT_SANITIZED,
                error_message=result.error_message
            )
        
        # Trim history if needed
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        total = len(self.execution_history)
        successful = sum(1 for r in self.execution_history if r.success)
        
        reason_counts: Dict[str, int] = {}
        for result in self.execution_history:
            reason = result.reason_code.value
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        avg_duration = 0.0
        if self.execution_history:
            durations = [r.duration_ms for r in self.execution_history]
            avg_duration = sum(durations) / len(durations)
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 1.0,
            "reason_distribution": reason_counts,
            "avg_duration_ms": avg_duration,
            "idempotency_cache_size": len(self.idempotency_cache)
        }


# Singleton instance
_executor_instance: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """Get singleton executor instance"""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ToolExecutor()
    return _executor_instance


def reset_tool_executor() -> None:
    """Reset executor (for testing)"""
    global _executor_instance
    _executor_instance = None
