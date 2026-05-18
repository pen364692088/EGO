"""
OpenEmotion Agent Runtime - Control Audit Trail

P2-D.5: Audit logging for control commands.

Records all user control actions for:
- Traceability
- Replay capability
- Distinguishing user vs background actions
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json
import os
import logging

from app.storage.models import Task


logger = logging.getLogger(__name__)


class AuditSource(str, Enum):
    """Source of control action."""
    TELEGRAM_COMMAND = "telegram_command"
    HEARTBEAT = "heartbeat"
    CRON = "cron"
    INTERNAL = "internal"


@dataclass
class AuditEntry:
    """
    Single audit entry for a control action.
    
    Records:
    - Who performed the action (actor)
    - What action was taken (command)
    - On which task (task_id)
    - Previous and new status
    - When (timestamp)
    - Source (telegram_command, heartbeat, cron, etc.)
    """
    # Required fields
    actor: str                      # "user" or system identifier
    command: str                    # approve, reject, retry, etc.
    task_id: str                    # Target task
    previous_status: str            # Status before action
    new_status: str                 # Status after action
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = AuditSource.TELEGRAM_COMMAND.value
    
    # Optional fields
    reason: Optional[str] = None    # User-provided reason
    payload: Optional[Dict[str, Any]] = None  # Additional data
    success: bool = True            # Whether action succeeded
    error: Optional[str] = None     # Error message if failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "actor": self.actor,
            "command": self.command,
            "task_id": self.task_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "timestamp": self.timestamp,
            "source": self.source,
            "reason": self.reason,
            "payload": self.payload,
            "success": self.success,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary."""
        return cls(
            actor=data["actor"],
            command=data["command"],
            task_id=data["task_id"],
            previous_status=data["previous_status"],
            new_status=data["new_status"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            source=data.get("source", AuditSource.TELEGRAM_COMMAND.value),
            reason=data.get("reason"),
            payload=data.get("payload"),
            success=data.get("success", True),
            error=data.get("error"),
        )


class ControlAuditLog:
    """
    Audit log for control actions.
    
    Provides:
    - Append-only log
    - Query by task_id
    - Query recent actions
    - Persistence to file
    """
    
    def __init__(self, log_path: Optional[str] = None):
        """
        Initialize audit log.
        
        Args:
            log_path: Path to audit log file (defaults to data/audit.log)
        """
        if log_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            log_path = os.path.join(data_dir, "control_audit.jsonl")
        
        self.log_path = log_path
        self._entries: List[AuditEntry] = []
        self._load_entries()
    
    def _load_entries(self) -> None:
        """Load existing entries from file."""
        if not os.path.exists(self.log_path):
            return
        
        try:
            with open(self.log_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = AuditEntry.from_dict(data)
                        self._entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Failed to load audit log: {e}")
    
    def append(self, entry: AuditEntry) -> None:
        """
        Append an entry to the audit log.
        
        Args:
            entry: AuditEntry to append
        """
        self._entries.append(entry)
        
        # Persist to file
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_entries_for_task(self, task_id: str, limit: int = 10) -> List[AuditEntry]:
        """
        Get audit entries for a specific task.
        
        Args:
            task_id: Task to query
            limit: Maximum entries to return
        
        Returns:
            List of AuditEntry (most recent first)
        """
        entries = [e for e in self._entries if e.task_id == task_id]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]
    
    def get_recent_entries(self, limit: int = 20) -> List[AuditEntry]:
        """
        Get recent audit entries.
        
        Args:
            limit: Maximum entries to return
        
        Returns:
            List of AuditEntry (most recent first)
        """
        entries = sorted(self._entries, key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]
    
    def get_entries_by_source(self, source: AuditSource, limit: int = 20) -> List[AuditEntry]:
        """
        Get entries by source.
        
        Args:
            source: Source to filter by
            limit: Maximum entries to return
        
        Returns:
            List of AuditEntry
        """
        entries = [e for e in self._entries if e.source == source.value]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]
    
    def get_summary_for_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get audit summary for a task.
        
        Args:
            task_id: Task to query
        
        Returns:
            Summary dict with recent actions
        """
        entries = self.get_entries_for_task(task_id, limit=5)
        
        return {
            "task_id": task_id,
            "total_actions": len([e for e in self._entries if e.task_id == task_id]),
            "recent_actions": [
                {
                    "command": e.command,
                    "timestamp": e.timestamp,
                    "source": e.source,
                    "success": e.success,
                }
                for e in entries
            ],
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def log_control_action(
    command: str,
    task: Task,
    previous_status: str,
    new_status: str,
    actor: str = "user",
    source: str = AuditSource.TELEGRAM_COMMAND.value,
    reason: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> AuditEntry:
    """
    Log a control action to the audit log.
    
    Args:
        command: Command executed
        task: Target task
        previous_status: Status before
        new_status: Status after
        actor: Who performed the action
        source: Source of the action
        reason: Optional reason
        payload: Optional additional data
        success: Whether action succeeded
        error: Error message if failed
    
    Returns:
        The created AuditEntry
    """
    audit_log = get_audit_log()
    
    entry = AuditEntry(
        actor=actor,
        command=command,
        task_id=task.id,
        previous_status=previous_status,
        new_status=new_status,
        source=source,
        reason=reason,
        payload=payload,
        success=success,
        error=error,
    )
    
    audit_log.append(entry)
    logger.info(f"Control action: {command} on {task.id} by {actor}")
    
    return entry


def get_task_audit_summary(task_id: str) -> Dict[str, Any]:
    """
    Get audit summary for a task.
    
    Args:
        task_id: Task to query
    
    Returns:
        Summary dict
    """
    audit_log = get_audit_log()
    return audit_log.get_summary_for_task(task_id)


def get_recent_task_audit(task_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent audit entries for a task.
    
    Args:
        task_id: Task to query
        limit: Maximum entries
    
    Returns:
        List of entry dicts
    """
    audit_log = get_audit_log()
    entries = audit_log.get_entries_for_task(task_id, limit)
    return [e.to_dict() for e in entries]


# ============================================================================
# Global Instance
# ============================================================================

_audit_log: Optional[ControlAuditLog] = None


def get_audit_log() -> ControlAuditLog:
    """Get or create global audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = ControlAuditLog()
    return _audit_log
