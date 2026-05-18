"""
OpenEmotion Agent Runtime - Foreground/Background Guard

P2-B.4: Isolation protection between foreground and background execution.

Core rules:
- Background never takes over foreground session
- Background never modifies foreground preference
- Background never writes to foreground reply channel
- session_affinity / task_scope must be preserved
"""

import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.storage.models import Task, TaskStatus


logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Execution mode."""
    FOREGROUND = "foreground"
    BACKGROUND = "background"


@dataclass
class SessionContext:
    """Session context for tracking foreground/background state."""
    session_id: str
    mode: ExecutionMode
    chat_id: Optional[str] = None
    user_id: Optional[str] = None
    scope_key: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    active_task_id: Optional[str] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_active(self, timeout_minutes: int = 30) -> bool:
        """Check if session is still active."""
        return datetime.now() - self.last_activity < timedelta(minutes=timeout_minutes)


@dataclass
class ForegroundState:
    """Global foreground state tracking."""
    # Active foreground sessions
    sessions: Dict[str, SessionContext] = field(default_factory=dict)
    
    # Task -> Session mapping
    task_session_map: Dict[str, str] = field(default_factory=dict)
    
    # Lock for thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def register_session(self, session_id: str, chat_id: Optional[str] = None,
                         user_id: Optional[str] = None) -> None:
        """Register a new foreground session."""
        with self._lock:
            scope_key = f"tg:{chat_id or 'unknown'}:{user_id or 'unknown'}"
            self.sessions[session_id] = SessionContext(
                session_id=session_id,
                mode=ExecutionMode.FOREGROUND,
                chat_id=chat_id,
                user_id=user_id,
                scope_key=scope_key
            )
            logger.debug(f"Registered foreground session: {session_id}")
    
    def unregister_session(self, session_id: str) -> None:
        """Unregister a foreground session."""
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                # Clean up task mapping
                tasks_to_remove = [
                    task_id for task_id, sid in self.task_session_map.items()
                    if sid == session_id
                ]
                for task_id in tasks_to_remove:
                    del self.task_session_map[task_id]
                logger.debug(f"Unregistered foreground session: {session_id}")
    
    def bind_task(self, session_id: str, task_id: str) -> None:
        """Bind a task to a foreground session."""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].active_task_id = task_id
                self.sessions[session_id].update_activity()
                self.task_session_map[task_id] = session_id
                logger.debug(f"Bound task {task_id} to session {session_id}")
    
    def get_session_for_task(self, task_id: str) -> Optional[SessionContext]:
        """Get the session that owns a task."""
        with self._lock:
            session_id = self.task_session_map.get(task_id)
            if session_id:
                return self.sessions.get(session_id)
            return None
    
    def is_task_in_foreground(self, task_id: str) -> bool:
        """Check if a task is currently in foreground."""
        session = self.get_session_for_task(task_id)
        return session is not None and session.is_active()
    
    def update_activity(self, session_id: str) -> None:
        """Update session activity."""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].update_activity()
    
    def cleanup_inactive_sessions(self, timeout_minutes: int = 60) -> int:
        """Clean up inactive sessions and return count."""
        with self._lock:
            inactive = [
                sid for sid, session in self.sessions.items()
                if not session.is_active(timeout_minutes)
            ]
            for sid in inactive:
                self.unregister_session(sid)
            return len(inactive)


# Global foreground state
_foreground_state: Optional[ForegroundState] = None


def get_foreground_state() -> ForegroundState:
    """Get or create global foreground state."""
    global _foreground_state
    if _foreground_state is None:
        _foreground_state = ForegroundState()
    return _foreground_state


# ============================================================================
# Guard Functions
# ============================================================================

def can_background_process(task: Task) -> tuple[bool, str]:
    """
    Check if background driver can process a task.
    
    Args:
        task: Task to check
    
    Returns:
        Tuple of (can_process, reason)
    """
    state = get_foreground_state()
    
    # Check if task is in active foreground session
    if state.is_task_in_foreground(task.id):
        return False, "Task is in active foreground session"
    
    # Check task scope
    if task.scope_key:
        # Find if any active session owns this scope
        for session in state.sessions.values():
            if session.scope_key == task.scope_key and session.is_active():
                return False, f"Scope {task.scope_key} is in foreground session {session.session_id}"
    
    return True, "Background processing allowed"


def check_session_affinity(task: Task, session_id: Optional[str] = None) -> bool:
    """
    Check session affinity for a task.
    
    Args:
        task: Task to check
        session_id: Optional session ID to verify
    
    Returns:
        True if session affinity is preserved
    """
    state = get_foreground_state()
    
    # Get bound session
    bound_session = state.get_session_for_task(task.id)
    
    if session_id:
        # Verify session matches
        return bound_session is None or bound_session.session_id == session_id
    
    return True


def preserve_task_scope(task: Task, new_scope_key: Optional[str] = None) -> bool:
    """
    Verify task scope is preserved.
    
    Background drivers should never change task scope.
    
    Args:
        task: Task to check
        new_scope_key: Proposed new scope key
    
    Returns:
        True if scope is preserved or unchanged
    """
    if new_scope_key is None:
        return True
    
    # Scope should never change
    return task.scope_key == new_scope_key


def get_execution_mode(task_id: str) -> ExecutionMode:
    """
    Get the execution mode for a task.
    
    Args:
        task_id: Task identifier
    
    Returns:
        FOREGROUND if task is in active session, else BACKGROUND
    """
    state = get_foreground_state()
    
    if state.is_task_in_foreground(task_id):
        return ExecutionMode.FOREGROUND
    
    return ExecutionMode.BACKGROUND


def mark_foreground_start(session_id: str, chat_id: Optional[str] = None,
                          user_id: Optional[str] = None) -> None:
    """Mark the start of a foreground session."""
    state = get_foreground_state()
    state.register_session(session_id, chat_id, user_id)


def mark_foreground_end(session_id: str) -> None:
    """Mark the end of a foreground session."""
    state = get_foreground_state()
    state.unregister_session(session_id)


def bind_task_to_foreground(session_id: str, task_id: str) -> None:
    """Bind a task to a foreground session."""
    state = get_foreground_state()
    state.bind_task(session_id, task_id)


def update_foreground_activity(session_id: str) -> None:
    """Update foreground session activity."""
    state = get_foreground_state()
    state.update_activity(session_id)


# ============================================================================
# Reply Channel Protection
# ============================================================================

@dataclass
class ReplyChannelGuard:
    """
    Guards reply channels from background noise.
    
    Background should not send intermediate noise to foreground reply channel.
    """
    
    # Allowed background notifications
    ALLOWED_BACKGROUND_NOTIFICATIONS: Set[str] = field(default_factory=lambda: {
        "completed",
        "blocked",
        "manual_action_required",
        "intent_mismatch_blocked",
        "path_extraction_blocked",
        "status_query_response",
    })
    
    # Forbidden background noise
    FORBIDDEN_BACKGROUND_NOISE: Set[str] = field(default_factory=lambda: {
        "heartbeat_tick",
        "cron_tick",
        "retry_attempt",
        "checkpoint_save",
        "intermediate_progress",
        "debug_log",
    })
    
    def can_send_notification(self, notification_type: str, 
                              execution_mode: ExecutionMode) -> bool:
        """
        Check if a notification can be sent.
        
        Args:
            notification_type: Type of notification
            execution_mode: Current execution mode
        
        Returns:
            True if notification is allowed
        """
        # Foreground can send any notification
        if execution_mode == ExecutionMode.FOREGROUND:
            return True
        
        # Background can only send allowed notifications
        if notification_type in self.FORBIDDEN_BACKGROUND_NOISE:
            return False
        
        return notification_type in self.ALLOWED_BACKGROUND_NOTIFICATIONS
    
    def filter_background_message(self, message: str, 
                                   execution_mode: ExecutionMode) -> Optional[str]:
        """
        Filter a background message.
        
        Args:
            message: Original message
            execution_mode: Current execution mode
        
        Returns:
            Filtered message or None if should be suppressed
        """
        if execution_mode == ExecutionMode.FOREGROUND:
            return message
        
        # Background message filtering
        # Suppress intermediate noise
        if any(noise in message.lower() for noise in ["heartbeat tick", "cron tick", "retrying"]):
            return None
        
        return message


def get_reply_guard() -> ReplyChannelGuard:
    """Get the reply channel guard."""
    return ReplyChannelGuard()


# ============================================================================
# Context Manager for Foreground Sessions
# ============================================================================

class ForegroundSession:
    """
    Context manager for foreground sessions.
    
    Usage:
        with ForegroundSession(session_id, chat_id, user_id) as session:
            session.bind_task(task_id)
            # ... do work ...
    """
    
    def __init__(self, session_id: str, chat_id: Optional[str] = None,
                 user_id: Optional[str] = None):
        self.session_id = session_id
        self.chat_id = chat_id
        self.user_id = user_id
        self._active = False
    
    def __enter__(self) -> "ForegroundSession":
        mark_foreground_start(self.session_id, self.chat_id, self.user_id)
        self._active = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        mark_foreground_end(self.session_id)
        self._active = False
    
    def bind_task(self, task_id: str) -> None:
        """Bind a task to this session."""
        if not self._active:
            raise RuntimeError("Session is not active")
        bind_task_to_foreground(self.session_id, task_id)
    
    def update_activity(self) -> None:
        """Update session activity."""
        if not self._active:
            raise RuntimeError("Session is not active")
        update_foreground_activity(self.session_id)
