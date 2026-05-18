"""
OpenEmotion Agent Runtime - Database Connection

Provides SQLite database connection and initialization.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import threading


class Database:
    """
    SQLite database connection manager.
    
    Thread-safe connection handling with connection pooling.
    """
    
    _instances: dict = {}  # Map from db_path to instance
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Optional[Path] = None):
        """Singleton per database path."""
        # Normalize path
        if db_path is None:
            db_path = Path.home() / ".openemotion" / "data" / "tasks.db"
        db_path = Path(db_path).resolve()
        
        with cls._lock:
            if db_path not in cls._instances:
                instance = super().__new__(cls)
                instance._db_path = db_path
                instance._initialized = False
                cls._instances[db_path] = instance
            return cls._instances[db_path]
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        if self._initialized:
            return
        
        self.db_path = self._db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        self._initialized = True
        
        # Initialize schema
        self._init_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.connection = conn
        return self._local.connection
    
    @contextmanager
    def connection(self):
        """Context manager for database connection."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
    
    @contextmanager
    def cursor(self):
        """Context manager for database cursor."""
        with self.connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def _init_schema(self):
        """Initialize database schema with migrations."""
        with self.cursor() as cur:
            # Tasks table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'created',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    current_step_index INTEGER DEFAULT 0,
                    error TEXT,
                    metadata TEXT
                )
            """)
            
            # Migration: Add scope columns if they don't exist
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN chat_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN user_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cur.execute("ALTER TABLE tasks ADD COLUMN scope_key TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Task steps table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_steps (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    step_order INTEGER DEFAULT 0,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status 
                ON tasks(status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_steps_task_id 
                ON task_steps(task_id)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_steps_status 
                ON task_steps(status)
            """)
            # New index for scope-based queries
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_scope_key 
                ON tasks(scope_key)
            """)
    
    def close(self):
        """Close database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
    
    @classmethod
    def get_instance(cls, db_path: Optional[Path] = None) -> 'Database':
        """Get singleton database instance for a path."""
        return cls(db_path)


def get_db(db_path: Optional[Path] = None) -> Database:
    """Get database instance."""
    return Database.get_instance(db_path)
