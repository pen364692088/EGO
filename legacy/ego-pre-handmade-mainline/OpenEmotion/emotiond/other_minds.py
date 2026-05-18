"""
MVP-6.2 D5: Other-Minds Model v0

Per-target latent model for social inference.

Design constraints:
- Learns only from interaction/ledger/tool cooperation signals.
- Influences appraisal/policy (social_threat, controllability, strategy bias).
- MUST NOT directly trigger high-impact events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class OtherMindState:
    reliability: float = 0.5
    cooperativeness: float = 0.5
    attentiveness: float = 0.5
    valence_toward_me: float = 0.0  # [-1, 1]
    uncertainty: float = 0.7
    last_updated: float = 0.0

    def clamp(self) -> "OtherMindState":
        self.reliability = max(0.0, min(1.0, self.reliability))
        self.cooperativeness = max(0.0, min(1.0, self.cooperativeness))
        self.attentiveness = max(0.0, min(1.0, self.attentiveness))
        self.valence_toward_me = max(-1.0, min(1.0, self.valence_toward_me))
        self.uncertainty = max(0.0, min(1.0, self.uncertainty))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _mix(old: float, target: float, alpha: float) -> float:
    return (1 - alpha) * old + alpha * target


class OtherMindsModel:
    """In-memory per-target other-minds model with deterministic updates."""

    def __init__(self, alpha: float = 0.2, uncertainty_decay: float = 0.06):
        self.alpha = alpha
        self.uncertainty_decay = uncertainty_decay
        self._states: Dict[str, OtherMindState] = {}

    def get_state(self, target: str) -> OtherMindState:
        if target not in self._states:
            self._states[target] = OtherMindState(last_updated=time.time())
        return self._states[target]

    def reset(self) -> None:
        self._states = {}

    def export(self) -> Dict[str, Dict[str, Any]]:
        return {k: v.to_dict() for k, v in self._states.items()}

    def import_state(self, data: Dict[str, Dict[str, Any]]) -> None:
        self._states = {}
        for k, v in data.items():
            self._states[k] = OtherMindState(**v).clamp()

    def update_from_interaction(self, target: str, outcome: str, strength: float = 1.0) -> OtherMindState:
        """
        Update based on interaction outcomes.

        outcome ∈ {continue, success, apology, care, ignored, interrupted, rejection,
                   betrayal, cold, unclear}
        """
        s = self.get_state(target)
        alpha = max(0.0, min(1.0, self.alpha * max(0.2, min(2.0, strength))))

        positive = {"continue", "success", "apology", "care", "repair_success"}
        negative = {"ignored", "interrupted", "rejection", "betrayal", "cold"}

        if outcome in positive:
            s.reliability = _mix(s.reliability, 0.75, alpha)
            s.cooperativeness = _mix(s.cooperativeness, 0.75, alpha)
            s.attentiveness = _mix(s.attentiveness, 0.75, alpha)
            s.valence_toward_me = _mix(s.valence_toward_me, 0.35, alpha)
            s.uncertainty = _mix(s.uncertainty, 0.25, self.uncertainty_decay)
        elif outcome in negative:
            s.reliability = _mix(s.reliability, 0.2, alpha)
            s.cooperativeness = _mix(s.cooperativeness, 0.2, alpha)
            if outcome in {"ignored", "cold", "interrupted"}:
                s.attentiveness = _mix(s.attentiveness, 0.15, alpha)
            else:
                s.attentiveness = _mix(s.attentiveness, 0.3, alpha)
            val_target = -0.6 if outcome in {"betrayal", "rejection"} else -0.35
            s.valence_toward_me = _mix(s.valence_toward_me, val_target, alpha)
            s.uncertainty = _mix(s.uncertainty, 0.35, self.uncertainty_decay)
        else:  # unclear/unknown
            s.uncertainty = _mix(s.uncertainty, 0.85, self.uncertainty_decay)

        s.last_updated = time.time()
        return s.clamp()

    def update_from_ledger(self, target: str, event: str, severity: float = 1.0) -> OtherMindState:
        """
        Update from ledger-style evidence.

        event ∈ {promise_kept, promise_broken, repeated_kept, repeated_broken}
        """
        s = self.get_state(target)
        sev = max(0.1, min(2.0, severity))
        alpha = max(0.0, min(1.0, self.alpha * sev))

        if event in {"promise_kept", "repeated_kept"}:
            bonus = 0.85 if event == "repeated_kept" else 0.75
            s.reliability = _mix(s.reliability, bonus, alpha)
            s.cooperativeness = _mix(s.cooperativeness, 0.65, alpha * 0.8)
            s.valence_toward_me = _mix(s.valence_toward_me, 0.25, alpha * 0.6)
            s.uncertainty = _mix(s.uncertainty, 0.2, self.uncertainty_decay)
        elif event in {"promise_broken", "repeated_broken"}:
            malus = 0.08 if event == "repeated_broken" else 0.18
            s.reliability = _mix(s.reliability, malus, alpha)
            s.cooperativeness = _mix(s.cooperativeness, 0.25, alpha)
            s.valence_toward_me = _mix(s.valence_toward_me, -0.55, alpha)
            s.uncertainty = _mix(s.uncertainty, 0.3, self.uncertainty_decay)

        s.last_updated = time.time()
        return s.clamp()

    def update_from_tool_result(self, target: str, status: str) -> OtherMindState:
        """Optional indirect cooperation signal from tool outcomes tied to target."""
        if status in {"success", "partial_success"}:
            return self.update_from_interaction(target, "continue", strength=0.6)
        if status in {"failure", "timeout", "error"}:
            return self.update_from_interaction(target, "interrupted", strength=0.5)
        return self.get_state(target)

    def appraisal_bias(self, target: str) -> Dict[str, float]:
        """
        Return appraisal modifiers.
        - social_threat increases when low reliability/cooperation/valence.
        - controllability increases with cooperativeness/attentiveness.
        """
        s = self.get_state(target)
        trust_proxy = (s.reliability + s.cooperativeness + s.attentiveness) / 3.0
        social_threat_delta = (1.0 - trust_proxy) * 0.35 + max(0.0, -s.valence_toward_me) * 0.2
        controllability_delta = (s.cooperativeness - 0.5) * 0.25 + (s.attentiveness - 0.5) * 0.15
        damp = 1.0 - 0.4 * s.uncertainty
        return {
            "social_threat_delta": social_threat_delta * damp,
            "controllability_delta": controllability_delta * damp,
            "uncertainty": s.uncertainty,
        }

    def strategy_bias(self, target: str) -> Dict[str, float]:
        """
        Bias over candidate intents/actions. Positive values favor.
        Keys align with existing policy vocabulary.
        """
        s = self.get_state(target)
        confidence = 1.0 - s.uncertainty
        trust_proxy = (s.reliability + s.cooperativeness) / 2.0

        repair = (0.5 * trust_proxy + 0.5 * max(0.0, s.valence_toward_me)) * confidence
        boundary = (1.0 - trust_proxy) * confidence * 0.9
        withdraw = (1.0 - s.attentiveness) * confidence * 0.85

        return {
            "repair": repair - 0.25,
            "repair_offer": repair - 0.25,
            "seek": repair - 0.3,
            "boundary": boundary - 0.2,
            "set_boundary": boundary - 0.2,
            "withdraw": withdraw - 0.2,
            # Explicitly keep high-impact paths untouched.
            "attack": 0.0,
            "retaliate": 0.0,
        }


_other_minds: Optional[OtherMindsModel] = None


def get_other_minds_model() -> OtherMindsModel:
    global _other_minds
    if _other_minds is None:
        _other_minds = OtherMindsModel()
    return _other_minds


def reset_other_minds_model() -> None:
    global _other_minds
    _other_minds = None


def apply_other_minds_to_appraisal(target: str, social_threat: float, controllability: float) -> Dict[str, float]:
    model = get_other_minds_model()
    bias = model.appraisal_bias(target)
    return {
        "social_threat": max(0.0, min(1.0, social_threat + bias["social_threat_delta"])),
        "controllability": max(0.0, min(1.0, controllability + bias["controllability_delta"])),
        "other_minds_uncertainty": bias["uncertainty"],
    }


def apply_other_minds_to_intent_scores(target: str, scores: Dict[str, float]) -> Dict[str, float]:
    model = get_other_minds_model()
    bias = model.strategy_bias(target)
    out = dict(scores)
    for k, v in bias.items():
        if k in out:
            out[k] += v
    return out
