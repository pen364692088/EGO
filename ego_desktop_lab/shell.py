from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ego_desktop_lab.console import MISJUDGED_SCENARIO_DIR, save_misjudged_input_as_scenario
from ego_desktop_lab.console_formatters import format_decision_card
from ego_desktop_lab.decision_view import DecisionView, build_decision_view_from_semantic_result
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
    )
    results = tuple(
        (
            title,
            run_shell(
                text=str(params["text"]),
                provider_mode=str(params["provider_mode"]),
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

    text = args.text
    if text is None and args.scenario is None:
        text = _prompt_or_demo_event()

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
    lines = [
        f"Provider Mode: {provider_mode}",
        "",
        format_decision_card(view, show_debug=show_debug),
        "## Action Boundary",
        "No external action executed.",
        f"no_action_executed: {_bool_text(view.no_action_executed)}",
        "",
    ]
    if strict_admission_summary is not None:
        lines.extend(
            [
                "## Strict Admission Experiment Sidecar",
                json.dumps(strict_admission_summary, indent=2, sort_keys=True),
                "strict admission sidecar did not override DecisionView canonical decision.",
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


def _prompt_or_demo_event() -> str:
    if sys.stdin.isatty():
        entered = input(f"User Event [{DEFAULT_DEMO_EVENT}]> ").strip()
        return entered or DEFAULT_DEMO_EVENT
    return DEFAULT_DEMO_EVENT


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


if __name__ == "__main__":
    raise SystemExit(main())
