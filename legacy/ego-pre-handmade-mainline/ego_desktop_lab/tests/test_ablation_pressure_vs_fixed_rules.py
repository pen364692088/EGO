from pathlib import Path

from ego_desktop_lab.drives import DEFAULT_DRIVE
from ego_desktop_lab.intention import generate_intentions, select_intention
from ego_desktop_lab.tension import detect_tensions
from ego_desktop_lab.verification_pack import load_scenario, run_scenario


def test_fixed_rules_are_not_sensitive_to_belief_counterfactuals(tmp_path: Path) -> None:
    low_path = Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json")
    high_path = Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json")
    low_scenario = load_scenario(low_path)
    high_scenario = load_scenario(high_path)

    low_selected = select_intention(generate_intentions(detect_tensions(low_scenario.state), DEFAULT_DRIVE))
    high_selected = select_intention(generate_intentions(detect_tensions(high_scenario.state), DEFAULT_DRIVE))

    assert low_selected is not None
    assert high_selected is not None
    assert low_selected.goal == high_selected.goal

    low_pressure_result = run_scenario(
        low_path,
        evidence_log_path_override=tmp_path / "low_pressure.jsonl",
    )
    high_pressure_result = run_scenario(
        high_path,
        evidence_log_path_override=tmp_path / "high_pressure.jsonl",
    )

    assert low_pressure_result.selected_intention is not None
    assert high_pressure_result.selected_intention is not None
    assert low_pressure_result.selected_intention.goal != high_pressure_result.selected_intention.goal
