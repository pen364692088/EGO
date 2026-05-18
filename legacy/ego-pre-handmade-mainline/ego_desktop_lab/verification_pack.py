from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ego_desktop_lab.reducer import AgentCycleResult, run_agent_cycle
from ego_desktop_lab.subject_state import SubjectState
from ego_desktop_lab.belief_state import BeliefState


PACKAGE_ROOT = Path(__file__).resolve().parent
SCENARIO_DIR = PACKAGE_ROOT / "scenarios"
DEFAULT_REPORT_SCENARIOS = (
    SCENARIO_DIR / "low_evidence_same_goal.json",
    SCENARIO_DIR / "high_evidence_same_goal.json",
    SCENARIO_DIR / "high_prediction_error_same_goal.json",
    SCENARIO_DIR / "identity_conflict_same_goal.json",
)


@dataclass(frozen=True)
class VerificationScenario:
    name: str
    timestamp: str
    expected_selected_intention: str
    evidence_log_path: Path
    state: SubjectState
    belief_state: BeliefState


def load_scenario(path: Path) -> VerificationScenario:
    scenario_path = _resolve_controlled_scenario_path(path)
    with scenario_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    state_payload = payload["state"]
    belief_payload = payload["belief_state"]
    return VerificationScenario(
        name=str(payload["name"]),
        timestamp=str(payload["timestamp"]),
        expected_selected_intention=str(payload["expected_selected_intention"]),
        evidence_log_path=Path(str(payload["evidence_log_path"])),
        state=SubjectState(
            agent_id=str(state_payload["agent_id"]),
            core_commitments=tuple(str(item) for item in state_payload["core_commitments"]),
            uncertainty=float(state_payload["uncertainty"]),
            integrity=float(state_payload["integrity"]),
            goal_pressure=float(state_payload["goal_pressure"]),
            risk_sensitivity=float(state_payload["risk_sensitivity"]),
            unfinished_goals=tuple(state_payload["unfinished_goals"]),
            recent_failures=tuple(str(item) for item in state_payload["recent_failures"]),
            identity_conflict=bool(state_payload["identity_conflict"]),
        ),
        belief_state=BeliefState(
            known_facts=tuple(str(item) for item in belief_payload["known_facts"]),
            unknowns=tuple(str(item) for item in belief_payload["unknowns"]),
            assumptions=tuple(str(item) for item in belief_payload["assumptions"]),
            evidence_strength=float(belief_payload["evidence_strength"]),
            confidence=float(belief_payload["confidence"]),
        ),
    )


def run_scenario(
    path: Path,
    *,
    evidence_log_path_override: Path | None = None,
) -> AgentCycleResult:
    scenario = load_scenario(path)
    evidence_log_path = evidence_log_path_override or scenario.evidence_log_path
    return run_agent_cycle(
        scenario.state,
        evidence_log_path=evidence_log_path,
        timestamp=scenario.timestamp,
        belief_state=scenario.belief_state,
    )


def build_priority_table(result: AgentCycleResult) -> list[dict[str, object]]:
    return [
        {
            "rank": index,
            "id": intention.id,
            "goal": intention.goal,
            "priority": intention.priority,
            "affordance": intention.affordance,
            "goal_id": intention.goal_id,
            "goal_description": intention.goal_description,
            "source_tension": intention.source_tension.type,
            "proposed_action": intention.proposed_action,
        }
        for index, intention in enumerate(
            sorted(result.generated_intentions, key=lambda item: (-item.priority, item.id)),
            start=1,
        )
    ]


def build_verification_report(
    output_path: Path,
    *,
    scenario_paths: tuple[Path, ...] = DEFAULT_REPORT_SCENARIOS,
) -> Path:
    lines = [
        "# Verification Pack v1 Report",
        "",
        "Claim ceiling: lab-only deterministic verification for `ego_desktop_lab`.",
        "This report does not prove consciousness, life, live autonomy, runtime efficacy, or user benefit.",
        "",
        "## Summary",
        "",
        "| Scenario | Expected | Selected | Status | Evidence Log | Failure Class |",
        "|---|---|---|---|---|---|",
    ]
    details: list[str] = []

    for scenario_path in scenario_paths:
        scenario = load_scenario(scenario_path)
        result = run_scenario(scenario_path)
        selected = result.selected_intention.goal if result.selected_intention else "none"
        status = "pass" if selected == scenario.expected_selected_intention else "fail"
        failure_class = "none" if status == "pass" else _classify_failure(result, scenario)
        lines.append(
            "| "
            + " | ".join(
                [
                    scenario.name,
                    scenario.expected_selected_intention,
                    selected,
                    status,
                    str(result.evidence_log_path),
                    failure_class,
                ]
            )
            + " |"
        )
        details.extend(_scenario_detail_lines(scenario, result, status, failure_class))

    lines.extend(["", "## Scenario Details", ""])
    lines.extend(details)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _resolve_controlled_scenario_path(path: Path) -> Path:
    resolved = path.resolve()
    scenario_root = SCENARIO_DIR.resolve()
    try:
        resolved.relative_to(scenario_root)
    except ValueError as exc:
        raise ValueError(f"scenario must be under {scenario_root}") from exc
    return resolved


def _classify_failure(
    result: AgentCycleResult,
    scenario: VerificationScenario,
) -> str:
    goals = {intention.goal for intention in result.generated_intentions}
    if scenario.expected_selected_intention not in goals:
        return "claim too strong"
    if result.selected_intention is None:
        return "algorithm issue"
    return "algorithm issue"


def _scenario_detail_lines(
    scenario: VerificationScenario,
    result: AgentCycleResult,
    status: str,
    failure_class: str,
) -> list[str]:
    selected = result.selected_intention.goal if result.selected_intention else "none"
    selected_priority = result.selected_intention.priority if result.selected_intention else "none"
    lines = [
        f"### {scenario.name}",
        "",
        f"- Expected selected intention: `{scenario.expected_selected_intention}`",
        f"- Actual selected intention: `{selected}`",
        f"- Selected priority: `{selected_priority}`",
        f"- Evidence log path: `{result.evidence_log_path}`",
        f"- Status: `{status}`",
        f"- Failure class: `{failure_class}`",
        "",
        "Affordance pressure map:",
        "",
        "| Affordance | Pressure |",
        "|---|---:|",
    ]
    for name, pressure in sorted(result.affordance_pressure.items()):
        lines.append(f"| `{name}` | {pressure} |")

    lines.extend(["", "Priority ranking:", "", "| Rank | Goal | Goal ID | Priority | Affordance | Source tension | Action |", "|---:|---|---|---:|---|---|---|"])
    for row in build_priority_table(result):
        lines.append(
            f"| {row['rank']} | `{row['goal']}` | `{row['goal_id']}` | {row['priority']} | "
            f"`{row['affordance']}` | `{row['source_tension']}` | `{row['proposed_action']}` |"
        )
    lines.append("")
    return lines
