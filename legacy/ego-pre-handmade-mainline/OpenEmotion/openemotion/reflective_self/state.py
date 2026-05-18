from __future__ import annotations

import time
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .history import ReflectionHistoryLedger
from .schemas import (
    CounterfactualRecord,
    DiagnosisRecord,
    ReflectionQueueItem,
    ReflectionTarget,
    RevisionProposal,
    UnresolvedReflectionItem,
)

FORMAL_OWNER_SCHEMA_VERSION = "mvp15-owner-v1"

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "reflection_queue",
    "reflection_targets",
    "diagnosis_records",
    "counterfactual_records",
    "revision_proposals",
    "unresolved_reflection_items",
    "reflection_history",
    "created_at",
    "updated_at",
    "owner_revision",
    "last_revision_id",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "diagnosis_records",
    "counterfactual_records",
    "revision_proposals",
    "unresolved_reflection_items",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "emotiond.reflection_engine",
    "emotiond.reflection_adapter",
    "emotiond.reflection_shadow",
    "emotiond.self_counterfactual",
    "emotiond.core:/plan",
    "emotiond.api:/decision/target",
    "emotiond.workspace",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.reflective_self"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = "runtime-local bounded projection of formal reflective self owner state"

FORBIDDEN_REQUESTED_EFFECTS = (
    "final_reply_text",
    "tool_command",
    "transport_directive",
    "authority_escalation",
    "direct_self_model_rewrite",
    "direct_drive_state_rewrite",
)

ALLOWED_REFLECTION_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
)

ALLOWED_PROPOSAL_STATUSES = (
    "proposed",
    "held",
    "approved_for_review",
    "rejected",
)


class ReflectiveSelfState(BaseModel):
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION
    reflection_queue: Dict[str, ReflectionQueueItem] = Field(default_factory=dict)
    reflection_targets: Dict[str, ReflectionTarget] = Field(default_factory=dict)
    diagnosis_records: Dict[str, DiagnosisRecord] = Field(default_factory=dict)
    counterfactual_records: Dict[str, CounterfactualRecord] = Field(default_factory=dict)
    revision_proposals: Dict[str, RevisionProposal] = Field(default_factory=dict)
    unresolved_reflection_items: Dict[str, UnresolvedReflectionItem] = Field(default_factory=dict)
    reflection_history: ReflectionHistoryLedger = Field(default_factory=ReflectionHistoryLedger)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    owner_revision: int = 0
    last_revision_id: Optional[str] = None

    def update_timestamp(self) -> None:
        self.updated_at = time.time()

    def get_reflection_pressure(self) -> float:
        queue_pressure = sum(item.priority for item in self.reflection_queue.values())
        unresolved_pressure = sum(item.severity for item in self.unresolved_reflection_items.values())
        proposal_pressure = min(1.0, len(self.revision_proposals) / 5.0)
        raw = queue_pressure + unresolved_pressure + proposal_pressure
        return min(1.0, raw / 5.0)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pending_reflections": len(self.reflection_queue),
            "tracked_targets": len(self.reflection_targets),
            "diagnosis_records": len(self.diagnosis_records),
            "counterfactual_records": len(self.counterfactual_records),
            "revision_proposals": len(self.revision_proposals),
            "unresolved_items": len(self.unresolved_reflection_items),
            "reflection_pressure": self.get_reflection_pressure(),
            "owner_revision": self.owner_revision,
            "last_revision_id": self.last_revision_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_runtime_projection(self) -> Dict[str, Any]:
        def _coerce_target(value: ReflectionTarget | dict[str, Any]) -> ReflectionTarget:
            if isinstance(value, ReflectionTarget):
                return value
            return ReflectionTarget.model_validate(value)

        top_targets = sorted(
            (_coerce_target(target) for target in self.reflection_targets.values()),
            key=lambda target: (-target.salience, target.target_id),
        )[:3]
        return {
            "owner_revision": self.owner_revision,
            "reflection_pressure": self.get_reflection_pressure(),
            "pending_reflections": len(self.reflection_queue),
            "unresolved_items": len(self.unresolved_reflection_items),
            "proposal_candidates": len(self.revision_proposals),
            "top_target_ids": [target.target_id for target in top_targets],
        }


ReflectionState = ReflectiveSelfState
