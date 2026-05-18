from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ego_desktop_lab.decision_view import build_decision_view_from_semantic_result
from ego_desktop_lab.llm_adapter import run_llm_cognition_adapter
from ego_desktop_lab.reducer import run_agent_cycle
from ego_desktop_lab.semantic_intelligence import run_semantic_scenario
from ego_desktop_lab.subject_state import build_demo_state
from ego_desktop_lab.verification_pack import run_scenario


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _print_section(title: str, value: object) -> None:
    print(f"\n{title}")
    print(json.dumps(_jsonable(value), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic ego desktop lab cycle.")
    parser.add_argument(
        "--scenario",
        type=Path,
        help="Run a controlled verification scenario JSON from ego_desktop_lab/scenarios.",
    )
    parser.add_argument(
        "--with-llm-mock",
        action="store_true",
        help="Run the deterministic core and then a mock LLM proposal-only adapter.",
    )
    parser.add_argument(
        "--with-llm-live",
        action="store_true",
        help="Run optional live LLM semantic observation if explicitly configured.",
    )
    parser.add_argument(
        "--semantic-scenario",
        type=Path,
        help="Run a controlled natural-language semantic scenario txt from ego_desktop_lab/semantic_scenarios.",
    )
    args = parser.parse_args()

    if args.semantic_scenario:
        provider_mode = "live" if args.with_llm_live else "mock" if args.with_llm_mock else "none"
        semantic_result = run_semantic_scenario(args.semantic_scenario, provider_mode=provider_mode)
        _print_section("semantic scenario", semantic_result.scenario)
        _print_section("decision view", build_decision_view_from_semantic_result(semantic_result))
        _print_section("live observation", semantic_result.live_observation)
        return

    if args.scenario:
        result = run_scenario(args.scenario)
    else:
        state = build_demo_state()
        evidence_log_path = Path("temp/ego_desktop_lab/evidence_log.jsonl")
        result = run_agent_cycle(state, evidence_log_path=evidence_log_path)

    _print_section("current state", result.old_state_summary)
    _print_section("belief state", result.belief_state)
    _print_section("detected tensions", result.tensions)
    _print_section("appraisal", result.appraisal)
    _print_section("motivation diff", result.motivation_diff)
    _print_section("motivation pressure", result.motivation_pressure)
    _print_section("affordance pressure", result.affordance_pressure)
    _print_section("generated intentions", result.generated_intentions)
    _print_section("selected intention", result.selected_intention)
    _print_section("gate decision", result.gate_decision)
    _print_section("suggestion", result.suggestion)

    if args.with_llm_mock:
        llm_result = run_llm_cognition_adapter(
            result,
            evidence_log_path=result.evidence_log_path,
            timestamp=result.evidence_record.timestamp,
        )
        _print_section("deterministic selected intention", result.selected_intention)
        _print_section("accepted semantic proposal", llm_result.semantic_proposal)
        _print_section("accepted plan proposals", llm_result.plan_proposals)
        _print_section("accepted goal reframe proposal", llm_result.goal_reframe_proposal)
        _print_section("LLM explanation", llm_result.explanation_draft)
        _print_section("proposal validation results", llm_result.proposal_validation_results)
        _print_section("rejected LLM proposals", llm_result.rejected_llm_proposals)
        _print_section("LLM plan gate results", llm_result.plan_gate_decisions)
        _print_section("LLM final suggestion", llm_result.llm_final_suggestion)

    _print_section("evidence log path", result.evidence_log_path)


if __name__ == "__main__":
    main()
