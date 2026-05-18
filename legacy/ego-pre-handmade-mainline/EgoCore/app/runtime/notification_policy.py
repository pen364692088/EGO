"""
OpenEmotion Agent Runtime - Notification Policy

P2-B.5: Minimal notification policy for background drivers.

Core rules:
- MUST notify: completed, blocked, manual_action_required, intent_mismatch_blocked, path_extraction_blocked, user status query
- DEFAULT NOT notify: heartbeat_tick, cron_tick, retry_attempt, checkpoint_save
- Background follows ReplyChannelGuard
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Set
from enum import Enum
from datetime import datetime
import logging

from app.runtime.execution_result import FailureClass
from app.runtime.failure_policy import (
    get_failure_policy,
    requires_user_notification,
    get_manual_action_hint,
)
from app.runtime.guard import ExecutionMode, get_reply_guard


logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Types of notifications."""
    # Must notify
    TASK_COMPLETED = "task_completed"
    TASK_BLOCKED = "task_blocked"
    MANUAL_ACTION_REQUIRED = "manual_action_required"
    INTENT_MISMATCH_BLOCKED = "intent_mismatch_blocked"
    PATH_EXTRACTION_BLOCKED = "path_extraction_blocked"
    STATUS_QUERY_RESPONSE = "status_query_response"
    
    # Should notify
    TASK_FAILED = "task_failed"
    RECOVERY_COMPLETED = "recovery_completed"
    
    # Default not notify
    HEARTBEAT_TICK = "heartbeat_tick"
    CRON_TICK = "cron_tick"
    RETRY_ATTEMPT = "retry_attempt"
    CHECKPOINT_SAVE = "checkpoint_save"
    INTERMEDIATE_PROGRESS = "intermediate_progress"
    
    # Debug only
    DEBUG_LOG = "debug_log"


@dataclass
class NotificationPayload:
    """Payload for a notification."""
    type: NotificationType
    task_id: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # User-facing fields
    user_safe_message: Optional[str] = None
    manual_action_hint: Optional[str] = None
    
    # Execution context
    trigger_source: str = "unknown"  # foreground, heartbeat, cron
    failure_class: Optional[str] = None


# ============================================================================
# Notification Categories
# ============================================================================

# MUST notify - always sent regardless of mode
MUST_NOTIFY: Set[NotificationType] = {
    NotificationType.TASK_COMPLETED,
    NotificationType.TASK_BLOCKED,
    NotificationType.MANUAL_ACTION_REQUIRED,
    NotificationType.INTENT_MISMATCH_BLOCKED,
    NotificationType.PATH_EXTRACTION_BLOCKED,
    NotificationType.STATUS_QUERY_RESPONSE,
}

# SHOULD notify - sent unless explicitly suppressed
SHOULD_NOTIFY: Set[NotificationType] = {
    NotificationType.TASK_FAILED,
    NotificationType.RECOVERY_COMPLETED,
}

# DEFAULT NOT notify - only sent if explicitly requested
DEFAULT_NOT_NOTIFY: Set[NotificationType] = {
    NotificationType.HEARTBEAT_TICK,
    NotificationType.CRON_TICK,
    NotificationType.RETRY_ATTEMPT,
    NotificationType.CHECKPOINT_SAVE,
    NotificationType.INTERMEDIATE_PROGRESS,
    NotificationType.DEBUG_LOG,
}


# ============================================================================
# Notification Policy Functions
# ============================================================================

def should_notify(notification_type: NotificationType,
                  execution_mode: ExecutionMode = ExecutionMode.FOREGROUND,
                  force_notify: bool = False) -> bool:
    """
    Determine if a notification should be sent.
    
    Args:
        notification_type: Type of notification
        execution_mode: Current execution mode
        force_notify: Force notification regardless of policy
    
    Returns:
        True if notification should be sent
    """
    if force_notify:
        return True
    
    # Must notify - always send
    if notification_type in MUST_NOTIFY:
        return True
    
    # Should notify - send unless suppressed
    if notification_type in SHOULD_NOTIFY:
        return True
    
    # Default not notify - only send if foreground or explicitly requested
    if notification_type in DEFAULT_NOT_NOTIFY:
        # Background should not send these
        if execution_mode == ExecutionMode.BACKGROUND:
            return False
        # Foreground can send debug info
        return True
    
    return False


def get_notification_for_failure(failure_class: FailureClass,
                                 task_id: str,
                                 trigger_source: str = "unknown") -> Optional[NotificationPayload]:
    """
    Create a notification for a failure.
    
    Args:
        failure_class: The failure classification
        task_id: Task identifier
        trigger_source: Source of the trigger (foreground/heartbeat/cron)
    
    Returns:
        NotificationPayload if notification should be sent, None otherwise
    """
    policy = get_failure_policy(failure_class)
    
    # Check if notification is required
    if not requires_user_notification(failure_class):
        return None
    
    # Determine notification type
    if failure_class == FailureClass.INTENT_MISMATCH:
        notification_type = NotificationType.INTENT_MISMATCH_BLOCKED
    elif failure_class == FailureClass.PATH_EXTRACTION_ERROR:
        notification_type = NotificationType.PATH_EXTRACTION_BLOCKED
    elif failure_class in (FailureClass.SAFETY_BLOCK, FailureClass.PERMISSION_ERROR):
        notification_type = NotificationType.MANUAL_ACTION_REQUIRED
    else:
        notification_type = NotificationType.TASK_BLOCKED
    
    # Build payload
    payload = NotificationPayload(
        type=notification_type,
        task_id=task_id,
        message=policy.reason,
        user_safe_message=policy.manual_action_hint,
        manual_action_hint=policy.manual_action_hint,
        trigger_source=trigger_source,
        failure_class=failure_class.value
    )
    
    return payload


def get_notification_for_completion(task_id: str,
                                    objective: str,
                                    trigger_source: str = "unknown") -> NotificationPayload:
    """
    Create a notification for task completion.
    
    Args:
        task_id: Task identifier
        objective: Task objective
        trigger_source: Source of the trigger
    
    Returns:
        NotificationPayload for completion
    """
    return NotificationPayload(
        type=NotificationType.TASK_COMPLETED,
        task_id=task_id,
        message=f"任务完成: {objective}",
        user_safe_message=f"✅ {objective}",
        trigger_source=trigger_source
    )


def get_notification_for_blocked(task_id: str,
                                 failure_class: FailureClass,
                                 error_message: str,
                                 trigger_source: str = "unknown") -> NotificationPayload:
    """
    Create a notification for a blocked task.
    
    Args:
        task_id: Task identifier
        failure_class: The failure classification
        error_message: Error message
        trigger_source: Source of the trigger
    
    Returns:
        NotificationPayload for blocked task
    """
    manual_hint = get_manual_action_hint(failure_class)
    
    return NotificationPayload(
        type=NotificationType.TASK_BLOCKED,
        task_id=task_id,
        message=error_message,
        user_safe_message=f"⚠️ 任务被阻塞: {error_message}",
        manual_action_hint=manual_hint,
        trigger_source=trigger_source,
        failure_class=failure_class.value
    )


# ============================================================================
# Notification Formatter
# ============================================================================

def format_notification(payload: NotificationPayload) -> str:
    """
    Format a notification for display.
    
    Args:
        payload: Notification payload
    
    Returns:
        Formatted message string
    """
    lines = []
    
    # Header based on type
    if payload.type == NotificationType.TASK_COMPLETED:
        lines.append("✅ 任务完成")
    elif payload.type == NotificationType.TASK_BLOCKED:
        lines.append("⚠️ 任务阻塞")
    elif payload.type == NotificationType.MANUAL_ACTION_REQUIRED:
        lines.append("🔔 需要人工干预")
    elif payload.type == NotificationType.INTENT_MISMATCH_BLOCKED:
        lines.append("🚫 意图不匹配")
    elif payload.type == NotificationType.PATH_EXTRACTION_BLOCKED:
        lines.append("🚫 路径解析失败")
    elif payload.type == NotificationType.TASK_FAILED:
        lines.append("❌ 任务失败")
    elif payload.type == NotificationType.STATUS_QUERY_RESPONSE:
        lines.append("📊 任务状态")
    else:
        lines.append("📢 通知")
    
    # Task ID
    if payload.task_id:
        lines.append(f"任务ID: {payload.task_id}")
    
    # Message
    if payload.user_safe_message:
        lines.append(payload.user_safe_message)
    elif payload.message:
        lines.append(payload.message)
    
    # Manual action hint
    if payload.manual_action_hint:
        lines.append(f"\n💡 建议: {payload.manual_action_hint}")
    
    # Failure class
    if payload.failure_class:
        lines.append(f"\n失败类型: {payload.failure_class}")
    
    # Trigger source
    if payload.trigger_source != "foreground":
        lines.append(f"\n触发源: {payload.trigger_source}")
    
    return "\n".join(lines)


# ============================================================================
# Notification Dispatcher
# ============================================================================

class NotificationDispatcher:
    """
    Dispatches notifications according to policy.
    
    Integrates with Telegram bot for sending notifications.
    """
    
    def __init__(self):
        self._reply_guard = get_reply_guard()
    
    def dispatch(self, payload: NotificationPayload,
                 execution_mode: ExecutionMode = ExecutionMode.FOREGROUND,
                 force_notify: bool = False) -> bool:
        """
        Dispatch a notification.
        
        Args:
            payload: Notification payload
            execution_mode: Current execution mode
            force_notify: Force notification
        
        Returns:
            True if notification was sent
        """
        # Check policy
        if not should_notify(payload.type, execution_mode, force_notify):
            logger.debug(f"Notification suppressed: {payload.type.value}")
            return False
        
        # Check reply guard
        if not self._reply_guard.can_send_notification(payload.type.value, execution_mode):
            logger.debug(f"Notification blocked by guard: {payload.type.value}")
            return False
        
        # Format message
        message = format_notification(payload)
        
        # Send via Telegram (if available)
        try:
            from app.telegram_bot import send_notification
            send_notification(payload.task_id, message)
            logger.info(f"Notification sent: {payload.type.value} for {payload.task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    def dispatch_failure(self, task_id: str, failure_class: FailureClass,
                         trigger_source: str = "unknown") -> bool:
        """
        Dispatch a failure notification.
        
        Args:
            task_id: Task identifier
            failure_class: Failure classification
            trigger_source: Source of trigger
        
        Returns:
            True if notification was sent
        """
        payload = get_notification_for_failure(failure_class, task_id, trigger_source)
        if payload:
            mode = ExecutionMode.BACKGROUND if trigger_source in ("heartbeat", "cron") else ExecutionMode.FOREGROUND
            return self.dispatch(payload, mode)
        return False
    
    def dispatch_completion(self, task_id: str, objective: str,
                           trigger_source: str = "unknown") -> bool:
        """
        Dispatch a completion notification.
        
        Args:
            task_id: Task identifier
            objective: Task objective
            trigger_source: Source of trigger
        
        Returns:
            True if notification was sent
        """
        payload = get_notification_for_completion(task_id, objective, trigger_source)
        mode = ExecutionMode.BACKGROUND if trigger_source in ("heartbeat", "cron") else ExecutionMode.FOREGROUND
        return self.dispatch(payload, mode)


# Global dispatcher
_dispatcher: Optional[NotificationDispatcher] = None


def get_notification_dispatcher() -> NotificationDispatcher:
    """Get or create global notification dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
