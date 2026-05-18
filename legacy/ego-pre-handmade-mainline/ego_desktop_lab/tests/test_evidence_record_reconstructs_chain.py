from pathlib import Path

from ego_desktop_lab.event_log import read_evidence_records
from ego_desktop_lab.policy import INTENTION_SPECS, calculate_pressure_priority
from ego_desktop_lab.pressure import MotivationPressure
from ego_desktop_lab.verification_pack import run_scenario


def test_evidence_record_reconstructs_causal_chain(tmp_path: Path) -> None:
    evidence_path = tmp_path / "evidence.jsonl"
    result = run_scenario(
        Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"),
        evidence_log_path_override=evidence_path,
    )
    records = read_evidence_records(evidence_path)

    assert len(records) == 1
    record = records[0]
    for key in (
        "belief_state",
        "appraisal",
        "motivation_pressure",
        "affordance_pressure",
        "generated_intentions",
        "selected_intention",
        "gate_decision",
        "suggestion",
    ):
        assert key in record

    pressure = MotivationPressure(**record["motivation_pressure"])  # type: ignore[arg-type]
    assert pressure.affordance_map() == record["affordance_pressure"]

    generated = record["generated_intentions"]
    assert isinstance(generated, list)
    for intention in generated:
        spec = INTENTION_SPECS[intention["goal"]]
        source_tension = intention["source_tension"]
        recalculated = calculate_pressure_priority(
            affordance_pressure=pressure.pressure_on_affordance(str(spec["affordance"])),
            tension_severity=float(source_tension["severity"]),
            expected_value=float(spec["expected_value"]),
            risk=float(spec["risk"]),
            cost=float(spec["cost"]),
        )
        assert recalculated == intention["priority"]

    selected = record["selected_intention"]
    assert selected is not None
    ordered = sorted(enumerate(generated), key=lambda item: (-item[1]["priority"], item[0], item[1]["id"]))
    assert selected["id"] == ordered[0][1]["id"]
    assert selected["goal"] == result.selected_intention.goal
    assert record["gate_decision"]["status"] == result.gate_decision.status
    assert record["suggestion"] == result.suggestion
