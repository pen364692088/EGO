"""
OpenEmotion Agent Runtime - Reply Binding

P2-C.4: Binds user replies to waiting tasks.

Core responsibilities:
- Find most recent waiting task
- Check session/scope/agent consistency
- Handle multiple waiting tasks (ask user to select)
- Avoid misbinding regular chat as confirmation
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.storage.models import Task, TaskStatus
from app.storage.repositories import TaskRepository
from app.runtime.approval_policy import (
    ApprovalRequest,
    validate_user_reply,
    parse_user_decision,
)
from app.runtime.confirmation_renderer import render_telegram_confirmation


logger = logging.getLogger(__name__)


@dataclass
class BindingResult:
    """Result of reply binding attempt."""
    success: bool
    task_id: Optional[str] = None
    waiting_request: Optional[ApprovalRequest] = None
    decision: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    needs_task_selection: bool = False
    candidate_tasks: List[Task] = field(default_factory=list)


class ReplyBinder:
    """
    Binds user replies to waiting tasks.
    
    Rules:
    - Bind to most recent waiting task in same scope
    - Check session/scope consistency
    - If multiple waiting tasks, ask user to select first
    - Don't bind regular chat as confirmation
    """
    
    def __init__(self, task_repo: Optional[TaskRepository] = None):
        self.task_repo = task_repo or TaskRepository()
    
    def find_waiting_tasks(
        self,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scope_key: Optional[str] = None,
    ) -> List[Task]:
        """
        Find all waiting tasks for a scope.
        
        Args:
            chat_id: Chat identifier
            user_id: User identifier
            scope_key: Scope key
        
        Returns:
            List of waiting tasks, sorted by most recent first
        """
        all_tasks = self.task_repo.list_all(limit=100)
        
        waiting = []
        for task in all_tasks:
            if task.status != TaskStatus.WAITING_USER_INPUT:
                continue
            
            # Check scope match
            if scope_key and task.scope_key:
                if task.scope_key != scope_key:
                    continue
            elif chat_id and task.chat_id:
                if task.chat_id != chat_id:
                    continue
            elif user_id and task.user_id:
                if task.user_id != user_id:
                    continue
            
            waiting.append(task)
        
        # Sort by most recent first
        waiting.sort(key=lambda t: t.updated_at, reverse=True)
        
        return waiting
    
    def try_bind_reply(
        self,
        user_reply: str,
        chat_id: Optional[str] = None,
        user_id: Optional[str] = None,
        scope_key: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> BindingResult:
        """
        Try to bind a user reply to a waiting task.
        
        Args:
            user_reply: User's reply text
            chat_id: Chat identifier
            user_id: User identifier
            scope_key: Scope key
            task_id: Optional explicit task ID to bind to
        
        Returns:
            BindingResult with success status and details
        """
        # Find waiting tasks
        waiting_tasks = self.find_waiting_tasks(chat_id, user_id, scope_key)
        
        if not waiting_tasks:
            return BindingResult(
                success=False,
                error="No waiting tasks found",
            )
        
        # If explicit task_id provided, find that task
        if task_id:
            for task in waiting_tasks:
                if task.id == task_id:
                    return self._bind_to_task(user_reply, task)
            return BindingResult(
                success=False,
                error=f"Task {task_id} not found or not waiting",
            )
        
        # If multiple waiting tasks, need user to select
        if len(waiting_tasks) > 1:
            return BindingResult(
                success=False,
                needs_task_selection=True,
                candidate_tasks=waiting_tasks,
                error="Multiple waiting tasks, please specify which task",
            )
        
        # Single waiting task, try to bind
        return self._bind_to_task(user_reply, waiting_tasks[0])
    
    def _bind_to_task(self, user_reply: str, task: Task) -> BindingResult:
        """
        Bind user reply to a specific task.
        
        Args:
            user_reply: User's reply text
            task: The task to bind to
        
        Returns:
            BindingResult
        """
        if not task.waiting_request:
            return BindingResult(
                success=False,
                error=f"Task {task.id} has no waiting request",
            )
        
        # Parse waiting request
        try:
            request = ApprovalRequest.from_dict(task.waiting_request)
        except Exception as e:
            logger.error(f"Failed to parse waiting request: {e}")
            return BindingResult(
                success=False,
                error=f"Invalid waiting request format",
            )
        
        # Validate reply
        is_valid, parsed_value, error = validate_user_reply(user_reply, request)
        
        if not is_valid:
            return BindingResult(
                success=False,
                task_id=task.id,
                waiting_request=request,
                error=error,
            )
        
        # Parse decision
        decision = parse_user_decision(user_reply, request)
        decision["task_id"] = task.id
        decision["timestamp"] = datetime.now().isoformat()
        
        return BindingResult(
            success=True,
            task_id=task.id,
            waiting_request=request,
            decision=decision,
        )
    
    def is_likely_confirmation_reply(self, user_reply: str) -> bool:
        """
        Check if a message looks like a confirmation reply.
        
        Used to avoid misbinding regular chat as confirmation.
        
        Args:
            user_reply: User's message
        
        Returns:
            True if likely a confirmation reply
        """
        reply_lower = user_reply.lower().strip()
        
        # Yes/no patterns
        if reply_lower in ("yes", "no", "y", "n", "是", "否", "确认", "取消", "ok", "cancel"):
            return True
        
        # Option index (single digit)
        if reply_lower.isdigit() and len(reply_lower) == 1:
            return True
        
        # Path-like (contains / or \ or .)
        if "/" in user_reply or "\\" in user_reply:
            return True
        
        # Very short reply (likely confirmation)
        if len(reply_lower) <= 10:
            return True
        
        return False
    
    def render_task_selection_message(self, tasks: List[Task]) -> str:
        """
        Render a message asking user to select which task.
        
        Args:
            tasks: List of waiting tasks
        
        Returns:
            Message string
        """
        lines = []
        lines.append("📝 **多个任务等待回复**")
        lines.append("")
        lines.append("请选择要回复的任务：")
        lines.append("")
        
        for i, task in enumerate(tasks[:5]):  # Limit to 5
            objective = task.objective[:40] + "..." if len(task.objective) > 40 else task.objective
            reason = task.waiting_reason or "等待确认"
            lines.append(f"**{i}**. {objective}")
            lines.append(f"   原因: {reason}")
            lines.append("")
        
        lines.append(f"回复 `/reply <编号> <回答>` 选择任务")
        
        return "\n".join(lines)


# ============================================================================
# Integration with Telegram Bot
# ============================================================================

def handle_user_reply(
    user_reply: str,
    chat_id: str,
    user_id: str,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Handle a user reply from Telegram.
    
    Main entry point for reply binding.
    
    Args:
        user_reply: User's reply text
        chat_id: Telegram chat ID
        user_id: Telegram user ID
        task_id: Optional explicit task ID
    
    Returns:
        Result dict with action to take
    """
    binder = ReplyBinder()
    scope_key = f"tg:{chat_id}:{user_id}"
    
    result = binder.try_bind_reply(
        user_reply=user_reply,
        chat_id=chat_id,
        user_id=user_id,
        scope_key=scope_key,
        task_id=task_id,
    )
    
    if result.success:
        return {
            "action": "resume_task",
            "task_id": result.task_id,
            "decision": result.decision,
            "waiting_request": result.waiting_request.to_dict() if result.waiting_request else None,
        }
    
    elif result.needs_task_selection:
        message = binder.render_task_selection_message(result.candidate_tasks)
        return {
            "action": "ask_task_selection",
            "message": message,
            "candidate_tasks": [t.id for t in result.candidate_tasks],
        }
    
    elif result.error:
        return {
            "action": "error",
            "error": result.error,
            "task_id": result.task_id,
        }
    
    else:
        return {
            "action": "no_waiting_tasks",
        }


# ============================================================================
# Global instance
# ============================================================================

_binder: Optional[ReplyBinder] = None


def get_reply_binder() -> ReplyBinder:
    """Get or create global reply binder."""
    global _binder
    if _binder is None:
        _binder = ReplyBinder()
    return _binder
