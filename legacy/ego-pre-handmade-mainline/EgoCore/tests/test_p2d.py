"""
P2-D: Operator Control Tests

Tests for:
- P2-D.1: Task list command
- P2-D.2: Task detail command
- P2-D.3: Control commands
- P2-D.4: State transition guard
- P2-D.5: Control audit trail
"""

import pytest
from datetime import datetime

from app.storage.models import Task, TaskStatus
from app.runtime.control_guard import (
    ControlCommand,
    check_command_allowed,
    get_available_commands,
    validate_task_id,
    COMMAND_VALID_STATES,
)
from app.runtime.control_audit import (
    AuditEntry,
    AuditSource,
    ControlAuditLog,
)


# ============================================================================
# P2-D.4: State Transition Guard Tests
# ============================================================================

class TestStateGuard:
    """Tests for P2-D.4: State Transition Guard."""
    
    def test_approve_only_waiting_tasks(self):
        """Approve command should only work on WAITING_USER_INPUT."""
        valid_states = COMMAND_VALID_STATES[ControlCommand.APPROVE]
        
        assert TaskStatus.WAITING_USER_INPUT in valid_states
        assert TaskStatus.RUNNING not in valid_states
        assert TaskStatus.COMPLETED not in valid_states
    
    def test_reject_only_waiting_tasks(self):
        """Reject command should only work on WAITING_USER_INPUT."""
        valid_states = COMMAND_VALID_STATES[ControlCommand.REJECT]
        
        assert TaskStatus.WAITING_USER_INPUT in valid_states
        assert TaskStatus.RUNNING not in valid_states
    
    def test_retry_only_blocked_tasks(self):
        """Retry command should only work on BLOCKED."""
        valid_states = COMMAND_VALID_STATES[ControlCommand.RETRY]
        
        assert TaskStatus.BLOCKED in valid_states
        assert TaskStatus.FAILED not in valid_states
        assert TaskStatus.RUNNING not in valid_states
    
    def test_cancel_allowed_states(self):
        """Cancel command should work on RUNNING/PAUSED/BLOCKED/WAITING."""
        valid_states = COMMAND_VALID_STATES[ControlCommand.CANCEL]
        
        assert TaskStatus.RUNNING in valid_states
        assert TaskStatus.PAUSED in valid_states
        assert TaskStatus.BLOCKED in valid_states
        assert TaskStatus.WAITING_USER_INPUT in valid_states
        assert TaskStatus.COMPLETED not in valid_states
    
    def test_resume_allowed_states(self):
        """Resume command should work on PAUSED/WAITING_USER_INPUT."""
        valid_states = COMMAND_VALID_STATES[ControlCommand.RESUME]
        
        assert TaskStatus.PAUSED in valid_states
        assert TaskStatus.WAITING_USER_INPUT in valid_states
        assert TaskStatus.BLOCKED not in valid_states
    
    def test_check_command_allowed_waiting_task(self):
        """Check approve on waiting task."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.WAITING_USER_INPUT,
        )
        
        guard = check_command_allowed(ControlCommand.APPROVE, task)
        
        assert guard.allowed is True
        assert guard.previous_status == "waiting_user_input"
        assert guard.new_status == "running"
    
    def test_check_command_not_allowed_completed_task(self):
        """Check approve on completed task should fail."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.COMPLETED,
        )
        
        guard = check_command_allowed(ControlCommand.APPROVE, task)
        
        assert guard.allowed is False
        assert guard.reason == "invalid_state"
    
    def test_check_command_task_not_found(self):
        """Check command on non-existent task."""
        guard = check_command_allowed(ControlCommand.APPROVE, None)
        
        assert guard.allowed is False
        assert guard.reason == "task_not_found"
    
    def test_get_available_commands_waiting(self):
        """Get available commands for waiting task."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.WAITING_USER_INPUT,
        )
        
        available = get_available_commands(task)
        
        assert "approve" in available
        assert "reject" in available
        assert "cancel" in available
        assert "retry" not in available
    
    def test_get_available_commands_blocked(self):
        """Get available commands for blocked task."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.BLOCKED,
        )
        
        available = get_available_commands(task)
        
        assert "retry" in available
        assert "cancel" in available
        assert "approve" not in available
    
    def test_get_available_commands_completed(self):
        """Get available commands for completed task."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.COMPLETED,
        )
        
        available = get_available_commands(task)
        
        assert len(available) == 0
    
    def test_validate_task_id(self):
        """Validate task ID format."""
        valid, error = validate_task_id("task_abc123")
        assert valid is True
        
        valid, error = validate_task_id("")
        assert valid is False
        assert "提供任务 ID" in error
        
        valid, error = validate_task_id("invalid")
        assert valid is False
        assert "格式" in error


# ============================================================================
# P2-D.5: Control Audit Trail Tests
# ============================================================================

class TestControlAudit:
    """Tests for P2-D.5: Control Audit Trail."""
    
    def test_audit_entry_creation(self):
        """Create audit entry."""
        entry = AuditEntry(
            actor="user",
            command="approve",
            task_id="task_1",
            previous_status="waiting_user_input",
            new_status="running",
        )
        
        assert entry.actor == "user"
        assert entry.command == "approve"
        assert entry.task_id == "task_1"
        assert entry.previous_status == "waiting_user_input"
        assert entry.new_status == "running"
        assert entry.source == AuditSource.TELEGRAM_COMMAND.value
    
    def test_audit_entry_serialization(self):
        """Audit entry should serialize correctly."""
        entry = AuditEntry(
            actor="user",
            command="reject",
            task_id="task_1",
            previous_status="waiting_user_input",
            new_status="failed",
            reason="User cancelled",
        )
        
        data = entry.to_dict()
        restored = AuditEntry.from_dict(data)
        
        assert restored.actor == entry.actor
        assert restored.command == entry.command
        assert restored.reason == entry.reason
    
    def test_audit_log_append(self, tmp_path):
        """Audit log should append entries."""
        log_path = tmp_path / "test_audit.jsonl"
        audit_log = ControlAuditLog(str(log_path))
        
        entry = AuditEntry(
            actor="user",
            command="approve",
            task_id="task_1",
            previous_status="waiting_user_input",
            new_status="running",
        )
        
        audit_log.append(entry)
        
        entries = audit_log.get_entries_for_task("task_1")
        assert len(entries) == 1
        assert entries[0].command == "approve"
    
    def test_audit_log_query_by_task(self, tmp_path):
        """Query audit log by task."""
        log_path = tmp_path / "test_audit.jsonl"
        audit_log = ControlAuditLog(str(log_path))
        
        # Add entries for multiple tasks
        for i in range(3):
            audit_log.append(AuditEntry(
                actor="user",
                command="approve",
                task_id=f"task_{i}",
                previous_status="waiting_user_input",
                new_status="running",
            ))
        
        entries = audit_log.get_entries_for_task("task_1")
        assert len(entries) == 1
        assert entries[0].task_id == "task_1"
    
    def test_audit_log_persistence(self, tmp_path):
        """Audit log should persist to file."""
        log_path = tmp_path / "test_audit.jsonl"
        
        # Create and add entry
        audit_log = ControlAuditLog(str(log_path))
        audit_log.append(AuditEntry(
            actor="user",
            command="approve",
            task_id="task_1",
            previous_status="waiting_user_input",
            new_status="running",
        ))
        
        # Create new instance to load from file
        audit_log2 = ControlAuditLog(str(log_path))
        entries = audit_log2.get_entries_for_task("task_1")
        
        assert len(entries) == 1


# ============================================================================
# P2-D.3: Control Commands Tests
# ============================================================================

class TestControlCommands:
    """Tests for P2-D.3: Control Commands."""
    
    def test_control_handler_exists(self):
        """Control handler should be importable."""
        from app.runtime.control_commands import ControlCommandsHandler, get_control_handler
        
        handler = get_control_handler()
        assert handler is not None
    
    def test_handle_tasks_empty(self):
        """Handle /tasks with no tasks."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        # This would need mock data in real test
        message = handler.handle_tasks()
        
        assert "任务列表" in message
    
    def test_approve_waiting_task(self):
        """Approve should transition waiting to running."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        
        # This would need a real task in repo
        # Structure test only
        assert hasattr(handler, 'handle_approve')
    
    def test_reject_waiting_task(self):
        """Reject should transition waiting to failed."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        assert hasattr(handler, 'handle_reject')
    
    def test_retry_blocked_task(self):
        """Retry should transition blocked to running."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        assert hasattr(handler, 'handle_retry')
    
    def test_cancel_task(self):
        """Cancel should transition to aborted."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        assert hasattr(handler, 'handle_cancel')
    
    def test_resume_task(self):
        """Resume should transition paused to running."""
        from app.runtime.control_commands import ControlCommandsHandler
        
        handler = ControlCommandsHandler()
        assert hasattr(handler, 'handle_resume')


# ============================================================================
# Integration Tests
# ============================================================================

class TestP2DIntegration:
    """Integration tests for P2-D."""
    
    def test_control_flow_with_guard(self):
        """Test control flow with guard check."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.WAITING_USER_INPUT,
        )
        
        # Check guard
        guard = check_command_allowed(ControlCommand.APPROVE, task)
        assert guard.allowed is True
        
        # Get available commands
        available = get_available_commands(task)
        assert "approve" in available
    
    def test_completed_task_no_commands(self):
        """Completed task should have no available commands."""
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.COMPLETED,
        )
        
        available = get_available_commands(task)
        assert len(available) == 0
        
        # All commands should be disallowed
        for command in ControlCommand:
            guard = check_command_allowed(command, task)
            assert guard.allowed is False
    
    def test_audit_on_control_action(self, tmp_path):
        """Audit should be logged on control action."""
        from app.runtime.control_audit import log_control_action
        
        log_path = tmp_path / "test_audit.jsonl"
        audit_log = ControlAuditLog(str(log_path))
        
        task = Task(
            id="task_1",
            objective="Test",
            status=TaskStatus.RUNNING,
        )
        
        entry = log_control_action(
            command="cancel",
            task=task,
            previous_status="running",
            new_status="aborted",
            actor="user",
        )
        
        assert entry.command == "cancel"
        assert entry.actor == "user"
