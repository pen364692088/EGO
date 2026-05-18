"""
OpenEmotion Agent Runtime - Project Memory

Handles OpenEmotion project background, structure, and long-term knowledge.
This provides context about the current project being worked on.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from app.memory.memory_manager import (
    MemoryManager, MemoryEntry, MemoryType, get_memory_manager
)


class ProjectMemory:
    """
    Handler for project memory.
    
    Project memory contains:
    - Project name and description
    - Project structure (directory layout, key files)
    - Coding conventions specific to project
    - Long-term knowledge about the project
    - Technical stack and dependencies
    
    These memories have:
    - Medium TTL (90 days)
    - Medium injection priority
    - Stored in JSON file for durability
    """
    
    # Standard project memory keys
    PROJECT_INFO = "project_info"
    PROJECT_STRUCTURE = "project_structure"
    PROJECT_CONVENTIONS = "project_conventions"
    PROJECT_STACK = "project_stack"
    PROJECT_DEPENDENCIES = "project_dependencies"
    
    def __init__(self, manager: Optional[MemoryManager] = None):
        """
        Initialize project memory handler.
        
        Args:
            manager: Memory manager instance
        """
        self._manager = manager or get_memory_manager()
    
    def save_project_context(self, 
                            project_name: str,
                            description: str,
                            structure: Optional[str] = None,
                            conventions: Optional[List[str]] = None,
                            tech_stack: Optional[List[str]] = None,
                            dependencies: Optional[Dict[str, str]] = None) -> MemoryEntry:
        """
        Save project context memory.
        
        Args:
            project_name: Project name
            description: Project description
            structure: Project structure summary
            conventions: List of coding conventions
            tech_stack: List of technologies used
            dependencies: Dict of dependencies and versions
        
        Returns:
            Created/updated memory entry
        """
        # Check if project info already exists
        existing = self.get_project_context(project_name)
        
        metadata = {
            'structure': structure,
            'conventions': conventions or [],
            'tech_stack': tech_stack or [],
            'dependencies': dependencies or {}
        }
        
        if existing:
            # Update existing entry
            existing.content = description
            existing.updated_at = datetime.now()
            existing.metadata.update(metadata)
            return self._manager.save(existing)
        else:
            # Create new entry
            entry = MemoryEntry.create(
                memory_type=MemoryType.PROJECT,
                key=f"project:{project_name}",
                content=description,
                metadata=metadata
            )
            return self._manager.save(entry)
    
    def get_project_context(self, project_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Get project context memory.
        
        Args:
            project_name: Specific project name (uses latest if not provided)
        
        Returns:
            Project memory entry if found
        """
        if project_name:
            entries = self._manager.search(f"project:{project_name}", MemoryType.PROJECT, limit=1)
            return entries[0] if entries else None
        else:
            # Get latest project memory
            entries = self._manager.list_by_type(MemoryType.PROJECT, limit=1)
            return entries[0] if entries else None
    
    def update_structure(self, structure: str, 
                        project_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Update project structure information.
        
        Args:
            structure: Project structure string
            project_name: Project name (uses latest if not provided)
        
        Returns:
            Updated memory entry
        """
        project = self.get_project_context(project_name)
        
        if project:
            project.metadata['structure'] = structure
            project.updated_at = datetime.now()
            return self._manager.save(project)
        
        return None
    
    def add_convention(self, convention: str,
                      project_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Add a coding convention to the project.
        
        Args:
            convention: Convention description
            project_name: Project name (uses latest if not provided)
        
        Returns:
            Updated memory entry
        """
        project = self.get_project_context(project_name)
        
        if project:
            conventions = project.metadata.get('conventions', [])
            if convention not in conventions:
                conventions.append(convention)
                project.metadata['conventions'] = conventions
                project.updated_at = datetime.now()
                return self._manager.save(project)
        
        return None
    
    def update_tech_stack(self, tech_stack: List[str],
                         project_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Update project tech stack.
        
        Args:
            tech_stack: List of technologies
            project_name: Project name (uses latest if not provided)
        
        Returns:
            Updated memory entry
        """
        project = self.get_project_context(project_name)
        
        if project:
            project.metadata['tech_stack'] = tech_stack
            project.updated_at = datetime.now()
            return self._manager.save(project)
        
        return None
    
    def add_dependency(self, name: str, version: str,
                      project_name: Optional[str] = None) -> Optional[MemoryEntry]:
        """
        Add a dependency to the project.
        
        Args:
            name: Dependency name
            version: Dependency version
            project_name: Project name (uses latest if not provided)
        
        Returns:
            Updated memory entry
        """
        project = self.get_project_context(project_name)
        
        if project:
            dependencies = project.metadata.get('dependencies', {})
            dependencies[name] = version
            project.metadata['dependencies'] = dependencies
            project.updated_at = datetime.now()
            return self._manager.save(project)
        
        return None
    
    def save_openemotion_default(self) -> MemoryEntry:
        """
        Save default OpenEmotion project context.
        
        Returns:
            Created memory entry
        """
        description = """
OpenEmotion Agent Runtime - A task-driven AI agent framework with state management.

Key Features:
- Task lifecycle management with state machine
- Memory system with four types (profile, project, task, interaction)
- Telegram bot integration
- Tool execution framework
- LLM integration

Architecture:
- app/runtime/ - Core task execution engine
- app/memory/ - Memory management system
- app/storage/ - SQLite-based persistence
- app/tools/ - Tool registry and implementations
- app/bridges/ - External service integrations
        """.strip()
        
        structure = """
app/
├── __init__.py
├── main.py              # Entry point
├── config.py            # Configuration loader
├── logger.py            # Logging setup
├── telegram_bot.py      # Telegram integration
├── command_router.py    # Command routing
├── memory/
│   ├── memory_manager.py    # Central memory coordinator
│   ├── profile_memory.py    # User preferences
│   ├── project_memory.py    # Project context
│   ├── task_memory.py       # Task state
│   └── interaction_memory.py # Recent interactions
├── runtime/
│   ├── state_machine.py     # Task state machine
│   ├── planner.py           # Task planning
│   └── task_runtime.py      # Execution engine
├── storage/
│   ├── db.py            # SQLite connection
│   ├── models.py        # Data models
│   └── repositories.py  # Data access layer
├── tools/
│   ├── base.py          # Tool base class
│   ├── tool_registry.py # Tool registry
│   ├── file_tool.py     # File operations
│   ├── shell_tool.py    # Shell commands
│   └── python_tool.py   # Python execution
└── bridges/             # External integrations
        """.strip()
        
        conventions = [
            "Use dataclasses for data models",
            "Repository pattern for data access",
            "State machine for task lifecycle",
            "Factory methods for object creation",
            "Type hints for all functions",
            "Docstrings for all public APIs"
        ]
        
        tech_stack = [
            "Python 3.10+",
            "SQLite for persistence",
            "python-telegram-bot for Telegram",
            "PyYAML for configuration"
        ]
        
        return self.save_project_context(
            project_name="OpenEmotion",
            description=description,
            structure=structure,
            conventions=conventions,
            tech_stack=tech_stack
        )
    
    def build_context_string(self, project_name: Optional[str] = None) -> str:
        """
        Build context string for injection.
        
        Args:
            project_name: Specific project name
        
        Returns:
            Formatted string of project context
        """
        project = self.get_project_context(project_name)
        
        if not project:
            return ""
        
        lines = ["## Project Context"]
        
        # Extract project name from key
        project_name = project.key.replace("project:", "")
        lines.append(f"**Project:** {project_name}")
        lines.append("")
        lines.append(project.content)
        
        # Add structure if available
        if project.metadata.get('structure'):
            lines.append("")
            lines.append("### Structure")
            lines.append(project.metadata['structure'])
        
        # Add conventions if available
        if project.metadata.get('conventions'):
            lines.append("")
            lines.append("### Conventions")
            for conv in project.metadata['conventions']:
                lines.append(f"- {conv}")
        
        # Add tech stack if available
        if project.metadata.get('tech_stack'):
            lines.append("")
            lines.append("### Tech Stack")
            for tech in project.metadata['tech_stack']:
                lines.append(f"- {tech}")
        
        return "\n".join(lines)


def get_project_handler() -> ProjectMemory:
    """Get project memory handler instance."""
    return ProjectMemory()
