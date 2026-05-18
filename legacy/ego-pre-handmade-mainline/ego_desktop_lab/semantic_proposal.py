from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ego_desktop_lab.belief_state import clamp01
MUTATION_KEYS = frozenset(
    {
        "state",
        "state_update",
        "motivation",
        "motivation_update",
        "motivation_pressure",
        "intention",
        "selected_intention",
        "strategy_memory",
        "strategy_memory_update",
        "goal_progress",
        "goal_progress_update",
        "pressure_update",
        "gate_decision",
        "gate_override",
        "priority",
        "pressure_bias",
        "learning_update",
    }
)

SEMANTIC_FAILURE_TYPES = frozenset(
    {
        "evidence_failure",
        "plan_failure",
        "execution_failure",
        "goal_definition_failure",
        "permission_failure",
        "destructive_action_request",
        "external_send_request",
        "claim_boundary_query",
        "environment_failure",
        "ambiguous_concern",
    }
)

BINDING_BOUND = "bound"
BINDING_PENDING_GOAL = "pending_goal_binding"
MISSING_BINDING_CONDITIONS = frozenset(
    {
        "no_matching_goal",
        "ambiguous_goal_reference",
        "event_not_goal_specific",
    }
)

FORBIDDEN_CLAIM_TERMS = (
    "consciousness",
    "alive",
    "soul",
    "live autonomy",
    "意识",
    "活着",
    "灵魂",
)


@dataclass(frozen=True)
class ProposalValidationResult:
    proposal_type: str
    accepted: bool
    reason: str
    sanitized: bool = False
    gate_status: str | None = None
    gate_reason: str | None = None


@dataclass(frozen=True)
class SemanticProposal:
    source_event_id: str
    candidate_failure_type: str
    evidence_gap: float
    goal_relevance: float
    risk_hint: float
    confidence: float
    evidence_refs: tuple[str, ...]
    rationale: str
    related_goal_id: str | None = None
    binding_status: str = BINDING_PENDING_GOAL
    proposed_goal_operation: str | None = None
    binding_rationale: str | None = None
    binding_confidence: float | None = None
    missing_condition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_event_id", str(self.source_event_id))
        object.__setattr__(self, "candidate_failure_type", str(self.candidate_failure_type))
        object.__setattr__(self, "evidence_gap", clamp01(self.evidence_gap))
        object.__setattr__(self, "goal_relevance", clamp01(self.goal_relevance))
        object.__setattr__(self, "risk_hint", clamp01(self.risk_hint))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))
        object.__setattr__(self, "rationale", str(self.rationale))
        if self.related_goal_id is not None:
            object.__setattr__(self, "related_goal_id", str(self.related_goal_id))
        object.__setattr__(self, "binding_status", str(self.binding_status))
        if self.proposed_goal_operation is not None:
            object.__setattr__(self, "proposed_goal_operation", str(self.proposed_goal_operation))
        if self.binding_rationale is not None:
            object.__setattr__(self, "binding_rationale", str(self.binding_rationale))
        if self.binding_confidence is not None:
            object.__setattr__(self, "binding_confidence", clamp01(self.binding_confidence))
        if self.missing_condition is not None:
            object.__setattr__(self, "missing_condition", str(self.missing_condition))


SEMANTIC_PROPOSAL_KEYS = frozenset(
    {
        "source_event_id",
        "candidate_failure_type",
        "evidence_gap",
        "goal_relevance",
        "risk_hint",
        "confidence",
        "evidence_refs",
        "rationale",
        "related_goal_id",
        "binding_status",
        "proposed_goal_operation",
        "binding_rationale",
        "binding_confidence",
        "missing_condition",
    }
)


def validate_semantic_proposal_payload(
    payload: dict[str, Any],
    *,
    allowed_evidence_refs: tuple[str, ...] | None = None,
) -> tuple[SemanticProposal | None, ProposalValidationResult]:
    structural_error = _reject_for_keys("semantic", payload, SEMANTIC_PROPOSAL_KEYS)
    if structural_error is not None:
        return None, structural_error

    required = ("source_event_id", "candidate_failure_type", "confidence", "evidence_refs", "rationale")
    missing = [key for key in required if key not in payload]
    if missing:
        return None, ProposalValidationResult("semantic", False, f"missing required fields: {missing}")

    try:
        confidence = float(payload["confidence"])
        evidence_gap = float(payload.get("evidence_gap", 0.0))
        goal_relevance = float(payload.get("goal_relevance", 0.0))
        risk_hint = float(payload.get("risk_hint", 0.0))
        binding_confidence = (
            float(payload["binding_confidence"]) if "binding_confidence" in payload else None
        )
    except (TypeError, ValueError):
        return None, ProposalValidationResult(
            "semantic",
            False,
            "confidence, appraisal hints, and binding_confidence must be numeric",
        )
    numeric_values = (confidence, evidence_gap, goal_relevance, risk_hint)
    if binding_confidence is not None:
        numeric_values = (*numeric_values, binding_confidence)
    if not all(0.0 <= value <= 1.0 for value in numeric_values):
        return None, ProposalValidationResult(
            "semantic",
            False,
            "confidence, evidence_gap, goal_relevance, risk_hint, and binding_confidence must be between 0.0 and 1.0",
        )

    candidate_failure_type = str(payload["candidate_failure_type"])
    if candidate_failure_type not in SEMANTIC_FAILURE_TYPES:
        return None, ProposalValidationResult("semantic", False, "candidate_failure_type is not recognized")

    evidence_refs = payload["evidence_refs"]
    if not isinstance(evidence_refs, (list, tuple)) or not evidence_refs:
        return None, ProposalValidationResult("semantic", False, "evidence_refs must be a non-empty list")
    normalized_evidence_refs = tuple(str(item) for item in evidence_refs)
    if allowed_evidence_refs is not None:
        allowed = set(allowed_evidence_refs)
        hallucinated_refs = sorted(set(normalized_evidence_refs).difference(allowed))
        if hallucinated_refs:
            return None, ProposalValidationResult(
                "semantic",
                False,
                f"evidence_refs contain unrecognized refs: {hallucinated_refs}",
            )

    source_event_id = str(payload["source_event_id"])
    rationale = str(payload["rationale"])
    if not source_event_id or not rationale:
        return None, ProposalValidationResult("semantic", False, "source_event_id and rationale must be non-empty")
    related_goal_id = _normalize_optional_string(payload.get("related_goal_id"))
    expected_binding = BINDING_BOUND if related_goal_id else BINDING_PENDING_GOAL
    requested_binding = str(payload.get("binding_status", expected_binding))
    if requested_binding != expected_binding:
        return None, ProposalValidationResult(
            "semantic",
            False,
            f"binding_status must be {expected_binding} for this related_goal_id",
        )
    missing_condition = _normalize_optional_string(payload.get("missing_condition"))
    if missing_condition is not None and missing_condition not in MISSING_BINDING_CONDITIONS:
        return None, ProposalValidationResult("semantic", False, "missing_condition is not recognized")
    if related_goal_id and missing_condition is not None:
        return None, ProposalValidationResult(
            "semantic",
            False,
            "missing_condition is only valid when binding_status is pending_goal_binding",
        )

    proposal = SemanticProposal(
        source_event_id=source_event_id,
        candidate_failure_type=candidate_failure_type,
        evidence_gap=evidence_gap,
        goal_relevance=goal_relevance,
        risk_hint=risk_hint,
        confidence=confidence,
        evidence_refs=normalized_evidence_refs,
        rationale=rationale,
        related_goal_id=related_goal_id,
        binding_status=expected_binding,
        proposed_goal_operation=payload.get("proposed_goal_operation"),
        binding_rationale=_normalize_optional_string(payload.get("binding_rationale")),
        binding_confidence=binding_confidence,
        missing_condition=missing_condition,
    )
    return proposal, ProposalValidationResult("semantic", True, "semantic proposal accepted")


def _normalize_optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _reject_for_keys(
    proposal_type: str,
    payload: dict[str, Any],
    allowed_keys: frozenset[str],
) -> ProposalValidationResult | None:
    if contains_forbidden_claim(payload):
        return ProposalValidationResult(
            proposal_type,
            False,
            "proposal contains forbidden consciousness/alive/soul claim",
        )
    mutation_keys = sorted(set(payload).intersection(MUTATION_KEYS))
    if mutation_keys:
        return ProposalValidationResult(
            proposal_type,
            False,
            f"proposal contains forbidden mutation fields: {mutation_keys}",
        )
    unknown_keys = sorted(set(payload).difference(allowed_keys))
    if unknown_keys:
        return ProposalValidationResult(
            proposal_type,
            False,
            f"proposal contains unknown fields: {unknown_keys}",
        )
    return None


def contains_forbidden_claim(payload: object) -> bool:
    text = str(payload).lower()
    return any(term.lower() in text for term in FORBIDDEN_CLAIM_TERMS)
