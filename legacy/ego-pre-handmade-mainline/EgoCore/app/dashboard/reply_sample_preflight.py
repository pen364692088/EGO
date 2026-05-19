from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from app.config import get_config, load_config
from app.dashboard.chat_service import DashboardChatService


@dataclass(frozen=True)
class ReplySamplePrompt:
    prompt_id: str
    label: str
    text: str


DEFAULT_REPLY_SAMPLE_PROMPTS: tuple[ReplySamplePrompt, ...] = (
    ReplySamplePrompt(prompt_id="plain_continue", label="plain continue", text="继续"),
    ReplySamplePrompt(prompt_id="ordinary_ask", label="ordinary ask", text="你现在想继续聊什么？"),
    ReplySamplePrompt(prompt_id="low_cue_chat", label="low-cue chat", text="我们继续聊聊。"),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim_text(value: Any, *, limit: int = 240) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _normalize_prompts(prompts: Sequence[ReplySamplePrompt | Mapping[str, str]] | None) -> list[ReplySamplePrompt]:
    if not prompts:
        return list(DEFAULT_REPLY_SAMPLE_PROMPTS)

    normalized: list[ReplySamplePrompt] = []
    for index, item in enumerate(prompts, start=1):
        if isinstance(item, ReplySamplePrompt):
            normalized.append(item)
            continue
        prompt_id = str(item.get("prompt_id") or item.get("id") or f"prompt_{index}").strip() or f"prompt_{index}"
        label = str(item.get("label") or prompt_id).strip() or prompt_id
        text = str(item.get("text") or "").strip()
        if not text:
            raise ValueError(f"prompt {prompt_id!r} is missing text")
        normalized.append(ReplySamplePrompt(prompt_id=prompt_id, label=label, text=text))
    return normalized


def _subject_gate_status(debug: Mapping[str, Any]) -> str:
    subject_gate = dict(debug.get("subject_gate") or {})
    ingress = dict(subject_gate.get("ingress") or {})
    finalize = dict(subject_gate.get("finalize") or {})
    if ingress.get("ok") is False:
        return "ingress_blocked"
    if finalize and finalize.get("ok") is False:
        return "finalize_blocked"
    return "passed"


def _subject_gate_reason(debug: Mapping[str, Any]) -> str | None:
    subject_gate = dict(debug.get("subject_gate") or {})
    ingress = dict(subject_gate.get("ingress") or {})
    finalize = dict(subject_gate.get("finalize") or {})
    if ingress.get("ok") is False:
        return str(ingress.get("reason") or "").strip() or None
    if finalize and finalize.get("ok") is False:
        return str(finalize.get("reason") or "").strip() or None
    return None


def _reply_authority(debug: Mapping[str, Any]) -> str | None:
    response_plan = dict(debug.get("response_plan") or {})
    return str(response_plan.get("reply_authority") or "").strip() or None


def _response_plan_status(payload: Mapping[str, Any], debug: Mapping[str, Any]) -> str | None:
    response_plan = dict(debug.get("response_plan") or {})
    if response_plan.get("kind"):
        return str(response_plan.get("kind"))
    assistant = dict(dict(payload.get("messages") or {}).get("assistant") or {})
    return str(assistant.get("status") or "").strip() or None


def _host_only_flags(payload: Mapping[str, Any], debug: Mapping[str, Any]) -> tuple[bool, bool]:
    gate_status = _subject_gate_status(debug)
    ingress = dict(debug.get("ingress") or {})
    pre_runtime = dict(ingress.get("pre_runtime") or {})
    authority = _reply_authority(debug) or ""
    assistant = dict(dict(payload.get("messages") or {}).get("assistant") or {})
    assistant_status = str(assistant.get("status") or "").strip()

    host_only_early_return = bool(pre_runtime.get("should_return_early"))
    host_only = (
        gate_status != "passed"
        or host_only_early_return
        or authority.startswith("host_")
        or assistant_status in {"subject_gate_blocked", "subject_gate_finalize_blocked"}
    )
    return host_only, host_only_early_return


def _sample_record(
    *,
    prompt: ReplySamplePrompt,
    payload: Mapping[str, Any],
    session_id: str,
) -> dict[str, Any]:
    debug = dict(payload.get("debug") or {})
    request = dict(debug.get("request") or {})
    output_check = dict(debug.get("output_check") or {})
    proto_self = dict(debug.get("proto_self") or {})
    assistant = dict(dict(payload.get("messages") or {}).get("assistant") or {})
    subject_gate_status = _subject_gate_status(debug)
    host_only, host_only_early_return = _host_only_flags(payload, debug)
    reply_text = assistant.get("text")
    reply_sample_present = bool(str(reply_text or "").strip())

    record = {
        "prompt_id": prompt.prompt_id,
        "label": prompt.label,
        "prompt_text": prompt.text,
        "entrypoint": "dashboard_chat",
        "session_id": session_id,
        "source_kind": str(request.get("source_kind") or "dashboard_local").strip() or "dashboard_local",
        "subject_gate_status": subject_gate_status,
        "subject_gate_reason": _subject_gate_reason(debug),
        "subject_ingress_ok": subject_gate_status == "passed",
        "response_plan_status": _response_plan_status(payload, debug),
        "reply_sample_present": reply_sample_present,
        "host_only": host_only,
        "host_only_early_return": host_only_early_return,
        "mainline_candidate": reply_sample_present and not host_only,
        "reply_authority": _reply_authority(debug),
        "reply_origin": str(output_check.get("reply_origin") or "").strip() or None,
        "oe_available": bool(proto_self.get("available")),
        "response_text_preview": _trim_text(reply_text, limit=400),
        "delivery_kind": assistant.get("delivery_kind"),
        "assistant_status": assistant.get("status"),
        "request_mode": dict(debug.get("ingress") or {}).get("request_mode"),
        "interaction_kind": dict(debug.get("ingress") or {}).get("interaction_kind"),
        "conversation_act": dict(debug.get("ingress") or {}).get("conversation_act"),
        "debug_trace_id": debug.get("trace_id"),
    }
    return record


def _bootstrap_preflight_environment() -> dict[str, Any]:
    config_loaded = True
    config_error: str | None = None
    try:
        cfg = get_config()
    except Exception as exc:
        try:
            cfg = load_config(validate=False)
        except Exception as load_exc:
            cfg = None
            config_loaded = False
            config_error = f"{type(load_exc).__name__}: {load_exc}"
        else:
            config_loaded = True
            config_error = f"{type(exc).__name__}: {exc}"

    openemotion_enabled = bool(cfg.openemotion.get("enabled", False)) if cfg is not None else False
    default_provider = str(cfg.llm.get("default_provider") or "").strip() or None if cfg is not None else None
    return {
        "config_loaded": config_loaded,
        "config_error": config_error,
        "openemotion_enabled": openemotion_enabled,
        "default_provider": default_provider,
        "semantic_parse_mode": "dashboard_service_public_path__local_no_external_llm",
    }


def run_reply_sample_preflight(
    *,
    service: DashboardChatService | None = None,
    prompts: Sequence[ReplySamplePrompt | Mapping[str, str]] | None = None,
    session_prefix: str = "reply-sample-preflight",
) -> dict[str, Any]:
    environment = _bootstrap_preflight_environment()
    dashboard_service = service or DashboardChatService(llm_client_resolver=lambda: None)
    normalized_prompts = _normalize_prompts(prompts)
    records: list[dict[str, Any]] = []

    for prompt in normalized_prompts:
        session = dashboard_service.ensure_session(f"{session_prefix}-{prompt.prompt_id}")
        payload = dashboard_service.send_message(session.session_id, prompt.text)
        records.append(_sample_record(prompt=prompt, payload=payload, session_id=session.session_id))

    host_only_total = sum(1 for item in records if item["host_only"])
    reply_sample_total = sum(1 for item in records if item["reply_sample_present"])
    mainline_candidate_total = sum(1 for item in records if item["mainline_candidate"])
    subject_gate_pass_total = sum(1 for item in records if item["subject_gate_status"] == "passed")
    oe_available_total = sum(1 for item in records if item["oe_available"])
    early_return_total = sum(1 for item in records if item["host_only_early_return"])
    if mainline_candidate_total > 0:
        verdict = "mainline_candidate_reply_sample_present"
    elif reply_sample_total > 0:
        verdict = "host_only_only"
    else:
        verdict = "no_reply_sample_observed"

    return {
        "schema_version": "dashboard_unified_ingress.reply_sample_preflight.v1",
        "generated_at": _utc_now_iso(),
        "report_kind": "bounded_preflight_reply_sample_evidence",
        "claim_ceiling": "bounded_local_proof",
        "entrypoint_contract": {
            "entrypoint": "dashboard_chat",
            "source_kind": "dashboard_local",
            "rule": (
                "This report proves only bounded local dashboard_chat preflight samples that traverse "
                "DashboardChatService -> unified ingress -> subject gate -> runtime/delivery. It is not fresh live proof "
                "and it does not auto-promote to telegram or Stage 1 pass."
            ),
        },
        "environment": environment,
        "summary": {
            "total_samples": len(records),
            "reply_sample_present_total": reply_sample_total,
            "host_only_total": host_only_total,
            "host_only_early_return_total": early_return_total,
            "mainline_candidate_total": mainline_candidate_total,
            "subject_gate_pass_total": subject_gate_pass_total,
            "oe_available_total": oe_available_total,
            "verdict": verdict,
        },
        "samples": records,
        "next_gate": {
            "required": "fresh_unified_ingress_ordinary_chat_live_window",
            "accepted_entrypoints": ["telegram", "dashboard_chat"],
            "rule": "Single-entry fresh evidence proves only that entrypoint and must remain separate from this bounded preflight artifact.",
        },
    }


def render_reply_sample_preflight_markdown(report: Mapping[str, Any]) -> str:
    summary = dict(report.get("summary") or {})
    entrypoint_contract = dict(report.get("entrypoint_contract") or {})
    environment = dict(report.get("environment") or {})
    lines = [
        "# Unified-Ingress Reply-Sample Preflight",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- report_kind: `{report.get('report_kind')}`",
        f"- claim_ceiling: `{report.get('claim_ceiling')}`",
        f"- entrypoint: `{entrypoint_contract.get('entrypoint')}`",
        f"- source_kind: `{entrypoint_contract.get('source_kind')}`",
        f"- verdict: `{summary.get('verdict')}`",
        f"- reply_sample_present_total: `{summary.get('reply_sample_present_total')}` / `{summary.get('total_samples')}`",
        f"- host_only_total: `{summary.get('host_only_total')}` / `{summary.get('total_samples')}`",
        f"- mainline_candidate_total: `{summary.get('mainline_candidate_total')}` / `{summary.get('total_samples')}`",
        f"- subject_gate_pass_total: `{summary.get('subject_gate_pass_total')}` / `{summary.get('total_samples')}`",
        f"- oe_available_total: `{summary.get('oe_available_total')}` / `{summary.get('total_samples')}`",
        f"- config_loaded: `{environment.get('config_loaded')}`",
        f"- openemotion_enabled: `{environment.get('openemotion_enabled')}`",
        f"- semantic_parse_mode: `{environment.get('semantic_parse_mode')}`",
        "",
        "## Contract",
        "",
        f"- rule: `{entrypoint_contract.get('rule')}`",
        "",
        "## Samples",
        "",
    ]
    for sample in list(report.get("samples") or []):
        lines.extend(
            [
                f"### `{sample.get('prompt_id')}`",
                "",
                f"- label: `{sample.get('label')}`",
                f"- prompt_text: `{sample.get('prompt_text')}`",
                f"- entrypoint: `{sample.get('entrypoint')}`",
                f"- source_kind: `{sample.get('source_kind')}`",
                f"- subject_gate_status: `{sample.get('subject_gate_status')}`",
                f"- subject_gate_reason: `{sample.get('subject_gate_reason')}`",
                f"- response_plan_status: `{sample.get('response_plan_status')}`",
                f"- reply_sample_present: `{sample.get('reply_sample_present')}`",
                f"- host_only: `{sample.get('host_only')}`",
                f"- host_only_early_return: `{sample.get('host_only_early_return')}`",
                f"- mainline_candidate: `{sample.get('mainline_candidate')}`",
                f"- reply_authority: `{sample.get('reply_authority')}`",
                f"- reply_origin: `{sample.get('reply_origin')}`",
                f"- oe_available: `{sample.get('oe_available')}`",
                f"- response_text_preview: `{sample.get('response_text_preview')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim Ceiling",
            "",
            "- This artifact is bounded local proof only.",
            "- It does not prove fresh live improvement, Stage 1 pass, same-session tendency change, real user benefit, runtime efficacy, or consciousness.",
            "- Next honest gate remains a fresh entrypoint-tagged unified-ingress live window.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEFAULT_REPLY_SAMPLE_PROMPTS",
    "ReplySamplePrompt",
    "render_reply_sample_preflight_markdown",
    "run_reply_sample_preflight",
]
