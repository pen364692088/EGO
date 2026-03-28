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
