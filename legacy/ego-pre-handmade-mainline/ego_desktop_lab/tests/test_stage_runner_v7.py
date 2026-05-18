from pathlib import Path

from ego_desktop_lab.stage_acceptance import PASS, UNKNOWN
from ego_desktop_lab.stage_runner import run_v7_stage_runner, write_stage_runner_result


def test_stage_runner_runs_passed_stages_in_order(tmp_path: Path) -> None:
    result = run_v7_stage_runner(
        out_dir=tmp_path,
        stages=("v7-stage-5", "v7-stage-6", "v7-stage-7"),
    )
    data = result.to_dict()

    assert data["overall_status"] == PASS
    assert data["completed_stages"] == ["v7-stage-5", "v7-stage-6", "v7-stage-7"]
    assert data["stopped_at"] is None
    assert [step["stage_id"] for step in data["steps"]] == ["v7-stage-5", "v7-stage-6", "v7-stage-7"]
    assert all(step["status"] == PASS for step in data["steps"])
    assert (tmp_path / "v7-stage-6_stage_result.json").exists()


def test_stage_runner_stops_on_unknown_future_stage(tmp_path: Path) -> None:
    result = run_v7_stage_runner(
        out_dir=tmp_path,
        stages=("v7-stage-5", "v7-stage-8", "v7-stage-9"),
    )
    data = result.to_dict()

    assert data["overall_status"] == UNKNOWN
    assert data["completed_stages"] == ["v7-stage-5"]
    assert data["stopped_at"] == "v7-stage-8"
    assert data["steps"][1]["status"] == UNKNOWN
    assert "Stop at" in data["steps"][1]["reason"] or "Stop and collect" in data["steps"][1]["reason"]
    assert (tmp_path / "v7-stage-8_stage_result.json").exists()
    assert not (tmp_path / "v7-stage-9_stage_result.json").exists()


def test_stage_runner_cli_report_writer(tmp_path: Path) -> None:
    result = run_v7_stage_runner(out_dir=tmp_path, stages=("v7-stage-5",))
    json_path, markdown_path = write_stage_runner_result(result, tmp_path / "runner.json")

    assert json_path.exists()
    assert markdown_path.exists()
    assert "overall_status = PASS" in markdown_path.read_text(encoding="utf-8")
    assert "v7-stage-5" in json_path.read_text(encoding="utf-8")
