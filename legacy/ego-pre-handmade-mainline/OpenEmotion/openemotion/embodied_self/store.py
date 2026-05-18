from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .governance import validate_embodied_state
from .history import EmbodiedRevisionRecord, compute_diff, hash_payload
from .replay import replay_state_from_revisions
from .schemas import GovernanceLedgerEntry
from .state import REQUIRED_WRITEBACK_GATE, EmbodiedSelfState

DEFAULT_OWNER_ARTIFACTS_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "mvp18" / "formal_embodied_self"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EmbodiedSelfStore:
    def __init__(self, base_dir: Optional[str | Path] = None, *, default_identity: str = "openemotion"):
        self.base_dir = Path(base_dir) if base_dir is not None else DEFAULT_OWNER_ARTIFACTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.default_identity = default_identity

    def _identity_dir(self, identity: str) -> Path:
        path = self.base_dir / identity
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self, identity: Optional[str] = None) -> Path:
        return self._identity_dir(identity or self.default_identity) / "embodied_self_state.json"

    def revision_log_file(self, identity: Optional[str] = None) -> Path:
        return self._identity_dir(identity or self.default_identity) / "embodied_self_revisions.jsonl"

    def load(self, identity: Optional[str] = None) -> Optional[EmbodiedSelfState]:
        path = self.state_file(identity)
        if not path.exists():
            return None
        return EmbodiedSelfState.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def load_snapshot(self, identity: Optional[str] = None) -> Optional[dict]:
        state = self.load(identity)
        return state.model_dump(mode="json") if state is not None else None

    def load_revision_log(self, identity: Optional[str] = None) -> List[EmbodiedRevisionRecord]:
        path = self.revision_log_file(identity)
        if not path.exists():
            return []
        return [
            EmbodiedRevisionRecord.model_validate(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _write_atomic_json(self, path: Path, payload: dict) -> None:
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
        state: EmbodiedSelfState,
        *,
        identity: Optional[str] = None,
        update_source: str = "unspecified_update",
        trace_reference: Optional[str] = None,
        gate_verdict: str = "allow_writeback",
    ) -> EmbodiedRevisionRecord:
        resolved_identity = identity or self.default_identity
        if state.identity_handle != resolved_identity:
            raise ValueError(
                f"embodied_state_identity_mismatch:{state.identity_handle}:{resolved_identity}"
            )
        before_snapshot = self.load_snapshot(resolved_identity) or {}
        verdict = validate_embodied_state(state)
        if not verdict.accepted:
            raise ValueError(f"embodied_state_governance_rejected: {verdict.violations}")

        revisions = self.load_revision_log(resolved_identity)
        model_version = len(revisions) + 1
        revision_id = f"embodied_rev_{model_version:06d}"
        timestamp = _utc_now_iso()
        trace_ref = trace_reference or f"embodied_self:{update_source}"

        after_state = EmbodiedSelfState.model_validate(state.model_dump(mode="json"))
        after_state.owner_revision = model_version
        after_state.last_revision_id = revision_id
        ledger_id = f"persist_{revision_id}"
        after_state.governance_ledger[ledger_id] = GovernanceLedgerEntry(
            ledger_id=ledger_id,
            event_type="state_persisted",
            reference_id=revision_id,
            gate_name=REQUIRED_WRITEBACK_GATE,
            gate_verdict=gate_verdict,
            details={
                "update_source": update_source,
                "trace_reference": trace_ref,
                "persisted_at": time.time(),
            },
        )
        after_snapshot = after_state.model_dump(mode="json")
        record = EmbodiedRevisionRecord(
            model_version=model_version,
            revision_id=revision_id,
            timestamp=timestamp,
            update_source=update_source,
            trace_reference=trace_ref,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            diff=compute_diff(before_snapshot, after_snapshot),
            gate_verdict=gate_verdict,
            previous_state_hash=hash_payload(before_snapshot) if before_snapshot else None,
            state_hash=hash_payload(after_snapshot),
        )
        self._write_atomic_json(self.state_file(resolved_identity), after_snapshot)
        with self.revision_log_file(resolved_identity).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        return record

    def replay(self, identity: Optional[str] = None) -> Optional[EmbodiedSelfState]:
        return replay_state_from_revisions(self.load_revision_log(identity))
