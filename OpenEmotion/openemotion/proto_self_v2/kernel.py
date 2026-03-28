from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from openemotion.proto_self.kernel import process_event as process_event_v1
from openemotion.proto_self.state import ProtoSelfState
from openemotion.proto_self_v2.schemas import KernelOutputV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2
from openemotion.proto_self_v2.trace_types import build_trace_payload_v2


def _stable_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_constraint_summary(state: ProtoSelfStateV2) -> Dict[str, Any]:
    return {
        "identity_confidence": state.identity.identity_confidence,
        "core_boundaries_count": len(state.identity.core_boundaries),
        "current_mode": state.self_model.current_mode,
        "stable_preferences_count": len(state.identity.stable_preferences),
    }


def _build_retrieval_summary(state: ProtoSelfStateV2, packet: UpdatePacketV2) -> Dict[str, Any]:
    matched_cycle_ids = []
    source = packet.event.source or "unknown"
    event_type = packet.event.event_type or "unknown"
    for cycle_id, signature in state.cycles.signatures.items():
        if signature.psi_bucket.startswith(f"{source}:{event_type}:"):
            matched_cycle_ids.append(cycle_id)
    return {
        "cycle_count": len(state.cycles.signatures),
        "recent_episode_count": len(state.trace_buffer),
        "matched_cycle_ids": matched_cycle_ids[:5],
    }


def _build_predictive_reflective_delta(packet: UpdatePacketV2, reflection_note: Dict[str, Any] | None) -> Dict[str, Any]:
    return {
        "prediction_snapshot_prev": packet.prediction_snapshot_prev,
        "external_outcome_observed": packet.external_outcome or {},
        "reflection_trigger": reflection_note.get("trigger") if reflection_note else None,
    }


def process_update_packet(state: ProtoSelfState, packet: UpdatePacketV2) -> KernelOutputV2:
    revision_before = state.revision_counter
    packet_dict = packet.to_dict()
    state_v2_before = ProtoSelfStateV2.from_v1(
        state,
        prediction_snapshot_prev=packet.prediction_snapshot_prev,
    )
    retrieval_summary = _build_retrieval_summary(state_v2_before, packet)
    constraint_summary = _build_constraint_summary(state_v2_before)

    v1_event = packet.to_v1_kernel_event()
    v1_output = process_event_v1(state, v1_event)
    revision_after = state.revision_counter

    reflection_dict = v1_output.reflection_note.to_dict() if v1_output.reflection_note else None
    predictive_reflective_delta = _build_predictive_reflective_delta(packet, reflection_dict)
    trace_payload = build_trace_payload_v2(
        event_id=packet.event_id,
        update_packet_hash=_stable_hash(packet_dict),
        state_revision_before=revision_before,
        state_revision_after=revision_after,
        retrieval_summary=retrieval_summary,
        constraint_summary=constraint_summary,
        perceived=v1_output.trace_payload.get("perceived", {}),
        identity_delta=v1_output.identity_state_delta,
        self_model_delta=v1_output.self_model_delta,
        drives_delta=v1_output.appraisal_state_delta,
        cycles_delta=v1_output.trace_payload.get("cycle_delta", {}),
        predictive_reflective_delta=predictive_reflective_delta,
        reflection_note=reflection_dict,
        policy_hint=v1_output.policy_hint,
        response_tendency=v1_output.response_tendency.to_dict() if v1_output.response_tendency else None,
        timestamp=packet.timestamp,
        legacy_trace_payload=v1_output.trace_payload,
    )
    return KernelOutputV2(
        event_id=packet.event_id,
        identity_delta=v1_output.identity_state_delta,
        self_model_delta=v1_output.self_model_delta,
        drives_delta=v1_output.appraisal_state_delta,
        cycles_delta=v1_output.trace_payload.get("cycle_delta", {}),
        predictive_reflective_delta=predictive_reflective_delta,
        memory_update=v1_output.memory_update,
        reflection_note=v1_output.reflection_note,
        policy_hint=v1_output.policy_hint,
        response_tendency=v1_output.response_tendency,
        confidence_meta=v1_output.confidence_meta,
        trace_payload=trace_payload,
    )
