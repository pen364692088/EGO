from __future__ import annotations

from dataclasses import dataclass


def clamp01(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


@dataclass(frozen=True)
class BeliefState:
    known_facts: tuple[str, ...]
    unknowns: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence_strength: float
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "known_facts", tuple(self.known_facts))
        object.__setattr__(self, "unknowns", tuple(self.unknowns))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "evidence_strength", clamp01(self.evidence_strength))
        object.__setattr__(self, "confidence", clamp01(self.confidence))


def build_demo_belief_state() -> BeliefState:
    return BeliefState(
        known_facts=("mock state contains one unfinished goal",),
        unknowns=("whether reflection changed later behavior", "whether evidence is strong enough"),
        assumptions=("proposal-only suggestion can reduce risk",),
        evidence_strength=0.38,
        confidence=0.44,
    )
