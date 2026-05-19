from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.runtime_v2.state import RuntimeV2State
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE
from openemotion.self_model import (
    Goal,
    GoalStatus,
    Limitation,
    Priority,
    SelfModelStore,
    StandingCommitment,
    create_default_self_model,
)


def _build_self_model_store(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    model = create_default_self_model("openemotion")
    model.limitations = [
        Limitation(
            limitation_id="lim_001",
            description="bounded continuity",
            impact_level="medium",
        )
    ]
    model.active_goals = [
        Goal(
            goal_id="goal_001",
            description="preserve continuity",
            status=GoalStatus.IN_PROGRESS.value,
            priority=Priority.HIGH.value,
            progress=0.4,
        )
    ]
    model.standing_commitments = [
        StandingCommitment(
            commitment_id="commitment_001",
            source="identity_invariants",
            description="do not bypass EgoCore",
            binding_level="hard",
            active=True,
        )
    ]
    model.confidence_by_domain = {"continuity": 0.74}
    store.save(
        model,
        update_source="test_subject_system_v1",
        trace_reference="trace:test_subject_system_v1",
        confidence_class="high",
    )
    return store


def test_process_ingress_writes_subject_system_v1_context_from_runtime_projection(tmp_path):
    store = _build_self_model_store(tmp_path)

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "self_model_delta": {"delta_kind": "bounded"},
                "memory_update": {"memory_written": True},
                "drives_delta": {"care": {"delta": 0.2}},
                "reflection_writeback_candidate": {"candidate_id": "reflect_001"},
                "policy_hint": {
                    "initiative_host_proactive_mode": "candidate",
                    "governor_hint": {"status": "bounded"},
                },
                "response_tendency": {"preferred_mode": "respond"},
                "initiative_policy_hints": {
                    "delivery_bias": "normal",
                    "host_proactive_mode": "candidate",
                },
                "commitment_execution_snapshot": {
                    "active_commitments_count": 1,
                    "continuity_confidence": 0.78,
                    "commitment_mode": "carry_forward",
                    "recent_delivery_status": "sent",
                },
                "host_proactive_candidate": {
                    "candidate_id": "candidate_ingress_001",
                    "candidate_label": "governed_host_proactive_followup",
                    "continuity_basis": "goal:followup",
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "hash_ingress_subject_system",
                    "initiative_context": {
                        "initiative_trigger": "commitment_followup",
                        "continuity_ref": "goal:followup",
                        "selected_priority": "carry_forward",
                        "idle_seconds": 1200.0,
                    },
                    "selfhood_integration_context": {
                        "selected_priority": "grow",
                        "highest_conflict_severity": "low",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_subject_bridge",
        source="telegram",
        user_input="继续保持连续性并推进承诺",
        state=state,
    )

    subject_system = state.proto_self_context["subject_system_v1"]
    assert subject_system["identity_invariants"]["identity_handle"] == "openemotion"
    assert subject_system["identity_invariants"]["limitations"][0]["limitation_id"] == "lim_001"
    assert subject_system["identity_invariants"]["active_goals"][0]["goal_id"] == "goal_001"
    assert subject_system["appraisal_state_delta"] == {"care": {"delta": 0.2}}
    assert subject_system["memory_update"] == {"memory_written": True}
    assert subject_system["host_proactive_candidate"]["candidate_family"] == "commitment_followup"
    assert subject_system["trace_payload"]["self_model_context_source"] == "loaded"
    assert "host_proactive_decision" not in state.proto_self_context


def test_process_developmental_tick_emits_candidate_only_host_proactive_decision(tmp_path):
    store = _build_self_model_store(tmp_path)

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "developmental_summary": {
                    "cycle_id": "cycle_subject_system",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "observation_source": event["runtime_summary"]["observation_source"],
                    "shadow_revision": 1,
                    "background_thought_candidates": [],
                    "background_thought_candidate_count": 0,
                },
                "memory_update": {"developmental_shadow_updated": True},
                "policy_hint": {
                    "initiative_host_proactive_mode": "candidate",
                    "governor_hint": {"status": "bounded"},
                },
                "response_tendency": {"preferred_mode": "respond"},
                "initiative_policy_hints": {
                    "delivery_bias": "normal",
                    "host_proactive_mode": "candidate",
                },
                "commitment_execution_snapshot": {
                    "active_commitments_count": 1,
                    "continuity_confidence": 0.82,
                    "commitment_mode": "carry_forward",
                    "recent_delivery_status": "sent",
                },
                "host_proactive_candidate": {
                    "candidate_id": "candidate_dev_001",
                    "candidate_label": "governed_host_proactive_followup",
                    "continuity_basis": "goal:followup",
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "hash_dev_subject_system",
                    "initiative_context": {
                        "initiative_trigger": "commitment_followup",
                        "continuity_ref": "goal:followup",
                        "selected_priority": "carry_forward",
                        "idle_seconds": 1200.0,
                    },
                    "selfhood_integration_context": {
                        "selected_priority": "grow",
                        "highest_conflict_severity": "low",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
    }

    result = runtime.process_developmental_tick(
        session_id="session:test",
        turn_id="turn_subject_system_dev",
        state=state,
        observation_source="direct_real",
        force_enable=True,
        idle_seconds=1200.0,
    )

    assert result is not None
    assert result["host_proactive_decision"]["status"] == "candidate_ready"
    assert result["host_proactive_decision"]["mode"] == "suggest"
    assert state.proto_self_context["host_proactive_decision"]["candidate_id"] == "candidate_dev_001"
    assert state.proto_self_context["subject_system_v1"]["host_proactive_candidate"]["candidate_family"] == (
        "commitment_followup"
    )
    assert state.get_pending_proactive_followup() is None
    assert state.peek_proactive_outbox_events() == []
