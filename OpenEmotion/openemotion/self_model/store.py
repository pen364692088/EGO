from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from .model import SelfModel

DEFAULT_OWNER_ARTIFACTS_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "mvp13" / "formal_self_model"
)

REQUIRED_REVISION_FIELDS = (
    "model_version",
    "revision_id",
    "timestamp",
    "update_source",
    "trace_reference",
    "before_snapshot",
    "after_snapshot",
    "diff",
    "confidence_class",
    "gate_verdict",
)


class SelfModelReplayError(RuntimeError):
    """Raised when a revision chain cannot be replayed deterministically."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _deep_copy_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return json.loads(_canonical_json(payload))


def _hash_payload(payload: Dict[str, Any]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _compute_diff(before: Any, after: Any, *, field_path: str = "") -> List[Dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        diffs: List[Dict[str, Any]] = []
        for key in sorted(set(before.keys()) | set(after.keys())):
            next_path = f"{field_path}.{key}" if field_path else str(key)
            diffs.extend(_compute_diff(before.get(key), after.get(key), field_path=next_path))
        return diffs
    return [{"field_path": field_path or "$", "before": before, "after": after}]


@dataclass(frozen=True)
class SelfModelRevisionRecord:
    model_version: int
    revision_id: str
    timestamp: str
    update_source: str
    trace_reference: str
    before_snapshot: Dict[str, Any]
    after_snapshot: Dict[str, Any]
    diff: List[Dict[str, Any]]
    confidence_class: str
    gate_verdict: str
    previous_state_hash: Optional[str]
    state_hash: str

    @property
    def state_snapshot(self) -> Dict[str, Any]:
        return self.after_snapshot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_version": self.model_version,
            "revision_id": self.revision_id,
            "timestamp": self.timestamp,
            "update_source": self.update_source,
            "trace_reference": self.trace_reference,
            "before_snapshot": self.before_snapshot,
            "after_snapshot": self.after_snapshot,
            "diff": self.diff,
            "confidence_class": self.confidence_class,
            "gate_verdict": self.gate_verdict,
            "previous_state_hash": self.previous_state_hash,
            "state_hash": self.state_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfModelRevisionRecord":
        missing = [field for field in REQUIRED_REVISION_FIELDS if field not in data]
        if missing:
            raise ValueError(f"missing required revision fields: {missing}")
        return cls(
            model_version=int(data["model_version"]),
            revision_id=str(data["revision_id"]),
            timestamp=str(data["timestamp"]),
            update_source=str(data["update_source"]),
            trace_reference=str(data["trace_reference"]),
            before_snapshot=dict(data["before_snapshot"] or {}),
            after_snapshot=dict(data["after_snapshot"] or {}),
            diff=list(data["diff"] or []),
            confidence_class=str(data["confidence_class"]),
            gate_verdict=str(data["gate_verdict"]),
            previous_state_hash=data.get("previous_state_hash"),
            state_hash=str(data["state_hash"]),
        )


class SelfModelStore:
    """Formal owner persistence for the MVP13 self-model."""

    def __init__(self, base_dir: Optional[str | Path] = None, *, default_identity_handle: str = "openemotion"):
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_OWNER_ARTIFACTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.default_identity_handle = default_identity_handle

    def _identity_dir(self, identity_handle: str) -> Path:
        identity_dir = self.base_dir / identity_handle
        identity_dir.mkdir(parents=True, exist_ok=True)
        return identity_dir

    def state_file(self, identity_handle: str) -> Path:
        return self._identity_dir(identity_handle) / "self_model_state.json"

    def backup_file(self, identity_handle: str) -> Path:
        return self._identity_dir(identity_handle) / "self_model_state.backup.json"

    def revision_log_file(self, identity_handle: str) -> Path:
        return self._identity_dir(identity_handle) / "self_model_revisions.jsonl"

    def exists(self, identity_handle: Optional[str] = None) -> bool:
        return self.state_file(identity_handle or self.default_identity_handle).exists()

    def load(self, identity_handle: Optional[str] = None) -> Optional[SelfModel]:
        state_file = self.state_file(identity_handle or self.default_identity_handle)
        if not state_file.exists():
            return None
        payload = json.loads(state_file.read_text(encoding="utf-8"))
        return SelfModel.from_dict(payload)

    def load_snapshot(self, identity_handle: Optional[str] = None) -> Optional[Dict[str, Any]]:
        model = self.load(identity_handle)
        return model.to_dict() if model is not None else None

    def load_revision_log(self, identity_handle: Optional[str] = None) -> List[SelfModelRevisionRecord]:
        log_file = self.revision_log_file(identity_handle or self.default_identity_handle)
        if not log_file.exists():
            return []
        records: List[SelfModelRevisionRecord] = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped:
                records.append(SelfModelRevisionRecord.from_dict(json.loads(stripped)))
        return records

    def load_revision_records(self, identity_handle: Optional[str] = None) -> List[SelfModelRevisionRecord]:
        return self.load_revision_log(identity_handle)

    def _write_atomic_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def save(
        self,
        model: SelfModel,
        *,
        update_source: Optional[str] = None,
        trace_reference: Optional[str] = None,
        confidence_class: str = "bounded",
        gate_verdict: str = "allow_writeback",
        changed_fields: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> SelfModelRevisionRecord:
        before_snapshot = self.load_snapshot(model.identity_handle) or {}
        current_state_file = self.state_file(model.identity_handle)
        if current_state_file.exists():
            shutil.copy2(current_state_file, self.backup_file(model.identity_handle))

        revisions = self.load_revision_log(model.identity_handle)
        model_version = len(revisions) + 1
        revision_id = f"rev_{model_version:06d}"
        timestamp = _utc_now_iso()
        update_reason = update_source or reason or "unspecified_update"
        trace_ref = trace_reference or f"self_model:{update_reason}"

        after_model = SelfModel.from_dict(model.to_dict())
        after_model.last_modified_at = timestamp
        after_model.modification_audit_trail = list(after_model.modification_audit_trail) + [
            {
                "timestamp": timestamp,
                "field_path": "$",
                "change_type": "add" if not before_snapshot else "update",
                "authorized": gate_verdict == "allow_writeback",
                "trigger": update_reason,
                "revision_id": revision_id,
                "model_version": model_version,
                "trace_reference": trace_ref,
                "gate_verdict": gate_verdict,
                "confidence_class": confidence_class,
                "reason": reason or update_reason,
                "changed_fields": list(changed_fields or []),
            }
        ]
        after_snapshot = after_model.to_dict()
        record = SelfModelRevisionRecord(
            model_version=model_version,
            revision_id=revision_id,
            timestamp=timestamp,
            update_source=update_reason,
            trace_reference=trace_ref,
            before_snapshot=_deep_copy_payload(before_snapshot),
            after_snapshot=_deep_copy_payload(after_snapshot),
            diff=_compute_diff(before_snapshot, after_snapshot),
            confidence_class=confidence_class,
            gate_verdict=gate_verdict,
            previous_state_hash=_hash_payload(before_snapshot) if before_snapshot else None,
            state_hash=_hash_payload(after_snapshot),
        )

        self._write_atomic_json(current_state_file, after_snapshot)
        with self.revision_log_file(model.identity_handle).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return record

    def replay(
        self,
        identity_handle: Optional[str] = None,
        *,
        base_snapshot: Optional[Dict[str, Any]] = None,
        revisions: Optional[List[SelfModelRevisionRecord]] = None,
    ) -> Optional[SelfModel]:
        resolved_identity = identity_handle or self.default_identity_handle
        replay_log = revisions if revisions is not None else self.load_revision_log(resolved_identity)
        if not replay_log:
            if base_snapshot:
                return SelfModel.from_dict(base_snapshot)
            return self.load(resolved_identity)

        current = _deep_copy_payload(base_snapshot or replay_log[0].before_snapshot)
        for revision in replay_log:
            if revision.previous_state_hash != (_hash_payload(current) if current else None):
                raise SelfModelReplayError(
                    f"replay divergence before {revision.revision_id}: previous_state_hash mismatch"
                )
            if current != revision.before_snapshot:
                raise SelfModelReplayError(
                    f"replay divergence before {revision.revision_id}: current state does not match before_snapshot"
                )
            if revision.state_hash != _hash_payload(revision.after_snapshot):
                raise SelfModelReplayError(
                    f"replay divergence after {revision.revision_id}: state_hash mismatch"
                )
            current = _deep_copy_payload(revision.after_snapshot)
        return SelfModel.from_dict(current)


SelfModelRevision = SelfModelRevisionRecord


SelfModelRevision = SelfModelRevisionRecord
