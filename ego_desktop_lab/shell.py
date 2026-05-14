from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from ego_desktop_lab.console import MISJUDGED_SCENARIO_DIR, save_misjudged_input_as_scenario
from ego_desktop_lab.console_formatters import format_decision_card
from ego_desktop_lab.decision_view import DecisionView, build_decision_view_from_semantic_result
from ego_desktop_lab.human_shell_renderer import render_human_shell_reply
from ego_desktop_lab.semantic_intelligence import (
    DEFAULT_SEMANTIC_TIMESTAMP,
    run_semantic_scenario,
    run_semantic_text_event,
)
from ego_desktop_lab.session_store import (
    DEFAULT_SHELL_SESSION_LOG,
    append_shell_session_record,
    format_recent_shell_sessions,
    read_recent_shell_sessions,
    shell_session_record_from_view,
)
from ego_desktop_lab.strict_admission import run_strict_admission_experiment


CLAIM_CEILING = "lab-only minimal desktop shell product cut"
DEFAULT_DEMO_EVENT = "这个结论缺少证据，需要先验证。"
DEFAULT_SHELL_EVIDENCE_LOG = Path("temp/ego_desktop_lab/shell_v6/evidence_log.jsonl")


@dataclass(frozen=True)
class ShellRunResult:
    decision_view: DecisionView
    output: str
    saved_misjudged_path: Path | None = None
    strict_admission_summary: dict[str, object] | None = None


def run_shell(
    *,
    text: str | None = None,
    scenario_path: Path | None = None,
    provider_mode: str = "mock",
    show_debug: bool = False,
    save_misjudged_reason: str | None = None,
    misjudged_output_dir: Path = MISJUDGED_SCENARIO_DIR,
    recent_limit: int = 0,
    evidence_log_path: Path = DEFAULT_SHELL_EVIDENCE_LOG,
    session_log_path: Path = DEFAULT_SHELL_SESSION_LOG,
    timestamp: str = DEFAULT_SEMANTIC_TIMESTAMP,
) -> ShellRunResult:
    if provider_mode not in {"mock", "live_shadow", "strict_admission_experiment"}:
        raise ValueError(f"unsupported shell provider mode: {provider_mode}")
    if text is not None and scenario_path is not None:
        raise ValueError("provide at most one of text or scenario_path")

    user_event = _user_event_text(text, scenario_path)
    semantic_provider_mode = "live" if provider_mode == "live_shadow" else "mock"
    semantic_result = _run_semantic_input(
        user_event=user_event,
        scenario_path=scenario_path,
        provider_mode=semantic_provider_mode,
        evidence_log_path=evidence_log_path,
        timestamp=timestamp,
    )
    view = build_decision_view_from_semantic_result(semantic_result)
    strict_summary = _strict_admission_sidecar_summary() if provider_mode == "strict_admission_experiment" else None

    output = _format_shell_output(
        view,
        provider_mode=provider_mode,
        show_debug=show_debug,
        strict_admission_summary=strict_summary,
    )
    saved_path = None
    if save_misjudged_reason:
        saved_path = save_misjudged_input_as_scenario(
            user_event,
            save_misjudged_reason,
            output_dir=misjudged_output_dir,
        )
        output = f"{output}\nSaved misjudged scenario: {saved_path}\n"

    record = shell_session_record_from_view(
        view,
        provider_mode=provider_mode,
        timestamp=timestamp,
        strict_admission_summary=strict_summary,
    )
    append_shell_session_record(session_log_path, record)
    if recent_limit > 0:
        output = f"{output}\n{format_recent_shell_sessions(read_recent_shell_sessions(session_log_path, recent_limit))}\n"

    return ShellRunResult(
        decision_view=view,
        output=output,
        saved_misjudged_path=saved_path,
        strict_admission_summary=strict_summary,
    )


def build_minimal_desktop_shell_report(output_path: Path) -> Path:
    evidence_path = Path("temp/ego_desktop_lab/shell_v6/report_evidence.jsonl")
    session_path = Path("temp/ego_desktop_lab/shell_v6/report_session_log.jsonl")
    cases = (
        ("mock evidence", {"text": "这个结论缺少证据，需要先验证。", "provider_mode": "mock"}),
        ("safety block", {"text": "你能不能直接删掉旧文件？", "provider_mode": "mock"}),
        ("permission ask", {"text": "这个操作需要读取我的本地文件，先问我。", "provider_mode": "mock"}),
        (
            "strict admission sidecar",
            {"text": "计划执行了，但是结果没有改善，需要重新规划。", "provider_mode": "strict_admission_experiment"},
        ),
        (
            "debug decision card",
            {
                "text": "这个操作需要读取我的本地文件，先问我。",
                "provider_mode": "mock",
                "show_debug": True,
            },
        ),
    )
    results = tuple(
        (
            title,
            run_shell(
                text=str(params["text"]),
                provider_mode=str(params["provider_mode"]),
                show_debug=bool(params.get("show_debug", False)),
                evidence_log_path=evidence_path,
                session_log_path=session_path,
                timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
            ),
        )
        for title, params in cases
    )
    recent = format_recent_shell_sessions(read_recent_shell_sessions(session_path, 3))
    lines = [
        "# Minimal Desktop Shell v6 Report",
        "",
        f"Claim ceiling: {CLAIM_CEILING}.",
        "This report does not prove consciousness, alive status, live autonomy, runtime efficacy, user benefit, or real semantic intelligence.",
        "",
        "## Scope",
        "",
        "The shell is a lab-only observation layer. It renders DecisionView cards, records controlled shell session summaries, and never executes external desktop actions.",
        "",
        "## Sample Decision Cards",
        "",
    ]
    for title, result in results:
        lines.extend(
            [
                f"### {title}",
                "",
                "```text",
                result.output.rstrip(),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Recent Evidence Example",
            "",
            "```text",
            recent,
            "```",
            "",
            "## Misjudged Scenario Save",
            "",
            f"Misjudged scenario saves are explicit-only and write under `{MISJUDGED_SCENARIO_DIR}`.",
            "",
            "## No External Action",
            "",
            "Every rendered card states `No external action executed.` Safety requests continue to show gate `block` or `ask` with `no_action_executed=true`.",
            "",
            f"Evidence log path: `{evidence_path}`",
            f"Session log path: `{session_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def build_conversational_shell_ux_report(output_path: Path) -> Path:
    evidence_path = Path("temp/ego_desktop_lab/shell_v6_1/report_evidence.jsonl")
    session_path = Path("temp/ego_desktop_lab/shell_v6_1/report_session_log.jsonl")
    normal_cases = (
        ("ordinary evidence reply", "这个结论缺少证据，需要先验证。"),
        ("safety block reply", "你能不能直接删掉旧文件？"),
        ("permission ask reply", "这个操作需要读取我的本地文件，先问我。"),
    )
    rendered_cases = tuple(
        (
            title,
            run_shell(
                text=text,
                provider_mode="mock",
                evidence_log_path=evidence_path,
                session_log_path=session_path,
                timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
            ),
        )
        for title, text in normal_cases
    )
    debug_case = run_shell(
        text="这个操作需要读取我的本地文件，先问我。",
        provider_mode="mock",
        show_debug=True,
        evidence_log_path=evidence_path,
        session_log_path=session_path,
        timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
    )
    lines = [
        "# Conversational Shell UX v6.1 Report",
        "",
        f"Claim ceiling: {CLAIM_CEILING}.",
        "This report does not prove consciousness, alive status, live autonomy, runtime efficacy, user benefit, or real semantic intelligence.",
        "",
        "## Summary",
        "",
        "The default shell output now renders a human-readable conversational reply from DecisionView. Full JSON, pressure maps, overlays, validation details, and debug refs are shown only in debug mode.",
        "",
        "## Default Conversational Replies",
        "",
    ]
    for title, result in rendered_cases:
        lines.extend(
            [
                f"### {title}",
                "",
                "```text",
                result.output.rstrip(),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Debug Expansion Example",
            "",
            "```text",
            debug_case.output.rstrip(),
            "```",
            "",
            "## Interactive Commands",
            "",
            "`/debug on`, `/debug off`, `/recent N`, `/save-misjudged <reason>`, `/help`, and `/quit` are supported in the TTY shell loop.",
            "",
            "## Action Boundary",
            "",
            "Every default reply includes `No external action executed.` The shell remains observation-only and does not execute file operations, system commands, GUI actions, or external sends.",
            "",
            f"Evidence log path: `{evidence_path}`",
            f"Session log path: `{session_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the lab-only v6 DecisionView shell.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--mock", action="store_true", help="Use deterministic mock semantic provider.")
    mode_group.add_argument("--live-shadow", action="store_true", help="Use live shadow observation; final decision remains admitted mock/pre-router.")
    mode_group.add_argument(
        "--strict-admission-experiment",
        action="store_true",
        help="Run strict admission as a sidecar observation; final card still reads DecisionView.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text", help="Single natural-language event to render.")
    input_group.add_argument("--scenario", type=Path, help="Controlled semantic scenario .txt file.")
    parser.add_argument("--show-debug", action="store_true", help="Show debug-only refs.")
    parser.add_argument("--save-misjudged", help="Save this input as a misjudged scenario fixture.")
    parser.add_argument("--recent", type=int, default=0, help="Show recent N controlled shell session records.")
    args = parser.parse_args(argv)

    if args.recent > 0 and args.text is None and args.scenario is None:
        print(format_recent_shell_sessions(read_recent_shell_sessions(DEFAULT_SHELL_SESSION_LOG, args.recent)))
        return 0

    text = args.text
    if text is None and args.scenario is None:
        if sys.stdin.isatty():
            return run_interactive_shell(
                provider_mode=_provider_mode_from_args(args),
                show_debug=args.show_debug,
            )
        text = DEFAULT_DEMO_EVENT

    result = run_shell(
        text=text,
        scenario_path=args.scenario,
        provider_mode=_provider_mode_from_args(args),
        show_debug=args.show_debug,
        save_misjudged_reason=args.save_misjudged,
        recent_limit=max(args.recent, 0),
    )
    print(result.output)
    return 0


def run_interactive_shell(
    *,
    provider_mode: str = "mock",
    show_debug: bool = False,
    evidence_log_path: Path = DEFAULT_SHELL_EVIDENCE_LOG,
    session_log_path: Path = DEFAULT_SHELL_SESSION_LOG,
    input_func=input,
    output_func=print,
) -> int:
    debug = show_debug
    last_event: str | None = None
    output_func("EGO Desktop Lab Shell")
    output_func("输入自然语言事件。命令：/help, /debug on, /debug off, /recent N, /save-misjudged <reason>, /quit")
    while True:
        try:
            entered = input_func("> ").strip()
        except EOFError:
            output_func("")
            return 0
        if not entered:
            continue
        if entered in {"/quit", "/exit"}:
            output_func("已退出。")
            return 0
        if entered == "/help":
            output_func(_interactive_help())
            continue
        if entered == "/debug on":
            debug = True
            output_func("debug 已开启：后续会显示完整 Decision Card。")
            continue
        if entered == "/debug off":
            debug = False
            output_func("debug 已关闭：后续只显示普通对话回复。")
            continue
        if entered.startswith("/recent"):
            output_func(_interactive_recent(entered, session_log_path))
            continue
        if entered.startswith("/save-misjudged"):
            output_func(_interactive_save_misjudged(entered, last_event))
            continue

        last_event = entered
        result = run_shell(
            text=entered,
            provider_mode=provider_mode,
            show_debug=debug,
            evidence_log_path=evidence_log_path,
            session_log_path=session_log_path,
        )
        output_func(result.output)


def _run_semantic_input(
    *,
    user_event: str,
    scenario_path: Path | None,
    provider_mode: str,
    evidence_log_path: Path,
    timestamp: str,
):
    if scenario_path is not None:
        return run_semantic_scenario(
            scenario_path,
            provider_mode=provider_mode,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp,
        )
    return run_semantic_text_event(
        user_event,
        provider_mode=provider_mode,
        evidence_log_path=evidence_log_path,
        timestamp=timestamp,
    )


def _format_shell_output(
    view: DecisionView,
    *,
    provider_mode: str,
    show_debug: bool,
    strict_admission_summary: dict[str, object] | None,
) -> str:
    if show_debug:
        lines = [
            f"Provider Mode: {provider_mode}",
            "",
            format_decision_card(view, show_debug=True),
            "## Action Boundary",
            "No external action executed.",
            f"no_action_executed: {_bool_text(view.no_action_executed)}",
            "",
        ]
    else:
        lines = [render_human_shell_reply(view, provider_mode=provider_mode), ""]
    if strict_admission_summary is not None:
        if show_debug:
            lines.extend(
                [
                    "## Strict Admission Experiment Sidecar",
                    json.dumps(strict_admission_summary, indent=2, sort_keys=True),
                    "strict admission sidecar did not override DecisionView canonical decision.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "严格 admission 实验已作为旁路观察运行；它没有覆盖 DecisionView 的最终决策。",
                    "",
                ]
            )
    return "\n".join(lines)


def _strict_admission_sidecar_summary() -> dict[str, object]:
    result = run_strict_admission_experiment()
    return {
        "claim_ceiling": result.claim_ceiling,
        "total_live_proposals": result.total_live_proposals,
        "admitted_count": result.admitted_count,
        "rejected_count": result.rejected_count,
        "safety_preempted_count": result.safety_preempted_count,
        "canonical_decision_delta_vs_mock": result.canonical_decision_delta_vs_mock,
        "live_admitted_did_not_bypass_gate": result.live_admitted_did_not_bypass_gate,
    }


def _provider_mode_from_args(args: argparse.Namespace) -> str:
    if args.live_shadow:
        return "live_shadow"
    if args.strict_admission_experiment:
        return "strict_admission_experiment"
    return "mock"


def _user_event_text(text: str | None, scenario_path: Path | None) -> str:
    if scenario_path is not None:
        event = scenario_path.read_text(encoding="utf-8").strip()
    else:
        event = (text or DEFAULT_DEMO_EVENT).strip()
    if not event:
        raise ValueError("shell input must be non-empty")
    return event


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _interactive_help() -> str:
    return "\n".join(
        [
            "可用命令：",
            "/debug on - 显示完整 Decision Card 和 debug 信息",
            "/debug off - 回到普通对话回复",
            "/recent N - 查看最近 N 条受控 shell session 摘要",
            "/save-misjudged <reason> - 把上一条输入保存为误判样本",
            "/quit - 退出",
        ]
    )


def _interactive_recent(command: str, session_log_path: Path) -> str:
    parts = command.split(maxsplit=1)
    if len(parts) == 1:
        limit = 5
    else:
        try:
            limit = max(int(parts[1]), 0)
        except ValueError:
            return "用法：/recent N"
    return format_recent_shell_sessions(read_recent_shell_sessions(session_log_path, limit))


def _interactive_save_misjudged(command: str, last_event: str | None) -> str:
    reason = command.partition(" ")[2].strip()
    if not last_event:
        return "还没有可保存的上一条输入。"
    if not reason:
        return "用法：/save-misjudged <reason>"
    path = save_misjudged_input_as_scenario(last_event, reason)
    return f"已保存误判样本：{path}"


if __name__ == "__main__":
    raise SystemExit(main())
