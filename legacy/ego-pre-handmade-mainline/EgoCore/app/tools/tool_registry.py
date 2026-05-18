"""
OpenEmotion Agent Runtime - Tool Registry

Central registry for all tools. Handles registration, lookup,
configuration, and execution with security and logging.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
import threading
from queue import Queue

from app.tools.base import (
    Tool, ToolResult, ToolExecution, ToolStatus,
    ToolError, ToolSecurityError, ToolTimeoutError
)


logger = logging.getLogger(__name__)


@dataclass
class ToolConfig:
    """Configuration for a single tool."""
    enabled: bool = True
    description: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolConfig':
        """Create from dictionary."""
        return cls(
            enabled=data.get('enabled', True),
            description=data.get('description', ''),
            config=data.get('config', {})
        )


@dataclass  
class GlobalToolConfig:
    """Global tool system configuration."""
    enabled: bool = True
    require_confirmation: bool = False
    log_executions: bool = True
    parallel_enabled: bool = False
    max_parallel_tools: int = 1
    retry_on_failure: bool = True
    max_retries: int = 2
    retry_delay: float = 1.0
    audit_log: bool = True
    audit_log_path: str = "./data/logs/tool_audit.log"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalToolConfig':
        """Create from dictionary."""
        global_conf = data.get('global', {})
        exec_conf = data.get('execution', {})
        security_conf = data.get('security', {})
        
        return cls(
            enabled=global_conf.get('enabled', True),
            require_confirmation=global_conf.get('require_confirmation', False),
            log_executions=global_conf.get('log_executions', True),
            parallel_enabled=exec_conf.get('parallel_enabled', False),
            max_parallel_tools=exec_conf.get('max_parallel_tools', 1),
            retry_on_failure=exec_conf.get('retry_on_failure', True),
            max_retries=exec_conf.get('max_retries', 2),
            retry_delay=exec_conf.get('retry_delay', 1.0),
            audit_log=security_conf.get('audit_log', True),
            audit_log_path=security_conf.get('audit_log_path', './data/logs/tool_audit.log')
        )


class ToolRegistry:
    """
    Central registry for all tools.
    
    Responsibilities:
    - Register and manage tools
    - Load configuration from tools.yaml
    - Execute tools with security checks
    - Log all tool executions
    - Handle errors gracefully
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the tool registry.
        
        Args:
            config: Tool configuration dictionary (from tools.yaml)
        """
        self._tools: Dict[str, Tool] = {}
        self._tool_configs: Dict[str, ToolConfig] = {}
        self._global_config: GlobalToolConfig = GlobalToolConfig()
        
        # Execution history (in-memory, recent only)
        self._execution_history: List[ToolExecution] = []
        self._max_history_size = 1000
        
        # Thread lock for thread-safe execution
        self._lock = threading.Lock()
        
        # Audit log file handle
        self._audit_log_file: Optional[Path] = None
        
        # Callback for external confirmation (if required)
        self._confirmation_callback: Optional[Callable[[str, Dict], bool]] = None
        
        # Load config if provided
        if config:
            self.load_config(config)
    
    def load_config(self, config: Dict[str, Any]) -> None:
        """
        Load configuration from tools.yaml format.
        
        Args:
            config: Configuration dictionary
        """
        # Load global config
        self._global_config = GlobalToolConfig.from_dict(config)
        
        # Load individual tool configs
        tools_config = config.get('tools', {})
        for tool_name, tool_conf in tools_config.items():
            self._tool_configs[tool_name] = ToolConfig.from_dict(tool_conf)
        
        # Setup audit log
        if self._global_config.audit_log:
            self._setup_audit_log()
        
        logger.info(f"Tool registry configured with {len(self._tool_configs)} tool configs")
    
    def _setup_audit_log(self) -> None:
        """Setup audit log file."""
        log_path = Path(self._global_config.audit_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._audit_log_file = log_path
    
    def register(self, tool: Tool) -> None:
        """
        Register a tool instance.
        
        Args:
            tool: Tool instance to register
        
        Raises:
            ValueError: If tool name already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            tool_name: Name of tool to unregister
        
        Returns:
            True if tool was unregistered
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")
            return True
        return False
    
    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a registered tool by name.
        
        Args:
            tool_name: Tool name
        
        Returns:
            Tool instance or None
        """
        return self._tools.get(tool_name)
    
    def get_tool_config(self, tool_name: str) -> ToolConfig:
        """
        Get configuration for a tool.
        
        Args:
            tool_name: Tool name
        
        Returns:
            ToolConfig (empty default if not found)
        """
        return self._tool_configs.get(tool_name, ToolConfig())
    
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all registered tools.
        
        Returns:
            Dictionary of tool name -> {description, parameters_schema, enabled}
        """
        info = {}
        for name, tool in self._tools.items():
            config = self.get_tool_config(name)
            info[name] = {
                'description': tool.description,
                'parameters_schema': tool.parameters_schema,
                'enabled': config.enabled,
                'config': config.config
            }
        return info
    
    def is_enabled(self, tool_name: str) -> bool:
        """
        Check if a tool is enabled.
        
        Args:
            tool_name: Tool name
        
        Returns:
            True if tool is enabled and registered
        """
        if tool_name not in self._tools:
            return False
        
        config = self.get_tool_config(tool_name)
        return config.enabled and self._global_config.enabled
    
    def set_confirmation_callback(self, callback: Callable[[str, Dict], bool]) -> None:
        """
        Set callback for user confirmation of tool executions.
        
        Args:
            callback: Function(tool_name, params) -> bool (True to allow)
        """
        self._confirmation_callback = callback
    
    def execute(self, tool_name: str, params: Dict[str, Any],
                task_id: Optional[str] = None,
                step_id: Optional[str] = None) -> ToolResult:
        """
        Execute a tool with security checks and logging.
        
        Args:
            tool_name: Name of tool to execute
            params: Parameters for the tool
            task_id: Optional task ID for tracking
            step_id: Optional step ID for tracking
        
        Returns:
            ToolResult with execution result
        
        Note: This method never raises exceptions; all errors
              are returned in ToolResult.
        """
        start_time = time.time()
        
        # Check if tools are globally enabled
        if not self._global_config.enabled:
            return ToolResult.denied_result("Tools are globally disabled")
        
        # Check if tool is registered
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult.failure_result(
                f"Tool not found: {tool_name}",
                ToolStatus.FAILED
            )
        
        # Check if tool is enabled
        if not self.is_enabled(tool_name):
            return ToolResult.denied_result(f"Tool is disabled: {tool_name}")
        
        # Validate parameters
        validation_error = tool.validate_params(params)
        if validation_error:
            return ToolResult.failure_result(
                f"Invalid parameters: {validation_error}",
                ToolStatus.FAILED
            )
        
        # Preflight check (T2: tool_doctor/preflight integration)
        preflight_result = self._run_preflight(tool_name, params)
        if preflight_result:
            return preflight_result  # Blocked by preflight
        
        # Check for confirmation if required
        if self._global_config.require_confirmation and self._confirmation_callback:
            try:
                if not self._confirmation_callback(tool_name, params):
                    return ToolResult.denied_result("User denied execution")
            except Exception as e:
                logger.error(f"Confirmation callback error: {e}")
                return ToolResult.denied_result(f"Confirmation error: {e}")
        
        # Execute with retry logic
        result = self._execute_with_retry(tool, params)
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        result.execution_time_ms = execution_time_ms
        
        # Create execution record
        execution = ToolExecution.create(
            tool_name=tool_name,
            params=params,
            result=result,
            task_id=task_id,
            step_id=step_id
        )
        
        # Log execution
        self._log_execution(execution)
        
        return result
    
    def _run_preflight(self, tool_name: str, params: Dict[str, Any]) -> Optional[ToolResult]:
        """
        Run preflight checks before tool execution.
        
        T2: tool_doctor/preflight integration at tool_registry level.
        This ensures all tool executions go through safety/validation checks.
        
        Args:
            tool_name: Name of the tool
            params: Tool parameters
        
        Returns:
            ToolResult if blocked, None if preflight passes
        """
        try:
            from app.runtime.tool_doctor import run_preflight
            
            # Run preflight check
            result = run_preflight(tool_name, params)
            
            # If preflight failed, convert to ToolResult
            if not result.success:
                return ToolResult.denied_result(
                    result.user_safe_message or result.summary
                )
            
            return None  # Preflight passed
            
        except ImportError:
            # tool_doctor not available, skip preflight
            logger.debug("tool_doctor not available, skipping preflight")
            return None
        except Exception as e:
            # Log error but don't block execution on preflight errors
            logger.warning(f"Preflight check error: {e}")
            return None
    
    def _execute_with_retry(self, tool: Tool, params: Dict[str, Any]) -> ToolResult:
        """
        Execute tool with retry logic.
        
        Args:
            tool: Tool instance
            params: Parameters
        
        Returns:
            ToolResult
        """
        max_attempts = self._global_config.max_retries + 1 if self._global_config.retry_on_failure else 1
        last_result = None
        
        for attempt in range(max_attempts):
            try:
                result = tool.execute(params)
                
                # Return immediately if success or non-retryable status
                if result.success or result.status in (ToolStatus.DENIED, ToolStatus.TIMEOUT):
                    return result
                
                last_result = result
                
                # Wait before retry
                if attempt < max_attempts - 1:
                    time.sleep(self._global_config.retry_delay)
                    logger.warning(f"Retrying tool {tool.name} (attempt {attempt + 2}/{max_attempts})")
                
            except ToolSecurityError as e:
                return ToolResult.denied_result(str(e))
            except ToolTimeoutError as e:
                return ToolResult.timeout_result(str(e))
            except ToolError as e:
                last_result = ToolResult.failure_result(str(e))
            except Exception as e:
                # Catch-all for unexpected errors - never crash
                logger.exception(f"Unexpected error in tool {tool.name}")
                last_result = ToolResult.failure_result(f"Internal error: {e}")
        
        # Return last result after all retries failed
        return last_result or ToolResult.failure_result("Unknown error after retries")
    
    def _log_execution(self, execution: ToolExecution) -> None:
        """
        Log a tool execution.
        
        Args:
            execution: Execution record
        """
        # Add to in-memory history
        with self._lock:
            self._execution_history.append(execution)
            # Trim history if too large
            if len(self._execution_history) > self._max_history_size:
                self._execution_history = self._execution_history[-self._max_history_size:]
        
        # Log to logger
        if self._global_config.log_executions:
            status = "SUCCESS" if execution.result.success else "FAILED"
            logger.info(
                f"Tool execution: {execution.tool_name} -> {status} "
                f"({execution.result.execution_time_ms:.1f}ms)"
            )
        
        # Write to audit log
        if self._global_config.audit_log and self._audit_log_file:
            self._write_audit_log(execution)
    
    def _write_audit_log(self, execution: ToolExecution) -> None:
        """
        Write execution to audit log file.
        
        Args:
            execution: Execution record
        """
        try:
            log_entry = json.dumps(execution.to_dict(), ensure_ascii=False)
            
            with open(self._audit_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_execution_history(self, limit: int = 100,
                               tool_name: Optional[str] = None,
                               task_id: Optional[str] = None) -> List[ToolExecution]:
        """
        Get recent execution history.
        
        Args:
            limit: Maximum number of records to return
            tool_name: Filter by tool name (optional)
            task_id: Filter by task ID (optional)
        
        Returns:
            List of execution records
        """
        with self._lock:
            history = list(self._execution_history)
        
        # Filter
        if tool_name:
            history = [e for e in history if e.tool_name == tool_name]
        if task_id:
            history = [e for e in history if e.task_id == task_id]
        
        # Return most recent
        return history[-limit:]
    
    def clear_history(self) -> None:
        """Clear execution history."""
        with self._lock:
            self._execution_history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tool usage.
        
        Returns:
            Dictionary with stats
        """
        with self._lock:
            history = list(self._execution_history)
        
        if not history:
            return {
                'total_executions': 0,
                'successful': 0,
                'failed': 0,
                'by_tool': {}
            }
        
        stats = {
            'total_executions': len(history),
            'successful': sum(1 for e in history if e.result.success),
            'failed': sum(1 for e in history if not e.result.success),
            'by_tool': {}
        }
        
        # Count by tool
        for execution in history:
            tool_name = execution.tool_name
            if tool_name not in stats['by_tool']:
                stats['by_tool'][tool_name] = {
                    'count': 0,
                    'success': 0,
                    'failed': 0
                }
            stats['by_tool'][tool_name]['count'] += 1
            if execution.result.success:
                stats['by_tool'][tool_name]['success'] += 1
            else:
                stats['by_tool'][tool_name]['failed'] += 1
        
        return stats


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """
    Get the global tool registry.
    
    Returns:
        ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def init_registry(config: Dict[str, Any]) -> ToolRegistry:
    """
    Initialize the global tool registry with configuration.
    
    Args:
        config: Tool configuration dictionary
    
    Returns:
        Initialized ToolRegistry
    """
    global _registry
    _registry = ToolRegistry(config)
    return _registry


def register_tool(tool: Tool) -> None:
    """
    Register a tool with the global registry.
    
    Args:
        tool: Tool instance to register
    """
    get_registry().register(tool)


def execute_tool(tool_name: str, params: Dict[str, Any],
                 task_id: Optional[str] = None,
                 step_id: Optional[str] = None) -> ToolResult:
    """
    Execute a tool using the global registry.
    
    Args:
        tool_name: Name of tool to execute
        params: Parameters for the tool
        task_id: Optional task ID
        step_id: Optional step ID
    
    Returns:
        ToolResult
    """
    return get_registry().execute(tool_name, params, task_id, step_id)
