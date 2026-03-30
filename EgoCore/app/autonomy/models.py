from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class AutonomyRunStatus(str, Enum):
    RUNNING = "running"
    RESUMABLE_PAUSE = "resumable_pause"
    WAITING_USER_INPUT = "waiting_user_input"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AutonomyExecutorKind(str, Enum):
    CONTRACT_EXECUTE = "contract_execute"
    GENERIC_RUNTIME = "generic_runtime"


class AutonomyStopReason(str, Enum):
    PLANNING_TIMEOUT = "planning_timeout"
    REPLY_TIMEOUT = "reply_timeout"
    MAX_STEPS_EXHAUSTED = "max_steps_exhausted"
    CONTEXT_COMPACTION_NEEDED = "context_compaction_needed"
    TRANSIENT_TIMEOUT = "transient_timeout"
    TRANSIENT_RETRY_BUDGET_EXCEEDED = "transient_retry_budget_exceeded"
    WAITING_USER_INPUT = "waiting_user_input"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    AUTONOMY_SAFETY_CAP_EXCEEDED = "autonomy_safety_cap_exceeded"


@dataclass
class AutonomySliceOutcome:
    status: AutonomyRunStatus
    stop_reason: Optional[str] = None
    current_phase: str = "running"
    checkpoint_payload: Dict[str, Any] = field(default_factory=dict)
    runtime_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    last_result_summary: Dict[str, Any] = field(default_factory=dict)
    hard_blocker_reason: Optional[str] = None


@dataclass
class AutonomyRun:
    id: str
    session_key: str
    surface: str
    status: AutonomyRunStatus
    executor_kind: AutonomyExecutorKind
    objective: str
    current_phase: str = "submitted"
    checkpoint_payload: Dict[str, Any] = field(default_factory=dict)
    runtime_state_snapshot: Dict[str, Any] = field(default_factory=dict)
    last_result_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    hard_blocker_reason: Optional[str] = None
    resume_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(
        cls,
        *,
        session_key: str,
        surface: str,
        status: AutonomyRunStatus,
        executor_kind: AutonomyExecutorKind,
        objective: str,
        current_phase: str = "submitted",
        checkpoint_payload: Optional[Dict[str, Any]] = None,
        runtime_state_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AutonomyRun":
        now = datetime.now()
        return cls(
            id=f"autonomy_{uuid.uuid4().hex[:12]}",
            session_key=session_key,
            surface=surface,
            status=status,
            executor_kind=executor_kind,
            objective=objective,
            current_phase=current_phase,
            checkpoint_payload=dict(checkpoint_payload or {}),
            runtime_state_snapshot=dict(runtime_state_snapshot or {}),
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_key": self.session_key,
            "surface": self.surface,
            "status": self.status.value,
            "executor_kind": self.executor_kind.value,
            "objective": self.objective,
            "current_phase": self.current_phase,
            "checkpoint_payload": self.checkpoint_payload,
            "runtime_state_snapshot": self.runtime_state_snapshot,
            "last_result_summary": self.last_result_summary,
            "metadata": self.metadata,
            "hard_blocker_reason": self.hard_blocker_reason,
            "resume_count": self.resume_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
