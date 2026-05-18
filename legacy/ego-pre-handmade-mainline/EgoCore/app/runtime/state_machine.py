"""
OpenEmotion Agent Runtime - Task State Machine

Defines valid state transitions for tasks.
"""

from typing import Dict, Set, Optional
from app.storage.models import TaskStatus


class StateMachine:
    """
    Task state machine with valid transitions.
    
    State diagram:
    
        created → planning → running → completed
            ↓         ↓         ↓
          aborted  paused   blocked
            ↓         ↓         ↓
          aborted  aborted   failed
                                ↓
                              aborted
    
    Valid transitions:
    - created → planning, aborted
    - planning → running, paused, aborted
    - running → paused, blocked, completed, failed, aborted
    - paused → running, aborted
    - blocked → running, failed, aborted
    - completed → (terminal)
    - failed → (terminal)
    - aborted → (terminal)
    """
    
    # Define valid transitions for each state
    TRANSITIONS: Dict[TaskStatus, Set[TaskStatus]] = {
        TaskStatus.CREATED: {
            TaskStatus.PLANNING,
            TaskStatus.ABORTED
        },
        TaskStatus.PLANNING: {
            TaskStatus.RUNNING,
            TaskStatus.PAUSED,
            TaskStatus.ABORTED
        },
        TaskStatus.RUNNING: {
            TaskStatus.PAUSED,
            TaskStatus.BLOCKED,
            TaskStatus.WAITING_USER_INPUT,  # P2-C: Can enter waiting
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.ABORTED
        },
        TaskStatus.PAUSED: {
            TaskStatus.RUNNING,
            TaskStatus.ABORTED
        },
        TaskStatus.BLOCKED: {
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            TaskStatus.ABORTED
        },
        TaskStatus.WAITING_USER_INPUT: {  # P2-C: Waiting state transitions
            TaskStatus.RUNNING,    # Resume after user reply
            TaskStatus.FAILED,     # User rejected
            TaskStatus.ABORTED,    # Aborted while waiting
        },
        TaskStatus.COMPLETED: set(),  # Terminal state
        TaskStatus.FAILED: set(),     # Terminal state
        TaskStatus.ABORTED: set(),    # Terminal state
    }
    
    # Terminal states (no further transitions)
    TERMINAL_STATES: Set[TaskStatus] = {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.ABORTED
    }
    
    # Active states (task is in progress)
    ACTIVE_STATES: Set[TaskStatus] = {
        TaskStatus.PLANNING,
        TaskStatus.RUNNING
    }
    
    # Paused/blocked states
    PAUSED_STATES: Set[TaskStatus] = {
        TaskStatus.PAUSED,
        TaskStatus.BLOCKED,
        TaskStatus.WAITING_USER_INPUT,  # P2-C: Also a paused state
    }
    
    # P2-C: Waiting states (background should not auto-progress)
    WAITING_STATES: Set[TaskStatus] = {
        TaskStatus.WAITING_USER_INPUT,
    }
    
    @classmethod
    def can_transition(cls, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """
        Check if transition is valid.
        
        Args:
            from_status: Current status
            to_status: Target status
        
        Returns:
            True if transition is valid
        """
        valid_targets = cls.TRANSITIONS.get(from_status, set())
        return to_status in valid_targets
    
    @classmethod
    def get_valid_transitions(cls, status: TaskStatus) -> Set[TaskStatus]:
        """
        Get all valid transitions from a status.
        
        Args:
            status: Current status
        
        Returns:
            Set of valid target statuses
        """
        return cls.TRANSITIONS.get(status, set()).copy()
    
    @classmethod
    def is_terminal(cls, status: TaskStatus) -> bool:
        """
        Check if status is terminal (no further transitions).
        
        Args:
            status: Status to check
        
        Returns:
            True if terminal
        """
        return status in cls.TERMINAL_STATES
    
    @classmethod
    def is_active(cls, status: TaskStatus) -> bool:
        """
        Check if status is active (task is in progress).
        
        Args:
            status: Status to check
        
        Returns:
            True if active
        """
        return status in cls.ACTIVE_STATES
    
    @classmethod
    def is_paused(cls, status: TaskStatus) -> bool:
        """
        Check if status is paused or blocked.
        
        Args:
            status: Status to check
        
        Returns:
            True if paused/blocked
        """
        return status in cls.PAUSED_STATES
    
    @classmethod
    def is_waiting(cls, status: TaskStatus) -> bool:
        """
        Check if status is waiting for user input.
        
        P2-C: Background drivers should not auto-progress waiting tasks.
        
        Args:
            status: Status to check
        
        Returns:
            True if waiting for user input
        """
        return status in cls.WAITING_STATES
    
    @classmethod
    def validate_transition(cls, from_status: TaskStatus, to_status: TaskStatus) -> None:
        """
        Validate a transition, raising exception if invalid.
        
        Args:
            from_status: Current status
            to_status: Target status
        
        Raises:
            InvalidStateTransition: If transition is invalid
        """
        if not cls.can_transition(from_status, to_status):
            valid = cls.get_valid_transitions(from_status)
            if valid:
                valid_str = ", ".join(s.value for s in valid)
                raise InvalidStateTransition(
                    f"Cannot transition from '{from_status.value}' to '{to_status.value}'. "
                    f"Valid transitions: {valid_str}"
                )
            else:
                raise InvalidStateTransition(
                    f"Cannot transition from terminal state '{from_status.value}'"
                )


class InvalidStateTransition(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


def transition_to(task_status: TaskStatus, target: TaskStatus) -> TaskStatus:
    """
    Helper function to validate and return target status.
    
    Args:
        task_status: Current task status
        target: Target status
    
    Returns:
        Target status if valid
    
    Raises:
        InvalidStateTransition: If transition is invalid
    """
    StateMachine.validate_transition(task_status, target)
    return target
