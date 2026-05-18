from __future__ import annotations

from typing import Any, Dict, List

from .state import DevelopmentalSelfState


def compute_developmental_risk_index(state: DevelopmentalSelfState) -> float:
    continuity_gap = 1.0 - state.continuity_score
    identity_gap = 1.0 - state.identity_preservation_confidence
    weighted = (
        continuity_gap * 0.35
        + state.stagnation_signal * 0.3
        + identity_gap * 0.25
        + max(0.0, state.growth_pressure - state.continuity_score) * 0.1
    )
    return max(0.0, min(1.0, weighted))


def collect_salient_marker_refs(state: DevelopmentalSelfState, limit: int = 3) -> List[str]:
    markers = sorted(
        state.continuity_markers.values(),
        key=lambda marker: (-marker.continuity_weight, marker.marker_id),
    )
    return [marker.reference for marker in markers[:limit]]


def build_continuity_snapshot(state: DevelopmentalSelfState) -> Dict[str, Any]:
    return {
        "continuity_score": state.continuity_score,
        "growth_pressure": state.growth_pressure,
        "stagnation_signal": state.stagnation_signal,
        "identity_preservation_confidence": state.identity_preservation_confidence,
        "developmental_risk_index": state.developmental_risk_index,
        "trajectory_summary": state.trajectory_summary.model_dump(mode="json"),
        "salient_marker_refs": collect_salient_marker_refs(state),
    }
