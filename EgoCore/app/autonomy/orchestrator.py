from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Dict, Optional

from .models import (
    AutonomyExecutorKind,
    AutonomyRun,
    AutonomyRunStatus,
    AutonomySliceOutcome,
    AutonomyStopReason,
)
from .repository import AutonomyRunRepository

logger = logging.getLogger(__name__)

InitialExecute = Callable[[AutonomyRun], Awaitable[AutonomySliceOutcome]]
ResumeExecute = Callable[[AutonomyRun, str], Awaitable[AutonomySliceOutcome]]


class AutonomyOrchestrator:
    def __init__(
        self,
        repository: Optional[AutonomyRunRepository] = None,
        *,
        inline_slice_budget_seconds: int = 8,
        background_slice_budget_seconds: int = 45,
        max_consecutive_slices: int = 20,
        max_total_runtime_seconds: int = 1800,
    ) -> None:
        self.repository = repository or AutonomyRunRepository()
        self.inline_slice_budget_seconds = inline_slice_budget_seconds
        self.background_slice_budget_seconds = background_slice_budget_seconds
        self.max_consecutive_slices = max_consecutive_slices
        self.max_total_runtime_seconds = max_total_runtime_seconds
        self._resume_handlers: Dict[str, ResumeExecute] = {}
        self._background_tasks: Dict[str, asyncio.Task[None]] = {}

    def register_surface(self, surface: str, resume_handler: ResumeExecute) -> None:
        self._resume_handlers[surface] = resume_handler

    def get_latest_run(self, session_key: str) -> Optional[AutonomyRun]:
        return self.repository.get_latest_for_session(session_key)

    def get_active_run(self, session_key: str) -> Optional[AutonomyRun]:
        return self.repository.get_active_for_session(session_key)

    def supersede_session_runs(self, session_key: str) -> int:
        return self.repository.supersede_session_runs(session_key)

    async def submit_ingress(
        self,
        *,
        surface: str,
        session_key: str,
        objective: str,
        executor_kind: AutonomyExecutorKind,
        metadata: Optional[dict] = None,
        initial_execute: InitialExecute,
    ) -> AutonomyRun:
        run = AutonomyRun.create(
            session_key=session_key,
            surface=surface,
            status=AutonomyRunStatus.RUNNING,
            executor_kind=executor_kind,
            objective=objective,
            current_phase="locking_goal",
            metadata=metadata or {},
        )
        self.repository.create(run)
        outcome = await initial_execute(run)
        return self._apply_outcome(run, outcome, increment_resume=False, schedule_background=True)

    async def resume_run(self, run_id: str, *, trigger_source: str = "manual") -> Optional[AutonomyRun]:
        run = self.repository.get(run_id)
        if run is None:
            return None
        if run.status not in {AutonomyRunStatus.RUNNING, AutonomyRunStatus.RESUMABLE_PAUSE} and not (
            trigger_source == "manual"
            and run.status == AutonomyRunStatus.BLOCKED
            and run.hard_blocker_reason in {
                AutonomyStopReason.TRANSIENT_RETRY_BUDGET_EXCEEDED.value,
                AutonomyStopReason.NO_PROGRESS_STALL_DETECTED.value,
                AutonomyStopReason.AUTONOMY_SAFETY_CAP_EXCEEDED.value,
            }
        ):
            return run
        handler = self._resume_handlers.get(run.surface)
        if handler is None:
            raise RuntimeError(f"no autonomy resume handler registered for surface={run.surface}")

        run.status = AutonomyRunStatus.RUNNING
        run.hard_blocker_reason = None
        if run.current_phase not in {"blocked", "completed"}:
            run.current_phase = "planning_current_slice"
        self.repository.update(run)
        outcome = await handler(run, trigger_source)
        return self._apply_outcome(
            run,
            outcome,
            increment_resume=(trigger_source != "ingress"),
            schedule_background=(trigger_source != "manual"),
        )

    def recover_surface(self, surface: str) -> None:
        for run in self.repository.list_resumable(surface=surface):
            self._schedule_background(run.id)

    async def wait_for_terminal(self, run_id: str, *, timeout_seconds: float = 60.0) -> Optional[AutonomyRun]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            run = self.repository.get(run_id)
            if run is None:
                return None
            if run.status not in {AutonomyRunStatus.RUNNING, AutonomyRunStatus.RESUMABLE_PAUSE}:
                return run
            await asyncio.sleep(0.05)
        return self.repository.get(run_id)

    def _apply_outcome(
        self,
        run: AutonomyRun,
        outcome: AutonomySliceOutcome,
        *,
        increment_resume: bool,
        schedule_background: bool,
    ) -> AutonomyRun:
        if increment_resume:
            run.resume_count += 1
        run.status = outcome.status
        run.current_phase = outcome.current_phase or run.current_phase
        run.checkpoint_payload = dict(outcome.checkpoint_payload or {})
        run.runtime_state_snapshot = dict(outcome.runtime_state_snapshot or {})
        run.last_result_summary = dict(outcome.last_result_summary or {})
        run.hard_blocker_reason = outcome.hard_blocker_reason
        self.repository.update(run)

        if schedule_background and run.status == AutonomyRunStatus.RESUMABLE_PAUSE:
            self._schedule_background(run.id)
        return run

    def _schedule_background(self, run_id: str) -> None:
        existing = self._background_tasks.get(run_id)
        if existing is not None and not existing.done():
            return
        self._background_tasks[run_id] = asyncio.create_task(self._background_worker(run_id))

    async def _background_worker(self, run_id: str) -> None:
        try:
            while True:
                run = self.repository.get(run_id)
                if run is None:
                    return
                if run.status != AutonomyRunStatus.RESUMABLE_PAUSE:
                    return
                if self._exceeded_safety_cap(run):
                    run.status = AutonomyRunStatus.BLOCKED
                    run.current_phase = "blocked"
                    run.hard_blocker_reason = AutonomyStopReason.AUTONOMY_SAFETY_CAP_EXCEEDED.value
                    run.last_result_summary = {
                        **dict(run.last_result_summary or {}),
                        "status": AutonomyRunStatus.BLOCKED.value,
                        "finish_reason": AutonomyStopReason.AUTONOMY_SAFETY_CAP_EXCEEDED.value,
                    }
                    self.repository.update(run)
                    logger.warning("autonomy.safety_cap_exceeded run_id=%s", run_id)
                    return
                await asyncio.sleep(0)
                await self.resume_run(run_id, trigger_source="driver")
        finally:
            self._background_tasks.pop(run_id, None)

    def _exceeded_safety_cap(self, run: AutonomyRun) -> bool:
        if run.resume_count >= self.max_consecutive_slices:
            return True
        return (time.time() - run.created_at.timestamp()) >= self.max_total_runtime_seconds
