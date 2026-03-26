from __future__ import annotations

import logging
from typing import Any, Optional

from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime

try:
    from app.openemotion_adapter import ProtoSelfAdapter, ProtoSelfTraceBridge
    _PROTO_SELF_IMPORT_OK = True
except Exception:
    ProtoSelfAdapter = None
    ProtoSelfTraceBridge = None
    _PROTO_SELF_IMPORT_OK = False

logger = logging.getLogger(__name__)


def _is_openemotion_enabled() -> bool:
    if not _PROTO_SELF_IMPORT_OK:
        return False
    try:
        from app.config import get_config
        cfg = get_config()
        return bool(cfg.openemotion.get("enabled", False)) if cfg else False
    except Exception:
        return False


class NativeOpenEmotionHooks:
    def __init__(self) -> None:
        if _is_openemotion_enabled():
            adapter = ProtoSelfAdapter(trace_bridge=ProtoSelfTraceBridge())
            self.runtime = RuntimeV2ProtoSelfRuntime(
                adapter=adapter,
                trace_bridge=adapter.trace_bridge,
            )
        else:
            self.runtime = None

    @property
    def enabled(self) -> bool:
        return self.runtime is not None

    def process_ingress(
        self,
        *,
        session_id: str,
        turn_id: str,
        source: str,
        user_input: str,
        state: Any,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_ingress(
            session_id=session_id,
            turn_id=turn_id,
            source=source,
            user_input=user_input,
            state=state,
        )

    def process_external_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        step: int,
        state: Any,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_external_result(
            session_id=session_id,
            turn_id=turn_id,
            step=step,
            state=state,
        )

    def capture_response_plan(self, *, result: Any) -> None:
        if self.runtime is None:
            return
        self.runtime.capture_response_plan(result=result)
