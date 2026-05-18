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
    def __init__(self, store: SelfModelStore, *, identity_handle: str) -> None:
        self.store = store
        self.identity_handle = identity_handle

    def load_revisions(self) -> List[SelfModelRevisionRecord]:
        return self.store.load_revision_log(self.identity_handle)

    def validate_chain(self, revisions: List[SelfModelRevisionRecord]) -> bool:
        if not revisions:
            return True
        try:
            self.store.replay(self.identity_handle, revisions=revisions)
        except Exception:
            return False
        return True

    def replay(self) -> SelfModelReplayResult:
        revisions = self.load_revisions()
        if not revisions:
            state = self.store.load(self.identity_handle)
            return SelfModelReplayResult(
                state=state,
                revision_count=0,
                valid_chain=state is not None,
            )

        if not self.validate_chain(revisions):
            return SelfModelReplayResult(
                state=None,
                revision_count=len(revisions),
                valid_chain=False,
            )

        state = self.store.replay(self.identity_handle, revisions=revisions)
        return SelfModelReplayResult(
            state=state,
            revision_count=len(revisions),
            valid_chain=True,
        )
