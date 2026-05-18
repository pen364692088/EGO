"""
OpenEmotion Agent Runtime - Status Query

P2-B.6: Minimal status query for task monitoring.

Returns:
- task_id
- current_status
- failure_class
- retry_count
- trigger_source
- last_progress_at
- blocked_reason
- manual_action_hint
- last_checkpoint_summary
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

from app.storage.models import Task, TaskStatus, TaskStep, TaskStepStatus
from app.storage.repositories import TaskRepository
from app.runtime.execution_result import FailureClass
from app.runtime.failure_policy import (
    get_failure_policy,
    get_manual_action_hint,
    is_background_blocked,
)
from app.runtime.checkpoint import get_checkpoint_manager


@dataclass
class TaskStatusSummary:
    """
    Summary of task status for monitoring.
    
    All fields required by P2-B.6.
    """
    # Core identification
    task_id: str
    current_status: str
    
    # Failure information
    failure_class: Optional[str] = None
    
    # Retry tracking
    retry_count: int = 0
    
    # Execution context
    trigger_source: str = "unknown"  # foreground, heartbeat, cron
    
    # Timing
    last_progress_at: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Blocker information
    blocked_reason: Optional[str] = None
    manual_action_hint: Optional[str] = None
    
    # Checkpoint
    last_checkpoint_summary: Optional[str] = None
    
    # Progress
    progress_percentage: float = 0.0
    completed_steps: int = 0
    total_steps: int = 0
    
    # Scope
    scope_key: Optional[str] = None
    
    # Objective
    objective: Optional[str] = None
    
    # Current step
    current_step_description: Optional[str] = None
    
    # Error
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "current_status": self.current_status,
            "failure_class": self.failure_class,
            "retry_count": self.retry_count,
            "trigger_source": self.trigger_source,
            "last_progress_at": self.last_progress_at,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "blocked_reason": self.blocked_reason,
            "manual_action_hint": self.manual_action_hint,
            "last_checkpoint_summary": self.last_checkpoint_summary,
            "progress_percentage": self.progress_percentage,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "scope_key": self.scope_key,
            "objective": self.objective,
            "current_step_description": self.current_step_description,
            "error": self.error,
        }
    
    def to_markdown(self) -> str:
        """Format as markdown for display."""
        lines = []
        
        # Header
        status_emoji = {
            "completed": "✅",
            "running": "▶️",
            "blocked": "⚠️",
            "failed": "❌",
            "paused": "⏸️",
            "created": "📝",
            "planning": "📋",
            "aborted": "🚫",
        }.get(self.current_status, "❓")
        
        lines.append(f"## {status_emoji} 任务状态: {self.task_id}")
        lines.append("")
        
        # Status
        lines.append(f"**状态**: {self.current_status.upper()}")
        lines.append(f"**目标**: {self.objective or 'N/A'}")
        
        # Progress
        if self.total_steps > 0:
            lines.append(f"**进度**: {self.completed_steps}/{self.total_steps} ({self.progress_percentage:.0f}%)")
        
        # Failure info
        if self.failure_class:
            lines.append("")
            lines.append(f"**失败类型**: `{self.failure_class}`")
        
        if self.blocked_reason:
            lines.append(f"**阻塞原因**: {self.blocked_reason}")
        
        if self.error:
            lines.append(f"**错误**: {self.error[:200]}")
        
        # Retry info
        if self.retry_count > 0:
            lines.append(f"**重试次数**: {self.retry_count}")
        
        # Trigger source
        if self.trigger_source != "foreground":
            lines.append(f"**触发源**: {self.trigger_source}")
        
        # Manual action hint
        if self.manual_action_hint:
            lines.append("")
            lines.append(f"💡 **建议**: {self.manual_action_hint}")
        
        # Timing
        lines.append("")
        lines.append("---")
        if self.created_at:
            lines.append(f"创建: {self._format_time(self.created_at)}")
        if self.last_progress_at:
            lines.append(f"最后更新: {self._format_time(self.last_progress_at)}")
        if self.completed_at:
            lines.append(f"完成: {self._format_time(self.completed_at)}")
        
        return "\n".join(lines)
    
    def _format_time(self, iso_time: str) -> str:
        """Format ISO time for display."""
        try:
            dt = datetime.fromisoformat(iso_time)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_time


# ============================================================================
# Status Query Functions
# ============================================================================

def get_task_status(task_id: str) -> Optional[TaskStatusSummary]:
    """
    Get the status summary for a task.
    
    Args:
        task_id: Task identifier
    
    Returns:
        TaskStatusSummary or None if task not found
    """
    task_repo = TaskRepository()
    task = task_repo.get(task_id)
    
    if not task:
        return None
    
    return build_status_summary(task)


def build_status_summary(task: Task) -> TaskStatusSummary:
    """
    Build a status summary from a task.
    
    Args:
        task: Task object
    
    Returns:
        TaskStatusSummary
    """
    # Extract failure class from error
    failure_class = None
    if task.error:
        if task.error.startswith("[") and "]" in task.error:
            class_str = task.error[1:task.error.index("]")]
            try:
                failure_class = class_str
            except Exception:
                pass
    
    # Get retry count
    retry_count = task.metadata.get("retry_count", 0)
    
    # Get trigger source
    trigger_source = task.metadata.get("trigger_source", "foreground")
    
    # Determine last progress time
    last_progress_at = task.updated_at.isoformat() if task.updated_at else None
    
    # Find last completed step for more accurate progress time
    for step in reversed(task.steps):
        if step.status == TaskStepStatus.COMPLETED and step.completed_at:
            last_progress_at = step.completed_at.isoformat()
            break
    
    # Get blocked reason
    blocked_reason = None
    manual_action_hint = None
    
    if task.status == TaskStatus.BLOCKED:
        if task.error:
            # Extract reason after failure class
            if "]" in task.error:
                blocked_reason = task.error[task.error.index("]") + 1:].strip()
            else:
                blocked_reason = task.error
        
        # Get manual action hint
        if failure_class:
            try:
                fc = FailureClass(failure_class)
                manual_action_hint = get_manual_action_hint(fc)
            except Exception:
                pass
    
    # Get checkpoint summary
    checkpoint_summary = None
    try:
        checkpoint_mgr = get_checkpoint_manager()
        checkpoint = checkpoint_mgr.load_checkpoint(task.id)
        if checkpoint:
            checkpoint_summary = f"Step {checkpoint.get('current_step_index', 0)}"
    except Exception:
        pass
    
    # Progress
    completed_steps, total_steps = task.progress
    progress_percentage = task.progress_percentage
    
    # Current step
    current_step_description = None
    if task.current_step:
        current_step_description = task.current_step.description
    
    return TaskStatusSummary(
        task_id=task.id,
        current_status=task.status.value,
        failure_class=failure_class,
        retry_count=retry_count,
        trigger_source=trigger_source,
        last_progress_at=last_progress_at,
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        blocked_reason=blocked_reason,
        manual_action_hint=manual_action_hint,
        last_checkpoint_summary=checkpoint_summary,
        progress_percentage=progress_percentage,
        completed_steps=completed_steps,
        total_steps=total_steps,
        scope_key=task.scope_key,
        objective=task.objective,
        current_step_description=current_step_description,
        error=task.error,
    )


def list_active_tasks(limit: int = 10) -> List[TaskStatusSummary]:
    """
    List all active (non-terminal) tasks.
    
    Args:
        limit: Maximum number of tasks to return
    
    Returns:
        List of TaskStatusSummary
    """
    task_repo = TaskRepository()
    tasks = task_repo.list_all(limit=limit)
    
    # Filter out terminal states
    active = [
        task for task in tasks
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.ABORTED)
    ]
    
    return [build_status_summary(task) for task in active]


def list_blocked_tasks(limit: int = 10) -> List[TaskStatusSummary]:
    """
    List all blocked tasks.
    
    Args:
        limit: Maximum number of tasks to return
    
    Returns:
        List of TaskStatusSummary for blocked tasks
    """
    task_repo = TaskRepository()
    tasks = task_repo.list_all(limit=limit)
    
    blocked = [task for task in tasks if task.status == TaskStatus.BLOCKED]
    
    return [build_status_summary(task) for task in blocked]


def list_recently_completed(limit: int = 5) -> List[TaskStatusSummary]:
    """
    List recently completed tasks.
    
    Args:
        limit: Maximum number of tasks to return
    
    Returns:
        List of TaskStatusSummary for completed tasks
    """
    task_repo = TaskRepository()
    tasks = task_repo.list_all(limit=limit * 3)  # Get more to filter
    
    completed = [
        task for task in tasks
        if task.status == TaskStatus.COMPLETED
    ][:limit]
    
    return [build_status_summary(task) for task in completed]


# ============================================================================
# Status Query API
# ============================================================================

def query_status(task_id: Optional[str] = None,
                 include_active: bool = False,
                 include_blocked: bool = False) -> Dict[str, Any]:
    """
    Query task status.
    
    Args:
        task_id: Optional specific task ID
        include_active: Include list of active tasks
        include_blocked: Include list of blocked tasks
    
    Returns:
        Status query result
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "task": None,
        "active_tasks": [],
        "blocked_tasks": [],
    }
    
    if task_id:
        status = get_task_status(task_id)
        result["task"] = status.to_dict() if status else None
    
    if include_active:
        result["active_tasks"] = [s.to_dict() for s in list_active_tasks()]
    
    if include_blocked:
        result["blocked_tasks"] = [s.to_dict() for s in list_blocked_tasks()]
    
    return result


def format_status_report(task_id: Optional[str] = None,
                         include_active: bool = False,
                         include_blocked: bool = False) -> str:
    """
    Format a status report for display.
    
    Args:
        task_id: Optional specific task ID
        include_active: Include list of active tasks
        include_blocked: Include list of blocked tasks
    
    Returns:
        Formatted markdown report
    """
    lines = []
    lines.append("# 📊 任务状态报告")
    lines.append("")
    lines.append(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    if task_id:
        status = get_task_status(task_id)
        if status:
            lines.append(status.to_markdown())
        else:
            lines.append(f"❌ 任务未找到: {task_id}")
    
    if include_active:
        active = list_active_tasks()
        if active:
            lines.append("")
            lines.append("## 活跃任务")
            for s in active:
                status_emoji = {"running": "▶️", "blocked": "⚠️", "paused": "⏸️"}.get(s.current_status, "📝")
                lines.append(f"- {status_emoji} `{s.task_id}`: {s.objective[:50] if s.objective else 'N/A'}...")
    
    if include_blocked:
        blocked = list_blocked_tasks()
        if blocked:
            lines.append("")
            lines.append("## 阻塞任务")
            for s in blocked:
                lines.append(f"- ⚠️ `{s.task_id}`: {s.failure_class or 'Unknown'}")
                if s.manual_action_hint:
                    lines.append(f"  - 💡 {s.manual_action_hint}")
    
    return "\n".join(lines)
