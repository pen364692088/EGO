from __future__ import annotations

import logging
from typing import Any, Optional

from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
try:
    from app.telegram_evidence_collector import get_evidence_collector
    _EVIDENCE_COLLECTOR_AVAILABLE = True
except Exception:
    get_evidence_collector = None
    _EVIDENCE_COLLECTOR_AVAILABLE = False

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
                evidence_collector_factory=get_evidence_collector if _EVIDENCE_COLLECTOR_AVAILABLE else None,
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
        evidence_collector: Optional[Any] = None,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_ingress(
            session_id=session_id,
            turn_id=turn_id,
            source=source,
            user_input=user_input,
            state=state,
            evidence_collector=evidence_collector,
        )

    def process_external_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        step: int,
        state: Any,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_external_result(
            session_id=session_id,
            turn_id=turn_id,
            step=step,
            state=state,
            evidence_collector=evidence_collector,
        )

    def capture_response_plan(self, *, result: Any, evidence_collector: Optional[Any] = None) -> None:
        if self.runtime is None:
            return
        self.runtime.capture_response_plan(result=result, evidence_collector=evidence_collector)

    def process_finalized_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        result: Any,
        state: Any,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_finalized_result(
            session_id=session_id,
            turn_id=turn_id,
            result=result,
            state=state,
            evidence_collector=evidence_collector,
        )

    def process_idle_check(
        self,
        *,
        session_id: str,
        turn_id: str,
        state: Any,
        evidence_collector: Optional[Any] = None,
    ) -> None:
        if self.runtime is None:
            return
        self.runtime.process_idle_check(
            session_id=session_id,
            turn_id=turn_id,
            state=state,
            evidence_collector=evidence_collector,
        )
