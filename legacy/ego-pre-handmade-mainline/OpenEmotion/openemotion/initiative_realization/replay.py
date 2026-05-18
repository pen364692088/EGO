from __future__ import annotations

from typing import Iterable, Optional

from .history import RealizationRevisionRecord, hash_payload
from .state import InitiativeRealizationState


class RealizationReplayError(RuntimeError):
    pass


def replay_state_from_revisions(
    revisions: Iterable[RealizationRevisionRecord],
    *,
    base_snapshot: Optional[dict] = None,
) -> Optional[InitiativeRealizationState]:
    current_hash = hash_payload(base_snapshot) if base_snapshot else None
    final_snapshot = base_snapshot
    for record in revisions:
        if record.previous_state_hash != current_hash:
            raise RealizationReplayError(
                f"revision chain mismatch at {record.revision_id}: "
                f"expected previous hash {current_hash}, got {record.previous_state_hash}"
            )
        computed_hash = hash_payload(record.after_snapshot)
        if computed_hash != record.state_hash:
            raise RealizationReplayError(
                f"state hash mismatch at {record.revision_id}: {computed_hash} != {record.state_hash}"
            )
        current_hash = computed_hash
        final_snapshot = record.after_snapshot
    if final_snapshot is None:
        return None
    return InitiativeRealizationState.model_validate(final_snapshot)
