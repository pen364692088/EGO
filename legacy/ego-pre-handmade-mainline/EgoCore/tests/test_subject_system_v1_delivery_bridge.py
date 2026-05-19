from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.response_contract.output_check import OutputCheckVerdict
from app.runtime_v2.proactive_delivery import consume_pending_proactive_followup
from app.runtime_v2.proactive_identity import build_proactive_outreach_epoch, build_sent_text_fingerprint
from app.runtime_v2.state import RuntimeV2State
from app.runtime_v2.subject_system_v1_delivery_bridge import (
    build_pending_proactive_followup_from_subject_system_v1,
)


def _subject_system_payload(*, candidate_family: str = "commitment_followup", idle_seconds: float = 1200.0) -> dict:
    return {
        "response_tendency": {"preferred_mode": "respond"},
        "host_proactive_candidate": {
            "candidate_id": "candidate-1",
            "candidate_family": candidate_family,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
            "continuity_ref": "goal:followup",
            "continuity_confidence": 0.82,
            "idle_seconds": idle_seconds,
            "topic_summary": "AI 自主性的下一步",
            "topic_anchor_summary": "AI 自主性的下一步",
            "final_text_candidate": "关于“AI 自主性的下一步”，我会先把它拆成一个可验证的小动作，再看反馈是否真的推动了目标。",
            "language_hint": "zh",
            "style_intent": {"candidate_family": candidate_family, "question_policy": "zero_questions"},
            "content_grounding": {
                "topic_anchor_summary": "AI 自主性的下一步",
                "topic_summary": "AI 自主性的下一步",
                "source_ref": "goal:followup",
            },
            "generation_trace": {"source": "test_fixture", "method": "provided_final_text_candidate"},
        },
        "trace_payload": {
            "update_packet_hash": "hash-1",
        },
    }


def _decision(*, status: str = "candidate_ready", mode: str | None = "suggest") -> dict:
    return {
        "status": status,
        "mode": mode,
        "candidate_id": "candidate-1",
        "candidate_family": "commitment_followup",
        "reason": "stable_commitment_followup" if status == "candidate_ready" else "not_ready",
        "draft_text": "I can follow up on the open commitment with a bounded next step if you want.",
        "proposal_discipline": "proposal_only",
        "behavioral_authority": "none",
    }


def _append_outreach_marker(
    state: RuntimeV2State,
    *,
    topic_fingerprint: str | None = None,
    topic_cluster_ref: str | None = None,
    sent_text: str | None = None,
    sent_at: str | None = None,
) -> None:
    if state.proto_self_context is None:
        state.proto_self_context = {}
    history = list((state.proto_self_context or {}).get("proactive_outreach_history") or [])
    history.append(
        {
            "candidate_family": "thought_probe",
            "topic_fingerprint": topic_fingerprint,
            "topic_cluster_ref": topic_cluster_ref,
            "sent_text_fingerprint": build_sent_text_fingerprint(sent_text),
            "proactive_outreach_epoch": build_proactive_outreach_epoch(state),
            "recent_user_turn_count": len(list(state.get_chat_state().recent_user_turns or [])),
            "sent_at": sent_at or datetime.now(UTC).isoformat(),
        }
    )
    state.proto_self_context["proactive_outreach_history"] = history


def test_subject_system_v1_delivery_bridge_creates_pending_followup_for_ask() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(candidate_family="repair_review"),
        host_proactive_decision={**_decision(mode="ask"), "candidate_family": "repair_review"},
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    assert pending["initiative_verdict"]["response_plan"]["authority_source"] == (
        "runtime_v2.subject_system_v1_delivery_bridge"
    )
    assert pending["initiative_verdict"]["response_plan"]["metadata"]["reply_origin"] == "subject_system_v1_proactive"
    assert pending["initiative_verdict"]["response_plan"]["metadata"]["initiative_mode"] == "subject_system_v1_ask"

    delivery = consume_pending_proactive_followup(
        session_id=state.session_id,
        state=state,
    )
    assert delivery.status == "artifact_emitted"
    assert delivery.emitted_delivery is not None
    assert delivery.emitted_delivery["reply_origin"] == "subject_system_v1_proactive"
    assert delivery.emitted_delivery["initiative_mode"] == "subject_system_v1_ask"
    assert delivery.emitted_delivery["delivery_kind"] == "ask"


def test_subject_system_v1_delivery_bridge_creates_pending_followup_for_suggest() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(),
        host_proactive_decision=_decision(mode="suggest"),
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    assert pending["initiative_verdict"]["response_plan"]["metadata"]["initiative_mode"] == "subject_system_v1_suggest"

    delivery = consume_pending_proactive_followup(
        session_id=state.session_id,
        state=state,
    )
    assert delivery.status == "artifact_emitted"
    assert delivery.emitted_delivery is not None
    assert delivery.emitted_delivery["initiative_mode"] == "subject_system_v1_suggest"
    assert delivery.emitted_delivery["delivery_kind"] == "chat"


def test_subject_system_v1_delivery_bridge_holds_when_decision_not_ready() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(),
        host_proactive_decision=_decision(status="held", mode=None),
    )

    assert result.status == "held"
    assert result.reason.startswith("host_proactive_decision:")
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_with_active_task() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.mark_task_started("active task")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(),
        host_proactive_decision=_decision(),
    )

    assert result.status == "held"
    assert result.reason == "active_task_present"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_when_pending_exists() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.set_pending_proactive_followup(
        {
            "schema_version": "mvp12.pending_proactive_followup.v1",
            "delivery_status": "pending",
        }
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(),
        host_proactive_decision=_decision(),
    )

    assert result.status == "held"
    assert result.reason == "pending_followup_exists"


def test_subject_system_v1_delivery_bridge_holds_when_output_check_blocks(monkeypatch) -> None:
    state = RuntimeV2State(session_id="session:test")

    def _blocked_output_check(plan, runtime_state):
        return OutputCheckVerdict(
            passed=False,
            reason="forced_block",
            reply_text="",
            delivery_kind="chat",
            applied_authority="host_guard",
            reply_origin="subject_system_v1_proactive",
        )

    monkeypatch.setattr(
        "app.runtime_v2.subject_system_v1_delivery_bridge.apply_output_check",
        _blocked_output_check,
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1=_subject_system_payload(),
        host_proactive_decision=_decision(),
    )

    assert result.status == "held"
    assert result.reason == "output_check_blocked"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_preserves_thought_probe_metadata() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 的自主性怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="关键可能在于目标和反思。", chat_act="light_chitchat")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_001",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_001",
                "continuity_confidence": 0.74,
                "topic_source": "internal_reflection",
                "topic_summary": "自主性是否等于重构问题的能力",
                "topic_anchor_summary": "你觉得 AI 的自主性怎么做",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "conversational",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_001",
                "topic_fingerprint": "thought_topic:abc123",
                "topic_cluster_ref": "thought_cluster:def456",
                    "draft_text": "如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。",
                    "open_question": "那真正关键的是不是“能不能自己重构问题”，而不是单次做出选择？",
                    "final_text_candidate": (
                        "关于“你觉得 AI 的自主性怎么做”，我更在意自主性是否等于重构问题的能力；"
                        "如果它能持续改写当前问题的切口，就不只是单次选择。"
                    ),
                    "language_hint": "zh",
                    "style_intent": {"shape": "concrete_observation"},
                    "content_grounding": {
                        "topic_anchor_summary": "你觉得 AI 的自主性怎么做",
                        "topic_summary": "自主性是否等于重构问题的能力",
                    },
                    "generation_trace": {"source": "openemotion.test_fixture"},
                    "proactive_topic_permission": "long_term_allow",
                    "quiet_state": "normal",
                    "feedback_signal": "inferred_reengaged",
                "outreach_reason": "free_jump_internal_reflection",
                "timing_advice": {
                    "schema_version": "subject_system_v1.timing_advice.v1",
                    "timing_mode": "delay_window",
                    "earliest_send_after_seconds": 540.0,
                    "preferred_send_after_seconds": 720.0,
                    "latest_send_after_seconds": 1800.0,
                    "timing_basis": "mixed",
                    "timing_confidence": 0.7,
                },
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_001",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。 那真正关键的是不是“能不能自己重构问题”，而不是单次做出选择？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    assert pending["subject_system_v1_summary"]["candidate_family"] == "thought_probe"
    assert pending["subject_system_v1_summary"]["topic_source"] == "internal_reflection"
    assert pending["subject_system_v1_summary"]["topic_fingerprint"] == "thought_topic:abc123"
    assert pending["subject_system_v1_summary"]["topic_cluster_ref"] == "thought_cluster:def456"
    assert pending["subject_system_v1_summary"]["topic_anchor_summary"] == "你觉得 AI 的自主性怎么做"
    assert pending["subject_system_v1_summary"]["topic_anchor_source"] == "prior_user_turn"
    assert pending["subject_system_v1_summary"]["topic_anchor_kind"] == "substantive_topic"
    assert pending["subject_system_v1_summary"]["topic_binding_mode"] == "recent_topic"
    assert pending["subject_system_v1_summary"]["topic_sendability"] == "anchored_topic"
    assert pending["subject_system_v1_summary"]["topic_conversation_grade"] == "conversational"
    assert pending["subject_system_v1_summary"]["message_shape_hint"] == "thought_plus_question"
    assert pending["subject_system_v1_summary"]["source_ref"] == "internal_reflection:bg_hash_001"
    assert pending["subject_system_v1_summary"]["quiet_state"] == "normal"
    assert pending["subject_system_v1_summary"]["feedback_signal"] == "inferred_reengaged"
    assert pending["subject_system_v1_summary"]["outreach_reason"] == "free_jump_internal_reflection"
    assert "你觉得 AI 的自主性怎么做" in pending["initiative_verdict"]["draft_reply_text"]
    assert "自主性是否等于重构问题的能力" in pending["initiative_verdict"]["draft_reply_text"]
    assert "我刚想到一个相关切口。你想继续展开吗？" not in pending["initiative_verdict"]["draft_reply_text"]


def test_subject_system_v1_delivery_bridge_rewrites_meta_thought_probe_into_topic_bound_human_message(monkeypatch) -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="AI 实现自主性最大的瓶颈是什么？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="可能在于长期因果推理和对齐。", chat_act="light_chitchat")
    state.prepare_chat_turn(user_text="你有没有什么想法 可以告诉我", chat_act="solicited_view")
    state.finalize_chat_turn(assistant_reply="我更想先抓住那个底层前提。", chat_act="solicited_view")

    monkeypatch.setattr(
        "app.runtime_v2.subject_system_v1_delivery_bridge._generate_conversational_thought_probe_text",
        lambda **kwargs: "关于 AI 实现自主性，我更担心我们太快把长程规划当成答案，反而没拆清它依赖哪些前提。",
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_meta",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_meta",
                "continuity_confidence": 0.76,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:meta111",
                "topic_cluster_ref": "thought_cluster:meta111",
                "topic_anchor_summary": "AI 实现自主性最大的瓶颈是什么",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "meta_reflection_only",
                "topic_summary": "当前判断背后还有一个没有显式展开的前提",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_meta",
                "frame_anchor": "这条判断的前提",
                "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                "open_question": "支撑这条判断的前提到底是什么？",
                "final_text_candidate": "关于 AI 实现自主性，我更担心我们太快把长程规划当成答案，反而没拆清它依赖哪些前提。",
                "language_hint": "zh",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
                "outreach_reason": "topic_deepening_internal_reflection",
            },
            "trace_payload": {"update_packet_hash": "hash-meta"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_meta",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。 支撑这条判断的前提到底是什么？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    text = pending["initiative_verdict"]["draft_reply_text"]
    assert "AI 实现自主性" in text
    assert "表面上的判断先停住了" not in text
    assert "支撑这条判断的前提到底是什么" not in text
    assert "你有没有什么想法 可以告诉我" not in text


def test_subject_system_v1_delivery_bridge_holds_prompt_like_anchor_thought_probe() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你有没有什么想法 可以告诉我", chat_act="solicited_view")
    state.finalize_chat_turn(assistant_reply="你更想先听哪个角度？", chat_act="solicited_view")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_prompt_like",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_prompt_like",
                "continuity_confidence": 0.73,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:prompt111",
                "topic_cluster_ref": "thought_cluster:prompt111",
                "topic_anchor_summary": "你有没有什么想法 可以告诉我",
                "topic_anchor_source": "current_turn",
                "topic_anchor_kind": "prompt_like_request",
                "topic_binding_mode": "none",
                "topic_sendability": "meta_only",
                "topic_conversation_grade": "meta_reflection_only",
                "topic_summary": "当前判断背后还有一个没有显式展开的前提",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_prompt_like",
                "frame_anchor": "这条判断的前提",
                "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                "open_question": "支撑这条判断的前提到底是什么？",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-prompt-like"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_prompt_like",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。 支撑这条判断的前提到底是什么？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_anchor_prompt_like"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_meta_only_thought_probe_without_topic_anchor() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_meta_only",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_meta_only",
                "continuity_confidence": 0.71,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:meta222",
                "topic_cluster_ref": "thought_cluster:meta222",
                "topic_anchor_summary": "",
                "topic_anchor_source": "none",
                "topic_anchor_kind": "none",
                "topic_binding_mode": "none",
                "topic_sendability": "meta_only",
                "topic_conversation_grade": "meta_reflection_only",
                "topic_summary": "当前判断背后还有一个没有显式展开的前提",
                "message_shape_hint": "question_only",
                "source_ref": "internal_reflection:bg_hash_meta_only",
                "frame_anchor": "这条判断的前提",
                "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                "open_question": "支撑这条判断的前提到底是什么？",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-meta-only"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_meta_only",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。 支撑这条判断的前提到底是什么？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_meta_only_candidate"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_meta_reflection_rewrite_that_still_sounds_like_weird_meta(monkeypatch) -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="AI 实现自主性最大的瓶颈是什么？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="可能在于长期因果推理和对齐。", chat_act="light_chitchat")

    monkeypatch.setattr(
        "app.runtime_v2.subject_system_v1_delivery_bridge._generate_conversational_thought_probe_text",
        lambda **kwargs: "关于“AI 实现自主性最大的瓶颈是什么”，当前判断背后还有一个没有显式展开的前提。",
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_meta_bad",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_meta_bad",
                "continuity_confidence": 0.76,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:meta333",
                "topic_cluster_ref": "thought_cluster:meta333",
                "topic_anchor_summary": "AI 实现自主性最大的瓶颈是什么",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "meta_reflection_only",
                "topic_summary": "当前判断背后还有一个没有显式展开的前提",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_meta_bad",
                "frame_anchor": "这条判断的前提",
                "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                "open_question": "支撑这条判断的前提到底是什么？",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-meta-bad"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_meta_bad",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。 支撑这条判断的前提到底是什么？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_meta_reflection_not_conversational"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_live_style_abstract_ability_meta_line() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="AI 实现自主性最大的瓶颈是什么？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="可能在于长期因果推理和对齐。", chat_act="light_chitchat")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_live_meta",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_live_meta",
                "continuity_confidence": 0.76,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:live_meta",
                "topic_cluster_ref": "thought_cluster:live_meta",
                "topic_anchor_summary": "这种能力如何实现",
                "topic_anchor_source": "internal_reflection",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "conversational",
                "topic_summary": "",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_live_meta",
                "draft_text": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                "open_question": "系统什么时候才算真的在想要，而不是只在执行规则？",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-live-meta"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_live_meta",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": (
                "关于“这种能力如何实现”，想要可以被拆成可实现的机制，而不丢掉主体性。 "
                "系统什么时候才算真的在想要，而不是只在执行规则？"
            ),
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_meta_reflection_not_conversational"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_rewrites_weak_generic_live_no_send_with_bounded_fallback() -> None:
    state = RuntimeV2State(session_id="session:test")
    turns = [
        (
            "以后可以主动来找我，也可以自己找新话题，不用每次都问我。",
            "light_chitchat",
            "明白，以后我会更主动地开启话题或分享想法，不用每次都等你确认。",
        ),
        (
            "你觉得AI实现自主性最大的瓶颈是什么？",
            "light_chitchat",
            "按目前的技术路径看，我倾向于认为最大的瓶颈可能还是稳定可泛化的世界模型与长期目标对齐能力。",
        ),
        (
            "你有没有什么想法 可以告诉我",
            "solicited_view",
            "我觉得AI实现自主性最大的瓶颈在于缺乏内在的目标生成机制和真实世界反馈闭环。",
        ),
    ]
    for user_text, chat_act, assistant_reply in turns:
        state.prepare_chat_turn(user_text=user_text, chat_act=chat_act)
        state.finalize_chat_turn(assistant_reply=assistant_reply, chat_act=chat_act)

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_weak_live",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_weak_live",
                "continuity_confidence": 0.76,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:weak_live",
                "topic_cluster_ref": "thought_cluster:weak_live",
                "topic_anchor_summary": "这种能力如何实现",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "conversational",
                "raw_topic_anchor_summary": "这种能力如何实现",
                "effective_topic_anchor_summary": "你觉得AI实现自主性最大的瓶颈是什么",
                "topic_anchor_rebound_source": "recent_substantive_topic",
                "weak_generic_topic_anchor": True,
                "recent_topic_fallback_allowed": True,
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_weak_live",
                "draft_text": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                "open_question": "系统什么时候才算真的在想要，而不是只在执行规则？",
                "final_text_candidate": (
                    "关于“你觉得AI实现自主性最大的瓶颈是什么”，"
                    "我会把瓶颈落到目标生成和真实反馈闭环上；缺少这两点，系统很难把一次回答变成长期自我校准。"
                ),
                "language_hint": "zh",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-weak-live"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_weak_live",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": (
                "关于“这种能力如何实现”，想要可以被拆成可实现的机制，而不丢掉主体性。 "
                "系统什么时候才算真的在想要，而不是只在执行规则？"
            ),
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "pending_created"
    assert result.selected_candidate is not None
    assert result.selected_candidate["topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert result.selected_candidate["raw_topic_anchor_summary"] == "这种能力如何实现"
    assert not result.selected_candidate.get("recent_topic_conversational_fallback_applied")
    text = result.pending_proactive_followup["initiative_verdict"]["draft_reply_text"]
    assert "你觉得AI实现自主性最大的瓶颈是什么" in text
    assert "目标生成" in text
    assert "真实反馈闭环" in text
    assert "想要可以被拆成可实现的机制" not in text
    assert "系统什么时候才算真的在想要" not in text


def test_subject_system_v1_delivery_bridge_holds_rewrite_that_echoes_user_prompt(monkeypatch) -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="AI 实现自主性最大的瓶颈是什么？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="可能在于长期因果推理和对齐。", chat_act="light_chitchat")
    state.prepare_chat_turn(user_text="你有没有什么想法 可以告诉我", chat_act="solicited_view")
    state.finalize_chat_turn(assistant_reply="我更想先抓住那个底层前提。", chat_act="solicited_view")

    monkeypatch.setattr(
        "app.runtime_v2.subject_system_v1_delivery_bridge._generate_conversational_thought_probe_text",
        lambda **kwargs: "关于“你有没有什么想法 可以告诉我”，我更担心我们把长程规划当成答案。",
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_prompt_echo",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_prompt_echo",
                "continuity_confidence": 0.76,
                "topic_source": "internal_reflection",
                "topic_fingerprint": "thought_topic:meta444",
                "topic_cluster_ref": "thought_cluster:meta444",
                "topic_anchor_summary": "AI 实现自主性最大的瓶颈是什么",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "meta_reflection_only",
                "topic_summary": "当前判断背后还有一个没有显式展开的前提",
                "message_shape_hint": "thought_plus_question",
                "source_ref": "internal_reflection:bg_hash_prompt_echo",
                "frame_anchor": "这条判断的前提",
                "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                "open_question": "支撑这条判断的前提到底是什么？",
                "final_text_candidate": "关于“你有没有什么想法 可以告诉我”，我更担心我们把长程规划当成答案。",
                "language_hint": "zh",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-prompt-echo"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_prompt_echo",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。 支撑这条判断的前提到底是什么？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_question_echoes_user_prompt"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_verbalizes_bounded_reminder_from_topic_anchor_not_legacy_family_template() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 实现自主性需要怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="可能得从长期记忆和自我修正开始。", chat_act="light_chitchat")
    state.prepare_chat_turn(user_text="我等下会回来继续这个话题，你之后可以提醒我继续。", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="好。", chat_act="light_chitchat")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "candidate-1",
                "candidate_family": "bounded_reminder",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "chat_followup:abc123",
                "continuity_confidence": 0.78,
                "idle_seconds": 1200.0,
                "topic_anchor_summary": "AI 实现自主性",
                "final_text_candidate": "关于“AI 实现自主性”，我会把重点先放在长期记忆和自我修正这两个可检验环节。",
                "language_hint": "zh",
                "style_intent": {"candidate_family": "bounded_reminder", "question_policy": "zero_questions"},
                "content_grounding": {"topic_anchor_summary": "AI 实现自主性", "source_ref": "chat_followup:abc123"},
                "generation_trace": {"source": "test_fixture", "method": "provided_final_text_candidate"},
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "candidate-1",
            "candidate_family": "bounded_reminder",
            "reason": "stable_bounded_reminder",
            "draft_text": "",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    text = pending["initiative_verdict"]["draft_reply_text"]
    assert "AI 实现自主性" in text
    assert "I can surface a bounded reminder to preserve continuity here if you want." not in text
    assert "轻轻接回来" not in text
    assert "现在继续吗" not in text
    assert "你想" not in text
    assert "？" not in text


def test_subject_system_v1_delivery_bridge_bounded_reminder_direct_random_share_not_askback() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="随机的分享", chat_act="direct_share")
    state.finalize_chat_turn(
        assistant_reply="分享个小现象：人会对没完成的事情保持更多注意力。",
        chat_act="direct_share",
    )
    state.prepare_chat_turn(user_text="待会儿你主动找我来聊吧", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="行。", chat_act="light_chitchat")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "candidate-random",
                "candidate_family": "bounded_reminder",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "topic_anchor_summary": "随机的分享",
                "idle_seconds": 1200.0,
                "final_text_candidate": "关于“随机的分享”，我想补一个具体观察：未完成的事情更容易被记住，是因为注意力还没有彻底释放。",
                "language_hint": "zh",
                "style_intent": {"candidate_family": "bounded_reminder", "question_policy": "zero_questions"},
                "content_grounding": {"topic_anchor_summary": "随机的分享", "source_ref": "chat_followup:random"},
                "generation_trace": {"source": "test_fixture", "method": "provided_final_text_candidate"},
            },
            "trace_payload": {"update_packet_hash": "hash-random"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "candidate-random",
            "candidate_family": "bounded_reminder",
            "reason": "stable_bounded_reminder",
            "draft_text": "",
            "topic_anchor_summary": "随机的分享",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "pending_created"
    pending = state.get_pending_proactive_followup()
    assert pending is not None
    text = pending["initiative_verdict"]["draft_reply_text"]
    assert "随机的分享" in text
    assert "未完成的事情" in text
    assert "现在继续吗" not in text
    assert "你想" not in text
    assert "？" not in text


def test_subject_system_v1_delivery_bridge_retries_when_final_text_candidate_missing() -> None:
    state = RuntimeV2State(session_id="session:test")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "candidate-missing-text",
                "candidate_family": "bounded_reminder",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "chat_followup:missing",
                "continuity_confidence": 0.78,
                "idle_seconds": 1200.0,
            },
            "trace_payload": {"update_packet_hash": "hash-missing-text"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "candidate-missing-text",
            "candidate_family": "bounded_reminder",
            "reason": "stable_bounded_reminder",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "retry_later"
    assert result.reason == "final_text_candidate_missing"
    assert result.selected_candidate is not None
    assert result.selected_candidate["next_retry_after_seconds"] == 300.0
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_same_topic_cluster_until_user_returns() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 的自主性怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="关键可能在于目标和反思。", chat_act="light_chitchat")
    _append_outreach_marker(
        state,
        topic_fingerprint="thought_topic:dup001",
        topic_cluster_ref="thought_cluster:dup001",
        sent_text="如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。 那真正关键的是不是“能不能自己重构问题”，而不是单次做出选择？",
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_001",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_001",
                "continuity_confidence": 0.74,
                "source_ref": "internal_reflection:bg_hash_002",
                "topic_fingerprint": "thought_topic:dup001",
                "topic_cluster_ref": "thought_cluster:dup001",
                "draft_text": "如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。",
                "open_question": "那真正关键的是不是“能不能自己改写问题”，而不是单次做出选择？",
                "proactive_topic_permission": "long_term_allow",
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_001",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "我刚想到一个相关切口。要不要继续展开？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "duplicate_topic_cluster_before_user_return"
    assert result.selected_candidate is not None
    assert result.selected_candidate["topic_cluster_ref"] == "thought_cluster:dup001"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_duplicate_verbalization_until_user_returns() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 的自主性怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="关键可能在于目标和反思。", chat_act="light_chitchat")
    repeated_text = "关于“你觉得 AI 的自主性怎么做”，如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。"
    _append_outreach_marker(
        state,
        topic_fingerprint="thought_topic:old001",
        topic_cluster_ref="thought_cluster:old001",
        sent_text=repeated_text,
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_003",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_003",
                "continuity_confidence": 0.74,
                "source_ref": "internal_reflection:bg_hash_003",
                "topic_fingerprint": "thought_topic:new001",
                "topic_cluster_ref": "thought_cluster:new001",
                "topic_anchor_summary": "你觉得 AI 的自主性怎么做",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "draft_text": repeated_text,
                "open_question": "那真正关键的是 framing 的自我修正吗？",
                "proactive_topic_permission": "long_term_allow",
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_003",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": repeated_text,
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "duplicate_verbalization_before_user_return"
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_second_thought_probe_within_host_pacing_floor() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 的自主性怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="关键可能在于目标和反思。", chat_act="light_chitchat")
    now_dt = datetime(2026, 4, 23, 0, 0, tzinfo=UTC)
    _append_outreach_marker(
        state,
        topic_fingerprint="thought_topic:old002",
        topic_cluster_ref="thought_cluster:old002",
        sent_text="如果让系统先怀疑自己的 framing，它反而更接近真正的主动性。",
        sent_at=(now_dt - timedelta(minutes=5)).isoformat(),
    )

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        now_ts=now_dt.timestamp(),
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_004",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_004",
                "continuity_confidence": 0.74,
                "source_ref": "internal_reflection:bg_hash_004",
                "topic_fingerprint": "thought_topic:new002",
                "topic_cluster_ref": "thought_cluster:new002",
                "topic_anchor_summary": "AI 的自主性怎么做",
                "topic_anchor_source": "prior_user_turn",
                "topic_anchor_kind": "substantive_topic",
                "topic_binding_mode": "recent_topic",
                "topic_sendability": "anchored_topic",
                "topic_conversation_grade": "conversational",
                "draft_text": "如果系统默认把“上下文连续”当成主体连续，它可能会过早跳过真正的身份约束。",
                "open_question": "那主体连续和内容连续是不是两回事？",
                "final_text_candidate": (
                    "关于“AI 的自主性怎么做”，我会先区分上下文连续和主体连续；"
                    "如果两者被混在一起，系统可能会过早跳过身份约束。"
                ),
                "language_hint": "zh",
                "proactive_topic_permission": "long_term_allow",
                "quiet_state": "normal",
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_004",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "如果系统默认把“上下文连续”当成主体连续，它可能会过早跳过真正的身份约束。 那主体连续和内容连续是不是两回事？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "held"
    assert result.reason == "proactive_pacing_floor_active"
    assert result.selected_candidate is not None
    assert result.selected_candidate["host_pacing_floor_seconds"] == 20 * 60
    assert result.selected_candidate["host_pacing_floor_not_before_at"]
    assert state.get_pending_proactive_followup() is None


def test_subject_system_v1_delivery_bridge_holds_thought_probe_when_verbalization_is_template_like() -> None:
    state = RuntimeV2State(session_id="session:test")
    state.prepare_chat_turn(user_text="你觉得 AI 的自主性怎么做？", chat_act="light_chitchat")
    state.finalize_chat_turn(assistant_reply="关键可能在于目标和反思。", chat_act="light_chitchat")

    result = build_pending_proactive_followup_from_subject_system_v1(
        session_id=state.session_id,
        state=state,
        subject_system_v1={
            "response_tendency": {"preferred_mode": "respond"},
            "host_proactive_candidate": {
                "candidate_id": "thought_probe:bg_hash_005",
                "candidate_family": "thought_probe",
                "proposal_discipline": "proposal_only",
                "behavioral_authority": "none",
                "continuity_ref": "internal_reflection:bg_hash_005",
                "continuity_confidence": 0.74,
                "source_ref": "internal_reflection:bg_hash_005",
                "topic_fingerprint": "thought_topic:tmpl001",
                "topic_cluster_ref": "thought_cluster:tmpl001",
                "draft_text": "我刚想到一个相关切口。",
                "open_question": "你想继续展开吗？",
                "proactive_topic_permission": "long_term_allow",
            },
            "trace_payload": {"update_packet_hash": "hash-1"},
        },
        host_proactive_decision={
            "status": "candidate_ready",
            "mode": "suggest",
            "candidate_id": "thought_probe:bg_hash_005",
            "candidate_family": "thought_probe",
            "reason": "durable_thought_probe_ready",
            "draft_text": "我刚想到一个相关切口。 你想继续展开吗？",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
    )

    assert result.status == "retry_later"
    assert result.reason in {"template_or_askback_detected", "topic_thrown_back_to_user"}
    assert state.get_pending_proactive_followup() is None
