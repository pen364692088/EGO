from __future__ import annotations

import inspect

from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult
from app.runtime_v2.state import RuntimeV2State


class TelegramRuntimeFallbackRunner:
    def __init__(self) -> None:
        self._loop = None

    @property
    def loop(self):
        return self._loop

    def get_loop(self):
        if self._loop is None:
            from app.runtime_v2.loop import RuntimeV2Loop

            self._loop = RuntimeV2Loop()
        return self._loop

    def attach_state(self, session_key: str, state: RuntimeV2State):
        loop = self.get_loop()
        loop._states[session_key] = state
        return loop

    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        state: RuntimeV2State,
        source: str = "telegram",
        evidence_collector=None,
        progress_callback=None,
        run_event_callback=None,
    ) -> TelegramTurnResult:
        loop = self.attach_state(session_key, state)
        kwargs = {
            "session_id": session_key,
            "user_input": user_input,
            "source": source,
        }
        parameters = inspect.signature(loop.run_turn_typed).parameters
        if "evidence_collector" in parameters:
            kwargs["evidence_collector"] = evidence_collector
        if "progress_callback" in parameters:
            kwargs["progress_callback"] = progress_callback
        if "run_event_callback" in parameters:
            kwargs["run_event_callback"] = run_event_callback
        result = await loop.run_turn_typed(**kwargs)
        return self.adapt_result(result)

    def adapt_result(self, result) -> TelegramTurnResult:
        reply = getattr(result, "reply", None)
        adapted_reply = None
        if reply is not None:
            adapted_reply = TelegramTurnReply(
                reply_text=reply.reply_text,
                delivery_kind=reply.delivery_kind,
                status=reply.status,
                suppressible=getattr(reply, "suppressible", False),
                request_id=getattr(reply, "request_id", None),
                generation_id=getattr(reply, "generation_id", None),
                turn_id=getattr(reply, "turn_id", None),
                metadata=dict(getattr(reply, "metadata", None) or {}),
            )
        return TelegramTurnResult(
            status=result.status,
            state=result.state,
            reply=adapted_reply,
            finish_reason=getattr(result, "finish_reason", None),
            checkpoint_payload=getattr(result, "checkpoint_payload", None),
        )


__all__ = ["TelegramRuntimeFallbackRunner"]
