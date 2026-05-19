from __future__ import annotations

from app.openemotion_adapter import ProtoSelfAdapter
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.subject_system_v1_idle_scheduler import run_subject_system_v1_idle_scheduler
from openemotion.initiative_self import InitiativeSelfStore
from openemotion.self_model import SelfModelStore, create_default_self_model


def _seed_self_model_store(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(
        create_default_self_model("openemotion"),
        update_source="owner_bootstrap",
        trace_reference="trace:test_subject_system_v1_explicit_followup_bridge",
        confidence_class="high",
    )
    return store


def _state_with_chat(*, user_text: str, assistant_reply: str) -> RuntimeV2State:
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(user_text=user_text, chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply=assistant_reply, chat_act="light_chitchat")
    return state


class _CaptureInitiativeContextAdapter:
    def __init__(self) -> None:
        self.last_event = None

    def handle_event(self, event):
        self.last_event = event
        return {
            "schema_version": "proto_self.output.v2",
            "event_id": event["event_id"],
            "developmental_summary": {
                "cycle_id": "cycle_capture",
                "trigger": "idle",
                "gate_status": "allow",
                "background_thought_candidates": [],
                "background_thought_candidate_count": 0,
            },
            "developmental_gate": {"status": "allow"},
            "trace_payload": {
                "schema_version": "proto_self.trace.v2",
                "event_id": event["event_id"],
                "developmental": {"cycle_id": "cycle_capture"},
            },
        }


class _ReminderCandidateAdapter:
    def handle_event(self, event):
        initiative_context = dict(event["runtime_summary"].get("initiative_context") or {})
        continuity_ref = str(initiative_context.get("continuity_ref") or "")
        initiative_trigger = str(initiative_context.get("initiative_trigger") or "")
        idle_seconds = float(initiative_context.get("idle_seconds") or 0.0)
        if initiative_trigger == "bounded_reminder" and continuity_ref:
            return {
                "schema_version": "proto_self.output.v2",
                "event_id": event["event_id"],
                "developmental_summary": {
                    "cycle_id": "cycle_bounded_reminder",
                    "trigger": "idle",
                    "gate_status": "allow",
                    "background_thought_candidates": [],
                    "background_thought_candidate_count": 0,
                },
                "developmental_gate": {"status": "allow"},
                "response_tendency": {"preferred_mode": "respond"},
                "host_proactive_candidate": {
                    "candidate_id": "candidate_explicit_reminder",
                    "candidate_label": "governed_host_proactive_followup",
                    "continuity_basis": continuity_ref,
                    "host_lane_hint": "host_proactive_outbox",
                    "proposal_discipline": "proposal_only",
                    "behavioral_authority": "none",
                },
                "commitment_execution_snapshot": {
                    "active_commitments_count": 1,
                    "continuity_confidence": 0.82,
                    "recent_delivery_status": "sent",
                    "commitment_mode": "carry_forward",
                    "idle_seconds": idle_seconds,
                },
                "initiative_policy_hints": {
                    "host_proactive_mode": "candidate",
                    "continuity_mode": "stable",
                    "delivery_bias": "normal",
                },
                "trace_payload": {
                    "schema_version": "proto_self.trace.v2",
                    "event_id": event["event_id"],
                    "update_packet_hash": "hash_explicit_reminder",
                    "initiative_context": {
                        "initiative_trigger": initiative_trigger,
                        "continuity_ref": continuity_ref,
                        "idle_seconds": idle_seconds,
                    },
                },
            }
        return {
            "schema_version": "proto_self.output.v2",
            "event_id": event["event_id"],
            "developmental_summary": {
                "cycle_id": "cycle_no_candidate",
                "trigger": "idle",
                "gate_status": "allow",
                "background_thought_candidates": [],
                "background_thought_candidate_count": 0,
            },
            "developmental_gate": {"status": "allow"},
            "trace_payload": {
                "schema_version": "proto_self.trace.v2",
                "event_id": event["event_id"],
                "developmental": {"cycle_id": "cycle_no_candidate"},
            },
        }


def test_process_developmental_tick_infers_bounded_reminder_from_explicit_followup_chat(tmp_path) -> None:
    adapter = _CaptureInitiativeContextAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=adapter,
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_chat(
        user_text="我等下会回来继续这个话题，你之后可以提醒我继续。",
        assistant_reply="没问题，你忙完随时回来接着聊就行。",
    )
    base_ts = state.get_chat_state().last_activity_at or 0.0

    runtime.process_developmental_tick(
        session_id=state.session_id,
        turn_id="turn_explicit_followup",
        state=state,
        observation_source="direct_real",
        trigger="idle",
        idle_seconds=900.0,
        force_enable=True,
    )

    initiative_context = dict(adapter.last_event["runtime_summary"].get("initiative_context") or {})
    assert initiative_context["initiative_trigger"] == "bounded_reminder"
    assert initiative_context["pending_commitment_refs"]
    assert initiative_context["continuity_ref"].startswith("chat_followup:")
    assert initiative_context["chat_followup_source"] == "explicit_same_thread_followup_request"
    assert initiative_context["chat_followup_inferred"] is True
    assert initiative_context["explicit_followup_text_matched"] is True
    assert initiative_context["pending_commitment_source"] == "suppressed_for_explicit_followup"
    assert initiative_context["continuity_confidence"] == 0.72
    assert state.idle_seconds_since_chat_activity(now_ts=base_ts + 900.0) >= 900.0


def test_process_developmental_tick_infers_bounded_reminder_from_proactive_recontact_chat(
    tmp_path,
) -> None:
    adapter = _CaptureInitiativeContextAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=adapter,
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(
        user_text="你觉得AI实现自主性最大的瓶颈是什么？",
        chat_act="solicited_view",
    )
    state.finalize_chat_turn(
        assistant_reply="我觉得最大的瓶颈在长期目标对齐和动态环境适应能力。",
        chat_act="solicited_view",
    )
    state.prepare_chat_turn(
        user_text="待会儿你主动找我来聊吧",
        chat_act="light_chitchat",
    )
    state.finalize_chat_turn(
        assistant_reply="行，那你先去忙。等你有空了，我来找你接着聊。",
        chat_act="light_chitchat",
    )
    state.current_goal = "修改 test.html 配色"

    runtime.process_developmental_tick(
        session_id=state.session_id,
        turn_id="turn_proactive_recontact_followup",
        state=state,
        observation_source="direct_real",
        trigger="idle",
        idle_seconds=900.0,
        force_enable=True,
    )

    initiative_context = dict(adapter.last_event["runtime_summary"].get("initiative_context") or {})
    assert initiative_context["initiative_trigger"] == "bounded_reminder"
    assert initiative_context["continuity_ref"].startswith("chat_followup:")
    assert initiative_context["chat_followup_source"] == "explicit_same_thread_followup_request"
    assert initiative_context["chat_followup_inferred"] is True
    assert initiative_context["explicit_followup_text_matched"] is True
    assert initiative_context["pending_commitment_source"] == "suppressed_for_explicit_followup"
    assert "修改 test.html 配色" not in initiative_context["pending_commitment_refs"][0]


def test_process_developmental_tick_infers_bounded_reminder_from_proactive_direct_continue_chat(
    tmp_path,
) -> None:
    adapter = _CaptureInitiativeContextAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=adapter,
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(
        user_text="你觉得AI实现自主性最大的瓶颈是什么？",
        chat_act="solicited_view",
    )
    state.finalize_chat_turn(
        assistant_reply="我觉得最大的瓶颈在长期目标对齐和动态环境适应能力。",
        chat_act="solicited_view",
    )
    state.prepare_chat_turn(
        user_text="我回来了。我们继续聊 AI 自主性最大的瓶颈。你待会儿主动接着说一个具体看法，不要等我再问。",
        chat_act="thread_continue",
    )
    state.finalize_chat_turn(
        assistant_reply="AI 自主性目前最大的卡点不在算力，而是开放环境下的长尾意图对齐。",
        chat_act="thread_continue",
    )
    state.current_goal = "修改 test.html 配色"

    runtime.process_developmental_tick(
        session_id=state.session_id,
        turn_id="turn_proactive_direct_continue_followup",
        state=state,
        observation_source="direct_real",
        trigger="idle",
        idle_seconds=900.0,
        force_enable=True,
    )

    initiative_context = dict(adapter.last_event["runtime_summary"].get("initiative_context") or {})
    assert initiative_context["initiative_trigger"] == "bounded_reminder"
    assert initiative_context["continuity_ref"].startswith("chat_followup:")
    assert initiative_context["chat_followup_source"] == "explicit_same_thread_followup_request"
    assert initiative_context["chat_followup_inferred"] is True
    assert initiative_context["explicit_followup_text_matched"] is True
    assert initiative_context["pending_commitment_source"] == "suppressed_for_explicit_followup"
    assert "修改 test.html 配色" not in initiative_context["pending_commitment_refs"][0]


def test_process_developmental_tick_does_not_infer_market_alert_as_same_thread_followup(tmp_path) -> None:
    adapter = _CaptureInitiativeContextAdapter()
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=adapter,
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_chat(
        user_text="你能不能在比特币有大波动或者趋势变化的时候告诉我？",
        assistant_reply="我这边暂时没有自动盯盘和实时推送的功能。",
    )

    runtime.process_developmental_tick(
        session_id=state.session_id,
        turn_id="turn_market_alert",
        state=state,
        observation_source="direct_real",
        trigger="idle",
        idle_seconds=900.0,
        force_enable=True,
    )

    initiative_context = dict(adapter.last_event["runtime_summary"].get("initiative_context") or {})
    assert initiative_context["pending_commitment_refs"] == []
    assert initiative_context["continuity_ref"] == ""
    assert initiative_context["initiative_trigger"] == "runtime_review"
    assert initiative_context["chat_followup_source"] == ""
    assert initiative_context["chat_followup_inferred"] is False
    assert initiative_context["explicit_followup_text_matched"] is False


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_explicit_followup_chat(tmp_path) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=_ReminderCandidateAdapter(),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_chat(
        user_text="我等下会回来继续这个话题，你之后可以提醒我继续。",
        assistant_reply="没问题，你忙完随时回来接着聊就行。",
    )
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 900.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert pending is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "bounded_reminder"
    assert pending["subject_system_v1_summary"]["continuity_ref"].startswith("chat_followup:")
    assert pending["host_proactive_decision"]["reason"] == "stable_bounded_reminder"


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_proactive_recontact_chat_with_stale_goal(
    tmp_path,
) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=_ReminderCandidateAdapter(),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(
        user_text="你觉得AI实现自主性最大的瓶颈是什么？",
        chat_act="solicited_view",
    )
    state.finalize_chat_turn(
        assistant_reply="我觉得最大的瓶颈在长期目标对齐和动态环境适应能力。",
        chat_act="solicited_view",
    )
    state.prepare_chat_turn(
        user_text="待会儿你主动找我来聊吧",
        chat_act="light_chitchat",
    )
    state.finalize_chat_turn(
        assistant_reply="行，那你先去忙。等你有空了，我来找你接着聊。",
        chat_act="light_chitchat",
    )
    state.current_goal = "修改 test.html 配色"
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 900.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert pending is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "bounded_reminder"
    assert pending["subject_system_v1_summary"]["continuity_ref"].startswith("chat_followup:")
    assert "修改 test.html 配色" not in pending["subject_system_v1_summary"]["continuity_ref"]
    assert pending["host_proactive_decision"]["reason"] == "stable_bounded_reminder"


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_explicit_followup_chat_with_real_proto_self_adapter(
    tmp_path,
) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_chat(
        user_text="我等下会回来继续这个话题，你之后可以提醒我继续。",
        assistant_reply="没问题，你忙完随时回来接着聊就行。",
    )
    state.prepare_chat_turn(
        user_text="如果我中断了，你可以只发一个轻提醒，不要连续发。",
        chat_act="light_chitchat",
    )
    state.finalize_chat_turn(
        assistant_reply="好的，我记下了。如果你中途没回，我只发一次轻提醒，不会连续刷屏打扰。",
        chat_act="light_chitchat",
    )
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 900.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert result.reason == "ok"
    assert pending is not None
    subject_system_v1 = state.proto_self_context["subject_system_v1"]
    assert subject_system_v1["host_proactive_candidate"] is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "bounded_reminder"
    assert pending["subject_system_v1_summary"]["continuity_ref"].startswith("chat_followup:")
    assert pending["timing_contract"]["timing_mode"] == "delay_window"
    assert pending["timing_contract"]["timing_source"] == "subject_system_v1"
    assert subject_system_v1["host_proactive_candidate"]["continuity_confidence"] >= 0.65
    assert subject_system_v1["host_proactive_candidate"]["timing_advice"]["earliest_send_after_seconds"] < 900.0
    assert pending["host_proactive_decision"]["reason"] == "stable_bounded_reminder"


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_proactive_recontact_chat_with_real_proto_self_adapter(
    tmp_path,
) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(
        user_text="你觉得AI实现自主性最大的瓶颈是什么？",
        chat_act="solicited_view",
    )
    state.finalize_chat_turn(
        assistant_reply="我觉得最大的瓶颈在长期目标对齐和动态环境适应能力。",
        chat_act="solicited_view",
    )
    state.prepare_chat_turn(
        user_text="待会儿你主动找我来聊吧",
        chat_act="light_chitchat",
    )
    state.finalize_chat_turn(
        assistant_reply="行，那你先去忙。等你有空了，我来找你接着聊。",
        chat_act="light_chitchat",
    )
    state.current_goal = "修改 test.html 配色"
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 900.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert pending is not None
    subject_system_v1 = state.proto_self_context["subject_system_v1"]
    assert subject_system_v1["host_proactive_candidate"] is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "bounded_reminder"
    assert pending["subject_system_v1_summary"]["continuity_ref"].startswith("chat_followup:")
    assert "修改 test.html 配色" not in pending["subject_system_v1_summary"]["continuity_ref"]
    assert subject_system_v1["host_proactive_candidate"]["continuity_confidence"] >= 0.65
    assert pending["host_proactive_decision"]["reason"] == "stable_bounded_reminder"


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_proactive_direct_continue_chat_with_real_proto_self_adapter(
    tmp_path,
) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(
        user_text="你觉得AI实现自主性最大的瓶颈是什么？",
        chat_act="solicited_view",
    )
    state.finalize_chat_turn(
        assistant_reply="我觉得最大的瓶颈在长期目标对齐和动态环境适应能力。",
        chat_act="solicited_view",
    )
    state.prepare_chat_turn(
        user_text="我回来了。我们继续聊 AI 自主性最大的瓶颈。你待会儿主动接着说一个具体看法，不要等我再问。",
        chat_act="thread_continue",
    )
    state.finalize_chat_turn(
        assistant_reply="AI 自主性目前最大的卡点不在算力，而是开放环境下的长尾意图对齐。",
        chat_act="thread_continue",
    )
    state.current_goal = "修改 test.html 配色"
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 900.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert pending is not None
    subject_system_v1 = state.proto_self_context["subject_system_v1"]
    assert subject_system_v1["host_proactive_candidate"] is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "bounded_reminder"
    assert pending["subject_system_v1_summary"]["continuity_ref"].startswith("chat_followup:")
    assert "修改 test.html 配色" not in pending["subject_system_v1_summary"]["continuity_ref"]
    assert subject_system_v1["host_proactive_candidate"]["continuity_confidence"] >= 0.65
    assert pending["host_proactive_decision"]["reason"] == "stable_bounded_reminder"
