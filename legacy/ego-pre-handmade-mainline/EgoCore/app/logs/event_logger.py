"""
OpenEmotion Agent Runtime - Event Logger

Event logging system for auditing and recovery.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class EventType(str, Enum):
    """Event types for logging."""
    # Telegram events
    TELEGRAM_MESSAGE_RECEIVED = "telegram_message_received"
    TELEGRAM_MESSAGE_SENT = "telegram_message_sent"
    
    # Task events
    TASK_CREATED = "task_created"
    TASK_PLANNED = "task_planned"
    TASK_STARTED = "task_started"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_ABORTED = "task_aborted"
    
    # Step events
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    
    # Tool events
    TOOL_CALLED = "tool_called"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    
    # Memory events
    MEMORY_WRITTEN = "memory_written"
    MEMORY_READ = "memory_read"
    
    # Checkpoint events
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    
    # System events
    SYSTEM_STARTED = "system_started"
    SYSTEM_SHUTDOWN = "system_shutdown"
    ERROR = "error"


class Event:
    """Event record."""
    
    def __init__(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        self.event_type = event_type
        self.data = data or {}
        self.session_id = session_id
        self.task_id = task_id
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "task_id": self.task_id,
            "data": self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create from dictionary."""
        event = cls(
            event_type=EventType(data["event_type"]),
            data=data.get("data", {}),
            session_id=data.get("session_id"),
            task_id=data.get("task_id")
        )
        event.timestamp = datetime.fromisoformat(data["timestamp"])
        return event


class EventLogger:
    """
    Event logger for OpenEmotion Agent Runtime.
    
    Writes events to JSONL files for auditing and recovery.
    """
    
    def __init__(self, events_dir: Optional[Path] = None):
        """
        Initialize event logger.
        
        Args:
            events_dir: Directory for event log files
        """
        from app.config import get_config
        config = get_config()
        self.events_dir = events_dir or config.get_path('events_dir')
        self.events_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_file = self.events_dir / f"events_{self.session_id}.jsonl"
    
    def log(self, event: Event) -> None:
        """
        Log an event.
        
        Args:
            event: Event to log
        """
        # Set session ID if not set
        if not event.session_id:
            event.session_id = self.session_id
        
        # Write to JSONL file
        with open(self.current_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')
    
    def log_event(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None
    ) -> None:
        """
        Convenience method to log an event.
        
        Args:
            event_type: Type of event
            data: Event data
            task_id: Associated task ID
        """
        event = Event(
            event_type=event_type,
            data=data,
            session_id=self.session_id,
            task_id=task_id
        )
        self.log(event)
    
    def get_events(
        self,
        event_type: Optional[EventType] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> list[Event]:
        """
        Get events from log files.
        
        Args:
            event_type: Filter by event type
            task_id: Filter by task ID
            limit: Maximum events to return
        
        Returns:
            List of events
        """
        events = []
        
        # Read all event files
        for event_file in sorted(self.events_dir.glob("events_*.jsonl"), reverse=True):
            with open(event_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        event = Event.from_dict(data)
                        
                        # Apply filters
                        if event_type and event.event_type != event_type:
                            continue
                        if task_id and event.task_id != task_id:
                            continue
                        
                        events.append(event)
                        
                        if len(events) >= limit:
                            return events
                    except:
                        continue
        
        return events
    
    def get_task_events(self, task_id: str) -> list[Event]:
        """Get all events for a task."""
        return self.get_events(task_id=task_id, limit=1000)


# Global event logger instance
_event_logger: Optional[EventLogger] = None


def get_event_logger() -> EventLogger:
    """Get the global event logger instance."""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()
    return _event_logger
