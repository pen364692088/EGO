"""
OpenEmotion Agent Runtime - Shell Tool

Shell command execution with security controls.
"""

import logging
import os
import shlex
import subprocess
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import threading

from app.tools.base import (
    Tool, ToolResult, ToolStatus, ToolSecurityError, ToolTimeoutError, ToolValidationError
)


logger = logging.getLogger(__name__)


class ShellTool(Tool):
    """
    Tool for executing shell commands with security restrictions.
    
    Security controls:
    - Command whitelist/blacklist
    - Working directory restriction
    - Timeout enforcement
    - Output truncation
    - Environment variable isolation
    """
    
    # Commands that are always denied (dangerous)
    ALWAYS_DENIED: Set[str] = {
        'rm -rf /', 'rm -rf /*', 'rm -rf ~', 'rm -rf ~/',
        'sudo', 'su', 'chmod 777', 'chown',
        'mkfs', 'dd if=', '> /dev/', 'mkfifo',
        'curl | bash', 'wget | bash', 'curl | sh', 'wget | sh',
        ':(){ :|:& };:',  # Fork bomb
        'shutdown', 'reboot', 'init 0', 'init 6',
        'halt', 'poweroff'
    }
    
    # Commands that require special care
    RESTRICTED_COMMANDS: Set[str] = {
        'rm', 'mv', 'cp', 'chmod', 'chown', 'kill', 'pkill'
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize shell tool.
        
        Args:
            config: Tool configuration from tools.yaml
        """
        self.config = config or {}
        
        # Timeout in seconds
        self.timeout: int = self.config.get('timeout', 60)
        
        # Maximum output length (增加到 50000 以支持读取大文件)
        self.max_output_length: int = self.config.get('max_output_length', 50000)
        
        # Allowed commands (if set, only these are allowed)
        self.allowed_commands: List[str] = self.config.get('allowed_commands', [])
        self._allowed_commands_normalized: Set[str] = {
            str(command).strip().lower() for command in self.allowed_commands if str(command).strip()
        }
        
        # Denied commands (always blocked)
        self.denied_commands: List[str] = self.config.get('denied_commands', [])
        
        # Working directory
        self.working_directory: Optional[str] = self.config.get('working_directory')
        
        # Environment variables to pass through
        self.env_passthrough: List[str] = self.config.get('env_passthrough', [])
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return "Execute shell commands with security restrictions"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute"
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
            "required": ["command"]
        }
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters."""
        command = params.get('command')
        if not command:
            return "Missing required parameter: command"
        
        if not isinstance(command, str):
            return "Command must be a string"
        
        return None
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute shell command with preflight check."""
        command = params['command']
        timeout = params.get('timeout', params.get('timeout_seconds', self.timeout))
        working_dir = params.get('working_directory', params.get('working_dir', self.working_directory))
        
        # P2-A.1: Preflight check via tool_doctor (统一前置检查)
        from app.runtime.tool_doctor import run_preflight
        preflight_result = run_preflight("shell", params)
        if not preflight_result.success:
            # Preflight blocked - return the blocked result
            return ToolResult.denied_result(
                preflight_result.user_safe_message or "Blocked by preflight"
            )
        
        # Legacy security check (保留作为双重保障)
        security_error = self._check_security(command)
        if security_error:
            return ToolResult.denied_result(security_error)
        
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
        
        # Execute command
        return self._execute_command(command, timeout, working_dir)
    
    def _check_security(self, command: str) -> Optional[str]:
        """
        Check command against security rules.
        
        Args:
            command: Command to check
        
        Returns:
            Error message if denied, None if allowed
        """
        command_lower = command.lower().strip()
        
        # Check always denied patterns
        for denied in self.ALWAYS_DENIED:
            if denied.lower() in command_lower:
                return f"Command contains forbidden pattern: {denied}"
        
        # Check denied commands from config
        for denied in self.denied_commands:
            if denied.lower() in command_lower:
                return f"Command is denied by configuration: {denied}"
        
        # Parse the command to get the base command
        try:
            # Handle pipes by checking each part
            parts = command.split('|')
            for part in parts:
                part = part.strip()
                # Extract base command
                tokens = shlex.split(part)
                if not tokens:
                    continue
                
                base_cmd = tokens[0]
                
                # Check if in allowed commands (if whitelist is set)
                if self._allowed_commands_normalized:
                    if base_cmd.lower() not in self._allowed_commands_normalized:
                        return f"Command not in allowed list: {base_cmd}"
                
                # Extra check for rm command
                if base_cmd == 'rm':
                    # Check for dangerous rm patterns
                    if '-rf /' in command or '-rf /*' in command:
                        return "Dangerous rm pattern detected"
                    if '-r' in tokens or '-rf' in tokens:
                        # Allow but log warning
                        logger.warning(f"Executing recursive rm: {command}")
        
        except ValueError:
            # shlex.split failed, command might have issues
            pass
        
        return None
    
    def _execute_command(self, command: str, timeout: int, 
                         working_dir: Optional[str]) -> ToolResult:
        """
        Execute the shell command.
        
        Args:
            command: Command to execute
            timeout: Timeout in seconds
            working_dir: Working directory
        
        Returns:
            ToolResult
        """
        try:
            # Build environment
            env = {}
            for var in self.env_passthrough:
                if var in os.environ:
                    env[var] = os.environ[var]
            
            # If no passthrough vars, inherit current environment
            if not env:
                env = None
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
                env=env
            )
            
            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                if output:
                    output += '\n' + result.stderr
                else:
                    output = result.stderr
            
            # Truncate output if needed
            truncated = False
            if len(output) > self.max_output_length:
                output = output[:self.max_output_length]
                output += f"\n... [truncated, {len(output)} chars total]"
                truncated = True
            
            # Build metadata
            metadata = {
                'command': command,
                'return_code': result.returncode,
                'timeout': timeout,
                'working_directory': working_dir,
                'truncated': truncated
            }
            
            if result.returncode == 0:
                return ToolResult.success_result(output or "Command completed successfully", metadata)
            else:
                return ToolResult.failure_result(
                    output or f"Command failed with exit code {result.returncode}",
                    ToolStatus.FAILED
                )
        
        except subprocess.TimeoutExpired:
            return ToolResult.timeout_result(
                f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.exception(f"Unexpected error executing command: {command}")
            return ToolResult.failure_result(f"Failed to execute command: {e}", ToolStatus.FAILED)


def create_shell_tool(config: Optional[Dict[str, Any]] = None) -> ShellTool:
    """
    Create and return a configured ShellTool instance.
    
    Args:
        config: Tool configuration
    
    Returns:
        ShellTool instance
    """
    return ShellTool(config)
