"""
OpenEmotion Agent Runtime - Data Models

Defines data models for tasks, task steps, and related entities.
Uses dataclasses for simple, type-safe data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid


class TaskStatus(str, Enum):
    """Task status states following state machine."""
    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    WAITING_USER_INPUT = "waiting_user_input"  # P2-C: Waiting for user confirmation
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class TaskStepStatus(str, Enum):
    """Task step status states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskStep:
    """
    Represents a single step within a task.
    
    Attributes:
        id: Unique step identifier
        task_id: Parent task identifier
        description: What this step does
        status: Current step status
        result: Optional result/output from step execution
        error: Optional error message if step failed
        created_at: When step was created
        updated_at: When step was last updated
        started_at: When step execution started
        completed_at: When step completed/failed
        order: Execution order (0-indexed)
    """
    id: str
    task_id: str
    description: str
    status: TaskStepStatus = TaskStepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    order: int = 0
    
    @classmethod
    def create(cls, task_id: str, description: str, order: int = 0) -> 'TaskStep':
        """Factory method to create a new task step."""
        now = datetime.now()
        return cls(
            id=f"step_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            description=description,
            order=order,
            created_at=now,
            updated_at=now
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'description': self.description,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'order': self.order
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TaskStep':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            task_id=data['task_id'],
            description=data['description'],
            status=TaskStepStatus(data['status']),
            result=data.get('result'),
            error=data.get('error'),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            order=data.get('order', 0)
        )


@dataclass
class Task:
    """
    Represents a task to be executed.
    
    Attributes:
        id: Unique task identifier
        objective: What this task aims to achieve
        status: Current task status (state machine)
        steps: List of task steps
        created_at: When task was created
        updated_at: When task was last updated
        started_at: When task execution started
        completed_at: When task completed/failed/aborted
        current_step_index: Index of current step being executed
        error: Optional error message if task failed
        metadata: Additional task metadata
        chat_id: Chat/conversation identifier for scope isolation
        user_id: User identifier for scope isolation
        scope_key: Combined scope key (e.g., "tg:{chat_id}:{user_id}")
        waiting_reason: P2-C: Reason for waiting user input
        waiting_request: P2-C: ApprovalRequest dict for user confirmation
        user_decision: P2-C: User's decision after confirmation
    """
    id: str
    objective: str
    status: TaskStatus = TaskStatus.CREATED
    steps: List[TaskStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    # Scope fields for isolation
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    scope_key: Optional[str] = None
    # P2-C: Waiting state fields
    waiting_reason: Optional[str] = None
    waiting_request: Optional[dict] = None
    user_decision: Optional[dict] = None
    
    @classmethod
    def create(cls, objective: str, chat_id: Optional[str] = None, 
               user_id: Optional[str] = None, scope_key: Optional[str] = None) -> 'Task':
        """Factory method to create a new task with scope."""
        now = datetime.now()
        
        # Auto-generate scope_key if not provided but chat_id/user_id are
        if not scope_key and (chat_id or user_id):
            scope_key = f"tg:{chat_id or 'unknown'}:{user_id or 'unknown'}"
        
        return cls(
            id=f"task_{uuid.uuid4().hex[:8]}",
            objective=objective,
            created_at=now,
            updated_at=now,
            chat_id=chat_id,
            user_id=user_id,
            scope_key=scope_key
        )
    
    @property
    def current_step(self) -> Optional[TaskStep]:
        """Get the current step being executed."""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    @property
    def progress(self) -> tuple[int, int]:
        """Get progress as (completed_steps, total_steps)."""
        completed = sum(1 for s in self.steps if s.status == TaskStepStatus.COMPLETED)
        return (completed, len(self.steps))
    
    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage."""
        if not self.steps:
            return 0.0
        completed, total = self.progress
        return (completed / total) * 100
    
    def add_step(self, description: str) -> TaskStep:
        """Add a new step to the task."""
        step = TaskStep.create(
            task_id=self.id,
            description=description,
            order=len(self.steps)
        )
        self.steps.append(step)
        self.updated_at = datetime.now()
        return step
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'objective': self.objective,
            'status': self.status.value,
            'steps': [s.to_dict() for s in self.steps],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'current_step_index': self.current_step_index,
            'error': self.error,
            'metadata': self.metadata,
            # Scope fields
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'scope_key': self.scope_key,
            # P2-C: Waiting state fields
            'waiting_reason': self.waiting_reason,
            'waiting_request': self.waiting_request,
            'user_decision': self.user_decision,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Task':
        """Create from dictionary. Handles legacy tasks without scope fields."""
        steps = [TaskStep.from_dict(s) for s in data.get('steps', [])]
        return cls(
            id=data['id'],
            objective=data['objective'],
            status=TaskStatus(data['status']),
            steps=steps,
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data.get('started_at') else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
            current_step_index=data.get('current_step_index', 0),
            error=data.get('error'),
            metadata=data.get('metadata', {}),
            # Scope fields (optional for backward compatibility)
            chat_id=data.get('chat_id'),
            user_id=data.get('user_id'),
            scope_key=data.get('scope_key'),
            # P2-C: Waiting state fields (optional for backward compatibility)
            waiting_reason=data.get('waiting_reason'),
            waiting_request=data.get('waiting_request'),
            user_decision=data.get('user_decision'),
        )
