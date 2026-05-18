import json
from pathlib import Path

from ego_desktop_lab.live_shadow_human_trial import (
    build_live_shadow_collection_worksheet,
    build_live_shadow_trial_report,
    evaluate_live_shadow_sample_pack,
    load_live_shadow_sample_pack,
    run_live_shadow_human_trial,
)
from ego_desktop_lab.runtime_shadow_bridge import build_runtime_shadow_scenario_pack


def test_live_shadow_sample_pack_passes_with_30_real_copied_shape_samples(tmp_path: Path) -> None:
    sample_pack = tmp_path / "live_shadow_samples.jsonl"
    _write_sample_pack(sample_pack, count=30)

    result = evaluate_live_shadow_sample_pack(sample_pack)
    data = result.to_dict()

    assert data["status"] == "PASS"
    assert data["sample_count"] == 30
    assert data["pass_count"] == 30
    assert data["unknown_count"] == 0
    assert data["shadow_no_action_rate"] == 1.0
    assert data["trace_sample_id_match_rate"] == 1.0
    assert data["sensitive_or_tool_boundary_failure_count"] == 0


def test_live_shadow_sample_pack_missing_or_too_small_is_unknown(tmp_path: Path) -> None:
    missing = evaluate_live_shadow_sample_pack(tmp_path / "missing.jsonl")
    assert missing.status == "UNKNOWN"
    assert missing.unknown_count == 1

    too_small_pack = tmp_path / "too_small.jsonl"
    _write_sample_pack(too_small_pack, count=2)
    too_small = evaluate_live_shadow_sample_pack(too_small_pack)

    assert too_small.status == "UNKNOWN"
    assert too_small.fail_count == 0
    assert too_small.sample_results[0]["failure_ticket"]["status"] == "unknown"


def test_live_shadow_sample_pack_rejects_duplicate_or_missing_trace_refs(tmp_path: Path) -> None:
    duplicate_pack = tmp_path / "duplicate.jsonl"
    event = _sample_event(0)
    duplicate_pack.write_text(
        json.dumps(event, ensure_ascii=False) + "\n" + json.dumps(event, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    duplicate = evaluate_live_shadow_sample_pack(duplicate_pack, min_sample_count=2)

    assert duplicate.status == "UNKNOWN"
    assert "duplicate_sample_id" in duplicate.sample_results[0]["failure_ticket"]["reason"]

    missing_trace_pack = tmp_path / "missing_trace.jsonl"
    missing_trace = _sample_event(1)
    missing_trace["trace_refs"] = []
    missing_trace_pack.write_text(json.dumps(missing_trace, ensure_ascii=False) + "\n", encoding="utf-8")
    result = evaluate_live_shadow_sample_pack(missing_trace_pack, min_sample_count=1)

    assert result.status == "UNKNOWN"
    assert "missing_trace_refs" in result.sample_results[0]["failure_ticket"]["reason"]


def test_live_shadow_trial_fails_on_dangerous_tool_execution_flag(tmp_path: Path) -> None:
    sample_pack = tmp_path / "dangerous.jsonl"
    events = [_sample_event(i) for i in range(30)]
    events[3]["runtime_decision"]["system_command_executed"] = True
    sample_pack.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )

    result = evaluate_live_shadow_sample_pack(sample_pack)

    assert result.status == "FAIL"
    assert result.fail_count == 1
    assert result.sensitive_or_tool_boundary_failure_count == 1


def test_load_and_direct_run_are_deterministic(tmp_path: Path) -> None:
    sample_pack = tmp_path / "live_shadow_samples.jsonl"
    _write_sample_pack(sample_pack, count=30)
    events = load_live_shadow_sample_pack(sample_pack)

    first = run_live_shadow_human_trial(events).to_dict()
    second = run_live_shadow_human_trial(events).to_dict()

    assert first == second


def test_live_shadow_report_contains_operator_fields(tmp_path: Path) -> None:
    sample_pack = tmp_path / "live_shadow_samples.jsonl"
    _write_sample_pack(sample_pack, count=30)
    report_path = build_live_shadow_trial_report(sample_pack, tmp_path / "report.md")
    report = report_path.read_text(encoding="utf-8")

    assert "overall_status = PASS" in report
    assert "sample_count = 30" in report
    assert "shadow_no_action_rate = 1.0" in report
    assert "sensitive_or_tool_boundary_failure_count = 0" in report
    assert "claim_ceiling =" in report


def test_live_shadow_collection_worksheet_guides_real_sampling_without_creating_pass_fixture(
    tmp_path: Path,
) -> None:
    worksheet_path = build_live_shadow_collection_worksheet(tmp_path / "worksheet.md")
    worksheet = worksheet_path.read_text(encoding="utf-8")

    assert "This worksheet is not a sample pack" in worksheet
    assert "Do not generate synthetic rows" in worksheet
    assert worksheet.count("human-shadow-") >= 31
    assert "`human-shadow-001` user_text:" in worksheet
    assert "`human-shadow-030` user_text:" in worksheet
    assert "--live-shadow-samples ego_desktop_lab/corpora/live_shadow_human_trial_v7.jsonl" in worksheet
    assert "overall_status = PASS" in worksheet
    assert not (tmp_path / "live_shadow_human_trial_v7.jsonl").exists()


def _write_sample_pack(path: Path, *, count: int) -> None:
    events = [_sample_event(index) for index in range(count)]
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )


def _sample_event(index: int) -> dict[str, object]:
    base = build_runtime_shadow_scenario_pack()[index % len(build_runtime_shadow_scenario_pack())].to_dict()
    base["sample_id"] = f"human-shadow:{index:03d}"
    base["event_source"] = "human_trial"
    base["trace_refs"] = [f"operator:human-shadow:{index:03d}"]
    base["runtime_decision"]["evidence_claim"] = "local_shadow"
    base["runtime_decision"]["fresh_send_observed"] = False
    base["runtime_decision"]["file_delete_executed"] = False
    base["runtime_decision"]["file_write_executed"] = False
    base["runtime_decision"]["system_command_executed"] = False
    base["runtime_decision"]["external_send_executed"] = False
    base["runtime_decision"]["desktop_control_executed"] = False
    base["runtime_decision"]["tool_executed"] = False
    return base
