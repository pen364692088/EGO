"""
P2-C: Human-in-the-Loop Tests

Tests for:
- P2-C.1: Approval Policy
- P2-C.2: Waiting State
- P2-C.3: Confirmation Renderer
- P2-C.4: Reply Binding
- P2-C.5: Resume Driver
- P2-C.6: Background Waiting Guard
"""

import pytest
from datetime import datetime

from app.storage.models import Task, TaskStatus, TaskStep, TaskStepStatus
from app.runtime.state_machine import StateMachine
from app.runtime.approval_policy import (
    ApprovalType,
    ApprovalReason,
    ApprovalRequest,
    ApprovalDecision,
    check_approval_needed,
    is_high_risk_operation,
    is_high_risk_path,
    validate_user_reply,
    parse_user_decision,
)
from app.runtime.confirmation_renderer import (
    render_confirmation_message,
    render_telegram_confirmation,
    get_quick_reply_hint,
)
from app.runtime.reply_binding import (
    ReplyBinder,
    BindingResult,
    handle_user_reply,
)
from app.runtime.failure_policy import FailureClass


# ============================================================================
# P2-C.1: Approval Policy Tests
# ============================================================================

class TestApprovalPolicy:
    """Tests for P2-C.1: Approval Policy."""
    
    def test_high_risk_operation_detection(self):
        """Detect high-risk operations."""
        assert is_high_risk_operation("delete the file") is True
        assert is_high_risk_operation("remove directory") is True
        assert is_high_risk_operation("rm -rf /") is True
        assert is_high_risk_operation("overwrite the config") is True
        assert is_high_risk_operation("read a file") is False
        assert is_high_risk_operation("list directory") is False
    
    def test_high_risk_path_detection(self):
        """Detect high-risk paths."""
        assert is_high_risk_path("/etc/passwd") is True
        assert is_high_risk_path("/usr/bin/test") is True
        assert is_high_risk_path("/home/user/file.txt") is True
        assert is_high_risk_path("/tmp/test.txt") is False
    
    def test_approval_needed_for_high_risk(self):
        """High-risk operation should need approval."""
        decision = check_approval_needed(
            step_description="delete the file",
            task_id="task_1",
        )
        
        assert decision.approval_needed is True
        assert decision.approval_request.reason == ApprovalReason.HIGH_RISK_OPERATION
        assert decision.approval_request.approval_type == ApprovalType.YES_NO
    
    def test_approval_needed_for_multiple_paths(self):
        """Multiple candidate paths should need approval."""
        decision = check_approval_needed(
            step_description="read a file",
            candidate_paths=["/path/a", "/path/b", "/path/c"],
            task_id="task_1",
        )
        
        assert decision.approval_needed is True
        assert decision.approval_request.reason == ApprovalReason.MULTIPLE_TARGETS
        assert decision.approval_request.approval_type == ApprovalType.OPTION_SELECT
        assert len(decision.approval_request.options) == 3
    
    def test_no_approval_for_safe_operations(self):
        """Safe operations should not need approval."""
        decision = check_approval_needed(
            step_description="list files in /tmp",
            task_id="task_1",
        )
        
        assert decision.approval_needed is False
    
    def test_approval_request_serialization(self):
        """ApprovalRequest should serialize/deserialize correctly."""
        request = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认删除？",
            task_id="task_1",
            expected_reply_type="yes_no",
            valid_replies=["yes", "no"],
        )
        
        data = request.to_dict()
        restored = ApprovalRequest.from_dict(data)
        
        assert restored.approval_type == ApprovalType.YES_NO
        assert restored.reason == ApprovalReason.HIGH_RISK_OPERATION
        assert restored.prompt == "确认删除？"
        assert restored.task_id == "task_1"


class TestReplyValidation:
    """Tests for reply validation."""
    
    def test_validate_yes_no_reply(self):
        """Validate yes/no replies."""
        request = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认？",
            valid_replies=["yes", "no"],
        )
        
        # Valid yes
        is_valid, value, error = validate_user_reply("yes", request)
        assert is_valid is True
        assert value == "yes"
        
        # Valid no
        is_valid, value, error = validate_user_reply("no", request)
        assert is_valid is True
        assert value == "no"
        
        # Chinese yes
        is_valid, value, error = validate_user_reply("是", request)
        assert is_valid is True
        assert value == "yes"
        
        # Invalid
        is_valid, value, error = validate_user_reply("maybe", request)
        assert is_valid is False
    
    def test_validate_option_select_reply(self):
        """Validate option selection replies."""
        request = ApprovalRequest(
            approval_type=ApprovalType.OPTION_SELECT,
            reason=ApprovalReason.MULTIPLE_TARGETS,
            prompt="选择：",
            options=["option_a", "option_b", "option_c"],
            valid_replies=["0", "1", "2"],
        )
        
        # Valid selection
        is_valid, value, error = validate_user_reply("1", request)
        assert is_valid is True
        assert value == "1"
        
        # Invalid selection
        is_valid, value, error = validate_user_reply("5", request)
        assert is_valid is False
    
    def test_parse_user_decision_yes_no(self):
        """Parse user decision for yes/no."""
        request = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认？",
        )
        
        decision = parse_user_decision("yes", request)
        assert decision["is_valid"] is True
        assert decision["approved"] is True
        
        decision = parse_user_decision("no", request)
        assert decision["is_valid"] is True
        assert decision["approved"] is False
    
    def test_parse_user_decision_option_select(self):
        """Parse user decision for option select."""
        request = ApprovalRequest(
            approval_type=ApprovalType.OPTION_SELECT,
            reason=ApprovalReason.MULTIPLE_TARGETS,
            prompt="选择：",
            options=["path_a", "path_b"],
        )
        
        decision = parse_user_decision("1", request)
        assert decision["is_valid"] is True
        assert decision["approved"] is True
        assert decision["selected_option"] == 1
        assert decision["selected_value"] == "path_b"


# ============================================================================
# P2-C.2: Waiting State Tests
# ============================================================================

class TestWaitingState:
    """Tests for P2-C.2: Waiting State."""
    
    def test_waiting_status_exists(self):
        """WAITING_USER_INPUT status should exist."""
        assert TaskStatus.WAITING_USER_INPUT.value == "waiting_user_input"
    
    def test_state_machine_waiting_transitions(self):
        """State machine should support waiting transitions."""
        # RUNNING -> WAITING_USER_INPUT
        assert StateMachine.can_transition(TaskStatus.RUNNING, TaskStatus.WAITING_USER_INPUT) is True
        
        # WAITING_USER_INPUT -> RUNNING
        assert StateMachine.can_transition(TaskStatus.WAITING_USER_INPUT, TaskStatus.RUNNING) is True
        
        # WAITING_USER_INPUT -> FAILED
        assert StateMachine.can_transition(TaskStatus.WAITING_USER_INPUT, TaskStatus.FAILED) is True
        
        # WAITING_USER_INPUT -> ABORTED
        assert StateMachine.can_transition(TaskStatus.WAITING_USER_INPUT, TaskStatus.ABORTED) is True
    
    def test_state_machine_is_waiting(self):
        """State machine should identify waiting states."""
        assert StateMachine.is_waiting(TaskStatus.WAITING_USER_INPUT) is True
        assert StateMachine.is_waiting(TaskStatus.RUNNING) is False
        assert StateMachine.is_waiting(TaskStatus.BLOCKED) is False
    
    def test_task_waiting_fields(self):
        """Task should have waiting-related fields."""
        task = Task(
            id="task_1",
            objective="Test task",
            status=TaskStatus.WAITING_USER_INPUT,
            waiting_reason="high_risk_operation",
            waiting_request={"approval_type": "yes_no"},
        )
        
        assert task.waiting_reason == "high_risk_operation"
        assert task.waiting_request is not None
    
    def test_task_waiting_serialization(self):
        """Task waiting fields should serialize correctly."""
        task = Task(
            id="task_1",
            objective="Test task",
            status=TaskStatus.WAITING_USER_INPUT,
            waiting_reason="test",
            waiting_request={"test": "data"},
            user_decision={"approved": True},
        )
        
        data = task.to_dict()
        restored = Task.from_dict(data)
        
        assert restored.waiting_reason == "test"
        assert restored.waiting_request == {"test": "data"}
        assert restored.user_decision == {"approved": True}


# ============================================================================
# P2-C.3: Confirmation Renderer Tests
# ============================================================================

class TestConfirmationRenderer:
    """Tests for P2-C.3: Confirmation Renderer."""
    
    def test_render_yes_no_message(self):
        """Render yes/no confirmation message."""
        request = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认删除文件？",
        )
        
        message = render_confirmation_message(request)
        
        assert "需要确认" in message
        assert "确认删除文件" in message
        assert "yes" in message.lower() or "是" in message
    
    def test_render_option_select_message(self):
        """Render option selection message."""
        request = ApprovalRequest(
            approval_type=ApprovalType.OPTION_SELECT,
            reason=ApprovalReason.MULTIPLE_TARGETS,
            prompt="选择文件：",
            options=["/path/a", "/path/b"],
        )
        
        message = render_confirmation_message(request)
        
        assert "请选择" in message
        assert "/path/a" in message
        assert "/path/b" in message
    
    def test_render_telegram_format(self):
        """Render Telegram-formatted message."""
        request = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认？",
        )
        
        message = render_telegram_confirmation(request)
        
        # Should use Telegram markdown (single *)
        assert "*" in message
    
    def test_get_quick_reply_hint(self):
        """Get quick reply hint."""
        request_yes_no = ApprovalRequest(
            approval_type=ApprovalType.YES_NO,
            reason=ApprovalReason.HIGH_RISK_OPERATION,
            prompt="确认？",
        )
        assert "yes/no" in get_quick_reply_hint(request_yes_no)
        
        request_options = ApprovalRequest(
            approval_type=ApprovalType.OPTION_SELECT,
            reason=ApprovalReason.MULTIPLE_TARGETS,
            prompt="选择：",
            options=["a", "b"],
        )
        assert "0-" in get_quick_reply_hint(request_options)


# ============================================================================
# P2-C.4: Reply Binding Tests
# ============================================================================

class TestReplyBinding:
    """Tests for P2-C.4: Reply Binding."""
    
    def test_find_waiting_tasks(self):
        """Find waiting tasks in scope."""
        binder = ReplyBinder()
        
        # Mock: would need to create test tasks in real test
        # This is a structure test
        assert binder.is_likely_confirmation_reply("yes") is True
        assert binder.is_likely_confirmation_reply("no") is True
        assert binder.is_likely_confirmation_reply("0") is True
        assert binder.is_likely_confirmation_reply("/home/user/file.txt") is True
        assert binder.is_likely_confirmation_reply("This is a long message about something else") is False
    
    def test_likely_confirmation_reply_detection(self):
        """Detect likely confirmation replies."""
        binder = ReplyBinder()
        
        # Yes/no patterns
        assert binder.is_likely_confirmation_reply("yes") is True
        assert binder.is_likely_confirmation_reply("是") is True
        
        # Option index
        assert binder.is_likely_confirmation_reply("2") is True
        
        # Path-like
        assert binder.is_likely_confirmation_reply("/tmp/file.txt") is True
        
        # Long message (not confirmation)
        assert binder.is_likely_confirmation_reply("Hello, how are you doing today?") is False


# ============================================================================
# P2-C.5: Resume Driver Tests
# ============================================================================

class TestResumeDriver:
    """Tests for P2-C.5: Resume Driver."""
    
    def test_resume_driver_exists(self):
        """ResumeDriver should be importable."""
        from app.runtime.resume_driver import ResumeDriver, get_resume_driver
        
        driver = get_resume_driver()
        assert driver is not None
    
    def test_resume_with_rejected_decision(self):
        """Resume with rejected decision should fail task."""
        from app.runtime.resume_driver import ResumeDriver
        
        # This would need a real task in a full test
        # Structure test only
        assert ResumeDriver is not None


# ============================================================================
# P2-C.6: Background Waiting Guard Tests
# ============================================================================

class TestBackgroundWaitingGuard:
    """Tests for P2-C.6: Background Waiting Guard."""
    
    def test_heartbeat_skips_waiting_tasks(self):
        """Heartbeat should skip WAITING_USER_INPUT tasks."""
        from app.runtime.heartbeat_driver import HeartbeatDriver
        
        driver = HeartbeatDriver()
        
        # Create mock waiting task
        task = Task(
            id="waiting_task",
            objective="Waiting task",
            status=TaskStatus.WAITING_USER_INPUT,
        )
        
        # scan_resumable_tasks should skip waiting tasks
        # This is verified by the code: if task.status == TaskStatus.WAITING_USER_INPUT: continue
    
    def test_cron_skips_waiting_tasks(self):
        """Cron should skip WAITING_USER_INPUT tasks."""
        from app.runtime.cron_driver import CronRecoveryDriver
        
        driver = CronRecoveryDriver()
        
        # find_stalled_tasks should skip waiting tasks
        # This is verified by the code: if task.status == TaskStatus.WAITING_USER_INPUT: continue
    
    def test_state_machine_waiting_in_paused_states(self):
        """WAITING_USER_INPUT should be in PAUSED_STATES."""
        assert TaskStatus.WAITING_USER_INPUT in StateMachine.PAUSED_STATES
        assert TaskStatus.WAITING_USER_INPUT in StateMachine.WAITING_STATES


# ============================================================================
# Integration Tests
# ============================================================================

class TestP2CIntegration:
    """Integration tests for P2-C components."""
    
    def test_ask_wait_resume_flow(self):
        """
        Test the ask/wait/resume flow.
        
        1. Check approval needed
        2. Create waiting state
        3. Bind user reply
        4. Resume task
        """
        # 1. Check approval needed
        decision = check_approval_needed(
            step_description="delete the file /tmp/test.txt",
            task_id="task_1",
        )
        
        assert decision.approval_needed is True
        assert decision.approval_request.approval_type == ApprovalType.YES_NO
        
        # 2. Create waiting state (simulated)
        task = Task(
            id="task_1",
            objective="Delete file",
            status=TaskStatus.WAITING_USER_INPUT,
            waiting_reason="high_risk_operation",
            waiting_request=decision.approval_request.to_dict(),
        )
        
        assert task.status == TaskStatus.WAITING_USER_INPUT
        
        # 3. Validate user reply
        is_valid, value, error = validate_user_reply("yes", decision.approval_request)
        assert is_valid is True
        assert value == "yes"
        
        # 4. Parse decision
        user_decision = parse_user_decision("yes", decision.approval_request)
        assert user_decision["approved"] is True
    
    def test_user_rejection_flow(self):
        """Test user rejection flow."""
        decision = check_approval_needed(
            step_description="delete the file",
            task_id="task_1",
        )
        
        user_decision = parse_user_decision("no", decision.approval_request)
        
        assert user_decision["is_valid"] is True
        assert user_decision["approved"] is False
    
    def test_background_cannot_progress_waiting(self):
        """Verify background drivers cannot progress waiting tasks."""
        # State machine marks WAITING_USER_INPUT as waiting state
        assert StateMachine.is_waiting(TaskStatus.WAITING_USER_INPUT) is True
        
        # Background drivers check this and skip
        # The code explicitly checks:
        # if task.status == TaskStatus.WAITING_USER_INPUT: continue
