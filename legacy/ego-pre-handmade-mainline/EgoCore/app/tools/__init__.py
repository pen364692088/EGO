"""
OpenEmotion Agent Runtime - Tools Package

This package provides the tool system for the agent runtime.

Tools are the execution primitives that the agent uses to
interact with the environment (files, shell, code, etc.).

Usage:
    from app.tools import ToolRegistry, FileTool, ShellTool, PythonTool
    from app.tools import init_registry, register_tool, execute_tool
    
    # Initialize registry with config
    init_registry(config)
    
    # Register tools
    register_tool(FileTool(config))
    register_tool(ShellTool(config))
    register_tool(PythonTool(config))
    
    # Execute a tool
    result = execute_tool('file', {'operation': 'read', 'path': './data/test.txt'})
"""

# Base classes and interfaces
from app.tools.base import (
    Tool,
    ToolResult,
    ToolExecution,
    ToolStatus,
    ToolError,
    ToolSecurityError,
    ToolTimeoutError,
    ToolValidationError,
)

# Tool registry
from app.tools.tool_registry import (
    ToolRegistry,
    ToolConfig,
    GlobalToolConfig,
    get_registry,
    init_registry,
    register_tool,
    execute_tool,
)

# Individual tools
from app.tools.file_tool import FileTool, create_file_tool
from app.tools.shell_tool import ShellTool, create_shell_tool
from app.tools.python_tool import PythonTool, create_python_tool


__all__ = [
    # Base classes
    'Tool',
    'ToolResult',
    'ToolExecution',
    'ToolStatus',
    'ToolError',
    'ToolSecurityError',
    'ToolTimeoutError',
    'ToolValidationError',
    
    # Registry
    'ToolRegistry',
    'ToolConfig',
    'GlobalToolConfig',
    'get_registry',
    'init_registry',
    'register_tool',
    'execute_tool',
    
    # Tools
    'FileTool',
    'ShellTool',
    'PythonTool',
    'create_file_tool',
    'create_shell_tool',
    'create_python_tool',
]


def setup_tools(config: dict) -> ToolRegistry:
    """
    Setup the tool system with all default tools.
    
    This is a convenience function that initializes the registry
    and registers all built-in tools.
    
    Args:
        config: Tool configuration from tools.yaml
    
    Returns:
        Initialized ToolRegistry with all tools registered
    """
    # Initialize registry
    registry = init_registry(config)
    
    # Get tool configs
    tools_config = config.get('tools', {})
    
    # Register file tool
    file_config = tools_config.get('file', {}).get('config', {})
    registry.register(create_file_tool(file_config))
    
    # Register shell tool
    shell_config = tools_config.get('shell', {}).get('config', {})
    registry.register(create_shell_tool(shell_config))
    
    # Register python tool
    python_config = tools_config.get('python', {}).get('config', {})
    registry.register(create_python_tool(python_config))
    
    return registry
