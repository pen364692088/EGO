"""
OpenEmotion Agent Runtime - Control State Guard

P2-D.4: State transition guard for control commands.

Defines which commands can operate on which task states.
Prevents illegal state transitions.
"""

from dataclasses import dataclass
from typing import Optional, Set, Dict, Any
from enum import Enum

from app.storage.models import Task, TaskStatus


class ControlCommand(str, Enum):
    """Control commands available to users."""
    APPROVE = "approve"
    REJECT = "reject"
    RETRY = "retry"
    CANCEL = "cancel"
    RESUME = "resume"
    PAUSE = "pause"
    ABORT = "abort"


@dataclass
class GuardResult:
    """Result of state guard check."""
    allowed: bool
    reason: str = ""
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    error_message: Optional[str] = None


# ============================================================================
# Command → Valid States Mapping
# ============================================================================

# Each command can only operate on tasks in these states
COMMAND_VALID_STATES: Dict[ControlCommand, Set[TaskStatus]] = {
    ControlCommand.APPROVE: {
        TaskStatus.WAITING_USER_INPUT,
    },
    ControlCommand.REJECT: {
        TaskStatus.WAITING_USER_INPUT,
    },
    ControlCommand.RETRY: {
        TaskStatus.BLOCKED,
    },
    ControlCommand.CANCEL: {
        TaskStatus.RUNNING,
        TaskStatus.PAUSED,
        TaskStatus.BLOCKED,
        TaskStatus.WAITING_USER_INPUT,
    },
    ControlCommand.RESUME: {
        TaskStatus.PAUSED,
        TaskStatus.WAITING_USER_INPUT,  # After user decision
    },
    ControlCommand.PAUSE: {
        TaskStatus.RUNNING,
    },
    ControlCommand.ABORT: {
        TaskStatus.CREATED,
        TaskStatus.PLANNING,
        TaskStatus.RUNNING,
        TaskStatus.PAUSED,
        TaskStatus.BLOCKED,
        TaskStatus.WAITING_USER_INPUT,
    },
}

# Command → New Status Mapping (for valid transitions)
COMMAND_NEW_STATUS: Dict[ControlCommand, Dict[TaskStatus, TaskStatus]] = {
    ControlCommand.APPROVE: {
        TaskStatus.WAITING_USER_INPUT: TaskStatus.RUNNING,
    },
    ControlCommand.REJECT: {
        TaskStatus.WAITING_USER_INPUT: TaskStatus.FAILED,
    },
    ControlCommand.RETRY: {
        TaskStatus.BLOCKED: TaskStatus.RUNNING,
    },
    ControlCommand.CANCEL: {
        TaskStatus.RUNNING: TaskStatus.ABORTED,
        TaskStatus.PAUSED: TaskStatus.ABORTED,
        TaskStatus.BLOCKED: TaskStatus.ABORTED,
        TaskStatus.WAITING_USER_INPUT: TaskStatus.ABORTED,
    },
    ControlCommand.RESUME: {
        TaskStatus.PAUSED: TaskStatus.RUNNING,
        TaskStatus.WAITING_USER_INPUT: TaskStatus.RUNNING,
    },
    ControlCommand.PAUSE: {
        TaskStatus.RUNNING: TaskStatus.PAUSED,
    },
    ControlCommand.ABORT: {
        TaskStatus.CREATED: TaskStatus.ABORTED,
        TaskStatus.PLANNING: TaskStatus.ABORTED,
        TaskStatus.RUNNING: TaskStatus.ABORTED,
        TaskStatus.PAUSED: TaskStatus.ABORTED,
        TaskStatus.BLOCKED: TaskStatus.ABORTED,
        TaskStatus.WAITING_USER_INPUT: TaskStatus.ABORTED,
    },
}


# ============================================================================
# Guard Functions
# ============================================================================

def check_command_allowed(
    command: ControlCommand,
    task: Optional[Task],
) -> GuardResult:
    """
    Check if a control command is allowed for a task.
    
    Args:
        command: Control command to check
        task: Target task (or None if not found)
    
    Returns:
        GuardResult with allowed status and details
    """
    # Task not found
    if task is None:
        return GuardResult(
            allowed=False,
            reason="task_not_found",
            error_message="任务不存在",
        )
    
    # Check if task status allows this command
    valid_states = COMMAND_VALID_STATES.get(command, set())
    
    if task.status not in valid_states:
        return GuardResult(
            allowed=False,
            reason="invalid_state",
            previous_status=task.status.value,
            error_message=f"当前状态 [{task.status.value}] 不允许执行 /{command.value}",
        )
    
    # Get new status
    new_status_map = COMMAND_NEW_STATUS.get(command, {})
    new_status = new_status_map.get(task.status)
    
    return GuardResult(
        allowed=True,
        previous_status=task.status.value,
        new_status=new_status.value if new_status else None,
    )


def get_available_commands(task: Task) -> list[str]:
    """
    Get list of commands available for a task.
    
    Args:
        task: Target task
    
    Returns:
        List of available command names
    """
    available = []
    
    for command in ControlCommand:
        valid_states = COMMAND_VALID_STATES.get(command, set())
        if task.status in valid_states:
            available.append(command.value)
    
    return available


def get_command_description(command: ControlCommand) -> str:
    """Get human-readable description of a command."""
    descriptions = {
        ControlCommand.APPROVE: "批准等待中的任务",
        ControlCommand.REJECT: "拒绝等待中的任务",
        ControlCommand.RETRY: "重试阻塞的任务",
        ControlCommand.CANCEL: "取消正在执行的任务",
        ControlCommand.RESUME: "恢复暂停的任务",
        ControlCommand.PAUSE: "暂停正在执行的任务",
        ControlCommand.ABORT: "中止任务",
    }
    return descriptions.get(command, command.value)


def validate_task_id(task_id: Optional[str]) -> tuple[bool, str]:
    """
    Validate task ID format.
    
    Args:
        task_id: Task ID to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not task_id:
        return False, "请提供任务 ID"
    
    if not task_id.startswith("task_"):
        return False, f"无效的任务 ID 格式: {task_id}"
    
    return True, ""


def check_idempotency(
    command: ControlCommand,
    task: Task,
    audit_entries: list[dict],
) -> tuple[bool, Optional[str]]:
    """
    Check if command is idempotent (already executed recently).
    
    Prevents duplicate control actions.
    
    Args:
        command: Control command
        task: Target task
        audit_entries: Recent audit entries for this task
    
    Returns:
        Tuple of (is_idempotent, skip_reason)
    """
    from datetime import datetime, timedelta
    
    if not audit_entries:
        return False, None
    
    # Check last 5 entries for duplicate within 1 minute
    threshold = datetime.now() - timedelta(minutes=1)
    
    for entry in audit_entries[:5]:
        if entry.get("command") != command.value:
            continue
        
        entry_time = entry.get("timestamp")
        if not entry_time:
            continue
        
        try:
            entry_dt = datetime.fromisoformat(entry_time)
            if entry_dt > threshold:
                return True, f"命令 /{command.value} 最近已执行，跳过重复操作"
        except Exception:
            pass
    
    return False, None
