"""
OpenEmotion Agent Runtime - Memory Types

Memory type definitions and base classes.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from pathlib import Path


class MemoryType(str, Enum):
    """Memory type enumeration."""
    PROFILE = "profile"       # User preferences, default rules
    PROJECT = "project"       # Project background, structure
    TASK = "task"            # Task goals, progress, next steps
    INTERACTION = "interaction"  # Recent interactions, decisions


class MemoryEntry(BaseModel):
    """Base memory entry model."""
    id: str = Field(..., description="Unique memory entry ID")
    type: MemoryType = Field(..., description="Memory type")
    key: str = Field(..., description="Memory key for retrieval")
    content: str = Field(..., description="Memory content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    class Config:
        use_enum_values = True


class MemoryQuery(BaseModel):
    """Memory query model."""
    type: Optional[MemoryType] = Field(None, description="Filter by memory type")
    key_pattern: Optional[str] = Field(None, description="Key pattern to match")
    limit: int = Field(10, description="Maximum results to return")


class MemorySummary(BaseModel):
    """Memory summary for a specific context."""
    profile_summary: Optional[str] = None
    project_summary: Optional[str] = None
    task_summary: Optional[str] = None
    recent_interactions: list[str] = Field(default_factory=list)
