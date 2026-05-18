from __future__ import annotations

from typing import Any, Dict

from .continuity import build_continuity_snapshot
from .state import DevelopmentalSelfState


def compact_developmental_self_context(state: DevelopmentalSelfState) -> Dict[str, Any]:
    return state.to_runtime_projection()


def build_developmental_intake_hint(state: DevelopmentalSelfState) -> Dict[str, Any]:
    snapshot = build_continuity_snapshot(state)
    snapshot["promotion_queue_size"] = len(state.promotion_queue)
    snapshot["recent_proposal_count"] = len(state.proposal_history)
    return snapshot
