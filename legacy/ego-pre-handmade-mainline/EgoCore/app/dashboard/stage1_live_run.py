from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from app.dashboard.live_api_client import DashboardLiveApiClient, DashboardLiveApiClientError
from app.dashboard.live_session_export import build_live_session_export
from app.dashboard.stage1_prompt_sources import (
    DashboardStage1Prompt,
    DashboardStage1PromptPack,
    DashboardStage1PromptProvenance,
    build_dashboard_stage1_prompt_pack,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_name_slug() -> str:
    return datetime.now(timezone.utc).strftime("codex-stage1-%Y%m%d-%H%M%S")


def _trim_text(value: Any, *, limit: int = 280) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else f"{text[:limit]}..."


def _normalize_prompts(prompts: Sequence[DashboardStage1Prompt | Mapping[str, str]] | None) -> list[DashboardStage1Prompt]:
    if not prompts:
        return list(build_dashboard_stage1_prompt_pack().prompts)
    normalized: list[DashboardStage1Prompt] = []
    for index, item in enumerate(prompts, start=1):
        if isinstance(item, DashboardStage1Prompt):
            normalized.append(item)
            continue
        prompt_id = str(item.get("prompt_id") or f"prompt_{index}").strip() or f"prompt_{index}"
        label = str(item.get("label") or prompt_id).strip() or prompt_id
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError(f"prompt {prompt_id!r} is missing text")
        normalized.append(
            DashboardStage1Prompt(
                prompt_id=prompt_id,
                label=label,
                text=text,
                input_provenance=DashboardStage1PromptProvenance(
                    source_kind=str(item.get("source_kind") or "custom"),
                    source_label=str(item.get("source_label") or label),
                    derivation=str(item.get("derivation") or "native"),
                    source_ref=str(item.get("source_ref") or "") or None,
                    normalization_applied=bool(item.get("normalization_applied")),
                ),
            )
        )
    return normalized


def _prompt_pack_from_custom_prompts(prompts: Sequence[DashboardStage1Prompt]) -> DashboardStage1PromptPack:
    source_counts: dict[str, int] = {}
    for prompt in prompts:
        source_kind = prompt.input_provenance.source_kind
        source_counts[source_kind] = source_counts.get(source_kind, 0) + 1
    return DashboardStage1PromptPack(
        pack_id="stage1_dashboard_ordinary_chat_custom_v1",
        strategy="custom",
        prompts=tuple(prompts),
        prompt_source_counts=source_counts,
        prompt_pack_degraded=False,
        prompt_pack_summary={
            "strategy": "custom",
            "prompt_count": len(prompts),
            "source_sequence": [prompt.input_provenance.source_kind for prompt in prompts],
            "curated_slot_source": None,
            "allow_public_web": False,
        },
    )


def _classify_turn(
    *,
    prompt: DashboardStage1Prompt,
    before_revision: int,
    send_payload: Mapping[str, Any],
    send_transport: str,
    session_payload: Mapping[str, Any],
    fetch_transport: str,
) -> dict[str, Any]:
    debug = dict(send_payload.get("debug") or {})
    ingress = dict(debug.get("ingress") or {})
    request = dict(debug.get("request") or {})
    subject_gate = dict(dict(debug.get("subject_gate") or {}).get("ingress") or {})
    proto_self = dict(debug.get("proto_self") or {})
    response_plan = dict(debug.get("response_plan") or {})
    output_check = dict(debug.get("output_check") or {})
    metadata = dict(response_plan.get("metadata") or {})
    assistant = dict(dict(send_payload.get("messages") or {}).get("assistant") or {})
    reply_authority = str(response_plan.get("reply_authority") or "").strip() or None
    subject_gate_ok = bool(subject_gate.get("ok"))
    host_only = (
        not subject_gate_ok
        or str(reply_authority or "").startswith("host_")
        or assistant.get("status") in {"subject_gate_blocked", "subject_gate_finalize_blocked"}
    )
    return {
        "prompt_id": prompt.prompt_id,
        "label": prompt.label,
        "prompt_text": prompt.text,
        "input_provenance": prompt.input_provenance.as_dict(),
        "before_revision": before_revision,
        "send_transport": send_transport,
        "fetch_transport": fetch_transport,
        "send_revision": int(send_payload.get("session_revision") or 0),
        "observed_revision": int(session_payload.get("session_revision") or 0),
        "assistant_present": bool(assistant),
        "assistant_message_id": assistant.get("message_id"),
        "assistant_status": assistant.get("status"),
        "assistant_text_preview": _trim_text(assistant.get("text")),
        "source_kind": request.get("source_kind") or "dashboard_local",
        "runtime_action": ingress.get("runtime_action"),
        "conversation_act": ingress.get("conversation_act"),
        "parser_source": ingress.get("parser_source"),
        "subject_gate_ok": subject_gate_ok,
        "subject_gate_reason": subject_gate.get("reason"),
        "oe_available": bool(proto_self.get("available")),
        "reply_authority": reply_authority,
        "reply_origin": output_check.get("reply_origin"),
        "host_only": host_only,
        "degraded": bool(metadata.get("degraded")) if metadata.get("degraded") is not None else False,
    }


def _classify_blocker(exc: DashboardLiveApiClientError | None) -> tuple[str, str | None]:
    if exc is None:
        return "blocked_unknown", "unknown"
    if exc.status_code == 503 or exc.error_code == "dashboard_chat_unavailable":
        return "blocked_service_unavailable", "service_unavailable"
    if exc.error_code == "transport_error":
        return "blocked_transport_error", "transport_error"
    return "blocked_api_error", exc.error_code


def build_dashboard_stage1_live_run(
    *,
    client: DashboardLiveApiClient,
    prompts: Sequence[DashboardStage1Prompt | Mapping[str, str]] | None = None,
    session_name: str | None = None,
    wait_timeout_ms: int = 15000,
    prompt_source_strategy: str = "hybrid",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    prompt_pack = (
        _prompt_pack_from_custom_prompts(_normalize_prompts(prompts))
        if prompts
        else build_dashboard_stage1_prompt_pack(strategy=prompt_source_strategy)
    )
    normalized_prompts = list(prompt_pack.prompts)
    resolved_session_name = str(session_name or "").strip() or _session_name_slug()
    run_started_at = _utc_now_iso()

    create_response = client.create_or_select_session(name=resolved_session_name)
    create_payload = create_response.payload
    session = dict(create_payload.get("session") or {})
    session_id = str(session.get("session_id") or "").strip()
    current_revision = int(create_payload.get("session_revision") or 0)

    turn_results: list[dict[str, Any]] = []
    last_session_payload: dict[str, Any] | None = None
    execution_verdict = "single_entry_live_window_captured"
    blocker_reason: str | None = None
    blocker_error: dict[str, Any] | None = None

    for prompt in normalized_prompts:
        before_revision = current_revision
        try:
            send_response = client.send_message(session_id, prompt.text)
            session_response = client.get_session(
                session_id,
                after_revision=before_revision,
                wait_timeout_ms=wait_timeout_ms,
            )
        except DashboardLiveApiClientError as exc:
            execution_verdict, blocker_reason = _classify_blocker(exc)
            blocker_error = {
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "transport": exc.transport,
                "message": str(exc),
            }
            break

        send_payload = send_response.payload
        current_session_payload = session_response.payload
        assistant = dict(dict(send_payload.get("messages") or {}).get("assistant") or {})
        if not assistant:
            execution_verdict = "blocked_assistant_missing"
            blocker_reason = "assistant_missing"
            blocker_error = {
                "error_code": "assistant_missing",
                "status_code": None,
                "transport": send_response.transport,
                "message": "dashboard live run did not receive an assistant turn",
            }
            break
        observed_revision = int(current_session_payload.get("session_revision") or 0)
        if observed_revision <= before_revision or current_session_payload.get("has_update") is False:
            execution_verdict = "blocked_revision_wait_timeout"
            blocker_reason = "revision_wait_timeout"
            blocker_error = {
                "error_code": "revision_wait_timeout",
                "status_code": None,
                "transport": session_response.transport,
                "message": "dashboard live run timed out waiting for a new session revision",
            }
            break

        turn_results.append(
            _classify_turn(
                prompt=prompt,
                before_revision=before_revision,
                send_payload=send_payload,
                send_transport=send_response.transport,
                session_payload=current_session_payload,
                fetch_transport=session_response.transport,
            )
        )
        last_session_payload = dict(current_session_payload)
        current_revision = observed_revision

    assistant_turn_count = len(turn_results)
    ordinary_chat_turn_count = sum(1 for row in turn_results if row.get("runtime_action") == "chat")
    execute_task_turn_count = sum(1 for row in turn_results if row.get("runtime_action") == "execute_task")
    subject_gate_ok_count = sum(1 for row in turn_results if row.get("subject_gate_ok"))
    oe_available_count = sum(1 for row in turn_results if row.get("oe_available"))
    host_only_count = sum(1 for row in turn_results if row.get("host_only"))
    degraded_count = sum(1 for row in turn_results if row.get("degraded"))
    clean_window = (
        assistant_turn_count > 0
        and host_only_count == 0
        and degraded_count == 0
        and ordinary_chat_turn_count >= 4
        and subject_gate_ok_count == assistant_turn_count
    )

    export_report = None
    if execution_verdict == "single_entry_live_window_captured" and last_session_payload is not None:
        input_provenance_by_message_id = {
            str(row.get("assistant_message_id")): dict(row.get("input_provenance") or {})
            for row in turn_results
            if row.get("assistant_message_id")
        }
        export_report = build_live_session_export(
            last_session_payload,
            base_url=client.base_url,
            observation_source="autonomous_dashboard_runner",
            input_provenance_by_message_id=input_provenance_by_message_id,
        )
        export_report["prompt_pack_summary"] = dict(prompt_pack.prompt_pack_summary)
        export_report["prompt_source_counts"] = dict(prompt_pack.prompt_source_counts)
        export_report["prompt_pack_degraded"] = prompt_pack.prompt_pack_degraded

    report = {
        "schema_version": "dashboard_stage1_live_run.v1",
        "generated_at": _utc_now_iso(),
        "run_started_at": run_started_at,
        "report_kind": "dashboard_stage1_autonomous_live_run",
        "claim_ceiling": "single_entry_live_window_observation",
        "entrypoint_contract": {
            "entrypoint": "dashboard_chat",
            "source_kind": "dashboard_local",
            "rule": (
                "This autonomous runner samples one fresh dashboard_chat live window through the public dashboard API. "
                "It proves only the sampled dashboard entrypoint/window and must not be auto-promoted to telegram, "
                "cross-entry Stage 1 pass, runtime efficacy, or consciousness-like claims."
            ),
        },
        "session_id": session_id,
        "session_name": session.get("session_name") or resolved_session_name,
        "prompt_pack_id": prompt_pack.pack_id,
        "prompt_source_strategy": prompt_pack.strategy,
        "prompt_pack_summary": dict(prompt_pack.prompt_pack_summary),
        "prompt_source_counts": dict(prompt_pack.prompt_source_counts),
        "prompt_pack_degraded": prompt_pack.prompt_pack_degraded,
        "transport": {
            "create_session": create_response.transport,
            "fallback_used": any(
                item == "windows_curl"
                for item in [
                    create_response.transport,
                    *[row["send_transport"] for row in turn_results],
                    *[row["fetch_transport"] for row in turn_results],
                ]
            ),
        },
        "summary": {
            "assistant_turn_count": assistant_turn_count,
            "ordinary_chat_turn_count": ordinary_chat_turn_count,
            "execute_task_turn_count": execute_task_turn_count,
            "subject_gate_ok_count": subject_gate_ok_count,
            "oe_available_count": oe_available_count,
            "host_only_count": host_only_count,
            "degraded_count": degraded_count,
            "clean_live_window": clean_window,
        },
        "policy_contract": {
            "single_session_rule": "Each run uses exactly one new dedicated dashboard session and never reuses dashboard:test:default.",
            "dashboard_only_until_acceptance": True,
            "strengthened_criteria": {
                "host_only_count": 0,
                "degraded_count": 0,
                "ordinary_chat_turn_count_min": 4,
                "subject_gate_ok_equals_assistant_turn_count": True,
                "consecutive_runs_required": 2,
            },
            "stop_after_same_blocker_count": 2,
            "note": "Even repeated clean dashboard runs remain single-entry strengthened evidence and do not by themselves close Stage 1.",
            "prompt_source_rule": (
                "Mixed-source ordinary-chat prompts count only after they traverse the real dashboard_chat live path. "
                "They keep full parity inside dashboard-only strengthened evidence but do not change the single-entry claim ceiling."
            ),
        },
        "turn_results": turn_results,
        "execution_verdict": execution_verdict,
        "blocker_reason": blocker_reason,
        "blocker_error": blocker_error,
        "export_artifact_path": None,
    }
    return report, export_report


def render_dashboard_stage1_live_run_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    transport = dict(report.get("transport") or {})
    policy_state = dict(report.get("autonomous_policy_state") or {})
    lines = [
        "# Dashboard Stage 1 Autonomous Live Run",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- run_started_at: `{report.get('run_started_at')}`",
        f"- report_kind: `{report.get('report_kind')}`",
        f"- claim_ceiling: `{report.get('claim_ceiling')}`",
        f"- session_id: `{report.get('session_id')}`",
        f"- session_name: `{report.get('session_name')}`",
        f"- prompt_pack_id: `{report.get('prompt_pack_id')}`",
        f"- prompt_source_strategy: `{report.get('prompt_source_strategy')}`",
        f"- execution_verdict: `{report.get('execution_verdict')}`",
        f"- blocker_reason: `{report.get('blocker_reason')}`",
        f"- export_artifact_path: `{report.get('export_artifact_path')}`",
        f"- create_session_transport: `{transport.get('create_session')}`",
        f"- fallback_used: `{transport.get('fallback_used')}`",
        "",
        "## Summary",
        "",
        f"- prompt_source_counts: `{report.get('prompt_source_counts')}`",
        f"- prompt_pack_degraded: `{report.get('prompt_pack_degraded')}`",
        f"- assistant_turn_count: `{summary.get('assistant_turn_count')}`",
        f"- ordinary_chat_turn_count: `{summary.get('ordinary_chat_turn_count')}`",
        f"- execute_task_turn_count: `{summary.get('execute_task_turn_count')}`",
        f"- subject_gate_ok_count: `{summary.get('subject_gate_ok_count')}`",
        f"- oe_available_count: `{summary.get('oe_available_count')}`",
        f"- host_only_count: `{summary.get('host_only_count')}`",
        f"- degraded_count: `{summary.get('degraded_count')}`",
        f"- clean_live_window: `{summary.get('clean_live_window')}`",
        f"- recent_consecutive_clean_runs: `{policy_state.get('recent_consecutive_clean_runs')}`",
        f"- recent_same_blocker_count: `{policy_state.get('recent_same_blocker_count')}`",
        f"- dashboard_only_stability_strengthened: `{policy_state.get('dashboard_only_stability_strengthened')}`",
        f"- stop_requested_by_same_blocker_rule: `{policy_state.get('stop_requested_by_same_blocker_rule')}`",
        "",
        "## Turn Results",
        "",
    ]
    for turn in list(report.get("turn_results") or []):
        lines.extend(
            [
                f"### `{turn.get('prompt_id')}`",
                "",
                f"- prompt_text: `{turn.get('prompt_text')}`",
                f"- input_provenance: `{turn.get('input_provenance')}`",
                f"- before_revision: `{turn.get('before_revision')}`",
                f"- send_transport: `{turn.get('send_transport')}`",
                f"- fetch_transport: `{turn.get('fetch_transport')}`",
                f"- observed_revision: `{turn.get('observed_revision')}`",
                f"- runtime_action: `{turn.get('runtime_action')}`",
                f"- parser_source: `{turn.get('parser_source')}`",
                f"- subject_gate_ok: `{turn.get('subject_gate_ok')}`",
                f"- oe_available: `{turn.get('oe_available')}`",
                f"- reply_authority: `{turn.get('reply_authority')}`",
                f"- reply_origin: `{turn.get('reply_origin')}`",
                f"- host_only: `{turn.get('host_only')}`",
                f"- degraded: `{turn.get('degraded')}`",
                f"- assistant_text_preview: `{turn.get('assistant_text_preview')}`",
                "",
            ]
        )
    if not list(report.get("turn_results") or []):
        lines.extend(["- none", ""])
    lines.extend(
        [
            "## Claim Ceiling",
            "",
            "- This run records one dedicated dashboard_chat live window only.",
            "- Mixed-source prompts retain parity only inside dashboard-only strengthened evidence.",
            "- It does not prove Stage 1 closeout, cross-entrypoint proof, runtime efficacy, live user benefit, or consciousness-like properties.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DashboardStage1Prompt",
    "build_dashboard_stage1_live_run",
    "render_dashboard_stage1_live_run_markdown",
]
