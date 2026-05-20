from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "run_ego_experience_trial.py"
spec = importlib.util.spec_from_file_location("run_ego_experience_trial", MODULE_PATH)
run_ego_experience_trial = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = run_ego_experience_trial
spec.loader.exec_module(run_ego_experience_trial)


def test_cli_compatible_dispatch_handles_provider_status(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    runtime = agent.build_demo_runtime(enable_operator_memory=False, runtime_mode="approve")

    reply = run_ego_experience_trial.dispatch_cli_compatible(runtime, "/provider_status")
    payload = json.loads(reply)

    assert payload["provider"] == "none"


def test_experience_trial_runs_sample_pack_through_cli_compatible_path(tmp_path, monkeypatch) -> None:
    agent = run_ego_experience_trial.agent
    monkeypatch.setattr(agent, "EGO_OPERATOR_ROOT", tmp_path)
    monkeypatch.setattr(agent, "DEFAULT_AGENT_WORKSPACE", tmp_path)
    (tmp_path / ".gitignore").write_text("artifacts/experience_trial/\nmemory/*.jsonl\n", encoding="utf-8")

    report = run_ego_experience_trial.run_experience_trial(output_dir=tmp_path, case_limit=3)

    payload = json.loads((tmp_path / "experience_trial_report.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "experience_trial_report.md").read_text(encoding="utf-8")
    assert report["schema_version"] == "ego_operator.experience_trial.v1"
    assert report["status"] == "scripted_real_entry_provider_unavailable"
    assert report["provider_mode"] == "none"
    assert report["case_count"] == 3
    assert all(item["entrypoint"] == "cli_compatible_dispatch" for item in report["results"])
    assert payload["case_count"] == 3
    assert "CLI-compatible EgoOperator path" in markdown
    assert "real consciousness" in payload["not_claimed"]
