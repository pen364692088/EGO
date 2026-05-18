from pathlib import Path

from ego_desktop_lab.runtime_shadow_bridge import (
    build_runtime_shadow_operator_report,
    build_runtime_shadow_scenario_pack,
    run_runtime_shadow_bridge,
)


def test_runtime_shadow_bridge_localizes_expected_mismatch_categories() -> None:
    reports = [run_runtime_shadow_bridge(event).to_dict() for event in build_runtime_shadow_scenario_pack()]
    categories = {
        report["event_summary"]["sample_id"]: report["shadow_result"]["mismatch"]["category"]
        for report in reports
    }

    assert categories["v7-stage-6:normal_match"] == "match"
    assert categories["v7-stage-6:runtime_bridge_mismatch"] == "runtime_bridge"
    assert categories["v7-stage-6:expression_surface_mismatch"] == "expression_surface"
    assert categories["v7-stage-6:evidence_claim_mismatch"] == "evidence_claim_mismatch"


def test_runtime_shadow_bridge_is_shadow_only_and_no_action() -> None:
    report = run_runtime_shadow_bridge(build_runtime_shadow_scenario_pack()[1]).to_dict()
    safety = report["safety"]

    assert safety["no_reply_mutation"] is True
    assert safety["no_openemotion_writeback"] is True
    assert safety["no_telegram_send"] is True
    assert safety["no_transport_mutation"] is True
    assert safety["no_action_executed"] is True
    assert report["trace"]["sample_id"] == report["trace"]["trace_sample_id"]


def test_runtime_shadow_bridge_is_deterministic() -> None:
    event = build_runtime_shadow_scenario_pack()[2]

    first = run_runtime_shadow_bridge(event).to_dict()
    second = run_runtime_shadow_bridge(event).to_dict()

    assert first == second


def test_runtime_shadow_operator_report_contains_operator_fields(tmp_path: Path) -> None:
    out = build_runtime_shadow_operator_report(tmp_path / "runtime_shadow.md")
    report = out.read_text(encoding="utf-8")

    assert "shadow_total = 4" in report
    assert "safety_pass = true" in report
    assert "runtime_bridge" in report
    assert "expression_surface" in report
    assert "evidence_claim_mismatch" in report
    assert "no Telegram send" in report
