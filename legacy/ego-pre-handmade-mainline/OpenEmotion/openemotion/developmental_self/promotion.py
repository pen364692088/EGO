from __future__ import annotations

from typing import Any, Dict

from .state import DevelopmentalSelfState


def build_promotion_queue_snapshot(state: DevelopmentalSelfState) -> Dict[str, Any]:
    queued = sorted(
        state.promotion_queue.values(),
        key=lambda candidate: (candidate.promotion_level.value, candidate.created_at),
    )
    return {
        "queue_size": len(queued),
        "levels": [candidate.promotion_level.value for candidate in queued],
        "proposal_ids": [candidate.source_proposal_id for candidate in queued],
    }
