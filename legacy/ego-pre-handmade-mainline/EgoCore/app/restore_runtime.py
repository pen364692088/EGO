from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from egocore.runtime.context_injector import ContextInjector
from egocore.runtime.self_restorer import RestoreResult, SelfRestorer


@dataclass
class PendingRestoreObservation:
    restore_id: str
    restore_status: str
    loaded_layers: List[str]
    degraded_mode: bool
    degradation_reason: Optional[str]
    restore_timestamp: str
    authority_source: str = "restore_audit"
    injection_summary: Dict[str, Any] = field(default_factory=dict)
    recovery_hints_present: bool = False
    standing_commitments_preview: List[str] = field(default_factory=list)
    post_restore_first_turn: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _build_injection_payload(result: RestoreResult) -> Dict[str, Any]:
    return {
        "restore_id": result.restore_id,
        "identity": result.identity or {},
        "self_model": result.self_model or {},
        "summary": result.summary or {},
    }


def perform_startup_restore(
    *,
    artifacts_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
    session_id: str = "telegram_startup_restore",
) -> tuple[RestoreResult, PendingRestoreObservation]:
    artifacts_root = artifacts_dir or Path("artifacts")
    audit_root = audit_dir or artifacts_root / "restore" / "audit"

    restorer = SelfRestorer(artifacts_dir=artifacts_root, audit_dir=audit_root)
    result = restorer.restore(session_id=session_id)

    injection_summary: Dict[str, Any] = {"injected": False}
    recovery_hints_present = False
    standing_commitments_preview: List[str] = []

    if result.status != "failed":
        injector = ContextInjector(audit_dir=audit_root)
        runtime_context = injector.inject(_build_injection_payload(result), session_id)
        injection_summary = injector.get_injected_context_summary()
        recovery_hints_present = runtime_context.recovery_hints is not None
        standing_commitments_preview = runtime_context.standing_commitments[:3]

    observation = PendingRestoreObservation(
        restore_id=result.restore_id,
        restore_status=result.status,
        loaded_layers=list(result.loaded_layers),
        degraded_mode=bool(result.degraded_mode),
        degradation_reason=result.degradation_reason,
        restore_timestamp=result.timestamp,
        injection_summary=injection_summary,
        recovery_hints_present=recovery_hints_present,
        standing_commitments_preview=standing_commitments_preview,
    )
    return result, observation


def format_restore_summary(observation: PendingRestoreObservation) -> str:
    layers = ", ".join(observation.loaded_layers) if observation.loaded_layers else "none"
    summary = (
        f"restore_id={observation.restore_id} "
        f"status={observation.restore_status} "
        f"layers=[{layers}] "
        f"degraded_mode={observation.degraded_mode}"
    )
    if observation.degradation_reason:
        summary += f" degradation_reason={observation.degradation_reason}"
    return summary
