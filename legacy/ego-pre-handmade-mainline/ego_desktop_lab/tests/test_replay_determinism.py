from pathlib import Path

from ego_desktop_lab.verification_pack import build_priority_table, run_scenario


def test_same_scenario_replay_is_deterministic(tmp_path: Path) -> None:
    scenario_path = Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json")
    first = run_scenario(
        scenario_path,
        evidence_log_path_override=tmp_path / "first.jsonl",
    )
    second = run_scenario(
        scenario_path,
        evidence_log_path_override=tmp_path / "second.jsonl",
    )

    assert first.selected_intention is not None
    assert second.selected_intention is not None
    assert first.selected_intention.goal == second.selected_intention.goal
    assert first.selected_intention.priority == second.selected_intention.priority
    assert first.gate_decision == second.gate_decision
    assert build_priority_table(first) == build_priority_table(second)
