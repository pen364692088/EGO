from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from openemotion.subject_system_v1.schemas import SubjectSystemV1Result


STATE_SCHEMA_VERSION = "subject_system_v1.state.v1"


@dataclass
class SubjectSystemV1State:
    schema_version: str = STATE_SCHEMA_VERSION
    active_result: Optional[SubjectSystemV1Result] = None
    last_candidate_family: Optional[str] = None

    def apply_result(self, result: SubjectSystemV1Result) -> None:
        self.active_result = result
        candidate = result.host_proactive_candidate or {}
        family = str(candidate.get("candidate_family") or "").strip()
        self.last_candidate_family = family or None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_result": self.active_result.to_dict() if self.active_result else None,
            "last_candidate_family": self.last_candidate_family,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "SubjectSystemV1State":
        payload = dict(raw or {})
        active_result = payload.get("active_result")
        return cls(
            schema_version=str(payload.get("schema_version") or STATE_SCHEMA_VERSION),
            active_result=SubjectSystemV1Result.from_dict(active_result) if active_result else None,
            last_candidate_family=str(payload.get("last_candidate_family") or "") or None,
        )
