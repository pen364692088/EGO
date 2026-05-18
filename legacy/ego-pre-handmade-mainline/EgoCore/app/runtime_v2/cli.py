from __future__ import annotations

import asyncio

from app.autonomy import (
    AutonomyExecutorKind,
    AutonomyOrchestrator,
    AutonomyRun,
    AutonomyRunStatus,
    AutonomySliceOutcome,
)

from .loop import RuntimeV2Loop
from .runtime_reply import RuntimeV2TurnResult
from .state import RuntimeV2State


class _CliAutonomySurface:
    def __init__(self, loop: RuntimeV2Loop) -> None:
        self.loop = loop

    async def run_ingress(self, run: AutonomyRun) -> AutonomySliceOutcome:
        result: RuntimeV2TurnResult = await self.loop.run_turn_typed(
            session_id=run.session_key,
            user_input=run.objective,
            source="cli",
        )
        return self._adapt(run, result)

    async def resume(self, run: AutonomyRun, trigger_source: str) -> AutonomySliceOutcome:
        state = RuntimeV2State.from_snapshot(run.runtime_state_snapshot)
        self.loop._states[run.session_key] = state
        result = await self.loop.continue_turn_typed(
            session_id=run.session_key,
            source=f"cli:{trigger_source}",
            state=state,
        )
        return self._adapt(run, result)

    def _adapt(self, run: AutonomyRun, result: RuntimeV2TurnResult) -> AutonomySliceOutcome:
        if result.reply_text:
            print(f"【AI】{result.reply_text}")
        status_map = {
            "resumable_pause": AutonomyRunStatus.RESUMABLE_PAUSE,
            "waiting_input": AutonomyRunStatus.WAITING_USER_INPUT,
            "blocked": AutonomyRunStatus.BLOCKED,
            "failed": AutonomyRunStatus.FAILED,
            "completed_verified": AutonomyRunStatus.COMPLETED,
            "completed": AutonomyRunStatus.COMPLETED,
            "chat": AutonomyRunStatus.COMPLETED,
        }
        return AutonomySliceOutcome(
            status=status_map.get(result.status, AutonomyRunStatus.FAILED),
            stop_reason=getattr(result, "finish_reason", None),
            current_phase="completed" if result.status in {"completed", "completed_verified", "chat"} else "planning_current_slice",
            checkpoint_payload=getattr(result, "checkpoint_payload", None) or {},
            runtime_state_snapshot=result.state.to_snapshot(),
            last_result_summary={
                "status": result.status,
                "reply_text": result.reply_text,
                "finish_reason": getattr(result, "finish_reason", None),
            },
            hard_blocker_reason=getattr(result, "finish_reason", None) if result.status == "blocked" else None,
        )


async def interactive_cli() -> int:
    loop = RuntimeV2Loop()
    autonomy = AutonomyOrchestrator()
    cli_surface = _CliAutonomySurface(loop)
    autonomy.register_surface("cli_runtime_v2", cli_surface.resume)
    session_id = "cli:runtime_v2"
    print("Runtime v2 CLI ready. Type 'exit' to quit.")
    while True:
        try:
            user_input = input("\n【你】")
        except EOFError:
            break
        if user_input.strip().lower() in {"exit", "quit"}:
            break
        run = await autonomy.submit_ingress(
            surface="cli_runtime_v2",
            session_key=session_id,
            objective=user_input,
            executor_kind=AutonomyExecutorKind.GENERIC_RUNTIME,
            metadata={},
            initial_execute=cli_surface.run_ingress,
        )
        await autonomy.wait_for_terminal(run.id, timeout_seconds=60.0)
    return 0


def run_cli() -> int:
    return asyncio.run(interactive_cli())
