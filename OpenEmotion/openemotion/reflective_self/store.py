from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .governance import validate_reflective_state
from .history import ReflectiveRevisionMarker, ReflectiveRevisionRecord, compute_diff, hash_payload
from .replay import replay_state_from_revisions
from .state import ReflectiveSelfState

DEFAULT_OWNER_ARTIFACTS_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "mvp15" / "formal_reflective_self"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReflectiveSelfStore:
    def __init__(self, base_dir: Optional[str | Path] = None, *, default_identity: str = "openemotion"):
        if base_dir is not None:
            self.base_dir = Path(base_dir)
        else:
            env_base_dir = os.environ.get("EMOTIOND_REFLECTIVE_SELF_DIR")
            self.base_dir = Path(env_base_dir) if env_base_dir else DEFAULT_OWNER_ARTIFACTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.default_identity = default_identity

    def _identity_dir(self, identity: str) -> Path:
        path = self.base_dir / identity
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self, identity: Optional[str] = None) -> Path:
        return self._identity_dir(identity or self.default_identity) / "reflective_self_state.json"

    def revision_log_file(self, identity: Optional[str] = None) -> Path:
        return self._identity_dir(identity or self.default_identity) / "reflective_self_revisions.jsonl"

    def load(self, identity: Optional[str] = None) -> Optional[ReflectiveSelfState]:
        path = self.state_file(identity)
        if not path.exists():
            return None
        return ReflectiveSelfState.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def load_snapshot(self, identity: Optional[str] = None) -> Optional[dict]:
        state = self.load(identity)
        return state.model_dump(mode="json") if state is not None else None

    def load_revision_log(self, identity: Optional[str] = None) -> List[ReflectiveRevisionRecord]:
        path = self.revision_log_file(identity)
        if not path.exists():
            return []
        return [
            ReflectiveRevisionRecord.model_validate(json.loads(line))
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
        state: ReflectiveSelfState,
        *,
        identity: Optional[str] = None,
        update_source: str = "unspecified_update",
        trace_reference: Optional[str] = None,
        gate_verdict: str = "allow_writeback",
    ) -> ReflectiveRevisionRecord:
        resolved_identity = identity or self.default_identity
        before_snapshot = self.load_snapshot(resolved_identity) or {}
        verdict = validate_reflective_state(state)
        if not verdict.accepted:
            raise ValueError(f"reflective_state_governance_rejected: {verdict.violations}")
        revisions = self.load_revision_log(resolved_identity)
        model_version = len(revisions) + 1
        revision_id = f"reflective_rev_{model_version:06d}"
        timestamp = _utc_now_iso()
        trace_ref = trace_reference or f"reflective_self:{update_source}"

        after_state = ReflectiveSelfState.model_validate(state.model_dump(mode="json"))
        after_state.owner_revision = model_version
        after_state.last_revision_id = revision_id
        after_state.updated_at = datetime.now(timezone.utc).timestamp()
        marker = ReflectiveRevisionMarker(
            revision_id=revision_id,
            timestamp=timestamp,
            update_source=update_source,
            trace_reference=trace_ref,
            gate_verdict=gate_verdict,
        )
        after_state.reflection_history.record_revision_marker(marker)
        after_snapshot = after_state.model_dump(mode="json")
        record = ReflectiveRevisionRecord(
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

    def replay(self, identity: Optional[str] = None) -> Optional[ReflectiveSelfState]:
        return replay_state_from_revisions(self.load_revision_log(identity))
