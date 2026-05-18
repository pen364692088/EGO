import json
from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.semantic_intelligence import (
    build_semantic_policy_calibration_report,
    run_semantic_scenario,
)


SCENARIO_DIR = Path("ego_desktop_lab/semantic_scenarios")


def test_canonical_decision_matches_report_after_selected(tmp_path: Path) -> None:
    report_path = tmp_path / "semantic_policy_report.md"
    build_semantic_policy_calibration_report(report_path)

    payload = _payload_for_scenario(report_path, "execution_failure")
    canonical = payload["canonical_decision"]

    assert canonical["after_selected_intention"]["goal"] == "retry_or_change_tool"
    assert canonical["selection_change_reason"] == (
        "execution_failure changed selection from verify_before_claim to retry_or_change_tool: "
        "execution failure calibrated toward bounded retry or tool change"
    )
    assert "after_selected_intention" not in payload
    assert "before_selected_intention" not in payload
    assert "selection_change_reason" not in payload


def test_legacy_next_core_cycle_cannot_override_canonical_decision(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO_DIR / "execution_failure.txt",
        provider_mode="mock",
        evidence_log_path=tmp_path / "execution.jsonl",
    )

    canonical = result.semantic_policy_calibration.canonical_decision
    legacy = result.next_core_cycle_influence

    assert canonical.after_selected_intention is not None
    assert canonical.after_selected_intention.goal == "retry_or_change_tool"
    assert legacy["record_role"] == "legacy_debug"
    assert legacy["is_final_decision_source"] is False
    assert legacy["after_selected_intention"] != canonical.after_selected_intention.goal


def test_each_failure_type_has_single_final_selected_intention(tmp_path: Path) -> None:
    expected = {
        "evidence_failure": "verify_before_claim",
        "plan_failure": "repair_or_replan_goal",
        "execution_failure": "retry_or_change_tool",
        "permission_failure": "ask_permission_or_defer",
        "goal_definition_failure": "split_goal_or_redefine_success_criteria",
    }

    for scenario_id, expected_goal in expected.items():
        result = run_semantic_scenario(
            SCENARIO_DIR / f"{scenario_id}.txt",
            provider_mode="mock",
            evidence_log_path=tmp_path / f"{scenario_id}.jsonl",
        )
        canonical = result.semantic_policy_calibration.canonical_decision
        evidence = result.evidence_record.to_dict()

        assert canonical.after_selected_intention is not None
        assert canonical.after_selected_intention.goal == expected_goal
        assert evidence["canonical_decision"]["after_selected_intention"]["goal"] == expected_goal
        assert evidence["after_selected_intention"]["goal"] == expected_goal
        assert evidence["next_core_cycle_influence"]["is_final_decision_source"] is False


def test_evidence_log_replay_uses_canonical_decision(tmp_path: Path) -> None:
    evidence_path = tmp_path / "semantic_policy.jsonl"
    run_semantic_scenario(
        SCENARIO_DIR / "execution_failure.txt",
        provider_mode="mock",
        evidence_log_path=evidence_path,
    )

    record = read_evidence_records(evidence_path)[0]
    canonical = record["canonical_decision"]
    legacy = record["next_core_cycle_influence"]

    replayed_final_goal = canonical["after_selected_intention"]["goal"]

    assert canonical["decision_source"] == "semantic_policy_calibration"
    assert canonical["semantic_policy_overlay_applied"] is True
    assert canonical["accepted_failure_type"] == "execution_failure"
    assert replayed_final_goal == "retry_or_change_tool"
    assert legacy["record_role"] == "legacy_debug"
    assert legacy["is_final_decision_source"] is False
    assert legacy["after_selected_intention"] != replayed_final_goal


def _payload_for_scenario(report_path: Path, scenario_id: str) -> dict[str, object]:
    for payload in _json_payloads(report_path.read_text(encoding="utf-8")):
        if payload.get("scenario_id") == scenario_id:
            return payload
    raise AssertionError(f"scenario payload not found: {scenario_id}")


def _json_payloads(markdown: str) -> tuple[dict[str, object], ...]:
    payloads: list[dict[str, object]] = []
    parts = markdown.split("```json")
    for part in parts[1:]:
        block, _, _ = part.partition("```")
        payloads.append(json.loads(block.strip()))
    return tuple(payloads)
