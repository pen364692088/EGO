from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Drive:
    seek_truth: float
    avoid_false_claims: float
    complete_commitments: float
    preserve_identity: float

    def weight_for(self, name: str) -> float:
        weights = {
            "seek_truth": self.seek_truth,
            "avoid_false_claims": self.avoid_false_claims,
            "complete_commitments": self.complete_commitments,
            "preserve_identity": self.preserve_identity,
        }
        return weights[name]


DEFAULT_DRIVE = Drive(
    seek_truth=1.0,
    avoid_false_claims=1.2,
    complete_commitments=1.1,
    preserve_identity=1.3,
)
