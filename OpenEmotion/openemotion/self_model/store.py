"""
Formal owner persistence for MVP13 self-model.

This module intentionally stays on the converged owner path:
- canonical state file
- revision ledger
- atomic save/load
- replay-friendly revision snapshots
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .model import FORMAL_OWNER_SCHEMA_VERSION, PHASE1_AUTHORITATIVE_FIELDS, SelfModel


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_payload(payload: Dict[str, Any]) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SelfModelRevisionRecord:
    revision_id: str
    timestamp: str
    previous_state_hash: Optional[str]
    state_hash: str
    changed_fields: List[str] = field(default_factory=list)
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    audit_entry: Dict[str, Any] = field(default_factory=dict)
    state_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "timestamp": self.timestamp,
            "previous_state_hash": self.previous_state_hash,
            "state_hash": self.state_hash,
            "changed_fields": list(self.changed_fields),
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "audit_entry": dict(self.audit_entry),
            "state_snapshot": dict(self.state_snapshot),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SelfModelRevisionRecord":
        return cls(
            revision_id=str(payload["revision_id"]),
            timestamp=str(payload["timestamp"]),
            previous_state_hash=payload.get("previous_state_hash"),
            state_hash=str(payload["state_hash"]),
            changed_fields=list(payload.get("changed_fields") or []),
            reason=str(payload.get("reason") or ""),
            evidence=dict(payload.get("evidence") or {}),
            audit_entry=dict(payload.get("audit_entry") or {}),
            state_snapshot=dict(payload.get("state_snapshot") or {}),
        )


class SelfModelStore:
    DEFAULT_STORAGE_DIR = Path("artifacts/mvp13/formal_owner_self_model")
    STATE_FILENAME = "self_model_state.json"
    BACKUP_FILENAME = "self_model_state.json.bak"
    REVISION_LEDGER_FILENAME = "self_model_revisions.jsonl"
    TEMP_SUFFIX = ".tmp"

    def __init__(
        self,
        *,
        base_dir: str | Path | None = None,
        storage_dir: str | Path | None = None,
        auto_backup: bool = True,
    ) -> None:
        self.base_dir = Path(base_dir or Path.cwd())
        storage_path = Path(storage_dir or self.DEFAULT_STORAGE_DIR)
        self.root = storage_path if storage_path.is_absolute() else self.base_dir / storage_path
        self.auto_backup = auto_backup
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def state_file(self) -> Path:
        return self.root / self.STATE_FILENAME

    @property
    def backup_file(self) -> Path:
        return self.root / self.BACKUP_FILENAME

    @property
    def revision_ledger_file(self) -> Path:
        return self.root / self.REVISION_LEDGER_FILENAME

    def _load_state_file(self, path: Path) -> Optional[SelfModel]:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            state = SelfModel.from_dict(payload)
        except Exception:
            return None

        if tuple(state.to_dict().keys()) != PHASE1_AUTHORITATIVE_FIELDS:
            return None
        return state

    def load(self) -> Optional[SelfModel]:
        state = self._load_state_file(self.state_file)
        if state is not None:
            return state

        backup = self._load_state_file(self.backup_file)
        if backup is not None:
            self.save(backup, reason="recovered_from_backup", changed_fields=["__recovery__"])
            return backup

        replayed = self.replay_latest()
        if replayed is not None:
            self.save(replayed, reason="recovered_from_replay", changed_fields=["__recovery__"])
            return replayed

        return None

    def _read_revision_records(self) -> List[SelfModelRevisionRecord]:
        if not self.revision_ledger_file.exists():
            return []

        records: List[SelfModelRevisionRecord] = []
        for line in self.revision_ledger_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            records.append(SelfModelRevisionRecord.from_dict(json.loads(line)))
        return records

    def load_revision_records(self) -> List[SelfModelRevisionRecord]:
        return self._read_revision_records()

    def latest_revision(self) -> Optional[SelfModelRevisionRecord]:
        records = self._read_revision_records()
        return records[-1] if records else None

    def _next_revision_id(self) -> str:
        return f"rev_{len(self._read_revision_records()) + 1:06d}"

    def _write_atomic_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=self.TEMP_SUFFIX)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _append_revision(self, record: SelfModelRevisionRecord) -> None:
        self.revision_ledger_file.parent.mkdir(parents=True, exist_ok=True)
        with self.revision_ledger_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def save(
        self,
        state: SelfModel,
        *,
        changed_fields: Optional[Iterable[str]] = None,
        reason: str = "state_update",
        evidence: Optional[Dict[str, Any]] = None,
        source: str = "formal_owner",
    ) -> SelfModelRevisionRecord:
        state_copy = SelfModel.from_dict(state.to_dict())
        timestamp = _utc_now()
        state_copy.last_modified_at = timestamp

        changed_fields_list = list(changed_fields or ["self_model"])
        audit_entry = {
            "timestamp": timestamp,
            "field_path": ",".join(changed_fields_list),
            "change_type": "update",
            "old_value": None,
            "new_value": None,
            "authorized": True,
            "trigger": source,
            "reason": reason,
        }
        state_copy.modification_audit_trail = list(state_copy.modification_audit_trail) + [audit_entry]

        state_snapshot = state_copy.to_dict()
        state_hash = _hash_payload(state_snapshot)
        previous_revision = self.latest_revision()
        record = SelfModelRevisionRecord(
            revision_id=self._next_revision_id(),
            timestamp=timestamp,
            previous_state_hash=previous_revision.state_hash if previous_revision else None,
            state_hash=state_hash,
            changed_fields=changed_fields_list,
            reason=reason,
            evidence=dict(evidence or {}),
            audit_entry=audit_entry,
            state_snapshot=state_snapshot,
        )

        if self.auto_backup and self.state_file.exists():
            shutil.copy2(self.state_file, self.backup_file)

        self._write_atomic_json(self.state_file, state_snapshot)
        self._append_revision(record)
        return record

    def replay_latest(self) -> Optional[SelfModel]:
        records = self._read_revision_records()
        if not records:
            return self._load_state_file(self.state_file) or self._load_state_file(self.backup_file)

        previous_hash: Optional[str] = None
        for record in records:
            expected_hash = _hash_payload(record.state_snapshot)
            if expected_hash != record.state_hash:
                return None
            if record.previous_state_hash != previous_hash:
                return None
            previous_hash = record.state_hash

        return SelfModel.from_dict(records[-1].state_snapshot)

