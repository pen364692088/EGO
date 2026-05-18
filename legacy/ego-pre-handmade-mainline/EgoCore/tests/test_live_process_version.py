import json
from pathlib import Path

from app.live_process_version import build_live_process_version_record, write_live_process_version_report


def test_build_live_process_version_record_contains_required_fields():
    record = build_live_process_version_record(
        process_kind="telegram",
        argv=["python", "-m", "app.main", "--telegram"],
        cwd="/tmp/demo",
        repo_root=Path(__file__).resolve().parents[2],
    )

    assert record["schema_version"] == "egocore.live_process_version.v1"
    assert record["process_kind"] == "telegram"
    assert record["argv"] == ["python", "-m", "app.main", "--telegram"]
    assert record["cwd"] == "/tmp/demo"
    assert isinstance(record["pid"], int)
    assert record["git_commit_sha"]
    assert record["git_commit_short"]


def test_write_live_process_version_report_writes_json(tmp_path):
    path = tmp_path / "LIVE_TELEGRAM_PROCESS_VERSION.json"
    written = write_live_process_version_report(
        process_kind="telegram",
        argv=["python", "-m", "app.main", "--telegram"],
        cwd="/tmp/demo",
        repo_root=Path(__file__).resolve().parents[2],
        report_path=path,
    )

    assert written == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["process_kind"] == "telegram"
    assert payload["schema_version"] == "egocore.live_process_version.v1"
