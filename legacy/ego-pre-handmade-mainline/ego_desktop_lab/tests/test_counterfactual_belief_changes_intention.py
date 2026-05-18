from pathlib import Path

from ego_desktop_lab.gate import evaluate_gate
from ego_desktop_lab.verification_pack import DEFAULT_REPORT_SCENARIOS, load_scenario, run_scenario


def test_counterfactual_scenarios_select_expected_intentions(tmp_path: Path) -> None:
    for scenario_path in DEFAULT_REPORT_SCENARIOS:
        scenario = load_scenario(scenario_path)
        result = run_scenario(
            scenario_path,
            evidence_log_path_override=tmp_path / f"{scenario.name}.jsonl",
        )

        assert result.selected_intention is not None
        assert result.selected_intention.goal == scenario.expected_selected_intention


def test_identity_conflict_blocks_identity_modify_gate(tmp_path: Path) -> None:
    scenario_path = Path("ego_desktop_lab/scenarios/identity_conflict_same_goal.json")
    result = run_scenario(
        scenario_path,
        evidence_log_path_override=tmp_path / "identity.jsonl",
    )
    gate_decision = evaluate_gate("identity_modify")

    assert result.selected_intention is not None
    assert result.selected_intention.goal == "preserve_identity_boundary"
    assert gate_decision.status == "block"
