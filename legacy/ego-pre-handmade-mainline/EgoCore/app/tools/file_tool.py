"""
OpenEmotion Agent Runtime - File Tool

File read/write operations with security controls.
"""

import logging
import os
import shutil
import re
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional, Set

from app.tools.base import (
    Tool, ToolResult, ToolStatus, ToolSecurityError, ToolValidationError
)


logger = logging.getLogger(__name__)

WINDOWS_ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_policy_path(path_str: str) -> str:
    if WINDOWS_ABS_PATH_RE.match(path_str or ""):
        return str(PureWindowsPath(path_str)).replace("/", "\\").lower().rstrip("\\")
    return str(Path(path_str).resolve())


def _is_within_path(candidate: str, allowed: str) -> bool:
    if candidate == allowed:
        return True
    if WINDOWS_ABS_PATH_RE.match(candidate):
        return candidate.startswith(allowed + "\\")
    return candidate.startswith(allowed.rstrip("/") + "/")


class FileTool(Tool):
    """
    Tool for file system operations.
    
    Supported operations:
    - read: Read file contents
    - write: Write content to file
    - list: List directory contents
    - exists: Check if file/directory exists
    - mkdir: Create directory
    - delete: Delete file (with restrictions)
    
    Security controls:
    - Path whitelist/blacklist
    - File extension restrictions
    - Max file size limits
    - Read-only mode option
    """
    
    # Dangerous paths that should never be accessed (exact match only, not prefix)
    # Note: removed /home to allow user project directories
    FORBIDDEN_PATHS: Set[str] = {
        '/etc', '/root', '/var', '/usr', '/bin', '/sbin',
        '.env', '.git', '.ssh', '.gnupg'
    }
    
    # Dangerous file extensions
    FORBIDDEN_EXTENSIONS: Set[str] = {
        '.env', '.pem', '.key', '.ssh', '.gnupg'
    }
    
    # P2-A.2: Allow user project directories by default
    # These paths are always allowed in addition to config
    DEFAULT_ALLOWED_PATH_PREFIXES: Set[str] = {
        '/home/',  # User home directories
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize file tool.
        
        Args:
            config: Tool configuration from tools.yaml
        """
        self.config = config or {}
        
        # Allowed paths (whitelist)
        self.allowed_paths: List[str] = self.config.get('allowed_paths', ['./data', './workspace'])
        
        # Denied paths (blacklist)
        self.denied_paths: List[str] = self.config.get('denied_paths', ['.env', '.git'])
        
        # Allowed file extensions
        self.allowed_extensions: Set[str] = set(
            self.config.get('allowed_extensions', 
                           ['.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.html', '.css'])
        )
        
        # Max file size in MB
        self.max_file_size_mb: int = self.config.get('max_file_size_mb', 10)
        
        # Read-only mode
        self.read_only_mode: bool = self.config.get('read_only_mode', False)
    
    @property
    def name(self) -> str:
        return "file"
    
    @property
    def description(self) -> str:
        return "Read, write, and manage files within allowed directories"
    
    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "list", "exists", "mkdir", "delete"],
                    "description": "Operation to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write operation)"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding"
                }
            },
            "required": ["operation", "path"]
        }
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate parameters."""
        operation = params.get('operation')
        if not operation:
            return "Missing required parameter: operation"
        
        valid_operations = {"read", "write", "list", "exists", "mkdir", "delete"}
        if operation not in valid_operations:
            return f"Invalid operation: {operation}. Valid: {valid_operations}"
        
        path = params.get('path')
        if not path:
            return "Missing required parameter: path"
        
        if operation == "write":
            if self.read_only_mode:
                return "Write operations disabled in read-only mode"
            if 'content' not in params:
                return "Missing required parameter: content for write operation"
        
        return None
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute file operation with preflight check."""
        # P2-A.1: Preflight check via tool_doctor (统一前置检查)
        from app.runtime.tool_doctor import run_preflight
        preflight_result = run_preflight("file", params)
        if not preflight_result.success:
            # Preflight blocked - return the blocked result
            return ToolResult.denied_result(
                preflight_result.user_safe_message or "Blocked by preflight"
            )
        
        operation = params['operation']
        path_str = params['path']
        
        try:
            path = self._resolve_and_validate_path(path_str, for_write=(operation in ['write', 'mkdir', 'delete']))
        except ToolSecurityError as e:
            return ToolResult.denied_result(str(e))
        
        # Route to operation handler
        handlers = {
            'read': self._read,
            'write': self._write,
            'list': self._list,
            'exists': self._exists,
            'mkdir': self._mkdir,
            'delete': self._delete
        }
        
        handler = handlers.get(operation)
        if handler:
            return handler(path, params)
        
        return ToolResult.failure_result(f"Unknown operation: {operation}")
    
    def _resolve_and_validate_path(self, path_str: str, for_write: bool = False) -> Path:
        """
        Resolve and validate a path.
        
        Args:
            path_str: Path string
            for_write: Whether this is for a write operation
        
        Returns:
            Resolved Path object
        
        Raises:
            ToolSecurityError: If path is not allowed
        """
        # Resolve to absolute path / canonical policy form
        is_windows_abs = WINDOWS_ABS_PATH_RE.match(path_str or "") is not None
        path = Path(path_str).resolve() if not is_windows_abs else Path(str(PureWindowsPath(path_str)))
        path_str_resolved = _normalize_policy_path(path_str)
        
        # Check forbidden paths (exact match for system dirs, prefix for hidden dirs)
        for forbidden in self.FORBIDDEN_PATHS:
            if forbidden.startswith('/'):
                # System paths: exact match only (don't block subdirectories)
                if path_str_resolved == _normalize_policy_path(forbidden):
                    raise ToolSecurityError(f"Access to path forbidden: {path_str}")
            else:
                # Hidden dirs (like .env, .git): prefix match
                forbidden_norm = forbidden.lower()
                if path_str_resolved.startswith(forbidden_norm) or path_str_resolved == forbidden_norm:
                    raise ToolSecurityError(f"Access to path forbidden: {path_str}")
        
        # Check denied paths from config
        for denied in self.denied_paths:
            denied_resolved = _normalize_policy_path(denied)
            if _is_within_path(path_str_resolved, denied_resolved):
                raise ToolSecurityError(f"Access to path denied by config: {path_str}")
        
        # Check if path is in allowed paths
        in_allowed = False
        
        # P2-A.2: Check default allowed path prefixes (user project directories)
        for allowed_prefix in self.DEFAULT_ALLOWED_PATH_PREFIXES:
            if _is_within_path(path_str_resolved, _normalize_policy_path(allowed_prefix)):
                in_allowed = True
                break
        
        # Check config allowed paths
        if not in_allowed:
            for allowed in self.allowed_paths:
                allowed_resolved = _normalize_policy_path(allowed)
                if _is_within_path(path_str_resolved, allowed_resolved):
                    in_allowed = True
                    break
        
        if not in_allowed:
            raise ToolSecurityError(f"Path not in allowed directories: {path_str}")
        
        # Check file extension for read/write
        if path.suffix:
            if path.suffix.lower() in self.FORBIDDEN_EXTENSIONS:
                raise ToolSecurityError(f"File extension forbidden: {path.suffix}")
            
            if self.allowed_extensions and path.suffix.lower() not in self.allowed_extensions:
                raise ToolSecurityError(f"File extension not allowed: {path.suffix}")
        
        return path
    
    def _read(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """Read file contents."""
        if not path.exists():
            return ToolResult.failure_result(f"File not found: {path}", ToolStatus.FAILED)
        
        if not path.is_file():
            return ToolResult.failure_result(f"Not a file: {path}", ToolStatus.FAILED)
        
        # Check file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            return ToolResult.failure_result(
                f"File too large: {file_size_mb:.1f}MB (max: {self.max_file_size_mb}MB)",
                ToolStatus.FAILED
            )
        
        # Read file
        encoding = params.get('encoding', 'utf-8')
        try:
            content = path.read_text(encoding=encoding)
            return ToolResult.success_result(
                content,
                metadata={
                    'path': str(path),
                    'size_bytes': path.stat().st_size,
                    'encoding': encoding
                }
            )
        except UnicodeDecodeError as e:
            return ToolResult.failure_result(f"Failed to decode file: {e}", ToolStatus.FAILED)
        except Exception as e:
            return ToolResult.failure_result(f"Failed to read file: {e}", ToolStatus.FAILED)
    
    def _write(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """Write content to file."""
        content = params.get('content', '')
        encoding = params.get('encoding', 'utf-8')
        
        # Check content size
        content_size_mb = len(content.encode(encoding)) / (1024 * 1024)
        if content_size_mb > self.max_file_size_mb:
            return ToolResult.failure_result(
                f"Content too large: {content_size_mb:.1f}MB (max: {self.max_file_size_mb}MB)",
                ToolStatus.FAILED
            )
        
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            path.write_text(content, encoding=encoding)
            
            return ToolResult.success_result(
                f"Successfully wrote {len(content)} characters to {path}",
                metadata={
                    'path': str(path),
                    'size_bytes': len(content.encode(encoding)),
                    'encoding': encoding
                }
            )
        except Exception as e:
            return ToolResult.failure_result(f"Failed to write file: {e}", ToolStatus.FAILED)
    
    def _list(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """List directory contents."""
        if not path.exists():
            return ToolResult.failure_result(f"Directory not found: {path}", ToolStatus.FAILED)
        
        if not path.is_dir():
            return ToolResult.failure_result(f"Not a directory: {path}", ToolStatus.FAILED)
        
        try:
            items = []
            for item in path.iterdir():
                item_type = "directory" if item.is_dir() else "file"
                size = item.stat().st_size if item.is_file() else None
                items.append({
                    'name': item.name,
                    'type': item_type,
                    'size': size
                })
            
            # Sort by name
            items.sort(key=lambda x: x['name'])
            
            # Format output
            lines = [f"Contents of {path}:"]
            for item in items:
                if item['type'] == 'directory':
                    lines.append(f"  📁 {item['name']}/")
                else:
                    size_str = f" ({item['size']} bytes)" if item['size'] is not None else ""
                    lines.append(f"  📄 {item['name']}{size_str}")
            
            return ToolResult.success_result(
                '\n'.join(lines),
                metadata={
                    'path': str(path),
                    'items': items,
                    'count': len(items)
                }
            )
        except Exception as e:
            return ToolResult.failure_result(f"Failed to list directory: {e}", ToolStatus.FAILED)
    
    def _exists(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """Check if file/directory exists."""
        exists = path.exists()
        item_type = None
        if exists:
            item_type = "directory" if path.is_dir() else "file"
        
        return ToolResult.success_result(
            f"{'Exists' if exists else 'Does not exist'}: {path}" + 
            (f" ({item_type})" if item_type else ""),
            metadata={
                'path': str(path),
                'exists': exists,
                'type': item_type
            }
        )
    
    def _mkdir(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """Create directory."""
        if path.exists():
            return ToolResult.failure_result(f"Path already exists: {path}", ToolStatus.FAILED)
        
        try:
            path.mkdir(parents=True, exist_ok=False)
            return ToolResult.success_result(
                f"Created directory: {path}",
                metadata={'path': str(path)}
            )
        except Exception as e:
            return ToolResult.failure_result(f"Failed to create directory: {e}", ToolStatus.FAILED)
    
    def _delete(self, path: Path, params: Dict[str, Any]) -> ToolResult:
        """Delete file (restricted)."""
        if not path.exists():
            return ToolResult.failure_result(f"Path not found: {path}", ToolStatus.FAILED)
        
        # Safety: only allow deleting files, not directories
        if path.is_dir():
            return ToolResult.denied_result(
                "Deleting directories is not allowed. Use individual file deletion."
            )
        
        try:
            path.unlink()
            return ToolResult.success_result(
                f"Deleted file: {path}",
                metadata={'path': str(path)}
            )
        except Exception as e:
            return ToolResult.failure_result(f"Failed to delete file: {e}", ToolStatus.FAILED)


def create_file_tool(config: Optional[Dict[str, Any]] = None) -> FileTool:
    """
    Create and return a configured FileTool instance.
    
    Args:
        config: Tool configuration
    
    Returns:
        FileTool instance
    """
    return FileTool(config)
