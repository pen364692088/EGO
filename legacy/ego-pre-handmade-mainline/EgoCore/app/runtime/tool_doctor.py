"""
OpenEmotion Agent Runtime - Tool Preflight & Doctor

Provides pre-execution validation and health checks for tools.

Preflight checks run BEFORE tool execution to catch:
- Invalid parameters
- Safety violations
- Resource unavailability
- Permission issues

Tool Doctor provides runtime diagnostics and suggestions.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Callable
from enum import Enum
import os
import re
from pathlib import Path

from app.runtime.execution_result import (
    UnifiedExecutionResult, ExecutionStatus, FailureClass,
    ExecutionEvidence, RetryHint
)


class PreflightCheck(str, Enum):
    """Types of preflight checks."""
    PARAMETER_VALIDATION = "parameter_validation"
    PATH_BOUNDARY = "path_boundary"
    WORKING_DIRECTORY = "working_directory"
    TIMEOUT_CONFIG = "timeout_config"
    COMMAND_DANGER = "command_danger"
    PYTHON_RESTRICTION = "python_restriction"
    INPUT_SIZE = "input_size"
    OUTPUT_SIZE = "output_size"
    DEPENDENCY_AVAILABILITY = "dependency_availability"
    PERMISSION = "permission"


@dataclass
class PreflightResult:
    """Result of a preflight check."""
    check: PreflightCheck
    passed: bool
    message: str
    severity: str = "warning"  # warning, error, critical
    suggestion: Optional[str] = None


@dataclass
class ToolDoctorReport:
    """Diagnostic report from tool doctor."""
    tool_name: str
    healthy: bool
    checks: List[PreflightResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    @property
    def has_errors(self) -> bool:
        return any(not c.passed for c in self.checks)
    
    def get_failed_checks(self) -> List[PreflightResult]:
        return [c for c in self.checks if not c.passed]


# ============ Preflight Rules ============

DANGEROUS_SHELL_PATTERNS = [
    r"rm\s+-rf\s+/",           # rm -rf /
    r"rm\s+-rf\s+~",           # rm -rf ~
    r">\s*/dev/sd",            # Write to disk
    r"mkfs",                   # Format disk
    r"dd\s+if=.*of=/dev/",     # dd to device
    r":()\s*{\s*:\|:&\s*}",    # Fork bomb
    r"chmod\s+777\s+/",        # chmod 777 /
    r"chown\s+.*\s+/",         # chown root
    r"wget.*\|\s*sh",          # Download and execute
    r"wget.*\|\s*bash",        # Download and execute
    r"curl.*\|\s*sh",          # Download and execute
    r"curl.*\|\s*bash",        # Download and execute
    r"eval\s+.*",              # eval
    r"exec\s+.*",              # exec
]

RESTRICTED_PATHS = [
    "/etc/passwd",
    "/etc/shadow",
    "/root",
    "/var/log",
    "/proc",
    "/sys",
]

ALLOWED_PATH_PREFIXES = [
    ".",                        # Current directory
    "./",                       # Relative path
    os.path.expanduser("~"),    # Home directory
]

DEFAULT_TIMEOUT_MS = 30000
MAX_TIMEOUT_MS = 300000
MAX_INPUT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_OUTPUT_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class ToolPreflight:
    """
    Preflight checker for tool execution.
    
    Run BEFORE tool execution to validate parameters and catch issues early.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._dangerous_patterns = [
            re.compile(p, re.IGNORECASE) for p in DANGEROUS_SHELL_PATTERNS
        ]
    
    def check_all(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> ToolDoctorReport:
        """
        Run all applicable preflight checks for a tool.
        
        Args:
            tool_name: Name of the tool (file, shell, python)
            params: Tool parameters
        
        Returns:
            ToolDoctorReport with all check results
        """
        report = ToolDoctorReport(tool_name=tool_name, healthy=True)
        
        # Always check input size
        report.checks.append(self._check_input_size(params))
        
        # Tool-specific checks
        if tool_name == "file":
            report.checks.extend(self._check_file_tool(params))
        elif tool_name == "shell":
            report.checks.extend(self._check_shell_tool(params))
        elif tool_name == "python":
            report.checks.extend(self._check_python_tool(params))
        
        # Check timeout
        report.checks.append(self._check_timeout(params))
        
        # Update health status
        report.healthy = not report.has_errors
        
        # Generate suggestions
        for check in report.get_failed_checks():
            if check.suggestion:
                report.suggestions.append(check.suggestion)
        
        return report
    
    def _check_input_size(self, params: Dict[str, Any]) -> PreflightResult:
        """Check if input size is within limits."""
        content = params.get("content", "")
        if isinstance(content, str):
            size = len(content.encode('utf-8'))
        elif isinstance(content, bytes):
            size = len(content)
        else:
            return PreflightResult(
                check=PreflightCheck.INPUT_SIZE,
                passed=True,
                message="No content to check"
            )
        
        if size > MAX_INPUT_SIZE_BYTES:
            return PreflightResult(
                check=PreflightCheck.INPUT_SIZE,
                passed=False,
                message=f"Input size ({size} bytes) exceeds limit ({MAX_INPUT_SIZE_BYTES} bytes)",
                severity="error",
                suggestion="Reduce input size or split into multiple operations"
            )
        
        return PreflightResult(
            check=PreflightCheck.INPUT_SIZE,
            passed=True,
            message=f"Input size: {size} bytes"
        )
    
    def _check_file_tool(self, params: Dict[str, Any]) -> List[PreflightResult]:
        """Preflight checks for file tool."""
        results = []
        
        path = params.get("path", "")
        operation = params.get("operation", "")
        
        # Path boundary check
        results.append(self._check_path_boundary(path))
        
        # Permission check for write operations
        if operation in ("write", "delete"):
            results.append(self._check_write_permission(path))
        
        # File existence for read operations
        if operation == "read":
            results.append(self._check_file_exists(path))
        
        return results
    
    def _check_shell_tool(self, params: Dict[str, Any]) -> List[PreflightResult]:
        """Preflight checks for shell tool."""
        results = []
        
        command = params.get("command", "")
        
        # Command danger check
        results.append(self._check_command_danger(command))
        
        # Working directory check
        cwd = params.get("cwd")
        if cwd:
            results.append(self._check_working_directory(cwd))
        
        return results
    
    def _check_python_tool(self, params: Dict[str, Any]) -> List[PreflightResult]:
        """Preflight checks for python tool."""
        results = []
        
        code = params.get("code", "")
        
        # Python restriction check
        results.append(self._check_python_restrictions(code))
        
        return results
    
    def _check_path_boundary(self, path: str) -> PreflightResult:
        """Check if path is within allowed boundaries."""
        if not path:
            return PreflightResult(
                check=PreflightCheck.PATH_BOUNDARY,
                passed=False,
                message="No path specified",
                severity="error"
            )
        
        # Resolve absolute path
        abs_path = os.path.abspath(path)
        
        # Check restricted paths
        for restricted in RESTRICTED_PATHS:
            if abs_path.startswith(restricted):
                return PreflightResult(
                    check=PreflightCheck.PATH_BOUNDARY,
                    passed=False,
                    message=f"Path '{path}' is in restricted area: {restricted}",
                    severity="critical",
                    suggestion="Choose a different path outside system directories"
                )
        
        return PreflightResult(
            check=PreflightCheck.PATH_BOUNDARY,
            passed=True,
            message=f"Path boundary OK: {abs_path}"
        )
    
    def _check_write_permission(self, path: str) -> PreflightResult:
        """Check write permission for path."""
        abs_path = os.path.abspath(path)
        parent = os.path.dirname(abs_path) or "."
        
        if not os.path.exists(parent):
            return PreflightResult(
                check=PreflightCheck.PERMISSION,
                passed=False,
                message=f"Parent directory does not exist: {parent}",
                severity="error",
                suggestion="Create the directory first or use a different path"
            )
        
        if not os.access(parent, os.W_OK):
            return PreflightResult(
                check=PreflightCheck.PERMISSION,
                passed=False,
                message=f"No write permission for: {parent}",
                severity="error",
                suggestion="Check file permissions or use a different location"
            )
        
        return PreflightResult(
            check=PreflightCheck.PERMISSION,
            passed=True,
            message=f"Write permission OK for: {parent}"
        )
    
    def _check_file_exists(self, path: str) -> PreflightResult:
        """Check if file exists."""
        if not os.path.exists(path):
            return PreflightResult(
                check=PreflightCheck.DEPENDENCY_AVAILABILITY,
                passed=False,
                message=f"File does not exist: {path}",
                severity="error",
                suggestion="Check the file path or create the file first"
            )
        
        return PreflightResult(
            check=PreflightCheck.DEPENDENCY_AVAILABILITY,
            passed=True,
            message=f"File exists: {path}"
        )
    
    def _check_command_danger(self, command: str) -> PreflightResult:
        """Check if command contains dangerous patterns."""
        if not command:
            return PreflightResult(
                check=PreflightCheck.COMMAND_DANGER,
                passed=False,
                message="No command specified",
                severity="error"
            )
        
        for pattern in self._dangerous_patterns:
            if pattern.search(command):
                return PreflightResult(
                    check=PreflightCheck.COMMAND_DANGER,
                    passed=False,
                    message=f"Dangerous command pattern detected",
                    severity="critical",
                    suggestion="This operation requires explicit confirmation"
                )
        
        return PreflightResult(
            check=PreflightCheck.COMMAND_DANGER,
            passed=True,
            message="Command appears safe"
        )
    
    def _check_working_directory(self, cwd: str) -> PreflightResult:
        """Check if working directory exists and is accessible."""
        if not os.path.isdir(cwd):
            return PreflightResult(
                check=PreflightCheck.WORKING_DIRECTORY,
                passed=False,
                message=f"Directory does not exist: {cwd}",
                severity="error"
            )
        
        if not os.access(cwd, os.X_OK):
            return PreflightResult(
                check=PreflightCheck.WORKING_DIRECTORY,
                passed=False,
                message=f"Cannot access directory: {cwd}",
                severity="error"
            )
        
        return PreflightResult(
            check=PreflightCheck.WORKING_DIRECTORY,
            passed=True,
            message=f"Working directory OK: {cwd}"
        )
    
    def _check_timeout(self, params: Dict[str, Any]) -> PreflightResult:
        """Check timeout configuration."""
        timeout = params.get("timeout", DEFAULT_TIMEOUT_MS)
        
        if timeout > MAX_TIMEOUT_MS:
            return PreflightResult(
                check=PreflightCheck.TIMEOUT_CONFIG,
                passed=False,
                message=f"Timeout ({timeout}ms) exceeds maximum ({MAX_TIMEOUT_MS}ms)",
                severity="warning",
                suggestion=f"Reduce timeout to at most {MAX_TIMEOUT_MS}ms"
            )
        
        return PreflightResult(
            check=PreflightCheck.TIMEOUT_CONFIG,
            passed=True,
            message=f"Timeout: {timeout}ms"
        )
    
    def _check_python_restrictions(self, code: str) -> PreflightResult:
        """Check for restricted Python operations."""
        dangerous_imports = [
            "os.system", "subprocess.call", "subprocess.run",
            "eval(", "exec(", "compile(",
            "__import__", "importlib",
            "open(", "file(",
        ]
        
        code_lower = code.lower()
        for dangerous in dangerous_imports:
            if dangerous.lower() in code_lower:
                return PreflightResult(
                    check=PreflightCheck.PYTHON_RESTRICTION,
                    passed=False,
                    message=f"Restricted Python operation detected: {dangerous}",
                    severity="warning",
                    suggestion="This operation may be restricted. Use appropriate tools instead."
                )
        
        return PreflightResult(
            check=PreflightCheck.PYTHON_RESTRICTION,
            passed=True,
            message="Python code passed restrictions check"
        )


class ToolDoctor:
    """
    Runtime diagnostics for tool health.
    
    Provides suggestions and health checks for tool configuration.
    """
    
    def __init__(self, preflight: Optional[ToolPreflight] = None):
        self.preflight = preflight or ToolPreflight()
    
    def diagnose(
        self,
        tool_name: str,
        params: Dict[str, Any]
    ) -> UnifiedExecutionResult:
        """
        Run preflight checks and return unified result.
        
        Args:
            tool_name: Tool to check
            params: Tool parameters
        
        Returns:
            UnifiedExecutionResult with diagnosis
        """
        report = self.preflight.check_all(tool_name, params)
        
        if report.healthy:
            return UnifiedExecutionResult.success_result(
                summary=f"Preflight checks passed for {tool_name}",
                evidence=ExecutionEvidence(
                    operation="preflight",
                    tool_name=tool_name
                )
            )
        
        # Get the most severe failure
        failed = report.get_failed_checks()
        critical = [c for c in failed if c.severity == "critical"]
        errors = [c for c in failed if c.severity == "error"]
        
        if critical:
            check = critical[0]
            failure_class = FailureClass.SAFETY_BLOCK
        elif errors:
            check = errors[0]
            failure_class = FailureClass.VALIDATION_ERROR
        else:
            check = failed[0]
            failure_class = FailureClass.VALIDATION_ERROR
        
        return UnifiedExecutionResult.blocked_result(
            summary=f"Preflight check failed: {check.message}",
            failure_class=failure_class,
            reason=check.message,
            next_action=check.suggestion,
            evidence=ExecutionEvidence(
                operation="preflight",
                tool_name=tool_name
            )
        )
    
    def get_suggestions(
        self,
        tool_name: str,
        error: Exception
    ) -> List[str]:
        """
        Get suggestions for resolving a tool error.
        
        Args:
            tool_name: Tool that failed
            error: The exception
        
        Returns:
            List of suggestions
        """
        suggestions = []
        error_str = str(error).lower()
        
        if "permission" in error_str:
            suggestions.append("检查文件或目录权限")
            suggestions.append("尝试使用用户目录下的路径")
        
        if "not found" in error_str or "no such" in error_str:
            suggestions.append("确认文件或目录路径正确")
            suggestions.append("使用绝对路径或检查当前工作目录")
        
        if "timeout" in error_str:
            suggestions.append("增加超时时间配置")
            suggestions.append("检查网络连接或系统负载")
        
        if tool_name == "shell":
            if "command not found" in error_str:
                suggestions.append("确认命令已安装")
                suggestions.append("检查 PATH 环境变量")
        
        return suggestions


# Singleton instances
_preflight: Optional[ToolPreflight] = None
_doctor: Optional[ToolDoctor] = None


def get_preflight() -> ToolPreflight:
    """Get or create preflight checker."""
    global _preflight
    if _preflight is None:
        _preflight = ToolPreflight()
    return _preflight


def get_doctor() -> ToolDoctor:
    """Get or create tool doctor."""
    global _doctor
    if _doctor is None:
        _doctor = ToolDoctor(get_preflight())
    return _doctor


def run_preflight(
    tool_name: str,
    params: Dict[str, Any]
) -> UnifiedExecutionResult:
    """
    Convenience function to run preflight checks.
    
    Args:
        tool_name: Tool to check
        params: Tool parameters
    
    Returns:
        UnifiedExecutionResult (success if checks pass)
    """
    return get_doctor().diagnose(tool_name, params)
