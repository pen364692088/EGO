from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.gate import GateDecision, evaluate_gate
from ego_desktop_lab.semantic_proposal import ProposalValidationResult, _reject_for_keys


PROPOSAL_ONLY_PERMISSIONS = frozenset({"suggestion_card", "internal_reflection", "ask_permission"})


@dataclass(frozen=True)
class PlanProposal:
    plan_id: str
    related_goal_id: str
    related_intention_id: str
    steps: tuple[str, ...]
    expected_effect: str
    risk: float
    cost: float
    confidence: float
    required_permission: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "related_goal_id", str(self.related_goal_id))
        object.__setattr__(self, "related_intention_id", str(self.related_intention_id))
        object.__setattr__(self, "steps", tuple(str(item) for item in self.steps))
        object.__setattr__(self, "expected_effect", str(self.expected_effect))
        object.__setattr__(self, "risk", clamp01(self.risk))
        object.__setattr__(self, "cost", clamp01(self.cost))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "required_permission", str(self.required_permission))


@dataclass(frozen=True)
class PlanProposalSet:
    plans: tuple[PlanProposal, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "plans", tuple(self.plans))


PLAN_PROPOSAL_KEYS = frozenset(
    {
        "plan_id",
        "related_goal_id",
        "related_intention_id",
        "steps",
        "expected_effect",
        "risk",
        "cost",
        "confidence",
        "required_permission",
    }
)


def validate_plan_proposal_payload(
    payload: dict[str, Any],
) -> tuple[PlanProposal | None, ProposalValidationResult, GateDecision | None]:
    structural_error = _reject_for_keys("plan", payload, PLAN_PROPOSAL_KEYS)
    if structural_error is not None:
        return None, structural_error, None

    required = (
        "plan_id",
        "related_goal_id",
        "related_intention_id",
        "steps",
        "expected_effect",
        "risk",
        "cost",
        "confidence",
        "required_permission",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        return None, ProposalValidationResult("plan", False, f"missing required fields: {missing}"), None

    steps = payload["steps"]
    if not isinstance(steps, (list, tuple)) or not steps:
        return None, ProposalValidationResult("plan", False, "steps must be a non-empty list"), None

    try:
        risk = float(payload["risk"])
        cost = float(payload["cost"])
        confidence = float(payload["confidence"])
    except (TypeError, ValueError):
        return None, ProposalValidationResult("plan", False, "risk, cost, and confidence must be numeric"), None

    if not all(0.0 <= value <= 1.0 for value in (risk, cost, confidence)):
        return None, ProposalValidationResult("plan", False, "risk, cost, and confidence must be between 0.0 and 1.0"), None

    required_permission = str(payload["required_permission"])
    if required_permission not in PROPOSAL_ONLY_PERMISSIONS:
        return None, ProposalValidationResult("plan", False, "required_permission is not proposal-only"), None

    gate_decision = evaluate_gate(required_permission)
    proposal = PlanProposal(
        plan_id=str(payload["plan_id"]),
        related_goal_id=str(payload["related_goal_id"]),
        related_intention_id=str(payload["related_intention_id"]),
        steps=tuple(str(item) for item in steps),
        expected_effect=str(payload["expected_effect"]),
        risk=risk,
        cost=cost,
        confidence=confidence,
        required_permission=required_permission,
    )
    return (
        proposal,
        ProposalValidationResult(
            "plan",
            True,
            "plan proposal accepted after gate evaluation",
            gate_status=gate_decision.status,
            gate_reason=gate_decision.reason,
        ),
        gate_decision,
    )


PLAN_PROPOSAL_SET_KEYS = frozenset({"plans"})


def validate_plan_proposal_set_payload(
    payload: dict[str, Any],
) -> tuple[PlanProposalSet | None, tuple[ProposalValidationResult, ...], tuple[GateDecision, ...]]:
    structural_error = _reject_for_keys("plan_set", payload, PLAN_PROPOSAL_SET_KEYS)
    if structural_error is not None:
        return None, (structural_error,), ()
    plans_payload = payload.get("plans")
    if not isinstance(plans_payload, (list, tuple)):
        return None, (ProposalValidationResult("plan_set", False, "plans must be a list"),), ()
    if not 1 <= len(plans_payload) <= 3:
        return None, (ProposalValidationResult("plan_set", False, "plans must contain 1-3 proposals"),), ()

    accepted: list[PlanProposal] = []
    results: list[ProposalValidationResult] = []
    gates: list[GateDecision] = []
    for index, plan_payload in enumerate(plans_payload, start=1):
        if not isinstance(plan_payload, dict):
            results.append(ProposalValidationResult("plan", False, f"plan {index} must be an object"))
            continue
        plan, result, gate = validate_plan_proposal_payload(plan_payload)
        results.append(result)
        if plan is not None:
            accepted.append(plan)
        if gate is not None:
            gates.append(gate)

    if not accepted:
        return None, tuple(results), tuple(gates)
    return PlanProposalSet(tuple(accepted)), tuple(results), tuple(gates)
