from __future__ import annotations

from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.subject_system_v1_idle_scheduler import run_subject_system_v1_idle_scheduler


def _state_with_chat() -> RuntimeV2State:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="我觉得是有了OS的操作员的感觉。", chat_act="light_chitchat")
    state.finalize_chat_turn(
        assistant_reply="这个比喻很妙——不是系统自己在跑，而是有人在“用”它。",
        chat_act="light_chitchat",
    )
    return state


class _CurrentLaneRuntime:
    def process_developmental_tick(self, **kwargs):
        return {
            "developmental_summary": {
                "cycle_id": "cycle-1",
                "trigger": "idle",
                "gate_status": "allow",
            },
            "developmental_gate": {"status": "allow"},
            "subject_system_v1": {
                "response_tendency": {"preferred_mode": "respond"},
                "host_proactive_candidate": {
                    "candidate_id": "candidate-1",
                    "candidate_family": "commitment_followup",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                    "continuity_ref": "goal:followup",
                    "continuity_confidence": 0.81,
                    "idle_seconds": kwargs.get("idle_seconds", 0.0),
                    "final_text_candidate": (
                        "关于刚才 OS 操作员的比喻，我想接一个具体点："
                        "如果系统只是被使用，它还不是主体；关键在于能不能自己维持下一步判断。"
                    ),
                    "language_hint": "zh",
                    "style_intent": {"shape": "concrete_observation"},
                    "content_grounding": {
                        "topic_anchor_summary": "OS的操作员的感觉",
                        "grounding_status": "candidate_grounded",
                    },
                    "generation_trace": {"source": "openemotion.test_fixture"},
                },
                "trace_payload": {"update_packet_hash": "hash-1"},
            },
            "host_proactive_decision": {
                "status": "candidate_ready",
                "mode": "suggest",
                "candidate_id": "candidate-1",
                "candidate_family": "commitment_followup",
                "reason": "stable_commitment_followup",
                "draft_text": "I can follow up on the open commitment with a bounded next step if you want.",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
            },
        }


class _LegacyOnlyRuntime:
    def process_developmental_tick(self, **kwargs):
        return {
            "developmental_summary": {
                "cycle_id": "cycle-legacy",
                "trigger": "idle",
                "gate_status": "allow",
            },
            "developmental_gate": {"status": "allow"},
        }


class _NoCandidateRuntime:
    def process_developmental_tick(self, **kwargs):
        return {
            "developmental_summary": {
                "cycle_id": "cycle-held",
                "trigger": "idle",
                "gate_status": "allow",
            },
            "developmental_gate": {"status": "allow"},
            "subject_system_v1": {
                "response_tendency": {"preferred_mode": "respond"},
                "trace_payload": {
                    "initiative_context": {
                        "initiative_trigger": "bounded_reminder",
                        "continuity_ref": "chat_followup:abc123",
                        "chat_followup_source": "explicit_same_thread_followup_request",
                        "pending_commitment_source": "suppressed_for_explicit_followup",
                    }
                },
            },
            "host_proactive_decision": {
                "status": "held",
                "reason": "missing_candidate",
            },
        }


def test_subject_system_v1_idle_scheduler_creates_pending_followup() -> None:
    state = _state_with_chat()
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=_CurrentLaneRuntime(),
        now_ts=base_ts + 900.0,
    )

    assert result.status == "pending_created"
    assert result.to_dict()["scheduler_source"] == "subject_system_v1"
    assert result.to_dict()["recent_user_turns_count"] == 1
    assert result.to_dict()["recent_assistant_replies_count"] == 1
    assert result.to_dict()["candidate_family"] == "commitment_followup"
    assert result.to_dict()["continuity_ref"] == "goal:followup"
    assert state.get_pending_proactive_followup() is not None
    scheduler_record = next(
        item["content"]
        for item in reversed(state.history)
        if item["role"] == "subject_system_v1_proactive_scheduler"
    )
    assert scheduler_record["status"] == "pending_created"
    assert scheduler_record["candidate_family"] == "commitment_followup"
    assert scheduler_record["recent_user_turns_count"] == 1


def test_subject_system_v1_idle_scheduler_holds_when_current_lane_explicitly_disabled() -> None:
    state = _state_with_chat()
    state.ingress_context = {"subject_system_v1_proactive_disabled": True}

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=_CurrentLaneRuntime(),
        now_ts=(state.get_chat_state().last_activity_at or 0.0) + 900.0,
    )

    assert result.status == "held"
    assert result.reason == "current_lane_disabled"


def test_subject_system_v1_idle_scheduler_holds_when_current_lane_surface_missing() -> None:
    state = _state_with_chat()

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=_LegacyOnlyRuntime(),
        now_ts=(state.get_chat_state().last_activity_at or 0.0) + 900.0,
    )

    assert result.status == "held"
    assert result.reason == "subject_system_v1_missing"


def test_subject_system_v1_idle_scheduler_records_structured_held_reason() -> None:
    state = _state_with_chat()

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=_NoCandidateRuntime(),
        now_ts=(state.get_chat_state().last_activity_at or 0.0) + 900.0,
    )

    assert result.status == "held"
    assert result.reason == "host_proactive_decision:missing_candidate"
    payload = result.to_dict()
    assert payload["chat_followup_inferred"] is True
    assert payload["initiative_trigger"] == "bounded_reminder"
    assert payload["continuity_ref"] == "chat_followup:abc123"
    assert payload["pending_commitment_source"] == "suppressed_for_explicit_followup"
    scheduler_record = next(
        item["content"]
        for item in reversed(state.history)
        if item["role"] == "subject_system_v1_proactive_scheduler"
    )
    assert scheduler_record["reason"] == "host_proactive_decision:missing_candidate"
    assert scheduler_record["chat_followup_inferred"] is True
    assert scheduler_record["continuity_ref"] == "chat_followup:abc123"
