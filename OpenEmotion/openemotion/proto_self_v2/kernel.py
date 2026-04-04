from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from openemotion.proto_self.kernel import process_event as process_event_v1
from openemotion.proto_self.schemas import ResponseTendency
from openemotion.proto_self.state import ProtoSelfState
from openemotion.proto_self_v2.developmental import run_developmental_cycle
from openemotion.proto_self_v2.developmental_self_context import (
    derive_developmental_outputs,
    extract_runtime_developmental_self_context,
    summarize_runtime_developmental_self_context,
)
from openemotion.proto_self_v2.endogenous_drive_context import (
    derive_endogenous_drive_outputs,
    extract_runtime_endogenous_drive_context,
    summarize_runtime_endogenous_drive_context,
)
from openemotion.proto_self_v2.reflective_self_context import (
    derive_reflective_self_outputs,
    extract_runtime_reflective_self_context,
    summarize_runtime_reflective_self_context,
)
from openemotion.proto_self_v2.schemas import (
    KernelOutputV2,
    UpdatePacketV2,
)
from openemotion.proto_self_v2.self_model_context import (
    extract_runtime_self_model_context,
    summarize_runtime_self_model_context,
)
from openemotion.proto_self_v2.seed_kernel import ProtoSelfSeedKernel
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState
from openemotion.proto_self_v2.state import ProtoSelfStateV2
from openemotion.proto_self_v2.trace_types import build_trace_payload_v2


def _stable_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_constraint_summary(
    state: ProtoSelfStateV2,
    *,
    subject_profile: str | None,
    runtime_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "identity_confidence": state.identity.identity_confidence,
        "core_boundaries_count": len(state.identity.core_boundaries),
        "current_mode": state.self_model.current_mode,
        "stable_preferences_count": len(state.identity.stable_preferences),
        "subject_profile": subject_profile,
        "self_model_context": summarize_runtime_self_model_context(runtime_summary),
        "developmental_self_context": summarize_runtime_developmental_self_context(runtime_summary),
        "endogenous_drive_context": summarize_runtime_endogenous_drive_context(runtime_summary),
        "reflective_self_context": summarize_runtime_reflective_self_context(runtime_summary),
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
        "seed_recent_outcomes_count": len(state.seed_state.recent_outcomes) if state.seed_state else 0,
        "self_model_context_present": bool(extract_runtime_self_model_context(packet.runtime_summary)),
        "developmental_self_context_present": bool(
            extract_runtime_developmental_self_context(packet.runtime_summary)
        ),
        "endogenous_drive_context_present": bool(extract_runtime_endogenous_drive_context(packet.runtime_summary)),
        "reflective_self_context_present": bool(extract_runtime_reflective_self_context(packet.runtime_summary)),
    }


def _build_predictive_reflective_delta(packet: UpdatePacketV2, reflection_note: Dict[str, Any] | None) -> Dict[str, Any]:
    return {
        "prediction_snapshot_prev": packet.prediction_snapshot_prev,
        "external_outcome_observed": packet.external_outcome or {},
        "reflection_trigger": reflection_note.get("trigger") if reflection_note else None,
    }


def _coerce_state_v2(state: ProtoSelfState | ProtoSelfStateV2, packet: UpdatePacketV2) -> ProtoSelfStateV2:
    if isinstance(state, ProtoSelfStateV2):
        return state
    return ProtoSelfStateV2.from_v1(
        state,
        prediction_snapshot_prev=packet.prediction_snapshot_prev,
    )


def _process_seed_profile(state_v2: ProtoSelfStateV2, packet: UpdatePacketV2) -> KernelOutputV2:
    seed_event = packet.to_seed_kernel_event()
    if seed_event is None:
        raise ValueError("seed_v0_2 profile requires seed_event")

    seed_state_before = state_v2.seed_state or ProtoSelfSeedState.empty()
    state_v2.seed_state = seed_state_before.copy()
    revision_before = state_v2.seed_state.revision_counter
    update_packet_hash = _stable_hash(packet.to_dict())
    retrieval_summary = _build_retrieval_summary(state_v2, packet)
    constraint_summary = _build_constraint_summary(
        state_v2,
        subject_profile=SEED_SUBJECT_PROFILE,
        runtime_summary=packet.runtime_summary,
    )

    seed_kernel = ProtoSelfSeedKernel()
    seed_result = seed_kernel.process_event(state_v2.seed_state, seed_event)
    state_v2.revision_counter = max(state_v2.revision_counter, state_v2.seed_state.revision_counter)
    revision_after = state_v2.seed_state.revision_counter

    trace_payload = build_trace_payload_v2(
        event_id=packet.event_id,
        subject_profile=SEED_SUBJECT_PROFILE,
        idle_eligible=seed_result.trace_payload.get("idle_eligible"),
        urge_score=seed_result.trace_payload.get("urge_score"),
        candidate_generated=seed_result.trace_payload.get("candidate_generated"),
        suppression_reason=seed_result.trace_payload.get("suppression_reason"),
        update_packet_hash=update_packet_hash,
        state_revision_before=revision_before,
        state_revision_after=revision_after,
        retrieval_summary=retrieval_summary,
        constraint_summary=constraint_summary,
        perceived=seed_result.trace_payload.get("perceived", {}),
        identity_delta={},
        self_model_delta={},
        drives_delta={},
        cycles_delta={},
        predictive_reflective_delta={},
        reflection_note=seed_result.reflection_note.to_dict() if seed_result.reflection_note else None,
        policy_hint=seed_result.policy_hint,
        response_tendency=seed_result.response_tendency.to_dict() if seed_result.response_tendency else None,
        candidate_actions=seed_result.candidate_actions,
        governor_hint=seed_result.trace_payload.get("governor_hint", {}),
        executed_action=seed_result.trace_payload.get("executed_action"),
        exec_result=seed_result.trace_payload.get("exec_result"),
        seed_state_delta=seed_result.state_delta,
        seed_state_snapshot=seed_result.trace_payload.get("seed_state_snapshot", {}),
        timestamp=packet.timestamp,
        legacy_trace_payload=seed_result.trace_payload,
    )
    return KernelOutputV2(
        event_id=packet.event_id,
        subject_profile=SEED_SUBJECT_PROFILE,
        seed_state_delta=seed_result.state_delta,
        memory_update={"seed_state_updated": True},
        candidate_actions=seed_result.candidate_actions,
        reflection_note=seed_result.reflection_note,
        policy_hint=seed_result.policy_hint,
        response_tendency=seed_result.response_tendency,
        confidence_meta={
            "seed_identity_confidence": state_v2.seed_state.identity_light.identity_confidence,
            "seed_revision_counter": state_v2.seed_state.revision_counter,
            "seed_recent_outcomes_count": len(state_v2.seed_state.recent_outcomes),
            "self_model_context_present": constraint_summary["self_model_context"]["present"],
        },
        trace_payload=trace_payload,
    )


def _process_default_v2(state_v2: ProtoSelfStateV2, packet: UpdatePacketV2) -> KernelOutputV2:
    revision_before = state_v2.revision_counter
    packet_dict = packet.to_dict()
    retrieval_summary = _build_retrieval_summary(state_v2, packet)
    constraint_summary = _build_constraint_summary(
        state_v2,
        subject_profile=packet.subject_profile,
        runtime_summary=packet.runtime_summary,
    )

    v1_state = state_v2.to_v1()
    v1_event = packet.to_v1_kernel_event()
    v1_output = process_event_v1(v1_state, v1_event)
    revision_after = v1_state.revision_counter

    reflection_dict = v1_output.reflection_note.to_dict() if v1_output.reflection_note else None
    predictive_reflective_delta = _build_predictive_reflective_delta(packet, reflection_dict)
    developmental_outputs = derive_developmental_outputs(packet.runtime_summary)
    endogenous_drive_outputs = derive_endogenous_drive_outputs(packet.runtime_summary)
    reflective_outputs = derive_reflective_self_outputs(packet.runtime_summary)
    state_v2.apply_v1_state(
        v1_state,
        prediction_snapshot_prev=packet.prediction_snapshot_prev,
        reflection_note=reflection_dict,
        mismatch_summary=predictive_reflective_delta,
    )
    trace_payload = build_trace_payload_v2(
        event_id=packet.event_id,
        subject_profile=packet.subject_profile,
        update_packet_hash=_stable_hash(packet_dict),
        state_revision_before=revision_before,
        state_revision_after=revision_after,
        retrieval_summary=retrieval_summary,
        constraint_summary=constraint_summary,
        perceived=v1_output.trace_payload.get("perceived", {}),
        identity_delta=v1_output.identity_state_delta,
        self_model_delta=v1_output.self_model_delta,
        drives_delta=v1_output.appraisal_state_delta,
        endogenous_drive_delta=endogenous_drive_outputs["endogenous_drive_delta"],
        drive_state_snapshot=endogenous_drive_outputs["drive_state_snapshot"],
        priority_snapshot=endogenous_drive_outputs["priority_snapshot"],
        candidate_bias_terms=endogenous_drive_outputs["candidate_bias_terms"],
        self_maintenance_candidate=endogenous_drive_outputs["self_maintenance_candidate"],
        drive_audit_entries=endogenous_drive_outputs["drive_audit_entries"],
        drive_context=endogenous_drive_outputs["drive_context"],
        reflective_self_delta=reflective_outputs["reflective_self_delta"],
        revision_proposal_candidates=reflective_outputs["revision_proposal_candidates"],
        confidence_adjustment_hints=reflective_outputs["confidence_adjustment_hints"],
        maintenance_priority_hints=reflective_outputs["maintenance_priority_hints"],
        reflection_writeback_candidate=reflective_outputs["reflection_writeback_candidate"],
        reflection_context=reflective_outputs["reflection_context"],
        cycles_delta=v1_output.trace_payload.get("cycle_delta", {}),
        predictive_reflective_delta=predictive_reflective_delta,
        developmental_self_delta=developmental_outputs["developmental_self_delta"],
        developmental_proposal_candidates=developmental_outputs["developmental_proposal_candidates"],
        developmental_continuity_snapshot=developmental_outputs["developmental_continuity_snapshot"],
        developmental_priority_hints=developmental_outputs["developmental_priority_hints"],
        developmental_audit_entries=developmental_outputs["developmental_audit_entries"],
        developmental_writeback_candidate=developmental_outputs["developmental_writeback_candidate"],
        developmental_context=developmental_outputs["developmental_context"],
        reflection_note=reflection_dict,
        policy_hint={
            **v1_output.policy_hint,
            **developmental_outputs["policy_hint_patch"],
            **endogenous_drive_outputs["policy_hint_patch"],
            **reflective_outputs["policy_hint_patch"],
        },
        response_tendency=(
            reflective_outputs["response_tendency"].to_dict()
            if reflective_outputs["response_tendency"]
            else (
                endogenous_drive_outputs["response_tendency"].to_dict()
                if endogenous_drive_outputs["response_tendency"]
                else (
                    developmental_outputs["response_tendency"].to_dict()
                    if developmental_outputs["response_tendency"]
                    else (v1_output.response_tendency.to_dict() if v1_output.response_tendency else None)
                )
            )
        ),
        timestamp=packet.timestamp,
        legacy_trace_payload=v1_output.trace_payload,
    )
    merged_policy_hint = {
        **v1_output.policy_hint,
        **developmental_outputs["policy_hint_patch"],
        **endogenous_drive_outputs["policy_hint_patch"],
        **reflective_outputs["policy_hint_patch"],
    }
    merged_response_tendency = (
        reflective_outputs["response_tendency"]
        or endogenous_drive_outputs["response_tendency"]
        or developmental_outputs["response_tendency"]
        or v1_output.response_tendency
    )
    output = KernelOutputV2(
        event_id=packet.event_id,
        subject_profile=packet.subject_profile,
        identity_delta=v1_output.identity_state_delta,
        self_model_delta=v1_output.self_model_delta,
        drives_delta=v1_output.appraisal_state_delta,
        cycles_delta=v1_output.trace_payload.get("cycle_delta", {}),
        predictive_reflective_delta=predictive_reflective_delta,
        memory_update=v1_output.memory_update,
        reflection_note=v1_output.reflection_note,
        policy_hint=merged_policy_hint,
        response_tendency=merged_response_tendency,
        confidence_meta=v1_output.confidence_meta,
        developmental_self_delta=developmental_outputs["developmental_self_delta"],
        developmental_proposal_candidates=developmental_outputs["developmental_proposal_candidates"],
        developmental_continuity_snapshot=developmental_outputs["developmental_continuity_snapshot"],
        developmental_priority_hints=developmental_outputs["developmental_priority_hints"],
        developmental_audit_entries=developmental_outputs["developmental_audit_entries"],
        developmental_writeback_candidate=developmental_outputs["developmental_writeback_candidate"],
        endogenous_drive_delta=endogenous_drive_outputs["endogenous_drive_delta"],
        drive_state_snapshot=endogenous_drive_outputs["drive_state_snapshot"],
        priority_snapshot=endogenous_drive_outputs["priority_snapshot"],
        candidate_bias_terms=endogenous_drive_outputs["candidate_bias_terms"],
        self_maintenance_candidate=endogenous_drive_outputs["self_maintenance_candidate"],
        drive_audit_entries=endogenous_drive_outputs["drive_audit_entries"],
        reflective_self_delta=reflective_outputs["reflective_self_delta"],
        revision_proposal_candidates=reflective_outputs["revision_proposal_candidates"],
        confidence_adjustment_hints=reflective_outputs["confidence_adjustment_hints"],
        maintenance_priority_hints=reflective_outputs["maintenance_priority_hints"],
        reflection_writeback_candidate=reflective_outputs["reflection_writeback_candidate"],
        trace_payload=trace_payload,
    )

    if constraint_summary["self_model_context"]["present"]:
        output.confidence_meta = dict(output.confidence_meta)
        output.confidence_meta["self_model_context_present"] = True
        output.confidence_meta["self_model_context_identity_handle"] = constraint_summary["self_model_context"].get(
            "identity_handle"
        )
    if constraint_summary["developmental_self_context"]["present"]:
        output.confidence_meta = dict(output.confidence_meta)
        output.confidence_meta["developmental_self_context_present"] = True
        output.confidence_meta["developmental_self_owner_revision"] = constraint_summary[
            "developmental_self_context"
        ].get("owner_revision")
    if constraint_summary["endogenous_drive_context"]["present"]:
        output.confidence_meta = dict(output.confidence_meta)
        output.confidence_meta["endogenous_drive_context_present"] = True
        output.confidence_meta["endogenous_drive_owner_revision"] = constraint_summary["endogenous_drive_context"].get(
            "owner_revision"
        )
    if constraint_summary["reflective_self_context"]["present"]:
        output.confidence_meta = dict(output.confidence_meta)
        output.confidence_meta["reflective_self_context_present"] = True
        output.confidence_meta["reflective_self_owner_revision"] = constraint_summary["reflective_self_context"].get(
            "owner_revision"
        )
    return output


def _process_developmental_v2(state_v2: ProtoSelfStateV2, packet: UpdatePacketV2) -> KernelOutputV2:
    revision_before = state_v2.revision_counter
    execution = run_developmental_cycle(state_v2, packet)
    developmental_outputs = derive_developmental_outputs(packet.runtime_summary)
    endogenous_drive_outputs = derive_endogenous_drive_outputs(packet.runtime_summary)
    reflective_outputs = derive_reflective_self_outputs(packet.runtime_summary)
    trace_payload = build_trace_payload_v2(
        event_id=packet.event_id,
        subject_profile=packet.subject_profile,
        update_packet_hash=_stable_hash(packet.to_dict()),
        state_revision_before=revision_before,
        state_revision_after=state_v2.revision_counter,
        retrieval_summary=_build_retrieval_summary(state_v2, packet),
        constraint_summary=_build_constraint_summary(
            state_v2,
            subject_profile=packet.subject_profile,
            runtime_summary=packet.runtime_summary,
        ),
        perceived={},
        identity_delta={},
        self_model_delta=execution.self_model_delta,
        drives_delta={},
        endogenous_drive_delta=endogenous_drive_outputs["endogenous_drive_delta"],
        drive_state_snapshot=endogenous_drive_outputs["drive_state_snapshot"],
        priority_snapshot=endogenous_drive_outputs["priority_snapshot"],
        candidate_bias_terms=endogenous_drive_outputs["candidate_bias_terms"],
        self_maintenance_candidate=endogenous_drive_outputs["self_maintenance_candidate"],
        drive_audit_entries=endogenous_drive_outputs["drive_audit_entries"],
        drive_context=endogenous_drive_outputs["drive_context"],
        reflective_self_delta=reflective_outputs["reflective_self_delta"],
        revision_proposal_candidates=reflective_outputs["revision_proposal_candidates"],
        confidence_adjustment_hints=reflective_outputs["confidence_adjustment_hints"],
        maintenance_priority_hints=reflective_outputs["maintenance_priority_hints"],
        reflection_writeback_candidate=reflective_outputs["reflection_writeback_candidate"],
        reflection_context=reflective_outputs["reflection_context"],
        cycles_delta={},
        predictive_reflective_delta={},
        developmental_self_delta=developmental_outputs["developmental_self_delta"],
        developmental_proposal_candidates=developmental_outputs["developmental_proposal_candidates"],
        developmental_continuity_snapshot=developmental_outputs["developmental_continuity_snapshot"],
        developmental_priority_hints=developmental_outputs["developmental_priority_hints"],
        developmental_audit_entries=developmental_outputs["developmental_audit_entries"],
        developmental_writeback_candidate=developmental_outputs["developmental_writeback_candidate"],
        developmental_context=developmental_outputs["developmental_context"],
        policy_hint={
            "preferred_action_type": "wait",
            "risk_tolerance": "conservative",
            "constraints": [
                "developmental_shadow_only",
                "no_direct_reply_authority",
                "no_direct_execution_authority",
            ],
            "governor_hint": {
                "status": execution.gate.get("status"),
                "mode": "developmental_shadow_only",
            },
            **developmental_outputs["policy_hint_patch"],
            **endogenous_drive_outputs["policy_hint_patch"],
            **reflective_outputs["policy_hint_patch"],
        },
        response_tendency=(
            reflective_outputs["response_tendency"].to_dict()
            if reflective_outputs["response_tendency"]
            else (
                endogenous_drive_outputs["response_tendency"].to_dict()
                if endogenous_drive_outputs["response_tendency"]
                else (
                    developmental_outputs["response_tendency"].to_dict()
                    if developmental_outputs["response_tendency"]
                    else None
                )
            )
        ),
        candidate_actions=[],
        governor_hint={
            "status": execution.gate.get("status"),
            "mode": "developmental_shadow_only",
        },
        executed_action=None,
        exec_result=None,
        seed_state_delta={},
        seed_state_snapshot={},
        developmental=execution.trace_block,
        timestamp=packet.timestamp,
        legacy_trace_payload={},
    )
    return KernelOutputV2(
        event_id=packet.event_id,
        subject_profile=packet.subject_profile,
        memory_update={"developmental_shadow_updated": True},
        candidate_actions=[],
        confidence_meta={
            "developmental_cycle_id": execution.summary.get("cycle_id"),
            "shadow_revision": execution.summary.get("shadow_revision"),
            "self_model_context_present": bool(extract_runtime_self_model_context(packet.runtime_summary)),
            "reflective_self_context_present": bool(extract_runtime_reflective_self_context(packet.runtime_summary)),
            **execution.self_model_confidence_meta,
        },
        self_model_delta=execution.self_model_delta,
        developmental_summary=execution.summary,
        developmental_shadow_delta=execution.shadow_delta,
        developmental_gate=execution.gate,
        developmental_self_delta=developmental_outputs["developmental_self_delta"],
        developmental_proposal_candidates=developmental_outputs["developmental_proposal_candidates"],
        developmental_continuity_snapshot=developmental_outputs["developmental_continuity_snapshot"],
        developmental_priority_hints=developmental_outputs["developmental_priority_hints"],
        developmental_audit_entries=developmental_outputs["developmental_audit_entries"],
        developmental_writeback_candidate=developmental_outputs["developmental_writeback_candidate"],
        policy_hint={
            "preferred_action_type": "wait",
            "risk_tolerance": "conservative",
            "constraints": [
                "developmental_shadow_only",
                "no_direct_reply_authority",
                "no_direct_execution_authority",
            ],
            "governor_hint": {
                "status": execution.gate.get("status"),
                "mode": "developmental_shadow_only",
            },
            **developmental_outputs["policy_hint_patch"],
            **endogenous_drive_outputs["policy_hint_patch"],
            **reflective_outputs["policy_hint_patch"],
        },
        response_tendency=(
            reflective_outputs["response_tendency"]
            or endogenous_drive_outputs["response_tendency"]
            or developmental_outputs["response_tendency"]
        ),
        endogenous_drive_delta=endogenous_drive_outputs["endogenous_drive_delta"],
        drive_state_snapshot=endogenous_drive_outputs["drive_state_snapshot"],
        priority_snapshot=endogenous_drive_outputs["priority_snapshot"],
        candidate_bias_terms=endogenous_drive_outputs["candidate_bias_terms"],
        self_maintenance_candidate=endogenous_drive_outputs["self_maintenance_candidate"],
        drive_audit_entries=endogenous_drive_outputs["drive_audit_entries"],
        reflective_self_delta=reflective_outputs["reflective_self_delta"],
        revision_proposal_candidates=reflective_outputs["revision_proposal_candidates"],
        confidence_adjustment_hints=reflective_outputs["confidence_adjustment_hints"],
        maintenance_priority_hints=reflective_outputs["maintenance_priority_hints"],
        reflection_writeback_candidate=reflective_outputs["reflection_writeback_candidate"],
        trace_payload=trace_payload,
    )


def process_update_packet(state: ProtoSelfState | ProtoSelfStateV2, packet: UpdatePacketV2) -> KernelOutputV2:
    state_v2 = _coerce_state_v2(state, packet)
    if packet.event.event_type in {"developmental_tick", "developmental_replay"}:
        return _process_developmental_v2(state_v2, packet)
    if packet.subject_profile == SEED_SUBJECT_PROFILE:
        return _process_seed_profile(state_v2, packet)
    return _process_default_v2(state_v2, packet)
