"""
OpenEmotion Agent Runtime - Data Repositories

Provides data access layer for tasks and task steps.
"""

import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from app.storage.db import Database, get_db
from app.storage.models import Task, TaskStep, TaskStatus, TaskStepStatus


class TaskRepository:
    """
    Repository for Task entities.
    
    Handles all database operations for tasks.
    """
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize repository.
        
        Args:
            db: Database instance (uses global if not provided)
        """
        self.db = db or get_db()
    
    def create(self, task: Task) -> Task:
        """
        Create a new task in the database.
        
        Args:
            task: Task to create
        
        Returns:
            Created task
        """
        with self.db.cursor() as cur:
            cur.execute("""
                INSERT INTO tasks (id, objective, status, created_at, updated_at,
                                   started_at, completed_at, current_step_index, error, metadata,
                                   chat_id, user_id, scope_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id,
                task.objective,
                task.status.value,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.current_step_index,
                task.error,
                json.dumps(task.metadata) if task.metadata else None,
                task.chat_id,
                task.user_id,
                task.scope_key
            ))
        
        # Create steps
        step_repo = TaskStepRepository(self.db)
        for step in task.steps:
            step_repo.create(step)
        
        return task
    
    def get(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Task if found, None otherwise
        """
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            task = self._row_to_task(row)
            
            # Load steps
            step_repo = TaskStepRepository(self.db)
            task.steps = step_repo.list_by_task(task_id)
            
            return task
    
    def update(self, task: Task) -> Task:
        """
        Update a task.
        
        Args:
            task: Task to update
        
        Returns:
            Updated task
        """
        task.updated_at = datetime.now()
        
        with self.db.cursor() as cur:
            cur.execute("""
                UPDATE tasks 
                SET objective = ?, status = ?, updated_at = ?,
                    started_at = ?, completed_at = ?, current_step_index = ?,
                    error = ?, metadata = ?
                WHERE id = ?
            """, (
                task.objective,
                task.status.value,
                task.updated_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.current_step_index,
                task.error,
                json.dumps(task.metadata) if task.metadata else None,
                task.id
            ))
        
        return task
    
    def delete(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            True if deleted, False if not found
        """
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0
    
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Task]:
        """
        List all tasks.
        
        Args:
            limit: Maximum number of tasks to return
            offset: Offset for pagination
        
        Returns:
            List of tasks
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT * FROM tasks 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            rows = cur.fetchall()
            tasks = [self._row_to_task(row) for row in rows]
            
            # Load steps for each task
            step_repo = TaskStepRepository(self.db)
            for task in tasks:
                task.steps = step_repo.list_by_task(task.id)
            
            return tasks
    
    def list_by_status(self, status: TaskStatus) -> List[Task]:
        """
        List tasks by status.
        
        Args:
            status: Task status to filter by
        
        Returns:
            List of tasks with given status
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT * FROM tasks 
                WHERE status = ? 
                ORDER BY created_at DESC
            """, (status.value,))
            
            rows = cur.fetchall()
            tasks = [self._row_to_task(row) for row in rows]
            
            # Load steps for each task
            step_repo = TaskStepRepository(self.db)
            for task in tasks:
                task.steps = step_repo.list_by_task(task.id)
            
            return tasks
    
    def get_active(self) -> Optional[Task]:
        """
        Get the currently active task (running or planning).
        
        Returns:
            Active task if exists, None otherwise
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT * FROM tasks 
                WHERE status IN ('running', 'planning') 
                ORDER BY updated_at DESC 
                LIMIT 1
            """)
            
            row = cur.fetchone()
            if not row:
                return None
            
            task = self._row_to_task(row)
            
            # Load steps
            step_repo = TaskStepRepository(self.db)
            task.steps = step_repo.list_by_task(task.id)
            
            return task
    
    def _row_to_task(self, row) -> Task:
        """Convert database row to Task object. Handles legacy tasks without scope fields."""
        return Task(
            id=row['id'],
            objective=row['objective'],
            status=TaskStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            current_step_index=row['current_step_index'],
            error=row['error'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            # Scope fields (optional for backward compatibility)
            chat_id=row['chat_id'] if 'chat_id' in row.keys() else None,
            user_id=row['user_id'] if 'user_id' in row.keys() else None,
            scope_key=row['scope_key'] if 'scope_key' in row.keys() else None
        )
    
    def get_active_for_scope(self, scope_key: str, include_legacy: bool = True) -> Optional[Task]:
        """
        Get the currently active task for a specific scope.
        
        Args:
            scope_key: Scope identifier (e.g., "tg:{chat_id}:{user_id}")
            include_legacy: If True, also check for tasks without scope (legacy data)
        
        Returns:
            Active task if exists, None otherwise
        """
        with self.db.cursor() as cur:
            # First try scoped task
            cur.execute("""
                SELECT * FROM tasks 
                WHERE scope_key = ? AND status IN ('running', 'planning') 
                ORDER BY updated_at DESC 
                LIMIT 1
            """, (scope_key,))
            
            row = cur.fetchone()
            
            # If not found and include_legacy, try legacy tasks (no scope)
            if not row and include_legacy:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE scope_key IS NULL AND status IN ('running', 'planning') 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """)
                row = cur.fetchone()
            
            if not row:
                return None
            
            task = self._row_to_task(row)
            
            # Load steps
            step_repo = TaskStepRepository(self.db)
            task.steps = step_repo.list_by_task(task.id)
            
            return task
    
    def list_recent_for_scope(self, scope_key: str, limit: int = 10, include_legacy: bool = True) -> List[Task]:
        """
        List recent tasks for a specific scope.
        
        Args:
            scope_key: Scope identifier
            limit: Maximum number of tasks to return
            include_legacy: If True, also include tasks without scope (legacy data)
        
        Returns:
            List of tasks
        """
        with self.db.cursor() as cur:
            if include_legacy:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE scope_key = ? OR scope_key IS NULL
                    ORDER BY 
                        CASE WHEN scope_key = ? THEN 0 ELSE 1 END,
                        created_at DESC 
                    LIMIT ?
                """, (scope_key, scope_key, limit))
            else:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE scope_key = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (scope_key, limit))
            
            rows = cur.fetchall()
            tasks = [self._row_to_task(row) for row in rows]
            
            # Load steps for each task
            step_repo = TaskStepRepository(self.db)
            for task in tasks:
                task.steps = step_repo.list_by_task(task.id)
            
            return tasks
    
    def get_resumable_for_scope(self, scope_key: str, include_legacy: bool = True) -> Optional[Task]:
        """
        Get the most recent resumable task for a specific scope.
        
        Resumable = paused, blocked, or incomplete (planning/running)
        
        Args:
            scope_key: Scope identifier
            include_legacy: If True, also check for tasks without scope (legacy data)
        
        Returns:
            Resumable task if exists, None otherwise
        """
        with self.db.cursor() as cur:
            # First try scoped task
            cur.execute("""
                SELECT * FROM tasks 
                WHERE scope_key = ? AND status IN ('paused', 'blocked', 'planning', 'running')
                ORDER BY updated_at DESC 
                LIMIT 1
            """, (scope_key,))
            
            row = cur.fetchone()
            
            # If not found and include_legacy, try legacy tasks
            if not row and include_legacy:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE scope_key IS NULL AND status IN ('paused', 'blocked', 'planning', 'running')
                    ORDER BY updated_at DESC 
                    LIMIT 1
                """)
                row = cur.fetchone()
            
            if not row:
                return None
            
            task = self._row_to_task(row)
            
            # Load steps
            step_repo = TaskStepRepository(self.db)
            task.steps = step_repo.list_by_task(task.id)
            
            return task
    
    def list_incomplete_for_scope(self, scope_key: str, include_legacy: bool = True) -> List[Task]:
        """
        List all incomplete tasks for a specific scope.
        
        Args:
            scope_key: Scope identifier
            include_legacy: If True, also include tasks without scope (legacy data)
        
        Returns:
            List of incomplete tasks
        """
        with self.db.cursor() as cur:
            if include_legacy:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE (scope_key = ? OR scope_key IS NULL) 
                          AND status NOT IN ('completed', 'aborted', 'failed')
                    ORDER BY 
                        CASE WHEN scope_key = ? THEN 0 ELSE 1 END,
                        updated_at DESC
                """, (scope_key, scope_key))
            else:
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE scope_key = ? AND status NOT IN ('completed', 'aborted', 'failed')
                    ORDER BY updated_at DESC
                """, (scope_key,))
            
            rows = cur.fetchall()
            tasks = [self._row_to_task(row) for row in rows]
            
            # Load steps for each task
            step_repo = TaskStepRepository(self.db)
            for task in tasks:
                task.steps = step_repo.list_by_task(task.id)
            
            return tasks


class TaskStepRepository:
    """
    Repository for TaskStep entities.
    
    Handles all database operations for task steps.
    """
    
    def __init__(self, db: Optional[Database] = None):
        """
        Initialize repository.
        
        Args:
            db: Database instance (uses global if not provided)
        """
        self.db = db or get_db()
    
    def create(self, step: TaskStep) -> TaskStep:
        """
        Create a new task step.
        
        Args:
            step: TaskStep to create
        
        Returns:
            Created step
        """
        with self.db.cursor() as cur:
            cur.execute("""
                INSERT INTO task_steps (id, task_id, description, status, result, error,
                                        created_at, updated_at, started_at, completed_at, step_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step.id,
                step.task_id,
                step.description,
                step.status.value,
                step.result,
                step.error,
                step.created_at.isoformat(),
                step.updated_at.isoformat(),
                step.started_at.isoformat() if step.started_at else None,
                step.completed_at.isoformat() if step.completed_at else None,
                step.order
            ))
        
        return step
    
    def get(self, step_id: str) -> Optional[TaskStep]:
        """
        Get a task step by ID.
        
        Args:
            step_id: Step identifier
        
        Returns:
            TaskStep if found, None otherwise
        """
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM task_steps WHERE id = ?", (step_id,))
            row = cur.fetchone()
            
            if not row:
                return None
            
            return self._row_to_step(row)
    
    def update(self, step: TaskStep) -> TaskStep:
        """
        Update a task step.
        
        Args:
            step: TaskStep to update
        
        Returns:
            Updated step
        """
        step.updated_at = datetime.now()
        
        with self.db.cursor() as cur:
            cur.execute("""
                UPDATE task_steps 
                SET description = ?, status = ?, result = ?, error = ?,
                    updated_at = ?, started_at = ?, completed_at = ?, step_order = ?
                WHERE id = ?
            """, (
                step.description,
                step.status.value,
                step.result,
                step.error,
                step.updated_at.isoformat(),
                step.started_at.isoformat() if step.started_at else None,
                step.completed_at.isoformat() if step.completed_at else None,
                step.order,
                step.id
            ))
        
        return step
    
    def delete(self, step_id: str) -> bool:
        """
        Delete a task step.
        
        Args:
            step_id: Step identifier
        
        Returns:
            True if deleted, False if not found
        """
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM task_steps WHERE id = ?", (step_id,))
            return cur.rowcount > 0
    
    def list_by_task(self, task_id: str) -> List[TaskStep]:
        """
        List all steps for a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            List of steps ordered by step_order
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT * FROM task_steps 
                WHERE task_id = ? 
                ORDER BY step_order
            """, (task_id,))
            
            rows = cur.fetchall()
            return [self._row_to_step(row) for row in rows]
    
    def _row_to_step(self, row) -> TaskStep:
        """Convert database row to TaskStep object."""
        return TaskStep(
            id=row['id'],
            task_id=row['task_id'],
            description=row['description'],
            status=TaskStepStatus(row['status']),
            result=row['result'],
            error=row['error'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            order=row['step_order']
        )
