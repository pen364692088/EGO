from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional

from openemotion.proto_self.state import (
    CycleStore,
    DriveField,
    EpisodicRecord,
    IdentityInvariants,
    ProtoSelfState,
    SelfModel,
)
from openemotion.proto_self_v2.developmental import DevelopmentalShadowState
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState


@dataclass
class PredictiveReflectiveState:
    expectation_snapshot: Dict[str, Any] = field(default_factory=dict)
    mismatch_summary: Dict[str, Any] = field(default_factory=dict)
    reflection_state: Optional[Dict[str, Any]] = None
    revision_counter: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expectation_snapshot": self.expectation_snapshot,
            "mismatch_summary": self.mismatch_summary,
            "reflection_state": self.reflection_state,
            "revision_counter": self.revision_counter,
        }


@dataclass
class ProtoSelfStateV2:
    identity: IdentityInvariants = field(default_factory=IdentityInvariants)
    self_model: SelfModel = field(default_factory=SelfModel)
    drives: DriveField = field(default_factory=DriveField)
    cycles: CycleStore = field(default_factory=CycleStore)
    predictive_reflective: PredictiveReflectiveState = field(default_factory=PredictiveReflectiveState)
    trace_buffer: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=100))
    seed_state: Optional[ProtoSelfSeedState] = None
    developmental_shadow: DevelopmentalShadowState = field(default_factory=DevelopmentalShadowState)
    revision_counter: int = 0

    @classmethod
    def from_v1(
        cls,
        state: ProtoSelfState,
        *,
        prediction_snapshot_prev: Optional[Dict[str, Any]] = None,
        reflection_note: Optional[Dict[str, Any]] = None,
        mismatch_summary: Optional[Dict[str, Any]] = None,
    ) -> "ProtoSelfStateV2":
        trace_buffer = deque([record.to_dict() for record in state.episodic_trace], maxlen=100)
        predictive_reflective = PredictiveReflectiveState(
            expectation_snapshot=prediction_snapshot_prev or {},
            mismatch_summary=mismatch_summary or {},
            reflection_state=reflection_note,
            revision_counter=state.revision_counter,
        )
        return cls(
            identity=state.identity,
            self_model=state.self_model,
            drives=state.drives,
            cycles=state.cycle_store,
            predictive_reflective=predictive_reflective,
            trace_buffer=trace_buffer,
            revision_counter=state.revision_counter,
        )

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ProtoSelfStateV2":
        trace_buffer = deque(list(raw.get("trace_buffer") or []), maxlen=100)
        seed_state_raw = raw.get("seed_state")
        return cls(
            identity=IdentityInvariants.from_dict(dict(raw.get("identity") or {})),
            self_model=SelfModel.from_dict(dict(raw.get("self_model") or {})),
            drives=DriveField.from_dict(dict(raw.get("drives") or {})),
            cycles=CycleStore.from_dict(dict(raw.get("cycles") or {})),
            predictive_reflective=PredictiveReflectiveState(
                expectation_snapshot=dict((raw.get("predictive_reflective") or {}).get("expectation_snapshot") or {}),
                mismatch_summary=dict((raw.get("predictive_reflective") or {}).get("mismatch_summary") or {}),
                reflection_state=(raw.get("predictive_reflective") or {}).get("reflection_state"),
                revision_counter=int((raw.get("predictive_reflective") or {}).get("revision_counter", 0)),
            ),
            trace_buffer=trace_buffer,
            seed_state=ProtoSelfSeedState.from_dict(dict(seed_state_raw or {})) if seed_state_raw else None,
            developmental_shadow=DevelopmentalShadowState.from_dict(dict(raw.get("developmental_shadow") or {})),
            revision_counter=int(raw.get("revision_counter", 0)),
        )

    @classmethod
    def empty(cls) -> "ProtoSelfStateV2":
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "self_model": self.self_model.to_dict(),
            "drives": self.drives.to_dict(),
            "cycles": self.cycles.to_dict(),
            "predictive_reflective": self.predictive_reflective.to_dict(),
            "trace_buffer": list(self.trace_buffer),
            "seed_state": self.seed_state.to_dict() if self.seed_state else None,
            "developmental_shadow": self.developmental_shadow.to_dict(),
            "revision_counter": self.revision_counter,
        }

    def to_v1(self) -> ProtoSelfState:
        return ProtoSelfState(
            identity=self.identity,
            self_model=self.self_model,
            drives=self.drives,
            cycle_store=self.cycles,
            episodic_trace=deque(
                [EpisodicRecord.from_dict(record) for record in list(self.trace_buffer)],
                maxlen=100,
            ),
            revision_counter=self.revision_counter,
        )

    def apply_v1_state(
        self,
        state: ProtoSelfState,
        *,
        prediction_snapshot_prev: Optional[Dict[str, Any]] = None,
        reflection_note: Optional[Dict[str, Any]] = None,
        mismatch_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        updated = self.from_v1(
            state,
            prediction_snapshot_prev=prediction_snapshot_prev,
            reflection_note=reflection_note,
            mismatch_summary=mismatch_summary,
        )
        self.identity = updated.identity
        self.self_model = updated.self_model
        self.drives = updated.drives
        self.cycles = updated.cycles
        self.predictive_reflective = updated.predictive_reflective
        self.trace_buffer = updated.trace_buffer
        self.revision_counter = updated.revision_counter
