from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openemotion.proto_self_v2.seed_schemas import KernelEvent
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState


@dataclass(slots=True)
class Affordance:
    action_type: str
    expected_gain: float
    risk_level: str
    reversible: bool
    target: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


def _pick_target(runtime_summary: Dict[str, Any], payload: Dict[str, Any]) -> Optional[str]:
    return (
        payload.get("resolved_target_path")
        or payload.get("resolved_target_name")
        or runtime_summary.get("resolved_target_path")
        or runtime_summary.get("resolved_target_name")
        or runtime_summary.get("recent_failure_target")
    )


def extract_affordances(event: KernelEvent, state: ProtoSelfSeedState) -> List[Affordance]:
    runtime = event.runtime_summary or {}
    payload = event.payload or {}
    affordances: List[Affordance] = []
    target = _pick_target(runtime, payload)

    if target:
        affordances.append(
            Affordance(
                action_type="inspect_file",
                target=target,
                expected_gain=0.62,
                risk_level="low",
                reversible=True,
                metadata={"origin": "resolved_target"},
            )
        )
        if runtime.get("request_mode") == "write":
            affordances.append(
                Affordance(
                    action_type="write_file",
                    target=target,
                    expected_gain=0.68,
                    risk_level="medium",
                    reversible=False,
                    metadata={"origin": "write_target"},
                )
            )

    if runtime.get("recent_failure_target"):
        affordances.append(
            Affordance(
                action_type="review_recent_failure",
                target=str(runtime.get("recent_failure_target")),
                expected_gain=0.58,
                risk_level="low",
                reversible=True,
                metadata={"origin": "recent_failure"},
            )
        )

    pending_commitment = runtime.get("pending_commitment") or state.focus_goal.pending_commitment
    if pending_commitment:
        affordances.append(
            Affordance(
                action_type="continue_pending_commitment",
                target=str(pending_commitment),
                expected_gain=0.66,
                risk_level="low",
                reversible=True,
                metadata={"origin": "pending_commitment"},
            )
        )

    if runtime.get("clarification_needed") or runtime.get("confirm_pending"):
        affordances.append(
            Affordance(
                action_type="ask_user",
                expected_gain=0.42,
                risk_level="low",
                reversible=True,
                metadata={"origin": "clarification"},
            )
        )

    browser_tabs = runtime.get("browser_tabs") or []
    if browser_tabs:
        affordances.append(
            Affordance(
                action_type="inspect_browser",
                target=str(browser_tabs[0]),
                expected_gain=0.50,
                risk_level="low",
                reversible=True,
                metadata={"origin": "browser_tabs"},
            )
        )

    return affordances
