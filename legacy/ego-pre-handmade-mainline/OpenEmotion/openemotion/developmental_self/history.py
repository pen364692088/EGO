from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


class DevelopmentalRevisionMarker(BaseModel):
    revision_id: str
    timestamp: str
    update_source: str
    trace_reference: str
    gate_verdict: str


class DevelopmentalRevisionRecord(BaseModel):
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

    def to_marker(self) -> DevelopmentalRevisionMarker:
        return DevelopmentalRevisionMarker(
            revision_id=self.revision_id,
            timestamp=self.timestamp,
            update_source=self.update_source,
            trace_reference=self.trace_reference,
            gate_verdict=self.gate_verdict,
        )
