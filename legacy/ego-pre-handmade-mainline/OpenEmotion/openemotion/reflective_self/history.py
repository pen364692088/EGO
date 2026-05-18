from __future__ import annotations

import json
import time
from hashlib import sha256
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hash_payload(payload: Dict[str, Any]) -> str:
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_diff(before: Any, after: Any, *, field_path: str = "") -> List[Dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        diffs: List[Dict[str, Any]] = []
        for key in sorted(set(before.keys()) | set(after.keys())):
            next_path = f"{field_path}.{key}" if field_path else str(key)
            diffs.extend(compute_diff(before.get(key), after.get(key), field_path=next_path))
        return diffs
    return [{"field_path": field_path or "$", "before": before, "after": after}]


class ReflectionHistoryEntry(BaseModel):
    entry_id: str
    entry_type: str
    linked_record_id: str | None = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class ReflectiveRevisionMarker(BaseModel):
    revision_id: str
    timestamp: str
    update_source: str
    trace_reference: str
    gate_verdict: str


class ReflectiveRevisionRecord(BaseModel):
    model_version: int
    revision_id: str
    timestamp: str
    update_source: str
    trace_reference: str
    before_snapshot: Dict[str, Any]
    after_snapshot: Dict[str, Any]
    diff: List[Dict[str, Any]]
    gate_verdict: str
    previous_state_hash: Optional[str] = None
    state_hash: str

    def to_marker(self) -> ReflectiveRevisionMarker:
        return ReflectiveRevisionMarker(
            revision_id=self.revision_id,
            timestamp=self.timestamp,
            update_source=self.update_source,
            trace_reference=self.trace_reference,
            gate_verdict=self.gate_verdict,
        )


class ReflectionHistoryLedger(BaseModel):
    entries: List[ReflectionHistoryEntry] = Field(default_factory=list)
    revision_markers: List[ReflectiveRevisionMarker] = Field(default_factory=list)
    max_entries: int = 500
    max_revision_markers: int = 200

    def record(
        self,
        *,
        entry_id: str,
        entry_type: str,
        linked_record_id: str | None = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ReflectionHistoryEntry:
        entry = ReflectionHistoryEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            linked_record_id=linked_record_id,
            details=details or {},
        )
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        return entry

    def record_revision_marker(self, marker: ReflectiveRevisionMarker) -> ReflectiveRevisionMarker:
        self.revision_markers.append(marker)
        if len(self.revision_markers) > self.max_revision_markers:
            self.revision_markers = self.revision_markers[-self.max_revision_markers :]
        return marker
