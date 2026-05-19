from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, *, limit: int = 400) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _summarize_live_window_verdict(
    *,
    ordinary_chat_count: int,
    mainline_candidate_count: int,
    host_only_count: int,
    degraded_count: int,
) -> str:
    if ordinary_chat_count <= 0:
        return "mixed_live_window_observed"
    if mainline_candidate_count > 0 and host_only_count == 0 and degraded_count == 0:
        return "ordinary_chat_mainline_observed"
    return "ordinary_chat_window_present__mainline_not_observed"


def _assistant_turn_rows(
    payload: Mapping[str, Any],
    *,
    input_provenance_by_message_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    transcript = list(payload.get("transcript") or [])
    debug_history = dict(payload.get("debug_history") or {})
    rows: list[dict[str, Any]] = []
    for message in transcript:
        if message.get("role") != "assistant":
            continue
        message_id = str(message.get("message_id") or "").strip()
        debug = dict(debug_history.get(message_id) or {})
        request = dict(debug.get("request") or {})
        ingress = dict(debug.get("ingress") or {})
        subject_gate = dict(dict(debug.get("subject_gate") or {}).get("ingress") or {})
        proto_self = dict(debug.get("proto_self") or {})
        response_plan = dict(debug.get("response_plan") or {})
        output_check = dict(debug.get("output_check") or {})
        delivery = dict(debug.get("delivery") or {})
        metadata = dict(response_plan.get("metadata") or {})
        runtime_action = ingress.get("runtime_action")
        response_tendency_summary = dict(metadata.get("response_tendency_summary") or {})
        chat_expression_hint = dict(metadata.get("chat_expression_hint") or {})
        proto_self_response_tendency = dict(proto_self.get("response_tendency") or {})
        preferred_mode = str(response_tendency_summary.get("preferred_mode") or "").strip() or None
        reply_mode = str(chat_expression_hint.get("reply_mode") or "").strip() or None
        input_provenance = (
            dict(input_provenance_by_message_id.get(message_id) or {})
            if input_provenance_by_message_id is not None
            else None
        )
        row = {
            "message_id": message_id,
            "entrypoint": "dashboard_chat",
            "source_kind": request.get("source_kind") or "dashboard_local",
            "user_input": request.get("user_input"),
            "assistant_text_preview": _trim_text(message.get("text")),
            "assistant_status": message.get("status"),
            "delivery_kind": message.get("delivery_kind") or delivery.get("delivery_kind"),
            "runtime_action": runtime_action,
            "conversation_act": ingress.get("conversation_act"),
            "parser_source": ingress.get("parser_source"),
            "subject_gate_ok": bool(subject_gate.get("ok")),
            "subject_gate_reason": subject_gate.get("reason"),
            "oe_available": bool(proto_self.get("available")),
            "reply_authority": response_plan.get("reply_authority"),
            "reply_origin": output_check.get("reply_origin"),
            "degraded": bool(metadata.get("degraded")) if metadata.get("degraded") is not None else False,
            "response_tendency_summary": response_tendency_summary,
            "chat_expression_hint": chat_expression_hint,
            "proto_self_response_tendency": proto_self_response_tendency,
            "preferred_mode": preferred_mode,
            "reply_mode": reply_mode,
            "tendency_signal_present": bool(response_tendency_summary or chat_expression_hint or proto_self_response_tendency),
            "non_ask_tendency": bool(preferred_mode and preferred_mode != "ask"),
            "input_provenance": input_provenance,
            "mainline_candidate": (
                bool(subject_gate.get("ok"))
                and bool(proto_self.get("available"))
                and response_plan.get("reply_authority") == "model_chat"
                and output_check.get("reply_origin") == "chat_mainline"
                and runtime_action == "chat"
            ),
            "host_only": bool(str(response_plan.get("reply_authority") or "").startswith("host_")),
        }
        rows.append(row)
    return rows


def build_live_session_export(
    payload: Mapping[str, Any],
    *,
    fetched_at: str | None = None,
    base_url: str | None = None,
    observation_source: str | None = None,
    input_provenance_by_message_id: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    assistant_rows = _assistant_turn_rows(payload, input_provenance_by_message_id=input_provenance_by_message_id)
    transcript = list(payload.get("transcript") or [])
    session = dict(payload.get("session") or {})
    session_state = dict(payload.get("session_state") or {})
    counter_runtime = Counter(row.get("runtime_action") for row in assistant_rows)
    counter_parser = Counter(row.get("parser_source") for row in assistant_rows)
    counter_authority = Counter(row.get("reply_authority") for row in assistant_rows)
    counter_input_sources = Counter(
        dict(row.get("input_provenance") or {}).get("source_kind")
        for row in assistant_rows
        if dict(row.get("input_provenance") or {}).get("source_kind")
    )

    ordinary_chat_rows = [row for row in assistant_rows if row.get("runtime_action") == "chat"]
    execute_task_rows = [row for row in assistant_rows if row.get("runtime_action") == "execute_task"]
    host_only_rows = [row for row in assistant_rows if row.get("host_only")]
    degraded_rows = [row for row in assistant_rows if row.get("degraded")]
    mainline_candidate_rows = [row for row in assistant_rows if row.get("mainline_candidate")]
    tendency_rows = [row for row in ordinary_chat_rows if row.get("tendency_signal_present")]
    non_ask_tendency_rows = [row for row in ordinary_chat_rows if row.get("non_ask_tendency")]
    counter_preferred_mode = Counter(
        row.get("preferred_mode")
        for row in ordinary_chat_rows
        if row.get("preferred_mode")
    )
    counter_reply_mode = Counter(
        row.get("reply_mode")
        for row in ordinary_chat_rows
        if row.get("reply_mode")
    )
    tendency_summary = {
        "signal_turn_count": len(tendency_rows),
        "non_ask_tendency_count": len(non_ask_tendency_rows),
        "preferred_mode_counts": dict(counter_preferred_mode),
        "reply_mode_counts": dict(counter_reply_mode),
        "revision_counter_available": False,
        "revision_counter_reason": (
            "Current dashboard live session export does not expose proto-self revision_counter; "
            "Stage 2 readout is limited to exported tendency signals until a dedicated revision surface is added."
        ),
        "verdict": (
            "non_ask_tendency_observed"
            if non_ask_tendency_rows
            else (
                "ask_only_tendency_observed"
                if tendency_rows
                else "no_tendency_signal_exported"
            )
        ),
    }
    summary_verdict = _summarize_live_window_verdict(
        ordinary_chat_count=len(ordinary_chat_rows),
        mainline_candidate_count=len(mainline_candidate_rows),
        host_only_count=len(host_only_rows),
        degraded_count=len(degraded_rows),
    )

    return {
        "schema_version": "dashboard_live_session_export.v1",
        "generated_at": fetched_at or _utc_now_iso(),
        "report_kind": "entrypoint_tagged_live_session_observation",
        "claim_ceiling": "single_entry_live_window_observation",
        "provenance": {
            "observation_source": observation_source,
        }
        if observation_source
        else None,
        "entrypoint_contract": {
            "entrypoint": "dashboard_chat",
            "source_kind": "dashboard_local",
            "rule": (
                "This export captures one fresh dashboard_chat live session through the public dashboard service. "
                "It proves only this sampled entrypoint/window and does not auto-promote to telegram, Stage 1 pass, "
                "or cross-entrypoint proof."
            ),
        },
        "fetch": {
            "base_url": base_url,
            "session_id": session.get("session_id"),
            "session_revision": payload.get("session_revision"),
        },
        "session": session,
        "session_state": {
            "task_status": session_state.get("task_status"),
            "waiting_for_user_input": bool(session_state.get("waiting_for_user_input")),
            "proto_self_scope": dict(session_state.get("proto_self_scope") or {}),
            "proto_self_available": bool(dict(session_state.get("proto_self") or {}).get("available")),
        },
        "summary": {
            "message_count": len(transcript),
            "assistant_turn_count": len(assistant_rows),
            "ordinary_chat_turn_count": len(ordinary_chat_rows),
            "execute_task_turn_count": len(execute_task_rows),
            "subject_gate_ok_count": sum(1 for row in assistant_rows if row.get("subject_gate_ok")),
            "oe_available_count": sum(1 for row in assistant_rows if row.get("oe_available")),
            "mainline_candidate_count": len(mainline_candidate_rows),
            "host_only_count": len(host_only_rows),
            "degraded_count": len(degraded_rows),
            "runtime_action_counts": dict(counter_runtime),
            "parser_source_counts": dict(counter_parser),
            "reply_authority_counts": dict(counter_authority),
            "source_counts": dict(counter_input_sources),
            "verdict": summary_verdict,
        },
        "tendency_summary": tendency_summary,
        "assistant_turns": assistant_rows,
        "transcript": transcript,
    }


def render_live_session_export_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    fetch = dict(report.get("fetch") or {})
    session = dict(report.get("session") or {})
    entrypoint_contract = dict(report.get("entrypoint_contract") or {})
    lines = [
        "# Dashboard Live Session Export",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- report_kind: `{report.get('report_kind')}`",
        f"- claim_ceiling: `{report.get('claim_ceiling')}`",
        f"- session_id: `{fetch.get('session_id') or session.get('session_id')}`",
        f"- session_revision: `{fetch.get('session_revision')}`",
        f"- entrypoint: `{entrypoint_contract.get('entrypoint')}`",
        f"- source_kind: `{entrypoint_contract.get('source_kind')}`",
        f"- verdict: `{summary.get('verdict')}`",
        f"- assistant_turn_count: `{summary.get('assistant_turn_count')}`",
        f"- ordinary_chat_turn_count: `{summary.get('ordinary_chat_turn_count')}`",
        f"- execute_task_turn_count: `{summary.get('execute_task_turn_count')}`",
        f"- subject_gate_ok_count: `{summary.get('subject_gate_ok_count')}`",
        f"- oe_available_count: `{summary.get('oe_available_count')}`",
        f"- mainline_candidate_count: `{summary.get('mainline_candidate_count')}`",
        f"- host_only_count: `{summary.get('host_only_count')}`",
        f"- degraded_count: `{summary.get('degraded_count')}`",
        f"- source_counts: `{summary.get('source_counts')}`",
        "",
        "## Stage 2 Tendency Readout",
        "",
        f"- tendency_verdict: `{dict(report.get('tendency_summary') or {}).get('verdict')}`",
        f"- signal_turn_count: `{dict(report.get('tendency_summary') or {}).get('signal_turn_count')}`",
        f"- non_ask_tendency_count: `{dict(report.get('tendency_summary') or {}).get('non_ask_tendency_count')}`",
        f"- preferred_mode_counts: `{dict(report.get('tendency_summary') or {}).get('preferred_mode_counts')}`",
        f"- reply_mode_counts: `{dict(report.get('tendency_summary') or {}).get('reply_mode_counts')}`",
        f"- revision_counter_available: `{dict(report.get('tendency_summary') or {}).get('revision_counter_available')}`",
        f"- revision_counter_reason: `{dict(report.get('tendency_summary') or {}).get('revision_counter_reason')}`",
        "",
        "## Contract",
        "",
        f"- rule: `{entrypoint_contract.get('rule')}`",
        "",
        "## Turn Summary",
        "",
    ]
    for row in list(report.get("assistant_turns") or []):
        lines.extend(
            [
                f"### `{row.get('message_id')}`",
                "",
                f"- user_input: `{row.get('user_input')}`",
                f"- runtime_action: `{row.get('runtime_action')}`",
                f"- conversation_act: `{row.get('conversation_act')}`",
                f"- parser_source: `{row.get('parser_source')}`",
                f"- subject_gate_ok: `{row.get('subject_gate_ok')}`",
                f"- oe_available: `{row.get('oe_available')}`",
                f"- reply_authority: `{row.get('reply_authority')}`",
                f"- reply_origin: `{row.get('reply_origin')}`",
                f"- preferred_mode: `{row.get('preferred_mode')}`",
                f"- reply_mode: `{row.get('reply_mode')}`",
                f"- non_ask_tendency: `{row.get('non_ask_tendency')}`",
                f"- host_only: `{row.get('host_only')}`",
                f"- degraded: `{row.get('degraded')}`",
                f"- response_tendency_summary: `{row.get('response_tendency_summary')}`",
                f"- chat_expression_hint: `{row.get('chat_expression_hint')}`",
                f"- input_provenance: `{row.get('input_provenance')}`",
                f"- mainline_candidate: `{row.get('mainline_candidate')}`",
                f"- assistant_text_preview: `{row.get('assistant_text_preview')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Ceiling",
            "",
            "- This export is a single-entry live-window observation for `dashboard_chat` only.",
            "- It does not by itself prove Stage 1 pass, cross-entrypoint proof, same-session tendency change, runtime efficacy, or consciousness.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "build_live_session_export",
    "render_live_session_export_markdown",
]
