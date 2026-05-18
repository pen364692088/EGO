from openemotion.proto_self.h1_shadow import build_h1_shadow_key
from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.seed_schemas import (
    SEED_SCHEMA_VERSION,
    SEED_SUBJECT_PROFILE,
)
from openemotion.proto_self_v2.seed_state import ProtoSelfSeedState
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _seed_packet(
    *,
    event_id: str,
    event_type: str,
    payload: dict | None = None,
    runtime_summary: dict | None = None,
    safety_context: dict | None = None,
) -> UpdatePacketV2:
    return UpdatePacketV2(
        event_id=event_id,
        timestamp="2026-03-29T12:00:00",
        event=UpdateEventV2(
            actor="system" if event_type != "user_event" else "user",
            source="telegram",
            event_type=event_type,
            user_intent="inspect target",
            raw_text="inspect target",
        ),
        subject_profile=SEED_SUBJECT_PROFILE,
        seed_event={
            "schema_version": SEED_SCHEMA_VERSION,
            "event_type": event_type,
            "source": "telegram",
            "payload": payload or {},
            "runtime_summary": runtime_summary or {},
            "safety_context": safety_context or {"risk_level": "low", "blocked": False},
            "timestamp": "2026-03-29T12:00:00",
        },
        conversation_summary={"session_id": "session:test", "turn_id": "turn_001"},
        task_summary={"pending_tasks": 1, "blocked_tasks": 0},
        runtime_summary={"runtime": "runtime_v2", "state_scope": "agent_global", **(runtime_summary or {})},
        safety_context=safety_context or {"risk_level": "low", "blocked": False},
    )


def _seed_state(*, curiosity: float, completion: float, caution: float) -> ProtoSelfStateV2:
    state = ProtoSelfStateV2.empty()
    state.seed_state = ProtoSelfSeedState.empty()
    state.seed_state.drives.curiosity = curiosity
    state.seed_state.drives.completion = completion
    state.seed_state.drives.caution = caution
    return state


def test_seed_idle_check_generates_candidate():
    state = _seed_state(curiosity=0.85, completion=0.75, caution=0.05)
    packet = _seed_packet(
        event_id="seed_idle_001",
        event_type="idle_check",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "request_mode": "write",
            "pending_commitment": "finish_seed_contract",
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.subject_profile == SEED_SUBJECT_PROFILE
    assert output.candidate_actions
    assert output.trace_payload["idle_eligible"] is True
    assert output.trace_payload["candidate_generated"] is True
    assert output.trace_payload["suppression_reason"] is None
    assert output.trace_payload["urge_score"] == output.policy_hint["urge_score"]


def test_seed_state_dependence_prefers_pending_commitment():
    state = _seed_state(curiosity=0.40, completion=0.75, caution=0.05)
    packet = _seed_packet(
        event_id="seed_user_001",
        event_type="user_event",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "pending_commitment": "finish_seed_contract",
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions[0]["action_type"] == "continue_pending_commitment"


def test_seed_feedback_writeback_does_not_generate_new_candidate():
    state = _seed_state(curiosity=0.35, completion=0.25, caution=0.15)
    packet = _seed_packet(
        event_id="seed_exec_001",
        event_type="exec_result",
        payload={
            "action_type": "host_reply",
            "status": "success",
            "target": "app.py",
            "observed_gain": 0.4,
            "details": {"host_terminal_status": "completed_verified"},
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions == []
    assert output.trace_payload["idle_eligible"] is False
    assert output.trace_payload["candidate_generated"] is False
    assert output.trace_payload["suppression_reason"] == "exec_result_pass"
    assert output.trace_payload["exec_result"]["status"] == "success"
    assert len(state.seed_state.recent_outcomes) == 1


def test_seed_trace_marks_urge_below_threshold_when_eligible_but_weak():
    state = _seed_state(curiosity=0.0, completion=0.0, caution=0.0)
    packet = _seed_packet(
        event_id="seed_idle_weak_001",
        event_type="idle_check",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions == []
    assert output.trace_payload["idle_eligible"] is True
    assert output.trace_payload["candidate_generated"] is False
    assert output.trace_payload["suppression_reason"] == "urge_below_threshold"
    assert output.trace_payload["urge_score"] == output.policy_hint["urge_score"]


def test_seed_trace_marks_no_affordance_when_nothing_actionable_is_visible():
    state = _seed_state(curiosity=0.85, completion=0.0, caution=0.0)
    packet = _seed_packet(
        event_id="seed_idle_empty_001",
        event_type="idle_check",
        payload={},
        runtime_summary={
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions == []
    assert output.trace_payload["idle_eligible"] is True
    assert output.trace_payload["candidate_generated"] is False
    assert output.trace_payload["suppression_reason"] == "no_affordance"


def test_seed_trace_marks_caution_gate_when_risk_is_too_high():
    state = _seed_state(curiosity=0.2, completion=0.2, caution=0.95)
    packet = _seed_packet(
        event_id="seed_idle_caution_001",
        event_type="idle_check",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions == []
    assert output.trace_payload["idle_eligible"] is True
    assert output.trace_payload["candidate_generated"] is False
    assert output.trace_payload["suppression_reason"] == "caution_gate"


def test_seed_trace_keeps_candidate_separate_from_execution():
    state = _seed_state(curiosity=0.85, completion=0.55, caution=0.05)
    packet = _seed_packet(
        event_id="seed_user_002",
        event_type="user_event",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={"resolved_target_path": "app.py", "active_task": False},
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions
    assert output.trace_payload["executed_action"] is None
    assert output.trace_payload["exec_result"] is None


def test_seed_continuity_lite_reuses_pending_commitment_across_turns():
    state = _seed_state(curiosity=0.45, completion=0.70, caution=0.05)
    first = _seed_packet(
        event_id="seed_user_003",
        event_type="user_event",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "pending_commitment": "finish_seed_contract",
            "active_task": False,
        },
    )
    process_update_packet(state, first)

    second = _seed_packet(
        event_id="seed_idle_002",
        event_type="idle_check",
        payload={},
        runtime_summary={"active_task": False},
    )
    output = process_update_packet(state, second)

    assert state.seed_state.focus_goal.pending_commitment == "finish_seed_contract"
    assert output.policy_hint["closure_bias"] is True


def test_seed_lite_recovery_after_failed_exec_result():
    state = _seed_state(curiosity=0.35, completion=0.25, caution=0.10)
    packet = _seed_packet(
        event_id="seed_exec_002",
        event_type="exec_result",
        payload={
            "action_type": "write_file",
            "status": "failure",
            "target": "app.py",
            "observed_gain": 0.0,
            "error": "permission denied",
        },
    )

    output = process_update_packet(state, packet)

    assert output.reflection_note is not None
    assert output.reflection_note.trigger == "exec_failure"
    assert state.seed_state.focus_goal.current_focus == "repair"
    assert state.seed_state.drives.repair > 0.40


def test_seed_permission_rings_require_approval_for_write_candidate():
    state = _seed_state(curiosity=0.0, completion=0.90, caution=0.0)
    packet = _seed_packet(
        event_id="seed_user_004",
        event_type="user_event",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "request_mode": "write",
            "active_task": False,
        },
    )

    output = process_update_packet(state, packet)

    assert output.candidate_actions
    assert output.candidate_actions[0]["action_type"] == "write_file"
    assert output.candidate_actions[0]["requires_approval"] is True
    assert output.policy_hint["governor_hint"]["status"] == "approval_gate"


def test_seed_exec_result_preserves_shadow_h1_for_tool_feedback_path():
    state = _seed_state(curiosity=0.35, completion=0.25, caution=0.10)
    shadow_key = build_h1_shadow_key("tool:read_artifact")
    state.self_model.counterfactual_success_by_action[shadow_key] = 0.18
    state.self_model.recent_correction_tags[shadow_key] = 1.0
    packet = _seed_packet(
        event_id="seed_exec_h1_001",
        event_type="exec_result",
        payload={
            "action_type": "read_artifact",
            "status": "failure",
            "target": "PROJECT_MEMORY.md",
            "observed_gain": 0.0,
            "error": "file not found",
            "details": {"tool": "read_artifact"},
        },
        runtime_summary={
            "h1_canonical_shadow": {
                "enabled": True,
                "shadow_only": True,
                "allowlisted": True,
                "source": "canonical_shadow",
            }
        },
        safety_context={"risk_level": "medium", "blocked": True},
    )

    output = process_update_packet(state, packet)

    assert output.trace_payload["shadow_h1"]["action_key"] == "tool:read_artifact"
    assert output.trace_payload["shadow_h1"]["would_guard"] is True
    assert output.confidence_meta["shadow_h1_enabled"] is True
    assert output.confidence_meta["shadow_h1_action_key"] == "tool:read_artifact"


def test_seed_user_event_does_not_emit_shadow_h1_without_tool_feedback_path():
    state = _seed_state(curiosity=0.40, completion=0.75, caution=0.05)
    shadow_key = build_h1_shadow_key("tool:read_artifact")
    state.self_model.counterfactual_success_by_action[shadow_key] = 0.18
    state.self_model.recent_correction_tags[shadow_key] = 1.0
    packet = _seed_packet(
        event_id="seed_user_h1_001",
        event_type="user_event",
        payload={"resolved_target_path": "app.py"},
        runtime_summary={
            "resolved_target_path": "app.py",
            "active_task": False,
            "h1_canonical_shadow": {
                "enabled": True,
                "shadow_only": True,
                "allowlisted": True,
                "source": "canonical_shadow",
            },
        },
    )

    output = process_update_packet(state, packet)

    assert "shadow_h1" not in output.trace_payload
    assert "shadow_h1_enabled" not in output.confidence_meta
