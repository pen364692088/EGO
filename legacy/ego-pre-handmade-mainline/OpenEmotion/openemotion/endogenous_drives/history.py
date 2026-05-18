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


class DriveHistoryEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    drive_id: str
    change_type: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    cause: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)


class DriveRevisionMarker(BaseModel):
    revision_id: str
    timestamp: str
    update_source: str
    trace_reference: str
    gate_verdict: str


class DriveRevisionRecord(BaseModel):
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

    def to_marker(self) -> DriveRevisionMarker:
        return DriveRevisionMarker(
            revision_id=self.revision_id,
            timestamp=self.timestamp,
            update_source=self.update_source,
            trace_reference=self.trace_reference,
            gate_verdict=self.gate_verdict,
        )


class DriveHistory(BaseModel):
    entries: List[DriveHistoryEntry] = Field(default_factory=list)
    revision_markers: List[DriveRevisionMarker] = Field(default_factory=list)
    max_entries: int = 500
    max_revision_markers: int = 200

    def record(
        self,
        drive_id: str,
        change_type: str,
        old_value: Optional[float],
        new_value: Optional[float],
        cause: str = "",
        evidence: Optional[Dict[str, Any]] = None,
    ) -> DriveHistoryEntry:
        entry = DriveHistoryEntry(
            drive_id=drive_id,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            cause=cause,
            evidence=evidence or {},
        )
        self.entries.append(entry)
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]
        return entry

    def record_revision_marker(self, marker: DriveRevisionMarker) -> DriveRevisionMarker:
        self.revision_markers.append(marker)
        if len(self.revision_markers) > self.max_revision_markers:
            self.revision_markers = self.revision_markers[-self.max_revision_markers :]
        return marker
