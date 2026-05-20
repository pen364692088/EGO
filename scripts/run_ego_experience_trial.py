#!/usr/bin/env python3
"""Run the EGO experience sample pack through a CLI-compatible EgoOperator path."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EGO_OPERATOR_DIR = ROOT / "EgoOperator"
if str(EGO_OPERATOR_DIR) not in sys.path:
    sys.path.insert(0, str(EGO_OPERATOR_DIR))

import agent_base as agent  # noqa: E402


DEFAULT_SAMPLE_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "chinese_experience_sample_pack.json"
)
DEFAULT_OUTPUT_DIR = EGO_OPERATOR_DIR / "artifacts" / "experience_trial" / "latest"
REPORT_SCHEMA = "ego_operator.experience_trial.v1"
CLAIM_CEILING = (
    "scripted real-entry experience trial local candidate only; not real consciousness, "
    "independent awareness, stable user benefit, runtime efficacy, live autonomy, or durable memory efficacy"
)
PROVIDER_UNAVAILABLE = {"none", "fallback", "fake", "unknown"}


@dataclass(frozen=True)
class TrialCaseResult:
    case_id: str
    category: str
    observation_class: str
    prompt: str
    reply_text: str
    entrypoint: str
    trace_path: str
    tool_use: tuple[str, ...]
    blocked_tools: tuple[str, ...]
    pending_approvals: int
    emotion_candidate: str
    response_need: str
    scenario_expectation_status: str
    status: str
    failure_notes: tuple[str, ...]


def load_sample_pack(path: Path = DEFAULT_SAMPLE_PACK) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dispatch_cli_compatible(runtime: agent.AgentRuntime, message: str) -> str:
    """Mirror the important non-interactive branches of `python EgoOperator/agent_base.py`.

    The goal is not to duplicate the whole CLI UI. It is to ensure scripted
    evaluation uses the same runtime command handlers for slash commands and
    the same `handle_user_message` path for ordinary user turns.
    """
    msg = message.strip()
    lowered = msg.lower()
    if lowered in {"/mode", "mode"}:
        return agent.render_runtime_permission_status(runtime)
    if lowered in {"/provider_status", "provider status"}:
        return json.dumps(runtime.provider_status(), ensure_ascii=False, indent=2)
    if lowered in {"/approvals", "approvals"}:
        return json.dumps(runtime.list_pending_approvals(), ensure_ascii=False, indent=2)
    if lowered.startswith("/approve "):
        proposal_id = msg.split(maxsplit=1)[1].strip()
        return runtime.format_approval_cli_output(runtime.approve_pending_operation(proposal_id))
    if lowered.startswith("/reject "):
        parts = msg.split(maxsplit=2)
        proposal_id = parts[1].strip() if len(parts) > 1 else ""
        reason = parts[2].strip() if len(parts) > 2 else "operator_rejected"
        return json.dumps(runtime.reject_pending_operation(proposal_id, reason=reason), ensure_ascii=False, indent=2)
    if msg.startswith("/remember "):
        return json.dumps(runtime.remember_operator_note(msg.removeprefix("/remember ").strip()), ensure_ascii=False, indent=2)
    if lowered.startswith("/memory_review"):
        parts = msg.split()
        limit = 20
        include_archived = "--all" in parts
        for part in parts[1:]:
            if part.isdigit():
                limit = int(part)
                break
        return json.dumps(runtime.review_operator_memory(limit=limit, include_archived=include_archived), ensure_ascii=False, indent=2)
    if msg.startswith("/memory_pin "):
        return json.dumps(runtime.pin_operator_memory(msg.removeprefix("/memory_pin ").strip()), ensure_ascii=False, indent=2)
    if msg.startswith("/memory_unpin "):
        return json.dumps(runtime.unpin_operator_memory(msg.removeprefix("/memory_unpin ").strip()), ensure_ascii=False, indent=2)
    if msg.startswith("/memory_archive "):
        return json.dumps(runtime.archive_operator_memory(msg.removeprefix("/memory_archive ").strip()), ensure_ascii=False, indent=2)
    if msg.startswith("/forget "):
        return json.dumps(runtime.forget_operator_memory(msg.removeprefix("/forget ").strip()), ensure_ascii=False, indent=2)
    if lowered in {"/tools", "tools"}:
        return json.dumps(runtime.tools.openai_tool_schemas(allowed_tool_names=runtime.gate.allowed_tools), ensure_ascii=False, indent=2)
    return runtime.handle_user_message(msg, source="experience_trial_cli_compatible").reply_text


def _trace_tool_summary(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    payload = _last_trace_payload(path)
    if not payload:
        return (), ()
    tool_trace = payload.get("tool_trace") if isinstance(payload, dict) else None
    if not isinstance(tool_trace, list):
        return (), ()
    tool_names: list[str] = []
    blocked: list[str] = []
    for item in tool_trace:
        if not isinstance(item, dict):
            continue
        call = item.get("tool_call") if isinstance(item.get("tool_call"), dict) else {}
        name = str(call.get("name") or "")
        if name:
            tool_names.append(name)
        output = item.get("output") if isinstance(item.get("output"), dict) else {}
        gate = item.get("gate") if isinstance(item.get("gate"), dict) else {}
        if name and (output.get("status") == "blocked" or gate.get("allowed") is False):
            blocked.append(name)
    return tuple(tool_names), tuple(blocked)


def _last_trace_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _trace_emotion_signal(path: Path) -> dict[str, Any]:
    payload = _last_trace_payload(path)
    subject_context = payload.get("subject_context") if isinstance(payload.get("subject_context"), dict) else {}
    appraisal = subject_context.get("appraisal_signal") if isinstance(subject_context.get("appraisal_signal"), dict) else {}
    signal = appraisal.get("emotion_signal") if isinstance(appraisal.get("emotion_signal"), dict) else {}
    return signal


def run_experience_trial(
    *,
    sample_pack_path: Path = DEFAULT_SAMPLE_PACK,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    case_limit: int | None = None,
    enable_operator_memory: bool = True,
) -> dict[str, Any]:
    sample_pack = load_sample_pack(sample_pack_path)
    cases = list(sample_pack.get("cases") or [])
    if case_limit is not None:
        cases = cases[: max(0, case_limit)]

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    trace_dir = out / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    memory_dir = out / "memory"
    runtime = agent.build_demo_runtime(
        enable_operator_memory=enable_operator_memory,
        operator_memory_dir=memory_dir,
        runtime_mode="approve",
    )

    previous_verbose = (agent.DEFAULT_VERBOSE_TOOLS, agent.DEFAULT_VERBOSE_TODOS, agent.DEFAULT_VERBOSE_SUBAGENTS)
    agent.DEFAULT_VERBOSE_TOOLS = False
    agent.DEFAULT_VERBOSE_TODOS = False
    agent.DEFAULT_VERBOSE_SUBAGENTS = False

    results: list[TrialCaseResult] = []
    started = time.monotonic()
    try:
        for case in cases:
            case_id = str(case.get("id") or "unknown_case")
            trace_path = trace_dir / f"{case_id}.jsonl"
            if trace_path.exists():
                trace_path.unlink()
            runtime.trace_store = agent.JsonlTraceStore(trace_path)
            reply = dispatch_cli_compatible(runtime, str(case.get("prompt") or ""))
            tool_use, blocked = _trace_tool_summary(trace_path)
            emotion_signal = _trace_emotion_signal(trace_path)
            pending_count = int(runtime.list_pending_approvals().get("count", 0))
            failure_notes: list[str] = []
            if not reply.strip():
                failure_notes.append("empty_reply")
            expected_emotion = str(case.get("expected_emotion_candidate") or "")
            observed_emotion = str(emotion_signal.get("primary_candidate") or "")
            expected_need = str(case.get("expected_response_need") or "")
            observed_need = str(emotion_signal.get("response_need") or "")
            if expected_emotion and observed_emotion != expected_emotion:
                failure_notes.append(f"emotion_candidate_mismatch:{observed_emotion or 'missing'}!= {expected_emotion}")
            if expected_need and observed_need != expected_need:
                failure_notes.append(f"response_need_mismatch:{observed_need or 'missing'}!= {expected_need}")
            if str(case.get("observation_class")) == "scripted_real_entry":
                failure_notes.append("scripted_real_entry_requires_review")
            scenario_expectation_failures = [
                note
                for note in failure_notes
                if note.startswith("emotion_candidate_mismatch:") or note.startswith("response_need_mismatch:")
            ]
            results.append(
                TrialCaseResult(
                    case_id=case_id,
                    category=str(case.get("category") or ""),
                    observation_class=str(case.get("observation_class") or ""),
                    prompt=str(case.get("prompt") or ""),
                    reply_text=reply,
                    entrypoint="cli_compatible_dispatch",
                    trace_path=str(trace_path),
                    tool_use=tool_use,
                    blocked_tools=blocked,
                    pending_approvals=pending_count,
                    emotion_candidate=observed_emotion,
                    response_need=observed_need,
                    scenario_expectation_status="pass" if not scenario_expectation_failures else "failed",
                    status="ok" if reply.strip() and not scenario_expectation_failures else "failed",
                    failure_notes=tuple(failure_notes),
                )
            )
    finally:
        agent.DEFAULT_VERBOSE_TOOLS, agent.DEFAULT_VERBOSE_TODOS, agent.DEFAULT_VERBOSE_SUBAGENTS = previous_verbose

    provider = str(getattr(runtime.planner.llm, "provider", "unknown") or "unknown").strip().lower()
    failed_count = sum(1 for item in results if item.status != "ok")
    if provider in PROVIDER_UNAVAILABLE:
        status = "scripted_real_entry_provider_unavailable"
    elif failed_count:
        status = "scripted_real_entry_failed"
    else:
        status = "scripted_real_entry_needs_review"

    report = {
        "schema_version": REPORT_SCHEMA,
        "status": status,
        "claim_ceiling": CLAIM_CEILING,
        "provider_mode": provider,
        "entrypoint_contract": "EgoOperator CLI-compatible slash-command dispatch plus AgentRuntime.handle_user_message",
        "sample_pack": str(sample_pack_path),
        "case_count": len(cases),
        "failed_count": failed_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "results": [asdict(item) for item in results],
        "not_claimed": [
            "real consciousness",
            "independent awareness",
            "stable user benefit",
            "runtime efficacy",
            "live autonomy",
            "durable memory efficacy",
        ],
    }
    report_path = out / "experience_trial_report.json"
    markdown_path = out / "experience_trial_report.md"
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    return report


def format_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# EgoOperator Experience Trial",
        "",
        f"status = `{report['status']}`",
        f"provider_mode = `{report['provider_mode']}`",
        f"case_count = `{report['case_count']}`",
        f"failed_count = `{report['failed_count']}`",
        f"claim_ceiling = `{report['claim_ceiling']}`",
        "",
        "This scripted report uses the CLI-compatible EgoOperator path. It cannot prove stable user benefit, live autonomy, runtime efficacy, durable memory efficacy, or consciousness.",
        "",
        "| case | category | observation_class | status | emotion | tools | pending approvals |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["results"]:
        tools = ", ".join(item["tool_use"]) if item["tool_use"] else "none"
        lines.append(
            f"| `{item['case_id']}` | `{item['category']}` | `{item['observation_class']}` | `{item['status']}` | `{item.get('emotion_candidate') or 'n/a'}` | {tools} | `{item['pending_approvals']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run EgoOperator experience sample pack through a CLI-compatible path.")
    parser.add_argument("--sample-pack", type=Path, default=DEFAULT_SAMPLE_PACK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case-limit", type=int, default=None)
    parser.add_argument("--disable-memory", action="store_true")
    args = parser.parse_args(argv)
    report = run_experience_trial(
        sample_pack_path=args.sample_pack,
        output_dir=args.out,
        case_limit=args.case_limit,
        enable_operator_memory=not args.disable_memory,
    )
    print(json.dumps({
        "status": report["status"],
        "json": str(Path(args.out).resolve() / "experience_trial_report.json"),
        "markdown": str(Path(args.out).resolve() / "experience_trial_report.md"),
        "case_count": report["case_count"],
        "provider_mode": report["provider_mode"],
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] in {"scripted_real_entry_needs_review", "scripted_real_entry_provider_unavailable"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
