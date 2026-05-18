"""
P2-B: Background Progression Tests

Tests for:
- P2-B.1: Failure Policy
- P2-B.2: Heartbeat Driver
- P2-B.3: Cron Recovery Driver
- P2-B.4: Foreground/Background Guard
- P2-B.5: Notification Policy
- P2-B.6: Status Query
"""

import pytest
from datetime import datetime, timedelta

from app.runtime.execution_result import FailureClass, ExecutionStatus
from app.runtime.failure_policy import (
    get_failure_policy,
    should_heartbeat_resume,
    should_cron_resume,
    can_auto_retry,
    is_false_success_failure,
    is_background_blocked,
    BackgroundAction,
)
from app.runtime.guard import (
    ExecutionMode,
    ForegroundSession,
    can_background_process,
    get_execution_mode,
    mark_foreground_start,
    mark_foreground_end,
    bind_task_to_foreground,
)
from app.runtime.notification_policy import (
    NotificationType,
    should_notify,
    MUST_NOTIFY,
    DEFAULT_NOT_NOTIFY,
)
from app.runtime.status_query import (
    TaskStatusSummary,
    build_status_summary,
)
from app.storage.models import Task, TaskStatus, TaskStep, TaskStepStatus


# ============================================================================
# P2-B.1: Failure Policy Tests
# ============================================================================

class TestFailurePolicy:
    """Tests for P2-B.1: Failure Policy."""
    
    def test_intent_mismatch_not_retryable(self):
        """INTENT_MISMATCH should never be auto-retried."""
        policy = get_failure_policy(FailureClass.INTENT_MISMATCH)
        
        assert policy.allow_auto_retry is False
        assert policy.allow_heartbeat_resume is False
        assert policy.allow_cron_resume is False
        assert policy.background_action == BackgroundAction.BLOCK_MANUAL
    
    def test_postcondition_failed_not_retryable(self):
        """POSTCONDITION_FAILED should never be auto-retried."""
        policy = get_failure_policy(FailureClass.POSTCONDITION_FAILED)
        
        assert policy.allow_auto_retry is False
        assert policy.allow_heartbeat_resume is False
        assert policy.allow_cron_resume is False
    
    def test_path_extraction_error_not_retryable(self):
        """PATH_EXTRACTION_ERROR should never be auto-retried."""
        policy = get_failure_policy(FailureClass.PATH_EXTRACTION_ERROR)
        
        assert policy.allow_auto_retry is False
        assert policy.allow_heartbeat_resume is False
        assert policy.allow_cron_resume is False
    
    def test_timeout_is_retryable(self):
        """TIMEOUT should be retryable."""
        policy = get_failure_policy(FailureClass.TIMEOUT)
        
        assert policy.allow_auto_retry is True
        assert policy.allow_heartbeat_resume is True
        assert policy.allow_cron_resume is True
        assert policy.retry_limit == 3
    
    def test_environment_error_is_retryable(self):
        """ENVIRONMENT_ERROR should be retryable."""
        policy = get_failure_policy(FailureClass.ENVIRONMENT_ERROR)
        
        assert policy.allow_auto_retry is True
        assert policy.background_action == BackgroundAction.RETRY
    
    def test_safety_block_requires_manual(self):
        """SAFETY_BLOCK should require manual intervention."""
        policy = get_failure_policy(FailureClass.SAFETY_BLOCK)
        
        assert policy.allow_auto_retry is False
        assert policy.user_notification_required is True
        assert policy.background_action == BackgroundAction.BLOCK_MANUAL
    
    def test_is_false_success_failure(self):
        """False success failures should be identified."""
        assert is_false_success_failure(FailureClass.INTENT_MISMATCH) is True
        assert is_false_success_failure(FailureClass.POSTCONDITION_FAILED) is True
        assert is_false_success_failure(FailureClass.PATH_EXTRACTION_ERROR) is True
        assert is_false_success_failure(FailureClass.TIMEOUT) is False
        assert is_false_success_failure(FailureClass.TOOL_ERROR) is False
    
    def test_is_background_blocked(self):
        """Background blocked failures should be identified."""
        assert is_background_blocked(FailureClass.INTENT_MISMATCH) is True
        assert is_background_blocked(FailureClass.SAFETY_BLOCK) is True
        assert is_background_blocked(FailureClass.PERMISSION_ERROR) is True
        assert is_background_blocked(FailureClass.TIMEOUT) is False
        assert is_background_blocked(FailureClass.NOT_FOUND) is False
    
    def test_can_auto_retry_with_limit(self):
        """Auto retry should respect retry limit."""
        # TIMEOUT allows 3 retries
        assert can_auto_retry(FailureClass.TIMEOUT, 0) is True
        assert can_auto_retry(FailureClass.TIMEOUT, 1) is True
        assert can_auto_retry(FailureClass.TIMEOUT, 2) is True
        assert can_auto_retry(FailureClass.TIMEOUT, 3) is False  # At limit
        
        # INTENT_MISMATCH never allows retry
        assert can_auto_retry(FailureClass.INTENT_MISMATCH, 0) is False
    
    def test_intent_mismatch_user_notification_required(self):
        """INTENT_MISMATCH should require user notification."""
        policy = get_failure_policy(FailureClass.INTENT_MISMATCH)
        assert policy.user_notification_required is True
        assert policy.manual_action_hint is not None


class TestFalseSuccessPrevention:
    """Tests for preventing false-success scenarios."""
    
    def test_intent_mismatch_cannot_become_completed_via_retry(self):
        """
        Verify that INTENT_MISMATCH cannot be auto-retried to completed.
        
        This is the core protection against "fake completed" scenarios.
        """
        # Given: A task failed with INTENT_MISMATCH
        failure_class = FailureClass.INTENT_MISMATCH
        
        # When: Checking if background can resume
        can_heartbeat = should_heartbeat_resume(failure_class)
        can_cron = should_cron_resume(failure_class)
        is_blocked = is_background_blocked(failure_class)
        
        # Then: All should be False
        assert can_heartbeat is False
        assert can_cron is False
        assert is_blocked is True
        
        # And: Auto-retry is not allowed
        assert can_auto_retry(failure_class, 0) is False
    
    def test_postcondition_failed_cannot_become_completed_via_retry(self):
        """Verify that POSTCONDITION_FAILED cannot be auto-retried."""
        failure_class = FailureClass.POSTCONDITION_FAILED
        
        assert should_heartbeat_resume(failure_class) is False
        assert should_cron_resume(failure_class) is False
        assert can_auto_retry(failure_class, 0) is False


# ============================================================================
# P2-B.2: Heartbeat Driver Tests
# ============================================================================

class TestHeartbeatDriver:
    """Tests for P2-B.2: Heartbeat Driver."""
    
    def test_heartbeat_config_defaults(self):
        """Verify default heartbeat configuration."""
        from app.runtime.heartbeat_driver import HeartbeatConfig, HeartbeatDriver
        
        config = HeartbeatConfig()
        assert config.scan_interval_seconds == 30
        assert config.max_concurrent_tasks == 3
        assert config.lease_duration_seconds == 60
    
    def test_lease_management(self):
        """Test lease acquisition and release."""
        from app.runtime.heartbeat_driver import HeartbeatDriver
        
        driver = HeartbeatDriver()
        
        # Acquire lease
        assert driver.acquire_lease("task_1", "heartbeat") is True
        
        # Cannot acquire again
        assert driver.acquire_lease("task_1", "heartbeat") is False
        
        # Release and reacquire
        driver.release_lease("task_1")
        assert driver.acquire_lease("task_1", "heartbeat") is True
    
    def test_lease_expiration(self):
        """Test lease expiration."""
        from app.runtime.heartbeat_driver import HeartbeatDriver, HeartbeatConfig
        
        config = HeartbeatConfig(lease_duration_seconds=1)
        driver = HeartbeatDriver(config)
        
        # Acquire lease
        assert driver.acquire_lease("task_1", "heartbeat") is True
        
        # Manually expire lease
        from datetime import datetime, timedelta
        driver._leases["task_1"].expires_at = datetime.now() - timedelta(seconds=1)
        
        # Should be able to acquire again
        assert driver.acquire_lease("task_1", "heartbeat") is True


# ============================================================================
# P2-B.3: Cron Recovery Driver Tests
# ============================================================================

class TestCronDriver:
    """Tests for P2-B.3: Cron Recovery Driver."""
    
    def test_cron_config_defaults(self):
        """Verify default cron configuration."""
        from app.runtime.cron_driver import CronConfig
        
        config = CronConfig()
        assert config.scan_interval_seconds == 300  # 5 minutes
        assert config.max_recovery_per_scan == 5
        assert config.max_recovery_attempts == 2
    
    def test_cron_never_retries_false_success(self):
        """Verify cron never retries false-success failures."""
        from app.runtime.cron_driver import CronRecoveryDriver
        from app.runtime.failure_policy import is_false_success_failure
        
        # False success failures
        for fc in [FailureClass.INTENT_MISMATCH, FailureClass.POSTCONDITION_FAILED, 
                   FailureClass.PATH_EXTRACTION_ERROR]:
            assert is_false_success_failure(fc) is True
            assert should_cron_resume(fc) is False


# ============================================================================
# P2-B.4: Foreground/Background Guard Tests
# ============================================================================

class TestForegroundBackgroundGuard:
    """Tests for P2-B.4: Foreground/Background Guard."""
    
    def test_foreground_session_context_manager(self):
        """Test foreground session context manager."""
        with ForegroundSession("session_1", "chat_1", "user_1") as session:
            session.bind_task("task_1")
            
            # Task should be in foreground
            assert get_execution_mode("task_1") == ExecutionMode.FOREGROUND
        
        # After context exit, task should not be in foreground
        # (session unregistered)
    
    def test_background_cannot_process_foreground_task(self):
        """Background should not process tasks in active foreground session."""
        # Register foreground session
        mark_foreground_start("session_1", "chat_1", "user_1")
        bind_task_to_foreground("session_1", "task_1")
        
        # Create mock task
        task = Task(
            id="task_1",
            objective="Test task",
            status=TaskStatus.RUNNING
        )
        task.scope_key = "tg:chat_1:user_1"
        
        # Check if background can process
        can_process, reason = can_background_process(task)
        
        assert can_process is False
        assert "foreground" in reason.lower()
        
        # Cleanup
        mark_foreground_end("session_1")
    
    def test_execution_mode_detection(self):
        """Test execution mode detection."""
        # Register session
        mark_foreground_start("session_1")
        bind_task_to_foreground("session_1", "task_1")
        
        # Task in foreground
        assert get_execution_mode("task_1") == ExecutionMode.FOREGROUND
        
        # Unknown task in background
        assert get_execution_mode("unknown_task") == ExecutionMode.BACKGROUND
        
        # Cleanup
        mark_foreground_end("session_1")
    
    def test_reply_channel_guard(self):
        """Test reply channel guard."""
        from app.runtime.guard import get_reply_guard
        
        guard = get_reply_guard()
        
        # Background cannot send heartbeat tick
        assert guard.can_send_notification("heartbeat_tick", ExecutionMode.BACKGROUND) is False
        
        # Background can send completed notification
        assert guard.can_send_notification("completed", ExecutionMode.BACKGROUND) is True
        
        # Foreground can send any
        assert guard.can_send_notification("heartbeat_tick", ExecutionMode.FOREGROUND) is True


# ============================================================================
# P2-B.5: Notification Policy Tests
# ============================================================================

class TestNotificationPolicy:
    """Tests for P2-B.5: Notification Policy."""
    
    def test_must_notify_types(self):
        """Verify must-notify types."""
        assert NotificationType.TASK_COMPLETED in MUST_NOTIFY
        assert NotificationType.TASK_BLOCKED in MUST_NOTIFY
        assert NotificationType.MANUAL_ACTION_REQUIRED in MUST_NOTIFY
        assert NotificationType.INTENT_MISMATCH_BLOCKED in MUST_NOTIFY
    
    def test_default_not_notify_types(self):
        """Verify default-not-notify types."""
        assert NotificationType.HEARTBEAT_TICK in DEFAULT_NOT_NOTIFY
        assert NotificationType.CRON_TICK in DEFAULT_NOT_NOTIFY
        assert NotificationType.RETRY_ATTEMPT in DEFAULT_NOT_NOTIFY
    
    def test_should_notify_completed_always(self):
        """Completed notification should always be sent."""
        assert should_notify(NotificationType.TASK_COMPLETED, ExecutionMode.FOREGROUND) is True
        assert should_notify(NotificationType.TASK_COMPLETED, ExecutionMode.BACKGROUND) is True
    
    def test_should_not_notify_heartbeat_tick_in_background(self):
        """Heartbeat tick should not be notified in background."""
        assert should_notify(NotificationType.HEARTBEAT_TICK, ExecutionMode.BACKGROUND) is False
    
    def test_failure_notification_required(self):
        """Test failure notification requirement."""
        from app.runtime.notification_policy import get_notification_for_failure
        
        # INTENT_MISMATCH should generate notification
        payload = get_notification_for_failure(
            FailureClass.INTENT_MISMATCH,
            "task_1",
            "foreground"
        )
        
        assert payload is not None
        assert payload.type == NotificationType.INTENT_MISMATCH_BLOCKED
        assert payload.manual_action_hint is not None


# ============================================================================
# P2-B.6: Status Query Tests
# ============================================================================

class TestStatusQuery:
    """Tests for P2-B.6: Status Query."""
    
    def test_build_status_summary(self):
        """Test building status summary."""
        task = Task(
            id="task_test",
            objective="Test objective",
            status=TaskStatus.RUNNING
        )
        task.created_at = datetime.now()
        task.updated_at = datetime.now()
        
        summary = build_status_summary(task)
        
        assert summary.task_id == "task_test"
        assert summary.current_status == "running"
        assert summary.objective == "Test objective"
    
    def test_build_status_summary_with_failure(self):
        """Test building status summary with failure."""
        task = Task(
            id="task_blocked",
            objective="Blocked task",
            status=TaskStatus.BLOCKED
        )
        task.error = "[intent_mismatch] Wrong operation"
        task.metadata = {"retry_count": 1, "trigger_source": "heartbeat"}
        
        summary = build_status_summary(task)
        
        assert summary.current_status == "blocked"
        assert summary.failure_class == "intent_mismatch"
        assert summary.retry_count == 1
        assert summary.trigger_source == "heartbeat"
        assert summary.blocked_reason == "Wrong operation"
    
    def test_status_summary_to_markdown(self):
        """Test markdown formatting."""
        summary = TaskStatusSummary(
            task_id="task_1",
            current_status="blocked",
            objective="Test task",
            failure_class="intent_mismatch",
            blocked_reason="Wrong operation",
            manual_action_hint="Please retry with correct intent"
        )
        
        md = summary.to_markdown()
        
        assert "任务状态" in md
        assert "task_1" in md
        assert "intent_mismatch" in md
        assert "建议" in md


# ============================================================================
# Integration Tests
# ============================================================================

class TestP2BIntegration:
    """Integration tests for P2-B components."""
    
    def test_false_success_prevention_e2e(self):
        """
        End-to-end test for false success prevention.
        
        Scenario:
        1. Task fails with INTENT_MISMATCH
        2. Heartbeat tries to resume
        3. Policy blocks resume
        4. User is notified
        """
        # 1. Task fails with INTENT_MISMATCH
        failure_class = FailureClass.INTENT_MISMATCH
        
        # 2. Heartbeat checks if can resume
        can_heartbeat = should_heartbeat_resume(failure_class)
        
        # 3. Policy blocks
        assert can_heartbeat is False
        assert is_background_blocked(failure_class) is True
        
        # 4. User notification required
        policy = get_failure_policy(failure_class)
        assert policy.user_notification_required is True
        assert policy.manual_action_hint is not None
    
    def test_transient_failure_retry_flow(self):
        """
        Test transient failure retry flow.
        
        Scenario:
        1. Task fails with TIMEOUT
        2. Heartbeat can resume
        3. Retry within limit
        4. Eventually succeeds or hits limit
        """
        failure_class = FailureClass.TIMEOUT
        
        # 1. Check can resume
        assert should_heartbeat_resume(failure_class) is True
        assert should_cron_resume(failure_class) is True
        
        # 2. Check can retry
        assert can_auto_retry(failure_class, 0) is True
        assert can_auto_retry(failure_class, 1) is True
        assert can_auto_retry(failure_class, 2) is True
        assert can_auto_retry(failure_class, 3) is False  # Limit reached
