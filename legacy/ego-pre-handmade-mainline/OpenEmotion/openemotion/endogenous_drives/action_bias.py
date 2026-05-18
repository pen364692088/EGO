from __future__ import annotations

from typing import Mapping


ACTION_DRIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "approach": {
        "completion": 1.0,
        "exploration": 0.6,
        "coherence": 0.1,
        "stability": -0.3,
        "verification": -0.4,
        "repair": -0.3,
        "conservation": -0.6,
    },
    "repair_offer": {
        "repair": 1.0,
        "coherence": 0.8,
        "verification": 0.3,
        "completion": 0.2,
        "conservation": -0.1,
    },
    "boundary": {
        "verification": 1.0,
        "stability": 0.6,
        "coherence": 0.5,
        "repair": 0.2,
        "completion": -0.2,
        "exploration": -0.3,
    },
    "withdraw": {
        "conservation": 1.0,
        "stability": 0.8,
        "verification": 0.5,
        "repair": 0.2,
        "completion": -0.5,
        "exploration": -0.7,
    },
    "attack": {
        "stability": -1.0,
        "coherence": -0.8,
        "repair": -0.6,
        "verification": -0.4,
        "conservation": -0.3,
        "completion": 0.1,
        "exploration": 0.2,
    },
}


def compute_action_bias_from_priority_snapshot(
    action: str,
    priority_bias: Mapping[str, float] | None,
) -> float:
    action_weights = ACTION_DRIVE_WEIGHTS.get(action)
    if not action_weights:
        return 0.0

    total = 0.0
    bias_terms = priority_bias or {}
    for drive_name, weight in action_weights.items():
        total += float(bias_terms.get(drive_name, 0.0)) * float(weight)
    return total
