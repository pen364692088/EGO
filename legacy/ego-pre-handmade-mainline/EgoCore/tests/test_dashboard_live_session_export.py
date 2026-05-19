from __future__ import annotations

from app.dashboard.live_session_export import build_live_session_export


def test_build_live_session_export_summarizes_mixed_live_window() -> None:
    payload = {
        "session": {
            "session_id": "dashboard:test:default",
            "session_name": "default",
        },
        "session_revision": 8,
        "session_state": {
            "task_status": "chat",
            "waiting_for_user_input": False,
            "proto_self_scope": {
                "state_scope": "experiment",
                "experiment_id": "dashboard_local:test:default",
                "owner": "dashboard_local",
            },
            "proto_self": {"available": True},
        },
        "transcript": [
            {"message_id": "msg_00001", "role": "user", "text": "你好啊"},
            {"message_id": "msg_00002", "role": "assistant", "status": "chat", "delivery_kind": "chat", "text": "你好啊！"},
            {"message_id": "msg_00003", "role": "user", "text": "你有没有什么想法?"},
            {"message_id": "msg_00004", "role": "assistant", "status": "chat", "delivery_kind": "chat", "text": "我有几个想法。"},
        ],
        "debug_history": {
            "msg_00002": {
                "request": {"source_kind": "dashboard_local", "user_input": "你好啊"},
                "ingress": {"runtime_action": "chat", "conversation_act": "light_chitchat", "parser_source": "semantic_parser"},
                "subject_gate": {"ingress": {"ok": True, "reason": "ok"}},
                "proto_self": {
                    "available": True,
                    "response_tendency": {
                        "preferred_mode": "ask",
                        "preferred_tone": "supportive",
                        "suggested_next_step": "continue_dialogue",
                    },
                },
                "response_plan": {
                    "reply_authority": "model_chat",
                    "metadata": {
                        "degraded": False,
                        "chat_expression_hint": {"reply_mode": "normal", "tone_profile": "supportive"},
                        "response_tendency_summary": {"preferred_mode": "ask", "preferred_tone": "supportive"},
                    },
                },
                "output_check": {"reply_origin": "chat_mainline"},
                "delivery": {"delivery_kind": "chat"},
            },
            "msg_00004": {
                "request": {"source_kind": "dashboard_local", "user_input": "你有没有什么想法?"},
                "ingress": {"runtime_action": "execute_task", "conversation_act": None, "parser_source": "semantic_parser"},
                "subject_gate": {"ingress": {"ok": True, "reason": "ok"}},
                "proto_self": {"available": True},
                "response_plan": {"reply_authority": "model_chat", "metadata": {}},
                "output_check": {"reply_origin": "chat_mainline"},
                "delivery": {"delivery_kind": "chat"},
            },
        },
    }

    report = build_live_session_export(
        payload,
        base_url="http://127.0.0.1:8787",
        input_provenance_by_message_id={
            "msg_00002": {
                "source_kind": "repo_authored_control",
                "source_label": "repo control:greeting",
                "derivation": "native",
                "source_ref": "internal:repo_authored_control:greeting",
                "normalization_applied": False,
            },
            "msg_00004": {
                "source_kind": "generated",
                "source_label": "local generated ordinary-chat template",
                "derivation": "generated",
                "source_ref": "internal:generated_ordinary_chat_v1:0",
                "normalization_applied": False,
            },
        },
    )

    assert report["claim_ceiling"] == "single_entry_live_window_observation"
    assert report["entrypoint_contract"]["entrypoint"] == "dashboard_chat"
    assert report["fetch"]["session_id"] == "dashboard:test:default"
    assert report["summary"]["assistant_turn_count"] == 2
    assert report["summary"]["ordinary_chat_turn_count"] == 1
    assert report["summary"]["execute_task_turn_count"] == 1
    assert report["summary"]["subject_gate_ok_count"] == 2
    assert report["summary"]["oe_available_count"] == 2
    assert report["summary"]["mainline_candidate_count"] == 1
    assert report["summary"]["host_only_count"] == 0
    assert report["summary"]["source_counts"] == {
        "repo_authored_control": 1,
        "generated": 1,
    }
    assert report["summary"]["verdict"] == "ordinary_chat_mainline_observed"
    assert report["tendency_summary"]["signal_turn_count"] == 1
    assert report["tendency_summary"]["non_ask_tendency_count"] == 0
    assert report["tendency_summary"]["preferred_mode_counts"] == {"ask": 1}
    assert report["tendency_summary"]["reply_mode_counts"] == {"normal": 1}
    assert report["tendency_summary"]["revision_counter_available"] is False
    assert report["tendency_summary"]["verdict"] == "ask_only_tendency_observed"
    assert report["assistant_turns"][0]["input_provenance"]["source_kind"] == "repo_authored_control"
    assert report["assistant_turns"][0]["mainline_candidate"] is True
    assert report["assistant_turns"][0]["preferred_mode"] == "ask"
    assert report["assistant_turns"][0]["reply_mode"] == "normal"
    assert report["assistant_turns"][0]["response_tendency_summary"]["preferred_tone"] == "supportive"
    assert report["assistant_turns"][1]["runtime_action"] == "execute_task"


def test_build_live_session_export_marks_zero_gate_window_as_not_observed() -> None:
    payload = {
        "session": {
            "session_id": "dashboard:test:zero-gate",
            "session_name": "zero-gate",
        },
        "session_revision": 3,
        "session_state": {
            "task_status": "chat",
            "waiting_for_user_input": False,
            "proto_self_scope": {
                "state_scope": "experiment",
                "experiment_id": "dashboard_local:test:zero-gate",
                "owner": "dashboard_local",
            },
            "proto_self": {"available": False},
        },
        "transcript": [
            {"message_id": "msg_10001", "role": "user", "text": "hi"},
            {"message_id": "msg_10002", "role": "assistant", "status": "chat", "delivery_kind": "chat", "text": "hello"},
        ],
        "debug_history": {
            "msg_10002": {
                "request": {"source_kind": "dashboard_local", "user_input": "hi"},
                "ingress": {"runtime_action": "chat", "conversation_act": "light_chitchat", "parser_source": "semantic_parser"},
                "subject_gate": {"ingress": {"ok": False, "reason": "subject_gate_blocked"}},
                "proto_self": {"available": False},
                "response_plan": {
                    "reply_authority": "model_chat",
                    "metadata": {},
                },
                "output_check": {"reply_origin": "chat_mainline"},
                "delivery": {"delivery_kind": "chat"},
            }
        },
    }

    report = build_live_session_export(payload, base_url="http://127.0.0.1:8787")

    assert report["summary"]["assistant_turn_count"] == 1
    assert report["summary"]["ordinary_chat_turn_count"] == 1
    assert report["summary"]["subject_gate_ok_count"] == 0
    assert report["summary"]["oe_available_count"] == 0
    assert report["summary"]["mainline_candidate_count"] == 0
    assert report["summary"]["host_only_count"] == 0
    assert report["summary"]["verdict"] == "ordinary_chat_window_present__mainline_not_observed"
    assert report["assistant_turns"][0]["mainline_candidate"] is False
