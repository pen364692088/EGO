from pathlib import Path

from ego_desktop_lab.agency_decision_view import (
    build_agency_decision_view,
    format_agency_decision_view,
)
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.shell import build_v7_agency_kernel_shell_report
from ego_desktop_lab.verification_pack import load_scenario


def test_lab_spine_docs_do_not_claim_formal_runtime_authority() -> None:
    readme = Path("ego_desktop_lab/README.md").read_text(encoding="utf-8")
    bridge = Path("ego_desktop_lab/FUTURE_RUNTIME_SHADOW_TAP.md").read_text(encoding="utf-8")

    assert "current active innovation and product-lab spine" in readme
    assert "does not override" in readme
    assert "does not mutate OpenEmotion state" in readme
    assert "does not affect EgoCore runtime replies" in readme
    assert "shadow/event tap" in readme
    assert "future integration spec only" in bridge
    assert "No mutation of EgoCore runtime state" in bridge
    assert "No mutation of OpenEmotion state" in bridge
    assert "No Telegram send" in bridge


def test_agency_decision_view_reads_cycle_result_without_recomputing() -> None:
    source = Path("ego_desktop_lab/agency_decision_view.py").read_text(encoding="utf-8")
    forbidden = (
        "run_agent_cycle",
        "select_intention",
        "evaluate_gate",
        "derive_motivation_pressure",
        "run_self_maintaining_agency_cycle",
    )
    for token in forbidden:
        assert token not in source

    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    cycle = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    view = build_agency_decision_view(cycle)

    assert view.selected_intention == cycle.selected_intention
    assert view.selected_behavior_option == cycle.selected_behavior_option
    assert view.no_action_executed is True
    assert view.debug_refs["recomputed_decision"] is False


def test_agency_decision_view_renderer_exposes_operator_sections() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/low_evidence_same_goal.json"))
    cycle = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )
    rendered = format_agency_decision_view(build_agency_decision_view(cycle))

    assert "# Agency Kernel DecisionView" in rendered
    assert "## Lab Spine" in rendered
    assert "## Affective Drive" in rendered
    assert "## Behavior Options" in rendered
    assert "## Next Cycle Delta" in rendered
    assert "no_action_executed: true" in rendered
    assert "no runtime authority" in rendered


def test_shell_report_renders_v7_agency_kernel_without_repo_evidence(tmp_path: Path) -> None:
    report_path = tmp_path / "agency_kernel_shell.md"

    returned = build_v7_agency_kernel_shell_report(report_path)
    text = returned.read_text(encoding="utf-8")

    assert returned == report_path
    assert "# v7 Agency Kernel Shell Report" in text
    assert "# Agency Kernel DecisionView" in text
    assert "No external action executed" in text
    assert "does not prove consciousness" in text
    assert "mutate OpenEmotion" in text
