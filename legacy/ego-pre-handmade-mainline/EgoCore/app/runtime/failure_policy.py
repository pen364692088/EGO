"""
OpenEmotion Agent Runtime - Background Failure Policy

P2-B.1: Defines failure_class -> background_action mapping for:
- Heartbeat driver
- Cron recovery driver

Core principle: "Tool execution success" != "Task completion success"
Prevents false-completed scenarios from being auto-retried to success.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Set
from enum import Enum

from app.runtime.execution_result import FailureClass


class BackgroundAction(str, Enum):
    """Actions background drivers can take."""
    RETRY = "retry"                    # Auto-retry the step
    BLOCK_MANUAL = "block_manual"      # Block and require manual intervention
    ABORT = "abort"                    # Abort the task
    SKIP_STEP = "skip_step"            # Skip current step, continue
    NO_ACTION = "no_action"            # No background action allowed
    NOTIFY_ONLY = "notify_only"        # Just notify user, no auto-retry


@dataclass
class FailurePolicyEntry:
    """
    Policy entry for a specific failure class.
    
    Defines how background drivers should handle each failure type.
    """
    # Whether auto-retry is allowed
    allow_auto_retry: bool = False
    
    # Whether heartbeat can resume this task
    allow_heartbeat_resume: bool = False
    
    # Whether cron can resume this task
    allow_cron_resume: bool = False
    
    # Maximum retry attempts (if retryable)
    retry_limit: int = 0
    
    # Final state if retries exhausted or not retryable
    final_state: str = "failed"
    
    # Whether user notification is required
    user_notification_required: bool = True
    
    # Recommended background action
    background_action: BackgroundAction = BackgroundAction.BLOCK_MANUAL
    
    # Human-readable reason for policy
    reason: str = ""
    
    # Manual action hint for users
    manual_action_hint: Optional[str] = None


# ============================================================================
# P2-B.1: Failure Class -> Background Policy Mapping
# ============================================================================

FAILURE_POLICY: Dict[FailureClass, FailurePolicyEntry] = {
    # ------------------------------------------------------------------------
    # CRITICAL: Intent/Postcondition failures - NEVER auto-retry
    # These represent "tool succeeded but goal not achieved"
    # ------------------------------------------------------------------------
    
    FailureClass.INTENT_MISMATCH: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Intent mismatch: executed wrong operation vs user intent",
        manual_action_hint="请重新描述任务目标，或确认操作意图"
    ),
    
    FailureClass.POSTCONDITION_FAILED: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Postcondition failed: tool success but goal not achieved",
        manual_action_hint="操作未达成预期结果，请检查环境或调整任务"
    ),
    
    FailureClass.PATH_EXTRACTION_ERROR: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Could not extract target path from user message",
        manual_action_hint="请明确指定目标路径，如：/home/user/file.txt"
    ),
    
    # ------------------------------------------------------------------------
    # SAFETY: Safety blocks - Require explicit user confirmation
    # ------------------------------------------------------------------------
    
    FailureClass.SAFETY_BLOCK: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="blocked",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Operation blocked by safety rules",
        manual_action_hint="如需执行危险操作，请使用 /confirm 确认"
    ),
    
    # ------------------------------------------------------------------------
    # PERMISSION: Permission errors - Require manual fix
    # ------------------------------------------------------------------------
    
    FailureClass.PERMISSION_ERROR: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Insufficient permissions",
        manual_action_hint="请检查文件/目录权限，或使用有权限的账户"
    ),
    
    # ------------------------------------------------------------------------
    # VALIDATION: Input validation errors - Require user correction
    # ------------------------------------------------------------------------
    
    FailureClass.VALIDATION_ERROR: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Input validation failed",
        manual_action_hint="请检查输入参数是否正确"
    ),
    
    FailureClass.UNSUPPORTED: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Operation not supported",
        manual_action_hint="该操作不支持，请选择其他方式"
    ),
    
    # ------------------------------------------------------------------------
    # NOT_FOUND: Resource not found - May be retryable if resource created later
    # ------------------------------------------------------------------------
    
    FailureClass.NOT_FOUND: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=True,   # Allow heartbeat to check again
        allow_cron_resume=True,        # Allow cron to check again
        retry_limit=2,                 # Limited retries
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.NOTIFY_ONLY,
        reason="Resource not found, may be created later",
        manual_action_hint="目标不存在，请确认路径或先创建资源"
    ),
    
    # ------------------------------------------------------------------------
    # TRANSIENT: Retryable failures - Auto-retry with backoff
    # ------------------------------------------------------------------------
    
    FailureClass.TIMEOUT: FailurePolicyEntry(
        allow_auto_retry=True,
        allow_heartbeat_resume=True,
        allow_cron_resume=True,
        retry_limit=3,
        final_state="failed",
        user_notification_required=False,  # Only notify on final failure
        background_action=BackgroundAction.RETRY,
        reason="Transient timeout, retryable"
    ),
    
    FailureClass.ENVIRONMENT_ERROR: FailurePolicyEntry(
        allow_auto_retry=True,
        allow_heartbeat_resume=True,
        allow_cron_resume=True,
        retry_limit=3,
        final_state="failed",
        user_notification_required=False,
        background_action=BackgroundAction.RETRY,
        reason="Transient environment error, retryable"
    ),
    
    FailureClass.MODEL_ERROR: FailurePolicyEntry(
        allow_auto_retry=True,
        allow_heartbeat_resume=True,
        allow_cron_resume=True,
        retry_limit=3,
        final_state="failed",
        user_notification_required=False,
        background_action=BackgroundAction.RETRY,
        reason="LLM/Model transient error, retryable"
    ),
    
    FailureClass.TOOL_ERROR: FailurePolicyEntry(
        allow_auto_retry=True,
        allow_heartbeat_resume=True,
        allow_cron_resume=True,
        retry_limit=2,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.RETRY,
        reason="Tool execution failed, may be retryable"
    ),
    
    # ------------------------------------------------------------------------
    # TASK_LOGIC: Task design issues - Require manual fix
    # ------------------------------------------------------------------------
    
    FailureClass.TASK_LOGIC_ERROR: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Task planning/step design issue",
        manual_action_hint="任务设计有问题，请重新规划步骤"
    ),
    
    # ------------------------------------------------------------------------
    # UNKNOWN: Unknown failures - Conservative approach
    # ------------------------------------------------------------------------
    
    FailureClass.UNKNOWN: FailurePolicyEntry(
        allow_auto_retry=False,
        allow_heartbeat_resume=False,
        allow_cron_resume=False,
        retry_limit=0,
        final_state="failed",
        user_notification_required=True,
        background_action=BackgroundAction.BLOCK_MANUAL,
        reason="Unknown failure, requires investigation",
        manual_action_hint="发生未知错误，请联系管理员或查看日志"
    ),
}


# ============================================================================
# Helper Functions
# ============================================================================

def get_failure_policy(failure_class: FailureClass) -> FailurePolicyEntry:
    """
    Get the background policy for a failure class.
    
    Args:
        failure_class: The failure classification
    
    Returns:
        FailurePolicyEntry with background action rules
    """
    return FAILURE_POLICY.get(failure_class, FAILURE_POLICY[FailureClass.UNKNOWN])


def should_heartbeat_resume(failure_class: FailureClass) -> bool:
    """Check if heartbeat driver can resume after this failure."""
    policy = get_failure_policy(failure_class)
    return policy.allow_heartbeat_resume


def should_cron_resume(failure_class: FailureClass) -> bool:
    """Check if cron driver can resume after this failure."""
    policy = get_failure_policy(failure_class)
    return policy.allow_cron_resume


def can_auto_retry(failure_class: FailureClass, current_retry: int = 0) -> bool:
    """
    Check if auto-retry is allowed for this failure class.
    
    Args:
        failure_class: The failure classification
        current_retry: Current retry count
    
    Returns:
        True if retry is allowed and limit not reached
    """
    policy = get_failure_policy(failure_class)
    return policy.allow_auto_retry and current_retry < policy.retry_limit


def get_background_action(failure_class: FailureClass) -> BackgroundAction:
    """Get the recommended background action for a failure."""
    policy = get_failure_policy(failure_class)
    return policy.background_action


def requires_user_notification(failure_class: FailureClass) -> bool:
    """Check if user notification is required for this failure."""
    policy = get_failure_policy(failure_class)
    return policy.user_notification_required


def get_manual_action_hint(failure_class: FailureClass) -> Optional[str]:
    """Get the manual action hint for a failure."""
    policy = get_failure_policy(failure_class)
    return policy.manual_action_hint


# ============================================================================
# False Success Prevention
# ============================================================================

# Failures that MUST NOT be auto-retried to "completed"
# These represent "tool succeeded but goal not achieved"
FALSE_SUCCESS_FAILURES: Set[FailureClass] = {
    FailureClass.INTENT_MISMATCH,
    FailureClass.POSTCONDITION_FAILED,
    FailureClass.PATH_EXTRACTION_ERROR,
}

# Failures that block background resume
BACKGROUND_BLOCKED_FAILURES: Set[FailureClass] = {
    FailureClass.INTENT_MISMATCH,
    FailureClass.POSTCONDITION_FAILED,
    FailureClass.PATH_EXTRACTION_ERROR,
    FailureClass.SAFETY_BLOCK,
    FailureClass.PERMISSION_ERROR,
    FailureClass.VALIDATION_ERROR,
    FailureClass.UNSUPPORTED,
    FailureClass.TASK_LOGIC_ERROR,
    FailureClass.UNKNOWN,
}

# Failures that allow retry (transient)
RETRYABLE_FAILURES: Set[FailureClass] = {
    FailureClass.TIMEOUT,
    FailureClass.ENVIRONMENT_ERROR,
    FailureClass.MODEL_ERROR,
    FailureClass.TOOL_ERROR,
    FailureClass.NOT_FOUND,  # Limited retry
}


def is_false_success_failure(failure_class: FailureClass) -> bool:
    """
    Check if this failure represents a "false success" scenario.
    
    These failures indicate that the tool executed successfully,
    but the user's actual goal was not achieved.
    
    Such failures MUST NOT be auto-retried to "completed" state.
    """
    return failure_class in FALSE_SUCCESS_FAILURES


def is_background_blocked(failure_class: FailureClass) -> bool:
    """
    Check if background resume is blocked for this failure.
    
    Background drivers should not attempt to resume tasks
    with these failure classes.
    """
    return failure_class in BACKGROUND_BLOCKED_FAILURES


def is_retryable_failure(failure_class: FailureClass) -> bool:
    """Check if this failure is retryable by background drivers."""
    return failure_class in RETRYABLE_FAILURES
