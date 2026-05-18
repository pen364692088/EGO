"""
OpenEmotion Agent Runtime - Control Commands Handler

P2-D.3: Handles user control commands for tasks.

Commands:
- /tasks: List tasks
- /task <id>: Task detail
- /approve <id>: Approve waiting task
- /reject <id>: Reject waiting task
- /retry <id>: Retry blocked task
- /cancel <id>: Cancel task
- /resume <id>: Resume task
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.runtime.control_guard import (
    ControlCommand,
    check_command_allowed,
    get_available_commands,
    validate_task_id,
)
from app.runtime.control_audit import (
    log_control_action,
    get_task_audit_summary,
    AuditSource,
)
from app.runtime.status_query import (
    get_task_status,
    list_active_tasks,
    list_blocked_tasks,
    TaskStatusSummary,
    format_status_report,
)
from app.runtime.resume_driver import ResumeDriver
from app.runtime.failure_policy import can_auto_retry


logger = logging.getLogger(__name__)


@dataclass
class ControlResult:
    """Result of a control command."""
    success: bool
    message: str
    task_id: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    audit_logged: bool = False
    error: Optional[str] = None


class ControlCommandsHandler:
    """
    Handles Telegram control commands.
    
    All commands:
    - Check state guard
    - Perform action
    - Log to audit trail
    - Return user message
    """
    
    def __init__(self):
        self.task_repo = TaskRepository()
        self.resume_driver = ResumeDriver()
    
    # ========================================================================
    # Task List and Detail
    # ========================================================================
    
    def handle_tasks(self, show_all: bool = False) -> str:
        """
        Handle /tasks command.
        
        Args:
            show_all: Show all tasks, not just active
        
        Returns:
            Formatted message
        """
        lines = []
        lines.append("📋 **任务列表**")
        lines.append("")
        
        # Get active tasks
        active = list_active_tasks(limit=10)
        
        if not active:
            lines.append("暂无活跃任务")
            return "\n".join(lines)
        
        lines.append(f"**活跃任务** ({len(active)}):")
        lines.append("")
        
        for summary in active:
            status_emoji = self._get_status_emoji(summary.current_status)
            lines.append(f"{status_emoji} `{summary.task_id}`")
            lines.append(f"   状态: {summary.current_status}")
            if summary.objective:
                obj = summary.objective[:40] + "..." if len(summary.objective) > 40 else summary.objective
                lines.append(f"   目标: {obj}")
            if summary.failure_class:
                lines.append(f"   失败: {summary.failure_class}")
            if summary.waiting_reason:
                lines.append(f"   等待: {summary.waiting_reason}")
            lines.append("")
        
        lines.append("使用 `/task <id>` 查看详情")
        
        return "\n".join(lines)
    
    def handle_task_detail(self, task_id: str) -> str:
        """
        Handle /task <id> command.
        
        Args:
            task_id: Task ID to query
        
        Returns:
            Formatted message
        """
        # Validate task_id
        valid, error = validate_task_id(task_id)
        if not valid:
            return f"❌ {error}"
        
        # Get task
        task = self.task_repo.get(task_id)
        if not task:
            return f"❌ 任务不存在: {task_id}"
        
        # Get status summary
        summary = get_task_status(task_id)
        if not summary:
            return f"❌ 无法获取任务状态: {task_id}"
        
        # Build detail message
        lines = []
        status_emoji = self._get_status_emoji(summary.current_status)
        
        lines.append(f"{status_emoji} **任务详情**")
        lines.append("")
        lines.append(f"**ID**: `{summary.task_id}`")
        lines.append(f"**状态**: {summary.current_status}")
        lines.append(f"**目标**: {summary.objective or 'N/A'}")
        
        # Progress
        if summary.total_steps > 0:
            lines.append(f"**进度**: {summary.completed_steps}/{summary.total_steps} ({summary.progress_percentage:.0f}%)")
        
        # Failure info
        if summary.failure_class:
            lines.append("")
            lines.append(f"**失败类型**: `{summary.failure_class}`")
        
        if summary.blocked_reason:
            lines.append(f"**阻塞原因**: {summary.blocked_reason}")
        
        if summary.waiting_reason:
            lines.append(f"**等待原因**: {summary.waiting_reason}")
        
        # Retry info
        if summary.retry_count > 0:
            lines.append(f"**重试次数**: {summary.retry_count}")
        
        # Trigger source
        if summary.trigger_source != "foreground":
            lines.append(f"**触发源**: {summary.trigger_source}")
        
        # Available actions
        available = get_available_commands(task)
        if available:
            lines.append("")
            lines.append("**可用操作**:")
            for cmd in available:
                lines.append(f"  `/{cmd} {task_id}`")
        
        # Audit summary
        audit_summary = get_task_audit_summary(task_id)
        if audit_summary["total_actions"] > 0:
            lines.append("")
            lines.append(f"**控制历史**: {audit_summary['total_actions']} 次操作")
        
        return "\n".join(lines)
    
    # ========================================================================
    # Control Commands
    # ========================================================================
    
    def handle_approve(self, task_id: str, actor: str = "user") -> ControlResult:
        """
        Handle /approve <id> command.
        
        Approves a waiting task.
        
        Args:
            task_id: Task ID to approve
            actor: Who is approving
        
        Returns:
            ControlResult
        """
        task = self.task_repo.get(task_id)
        guard = check_command_allowed(ControlCommand.APPROVE, task)
        
        if not guard.allowed:
            return ControlResult(
                success=False,
                message=guard.error_message or "操作不允许",
                error=guard.reason,
            )
        
        previous_status = task.status.value
        
        # Resume task with user decision
        decision = {
            "is_valid": True,
            "approved": True,
            "source": "telegram_command",
            "timestamp": datetime.now().isoformat(),
        }
        
        task.user_decision = decision
        task.status = TaskStatus.RUNNING
        task.waiting_reason = None
        task.waiting_request = None
        self.task_repo.update(task)
        
        # Log audit
        log_control_action(
            command="approve",
            task=task,
            previous_status=previous_status,
            new_status=task.status.value,
            actor=actor,
        )
        
        return ControlResult(
            success=True,
            message=f"✅ 任务已批准，继续执行: {task_id}",
            task_id=task_id,
            previous_status=previous_status,
            new_status=task.status.value,
            audit_logged=True,
        )
    
    def handle_reject(self, task_id: str, actor: str = "user", reason: Optional[str] = None) -> ControlResult:
        """
        Handle /reject <id> command.
        
        Rejects a waiting task.
        
        Args:
            task_id: Task ID to reject
            actor: Who is rejecting
            reason: Optional rejection reason
        
        Returns:
            ControlResult
        """
        task = self.task_repo.get(task_id)
        guard = check_command_allowed(ControlCommand.REJECT, task)
        
        if not guard.allowed:
            return ControlResult(
                success=False,
                message=guard.error_message or "操作不允许",
                error=guard.reason,
            )
        
        previous_status = task.status.value
        
        # Mark as failed
        task.status = TaskStatus.FAILED
        task.error = "[user_rejected] 用户拒绝了操作"
        if reason:
            task.error += f" - {reason}"
        task.user_decision = {
            "is_valid": True,
            "approved": False,
            "reason": reason,
            "source": "telegram_command",
            "timestamp": datetime.now().isoformat(),
        }
        self.task_repo.update(task)
        
        # Log audit
        log_control_action(
            command="reject",
            task=task,
            previous_status=previous_status,
            new_status=task.status.value,
            actor=actor,
            reason=reason,
        )
        
        return ControlResult(
            success=True,
            message=f"❌ 任务已拒绝: {task_id}",
            task_id=task_id,
            previous_status=previous_status,
            new_status=task.status.value,
            audit_logged=True,
        )
    
    def handle_retry(self, task_id: str, actor: str = "user") -> ControlResult:
        """
        Handle /retry <id> command.
        
        Retries a blocked task.
        
        Args:
            task_id: Task ID to retry
            actor: Who is retrying
        
        Returns:
            ControlResult
        """
        task = self.task_repo.get(task_id)
        guard = check_command_allowed(ControlCommand.RETRY, task)
        
        if not guard.allowed:
            return ControlResult(
                success=False,
                message=guard.error_message or "操作不允许",
                error=guard.reason,
            )
        
        previous_status = task.status.value
        
        # Check if retry is allowed by failure policy
        from app.runtime.execution_result import FailureClass
        failure_class = None
        if task.error and task.error.startswith("[") and "]" in task.error:
            class_str = task.error[1:task.error.index("]")]
            try:
                failure_class = FailureClass(class_str)
            except ValueError:
                pass
        
        if failure_class:
            retry_count = task.metadata.get("retry_count", 0)
            if not can_auto_retry(failure_class, retry_count):
                return ControlResult(
                    success=False,
                    message=f"失败类型 [{failure_class.value}] 不允许重试",
                    task_id=task_id,
                    error="retry_not_allowed",
                )
        
        # Reset to running
        task.status = TaskStatus.RUNNING
        task.metadata["retry_count"] = task.metadata.get("retry_count", 0) + 1
        task.metadata["trigger_source"] = "user_retry"
        self.task_repo.update(task)
        
        # Log audit
        log_control_action(
            command="retry",
            task=task,
            previous_status=previous_status,
            new_status=task.status.value,
            actor=actor,
        )
        
        return ControlResult(
            success=True,
            message=f"🔄 任务已重试: {task_id}",
            task_id=task_id,
            previous_status=previous_status,
            new_status=task.status.value,
            audit_logged=True,
        )
    
    def handle_cancel(self, task_id: str, actor: str = "user", reason: Optional[str] = None) -> ControlResult:
        """
        Handle /cancel <id> command.
        
        Cancels a task.
        
        Args:
            task_id: Task ID to cancel
            actor: Who is cancelling
            reason: Optional cancellation reason
        
        Returns:
            ControlResult
        """
        task = self.task_repo.get(task_id)
        guard = check_command_allowed(ControlCommand.CANCEL, task)
        
        if not guard.allowed:
            return ControlResult(
                success=False,
                message=guard.error_message or "操作不允许",
                error=guard.reason,
            )
        
        previous_status = task.status.value
        
        # Cancel task
        task.status = TaskStatus.ABORTED
        task.error = "[user_cancelled] 用户取消了任务"
        if reason:
            task.error += f" - {reason}"
        self.task_repo.update(task)
        
        # Log audit
        log_control_action(
            command="cancel",
            task=task,
            previous_status=previous_status,
            new_status=task.status.value,
            actor=actor,
            reason=reason,
        )
        
        return ControlResult(
            success=True,
            message=f"🚫 任务已取消: {task_id}",
            task_id=task_id,
            previous_status=previous_status,
            new_status=task.status.value,
            audit_logged=True,
        )
    
    def handle_resume(self, task_id: str, actor: str = "user") -> ControlResult:
        """
        Handle /resume <id> command.
        
        Resumes a paused task.
        
        Args:
            task_id: Task ID to resume
            actor: Who is resuming
        
        Returns:
            ControlResult
        """
        task = self.task_repo.get(task_id)
        guard = check_command_allowed(ControlCommand.RESUME, task)
        
        if not guard.allowed:
            return ControlResult(
                success=False,
                message=guard.error_message or "操作不允许",
                error=guard.reason,
            )
        
        previous_status = task.status.value
        
        # Resume task
        task.status = TaskStatus.RUNNING
        task.metadata["trigger_source"] = "user_resume"
        self.task_repo.update(task)
        
        # Log audit
        log_control_action(
            command="resume",
            task=task,
            previous_status=previous_status,
            new_status=task.status.value,
            actor=actor,
        )
        
        return ControlResult(
            success=True,
            message=f"▶️ 任务已恢复: {task_id}",
            task_id=task_id,
            previous_status=previous_status,
            new_status=task.status.value,
            audit_logged=True,
        )
    
    # ========================================================================
    # Helpers
    # ========================================================================
    
    def _get_status_emoji(self, status: str) -> str:
        """Get emoji for task status."""
        return {
            "completed": "✅",
            "running": "▶️",
            "blocked": "⚠️",
            "failed": "❌",
            "paused": "⏸️",
            "waiting_user_input": "⏳",
            "created": "📝",
            "planning": "📋",
            "aborted": "🚫",
        }.get(status, "❓")


# ============================================================================
# Global Instance
# ============================================================================

_handler: Optional[ControlCommandsHandler] = None


def get_control_handler() -> ControlCommandsHandler:
    """Get or create global control handler instance."""
    global _handler
    if _handler is None:
        _handler = ControlCommandsHandler()
    return _handler
