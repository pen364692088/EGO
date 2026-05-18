from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from ego_desktop_lab.console_formatters import format_decision_card
from ego_desktop_lab.decision_view import DecisionView, build_decision_view_from_semantic_result
from ego_desktop_lab.semantic_intelligence import (
    DEFAULT_SEMANTIC_TIMESTAMP,
    SEMANTIC_SCENARIO_DIR,
    run_semantic_scenario,
    run_semantic_text_event,
)


MISJUDGED_SCENARIO_DIR = SEMANTIC_SCENARIO_DIR / "user_misjudged"
CLAIM_CEILING = "lab-only CLI operator console cut"


@dataclass(frozen=True)
class ConsoleRunResult:
    decision_view: DecisionView
    output: str
    saved_misjudged_path: Path | None = None


def run_operator_console(
    *,
    text: str | None = None,
    scenario_path: Path | None = None,
    provider_mode: str = "mock",
    show_debug: bool = False,
    save_misjudged_reason: str | None = None,
    misjudged_output_dir: Path = MISJUDGED_SCENARIO_DIR,
    evidence_log_path: Path | None = None,
    timestamp: str = DEFAULT_SEMANTIC_TIMESTAMP,
) -> ConsoleRunResult:
    if provider_mode != "mock":
        raise ValueError("v5a operator console only supports provider_mode='mock'")
    if bool(text) == bool(scenario_path):
        raise ValueError("provide exactly one of text or scenario_path")

    user_event = _scenario_text(scenario_path) if scenario_path is not None else str(text).strip()
    if not user_event:
        raise ValueError("operator console input must be non-empty")

    if scenario_path is not None:
        semantic_result = run_semantic_scenario(
            scenario_path,
            provider_mode=provider_mode,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp,
        )
    else:
        semantic_result = run_semantic_text_event(
            user_event,
            provider_mode=provider_mode,
            evidence_log_path=evidence_log_path,
            timestamp=timestamp,
        )

    view = build_decision_view_from_semantic_result(semantic_result)
    output = format_decision_card(view, show_debug=show_debug)
    saved_path = None
    if save_misjudged_reason:
        saved_path = save_misjudged_input_as_scenario(
            user_event,
            save_misjudged_reason,
            output_dir=misjudged_output_dir,
        )
        output = f"{output}\nSaved misjudged scenario: {saved_path}\n"
    return ConsoleRunResult(decision_view=view, output=output, saved_misjudged_path=saved_path)


def save_misjudged_input_as_scenario(
    user_event: str,
    reason: str,
    *,
    output_dir: Path = MISJUDGED_SCENARIO_DIR,
) -> Path:
    normalized_event = " ".join(user_event.strip().split())
    normalized_reason = " ".join(reason.strip().split())
    if not normalized_event:
        raise ValueError("user_event must be non-empty")
    if not normalized_reason:
        raise ValueError("reason must be non-empty")
    digest = hashlib.sha256(f"{normalized_event}\n{normalized_reason}".encode("utf-8")).hexdigest()[:16]
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"misjudged_{digest}.txt"
    path.write_text(
        "\n".join(
            (
                "User event:",
                normalized_event,
                "",
                "Misjudged reason:",
                normalized_reason,
                "",
                "Claim ceiling:",
                CLAIM_CEILING,
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


def build_cli_operator_console_report(output_path: Path) -> Path:
    evidence_path = Path("temp/ego_desktop_lab/cli_operator_console_v5a/report.jsonl")
    scenarios = (
        SEMANTIC_SCENARIO_DIR / "evidence_failure.txt",
        SEMANTIC_SCENARIO_DIR / "permission_failure.txt",
        SEMANTIC_SCENARIO_DIR / "ambiguous_user_concern.txt",
    )
    results = tuple(
        run_operator_console(
            scenario_path=path,
            provider_mode="mock",
            evidence_log_path=evidence_path,
            timestamp=DEFAULT_SEMANTIC_TIMESTAMP,
        )
        for path in scenarios
    )
    example_save_path = _misjudged_path_for(
        "The operator thinks this was misclassified.",
        "example misjudged save reason",
        MISJUDGED_SCENARIO_DIR,
    )
    lines = [
        "# CLI Operator Console v5a Report",
        "",
        f"Claim ceiling: {CLAIM_CEILING}.",
        "This report does not prove consciousness, alive status, live autonomy, runtime efficacy, user benefit, or real semantic intelligence.",
        "",
        "## Scope",
        "",
        "The console reads DecisionView and renders an operator card. It does not recompute selected intention, pressure, semantic policy, or gate decisions.",
        "",
        "## Sample Cards",
        "",
    ]
    for result in results:
        scenario_id = result.decision_view.semantic_understanding.get("accepted_failure_type") or "pending"
        lines.extend(
            [
                f"### {scenario_id}",
                "",
                "```text",
                result.output.rstrip(),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Misjudged Save Example",
            "",
            f"Example deterministic save path: `{example_save_path}`",
            "",
            "## No-LLM Fallback",
            "",
            "The v5a operator console supports only `--mock`. No live provider is required for pytest or CLI acceptance.",
            "",
            f"Evidence log path: `{evidence_path}`",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a lab-only DecisionView operator card.")
    parser.add_argument("--mock", action="store_true", help="Use deterministic mock semantic proposals.")
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text", help="Single natural-language event to render.")
    input_group.add_argument("--scenario", type=Path, help="Controlled semantic scenario .txt file.")
    parser.add_argument("--show-debug", action="store_true", help="Show debug-only refs folded by default.")
    parser.add_argument("--save-misjudged", help="Save the current input as a misjudged semantic scenario.")
    args = parser.parse_args(argv)

    if not args.mock:
        parser.error("v5a operator console requires --mock; live providers are out of scope")

    text = args.text
    if text is None and args.scenario is None:
        if not sys.stdin.isatty():
            parser.error("provide --text or --scenario when stdin is not interactive")
        text = input("User Event> ").strip()

    result = run_operator_console(
        text=text,
        scenario_path=args.scenario,
        provider_mode="mock",
        show_debug=args.show_debug,
        save_misjudged_reason=args.save_misjudged,
    )
    print(result.output)
    return 0


def _scenario_text(path: Path | None) -> str:
    if path is None:
        return ""
    return path.read_text(encoding="utf-8").strip()


def _misjudged_path_for(user_event: str, reason: str, output_dir: Path) -> Path:
    normalized_event = " ".join(user_event.strip().split())
    normalized_reason = " ".join(reason.strip().split())
    digest = hashlib.sha256(f"{normalized_event}\n{normalized_reason}".encode("utf-8")).hexdigest()[:16]
    return output_dir / f"misjudged_{digest}.txt"


if __name__ == "__main__":
    raise SystemExit(main())
