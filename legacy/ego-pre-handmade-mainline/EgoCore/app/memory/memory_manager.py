"""
OpenEmotion Agent Runtime - Memory Manager

Central memory management for all memory types.
Handles storage, retrieval, and persistence.
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from app.memory.types import MemoryEntry, MemoryType, MemoryQuery, MemorySummary
from app.config import get_config


class MemoryManager:
    """
    Central memory manager for OpenEmotion Agent Runtime.
    
    Manages four types of memory:
    - Profile: User preferences, default rules
    - Project: Project background, structure
    - Task: Task goals, progress, next steps (most important)
    - Interaction: Recent interactions, key decisions
    
    Storage:
    - SQLite index for fast queries
    - JSON files for content persistence
    """
    
    def __init__(self, db_path: Optional[Path] = None, memory_dir: Optional[Path] = None):
        """
        Initialize memory manager.
        
        Args:
            db_path: Path to SQLite database
            memory_dir: Directory for memory JSON files
        """
        config = None
        if db_path is None or memory_dir is None:
            config = get_config()
        self.db_path = db_path or config.get_path('data_dir') / 'memory.db'
        self.memory_dir = memory_dir or config.get_path('memory_dir')
        
        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize memory database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content_file TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(key)
            ''')
            conn.commit()
    
    def _get_content_path(self, entry_id: str) -> Path:
        """Get path for memory content file."""
        return self.memory_dir / f"{entry_id}.json"
    
    def write(self, entry: MemoryEntry) -> str:
        """
        Write a memory entry.
        
        Args:
            entry: Memory entry to write
        
        Returns:
            Entry ID
        """
        # Generate ID if not provided
        if not entry.id:
            entry.id = str(uuid.uuid4())
        
        # Update timestamp
        entry.updated_at = datetime.now()
        
        # Write content to JSON file
        content_path = self._get_content_path(entry.id)
        with open(content_path, 'w', encoding='utf-8') as f:
            # Convert datetime to ISO format string for JSON serialization
            data = entry.model_dump()
            data['created_at'] = entry.created_at.isoformat()
            data['updated_at'] = entry.updated_at.isoformat()
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Write index to database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO memory 
                (id, type, key, content_file, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.id,
                entry.type,
                entry.key,
                str(content_path),
                json.dumps(entry.metadata),
                entry.created_at.isoformat(),
                entry.updated_at.isoformat()
            ))
            conn.commit()
        
        return entry.id
    
    def read(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        Read a memory entry by ID.
        
        Args:
            entry_id: Entry ID
        
        Returns:
            Memory entry or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT id, type, key, content_file FROM memory WHERE id = ?',
                (entry_id,)
            )
            row = cursor.fetchone()
            
        if not row:
            return None
        
        # Read content from JSON file
        content_path = Path(row[3])
        if content_path.exists():
            with open(content_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return MemoryEntry(**data)
        
        return None
    
    def query(self, query: MemoryQuery) -> List[MemoryEntry]:
        """
        Query memory entries.
        
        Args:
            query: Query parameters
        
        Returns:
            List of matching entries
        """
        sql = 'SELECT id, type, key, content_file FROM memory WHERE 1=1'
        params = []
        
        if query.type:
            sql += ' AND type = ?'
            params.append(query.type)
        
        if query.key_pattern:
            sql += ' AND key LIKE ?'
            params.append(f'%{query.key_pattern}%')
        
        sql += f' ORDER BY updated_at DESC LIMIT {query.limit}'
        
        entries = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            for row in cursor.fetchall():
                content_path = Path(row[3])
                if content_path.exists():
                    with open(content_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        entries.append(MemoryEntry(**data))
        
        return entries
    
    def get_by_key(self, key: str, memory_type: Optional[MemoryType] = None) -> Optional[MemoryEntry]:
        """
        Get memory entry by key.
        
        Args:
            key: Memory key
            memory_type: Optional type filter
        
        Returns:
            Memory entry or None
        """
        query = MemoryQuery(key_pattern=key, limit=1)
        if memory_type:
            query.type = memory_type
        
        results = self.query(query)
        return results[0] if results else None
    
    def get_latest_task_memory(self) -> Optional[MemoryEntry]:
        """Get the most recent task memory."""
        query = MemoryQuery(type=MemoryType.TASK, limit=1)
        results = self.query(query)
        return results[0] if results else None
    
    def delete(self, entry_id: str) -> bool:
        """
        Delete a memory entry.
        
        Args:
            entry_id: Entry ID to delete
        
        Returns:
            True if deleted
        """
        # Get content file path
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT content_file FROM memory WHERE id = ?',
                (entry_id,)
            )
            row = cursor.fetchone()
            
            if row:
                content_path = Path(row[0])
                if content_path.exists():
                    content_path.unlink()
                
                conn.execute('DELETE FROM memory WHERE id = ?', (entry_id,))
                conn.commit()
                return True
        
        return False
    
    def get_summary(self) -> MemorySummary:
        """
        Get memory summary for context injection.
        
        Returns:
            MemorySummary with key information
        """
        summary = MemorySummary()
        
        # Get profile summary
        profile_entries = self.query(MemoryQuery(type=MemoryType.PROFILE, limit=5))
        if profile_entries:
            summary.profile_summary = '\n'.join([f"- {e.key}: {e.content[:200]}" for e in profile_entries])
        
        # Get project summary
        project_entries = self.query(MemoryQuery(type=MemoryType.PROJECT, limit=5))
        if project_entries:
            summary.project_summary = '\n'.join([f"- {e.key}: {e.content[:200]}" for e in project_entries])
        
        # Get latest task summary
        task_entry = self.get_latest_task_memory()
        if task_entry:
            summary.task_summary = task_entry.content[:500]
        
        # Get recent interactions
        interaction_entries = self.query(MemoryQuery(type=MemoryType.INTERACTION, limit=5))
        summary.recent_interactions = [e.content[:100] for e in interaction_entries]
        
        return summary


# Global memory manager instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
