#!/usr/bin/env python3
"""
Test script for Phase 4 - Tool System

Tests:
1. Tool registry initialization
2. File tool operations
3. Shell tool operations
4. Python tool operations
5. Tool execution logging
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import directly from submodules to avoid app/__init__.py dependencies
from app.tools.base import ToolResult, ToolStatus
from app.tools.tool_registry import ToolRegistry, init_registry, register_tool
from app.tools.file_tool import create_file_tool
from app.tools.shell_tool import create_shell_tool
from app.tools.python_tool import create_python_tool
import yaml


def load_tools_config():
    """Load tools configuration."""
    config_path = project_root / 'config' / 'tools.yaml'
    with open(config_path) as f:
        return yaml.safe_load(f)


def test_registry():
    """Test tool registry."""
    print("\n=== Testing Tool Registry ===")
    
    config = load_tools_config()
    registry = init_registry(config)
    
    # Register tools manually
    tools_config = config.get('tools', {})
    
    file_config = tools_config.get('file', {}).get('config', {})
    registry.register(create_file_tool(file_config))
    
    shell_config = tools_config.get('shell', {}).get('config', {})
    registry.register(create_shell_tool(shell_config))
    
    python_config = tools_config.get('python', {}).get('config', {})
    registry.register(create_python_tool(python_config))
    
    # List registered tools
    tools = registry.list_tools()
    print(f"Registered tools: {tools}")
    
    # Get tools info
    info = registry.get_tools_info()
    for name, tool_info in info.items():
        print(f"\n{name}:")
        print(f"  Description: {tool_info['description']}")
        print(f"  Enabled: {tool_info['enabled']}")
    
    return registry


def test_file_tool(registry: ToolRegistry):
    """Test file tool operations."""
    print("\n=== Testing File Tool ===")
    
    # Create test directory
    test_dir = Path('./data/test_tools')
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Test mkdir
    print("\n1. Testing mkdir operation...")
    result = registry.execute('file', {
        'operation': 'mkdir',
        'path': str(test_dir / 'subdir')
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test write
    print("\n2. Testing write operation...")
    test_file = test_dir / 'test.txt'
    result = registry.execute('file', {
        'operation': 'write',
        'path': str(test_file),
        'content': 'Hello, OpenEmotion!\nThis is a test file.'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test exists
    print("\n3. Testing exists operation...")
    result = registry.execute('file', {
        'operation': 'exists',
        'path': str(test_file)
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test read
    print("\n4. Testing read operation...")
    result = registry.execute('file', {
        'operation': 'read',
        'path': str(test_file)
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output[:100]}")
    
    # Test list
    print("\n5. Testing list operation...")
    result = registry.execute('file', {
        'operation': 'list',
        'path': str(test_dir)
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test delete
    print("\n6. Testing delete operation...")
    result = registry.execute('file', {
        'operation': 'delete',
        'path': str(test_file)
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")


def test_shell_tool(registry: ToolRegistry):
    """Test shell tool operations."""
    print("\n=== Testing Shell Tool ===")
    
    # Test simple command
    print("\n1. Testing 'ls' command...")
    result = registry.execute('shell', {
        'command': 'ls -la ./data'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output[:200]}")
    
    # Test echo
    print("\n2. Testing 'echo' command...")
    result = registry.execute('shell', {
        'command': 'echo "Hello from shell tool"'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test denied command
    print("\n3. Testing denied command (sudo)...")
    result = registry.execute('shell', {
        'command': 'sudo ls'
    })
    print(f"   Result: {result.success}")
    print(f"   Status: {result.status}")
    print(f"   Error: {result.error}")
    
    # Test timeout (short sleep)
    print("\n4. Testing timeout...")
    result = registry.execute('shell', {
        'command': 'sleep 2',
        'timeout': 1
    })
    print(f"   Result: {result.success}")
    print(f"   Status: {result.status}")
    print(f"   Error: {result.error}")


def test_python_tool(registry: ToolRegistry):
    """Test Python tool operations."""
    print("\n=== Testing Python Tool ===")
    
    # Test simple code
    print("\n1. Testing simple calculation...")
    result = registry.execute('python', {
        'code': 'print("Hello from Python tool!")\nresult = 2 + 2\nprint(f"2 + 2 = {result}")'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test math operations
    print("\n2. Testing math module...")
    result = registry.execute('python', {
        'code': 'import math\nprint(f"Pi = {math.pi:.6f}")\nprint(f"sqrt(16) = {math.sqrt(16)}")'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test datetime
    print("\n3. Testing datetime module...")
    result = registry.execute('python', {
        'code': 'from datetime import datetime\nprint(f"Current time: {datetime.now()}")'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output}")
    
    # Test error handling
    print("\n4. Testing error handling...")
    result = registry.execute('python', {
        'code': 'print(undefined_variable)'
    })
    print(f"   Result: {result.success}")
    print(f"   Output: {result.output[:200]}")
    
    # Test denied import
    print("\n5. Testing denied import (subprocess)...")
    result = registry.execute('python', {
        'code': 'import subprocess\nprint("Should not reach here")'
    })
    print(f"   Result: {result.success}")
    print(f"   Status: {result.status}")


def test_execution_logging(registry: ToolRegistry):
    """Test execution logging."""
    print("\n=== Testing Execution Logging ===")
    
    # Get execution history
    history = registry.get_execution_history(limit=10)
    print(f"\nRecent executions: {len(history)}")
    
    for execution in history[-5:]:
        print(f"\n  Tool: {execution.tool_name}")
        print(f"  Status: {execution.result.status.value}")
        print(f"  Success: {execution.result.success}")
        print(f"  Time: {execution.result.execution_time_ms:.2f}ms")
    
    # Get stats
    stats = registry.get_stats()
    print(f"\nTool Statistics:")
    print(f"  Total executions: {stats['total_executions']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    for tool_name, tool_stats in stats['by_tool'].items():
        print(f"  {tool_name}: {tool_stats['count']} executions")


def test_security():
    """Test security restrictions."""
    print("\n=== Testing Security ===")
    
    config = load_tools_config()
    registry = init_registry(config)
    
    # Register tools
    tools_config = config.get('tools', {})
    file_config = tools_config.get('file', {}).get('config', {})
    registry.register(create_file_tool(file_config))
    shell_config = tools_config.get('shell', {}).get('config', {})
    registry.register(create_shell_tool(shell_config))
    
    # Test path restriction
    print("\n1. Testing path restriction (trying to read /etc/passwd)...")
    result = registry.execute('file', {
        'operation': 'read',
        'path': '/etc/passwd'
    })
    print(f"   Result: {result.success}")
    print(f"   Status: {result.status}")
    print(f"   Error: {result.error}")
    
    # Test dangerous command
    print("\n2. Testing dangerous command (rm -rf /)...")
    result = registry.execute('shell', {
        'command': 'rm -rf /'
    })
    print(f"   Result: {result.success}")
    print(f"   Status: {result.status}")
    print(f"   Error: {result.error}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 4 - Tool System Test")
    print("=" * 60)
    
    try:
        # Test registry
        registry = test_registry()
        
        # Test individual tools
        test_file_tool(registry)
        test_shell_tool(registry)
        test_python_tool(registry)
        
        # Test logging
        test_execution_logging(registry)
        
        # Test security
        test_security()
        
        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during tests: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
