"""
OpenEmotion Agent Runtime - Checkpoint System

Provides checkpoint persistence for task state recovery.
Enables resuming tasks after program restart.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
import uuid
import threading

from app.storage.models import Task, TaskStatus, TaskStep, TaskStepStatus
from app.logs.event_logger import get_event_logger, EventType


@dataclass
class Checkpoint:
    """
    Represents a checkpoint of task state.
    
    Attributes:
        id: Unique checkpoint identifier
        task_id: Associated task ID
        state: Task state at checkpoint time
        context: Context snapshot (task details, current step, etc.)
        created_at: When checkpoint was created
        metadata: Additional metadata
    """
    id: str
    task_id: str
    state: str  # Task status value
    context: Dict[str, Any]  # Task context snapshot
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'state': self.state,
            'context': self.context,
            'created_at': self.created_at.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            task_id=data['task_id'],
            state=data['state'],
            context=data['context'],
            created_at=datetime.fromisoformat(data['created_at']),
            metadata=data.get('metadata', {})
        )
    
    @classmethod
    def create_from_task(cls, task: Task, metadata: Optional[Dict[str, Any]] = None) -> 'Checkpoint':
        """
        Create a checkpoint from a task.
        
        Args:
            task: Task to checkpoint
            metadata: Additional metadata
        
        Returns:
            Checkpoint object
        """
        context = {
            'objective': task.objective,
            'status': task.status.value,
            'current_step_index': task.current_step_index,
            'total_steps': len(task.steps),
            'steps': [
                {
                    'id': step.id,
                    'description': step.description,
                    'status': step.status.value,
                    'result': step.result,
                    'error': step.error
                }
                for step in task.steps
            ],
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'error': task.error,
            'task_metadata': task.metadata
        }
        
        return cls(
            id=f"ckpt_{uuid.uuid4().hex[:8]}",
            task_id=task.id,
            state=task.status.value,
            context=context,
            metadata=metadata or {}
        )


class CheckpointManager:
    """
    Manages checkpoint creation, storage, and restoration.
    
    Features:
    - Persistent JSON file storage
    - Automatic checkpoint cleanup
    - Task state recovery
    - Thread-safe operations
    """
    
    DEFAULT_CHECKPOINT_DIR = "data/checkpoints"
    MAX_CHECKPOINTS_PER_TASK = 5
    MAX_CHECKPOINT_AGE_HOURS = 24
    
    def __init__(self, checkpoint_dir: Optional[str] = None):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir or self.DEFAULT_CHECKPOINT_DIR)
        self._lock = threading.Lock()
        self._ensure_directory()
    
    def _ensure_directory(self) -> None:
        """Ensure checkpoint directory exists."""
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get path for a checkpoint file."""
        return self.checkpoint_dir / f"{checkpoint_id}.json"
    
    def _get_task_checkpoint_index_path(self, task_id: str) -> Path:
        """Get path for task checkpoint index."""
        return self.checkpoint_dir / f"task_{task_id}_index.json"
    
    def create_checkpoint(self, task: Task, metadata: Optional[Dict[str, Any]] = None) -> Checkpoint:
        """
        Create and save a checkpoint for a task.
        
        Args:
            task: Task to checkpoint
            metadata: Additional metadata
        
        Returns:
            Created checkpoint
        """
        checkpoint = Checkpoint.create_from_task(task, metadata)
        
        with self._lock:
            # Save checkpoint file
            checkpoint_path = self._get_checkpoint_path(checkpoint.id)
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
            
            # Update task index
            self._update_task_index(task.id, checkpoint.id)
            
            # Cleanup old checkpoints
            self._cleanup_old_checkpoints(task.id)
        
        # Log checkpoint creation
        get_event_logger().log_event(EventType.CHECKPOINT_CREATED, {'checkpoint_id': checkpoint.id, 'task_id': task.id})
        
        return checkpoint
    
    def _update_task_index(self, task_id: str, checkpoint_id: str) -> None:
        """Update the checkpoint index for a task."""
        index_path = self._get_task_checkpoint_index_path(task_id)
        
        # Load existing index
        index = []
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        
        # Add new checkpoint
        index.append({
            'checkpoint_id': checkpoint_id,
            'created_at': datetime.now().isoformat()
        })
        
        # Save index
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    
    def _cleanup_old_checkpoints(self, task_id: str) -> None:
        """Remove old checkpoints for a task."""
        index_path = self._get_task_checkpoint_index_path(task_id)
        
        if not index_path.exists():
            return
        
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        # Keep only the most recent checkpoints
        if len(index) > self.MAX_CHECKPOINTS_PER_TASK:
            # Sort by created_at
            index.sort(key=lambda x: x['created_at'], reverse=True)
            
            # Get checkpoints to remove
            to_remove = index[self.MAX_CHECKPOINTS_PER_TASK:]
            
            # Remove old checkpoint files
            for entry in to_remove:
                checkpoint_path = self._get_checkpoint_path(entry['checkpoint_id'])
                if checkpoint_path.exists():
                    checkpoint_path.unlink()
            
            # Update index
            index = index[:self.MAX_CHECKPOINTS_PER_TASK]
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """
        Get a checkpoint by ID.
        
        Args:
            checkpoint_id: Checkpoint identifier
        
        Returns:
            Checkpoint if found, None otherwise
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)
        
        if not checkpoint_path.exists():
            return None
        
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return Checkpoint.from_dict(data)
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """
        Get the latest checkpoint for a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Latest checkpoint if exists, None otherwise
        """
        index_path = self._get_task_checkpoint_index_path(task_id)
        
        if not index_path.exists():
            return None
        
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        if not index:
            return None
        
        # Sort by created_at to get latest
        index.sort(key=lambda x: x['created_at'], reverse=True)
        latest_id = index[0]['checkpoint_id']
        
        return self.get_checkpoint(latest_id)
    
    def get_task_checkpoints(self, task_id: str) -> List[Checkpoint]:
        """
        Get all checkpoints for a task.
        
        Args:
            task_id: Task identifier
        
        Returns:
            List of checkpoints (newest first)
        """
        index_path = self._get_task_checkpoint_index_path(task_id)
        
        if not index_path.exists():
            return []
        
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        # Sort by created_at
        index.sort(key=lambda x: x['created_at'], reverse=True)
        
        checkpoints = []
        for entry in index:
            checkpoint = self.get_checkpoint(entry['checkpoint_id'])
            if checkpoint:
                checkpoints.append(checkpoint)
        
        return checkpoints
    
    def list_all_checkpoints(self) -> List[Checkpoint]:
        """
        List all checkpoints.
        
        Returns:
            List of all checkpoints (newest first)
        """
        checkpoints = []
        
        for file_path in self.checkpoint_dir.glob("ckpt_*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                checkpoints.append(Checkpoint.from_dict(data))
            except (json.JSONDecodeError, KeyError):
                continue
        
        # Sort by created_at
        checkpoints.sort(key=lambda x: x.created_at, reverse=True)
        
        return checkpoints
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint identifier
        
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            checkpoint_path = self._get_checkpoint_path(checkpoint_id)
            
            if not checkpoint_path.exists():
                return False
            
            # Get checkpoint to find task_id
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            task_id = data.get('task_id')
            
            # Remove checkpoint file
            checkpoint_path.unlink()
            
            # Update index
            if task_id:
                self._remove_from_index(task_id, checkpoint_id)
            
            return True
    
    def _remove_from_index(self, task_id: str, checkpoint_id: str) -> None:
        """Remove checkpoint from task index."""
        index_path = self._get_task_checkpoint_index_path(task_id)
        
        if not index_path.exists():
            return
        
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        
        # Remove entry
        index = [e for e in index if e['checkpoint_id'] != checkpoint_id]
        
        if index:
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        else:
            # Remove empty index file
            index_path.unlink()
    
    def cleanup_expired_checkpoints(self, max_age_hours: Optional[int] = None) -> int:
        """
        Remove checkpoints older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours (uses default if not specified)
        
        Returns:
            Number of checkpoints removed
        """
        max_age_hours = max_age_hours or self.MAX_CHECKPOINT_AGE_HOURS
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        
        removed = 0
        
        with self._lock:
            for file_path in self.checkpoint_dir.glob("ckpt_*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    checkpoint = Checkpoint.from_dict(data)
                    
                    if checkpoint.created_at.timestamp() < cutoff:
                        file_path.unlink()
                        removed += 1
                        
                        # Update index
                        if checkpoint.task_id:
                            self._remove_from_index(checkpoint.task_id, checkpoint.id)
                        
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return removed
    
    def get_recovery_info(self) -> Dict[str, Any]:
        """
        Get information about recoverable tasks.
        
        Returns:
            Dict with recovery information
        """
        checkpoints = self.list_all_checkpoints()
        
        # Group by task_id
        by_task: Dict[str, List[Checkpoint]] = {}
        for checkpoint in checkpoints:
            if checkpoint.task_id not in by_task:
                by_task[checkpoint.task_id] = []
            by_task[checkpoint.task_id].append(checkpoint)
        
        # Build recovery info
        recoverable = []
        for task_id, task_checkpoints in by_task.items():
            latest = task_checkpoints[0]
            
            # Check if state is recoverable (not terminal)
            terminal_states = {'completed', 'failed', 'aborted'}
            is_recoverable = latest.state not in terminal_states
            
            recoverable.append({
                'task_id': task_id,
                'state': latest.state,
                'latest_checkpoint': latest.id,
                'created_at': latest.created_at.isoformat(),
                'recoverable': is_recoverable,
                'checkpoint_count': len(task_checkpoints)
            })
        
        return {
            'total_checkpoints': len(checkpoints),
            'unique_tasks': len(by_task),
            'recoverable_tasks': [t for t in recoverable if t['recoverable']],
            'all_tasks': recoverable
        }


class CheckpointRecovery:
    """
    Handles task recovery from checkpoints.
    """
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None):
        """
        Initialize recovery handler.
        
        Args:
            checkpoint_manager: CheckpointManager instance
        """
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
    
    def get_recoverable_tasks(self) -> List[Dict[str, Any]]:
        """
        Get list of recoverable tasks.
        
        Returns:
            List of recoverable task info
        """
        recovery_info = self.checkpoint_manager.get_recovery_info()
        return recovery_info['recoverable_tasks']
    
    def has_recoverable_tasks(self) -> bool:
        """Check if there are recoverable tasks."""
        return len(self.get_recoverable_tasks()) > 0
    
    def recover_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Recover a task from its latest checkpoint.
        
        Args:
            task_id: Task identifier
        
        Returns:
            Recovery context if successful, None otherwise
        """
        checkpoint = self.checkpoint_manager.get_latest_checkpoint(task_id)
        
        if not checkpoint:
            return None
        
        # Log restoration
        get_event_logger().log_event(EventType.CHECKPOINT_RESTORED, {'checkpoint_id': checkpoint.id, 'task_id': task_id})
        
        return {
            'task_id': task_id,
            'checkpoint_id': checkpoint.id,
            'state': checkpoint.state,
            'context': checkpoint.context,
            'recovered_at': datetime.now().isoformat()
        }
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """
        Get recovery status summary.
        
        Returns:
            Status summary
        """
        recovery_info = self.checkpoint_manager.get_recovery_info()
        
        return {
            'has_recoverable_tasks': len(recovery_info['recoverable_tasks']) > 0,
            'recoverable_count': len(recovery_info['recoverable_tasks']),
            'total_checkpoints': recovery_info['total_checkpoints'],
            'tasks': recovery_info['all_tasks']
        }
    
    def create_status_message(self) -> str:
        """
        Create a user-friendly status message.
        
        Returns:
            Status message
        """
        status = self.get_recovery_status()
        
        lines = ["📊 *Recovery Status*", ""]
        
        if status['has_recoverable_tasks']:
            lines.append(f"✅ Found {status['recoverable_count']} recoverable task(s)")
            lines.append("")
            
            for task in status['tasks']:
                recoverable = "🔄" if task['recoverable'] else "✓"
                lines.append(
                    f"{recoverable} `{task['task_id']}` - {task['state']}"
                )
            
            lines.append("")
            lines.append("Use /resume `task_id` to recover a task.")
        else:
            lines.append("No recoverable tasks found.")
            lines.append("")
            lines.append("Use /new to create a new task.")
        
        return "\n".join(lines)


# Global instances
_checkpoint_manager: Optional[CheckpointManager] = None
_checkpoint_recovery: Optional[CheckpointRecovery] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get or create global checkpoint manager."""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


def get_checkpoint_recovery() -> CheckpointRecovery:
    """Get or create global checkpoint recovery handler."""
    global _checkpoint_recovery
    if _checkpoint_recovery is None:
        _checkpoint_recovery = CheckpointRecovery(get_checkpoint_manager())
    return _checkpoint_recovery


def create_checkpoint(task: Task, metadata: Optional[Dict[str, Any]] = None) -> Checkpoint:
    """Convenience function to create a checkpoint."""
    return get_checkpoint_manager().create_checkpoint(task, metadata)


def get_latest_checkpoint(task_id: str) -> Optional[Checkpoint]:
    """Convenience function to get latest checkpoint."""
    return get_checkpoint_manager().get_latest_checkpoint(task_id)


def recover_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to recover a task."""
    return get_checkpoint_recovery().recover_task(task_id)
