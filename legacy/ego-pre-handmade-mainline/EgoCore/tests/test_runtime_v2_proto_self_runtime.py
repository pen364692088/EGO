from pathlib import Path
from types import SimpleNamespace

from app.config import load_config
from app.runtime_v2.proto_self_runtime import (
    RuntimeV2ProtoSelfRuntime,
    assess_risk_level,
    build_developmental_tick_event,
    build_external_result_event,
    build_finalized_result_event,
    build_idle_check_event,
    build_proto_self_ingress_event,
    build_response_plan_payload,
    normalize_chat_subject_surface,
    resolve_proto_self_schema_version,
    resolve_proto_self_subject_profile,
)
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from app.runtime_v2.state import RuntimeV2State
from app.telegram_evidence_collector import TelegramEvidenceCollector
from openemotion.developmental_self import (
    DevelopmentalSelfOwner,
    DevelopmentalSelfStore,
    PromotionLevel,
)
from openemotion.embodied_self import (
    EmbodiedSelfOwner,
    EmbodiedSelfStore,
)
from openemotion.initiative_realization import (
    REQUIRED_WRITEBACK_GATE as INITIATIVE_REALIZATION_WRITEBACK_GATE,
    CommitmentFulfillmentStatus,
    ControlledDeliveryCandidateStatus,
    InitiativeRealizationOwner,
    InitiativeRealizationStore,
    RealizationMode,
    RealizationProposalStatus,
)
from openemotion.initiative_self import (
    InitiativePriority,
    InitiativeSelfOwner,
    InitiativeSelfStore,
)
from openemotion.endogenous_drives import EndogenousDriveStore
from openemotion.endogenous_drives.reducers import seed_default_state
from openemotion.reflective_self import ReflectiveSelfOwner, ReflectiveSelfStore, ReflectionTargetType
from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE
from openemotion.selfhood_integration import (
    SelfhoodIntegrationOwner,
    SelfhoodIntegrationStore,
)
from openemotion.social_self import (
    BoundaryMode as SocialBoundaryMode,
    CommitmentStatus as SocialCommitmentStatus,
    RelationshipContinuityStatus,
    SocialSelfOwner,
    SocialSelfStore,
)
from openemotion.self_model import Goal, GoalStatus, Priority, SelfModelStore, create_default_self_model
from openemotion.self_model import SelfModelStore, create_default_self_model


def test_assess_risk_level_keeps_existing_keywords():
    assert assess_risk_level("删除生产数据库") == "critical"
    assert assess_risk_level("git push origin main") == "high"
    assert assess_risk_level("状态查询") == "low"


def test_build_proto_self_ingress_event_preserves_v1_fallback_shape():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v1",
        "restore_observation": {
            "restore_id": "restore_001",
            "restore_status": "success",
            "post_restore_first_turn": True,
        }
    }
    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="删除生产数据库",
        state=state,
    )
    assert event["event_id"] == "session:test_turn_001"
    assert event["source"] == "telegram"
    assert event["safety_context"]["risk_level"] == "critical"
    assert "risk" not in event["safety_context"]
    assert event["external_result"] is None
    assert event["runtime_summary"]["restore_observation"]["restore_id"] == "restore_001"


def test_resolve_proto_self_schema_version_defaults_to_v2():
    state = RuntimeV2State(session_id="session:test")
    assert resolve_proto_self_schema_version(state) == "proto_self.v2"


def test_resolve_proto_self_schema_version_supports_explicit_v1_fallback():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v1"}
    assert resolve_proto_self_schema_version(state) == "proto_self.v1"


def test_build_proto_self_ingress_event_supports_v2_shape():
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "prediction_snapshot_prev": {"expected_success": True},
        "executed_action_prev": {"kind": "reply"},
    }
    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_002",
        source="telegram",
        user_input="帮我看下 app.py",
        state=state,
    )

    assert event["schema_version"] == "proto_self.v2"
    assert event["event"]["source"] == "telegram"
    assert event["safety_context"]["risk_level"] == "low"
    assert event["prediction_snapshot_prev"]["expected_success"] is True
    assert event["external_outcome"] is None


def test_build_proto_self_ingress_event_injects_h1_shadow_context(monkeypatch):
    monkeypatch.setenv("EGO_ENABLE_H1_CANONICAL_SHADOW", "true")
    monkeypatch.setenv("EGO_H1_CANONICAL_SHADOW_ALLOWLIST", "session:test")
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_h1_ingress",
        source="telegram",
        user_input="继续",
        state=state,
    )

    assert event["runtime_summary"]["h1_canonical_shadow"]["enabled"] is True
    assert event["runtime_summary"]["h1_canonical_shadow"]["shadow_only"] is True


def test_v2_events_inject_formal_self_model_context(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:self_model_context",
        confidence_class="high",
    )

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_self_model_bridge"
    state.ingress_context = {"proto_self_version": "v2"}
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_ctx_ingress",
        source="telegram",
        user_input="帮我整理下 self-model 读链",
        state=state,
        self_model_store=store,
    )
    external_event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_ctx_external",
        step=0,
        tool_result={"success": True, "tool": "shell", "exit_code": 0, "stderr": ""},
        state=state,
        self_model_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_ctx_finalized",
        result=result,
        state=state,
        self_model_store=store,
    )

    assert ingress_event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"
    assert external_event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"


def test_v2_events_inject_formal_endogenous_drive_context(tmp_path):
    store = EndogenousDriveStore(base_dir=tmp_path)
    store.save(
        seed_default_state(),
        update_source="owner_bootstrap",
        trace_reference="trace:drive_context",
    )

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_drive_bridge"
    state.ingress_context = {"proto_self_version": "v2"}
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_drive_ctx_ingress",
        source="telegram",
        user_input="帮我整理 drive read 链",
        state=state,
        endogenous_drive_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_drive_ctx_finalized",
        result=result,
        state=state,
        endogenous_drive_store=store,
    )

    assert ingress_event["runtime_summary"]["endogenous_drive_context"]["schema_version"] == "mvp14-owner-v1"
    assert ingress_event["runtime_summary"]["endogenous_drive_context"]["owner_revision"] == 1
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["endogenous_drive_context"]["owner_revision"] == 1


def test_v2_events_inject_formal_reflective_self_context(tmp_path):
    store = ReflectiveSelfStore(base_dir=tmp_path)
    owner = ReflectiveSelfOwner(store=store)
    owner.upsert_target(
        target_id="decision:target",
        target_type=ReflectionTargetType.DECISION,
        reference="decision:target",
        reason="review needed",
        salience=0.8,
    )
    owner.enqueue_reflection(
        target_type=ReflectionTargetType.DECISION,
        target_reference="decision:target",
        trigger_source="owner_bootstrap",
        priority=0.7,
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:reflective_context")

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_reflective_bridge"
    state.ingress_context = {"proto_self_version": "v2"}
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_reflect_ctx_ingress",
        source="telegram",
        user_input="帮我整理 reflection read 链",
        state=state,
        reflective_self_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_reflect_ctx_finalized",
        result=result,
        state=state,
        reflective_self_store=store,
    )

    assert ingress_event["runtime_summary"]["reflective_self_context"]["schema_version"] == "mvp15-owner-v1"
    assert ingress_event["runtime_summary"]["reflective_self_context"]["owner_revision"] == 1
    assert ingress_event["runtime_summary"]["reflective_self_context"]["top_target_ids"] == ["decision:target"]
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["reflective_self_context"]["owner_revision"] == 1


def test_v2_events_inject_formal_developmental_self_context_and_host_context(tmp_path):
    store = DevelopmentalSelfStore(base_dir=tmp_path)
    owner = DevelopmentalSelfOwner(store=store)
    owner.set_identity_anchor(
        anchor_summary="bounded developmental continuity",
        invariant_refs=["self_model:identity"],
        confidence=0.93,
    )
    owner.set_trajectory_summary(
        current_arc="governed_growth",
        current_phase="candidate_review",
        continuity_note="keep identity bounded",
        source_refs=["trace:trajectory"],
    )
    owner.set_continuity_metrics(
        continuity_score=0.71,
        growth_pressure=0.58,
        stagnation_signal=0.22,
        identity_preservation_confidence=0.9,
    )
    proposal = owner.add_proposal(
        proposal_kind="continuity_gap",
        summary="review identity-preserving adaptation",
        proposed_adjustment={"continuity_bias": "elevated"},
        justification="bounded developmental continuity",
        promotion_level=PromotionLevel.REVIEW_ONLY,
    )
    owner.queue_promotion(source_proposal_id=proposal.proposal_id, summary="review developmental proposal")
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:developmental_context")

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_developmental_bridge"
    state.ingress_context = {
        "proto_self_version": "v2",
        "developmental_context": {
            "source": "runtime_v2",
            "continuity_gap": 0.28,
            "growth_pressure_hint": 0.64,
            "stagnation_signal_hint": 0.33,
            "identity_guard": "strict",
            "replay_debt": 0.2,
            "promotion_budget": "controlled_axis",
            "drift_markers": ["marker:trajectory_gap"],
        },
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_dev_ctx_ingress",
        source="telegram",
        user_input="帮我整理 developmental continuity bridge",
        state=state,
        developmental_self_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_dev_ctx_finalized",
        result=result,
        state=state,
        developmental_self_store=store,
    )

    assert ingress_event["runtime_summary"]["developmental_self_context"]["schema_version"] == "mvp16-owner-v1"
    assert ingress_event["runtime_summary"]["developmental_self_context"]["owner_revision"] == 1
    assert ingress_event["runtime_summary"]["developmental_context"]["identity_guard"] == "strict"
    assert ingress_event["runtime_summary"]["developmental_context"]["promotion_budget"] == "controlled_axis"
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["developmental_self_context"]["owner_revision"] == 1


def test_v2_events_inject_formal_social_self_context_and_host_context(tmp_path):
    store = SocialSelfStore(base_dir=tmp_path)
    owner = SocialSelfOwner(store=store)
    owner.upsert_relation_memory(
        counterpart_id="telegram:8420019401",
        relationship_summary="ongoing trusted interaction",
        continuity_status=RelationshipContinuityStatus.ACTIVE,
        source_refs=["trace:social_seed"],
    )
    owner.set_trust_state(
        counterpart_id="telegram:8420019401",
        trust_level=0.72,
        trust_delta=-0.08,
        trust_basis=["recent strain"],
    )
    owner.record_commitment(
        counterpart_id="telegram:8420019401",
        summary="follow through on repair",
        status=SocialCommitmentStatus.HELD,
        source_refs=["trace:social_seed"],
        commitment_id="commitment_social_seed",
    )
    owner.set_social_boundary(
        counterpart_id="telegram:8420019401",
        caution_level=0.58,
        boundary_mode=SocialBoundaryMode.CAUTIOUS,
        reason="keep social adjustments bounded",
        source_refs=["trace:social_seed"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:social_context")

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_social_bridge"
    state.ingress_context = {
        "proto_self_version": "v2",
        "social_context": {
            "source": "runtime_v2",
            "counterpart_id": "telegram:8420019401",
            "relationship_event": "tone_feedback",
            "relationship_continuity": "strained",
            "trust_drift": -0.2,
            "commitment_event": "held",
            "repair_outcome": "blocked",
            "unresolved_repair": True,
            "boundary_signal": "cautious",
            "promotion_budget": "review_only",
        },
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_social_ctx_ingress",
        source="telegram",
        user_input="帮我整理 social bridge",
        state=state,
        social_self_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_social_ctx_finalized",
        result=result,
        state=state,
        social_self_store=store,
    )

    assert ingress_event["runtime_summary"]["social_self_context"]["schema_version"] == "mvp17-owner-v1"
    assert ingress_event["runtime_summary"]["social_self_context"]["owner_revision"] == 1
    assert ingress_event["runtime_summary"]["social_context"]["counterpart_id"] == "telegram:8420019401"
    assert ingress_event["runtime_summary"]["social_context"]["relationship_continuity"] == "strained"
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["social_self_context"]["owner_revision"] == 1


def test_v2_events_inject_formal_embodied_self_context_and_environment_context(tmp_path):
    store = EmbodiedSelfStore(base_dir=tmp_path)
    owner = EmbodiedSelfOwner(store=store)
    owner.set_embodied_state(
        resource_slack=0.31,
        perceived_load=0.69,
        action_readiness=0.34,
        source_refs=["trace:embodied_seed"],
    )
    owner.upsert_environment_coupling(
        coupling_id="delivery:telegram:turn_001",
        coupling_strength=0.74,
        controllability_estimate=0.51,
        recent_outcome_summary="delivery timeout increased embodied pressure",
        source_refs=["trace:embodied_seed"],
    )
    owner.set_resource_pressure(
        pressure_id="resource:slack",
        pressure_level=0.77,
        slack_level=0.24,
        recovery_bias=0.63,
        source_refs=["trace:embodied_seed"],
    )
    owner.set_boundary_pressure(
        boundary_id="self_world",
        pressure_level=0.59,
        reason="guard self/world boundary under pressure",
        source_refs=["trace:embodied_seed"],
    )
    owner.record_action_consequence(
        action_ref="delivery:telegram:turn_001",
        outcome_type="failure",
        consequence_summary="delivery timeout caused missed followup",
        impact_score=0.62,
        controllability_estimate=0.47,
        source_refs=["trace:embodied_seed"],
        consequence_id="consequence_embodied_seed",
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:embodied_context")

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_embodied_bridge"
    state.ingress_context = {
        "proto_self_version": "v2",
        "environment_context": {
            "source": "runtime_v2",
            "action_ref": "delivery:telegram:turn_001",
            "coupling_event": "delivery_feedback",
            "outcome_type": "failure",
            "outcome_summary": "delivery timeout caused missed followup",
            "resource_pressure_hint": 0.79,
            "slack_hint": 0.2,
            "boundary_signal": "guarded",
            "boundary_pressure_hint": 0.64,
            "stabilization_needed": True,
            "promotion_budget": "controlled_axis",
        },
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_embodied_ctx_ingress",
        source="telegram",
        user_input="帮我整理 embodied bridge",
        state=state,
        embodied_self_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_embodied_ctx_finalized",
        result=result,
        state=state,
        embodied_self_store=store,
    )

    assert ingress_event["runtime_summary"]["embodied_self_context"]["schema_version"] == "mvp18-owner-v1"
    assert ingress_event["runtime_summary"]["embodied_self_context"]["owner_revision"] == 1
    assert ingress_event["runtime_summary"]["environment_context"]["action_ref"] == "delivery:telegram:turn_001"
    assert ingress_event["runtime_summary"]["environment_context"]["promotion_budget"] == "controlled_axis"
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["embodied_self_context"]["owner_revision"] == 1


def test_v2_events_inject_formal_selfhood_integration_context(tmp_path):
    store = SelfhoodIntegrationStore(base_dir=tmp_path)
    owner = SelfhoodIntegrationOwner(store=store)
    owner.set_integration_state(
        posture="review",
        dominant_pressure_axis="embodied_self",
        stability_bias=0.72,
        integration_confidence=0.63,
        active_axis_count=4,
        rationale_summary="bounded integration",
        source_refs=["trace:selfhood_seed"],
    )
    owner.set_cross_axis_priority_state(
        selected_priority="review",
        stabilize_weight=0.62,
        conserve_weight=0.67,
        guard_weight=0.59,
        review_weight=0.71,
        repair_weight=0.38,
        grow_weight=0.21,
        reflective_modifier=0.12,
        priority_reason="hold under review",
        upstream_pressure_sources=["self_model", "embodied_self"],
        source_refs=["trace:selfhood_seed"],
    )
    owner.propose_integrated_tendency(
        tendency_label="review_first_integration",
        priority_mode="review",
        proposed_effects={"policy_hint": {"self_integration_priority": "review"}},
        justification="bounded integration review",
        source_refs=["trace:selfhood_seed"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:selfhood_seed")

    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "verify_selfhood_bridge"
    state.ingress_context = {"proto_self_version": "v2"}
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_selfhood_ctx_ingress",
        source="telegram",
        user_input="帮我整理 selfhood integration bridge",
        state=state,
        selfhood_integration_store=store,
    )
    finalized_event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_selfhood_ctx_finalized",
        result=result,
        state=state,
        selfhood_integration_store=store,
    )

    assert ingress_event["runtime_summary"]["selfhood_integration_context"]["schema_version"] == "mvp19-owner-v1"
    assert ingress_event["runtime_summary"]["selfhood_integration_context"]["owner_revision"] == 1
    assert finalized_event is not None
    assert finalized_event["runtime_summary"]["selfhood_integration_context"]["owner_revision"] == 1


def test_process_ingress_applies_governed_self_model_writeback(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    class DummyAdapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {},
                "response_tendency": {},
                "reflection_note": None,
                "candidate_actions": [],
                "self_model_delta": {
                    "active_goals": [
                        Goal(
                            goal_id="goal_runtime_bridge",
                            description="Bridge formal self-model writeback through runtime_v2",
                            status=GoalStatus.IN_PROGRESS.value,
                            priority=Priority.HIGH.value,
                            progress=0.5,
                        ).to_dict()
                    ]
                },
                "confidence_meta": {
                    "self_model_update_mode": "append_observation",
                    "self_model_update_source": "proto_self_v2",
                    "self_model_confidence_class": "high",
                    "self_model_trace_reference": "trace:runtime_bridge",
                },
                "trace_payload": {"update_packet_hash": "hash_runtime_bridge"},
            }

    adapter = DummyAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(adapter=adapter, self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_writeback",
        source="telegram",
        user_input="把 self-model 写回接上正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert adapter.last_event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"
    assert state.proto_self_context["self_model_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.active_goals[0].goal_id == "goal_runtime_bridge"
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_rejects_legacy_self_model_writeback(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    class DummyAdapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {},
                "response_tendency": {},
                "reflection_note": None,
                "candidate_actions": [],
                "self_model_delta": {"active_tensions": [{"tension_id": "legacy_only"}]},
                "confidence_meta": {
                    "self_model_update_mode": "append_observation",
                    "self_model_update_source": "proto_self_v2",
                    "self_model_confidence_class": "high",
                    "self_model_trace_reference": "trace:legacy_reject",
                },
                "trace_payload": {"update_packet_hash": "hash_legacy_reject"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=DummyAdapter(), self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_legacy_reject",
        source="telegram",
        user_input="不要把 legacy field 写回 owner store",
        state=state,
    )

    saved = store.load("openemotion")

    assert state.proto_self_context["self_model_writeback"]["decision"]["gate_verdict"] == "reject"
    assert saved is not None
    assert "active_tensions" not in saved.to_dict()
    assert len(store.load_revision_log("openemotion")) == 1


def test_process_ingress_applies_governed_endogenous_drive_writeback(tmp_path):
    store = EndogenousDriveStore(base_dir=tmp_path)
    store.save(
        seed_default_state(),
        update_source="owner_bootstrap",
        trace_reference="trace:init_drive",
    )

    class DummyAdapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {},
                "response_tendency": {},
                "reflection_note": None,
                "candidate_actions": [],
                "self_model_delta": {},
                "endogenous_drive_delta": {
                    "maintenance_debts": [
                        {
                            "category": "replay_verification",
                            "amount": 0.25,
                            "priority": 0.8,
                            "source": "maintenance_context",
                        }
                    ],
                    "drive_adjustments": [
                        {
                            "drive_type": "repair",
                            "intensity_delta": 0.1,
                            "cause": "recent_delivery_outcome:failure",
                        }
                    ],
                },
                "drive_state_snapshot": {"owner_revision": 1},
                "priority_snapshot": {"dominant_drive": "repair"},
                "candidate_bias_terms": {"repair": 0.3},
                "self_maintenance_candidate": {"category": "self_maintenance", "priority": 0.8},
                "confidence_meta": {
                    "endogenous_drive_update_source": "proto_self_v2",
                    "endogenous_drive_trace_reference": "trace:drive_writeback",
                },
                "trace_payload": {"update_packet_hash": "hash_drive_runtime_bridge"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=DummyAdapter(), endogenous_drive_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_drive_writeback",
        source="telegram",
        user_input="把 drive writeback 接上正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert state.proto_self_context["endogenous_drive_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.get_total_maintenance_debt() >= 0.25
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_records_governed_reflection_writeback_without_authority_promotion(tmp_path):
    store = ReflectiveSelfStore(base_dir=tmp_path)
    owner = ReflectiveSelfOwner(store=store)
    owner.upsert_target(
        target_id="decision:target",
        target_type=ReflectionTargetType.DECISION,
        reference="decision:target",
        reason="review needed",
        salience=0.9,
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:reflective_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"reflection_bias": "elevated"},
                "response_tendency": {"preferred_mode": "respond", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "self_model_delta": {},
                "endogenous_drive_delta": {},
                "reflective_self_delta": {"target_ids": ["decision:target"]},
                "revision_proposal_candidates": [
                    {
                        "candidate_id": "reflection_candidate:decision:target",
                        "target_id": "decision:target",
                        "required_gate": "reflection_writeback_gate",
                        "proposal_discipline": "proposal_only",
                    }
                ],
                "confidence_adjustment_hints": {"certainty_bound": "bounded"},
                "maintenance_priority_hints": {"reflection_followup_priority": "elevated"},
                "reflection_writeback_candidate": {
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "required_gate": "reflection_writeback_gate",
                },
                "trace_payload": {"update_packet_hash": "hash_reflective_bridge"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), reflective_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_reflective_bridge",
        source="telegram",
        user_input="把 reflection bridge 接到正式主链",
        state=state,
    )

    assert runtime.adapter.last_event["runtime_summary"]["reflective_self_context"]["owner_revision"] == 1
    assert state.proto_self_context["reflective_self_delta"]["target_ids"] == ["decision:target"]
    assert state.proto_self_context["revision_proposal_candidates"][0]["proposal_discipline"] == "proposal_only"
    assert state.proto_self_context["reflection_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["reflective_self_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    saved = store.load("openemotion")
    assert saved is not None
    assert len(saved.revision_proposals) == 1
    proposal = next(iter(saved.revision_proposals.values()))
    assert proposal.status == "held"
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_applies_governed_developmental_writeback_without_authority_promotion(tmp_path):
    store = DevelopmentalSelfStore(base_dir=tmp_path)
    owner = DevelopmentalSelfOwner(store=store)
    owner.set_identity_anchor(
        anchor_summary="bounded developmental continuity",
        invariant_refs=["self_model:identity"],
        confidence=0.95,
    )
    owner.set_trajectory_summary(
        current_arc="continuity_first",
        current_phase="baseline",
        continuity_note="guard continuity before promotion",
    )
    owner.set_continuity_metrics(
        continuity_score=0.74,
        growth_pressure=0.52,
        stagnation_signal=0.16,
        identity_preservation_confidence=0.92,
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:developmental_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"developmental_continuity_bias": "elevated"},
                "response_tendency": {"preferred_mode": "respond", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "developmental_self_delta": {
                    "proposal_candidate_count": 1,
                    "surface_reasons": ["continuity_gap", "replay_debt"],
                },
                "developmental_proposal_candidates": [
                    {
                        "candidate_id": "developmental_candidate:1:1",
                        "reason": "developmental_continuity",
                        "surface_reasons": ["continuity_gap", "replay_debt"],
                        "continuity_gap": 0.34,
                        "required_gate": "developmental_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "developmental_continuity_snapshot": {
                    "owner_revision": 1,
                    "last_revision_id": "developmental_rev_000001",
                    "continuity_score": 0.66,
                    "continuity_gap": 0.34,
                    "growth_pressure": 0.79,
                    "stagnation_signal": 0.41,
                    "identity_preservation_confidence": 0.86,
                    "developmental_risk_index": 0.47,
                    "trajectory_summary": {
                        "current_arc": "identity_preserving_adaptation",
                        "current_phase": "candidate_review",
                        "recent_shift": "growth pressure up",
                        "continuity_note": "review before promotion",
                        "source_refs": ["trace:developmental_writeback"],
                    },
                    "promotion_queue_size": 0,
                    "recent_proposal_count": 0,
                },
                "developmental_priority_hints": {
                    "continuity_priority": "elevated",
                    "identity_preservation_guard": "strict",
                    "promotion_budget": "controlled_axis",
                },
                "developmental_audit_entries": [
                    {"kind": "developmental_signal", "reason": "continuity_gap"},
                    {"kind": "developmental_signal", "reason": "replay_debt"},
                ],
                "developmental_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "developmental_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "surface_reasons": ["continuity_gap", "replay_debt"],
                    "owner_revision": 1,
                },
                "trace_payload": {"update_packet_hash": "hash_developmental_bridge"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), developmental_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "developmental_context": {
            "source": "runtime_v2",
            "continuity_gap": 0.34,
            "growth_pressure_hint": 0.79,
            "stagnation_signal_hint": 0.41,
            "identity_guard": "strict",
            "replay_debt": 0.2,
            "promotion_budget": "controlled_axis",
            "drift_markers": ["marker:trajectory_gap"],
        },
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_developmental_bridge",
        source="telegram",
        user_input="把 developmental continuity bridge 接到正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["developmental_self_context"]["owner_revision"] == 1
    assert runtime.adapter.last_event["runtime_summary"]["developmental_context"]["promotion_budget"] == "controlled_axis"
    assert state.proto_self_context["developmental_self_delta"]["proposal_candidate_count"] == 1
    assert state.proto_self_context["developmental_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["developmental_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert len(saved.proposal_history) == 1
    assert len(saved.promotion_queue) == 1


def test_process_ingress_applies_governed_social_writeback_without_authority_promotion(tmp_path):
    store = SocialSelfStore(base_dir=tmp_path)
    owner = SocialSelfOwner(store=store)
    owner.upsert_relation_memory(
        counterpart_id="telegram:8420019401",
        relationship_summary="long-running collaboration",
        continuity_status=RelationshipContinuityStatus.ACTIVE,
        source_refs=["trace:social_init"],
    )
    owner.set_trust_state(
        counterpart_id="telegram:8420019401",
        trust_level=0.61,
        trust_delta=-0.05,
        trust_basis=["baseline trust"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:social_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"social_repair_bias": "elevated"},
                "response_tendency": {"preferred_mode": "repair", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "social_self_delta": {
                    "proposal_candidate_count": 1,
                    "counterpart_id": "telegram:8420019401",
                    "relationship_continuity": "strained",
                    "surface_reasons": ["commitment_breach", "unresolved_repair"],
                },
                "relation_update_candidates": [
                    {
                        "candidate_id": "relation_update:telegram:8420019401:1",
                        "counterpart_id": "telegram:8420019401",
                        "relationship_event": "repair_followup",
                        "relationship_continuity": "strained",
                        "required_gate": "social_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "review_only",
                    }
                ],
                "trust_commitment_snapshot": {
                    "counterpart_id": "telegram:8420019401",
                    "owner_revision": 1,
                    "last_revision_id": "social_rev_000001",
                    "trust_signal_max": 0.58,
                    "open_commitment_count": 1,
                    "breached_commitment_count": 1,
                    "pending_repair_count": 1,
                    "boundary_caution_max": 0.67,
                    "relationship_continuity": "strained",
                    "trust_drift": -0.2,
                },
                "social_policy_hints": {
                    "relationship_continuity": "strained",
                    "trust_bias": "guarded",
                    "commitment_guard": "strict",
                    "repair_bias": "elevated",
                    "boundary_mode": "cautious",
                    "counterpart_id": "telegram:8420019401",
                },
                "repair_proposal_candidates": [
                    {
                        "candidate_id": "repair_candidate:telegram:8420019401:2",
                        "counterpart_id": "telegram:8420019401",
                        "reason": "social_repair",
                        "surface_reasons": ["commitment_breach", "unresolved_repair"],
                        "required_gate": "social_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "review_only",
                    }
                ],
                "social_writeback_candidate": {
                    "source": "proto_self_v2",
                    "counterpart_id": "telegram:8420019401",
                    "required_gate": "social_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "review_only",
                    "surface_reasons": ["commitment_breach", "unresolved_repair"],
                    "owner_revision": 1,
                },
                "trace_payload": {
                    "update_packet_hash": "hash_social_bridge",
                    "social_context": {
                        "contract_version": "mvp17.social_contract.v1",
                        "counterpart_id": "telegram:8420019401",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), social_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "social_context": {
            "source": "runtime_v2",
            "counterpart_id": "telegram:8420019401",
            "relationship_event": "tone_feedback",
            "relationship_continuity": "strained",
            "trust_drift": -0.2,
            "commitment_breach": True,
            "repair_outcome": "blocked",
            "unresolved_repair": True,
            "boundary_signal": "cautious",
            "promotion_budget": "review_only",
        },
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_social_bridge",
        source="telegram",
        user_input="把 social writeback 接上正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["social_self_context"]["owner_revision"] == 1
    assert runtime.adapter.last_event["runtime_summary"]["social_context"]["counterpart_id"] == "telegram:8420019401"
    assert state.proto_self_context["social_self_delta"]["proposal_candidate_count"] == 1
    assert state.proto_self_context["social_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["social_context"]["counterpart_id"] == "telegram:8420019401"
    assert state.proto_self_context["social_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert len(saved.repair_state) == 1
    assert len(saved.commitment_state) >= 1
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_applies_governed_embodied_writeback_without_authority_promotion(tmp_path):
    store = EmbodiedSelfStore(base_dir=tmp_path)
    owner = EmbodiedSelfOwner(store=store)
    owner.set_embodied_state(
        resource_slack=0.36,
        perceived_load=0.64,
        action_readiness=0.41,
        source_refs=["trace:embodied_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:embodied_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"embodied_resource_bias": "conserve"},
                "response_tendency": {"preferred_mode": "stabilize", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "embodied_self_delta": {
                    "proposal_candidate_count": 1,
                    "action_ref": "delivery:telegram:turn_001",
                    "surface_reasons": ["resource_pressure", "boundary_pressure"],
                    "boundary_signal": "guarded",
                },
                "consequence_update_candidates": [
                    {
                        "candidate_id": "consequence_update:delivery:telegram:turn_001:1",
                        "action_ref": "delivery:telegram:turn_001",
                        "outcome_type": "failure",
                        "required_gate": "embodied_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "resource_boundary_snapshot": {
                    "owner_revision": 1,
                    "last_revision_id": "embodied_rev_000001",
                    "resource_slack": 0.28,
                    "perceived_load": 0.78,
                    "active_coupling_count": 1,
                    "max_resource_pressure": 0.81,
                    "min_resource_slack": 0.19,
                    "max_boundary_pressure": 0.67,
                    "recent_consequence_count": 1,
                    "stabilization_proposal_count": 0,
                    "self_world_guard_bias": 0.61,
                    "action_ref": "delivery:telegram:turn_001",
                    "outcome_type": "failure",
                    "coupling_event": "delivery_feedback",
                    "boundary_signal": "guarded",
                },
                "embodied_policy_hints": {
                    "resource_bias": "conserve",
                    "boundary_mode": "guarded",
                    "stabilization_bias": "elevated",
                    "consequence_mode": "repair",
                    "self_world_guard": "tight",
                    "action_ref": "delivery:telegram:turn_001",
                },
                "repair_or_stabilize_proposal_candidates": [
                    {
                        "candidate_id": "embodied_stabilize:delivery:telegram:turn_001:1",
                        "reason": "repair_or_stabilize",
                        "surface_reasons": ["resource_pressure", "boundary_pressure"],
                        "required_gate": "embodied_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "controlled_axis",
                    }
                ],
                "embodied_writeback_candidate": {
                    "source": "proto_self_v2",
                    "action_ref": "delivery:telegram:turn_001",
                    "required_gate": "embodied_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "surface_reasons": ["resource_pressure", "boundary_pressure"],
                    "owner_revision": 1,
                },
                "trace_payload": {
                    "update_packet_hash": "hash_embodied_bridge",
                    "environment_context": {
                        "contract_version": "mvp18.embodied_contract.v1",
                        "action_ref": "delivery:telegram:turn_001",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), embodied_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "environment_context": {
            "source": "runtime_v2",
            "action_ref": "delivery:telegram:turn_001",
            "coupling_event": "delivery_feedback",
            "outcome_type": "failure",
            "outcome_summary": "delivery timeout increased embodied pressure",
            "resource_pressure_hint": 0.81,
            "slack_hint": 0.19,
            "boundary_signal": "guarded",
            "boundary_pressure_hint": 0.67,
            "stabilization_needed": True,
            "promotion_budget": "controlled_axis",
        },
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_embodied_bridge",
        source="telegram",
        user_input="把 embodied writeback 接上正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["embodied_self_context"]["owner_revision"] == 1
    assert runtime.adapter.last_event["runtime_summary"]["environment_context"]["action_ref"] == "delivery:telegram:turn_001"
    assert state.proto_self_context["embodied_self_delta"]["proposal_candidate_count"] == 1
    assert state.proto_self_context["embodied_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["environment_context"]["action_ref"] == "delivery:telegram:turn_001"
    assert state.proto_self_context["embodied_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert len(saved.action_consequence_memory) == 1
    assert len(saved.proposal_history) == 1
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_applies_gated_initiative_writeback_without_host_execution_promotion(tmp_path):
    store = InitiativeSelfStore(base_dir=tmp_path)
    owner = InitiativeSelfOwner(store=store)
    owner.set_initiative_state(
        dominant_mode=InitiativePriority.CARRY_FORWARD,
        initiative_pressure=0.74,
        commitment_carryover_bias=0.79,
        recent_delivery_sensitivity=0.42,
        rationale_summary="keep bounded commitment continuity visible",
        source_refs=["trace:initiative_init"],
    )
    owner.set_initiative_priority_state(
        selected_priority=InitiativePriority.CARRY_FORWARD,
        hold_weight=0.2,
        review_weight=0.4,
        prepare_weight=0.5,
        carry_forward_weight=0.9,
        schedule_weight=0.3,
        priority_reason="existing commitment continuity",
        upstream_pressure_sources=["selfhood_integration"],
        source_refs=["trace:initiative_init"],
    )
    owner.set_commitment_continuity_state(
        status="active",
        active_commitments_count=1,
        carried_commitment_refs=["goal:followup"],
        blocked_commitment_refs=[],
        continuity_confidence=0.76,
        carryover_summary="carry forward bounded followup review",
        source_refs=["trace:initiative_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:initiative_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"initiative_priority": "review"},
                "response_tendency": {"preferred_mode": "defer", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "initiative_self_delta": {
                    "proposal_candidate_count": 1,
                    "selected_priority": "review",
                    "commitment_mode": "carry_forward",
                    "host_proactive_mode": "held",
                    "surface_reasons": ["active_commitments", "idle_window", "integration_guard"],
                },
                "initiative_proposal_candidates": [
                    {
                        "proposal_id": "initiative:review:1",
                        "proposal_label": "review_commitment_continuity",
                        "priority_mode": "review",
                        "proposed_effects": {
                            "initiative_bias": "review",
                            "commitment_mode": "carry_forward",
                            "host_proactive_mode": "held",
                        },
                        "justification": "active commitments under guarded integration",
                        "required_gate": "initiative_writeback_gate",
                        "effect_scope": "proposal_only",
                        "behavioral_authority": "none",
                        "requested_effects": ["governed_initiative_review"],
                        "promotion_level": "controlled_axis",
                    }
                ],
                "commitment_execution_snapshot": {
                    "owner_revision": 1,
                    "last_revision_id": "initiative_rev_000001",
                    "selected_priority": "review",
                    "active_commitments_count": 1,
                    "blocked_commitments_count": 0,
                    "continuity_confidence": 0.76,
                    "commitment_mode": "carry_forward",
                    "reserve_level": "medium",
                    "recent_delivery_status": "sent",
                    "idle_seconds": 1200.0,
                    "integrated_priority": "review",
                },
                "initiative_policy_hints": {
                    "initiative_bias": "review",
                    "continuity_mode": "stable",
                    "commitment_mode": "carry_forward",
                    "host_proactive_mode": "held",
                    "reserve_bias": "bounded",
                    "delivery_bias": "normal",
                },
                "host_proactive_candidate": {
                    "candidate_id": "host_proactive:review:1",
                    "candidate_label": "governed_host_proactive_followup",
                    "continuity_basis": "goal:followup",
                    "host_lane_hint": "host_proactive_outbox",
                    "required_gate": "initiative_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "requested_effects": ["governed_host_proactive_review"],
                    "promotion_level": "controlled_axis",
                },
                "initiative_audit_entries": [
                    {
                        "entry_type": "initiative_surface",
                        "selected_priority": "review",
                        "host_proactive_mode": "held",
                        "surface_reasons": ["active_commitments", "idle_window", "integration_guard"],
                    }
                ],
                "initiative_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "initiative_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "selected_priority": "review",
                    "surface_reasons": ["active_commitments", "idle_window", "integration_guard"],
                    "owner_revision": 1,
                },
                "trace_payload": {
                    "update_packet_hash": "hash_initiative_bridge",
                    "initiative_context": {
                        "contract_version": "mvp20.initiative_contract.v1",
                        "projection_field": "runtime_summary.initiative_self_context",
                        "host_hint_field": "runtime_summary.initiative_context",
                        "selected_priority": "carry_forward",
                        "initiative_trigger": "commitment_followup",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), initiative_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "followup"
    state.ingress_context = {
        "proto_self_version": "v2",
        "initiative_context": {
            "source": "runtime_v2",
            "initiative_trigger": "commitment_followup",
            "continuity_ref": "goal:followup",
            "pending_commitment_refs": ["goal:followup"],
            "blocked_commitment_refs": [],
            "reserve_level": "medium",
            "recent_delivery_status": "sent",
            "delivery_failure": False,
            "idle_seconds": 1200.0,
            "host_lane_hint": "host_proactive_outbox",
            "promotion_budget": "controlled_axis",
        },
    }
    state.proto_self_context = {
        "cross_axis_priority_snapshot": {"selected_priority": "review"},
        "integrated_policy_hints": {"integrated_priority": "review"},
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_initiative_bridge",
        source="telegram",
        user_input="继续推进之前承诺的后续动作",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["initiative_self_context"]["owner_revision"] == 1
    assert runtime.adapter.last_event["runtime_summary"]["initiative_context"]["continuity_ref"] == "goal:followup"
    assert state.proto_self_context["initiative_self_delta"]["proposal_candidate_count"] == 1
    assert state.proto_self_context["initiative_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["initiative_writeback_candidate"]["required_gate"] == "initiative_writeback_gate"
    assert state.proto_self_context["initiative_context"]["initiative_trigger"] == "commitment_followup"
    assert state.proto_self_context["initiative_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert saved.initiative_proposal_candidate is not None
    assert saved.initiative_proposal_candidate.behavioral_authority == "none"
    assert saved.host_proactive_candidate is not None
    assert saved.host_proactive_candidate.behavioral_authority == "none"
    assert saved.host_proactive_candidate.host_lane_hint == "host_proactive_outbox"
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_applies_gated_initiative_realization_writeback_without_delivery_promotion(
    tmp_path,
):
    store = InitiativeRealizationStore(base_dir=tmp_path)
    owner = InitiativeRealizationOwner(store=store)
    owner.set_realization_state(
        dominant_mode=RealizationMode.REVIEW,
        realization_pressure=0.22,
        fulfillment_readiness=0.61,
        hold_bias=0.44,
        failure_recovery_bias=0.36,
        rationale_summary="bounded_realization_seed",
        source_refs=["seed"],
    )
    owner.set_delivery_readiness_state(
        selected_lane=RealizationMode.REVIEW,
        hold_weight=0.31,
        review_weight=0.74,
        prepare_weight=0.43,
        mediate_weight=0.28,
        fulfill_weight=0.17,
        lane_reason="bounded_seed_readiness",
        host_lane_hints=["host_reality_review"],
        source_refs=["seed"],
    )
    owner.set_commitment_fulfillment_state(
        status=CommitmentFulfillmentStatus.ACTIVE,
        active_commitments_count=1,
        ready_commitments_count=1,
        realized_commitment_refs=[],
        blocked_commitment_refs=[],
        continuity_confidence=0.79,
        fulfillment_summary="bounded_seed_continuity",
        source_refs=["seed"],
    )
    owner.propose_realization(
        candidate_id="realization_seed_1",
        candidate_label="bounded_realization_seed",
        selected_mode=RealizationMode.REVIEW,
        proposed_effects={"review_queue": True},
        justification="seeded review continuity",
        source_refs=["seed"],
        requested_effects=["governed_realization_review"],
    )
    owner.set_initiative_realization_candidate_status(status=RealizationProposalStatus.HELD)
    owner.set_controlled_delivery_candidate(
        candidate_id="delivery_seed_1",
        candidate_label="bounded_controlled_delivery_seed",
        readiness_basis="seeded_delivery_readiness",
        delivery_readiness=0.72,
        host_lane_hint="host_reality_review",
        source_refs=["seed"],
        requested_effects=["governed_controlled_delivery_review"],
    )
    owner.set_controlled_delivery_candidate_status(status=ControlledDeliveryCandidateStatus.HELD)
    owner.persist(update_source="seed", trace_reference="seed_realization_bridge")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "subject_profile": "seed.v1",
                "policy_hint": {"governor_hint": {"risk": "low"}},
                "candidate_actions": [{"action_type": "review_commitment"}],
                "initiative_realization_delta": {
                    "dominant_mode": "review",
                    "selected_lane": "review",
                    "realization_pressure": 0.63,
                    "fulfillment_readiness": 0.78,
                    "hold_bias": 0.22,
                    "failure_recovery_bias": 0.41,
                    "hold_weight": 0.22,
                    "review_weight": 0.84,
                    "prepare_weight": 0.37,
                    "mediate_weight": 0.31,
                    "fulfill_weight": 0.29,
                    "active_commitments_count": 1,
                    "ready_commitments_count": 1,
                    "continuity_confidence": 0.83,
                    "surface_reasons": ["delivery_continuity_gap", "realization_review"],
                    "fulfillment_summary": "bounded_realization_followup",
                },
                "commitment_fulfillment_candidates": [
                    {
                        "candidate_id": "realization_candidate_1",
                        "candidate_label": "bounded_realization_followup",
                        "selected_mode": "review",
                        "proposed_effects": {"review_commitment": True},
                        "justification": "bounded delivery continuity review",
                        "required_gate": "initiative_realization_writeback_gate",
                        "behavioral_authority": "none",
                        "effect_scope": "proposal_only",
                        "requested_effects": ["governed_realization_review"],
                        "source_refs": ["goal:followup"],
                    }
                ],
                "delivery_readiness_snapshot": {
                    "selected_lane": "review",
                    "readiness_basis": "delivery_continuity_gap",
                    "delivery_readiness": 0.78,
                    "lane_reason": "bounded delivery continuity review",
                },
                "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
                "controlled_delivery_candidate": {
                    "candidate_id": "controlled_delivery_candidate_1",
                    "candidate_label": "governed_controlled_delivery_review",
                    "readiness_basis": "delivery_continuity_gap",
                    "delivery_readiness": 0.78,
                    "host_lane_hint": "host_reality_review",
                    "required_gate": "initiative_realization_writeback_gate",
                    "behavioral_authority": "none",
                    "effect_scope": "proposal_only",
                    "requested_effects": ["governed_controlled_delivery_review"],
                    "source_refs": ["goal:followup"],
                },
                "initiative_realization_audit_entries": [
                    {
                        "entry_type": "initiative_realization_surface",
                        "selected_lane": "review",
                        "surface_reasons": ["delivery_continuity_gap", "realization_review"],
                    }
                ],
                "initiative_realization_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "initiative_realization_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "controlled_axis",
                    "selected_lane": "review",
                },
                "trace_payload": {
                    "update_packet_hash": "hash_realization_bridge",
                    "initiative_realization_context": {
                        "contract_version": "mvp21.initiative_realization_contract.v1",
                        "projection_field": "runtime_summary.initiative_realization_context",
                        "host_hint_field": "runtime_summary.host_proactive_context",
                        "selected_lane": "review",
                        "dominant_mode": "review",
                    },
                    "host_proactive_context": {
                        "source": "runtime_v2",
                        "host_lane_hint": "host_reality_review",
                        "host_lane_hints": ["host_reality_review", "host_continuity_queue"],
                        "pending_realization_refs": ["goal:followup"],
                        "delivery_readiness": 0.78,
                        "readiness_basis": "delivery_continuity_gap",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), initiative_realization_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "followup"
    state.ingress_context = {
        "proto_self_version": "v2",
        "initiative_context": {
            "source": "runtime_v2",
            "initiative_trigger": "commitment_followup",
            "continuity_ref": "goal:followup",
            "pending_commitment_refs": ["goal:followup"],
            "blocked_commitment_refs": [],
            "reserve_level": "medium",
            "recent_delivery_status": "sent",
            "delivery_failure": False,
            "idle_seconds": 1200.0,
            "host_lane_hint": "host_reality_review",
            "promotion_budget": "controlled_axis",
        },
    }

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_realization_bridge",
        source="telegram",
        user_input="把承诺闭环，但先走宿主审查通道。",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["initiative_realization_context"]["owner_revision"] == 1
    assert runtime.adapter.last_event["runtime_summary"]["host_proactive_context"]["host_lane_hint"] == "host_reality_review"
    assert state.proto_self_context["initiative_realization_delta"]["selected_lane"] == "review"
    assert state.proto_self_context["controlled_delivery_candidate"]["behavioral_authority"] == "none"
    assert (
        state.proto_self_context["initiative_realization_writeback_candidate"]["required_gate"]
        == INITIATIVE_REALIZATION_WRITEBACK_GATE
    )
    assert state.proto_self_context["initiative_realization_context"]["selected_lane"] == "review"
    assert state.proto_self_context["host_proactive_context"]["pending_realization_refs"] == ["goal:followup"]
    assert state.proto_self_context["initiative_realization_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert saved.initiative_realization_candidate is not None
    assert saved.initiative_realization_candidate.behavioral_authority == "none"
    assert saved.controlled_delivery_candidate is not None
    assert saved.controlled_delivery_candidate.behavioral_authority == "none"
    assert saved.controlled_delivery_candidate.host_lane_hint == "host_reality_review"
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_rejects_embodied_writeback_behavioral_authority_escalation(tmp_path):
    store = EmbodiedSelfStore(base_dir=tmp_path)
    owner = EmbodiedSelfOwner(store=store)
    owner.set_embodied_state(
        resource_slack=0.41,
        perceived_load=0.52,
        action_readiness=0.44,
        source_refs=["trace:embodied_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:embodied_init")

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"embodied_resource_bias": "conserve"},
                "response_tendency": {"preferred_mode": "stabilize", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "embodied_self_delta": {
                    "proposal_candidate_count": 1,
                    "action_ref": "delivery:telegram:turn_001",
                    "surface_reasons": ["resource_pressure"],
                    "boundary_signal": "guarded",
                },
                "repair_or_stabilize_proposal_candidates": [
                    {
                        "candidate_id": "embodied_stabilize:delivery:telegram:turn_001:1",
                        "reason": "repair_or_stabilize",
                        "surface_reasons": ["resource_pressure"],
                        "required_gate": "embodied_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "review_only",
                    }
                ],
                "embodied_writeback_candidate": {
                    "source": "proto_self_v2",
                    "action_ref": "delivery:telegram:turn_001",
                    "required_gate": "embodied_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "tool",
                    "promotion_level": "review_only",
                },
                "trace_payload": {"update_packet_hash": "hash_embodied_reject"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), embodied_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_embodied_reject",
        source="telegram",
        user_input="不要让 embodied writeback 越权",
        state=state,
    )

    saved = store.load("openemotion")

    assert state.proto_self_context["embodied_writeback"]["decision"]["gate_verdict"] == "reject"
    assert saved is not None
    assert saved.owner_revision == 1
    assert len(saved.proposal_history) == 0


def test_process_ingress_applies_governed_selfhood_integration_writeback_without_authority_promotion(tmp_path):
    store = SelfhoodIntegrationStore(base_dir=tmp_path)
    owner = SelfhoodIntegrationOwner(store=store)
    owner.set_integration_state(
        posture="review",
        dominant_pressure_axis="maintenance",
        stability_bias=0.68,
        integration_confidence=0.57,
        active_axis_count=4,
        rationale_summary="baseline cross-axis review",
        source_refs=["trace:selfhood_init"],
    )
    owner.set_cross_axis_priority_state(
        selected_priority="review",
        stabilize_weight=0.58,
        conserve_weight=0.61,
        guard_weight=0.56,
        review_weight=0.69,
        repair_weight=0.36,
        grow_weight=0.22,
        reflective_modifier=0.11,
        priority_reason="baseline review priority",
        upstream_pressure_sources=["self_model", "endogenous_drives"],
        source_refs=["trace:selfhood_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:selfhood_init")

    class Adapter:
        def __init__(self):
            self.last_event = None

        def handle_event(self, event):
            self.last_event = event
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {"self_integration_priority": "review"},
                "response_tendency": {"preferred_mode": "defer", "certainty_bound": "bounded"},
                "reflection_note": None,
                "candidate_actions": [],
                "self_integration_delta": {
                    "active_axis_count": 5,
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "integration_confidence": 0.64,
                    "stability_bias": 0.73,
                    "surface_reasons": ["self_model_low_confidence", "embodied_pressure_high"],
                },
                "cross_axis_priority_snapshot": {
                    "selected_priority": "review",
                    "stabilize_weight": 0.77,
                    "conserve_weight": 0.74,
                    "guard_weight": 0.72,
                    "review_weight": 0.8,
                    "repair_weight": 0.46,
                    "grow_weight": 0.19,
                    "reflective_modifier": 0.16,
                    "priority_reason": "hold cross-axis proposals under bounded review",
                    "upstream_pressure_sources": ["self_model", "embodied_self", "social_self"],
                    "active_axes": ["self_model", "embodied_self", "social_self"],
                },
                "proposal_conflict_snapshot": {
                    "highest_severity": "medium",
                    "conflict_count": 2,
                    "unresolved_conflict_refs": ["conflict:self_model_vs_growth", "conflict:boundary_vs_repair"],
                    "blocked_axes": ["developmental_self"],
                    "resolution_posture": "review",
                    "source_refs": ["self_model_low_confidence", "embodied_pressure_high"],
                },
                "integrated_policy_hints": {
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "stability_bias": 0.73,
                    "conflict_severity": "medium",
                    "active_axes": ["self_model", "embodied_self", "social_self"],
                    "required_gate": "self_integration_writeback_gate",
                    "behavioral_authority": "none",
                    "proposal_only": True,
                },
                "integrated_tendency_proposal": {
                    "proposal_id": "self_integration:review:1:3",
                    "tendency_label": "review_first_integration",
                    "priority_mode": "review",
                    "policy_mode": "stability_first",
                    "proposed_effects": {"integrated_policy_hints": {"selected_priority": "review"}},
                    "justification": "bounded selfhood integration under review",
                    "required_gate": "self_integration_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "requested_effects": [],
                    "source_refs": ["self_model_low_confidence", "embodied_pressure_high"],
                    "status": "proposed",
                },
                "axis_arbitration_hints": {
                    "self_model": {
                        "hint_id": "axis_hint:self_model:review",
                        "axis_name": "self_model",
                        "recommendation": "hold broad growth until confidence recovers",
                        "priority_weight": 0.83,
                        "guardrail_summary": "advisory_only_no_upstream_owner_mutation",
                        "advisory_only": True,
                        "source_refs": ["self_model_low_confidence"],
                    },
                    "embodied_self": {
                        "hint_id": "axis_hint:embodied_self:review",
                        "axis_name": "embodied_self",
                        "recommendation": "guard boundary before broader coupling",
                        "priority_weight": 0.79,
                        "guardrail_summary": "advisory_only_no_upstream_owner_mutation",
                        "advisory_only": True,
                        "source_refs": ["embodied_pressure_high"],
                    },
                },
                "integration_audit_entries": [
                    {
                        "kind": "integration_priority_selected",
                        "selected_priority": "review",
                        "dominant_pressure_axis": "embodied_self",
                        "source_refs": ["self_model_low_confidence", "embodied_pressure_high"],
                    }
                ],
                "self_integration_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "self_integration_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "selected_priority": "review",
                    "dominant_pressure_axis": "embodied_self",
                    "conflict_severity": "medium",
                    "active_axes": ["self_model", "embodied_self", "social_self"],
                    "owner_revision": 1,
                },
                "trace_payload": {
                    "update_packet_hash": "hash_selfhood_bridge",
                    "selfhood_integration_context": {
                        "contract_version": "mvp19.selfhood_integration_contract.v1",
                        "selected_priority": "review",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), selfhood_integration_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_selfhood_bridge",
        source="telegram",
        user_input="把 selfhood integration bridge 接到正式主链",
        state=state,
    )

    saved = store.load("openemotion")

    assert runtime.adapter.last_event["runtime_summary"]["selfhood_integration_context"]["owner_revision"] == 1
    assert state.proto_self_context["self_integration_delta"]["selected_priority"] == "review"
    assert state.proto_self_context["self_integration_writeback_candidate"]["behavioral_authority"] == "none"
    assert state.proto_self_context["selfhood_integration_context"]["selected_priority"] == "review"
    assert state.proto_self_context["selfhood_integration_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert saved is not None
    assert saved.owner_revision == 2
    assert saved.integrated_tendency_proposal is not None
    assert saved.integrated_tendency_proposal.behavioral_authority == "none"
    assert saved.integrated_tendency_proposal.status == "held"
    assert "self_model" in saved.axis_arbitration_hints
    assert len(store.load_revision_log("openemotion")) == 2


def test_process_ingress_rejects_selfhood_integration_behavioral_authority_escalation(tmp_path):
    store = SelfhoodIntegrationStore(base_dir=tmp_path)
    owner = SelfhoodIntegrationOwner(store=store)
    owner.set_integration_state(
        posture="review",
        dominant_pressure_axis="stability",
        stability_bias=0.61,
        integration_confidence=0.58,
        active_axis_count=3,
        rationale_summary="baseline selfhood integration",
        source_refs=["trace:selfhood_reject_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:selfhood_reject_init")

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {},
                "response_tendency": {},
                "reflection_note": None,
                "candidate_actions": [],
                "self_integration_delta": {
                    "active_axis_count": 3,
                    "selected_priority": "guard",
                    "dominant_pressure_axis": "embodied_self",
                    "integration_confidence": 0.63,
                    "stability_bias": 0.77,
                    "surface_reasons": ["boundary_pressure"],
                },
                "cross_axis_priority_snapshot": {
                    "selected_priority": "guard",
                    "stabilize_weight": 0.71,
                    "conserve_weight": 0.69,
                    "guard_weight": 0.82,
                    "review_weight": 0.66,
                    "repair_weight": 0.28,
                    "grow_weight": 0.11,
                    "reflective_modifier": 0.08,
                    "priority_reason": "guard boundary first",
                    "upstream_pressure_sources": ["embodied_self"],
                    "active_axes": ["embodied_self"],
                },
                "proposal_conflict_snapshot": {
                    "highest_severity": "low",
                    "conflict_count": 1,
                    "unresolved_conflict_refs": ["conflict:boundary"],
                    "blocked_axes": [],
                    "resolution_posture": "review",
                    "source_refs": ["boundary_pressure"],
                },
                "integrated_policy_hints": {
                    "selected_priority": "guard",
                    "dominant_pressure_axis": "embodied_self",
                    "stability_bias": 0.77,
                    "conflict_severity": "low",
                    "active_axes": ["embodied_self"],
                    "required_gate": "self_integration_writeback_gate",
                    "behavioral_authority": "none",
                    "proposal_only": True,
                },
                "self_integration_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "self_integration_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "reply",
                    "selected_priority": "guard",
                    "dominant_pressure_axis": "embodied_self",
                    "conflict_severity": "low",
                    "active_axes": ["embodied_self"],
                    "owner_revision": 1,
                },
                "trace_payload": {"update_packet_hash": "hash_selfhood_reject"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), selfhood_integration_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_selfhood_reject",
        source="telegram",
        user_input="不要让 selfhood integration 越权",
        state=state,
    )

    saved = store.load("openemotion")

    assert state.proto_self_context["selfhood_integration_writeback"]["decision"]["gate_verdict"] == "reject"
    assert saved is not None
    assert saved.owner_revision == 1
    assert saved.integrated_tendency_proposal is None


def test_process_ingress_rejects_social_writeback_behavioral_authority_escalation(tmp_path):
    store = SocialSelfStore(base_dir=tmp_path)
    owner = SocialSelfOwner(store=store)
    owner.upsert_relation_memory(
        counterpart_id="telegram:8420019401",
        relationship_summary="baseline social state",
        continuity_status=RelationshipContinuityStatus.ACTIVE,
        source_refs=["trace:social_reject_init"],
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:social_reject_init")

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "policy_hint": {},
                "response_tendency": {},
                "reflection_note": None,
                "candidate_actions": [],
                "social_self_delta": {
                    "proposal_candidate_count": 1,
                    "counterpart_id": "telegram:8420019401",
                    "surface_reasons": ["commitment_breach"],
                },
                "relation_update_candidates": [],
                "trust_commitment_snapshot": {
                    "counterpart_id": "telegram:8420019401",
                    "owner_revision": 1,
                    "trust_signal_max": 0.4,
                    "breached_commitment_count": 1,
                },
                "social_policy_hints": {
                    "commitment_guard": "strict",
                    "boundary_mode": "cautious",
                },
                "repair_proposal_candidates": [],
                "social_writeback_candidate": {
                    "source": "proto_self_v2",
                    "counterpart_id": "telegram:8420019401",
                    "required_gate": "social_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "reply",
                },
                "trace_payload": {"update_packet_hash": "hash_social_reject"},
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), social_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_social_reject",
        source="telegram",
        user_input="不要让 social writeback 越权",
        state=state,
    )

    saved = store.load("openemotion")

    assert state.proto_self_context["social_writeback"]["decision"]["gate_verdict"] == "reject"
    assert saved is not None
    assert saved.owner_revision == 1
    assert len(store.load_revision_log("openemotion")) == 1


def test_build_proto_self_ingress_event_supports_seed_profile_shape():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "finish_seed_contract"
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "request_mode": "write",
        "runtime_action": "execute_task",
        "interaction_kind": "chat",
        "conversation_act": "presence_check",
        "resolved_target": {"path": "app.py", "filename": "app.py"},
    }

    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_seed_001",
        source="telegram",
        user_input="修改 app.py",
        state=state,
    )

    assert resolve_proto_self_subject_profile(state) == SEED_SUBJECT_PROFILE
    assert event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert event["seed_event"]["event_type"] == "user_event"
    assert event["seed_event"]["runtime_summary"]["request_mode"] == "write"
    assert event["seed_event"]["runtime_summary"]["conversation_act"] == "presence_check"
    assert event["seed_event"]["payload"]["conversation_act"] == "presence_check"
    assert event["seed_event"]["payload"]["resolved_target_path"] == "app.py"


def test_build_external_result_event_preserves_v1_feedback_contract():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {"proto_self_version": "v1"}
    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_001",
        step=0,
        tool_result={"success": False, "tool": "shell", "exit_code": 1, "stderr": "boom"},
        state=state,
    )
    assert event["event_type"] == "tool_result"
    assert event["safety_context"]["risk_level"] == "high"
    assert event["external_result"]["success"] is False
    assert event["task_context"]["blocked_tasks"] == 1


def test_build_external_result_event_supports_v2_shape():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {
        "proto_self_version": "v2",
        "executed_action_prev": {"kind": "tool"},
    }
    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_003",
        step=1,
        tool_result={"success": False, "tool": "shell", "exit_code": 1, "stderr": "boom"},
        state=state,
    )

    assert event["schema_version"] == "proto_self.v2"
    assert event["event"]["event_type"] == "tool_result"
    assert event["external_outcome"]["success"] is False
    assert event["executed_action_prev"]["kind"] == "tool"


def test_build_finalized_result_event_supports_seed_feedback_writeback():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "finish_seed_contract"
    state.last_model_action = {"type": "act"}
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "request_mode": "write",
        "runtime_action": "execute_task",
        "resolved_target": {"path": "app.py", "filename": "app.py"},
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_004",
        result=result,
        state=state,
    )

    assert event is not None
    assert event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert event["seed_event"]["event_type"] == "exec_result"
    assert event["seed_event"]["payload"]["status"] == "success"
    assert event["seed_event"]["payload"]["details"]["host_terminal_status"] == "completed_verified"


def test_build_idle_check_event_requires_seed_profile():
    state = RuntimeV2State(session_id="session:test")
    assert build_idle_check_event(session_id="session:test", turn_id="turn_005", state=state) is None

    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
    idle_event = build_idle_check_event(session_id="session:test", turn_id="turn_005", state=state)
    assert idle_event is not None
    assert idle_event["subject_profile"] == SEED_SUBJECT_PROFILE
    assert idle_event["seed_event"]["event_type"] == "idle_check"


def test_build_developmental_tick_event_requires_explicit_enable(monkeypatch):
    monkeypatch.delenv("EGO_ENABLE_MVP12_SANDBOX", raising=False)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    assert build_developmental_tick_event(
        session_id="session:test",
        turn_id="turn_dev",
        state=state,
    ) is None

    event = build_developmental_tick_event(
        session_id="session:test",
        turn_id="turn_dev",
        state=state,
        force_enable=True,
    )
    assert event is not None
    assert event["event"]["event_type"] == "developmental_tick"
    assert event["runtime_summary"]["developmental_mode"] == "shadow_observe"


def test_v2_event_builders_preserve_experiment_proto_self_scope_across_dashboard_paths():
    experiment_id = "dashboard_local:testnonce:dashboard:test:scope"
    state = RuntimeV2State(session_id="dashboard:test:scope")
    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_state_scope": "experiment",
        "proto_self_experiment_id": experiment_id,
        "proto_self_scope_owner": "dashboard_local",
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id=state.session_id,
        turn_id="turn_scope_ingress",
        source="api:dashboard",
        user_input="你好",
        state=state,
    )
    external_event = build_external_result_event(
        session_id=state.session_id,
        turn_id="turn_scope_external",
        step=0,
        tool_result={"success": True, "tool": "shell", "exit_code": 0, "stderr": ""},
        state=state,
    )
    finalized_event = build_finalized_result_event(
        session_id=state.session_id,
        turn_id="turn_scope_finalized",
        result=result,
        state=state,
    )
    idle_event = build_idle_check_event(
        session_id=state.session_id,
        turn_id="turn_scope_idle",
        state=state,
    )
    developmental_event = build_developmental_tick_event(
        session_id=state.session_id,
        turn_id="turn_scope_dev",
        state=state,
        force_enable=True,
    )

    for event in [ingress_event, external_event, finalized_event, idle_event, developmental_event]:
        assert event is not None
        assert event["runtime_summary"]["state_scope"] == "experiment"
        assert event["runtime_summary"]["experiment_id"] == experiment_id

    for event in [ingress_event, external_event, finalized_event, idle_event]:
        assert event["seed_event"]["runtime_summary"]["state_scope"] == "experiment"
        assert event["seed_event"]["runtime_summary"]["experiment_id"] == experiment_id


def test_v2_event_builders_preserve_private_research_runtime_summary_overrides():
    experiment_id = "active_inference_controlled_observation:failure_repair_retry_file_blocked"
    state = RuntimeV2State(session_id="session:observation:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_state_scope": "experiment",
        "proto_self_experiment_id": experiment_id,
        "proto_self_runtime_summary_overrides": {
            "mvs_replay": {
                "enabled": True,
                "shadow_only": True,
                "variant_id": "mvs_challenger_active_inference_self_model",
                "action_family": "tool:file",
                "scenario_id": "failure_repair_retry_file_blocked",
                "segment_id": "seg_a",
            },
            "controlled_observation": {
                "enabled": True,
                "shadow_only": True,
                "trial_id": "active_inference_controlled_observation",
                "scenario_id": "failure_repair_retry_file_blocked",
                "family": "failure_repair_retry",
                "source_type": "repo_authored_observation_scenario",
                "segment_id": "seg_a",
                "state_snapshot_ref": "fresh_runtime_state",
            },
        },
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(reply_text="已完成", delivery_kind="final", status="completed_verified"),
    )

    ingress_event = build_proto_self_ingress_event(
        session_id=state.session_id,
        turn_id="turn_obs_ingress",
        source="runtime_harness",
        user_input="继续同一条 bounded lane。",
        state=state,
    )
    external_event = build_external_result_event(
        session_id=state.session_id,
        turn_id="turn_obs_external",
        step=0,
        tool_result={"success": False, "tool": "file", "exit_code": 1, "error": "permission denied"},
        state=state,
    )
    finalized_event = build_finalized_result_event(
        session_id=state.session_id,
        turn_id="turn_obs_finalized",
        result=result,
        state=state,
    )

    for event in [ingress_event, external_event, finalized_event]:
        assert event is not None
        runtime_summary = event["runtime_summary"]
        assert runtime_summary["state_scope"] == "experiment"
        assert runtime_summary["experiment_id"] == experiment_id
        assert runtime_summary["mvs_replay"] == {
            "enabled": True,
            "shadow_only": True,
            "variant_id": "mvs_challenger_active_inference_self_model",
            "action_family": "tool:file",
            "scenario_id": "failure_repair_retry_file_blocked",
            "segment_id": "seg_a",
        }
        assert runtime_summary["controlled_observation"] == {
            "enabled": True,
            "shadow_only": True,
            "trial_id": "active_inference_controlled_observation",
            "scenario_id": "failure_repair_retry_file_blocked",
            "family": "failure_repair_retry",
            "source_type": "repo_authored_observation_scenario",
            "segment_id": "seg_a",
            "state_snapshot_ref": "fresh_runtime_state",
        }


def test_build_proto_self_ingress_event_preserves_private_safety_context_overrides():
    state = RuntimeV2State(session_id="session:observation:safety")
    state.ingress_context = {
        "proto_self_version": "v2",
        "proto_self_safety_context_overrides": {
            "risk_level": "high",
            "boundary_touched": True,
        },
    }

    event = build_proto_self_ingress_event(
        session_id=state.session_id,
        turn_id="turn_obs_safety",
        source="runtime_harness",
        user_input="继续，但如果边界不稳就别直接执行。",
        state=state,
    )

    assert event["safety_context"] == {
        "risk_level": "high",
        "boundary_touched": True,
    }


def test_build_proto_self_ingress_event_injects_formal_self_model_context(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_ctx",
        source="telegram",
        user_input="继续",
        state=state,
        self_model_store=store,
    )

    assert event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"
    assert event["runtime_summary"]["self_model_context"]["schema_version"] == "1.0.0"


def test_build_finalized_result_event_injects_formal_self_model_context(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="done",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    event = build_finalized_result_event(
        session_id="session:test",
        turn_id="turn_ctx",
        result=result,
        state=state,
        self_model_store=store,
    )

    assert event is not None
    assert event["runtime_summary"]["self_model_context"]["identity_handle"] == "openemotion"


def test_build_external_result_event_v1_fallback_does_not_steal_family_or_repair_semantics():
    state = RuntimeV2State(session_id="session:test")
    state.current_goal = "执行任务"
    state.ingress_context = {"proto_self_version": "v1"}

    event = build_external_result_event(
        session_id="session:test",
        turn_id="turn_002",
        step=0,
        tool_result={"success": False, "tool": "file", "exit_code": 1, "stderr": "blocked: missing file"},
        state=state,
    )

    assert "closure_family_id" not in event
    assert "closure_signature" not in event
    assert "repair_closure" not in event
    assert "mode_signature" not in event
    assert event["external_result"] == {
        "success": False,
        "tool": "file",
        "exit_code": 1,
        "error": "blocked: missing file",
    }


def test_capture_response_plan_uses_same_payload_shape():
    captured = {}

    class Collector:
        def capture_response_plan(self, plan):
            captured.update(plan)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=object())
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "restore_observation": {
            "restore_id": "restore_001",
            "restore_status": "success",
            "post_restore_first_turn": True,
        }
    }
    state.proto_self_context = {
        "subject_profile": SEED_SUBJECT_PROFILE,
        "candidate_actions": [{"action_type": "inspect_file"}],
        "governor_hint": {"status": "approved"},
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
        ),
    )
    runtime.capture_response_plan(result=result, evidence_collector=Collector())
    assert captured == build_response_plan_payload(result=result)
    assert captured["restore_observation"]["restore_id"] == "restore_001"
    assert captured["proto_self_subject_profile"] == SEED_SUBJECT_PROFILE
    assert captured["candidate_action_types"] == ["inspect_file"]
    assert captured["proto_self_governor_hint"]["status"] == "approved"


def test_process_ingress_prefers_collector_for_trace_capture():
    captured = {"normalized_event": None, "result": None, "trace": None}

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "policy_hint": {"risk_bias": "high"},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v1",
                    "event_id": event["event_id"],
                    "policy_hint": {"risk_bias": "high"},
                },
            }

    class Collector:
        def capture_normalized_event(self, event):
            captured["normalized_event"] = event

        def capture_openemotion_result(self, result):
            captured["result"] = result

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["trace"] = {"payload": trace_payload, "stage": stage}

    class TraceBridge:
        def __init__(self):
            self.entries = []

        def write(self, payload):
            self.entries.append(payload)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), trace_bridge=TraceBridge())
    state = RuntimeV2State(session_id="session:test")
    collector = Collector()

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="删除生产数据库",
        state=state,
        evidence_collector=collector,
    )

    assert captured["normalized_event"]["event_id"] == "session:test_turn_001"
    assert captured["result"]["event_id"] == "session:test_turn_001"
    assert captured["trace"]["stage"] == "ingress_kernel_trace"
    assert runtime.trace_bridge.entries == []


def test_normalize_chat_subject_surface_exposes_explicit_richer_fields_for_capture():
    captured = {"result": None, "trace": None}

    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "policy_hint": {"risk_bias": "high"},
                "response_tendency": {"preferred_mode": "ask"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                },
            }

    class Collector:
        def capture_normalized_event(self, event):
            return None

        def capture_openemotion_result(self, result):
            captured["result"] = result

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["trace"] = trace_payload

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="你好",
        state=state,
        evidence_collector=Collector(),
    )

    for field in (
        "social_policy_hints",
        "embodied_policy_hints",
        "integrated_policy_hints",
        "initiative_policy_hints",
    ):
        assert field in captured["result"]
        assert captured["result"][field] == {}
        assert state.proto_self_context[field] == {}

    for field in (
        "social_context",
        "environment_context",
        "selfhood_integration_context",
        "initiative_realization_context",
        "host_proactive_context",
    ):
        assert field in captured["trace"]
        assert captured["trace"][field] == {}


def test_normalize_chat_subject_surface_helper_keeps_existing_values():
    result = normalize_chat_subject_surface(
        {
            "social_policy_hints": {"repair_bias": "elevated"},
            "trace_payload": {
                "schema_version": "proto_self.trace.v2",
                "social_context": {"counterpart_id": "telegram:8420019401"},
            },
        }
    )

    assert result["social_policy_hints"] == {"repair_bias": "elevated"}
    assert result["embodied_policy_hints"] == {}
    assert result["trace_payload"]["social_context"] == {"counterpart_id": "telegram:8420019401"}
    assert result["trace_payload"]["environment_context"] == {}


def test_process_ingress_falls_back_to_trace_bridge_without_collector():
    class Adapter:
        def handle_event(self, event):
            return {
                "event_id": event["event_id"],
                "policy_hint": {"risk_bias": "normal"},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v1",
                    "event_id": event["event_id"],
                    "policy_hint": {"risk_bias": "normal"},
                },
            }

    class TraceBridge:
        def __init__(self):
            self.entries = []

        def write(self, payload):
            self.entries.append(payload)

    bridge = TraceBridge()
    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), trace_bridge=bridge)
    state = RuntimeV2State(session_id="session:test")

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="你好",
        state=state,
    )

    assert bridge.entries == [
        {
            "schema_version": "proto_self.trace.v1",
            "event_id": "session:test_turn_001",
            "policy_hint": {"risk_bias": "normal"},
            "social_context": {},
            "environment_context": {},
            "selfhood_integration_context": {},
            "initiative_realization_context": {},
            "host_proactive_context": {},
        }
    ]


async def _run_chat_turn(loop, session_id: str, text: str, *, source: str, collector):
    from app.runtime_v2.action_protocol import RuntimeV2Action

    async def fake_decide(_state):
        return RuntimeV2Action.from_model_output('{"type":"chat","message":"已收到"}')

    loop._decide = fake_decide
    return await loop.run_turn_typed(session_id, text, source=source, evidence_collector=collector)


def test_runtime_loop_captures_proto_self_v2_evidence_in_ledger(monkeypatch, tmp_path):
    import asyncio

    from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
    from app.runtime_v2.loop import RuntimeV2Loop

    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    load_config(validate=False)

    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated",
        channel="telegram",
        evidence_level="E4",
    )
    collector.start_sample(
        {
            "update_id": 5001,
            "message": {
                "message_id": 5001,
                "date": 1774483895,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "is_bot": False, "username": "tester"},
                "text": "帮我看下 app.py",
            },
        }
    )

    loop = RuntimeV2Loop()
    loop.proto_self_runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    )
    state = loop.get_state("session:test-v2")
    state.ingress_context = {
        "proto_self_version": "v2",
        "prediction_snapshot_prev": {"expected_success": True},
        "executed_action_prev": {"kind": "reply", "status": "delivered"},
    }

    result = asyncio.run(
        _run_chat_turn(
            loop,
            "session:test-v2",
            "帮我看下 app.py",
            source="telegram",
            collector=collector,
        )
    )
    collector.capture_outbox_record(
        {
            "chat_id": 42,
            "message_id": 5002,
            "date": "2026-03-28T00:00:01",
            "text_length": len(result.reply_text),
            "success": True,
        }
    )
    sample = collector.finalize_sample()

    assert sample is not None
    assert sample.normalized_event["schema_version"] == "proto_self.v2"
    assert sample.openemotion_result["schema_version"] == "proto_self.output.v2"
    assert sample.openemotion_trace["schema_version"] == "proto_self.trace.v2"
    assert sample.ledger["openemotion"]["trace_payload"]["schema_version"] == "proto_self.trace.v2"


def test_process_finalized_result_and_idle_check_capture_seed_trace():
    captured = {"stages": []}

    class Adapter:
        def handle_event(self, event):
            suffix = event["event_id"].split("_")[-1]
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "candidate_actions": [{"action_type": "inspect_file"}] if suffix == "idle" else [],
                "policy_hint": {"governor_hint": {"status": "approved"}},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "subject_profile": event.get("subject_profile"),
                    "exec_result": (event.get("seed_event") or {}).get("payload"),
                    "candidate_actions": [{"action_type": "inspect_file"}] if suffix == "idle" else [],
                },
            }

    class Collector:
        def capture_openemotion_result(self, result):
            captured.setdefault("results", []).append(result["event_id"])

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["stages"].append(stage)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")
    state.proto_self_subject_profile_override = SEED_SUBJECT_PROFILE
    state.ingress_context = {
        "proto_self_subject_profile": SEED_SUBJECT_PROFILE,
        "resolved_target": {"path": "app.py", "filename": "app.py"},
    }
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state=state,
        reply=RuntimeV2Reply(
            reply_text="done",
            delivery_kind="final",
            status="completed_verified",
        ),
    )

    runtime.process_finalized_result(
        session_id="session:test",
        turn_id="turn_final",
        result=result,
        state=state,
        evidence_collector=Collector(),
    )
    runtime.process_idle_check(
        session_id="session:test",
        turn_id="turn_final",
        state=state,
        evidence_collector=Collector(),
    )

    assert "finalized_result_kernel_trace" in captured["stages"]
    assert "idle_check_kernel_trace" in captured["stages"]
    assert state.proto_self_context["last_exec_result"]["status"] == "success"


def test_process_ingress_records_self_model_writeback_without_owner_promotion(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    baseline = create_default_self_model("openemotion")
    store.save(
        baseline,
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "self_model_delta": {"confidence_by_domain": {"reasoning": 0.97}},
                "policy_hint": {"governor_hint": {"status": "approved"}},
                "response_tendency": {"preferred_mode": "respond"},
                "reflection_note": None,
                "candidate_actions": [],
                "confidence_meta": {
                    "self_model_update_mode": "append_observation",
                    "self_model_update_source": "proto_self_v2",
                    "self_model_confidence_class": "high",
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "hash_001",
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_001",
        source="telegram",
        user_input="继续",
        state=state,
    )

    saved = store.load("openemotion")

    assert saved is not None
    assert saved.confidence_by_domain["reasoning"] == 0.97
    assert state.proto_self_context["self_model_delta"] == {"confidence_by_domain": {"reasoning": 0.97}}
    assert state.proto_self_context["self_model_writeback"]["decision"]["gate_verdict"] == "allow_writeback"


def test_process_ingress_bridges_shadow_h1_without_promoting_live_policy(monkeypatch):
    monkeypatch.setenv("EGO_ENABLE_H1_CANONICAL_SHADOW", "true")
    monkeypatch.setenv("EGO_H1_CANONICAL_SHADOW_ALLOWLIST", "session:test")

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "subject_profile": event.get("subject_profile"),
                "self_model_delta": {},
                "policy_hint": {"ask_preferred": False, "governor_hint": {"status": "bounded"}},
                "response_tendency": {"preferred_mode": "respond", "ask_needed": False},
                "reflection_note": None,
                "candidate_actions": [],
                "confidence_meta": {
                    "shadow_h1_enabled": True,
                    "shadow_h1_action_key": "tool:file",
                    "shadow_h1_predicted_success": 0.22,
                    "shadow_h1_threshold": 0.35,
                    "shadow_h1_would_guard": True,
                    "shadow_h1_would_ask": True,
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "shadow_h1": {
                        "enabled": True,
                        "action_key": "tool:file",
                        "predicted_success": 0.22,
                        "threshold": 0.35,
                        "would_guard": True,
                        "would_ask": True,
                        "source": "canonical_shadow",
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    runtime.process_ingress(
        session_id="session:test",
        turn_id="turn_h1_bridge",
        source="telegram",
        user_input="继续",
        state=state,
    )

    assert state.proto_self_context["shadow_h1"]["action_key"] == "tool:file"
    assert state.proto_self_context["shadow_h1"]["would_guard"] is True
    assert state.proto_self_context["policy_hint"]["ask_preferred"] is False


def test_process_developmental_tick_updates_shadow_summary_and_trace():
    captured = {"stages": []}

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "developmental_summary": {
                    "cycle_id": "cycle_001",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "observation_source": event["runtime_summary"]["observation_source"],
                    "shadow_revision": 2,
                    "background_thought_candidates": [
                        {
                            "candidate_id": "cand_001",
                            "draft_text": "我后来又想到一个问题。",
                            "initiative_score": 0.74,
                            "delivery_ready": True,
                        }
                    ],
                    "background_thought_candidate_count": 1,
                },
                "developmental_gate": {"status": "allow"},
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "developmental": {"cycle_id": "cycle_001"},
                },
            }

    class Collector:
        def capture_normalized_event(self, event):
            captured["event_id"] = event["event_id"]

        def capture_openemotion_result(self, result):
            captured["result_id"] = result["event_id"]

        def capture_openemotion_trace(self, trace_payload, *, stage):
            captured["stages"].append(stage)

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    result = runtime.process_developmental_tick(
        session_id="session:test",
        turn_id="turn_dev",
        state=state,
        observation_source="synthetic",
        force_enable=True,
        evidence_collector=Collector(),
    )

    assert result is not None
    assert captured["event_id"] == "session:test_turn_dev_developmental"
    assert "developmental_tick_kernel_trace" in captured["stages"]
    assert state.proto_self_context["developmental_summary"]["cycle_id"] == "cycle_001"
    assert state.proto_self_context["background_thought_candidates"][0]["candidate_id"] == "cand_001"
    assert state.proto_self_context["shadow_revision"] == 2
    assert state.proto_self_context["last_developmental_cycle"] == "cycle_001"


def test_process_developmental_tick_preserves_observation_refs():
    class Adapter:
        def handle_event(self, event):
            refs = (
                (((event.get("intervention_context") or {}).get("developmental_input") or {}).get("observation_refs"))
                or []
            )
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "developmental_summary": {
                    "cycle_id": "cycle_refs",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "observation_source": event["runtime_summary"]["observation_source"],
                    "shadow_revision": 1,
                    "background_thought_candidates": [],
                    "background_thought_candidate_count": 0,
                },
                "developmental_gate": {"status": "allow"},
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "developmental": {
                        "cycle_id": "cycle_refs",
                        "observation_refs": refs,
                    },
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter())
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    result = runtime.process_developmental_tick(
        session_id="session:test",
        turn_id="turn_dev_refs",
        state=state,
        observation_source="direct_real",
        observation_refs=[
            {"kind": "telegram_ingress", "event_id": "ingress_1"},
            {"kind": "telegram_delivery", "event_id": "delivery_1"},
        ],
        force_enable=True,
    )

    assert result is not None
    assert result["trace_payload"]["developmental"]["observation_refs"] == [
        {"kind": "telegram_ingress", "event_id": "ingress_1"},
        {"kind": "telegram_delivery", "event_id": "delivery_1"},
    ]


def test_process_developmental_tick_writes_formal_owner_revision(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(
        create_default_self_model("openemotion"),
        update_source="owner_bootstrap",
        trace_reference="trace:init",
        confidence_class="high",
    )

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "self_model_delta": {
                    "known_unknowns": [
                        {
                            "unknown_id": "unknown_dev_001",
                            "category": "dialogue_frame",
                            "frame_kind": "continuity_gap",
                            "anchor": "内容回返与主体连续",
                            "open_question": "回返的内容和连续的主体，到底是不是同一回事？",
                            "hidden_premise": "内容能回返，就足以证明主体连续。",
                            "source_cycle": "dev-trace",
                            "source_candidate_hash": "hash_dev_001",
                            "observation_source": "direct_real",
                            "status": "open",
                        }
                    ],
                    "confidence_by_domain": {
                        "dialogue_frame:continuity_gap": 0.81,
                    },
                },
                "confidence_meta": {
                    "self_model_update_mode": "append_observation",
                    "self_model_update_source": "proto_self_v2.developmental",
                    "self_model_trace_reference": "developmental:dev-trace:hash_dev_001",
                    "self_model_confidence_class": "high",
                    "self_model_candidate_id": "cand_dev_001",
                    "self_model_supporting_evidence": [
                        "frame:continuity_gap",
                        "unknown:unknown_dev_001",
                    ],
                },
                "developmental_summary": {
                    "cycle_id": "dev-trace",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "observation_source": event["runtime_summary"]["observation_source"],
                    "shadow_revision": 3,
                    "background_thought_candidates": [],
                    "background_thought_candidate_count": 0,
                    "self_model_delta_fields": ["confidence_by_domain", "known_unknowns"],
                },
                "developmental_gate": {"status": "allow"},
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "tracehash_dev_001",
                    "developmental": {"cycle_id": "dev-trace"},
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), self_model_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {"proto_self_version": "v2"}

    result = runtime.process_developmental_tick(
        session_id="session:test",
        turn_id="turn_dev_writeback",
        state=state,
        observation_source="direct_real",
        force_enable=True,
    )

    saved = store.load("openemotion")
    revisions = store.load_revision_log("openemotion")

    assert result is not None
    assert saved is not None
    assert saved.known_unknowns[-1]["unknown_id"] == "unknown_dev_001"
    assert saved.confidence_by_domain["dialogue_frame:continuity_gap"] == 0.81
    assert state.proto_self_context["self_model_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert revisions[-1].trace_reference == "developmental:dev-trace:hash_dev_001"


def test_process_developmental_tick_records_formal_developmental_writeback(tmp_path):
    store = DevelopmentalSelfStore(base_dir=tmp_path)
    owner = DevelopmentalSelfOwner(store=store)
    owner.set_identity_anchor(
        anchor_summary="bounded developmental continuity",
        invariant_refs=["self_model:identity"],
        confidence=0.94,
    )
    owner.set_trajectory_summary(
        current_arc="governed_growth",
        current_phase="observation",
        continuity_note="preserve identity before promotion",
    )
    owner.set_continuity_metrics(
        continuity_score=0.69,
        growth_pressure=0.57,
        stagnation_signal=0.24,
        identity_preservation_confidence=0.91,
    )
    owner.persist(update_source="owner_bootstrap", trace_reference="trace:developmental_tick_init")

    class Adapter:
        def handle_event(self, event):
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "developmental_summary": {
                    "cycle_id": "cycle_dev_owner",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "observation_source": event["runtime_summary"]["observation_source"],
                    "shadow_revision": 4,
                    "background_thought_candidates": [],
                    "background_thought_candidate_count": 0,
                },
                "developmental_self_delta": {
                    "proposal_candidate_count": 1,
                    "surface_reasons": ["continuity_gap"],
                },
                "developmental_proposal_candidates": [
                    {
                        "candidate_id": "developmental_candidate:2:1",
                        "reason": "developmental_continuity",
                        "surface_reasons": ["continuity_gap"],
                        "continuity_gap": 0.29,
                        "required_gate": "developmental_writeback_gate",
                        "proposal_discipline": "proposal_only",
                        "behavioral_authority": "none",
                        "promotion_level": "review_only",
                    }
                ],
                "developmental_continuity_snapshot": {
                    "owner_revision": 1,
                    "last_revision_id": "developmental_rev_000001",
                    "continuity_score": 0.71,
                    "continuity_gap": 0.29,
                    "growth_pressure": 0.68,
                    "stagnation_signal": 0.35,
                    "identity_preservation_confidence": 0.89,
                    "developmental_risk_index": 0.39,
                    "trajectory_summary": {
                        "current_arc": "identity_preserving_adaptation",
                        "current_phase": "review",
                        "recent_shift": "gap surfaced under growth pressure",
                        "continuity_note": "hold promotion until review",
                        "source_refs": ["trace:developmental_tick"],
                    },
                    "promotion_queue_size": 0,
                    "recent_proposal_count": 0,
                },
                "developmental_priority_hints": {
                    "continuity_priority": "elevated",
                    "identity_preservation_guard": "bounded",
                    "promotion_budget": "review_only",
                },
                "developmental_audit_entries": [
                    {"kind": "developmental_signal", "reason": "continuity_gap"}
                ],
                "developmental_writeback_candidate": {
                    "source": "proto_self_v2",
                    "required_gate": "developmental_writeback_gate",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "promotion_level": "review_only",
                    "surface_reasons": ["continuity_gap"],
                    "owner_revision": 1,
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "tracehash_dev_owner_001",
                    "developmental": {"cycle_id": "cycle_dev_owner"},
                },
            }

    runtime = RuntimeV2ProtoSelfRuntime(adapter=Adapter(), developmental_self_store=store)
    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "developmental_context": {
            "source": "runtime_v2",
            "continuity_gap": 0.29,
            "growth_pressure_hint": 0.68,
            "stagnation_signal_hint": 0.35,
            "identity_guard": "bounded",
            "replay_debt": 0.0,
            "promotion_budget": "review_only",
            "drift_markers": [],
        },
    }

    result = runtime.process_developmental_tick(
        session_id="session:test",
        turn_id="turn_dev_owner",
        state=state,
        observation_source="direct_real",
        force_enable=True,
    )

    saved = store.load("openemotion")
    revisions = store.load_revision_log("openemotion")

    assert result is not None
    assert saved is not None
    assert state.proto_self_context["developmental_writeback"]["decision"]["gate_verdict"] == "allow_writeback"
    assert state.proto_self_context["developmental_proposal_candidates"][0]["promotion_level"] == "review_only"
    assert state.proto_self_context["developmental_continuity_snapshot"]["continuity_gap"] == 0.29
    assert state.proto_self_context["developmental_priority_hints"]["identity_preservation_guard"] == "bounded"
    assert saved.owner_revision == 2
    assert len(saved.proposal_history) == 1
    assert revisions[-1].trace_reference == "tracehash_dev_owner_001"
