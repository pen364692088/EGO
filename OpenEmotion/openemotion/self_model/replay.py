"""
Formal owner replay helpers for MVP13 self-model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .model import SelfModel
from .store import SelfModelRevisionRecord, SelfModelStore


@dataclass(frozen=True)
class SelfModelReplayResult:
    state: Optional[SelfModel]
    revision_count: int
    valid_chain: bool


class SelfModelReplay:
    def __init__(self, store: SelfModelStore) -> None:
        self.store = store

    def load_revisions(self) -> List[SelfModelRevisionRecord]:
        return self.store.load_revision_records()

    def validate_chain(self, revisions: List[SelfModelRevisionRecord]) -> bool:
        previous_hash: Optional[str] = None
        for revision in revisions:
            if revision.previous_state_hash != previous_hash:
                return False
            previous_hash = revision.state_hash
        return True

    def replay(self) -> SelfModelReplayResult:
        revisions = self.load_revisions()
        if not revisions:
            state = self.store.load()
            return SelfModelReplayResult(state=state, revision_count=0, valid_chain=state is not None)

        if not self.validate_chain(revisions):
            return SelfModelReplayResult(state=None, revision_count=len(revisions), valid_chain=False)

        state = SelfModel.from_dict(revisions[-1].state_snapshot)
        return SelfModelReplayResult(state=state, revision_count=len(revisions), valid_chain=True)

