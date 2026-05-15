from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from ego_desktop_lab.belief_state import BeliefState, clamp01
from ego_desktop_lab.learning import PRESSURE_KEYS, derive_learning_update, merge_pressure_bias
from ego_desktop_lab.outcome import OutcomeRecord, strategy_id_for_goal
from ego_desktop_lab.subject_state import SubjectState


CLAIM_CEILING = (
    "lab-only experience-memory behavior; no runtime persistence, no OpenEmotion "
    "memory write, no long-term user memory, no live benefit, no consciousness, "
    "and no alive status"
)

ACTIVE_STATUS = "active"
NEEDS_REVIEW_STATUS = "needs_review"
IGNORED_STATUS = "ignored"


@dataclass(frozen=True)
class ExperienceContext:
    goal_fingerprint: str
    goal_count: int
    evidence_band: str
    confidence_band: str
    failure_band: str
    identity_conflict: bool
    unfinished_goal_texts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperienceCard:
    card_id: str
    context_signature: dict[str, object]
    selected_goal: str
    strategy_id: str
    outcome_label: str
    valence: str
    lesson: str
    pressure_bias_delta: dict[str, float]
    strategy_confidence_delta: float
    confidence: float
    applicability: float
    decay: float
    status: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_signature", _jsonable_mapping(self.context_signature))
        object.__setattr__(
            self,
            "pressure_bias_delta",
            {key: round(float(self.pressure_bias_delta.get(key, 0.0)), 6) for key in PRESSURE_KEYS},
        )
        object.__setattr__(self, "strategy_confidence_delta", round(float(self.strategy_confidence_delta), 6))
        object.__setattr__(self, "confidence", clamp01(self.confidence))
        object.__setattr__(self, "applicability", clamp01(self.applicability))
        object.__setattr__(self, "decay", clamp01(self.decay))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExperienceBias:
    pressure_bias_delta: dict[str, float]
    strategy_confidence_delta_by_strategy: dict[str, float]
    applied_card_ids: tuple[str, ...]
    ignored_card_ids: tuple[str, ...]
    needs_review_card_ids: tuple[str, ...]
    effective_strength_by_card: dict[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "pressure_bias_delta",
            {key: round(float(self.pressure_bias_delta.get(key, 0.0)), 6) for key in PRESSURE_KEYS},
        )
        object.__setattr__(
            self,
            "strategy_confidence_delta_by_strategy",
            {
                str(key): round(max(-0.35, min(0.35, float(value))), 6)
                for key, value in self.strategy_confidence_delta_by_strategy.items()
            },
        )
        object.__setattr__(self, "applied_card_ids", tuple(self.applied_card_ids))
        object.__setattr__(self, "ignored_card_ids", tuple(self.ignored_card_ids))
        object.__setattr__(self, "needs_review_card_ids", tuple(self.needs_review_card_ids))
        object.__setattr__(
            self,
            "effective_strength_by_card",
            {str(key): round(float(value), 6) for key, value in self.effective_strength_by_card.items()},
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_current_experience_context(
    state: SubjectState,
    belief_state: BeliefState,
) -> ExperienceContext:
    goals = tuple(goal.description for goal in state.unfinished_goals)
    return ExperienceContext(
        goal_fingerprint=_goal_fingerprint(goals),
        goal_count=len(goals),
        evidence_band=_evidence_band(belief_state.evidence_strength),
        confidence_band=_confidence_band(belief_state.confidence),
        failure_band=_failure_band_from_count(len(state.recent_failures)),
        identity_conflict=bool(state.identity_conflict),
        unfinished_goal_texts=goals,
    )


def build_experience_card(
    outcome: OutcomeRecord,
    cycle_result: Mapping[str, Any] | Any | None = None,
    ticket: Mapping[str, Any] | Any | None = None,
    timestamp: str | None = None,
) -> ExperienceCard:
    strategy_id = strategy_id_for_goal(outcome.selected_plan_id)
    learning_update = derive_learning_update(outcome)
    valence = "positive" if outcome.success_score >= 0.65 else "negative"
    context_signature = _context_signature_from_cycle(cycle_result) or _fallback_context_signature(outcome)
    ticket_data = _to_dict(ticket) if ticket is not None else {}
    confidence = _experience_confidence(outcome, ticket_data)
    raw = {
        "context_signature": context_signature,
        "selected_goal": outcome.selected_plan_id,
        "strategy_id": strategy_id,
        "outcome_label": outcome.actual_effect,
        "valence": valence,
        "timestamp": timestamp or "unspecified",
        "evidence_refs": tuple(outcome.evidence_refs),
    }
    return ExperienceCard(
        card_id=f"experience:{_stable_hash(raw)}",
        context_signature=context_signature,
        selected_goal=outcome.selected_plan_id,
        strategy_id=strategy_id,
        outcome_label=outcome.actual_effect,
        valence=valence,
        lesson=_lesson_from_outcome(outcome, strategy_id, ticket_data),
        pressure_bias_delta=learning_update.pressure_bias_delta,
        strategy_confidence_delta=round((outcome.success_score - 0.50) * 0.50, 6),
        confidence=confidence,
        applicability=1.0,
        decay=1.0,
        status=ACTIVE_STATUS,
        evidence_refs=outcome.evidence_refs,
    )


def resolve_experience_conflicts(
    cards: Sequence[ExperienceCard],
) -> tuple[ExperienceCard, ...]:
    conflict_keys: dict[tuple[object, ...], set[str]] = {}
    for card in cards:
        conflict_keys.setdefault(_conflict_key(card), set()).add(card.valence)

    resolved: list[ExperienceCard] = []
    for card in cards:
        if len(conflict_keys[_conflict_key(card)]) > 1:
            resolved.append(
                replace(
                    card,
                    status=NEEDS_REVIEW_STATUS,
                    confidence=round(card.confidence * 0.25, 6),
                )
            )
        else:
            resolved.append(card)
    return tuple(resolved)


def derive_experience_bias(
    cards: Sequence[ExperienceCard],
    context: ExperienceContext | Mapping[str, Any],
) -> ExperienceBias:
    context_map = _context_to_dict(context)
    resolved = resolve_experience_conflicts(tuple(cards))
    pressure_bias: dict[str, float] = {key: 0.0 for key in PRESSURE_KEYS}
    confidence_delta_by_strategy: dict[str, float] = {}
    applied_ids: list[str] = []
    ignored_ids: list[str] = []
    needs_review_ids: list[str] = []
    strength_by_card: dict[str, float] = {}

    for card in resolved:
        if card.status == NEEDS_REVIEW_STATUS:
            needs_review_ids.append(card.card_id)
            ignored_ids.append(card.card_id)
            strength_by_card[card.card_id] = 0.0
            continue
        applicability = _applicability_score(card.context_signature, context_map)
        strength = round(applicability * card.confidence * card.applicability * card.decay, 6)
        strength_by_card[card.card_id] = strength
        if strength <= 0.0:
            ignored_ids.append(card.card_id)
            continue
        applied_ids.append(card.card_id)
        for key in PRESSURE_KEYS:
            pressure_bias[key] += card.pressure_bias_delta.get(key, 0.0) * strength
        confidence_delta_by_strategy[card.strategy_id] = (
            confidence_delta_by_strategy.get(card.strategy_id, 0.0)
            + (card.strategy_confidence_delta * strength)
        )

    return ExperienceBias(
        pressure_bias_delta=merge_pressure_bias(None, pressure_bias),
        strategy_confidence_delta_by_strategy=confidence_delta_by_strategy,
        applied_card_ids=tuple(applied_ids),
        ignored_card_ids=tuple(ignored_ids),
        needs_review_card_ids=tuple(needs_review_ids),
        effective_strength_by_card=strength_by_card,
    )


def _context_signature_from_cycle(
    cycle_result: Mapping[str, Any] | Any | None,
) -> dict[str, object] | None:
    if cycle_result is None:
        return None
    data = _to_dict(cycle_result)
    boundary = _mapping(data.get("boundary_summary") or data.get("boundary"))
    viability = _mapping(data.get("viability_snapshot") or data.get("viability"))
    before = _mapping(viability.get("before"))
    goals = tuple(str(goal) for goal in boundary.get("owned_goals") or ())
    if not goals and not before:
        return None
    uncertainty = _optional_float(before.get("uncertainty_precision"))
    prediction_error = _optional_float(before.get("prediction_error"))
    return {
        "goal_fingerprint": _goal_fingerprint(goals),
        "goal_count": len(goals),
        "evidence_band": _evidence_band_from_uncertainty(uncertainty),
        "confidence_band": "unknown",
        "failure_band": _failure_band_from_prediction_error(prediction_error),
        "identity_conflict": False,
    }


def _fallback_context_signature(outcome: OutcomeRecord) -> dict[str, object]:
    return {
        "goal_fingerprint": f"scenario:{outcome.scenario_id}",
        "goal_count": 0,
        "evidence_band": "unknown",
        "confidence_band": "unknown",
        "failure_band": "unknown",
        "identity_conflict": False,
    }


def _experience_confidence(
    outcome: OutcomeRecord,
    ticket_data: Mapping[str, Any],
) -> float:
    ticket_confidence = _optional_float(ticket_data.get("confidence"))
    if ticket_confidence is None:
        ticket_confidence = 0.70
    outcome_strength = abs(outcome.success_score - 0.50) * 0.50
    prediction_signal = outcome.prediction_error * 0.15
    return clamp01(ticket_confidence + outcome_strength + prediction_signal)


def _lesson_from_outcome(
    outcome: OutcomeRecord,
    strategy_id: str,
    ticket_data: Mapping[str, Any],
) -> str:
    category = ticket_data.get("category")
    if outcome.success_score >= 0.65:
        return f"{strategy_id} worked in this context; prefer it only when the context signature matches."
    if category:
        return f"{strategy_id} failed with {category}; reduce repeat tendency and prefer repair in matching contexts."
    return f"{strategy_id} failed in this context; reduce repeat tendency and prefer repair in matching contexts."


def _applicability_score(
    card_signature: Mapping[str, Any],
    context: Mapping[str, Any],
) -> float:
    card_goal = str(card_signature.get("goal_fingerprint") or "")
    context_goal = str(context.get("goal_fingerprint") or "")
    if not card_goal or card_goal != context_goal:
        return 0.0

    evidence_score = _field_match_score(card_signature.get("evidence_band"), context.get("evidence_band"))
    confidence_score = _field_match_score(card_signature.get("confidence_band"), context.get("confidence_band"))
    failure_score = _field_match_score(card_signature.get("failure_band"), context.get("failure_band"))
    identity_score = 1.0 if bool(card_signature.get("identity_conflict")) == bool(context.get("identity_conflict")) else 0.0

    if evidence_score == 0.0 or failure_score == 0.0 or identity_score == 0.0:
        return 0.0
    return round(evidence_score * confidence_score * failure_score * identity_score, 6)


def _field_match_score(left: Any, right: Any) -> float:
    left_text = str(left or "unknown")
    right_text = str(right or "unknown")
    if "unknown" in {left_text, right_text}:
        return 1.0
    return 1.0 if left_text == right_text else 0.0


def _context_to_dict(context: ExperienceContext | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(context, ExperienceContext):
        return context.to_dict()
    return _mapping(context)


def _goal_fingerprint(goals: Sequence[str]) -> str:
    normalized = tuple(sorted(str(goal).strip().lower() for goal in goals if str(goal).strip()))
    if not normalized:
        return "none"
    return _stable_hash({"goals": normalized})


def _evidence_band(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"


def _confidence_band(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    return "low"


def _evidence_band_from_uncertainty(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0.25:
        return "high"
    if value <= 0.55:
        return "medium"
    return "low"


def _failure_band_from_count(count: int) -> str:
    if count >= 2:
        return "high"
    if count >= 1:
        return "some"
    return "none"


def _failure_band_from_prediction_error(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value >= 0.60:
        return "high"
    if value >= 0.25:
        return "some"
    return "none"


def _conflict_key(card: ExperienceCard) -> tuple[object, ...]:
    signature = card.context_signature
    return (
        signature.get("goal_fingerprint"),
        signature.get("evidence_band"),
        signature.get("failure_band"),
        signature.get("identity_conflict"),
        card.strategy_id,
    )


def _stable_hash(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _to_dict(value: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "to_dict"):
        return _to_dict(value.to_dict())
    if is_dataclass(value):
        return _to_dict(asdict(value))
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _jsonable_mapping(value: Mapping[str, Any]) -> dict[str, object]:
    return {str(key): _jsonable(item) for key, item in value.items()}


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
