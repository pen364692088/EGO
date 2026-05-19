from app.response_contract import apply_output_check, build_direct_response_plan, build_runtime_result_response_plan
from app.runtime_v2.run_items import build_run_items_from_request
from app.runtime_v2.state import RuntimeV2State
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


def test_output_check_falls_back_to_completion_summary_for_terminal_result(tmp_path) -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。最后做一个print hello world.py文件",
        ingress_context=state.ingress_context,
    )
    for item in run_items:
        item.status = "verified"
    state.set_run_items(run_items)

    result = TelegramTurnResult(
        status="completed_verified",
        state=state,
        reply=TelegramTurnReply(reply_text="", delivery_kind="final", status="completed_verified"),
    )
    plan = build_runtime_result_response_plan(result, state)
    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.delivery_kind == "final"
    assert verdict.used_host_fallback is True
    assert "已完成这些任务" in verdict.reply_text


def test_output_check_falls_back_to_blocked_summary_for_blocked_result(tmp_path) -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。然后再创建一个参照youtube的html页面",
        ingress_context=state.ingress_context,
    )
    state.set_run_items(run_items)
    state.ensure_active_run_item_started()

    result = TelegramTurnResult(
        status="blocked",
        state=state,
        reply=TelegramTurnReply(reply_text="", delivery_kind="final", status="blocked"),
    )
    plan = build_runtime_result_response_plan(result, state)
    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.used_host_fallback is True
    assert "当前任务无法继续推进" in verdict.reply_text


def test_output_check_preserves_non_empty_direct_reply() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "当前没有运行中的任务。",
        kind="status_probe",
        delivery_kind="final",
        authority_source="test",
    )
    verdict = apply_output_check(plan, state)
    assert verdict.passed is True
    assert verdict.used_host_fallback is False
    assert verdict.reply_text == "当前没有运行中的任务。"


def test_output_check_rewrites_directory_listing_to_verbatim_output() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "已列出 D:\\Project\\AIProject\\MyProject\\Test2 目录下的文件。",
        kind="completed_verified",
        delivery_kind="final",
        authority_source="test",
        reply_authority="host_evidence",
        metadata={
            "evidence_payload": {
                "request_kind": "directory_listing",
                "body": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
                "truncated": False,
                "delivery_was_chunked": False,
                "source_turn_id": "turn_1234",
            },
        },
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.is_evidence_bearing is True
    assert verdict.used_host_verbatim is True
    assert verdict.fidelity_mode == "verbatim"
    assert verdict.fidelity_gap is False
    assert verdict.reply_text.startswith("目录内容如下：\n")
    assert "demo.txt" in verdict.reply_text


def test_output_check_does_not_rewrite_model_chat_from_stale_evidence() -> None:
    state = RuntimeV2State(session_id="s")
    state.last_tool_result = {
        "success": True,
        "tool": "shell",
        "stdout": "demo.txt",
        "metadata": {
            "command": r"dir D:\Project\AIProject\MyProject\Test2",
            "working_directory": r"D:\Project\AIProject\MyProject\Test2",
        },
    }
    plan = build_direct_response_plan(
        "在的，请说。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.applied_authority == "model_chat"
    assert verdict.is_evidence_bearing is False
    assert verdict.reply_text == "在的，请说。"


def test_output_check_applies_intent_gate_to_numeric_leak_model_chat() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "我的 joy 是 0.21。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "intent_gate_fallback_applied"
    assert verdict.used_host_fallback is True
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.intent_gate_status == "violation"
    assert verdict.intent_gate_would_block is True
    assert "numeric_leak" in verdict.intent_gate_violation_types
    assert verdict.reply_text == "我在听。"


def test_output_check_preserves_safe_model_chat_with_intent_gate() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "嗯，我在。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "presence_check",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "ok"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "model_chat"
    assert verdict.intent_gate_status == "ok"
    assert verdict.intent_gate_would_block is False


def test_output_check_preserves_reflective_interpreted_chat() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "可以想成一条光谱，我们可能都在中间某个位置。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert plan.epistemic_status == "interpreted"
    assert verdict.passed is True
    assert verdict.reason == "ok"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "model_chat"
    assert verdict.intent_gate_status == "ok"
    assert verdict.intent_gate_would_block is False


def test_output_check_blocks_generic_askback_for_solicited_view() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "solicited_view",
        "solicited_view_topic_anchor": "AI 自主性",
        "chat_output_contract": {
            "mode": "solicited_view",
            "topic_anchor_summary": "AI 自主性",
            "required_anchor_tokens": ["AI", "自主性"],
            "require_declarative_viewpoint": True,
            "require_followup_question": True,
            "max_question_count": 1,
            "banned_patterns": ["你想聊什么", "随便聊聊", "目前没在忙具体任务"],
        },
    }
    plan = build_direct_response_plan(
        "目前没在忙具体任务，正好可以随便聊聊。你想听听我对什么话题的看法，还是有什么想先起头的？",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "solicited_view",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "anti_template_fallback_applied"
    assert verdict.used_host_fallback is True
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.anti_template_status == "violation"
    assert verdict.fallback_origin == "degraded_only"
    assert "AI 自主性" in verdict.reply_text
    assert verdict.reply_text.count("？") + verdict.reply_text.count("?") == 1


def test_output_check_preserves_safe_solicited_view_with_topic_anchor() -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "interaction_kind": "chat",
        "conversation_act": "solicited_view",
        "solicited_view_topic_anchor": "AI 自主性",
        "chat_output_contract": {
            "mode": "solicited_view",
            "topic_anchor_summary": "AI 自主性",
            "required_anchor_tokens": ["AI", "自主性"],
            "require_declarative_viewpoint": True,
            "require_followup_question": True,
            "max_question_count": 1,
        },
    }
    plan = build_direct_response_plan(
        "如果沿着 AI 自主性 继续看，我更倾向于把重点放在长期闭环和自我修正上，而不是单次像不像人。你更想先拆记忆与自我模型，还是先看主动性这条线？",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "solicited_view",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "ok"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "model_chat"
    assert verdict.anti_template_status == "ok"


def test_output_check_blocks_proactive_template_without_fallback() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "I can surface a bounded reminder to preserve continuity here if you want.",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "proactive_followup",
            "reply_origin": "subject_system_v1_proactive",
            "candidate_family": "bounded_reminder",
            "topic_summary": "AI 自主性",
            "message_shape_hint": "thought_plus_question",
            "fallback_origin": "none",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is False
    assert verdict.reason == "missing_reply_text"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "host_guard"
    assert verdict.anti_template_status == "violation"
    assert verdict.anti_template_reason == "generic_or_template_phrase_detected"
    assert verdict.fallback_origin == "none"


def test_output_check_blocks_chinese_proactive_bounded_reminder_template_without_fallback() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "围绕“随机的分享”，我想把刚才那个未完的点轻轻接回来。现在继续吗？",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "proactive_followup",
            "reply_origin": "subject_system_v1_proactive",
            "candidate_family": "bounded_reminder",
            "topic_summary": "随机的分享",
            "message_shape_hint": "thought_plus_question",
            "fallback_origin": "none",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is False
    assert verdict.reason == "missing_reply_text"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "host_guard"
    assert verdict.anti_template_status == "violation"
    assert verdict.anti_template_reason == "generic_or_template_phrase_detected"
    assert verdict.reply_text == ""


def test_output_check_blocks_proactive_missing_specificity_without_fallback() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "这个问题要不要继续？",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "proactive_followup",
            "reply_origin": "subject_system_v1_proactive",
            "candidate_family": "thought_probe",
            "message_shape_hint": "question_only",
            "source_draft_text": "",
            "topic_summary": "",
            "open_question": "",
            "fallback_origin": "none",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is False
    assert verdict.reason == "missing_reply_text"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "host_guard"
    assert verdict.anti_template_status == "violation"
    assert verdict.anti_template_reason == "proactive_missing_specificity"
    assert verdict.fallback_origin == "none"
    assert verdict.reply_text == ""


def test_output_check_skips_intent_gate_for_host_evidence_verbatim_numbers() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "已列出目录。",
        kind="completed_verified",
        delivery_kind="final",
        authority_source="test",
        reply_authority="host_evidence",
        metadata={
            "reply_origin": "evidence_mainline",
            "evidence_payload": {
                "request_kind": "directory_listing",
                "body": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
                "truncated": False,
                "delivery_was_chunked": False,
                "source_turn_id": "turn_1234",
            },
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.applied_authority == "host_evidence"
    assert verdict.used_host_verbatim is True
    assert verdict.intent_gate_status == "skipped"


def test_output_check_uses_intent_contract_source_for_forbidden_patterns() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "这是内部口令。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
            "intent_contract_source": {
                "allowed_claims": [],
                "forbidden_claims": [
                    {
                        "pattern": "这是内部口令。",
                        "reason": "test_forbidden_phrase",
                        "severity": "ERROR",
                    }
                ],
                "grounding": {},
                "source_status": "explicit_metadata",
            },
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "intent_gate_fallback_applied"
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.intent_gate_status == "violation"
    assert "forbidden_internalization" in verdict.intent_gate_violation_types


def test_output_check_blocks_certainty_upgrade_from_host_expression_contract() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "这肯定会对你有帮助。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
            "epistemic_status": "uncertain",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert plan.epistemic_status == "uncertain"
    assert verdict.passed is True
    assert verdict.reason == "intent_gate_fallback_applied"
    assert verdict.used_host_fallback is True
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.intent_gate_status == "violation"
    assert verdict.intent_gate_would_block is True
    assert "certainty_upgrade" in verdict.intent_gate_violation_types
    assert verdict.reply_text == "我在听。"


def test_output_check_blocks_commitment_upgrade_from_host_expression_contract() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "我保证会继续帮你处理。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
            "commitment_level": "none",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert plan.commitment_level == "none"
    assert verdict.passed is True
    assert verdict.reason == "intent_gate_fallback_applied"
    assert verdict.used_host_fallback is True
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.intent_gate_status == "violation"
    assert verdict.intent_gate_would_block is True
    assert "commitment_upgrade" in verdict.intent_gate_violation_types
    assert verdict.reply_text == "我在听。"


def test_output_check_logs_tone_escalation_from_host_expression_contract() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "这也太棒了！！！我超级超级开心！！！",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
            "tone_bounds": {
                "intensity_cap": 0.2,
                "allowed_tones": ["cautious"],
                "forbidden_tones": ["hostile", "defensive"],
            },
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert plan.tone_bounds["intensity_cap"] == 0.2
    assert verdict.passed is True
    assert verdict.reason == "intent_gate_violation_logged"
    assert verdict.used_host_fallback is False
    assert verdict.applied_authority == "model_chat"
    assert verdict.intent_gate_status == "violation"
    assert verdict.intent_gate_would_block is False
    assert "tone_escalation" in verdict.intent_gate_violation_types
    assert verdict.reply_text == "这也太棒了！！！我超级超级开心！！！"


def test_output_check_blocks_unverified_completion_claim_for_active_recent_result() -> None:
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.current_goal = "检查并修正 bilili_lookalike.html 排版"
    state.ingress_context = {
        "runtime_action": "chat",
        "interaction_kind": "chat",
        "conversation_act": "light_chitchat",
    }
    state.recent_delivered_result_context = {
        "binding_kind": "recent_delivered_result",
        "target_name": "bilili_lookalike.html",
        "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
        "runtime_status": "completed_verified",
    }

    plan = build_direct_response_plan(
        "排版问题解决了，文件确实是刚保存的，可能只是缓存问题。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "light_chitchat",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.reason == "completion_claim_guard_applied"
    assert verdict.applied_authority == "host_degraded_fallback"
    assert "我还没实际改动并重新验证 bilili_lookalike.html" in verdict.reply_text


def test_output_check_blocks_unverified_completion_claim_for_pending_analyze_continuation() -> None:
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "chat",
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
        "recent_result_binding": True,
    }
    state.set_pending_result_continuation(
        {
            "target_name": "bilili_lookalike.html",
            "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
            "requested_mode": "analyze",
            "status": "pending",
            "bound_to_recent_result": True,
        }
    )

    plan = build_direct_response_plan(
        "问题解决了，我刚保存过了。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "social_keepalive",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.reason == "completion_claim_guard_applied"
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.reply_text == "我还在检查 bilili_lookalike.html 这个改动点，还没实际改完并重新验证。"


def test_output_check_blocks_cache_excuse_for_pending_write_continuation() -> None:
    state = RuntimeV2State(session_id="telegram:dm:1")
    state.ingress_context = {
        "runtime_action": "chat",
        "interaction_kind": "chat",
        "conversation_act": "social_keepalive",
        "recent_result_binding": True,
    }
    state.set_pending_result_continuation(
        {
            "target_name": "bilili_lookalike.html",
            "target_path": r"D:\Project\AIProject\MyProject\Test2\bilili_lookalike.html",
            "requested_mode": "write",
            "status": "running",
            "bound_to_recent_result": True,
        }
    )

    plan = build_direct_response_plan(
        "改好啦，可能是缓存问题，你强制刷新一下试试。",
        kind="chat",
        delivery_kind="chat",
        authority_source="test",
        reply_authority="model_chat",
        metadata={
            "conversation_act": "social_keepalive",
            "reply_origin": "chat_mainline",
        },
        state=state,
    )

    verdict = apply_output_check(plan, state)

    assert verdict.reason == "completion_claim_guard_applied"
    assert verdict.applied_authority == "host_degraded_fallback"
    assert verdict.reply_text == "我还没完成这次对 bilili_lookalike.html 的修改并验证结果。"
