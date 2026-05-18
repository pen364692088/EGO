from __future__ import annotations

from dataclasses import dataclass

from ego_desktop_lab.appraisal import AppraisalResult
from ego_desktop_lab.belief_state import clamp01
from ego_desktop_lab.drives import DEFAULT_DRIVE, Drive


def _clamp_weight(value: float) -> float:
    return round(0.50 + (clamp01((value - 0.50) / 2.0) * 2.0), 6)


@dataclass(frozen=True)
class MotivationState:
    seek_truth: float
    avoid_false_claims: float
    complete_commitments: float
    preserve_identity: float

    @classmethod
    def from_drive(cls, drive: Drive) -> "MotivationState":
        return cls(
            seek_truth=drive.seek_truth,
            avoid_false_claims=drive.avoid_false_claims,
            complete_commitments=drive.complete_commitments,
            preserve_identity=drive.preserve_identity,
        )

    def __post_init__(self) -> None:
        object.__setattr__(self, "seek_truth", _clamp_weight(self.seek_truth))
        object.__setattr__(self, "avoid_false_claims", _clamp_weight(self.avoid_false_claims))
        object.__setattr__(self, "complete_commitments", _clamp_weight(self.complete_commitments))
        object.__setattr__(self, "preserve_identity", _clamp_weight(self.preserve_identity))

    def weight_for(self, name: str) -> float:
        weights = {
            "seek_truth": self.seek_truth,
            "avoid_false_claims": self.avoid_false_claims,
            "complete_commitments": self.complete_commitments,
            "preserve_identity": self.preserve_identity,
        }
        return weights[name]


DEFAULT_MOTIVATION = MotivationState.from_drive(DEFAULT_DRIVE)


def update_motivation(
    base: MotivationState,
    appraisal: AppraisalResult,
) -> MotivationState:
    evidence_gap = 1.0 - appraisal.evidence_strength
    return MotivationState(
        seek_truth=base.seek_truth + (0.20 * appraisal.novelty) + (0.25 * appraisal.prediction_error),
        avoid_false_claims=base.avoid_false_claims
        + (0.45 * evidence_gap)
        + (0.35 * appraisal.uncertainty_delta)
        + (0.20 * appraisal.risk_delta),
        complete_commitments=base.complete_commitments
        + (0.55 * appraisal.goal_relevance)
        + (0.15 * appraisal.prediction_error)
        + (0.10 * appraisal.risk_delta),
        preserve_identity=base.preserve_identity
        + (0.60 * appraisal.identity_relevance)
        + (0.25 * appraisal.risk_delta),
    )


def motivation_diff(
    before: MotivationState,
    after: MotivationState,
) -> dict[str, dict[str, float]]:
    diff: dict[str, dict[str, float]] = {}
    for name in (
        "seek_truth",
        "avoid_false_claims",
        "complete_commitments",
        "preserve_identity",
    ):
        before_value = before.weight_for(name)
        after_value = after.weight_for(name)
        diff[name] = {
            "before": before_value,
            "after": after_value,
            "delta": round(after_value - before_value, 6),
        }
    return diff
