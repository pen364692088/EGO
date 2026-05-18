from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

SUBJECT_GATE_AUTHORITY_SOURCE = "mandatory_subject_gate"
SUBJECT_GATE_FAILED_REPLY = "subject_gate_failed：主体暂时不可用，这一步已阻断，请稍后重试。"


@dataclass(frozen=True)
class SubjectGateVerdict:
    ok: bool
    stage: str
    reason: str
    reply_text: str
    authority_source: str = SUBJECT_GATE_AUTHORITY_SOURCE

    @classmethod
    def allow(cls, *, stage: str, reason: str = "ok") -> "SubjectGateVerdict":
        return cls(
            ok=True,
            stage=stage,
            reason=reason,
            reply_text="",
            authority_source=SUBJECT_GATE_AUTHORITY_SOURCE,
        )

    @classmethod
    def block(
        cls,
        *,
        stage: str,
        reason: str,
        reply_text: str = SUBJECT_GATE_FAILED_REPLY,
    ) -> "SubjectGateVerdict":
        return cls(
            ok=False,
            stage=stage,
            reason=reason,
            reply_text=reply_text,
            authority_source=SUBJECT_GATE_AUTHORITY_SOURCE,
        )


class MandatorySubjectGate:
    def __init__(
        self,
        hooks: Optional[Any],
        *,
        authority_source: str = SUBJECT_GATE_AUTHORITY_SOURCE,
        failed_reply_text: str = SUBJECT_GATE_FAILED_REPLY,
    ) -> None:
        self.hooks = hooks
        self.authority_source = authority_source
        self.failed_reply_text = failed_reply_text

    def _block(self, *, stage: str, reason: str) -> SubjectGateVerdict:
        return SubjectGateVerdict(
            ok=False,
            stage=stage,
            reason=reason,
            reply_text=self.failed_reply_text,
            authority_source=self.authority_source,
        )

    def _call(self, *, stage: str, method_name: str, **kwargs: Any) -> SubjectGateVerdict:
        hooks = self.hooks
        if hooks is None:
            return self._block(stage=stage, reason="hooks_unavailable")
        if not bool(getattr(hooks, "enabled", False)):
            return self._block(stage=stage, reason="hooks_disabled")
        method = getattr(hooks, method_name, None)
        if method is None:
            return self._block(stage=stage, reason=f"{method_name}_missing")
        try:
            method(**kwargs)
        except Exception as exc:
            logger.exception("subject_gate.%s.failed err=%s", stage, exc)
            return self._block(stage=stage, reason=f"{method_name}_failed:{type(exc).__name__}")
        return SubjectGateVerdict(
            ok=True,
            stage=stage,
            reason="ok",
            reply_text="",
            authority_source=self.authority_source,
        )

    def process_ingress(self, **kwargs: Any) -> SubjectGateVerdict:
        return self._call(stage="ingress", method_name="process_ingress", **kwargs)

    def process_finalized_result(self, **kwargs: Any) -> SubjectGateVerdict:
        return self._call(stage="finalized_result", method_name="process_finalized_result", **kwargs)

    def capture_response_plan(self, **kwargs: Any) -> SubjectGateVerdict:
        return self._call(stage="response_plan", method_name="capture_response_plan", **kwargs)

    def finalize_host_owned_result(
        self,
        *,
        session_id: str,
        turn_id: str,
        result: Any,
        state: Any,
        evidence_collector: Optional[Any] = None,
    ) -> SubjectGateVerdict:
        finalized = self.process_finalized_result(
            session_id=session_id,
            turn_id=turn_id,
            result=result,
            state=state,
            evidence_collector=evidence_collector,
        )
        if not finalized.ok:
            return finalized
        return self.capture_response_plan(
            result=result,
            evidence_collector=evidence_collector,
        )
