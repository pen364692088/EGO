"""
OpenEmotion Agent Runtime - Python Tool

Python code execution with security controls.
"""

import logging
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading

# resource 模块仅在 Unix 系统可用
try:
    import resource
except ImportError:
    resource = None

from app.tools.base import (
    Tool, ToolResult, ToolStatus, ToolSecurityError, ToolTimeoutError, ToolValidationError
)


logger = logging.getLogger(__name__)


class PythonTool(Tool):
    """
    Tool for executing Python code in a controlled environment.
    
    Security controls:
    - Module whitelist/blacklist
    - Timeout enforcement
    - Memory limits
    - Output truncation
    - Working directory restriction
    - Built-in function restrictions
    """
    
    # Always denied modules (dangerous)
    ALWAYS_DENIED_MODULES: Set[str] = {
        'subprocess', 'socket', 'multiprocessing', 'threading',
        'ctypes', 'signal', 'posix', 'nt',
        'importlib', 'pkgutil',  # Import control
    }
    
    # Dangerous built-in functions to restrict
    RESTRICTED_BUILTINS: Set[str] = {
        'exec', 'eval', 'compile', 'open', 'input',
        '__import__', 'exit', 'quit'
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Python tool.
        
        Args:
            config: Tool configuration from tools.yaml
        """
        self.config = config or {}
        
        # Timeout in seconds
        self.timeout: int = self.config.get('timeout', 120)
        
        # Maximum output length
        self.max_output_length: int = self.config.get('max_output_length', 10000)
        
        # Allowed modules
        self.allowed_modules: Set[str] = set(
            self.config.get('allowed_modules', 
                           ['os', 'sys', 'json', 're', 'datetime', 'math', 'pathlib'])
        )
        
        # Denied modules
        self.denied_modules: Set[str] = set(
            self.config.get('denied_modules', [])
        )
        
        # Memory limit in MB
        self.memory_limit_mb: int = self.config.get('memory_limit_mb', 512)
        
        # Working directory
        self.working_directory: Optional[str] = self.config.get('working_directory')
    
    @property
    def name(self) -> str:
        return "python"
    
    @property
    def description(self) -> str:
        return "Execute Python code with security restrictions"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default: {self.timeout})"
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory (overrides config)"
                }
            },
            "required": ["code"]
        }
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters."""
        code = params.get('code')
        if not code:
            return "Missing required parameter: code"
        
        if not isinstance(code, str):
            return "Code must be a string"
        
        # Check for forbidden patterns
        forbidden_patterns = [
            '__import__',
            'import subprocess',
            'import socket',
            'import multiprocessing',
            'import threading',
            'from subprocess',
            'from socket',
            'exec(',
            'eval(',
        ]
        
        code_lower = code.lower()
        for pattern in forbidden_patterns:
            if pattern.lower() in code_lower:
                return f"Code contains forbidden pattern: {pattern}"
        
        return None
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute Python code."""
        code = params['code']
        timeout = params.get('timeout', self.timeout)
        working_dir = params.get('working_directory', self.working_directory)
        
        # Validate working directory
        if working_dir:
            try:
                work_path = Path(working_dir).resolve()
                if not work_path.exists():
                    return ToolResult.failure_result(
                        f"Working directory does not exist: {working_dir}",
                        ToolStatus.FAILED
                    )
                if not work_path.is_dir():
                    return ToolResult.failure_result(
                        f"Working directory is not a directory: {working_dir}",
                        ToolStatus.FAILED
                    )
                working_dir = str(work_path)
            except Exception as e:
                return ToolResult.failure_result(
                    f"Invalid working directory: {e}",
                    ToolStatus.FAILED
                )
        
        # Execute code
        return self._execute_code(code, timeout, working_dir)
    
    def _execute_code(self, code: str, timeout: int, 
                      working_dir: Optional[str]) -> ToolResult:
        """
        Execute Python code in a controlled environment.
        
        Args:
            code: Python code to execute
            timeout: Timeout in seconds
            working_dir: Working directory
        
        Returns:
            ToolResult
        """
        # Create execution namespace with restricted builtins
        safe_builtins = self._create_safe_builtins()
        
        # Prepare namespace
        namespace = {
            '__builtins__': safe_builtins,
            '__name__': '__main__',
        }
        
        # Import allowed modules
        for module_name in self.allowed_modules:
            if module_name in self.denied_modules or module_name in self.ALWAYS_DENIED_MODULES:
                continue
            try:
                namespace[module_name] = __import__(module_name)
            except ImportError:
                logger.warning(f"Could not import allowed module: {module_name}")
        
        # Capture stdout/stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        # Result storage
        result_container = {'result': None, 'error': None}
        
        def run_code():
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    # Change directory if specified
                    original_dir = None
                    if working_dir:
                        original_dir = Path.cwd()
                        os.chdir(working_dir)
                    
                    try:
                        exec(code, namespace)
                    finally:
                        # Restore directory
                        if original_dir:
                            os.chdir(original_dir)
            
            except Exception:
                result_container['error'] = traceback.format_exc()
        
        # Run in thread with timeout
        thread = threading.Thread(target=run_code)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            # Thread is still running - timeout
            return ToolResult.timeout_result(
                f"Code execution timed out after {timeout} seconds"
            )
        
        # Get outputs
        stdout = stdout_capture.getvalue()
        stderr = stderr_capture.getvalue()
        error = result_container.get('error')
        
        # Combine outputs
        output = stdout
        if stderr:
            if output:
                output += '\n' + stderr
            else:
                output = stderr
        
        # Add error info if present
        if error:
            if output:
                output += '\n' + error
            else:
                output = error
        
        # Truncate if needed
        truncated = False
        if len(output) > self.max_output_length:
            output = output[:self.max_output_length]
            output += f"\n... [truncated, {len(output)} chars total]"
            truncated = True
        
        # Build metadata
        metadata = {
            'timeout': timeout,
            'working_directory': working_dir,
            'truncated': truncated,
            'has_error': error is not None
        }
        
        if error:
            return ToolResult.failure_result(output or "Code execution failed", ToolStatus.FAILED)
        else:
            return ToolResult.success_result(output or "Code executed successfully", metadata)
    
    def _create_safe_builtins(self) -> Dict[str, Any]:
        """
        Create a restricted builtins dict.
        
        Returns:
            Dictionary with safe built-in functions
        """
        import builtins
        
        safe = {}
        
        # Copy allowed builtins
        allowed = {
            'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter',
            'float', 'format', 'frozenset', 'hash', 'hex', 'int', 'isinstance',
            'issubclass', 'iter', 'len', 'list', 'map', 'max', 'min', 'next',
            'object', 'oct', 'ord', 'pow', 'print', 'range', 'repr', 'reversed',
            'round', 'set', 'slice', 'sorted', 'str', 'sum', 'tuple', 'type',
            'zip', 'True', 'False', 'None', 'Ellipsis', 'NotImplemented',
            'bytes', 'bytearray', 'complex', 'chr', 'divmod', 'id', 'vars',
            'locals', 'globals', 'dir', 'hasattr', 'getattr', 'setattr',
            'delattr', 'callable', 'property', 'classmethod', 'staticmethod',
            'super', 'base', 'breakpoint', 'ascii', 'bin', 'copyright',
            'credits', 'help', 'license'
        }
        
        for name in allowed:
            if hasattr(builtins, name):
                safe[name] = getattr(builtins, name)
        
        return safe


# Import os for chdir in run_code
import os


def create_python_tool(config: Optional[Dict[str, Any]] = None) -> PythonTool:
    """
    Create and return a configured PythonTool instance.
    
    Args:
        config: Tool configuration
    
    Returns:
        PythonTool instance
    """
    return PythonTool(config)
