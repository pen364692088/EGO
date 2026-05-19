from __future__ import annotations

from app.openemotion_adapter import ProtoSelfAdapter
from app.runtime_v2.proto_self_runtime import RuntimeV2ProtoSelfRuntime, _build_initiative_context
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.subject_system_v1_idle_scheduler import run_subject_system_v1_idle_scheduler
from openemotion.initiative_self import InitiativeSelfStore
from openemotion.self_model import SelfModelStore, create_default_self_model


def _seed_self_model_store(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    store.save(
        create_default_self_model("openemotion"),
        update_source="owner_bootstrap",
        trace_reference="trace:test_subject_system_v1_thought_probe",
        confidence_class="high",
    )
    return store


def _state_with_autonomy_chat(
    *,
    proactive_topic_permission: str | None = None,
    quiet_state: str | None = None,
    feedback_signal: str | None = None,
    outreach_aggression_mode: str | None = None,
    outreach_feedback_adaptation: str | None = None,
) -> RuntimeV2State:
    state = RuntimeV2State(session_id="telegram:dm:test")
    state.prepare_chat_turn(user_text="你觉得AI实现自主性需要怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(
        assistant_reply="AI要实现真正的自主性，可能得从模式匹配转向能在环境里闭环试错。",
        chat_act="light_chitchat",
    )
    state.prepare_chat_turn(user_text="如果核心不是选择，而是自己重构问题的能力呢？", chat_act="light_chitchat")
    state.finalize_chat_turn(
        assistant_reply="那关键可能就不是一次决策，而是能不能持续改写自己的问题框架。",
        chat_act="light_chitchat",
    )
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
        "proactive_topic_permission": proactive_topic_permission,
        "quiet_state": quiet_state,
        "feedback_signal": feedback_signal,
        "outreach_aggression_mode": outreach_aggression_mode,
        "outreach_feedback_adaptation": outreach_feedback_adaptation,
    }
    return state


def _state_with_live_no_send_topic_anchor_regression() -> RuntimeV2State:
    state = RuntimeV2State(session_id="telegram:dm:test")
    turns = [
        ("你好", "light_chitchat", "你好，我在。今天有什么想聊的，或者需要协助的直接说就行。"),
        (
            "以后可以主动来找我，也可以自己找新话题，不用每次都问我。",
            "light_chitchat",
            "我在。刚才聊天生成出了点问题，你可以继续说。",
        ),
        (
            "你觉得AI实现自主性最大的瓶颈是什么？",
            "light_chitchat",
            "最大的瓶颈在于缺乏对复杂现实环境的长期因果推理能力。",
        ),
        (
            "以后可以主动来找我，也可以自己找新话题，不用每次都问我。",
            "light_chitchat",
            "收到，以后我会更主动地开启对话或分享新话题，不再总等你先开口。",
        ),
        (
            "你有没有什么想法 可以告诉我",
            "solicited_view",
            "我认为最大的瓶颈在于开放环境下的长程目标规划与自我纠错能力。",
        ),
    ]
    for user_text, chat_act, assistant_reply in turns:
        state.prepare_chat_turn(user_text=user_text, chat_act=chat_act)
        state.finalize_chat_turn(assistant_reply=assistant_reply, chat_act=chat_act)
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "solicited_view",
        "proactive_topic_permission": "long_term_allow",
        "outreach_aggression_mode": "high_exploration",
        "outreach_feedback_adaptation": "enabled",
        "quiet_state": "normal",
    }
    return state


def _state_with_live_bare_continue_no_send_regression() -> RuntimeV2State:
    state = RuntimeV2State(session_id="telegram:dm:test")
    turns = [
        (
            "以后可以主动来找我，也可以自己找新话题，不用每次都问我。",
            "light_chitchat",
            "刚才聊天生成超时了，这轮先走降级回复。你可以继续说。",
        ),
        (
            "以后可以主动来找我，也可以自己找新话题，不用每次都问我。",
            "light_chitchat",
            "明白了，以后我会更主动些，想到新话题直接跟你聊。",
        ),
        (
            "你觉得AI实现自主性最大的瓶颈是什么？",
            "light_chitchat",
            "我觉得最大的瓶颈还是复杂环境下的可靠泛化与价值对齐。",
        ),
        (
            "你有没有什么想法 可以告诉我",
            "solicited_view",
            "AI现在能生成计划，但很难在脱离人类持续干预的情况下自主验证结果。",
        ),
        (
            "继续",
            "thread_continue",
            "既然你提到继续，那我们就顺着之前的节奏往下展开。",
        ),
    ]
    for user_text, chat_act, assistant_reply in turns:
        state.prepare_chat_turn(user_text=user_text, chat_act=chat_act)
        state.finalize_chat_turn(assistant_reply=assistant_reply, chat_act=chat_act)
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "thread_continue",
        "proactive_topic_permission": "long_term_allow",
        "outreach_aggression_mode": "high_exploration",
        "outreach_feedback_adaptation": "enabled",
        "quiet_state": "normal",
    }
    return state


def test_subject_system_v1_idle_scheduler_creates_pending_followup_from_thought_probe_with_real_proto_self_adapter(
    tmp_path,
) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_autonomy_chat(proactive_topic_permission="long_term_allow")
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 1200.0,
    )

    pending = state.get_pending_proactive_followup()
    assert result.status == "pending_created"
    assert pending is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "thought_probe"
    assert pending["subject_system_v1_summary"]["topic_source"] == "internal_reflection"
    assert pending["subject_system_v1_summary"]["source_ref"].startswith("internal_reflection:")
    assert pending["subject_system_v1_summary"]["message_shape_hint"] in {
        "thought_plus_question",
        "question_only",
        "short_view",
    }
    assert pending["host_proactive_decision"]["reason"] == "durable_thought_probe_ready"
    assert pending["timing_contract"]["timing_mode"] == "delay_window"
    subject_system_v1 = state.proto_self_context["subject_system_v1"]
    assert subject_system_v1["host_proactive_candidate"]["candidate_family"] == "thought_probe"
    assert subject_system_v1["host_proactive_candidate"]["proactive_topic_permission"] == "long_term_allow"


def test_subject_system_v1_idle_scheduler_skips_permission_turn_as_thought_probe_anchor(tmp_path) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_live_no_send_topic_anchor_regression()
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 1200.0,
    )

    assert result.observation["topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert result.observation["topic_anchor_summary"] != "以后可以主动来找我，也可以自己找新话题，不用每次都问我"
    assert result.observation["topic_anchor_source"] == "prior_user_turn"
    assert result.observation["topic_anchor_kind"] == "substantive_topic"


def test_subject_system_v1_idle_scheduler_skips_bare_continue_as_thought_probe_anchor(tmp_path) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_live_bare_continue_no_send_regression()
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 1200.0,
    )

    assert result.observation["topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert result.observation["topic_anchor_summary"] != "继续"
    assert result.observation["topic_anchor_source"] == "prior_user_turn"
    assert result.observation["topic_anchor_kind"] == "substantive_topic"


def test_subject_system_v1_idle_scheduler_holds_thought_probe_without_long_term_permission(tmp_path) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_autonomy_chat(proactive_topic_permission=None)
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 1200.0,
    )

    assert result.status == "held"
    assert result.reason == "host_proactive_decision:missing_candidate"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_idle_scheduler_holds_thought_probe_when_paused(tmp_path) -> None:
    runtime = RuntimeV2ProtoSelfRuntime(
        adapter=ProtoSelfAdapter(mirror_dir=tmp_path / "mirror"),
        self_model_store=_seed_self_model_store(tmp_path),
        initiative_self_store=InitiativeSelfStore(base_dir=tmp_path),
    )
    state = _state_with_autonomy_chat(
        proactive_topic_permission="long_term_allow",
        quiet_state="paused",
        outreach_aggression_mode="high_exploration",
        outreach_feedback_adaptation="enabled",
    )
    base_ts = state.get_chat_state().last_activity_at or 0.0

    result = run_subject_system_v1_idle_scheduler(
        session_id=state.session_id,
        state=state,
        proto_self_runtime=runtime,
        now_ts=base_ts + 1200.0,
    )

    assert result.status == "held"
    assert result.reason == "host_proactive_decision:missing_candidate"
    assert state.get_pending_proactive_followup() is None


def test_initiative_context_infers_cooling_only_after_proactive_send() -> None:
    state = _state_with_autonomy_chat(
        proactive_topic_permission="long_term_allow",
        quiet_state="normal",
        outreach_aggression_mode="high_exploration",
        outreach_feedback_adaptation="enabled",
    )
    baseline_turn_count = len(list(state.get_chat_state().recent_user_turns or []))
    state.proto_self_context = {
        "last_sent_proactive": {
            "candidate_family": "thought_probe",
            "source_ref": "internal_reflection:bg_hash_prev",
            "recent_user_turn_count": baseline_turn_count,
        }
    }
    state.prepare_chat_turn(user_text="嗯", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="收到。", chat_act="light_chitchat")
    state.prepare_chat_turn(user_text="好", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="明白。", chat_act="light_chitchat")

    initiative_context = _build_initiative_context(state, idle_seconds_override=1200.0)

    assert initiative_context["feedback_signal"] == "inferred_cooling"
    assert initiative_context["quiet_state"] == "reduced"
