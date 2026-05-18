from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.policy import GATE_ACTION_STATUS, GATE_REASONS


@dataclass(frozen=True)
class GateDecision:
    status: str
    reason: str
    allowed_as: str


def evaluate_gate(proposed_action: str) -> GateDecision:
    status = GATE_ACTION_STATUS[proposed_action]
    allowed_as = proposed_action if status == "allow" else "none"
    return GateDecision(
        status=status,
        reason=GATE_REASONS[proposed_action],
        allowed_as=allowed_as,
    )
