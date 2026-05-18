from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from app.storage.db import Database, get_db

from .models import AutonomyExecutorKind, AutonomyRun, AutonomyRunStatus


class AutonomyRunRepository:
    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or get_db()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS autonomy_runs (
                    id TEXT PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    surface TEXT NOT NULL,
                    status TEXT NOT NULL,
                    executor_kind TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    current_phase TEXT NOT NULL,
                    checkpoint_payload TEXT,
                    runtime_state_snapshot TEXT,
                    last_result_summary TEXT,
                    metadata TEXT,
                    hard_blocker_reason TEXT,
                    resume_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_autonomy_runs_session_key
                ON autonomy_runs(session_key)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_autonomy_runs_status
                ON autonomy_runs(status)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_autonomy_runs_surface
                ON autonomy_runs(surface)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_autonomy_runs_updated_at
                ON autonomy_runs(updated_at)
                """
            )

    def create(self, run: AutonomyRun) -> AutonomyRun:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO autonomy_runs (
                    id, session_key, surface, status, executor_kind, objective,
                    current_phase, checkpoint_payload, runtime_state_snapshot,
                    last_result_summary, metadata, hard_blocker_reason,
                    resume_count, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.session_key,
                    run.surface,
                    run.status.value,
                    run.executor_kind.value,
                    run.objective,
                    run.current_phase,
                    json.dumps(run.checkpoint_payload or {}),
                    json.dumps(run.runtime_state_snapshot or {}),
                    json.dumps(run.last_result_summary or {}),
                    json.dumps(run.metadata or {}),
                    run.hard_blocker_reason,
                    run.resume_count,
                    run.created_at.isoformat(),
                    run.updated_at.isoformat(),
                ),
            )
        return run

    def update(self, run: AutonomyRun) -> AutonomyRun:
        run.updated_at = datetime.now()
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE autonomy_runs
                SET session_key = ?, surface = ?, status = ?, executor_kind = ?, objective = ?,
                    current_phase = ?, checkpoint_payload = ?, runtime_state_snapshot = ?,
                    last_result_summary = ?, metadata = ?, hard_blocker_reason = ?,
                    resume_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    run.session_key,
                    run.surface,
                    run.status.value,
                    run.executor_kind.value,
                    run.objective,
                    run.current_phase,
                    json.dumps(run.checkpoint_payload or {}),
                    json.dumps(run.runtime_state_snapshot or {}),
                    json.dumps(run.last_result_summary or {}),
                    json.dumps(run.metadata or {}),
                    run.hard_blocker_reason,
                    run.resume_count,
                    run.updated_at.isoformat(),
                    run.id,
                ),
            )
        return run

    def get(self, run_id: str) -> Optional[AutonomyRun]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM autonomy_runs WHERE id = ?", (run_id,))
            row = cur.fetchone()
        return self._row_to_run(row) if row else None

    def get_latest_for_session(self, session_key: str) -> Optional[AutonomyRun]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM autonomy_runs
                WHERE session_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (session_key,),
            )
            row = cur.fetchone()
        return self._row_to_run(row) if row else None

    def get_active_for_session(self, session_key: str) -> Optional[AutonomyRun]:
        active_statuses = (
            AutonomyRunStatus.RUNNING.value,
            AutonomyRunStatus.RESUMABLE_PAUSE.value,
            AutonomyRunStatus.WAITING_USER_INPUT.value,
            AutonomyRunStatus.BLOCKED.value,
        )
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM autonomy_runs
                WHERE session_key = ? AND status IN (?, ?, ?, ?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (
                    session_key,
                    active_statuses[0],
                    active_statuses[1],
                    active_statuses[2],
                    active_statuses[3],
                ),
            )
            row = cur.fetchone()
        return self._row_to_run(row) if row else None

    def supersede_session_runs(self, session_key: str) -> int:
        active_statuses = (
            AutonomyRunStatus.RUNNING.value,
            AutonomyRunStatus.RESUMABLE_PAUSE.value,
            AutonomyRunStatus.WAITING_USER_INPUT.value,
            AutonomyRunStatus.BLOCKED.value,
        )
        updated_at = datetime.now().isoformat()
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE autonomy_runs
                SET status = ?, current_phase = ?, updated_at = ?
                WHERE session_key = ? AND status IN (?, ?, ?, ?)
                """,
                (
                    AutonomyRunStatus.SUPERSEDED.value,
                    "superseded",
                    updated_at,
                    session_key,
                    active_statuses[0],
                    active_statuses[1],
                    active_statuses[2],
                    active_statuses[3],
                ),
            )
            return int(cur.rowcount or 0)

    def list_resumable(self, *, surface: Optional[str] = None, limit: int = 50) -> List[AutonomyRun]:
        statuses = (
            AutonomyRunStatus.RUNNING.value,
            AutonomyRunStatus.RESUMABLE_PAUSE.value,
        )
        with self.db.cursor() as cur:
            if surface:
                cur.execute(
                    """
                    SELECT * FROM autonomy_runs
                    WHERE status IN (?, ?) AND surface = ?
                    ORDER BY updated_at ASC
                    LIMIT ?
                    """,
                    (statuses[0], statuses[1], surface, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM autonomy_runs
                    WHERE status IN (?, ?)
                    ORDER BY updated_at ASC
                    LIMIT ?
                    """,
                    (statuses[0], statuses[1], limit),
                )
            rows = cur.fetchall()
        return [self._row_to_run(row) for row in rows]

    def _row_to_run(self, row) -> AutonomyRun:
        return AutonomyRun(
            id=row["id"],
            session_key=row["session_key"],
            surface=row["surface"],
            status=AutonomyRunStatus(row["status"]),
            executor_kind=AutonomyExecutorKind(row["executor_kind"]),
            objective=row["objective"],
            current_phase=row["current_phase"],
            checkpoint_payload=json.loads(row["checkpoint_payload"]) if row["checkpoint_payload"] else {},
            runtime_state_snapshot=json.loads(row["runtime_state_snapshot"]) if row["runtime_state_snapshot"] else {},
            last_result_summary=json.loads(row["last_result_summary"]) if row["last_result_summary"] else {},
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            hard_blocker_reason=row["hard_blocker_reason"],
            resume_count=int(row["resume_count"] or 0),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
