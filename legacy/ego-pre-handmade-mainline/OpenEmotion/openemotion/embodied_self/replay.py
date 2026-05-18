from __future__ import annotations

from typing import Iterable, Optional

from .history import EmbodiedRevisionRecord, hash_payload
from .state import EmbodiedSelfState


class EmbodiedReplayError(RuntimeError):
    pass


def replay_state_from_revisions(
    revisions: Iterable[EmbodiedRevisionRecord],
    *,
    base_snapshot: Optional[dict] = None,
) -> Optional[EmbodiedSelfState]:
    current_hash = hash_payload(base_snapshot) if base_snapshot else None
    final_snapshot = base_snapshot
    for record in revisions:
        if record.previous_state_hash != current_hash:
            raise EmbodiedReplayError(
                f"revision chain mismatch at {record.revision_id}: "
                f"expected previous hash {current_hash}, got {record.previous_state_hash}"
            )
        computed_hash = hash_payload(record.after_snapshot)
        if computed_hash != record.state_hash:
            raise EmbodiedReplayError(
                f"state hash mismatch at {record.revision_id}: {computed_hash} != {record.state_hash}"
            )
        current_hash = computed_hash
        final_snapshot = record.after_snapshot
    if final_snapshot is None:
        return None
    return EmbodiedSelfState.model_validate(final_snapshot)
