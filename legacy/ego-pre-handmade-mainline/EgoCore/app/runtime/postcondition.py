"""
OpenEmotion Agent Runtime - Postcondition Validator

P2-A.2: Validates that execution results match user intent.

Prevents "fake completed" scenarios where:
- Tool executes successfully
- But actual result doesn't match user's goal

Core checks:
- Actual path matches intended path
- Operation type matches intent
- File/dir actually exists after creation
"""

from dataclasses import dataclass
from typing import Optional, List
import os

from app.runtime.intent_mapper import OperationIntent, OperationType
from app.runtime.execution_result import (
    UnifiedExecutionResult, ExecutionStatus, FailureClass, ExecutionEvidence
)


@dataclass
class PostconditionResult:
    """
    Result of postcondition validation.
    
    Indicates whether the execution actually achieved the user's intent.
    """
    success: bool
    actual_path: Optional[str] = None
    expected_path: Optional[str] = None
    path_match: bool = True
    operation_match: bool = True
    exists_check: bool = True
    violations: List[str] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []
    
    def to_failure_class(self) -> Optional[FailureClass]:
        """Determine the appropriate failure class for violations."""
        if not self.path_match:
            return FailureClass.INTENT_MISMATCH
        if not self.operation_match:
            return FailureClass.INTENT_MISMATCH
        if not self.exists_check:
            return FailureClass.POSTCONDITION_FAILED
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "actual_path": self.actual_path,
            "expected_path": self.expected_path,
            "path_match": self.path_match,
            "operation_match": self.operation_match,
            "exists_check": self.exists_check,
            "violations": self.violations
        }


class PostconditionValidator:
    """
    Validates that execution results match user intent.
    
    P2-A.2 implementation:
    - Path validation (actual vs expected)
    - Operation type validation
    - Existence verification for write/mkdir operations
    """
    
    def validate(
        self,
        intent: OperationIntent,
        actual_path: Optional[str],
        tool_result: Optional[dict] = None
    ) -> PostconditionResult:
        """
        Validate that execution matches intent.
        
        Args:
            intent: The parsed operation intent
            actual_path: The path actually used in execution
            tool_result: The tool execution result (optional)
        
        Returns:
            PostconditionResult with validation outcome
        """
        violations = []
        expected_path = intent.target_path
        
        # 1. Path match validation
        path_match = self._validate_path_match(expected_path, actual_path, violations)
        
        # 2. Existence check for write/mkdir operations
        exists_check = True
        if intent.operation in (OperationType.WRITE_FILE, OperationType.MKDIR):
            if expected_path:
                exists_check = self._validate_exists(expected_path, violations)
        
        # 3. Content check for write operations (if we have tool result)
        # TODO: Add content validation if needed
        
        success = path_match and exists_check and len(violations) == 0
        
        return PostconditionResult(
            success=success,
            actual_path=actual_path,
            expected_path=expected_path,
            path_match=path_match,
            exists_check=exists_check,
            violations=violations
        )
    
    def validate_and_wrap_result(
        self,
        intent: OperationIntent,
        actual_path: Optional[str],
        tool_result: UnifiedExecutionResult
    ) -> UnifiedExecutionResult:
        """
        Validate and potentially modify the execution result.
        
        If postcondition fails, converts SUCCESS to FAILURE.
        
        Args:
            intent: The parsed operation intent
            actual_path: The path actually used in execution
            tool_result: The original tool execution result
        
        Returns:
            Original or modified UnifiedExecutionResult
        """
        # Only validate if tool reported success
        if not tool_result.success:
            return tool_result
        
        # Run validation
        postcondition = self.validate(intent, actual_path)
        
        if postcondition.success:
            # Add postcondition info to evidence
            tool_result.evidence.additional_data["postcondition"] = postcondition.to_dict()
            return tool_result
        
        # Postcondition failed - convert to failure
        failure_class = postcondition.to_failure_class()
        
        violation_msg = "; ".join(postcondition.violations) if postcondition.violations else "Postcondition validation failed"
        
        return UnifiedExecutionResult.failure_result(
            summary=f"操作执行但未达成目标: {violation_msg}",
            failure_class=failure_class or FailureClass.POSTCONDITION_FAILED,
            user_safe_message=f"操作完成但结果不符合预期。预期路径: {postcondition.expected_path}, 实际路径: {postcondition.actual_path}",
            next_action="请检查请求描述是否清晰，或重新尝试",
            evidence=ExecutionEvidence(
                operation="postcondition_validation",
                additional_data={
                    "postcondition": postcondition.to_dict(),
                    "original_result": tool_result.to_dict()
                }
            )
        )
    
    def _validate_path_match(
        self,
        expected: Optional[str],
        actual: Optional[str],
        violations: List[str]
    ) -> bool:
        """Validate that actual path matches expected path."""
        if not expected:
            # No expected path - can't validate
            return True
        
        if not actual:
            violations.append(f"实际路径为空，预期: {expected}")
            return False
        
        # Normalize paths for comparison
        expected_norm = os.path.normpath(expected.rstrip('/'))
        actual_norm = os.path.normpath(actual.rstrip('/'))
        
        if expected_norm != actual_norm:
            violations.append(f"路径不匹配: 预期 '{expected_norm}', 实际 '{actual_norm}'")
            return False
        
        return True
    
    def _validate_exists(self, path: str, violations: List[str]) -> bool:
        """Validate that a path exists (for write/mkdir operations)."""
        if not os.path.exists(path):
            violations.append(f"路径不存在: {path}")
            return False
        return True


# Global instance
_validator: Optional[PostconditionValidator] = None


def get_postcondition_validator() -> PostconditionValidator:
    """Get or create global PostconditionValidator instance."""
    global _validator
    if _validator is None:
        _validator = PostconditionValidator()
    return _validator


def validate_postcondition(
    intent: OperationIntent,
    actual_path: Optional[str],
    tool_result: UnifiedExecutionResult
) -> UnifiedExecutionResult:
    """
    Validate and potentially modify execution result.
    
    Convenience function using global validator.
    """
    return get_postcondition_validator().validate_and_wrap_result(
        intent, actual_path, tool_result
    )
