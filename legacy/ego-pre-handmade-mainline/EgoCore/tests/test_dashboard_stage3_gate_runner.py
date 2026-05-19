from __future__ import annotations

import argparse
import importlib
import json

from app.dashboard.stage3_stance_integrity import DEFAULT_STAGE3_CASES, build_stage3_run_state, record_stage3_completed_case


def _fake_case_result(case, *, initial_label: str = "OPTION_A", revised_label: str = "OPTION_B") -> dict:
    return {
        "case": {
            "case_id": case.case_id,
            "family": case.family,
            "topic_id": case.topic_id,
            "scenario": case.scenario,
            "option_a_label": case.option_a_label,
            "option_b_label": case.option_b_label,
        },
        "turns": [
            {
                "round_id": "Q1",
                "assistant_text": f"{initial_label} BASIS:none",
                "parsed": {"stance_label": initial_label, "revision_basis": "none"},
            },
            {
                "round_id": "Q2",
                "assistant_text": f"{initial_label} BASIS:none",
                "parsed": {"stance_label": initial_label, "revision_basis": "none"},
            },
            {
                "round_id": "Q3",
                "assistant_text": f"{initial_label} BASIS:none",
                "parsed": {"stance_label": initial_label, "revision_basis": "none"},
            },
            {
                "round_id": "Q4",
                "assistant_text": f"{revised_label} BASIS:new_evidence",
                "parsed": {"stance_label": revised_label, "revision_basis": "new_evidence"},
            },
        ],
        "scored": {
            "case_id": case.case_id,
            "case_family": case.family,
            "topic_id": case.topic_id,
            "initial_stance_present": True,
            "initial_stance_label": initial_label,
            "pressure_round_count": 2,
            "unsupported_reversal": False,
            "new_evidence_present": True,
            "revision_occurred": True,
            "revision_justified": True,
            "expected_revision_target": revised_label,
            "gate_verdict": "pass",
        },
    }


def _patch_artifact_paths(monkeypatch, runner_module, tmp_path) -> None:
    monkeypatch.setattr(runner_module, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(runner_module, "REPORT_JSON", tmp_path / "STAGE3_STANCE_INTEGRITY_GATE_CURRENT.json")
    monkeypatch.setattr(runner_module, "REPORT_MD", tmp_path / "STAGE3_STANCE_INTEGRITY_GATE_CURRENT.md")
    monkeypatch.setattr(runner_module, "LIFECYCLE_JSON", tmp_path / "STAGE3_STANCE_INTEGRITY_LIFECYCLE_CURRENT.json")
    monkeypatch.setattr(runner_module, "LIFECYCLE_MD", tmp_path / "STAGE3_STANCE_INTEGRITY_LIFECYCLE_CURRENT.md")
    monkeypatch.setattr(runner_module, "RUN_STATE_JSON", tmp_path / "STAGE3_STANCE_INTEGRITY_RUN_STATE_CURRENT.json")
    monkeypatch.setattr(runner_module, "RUN_STATE_MD", tmp_path / "STAGE3_STANCE_INTEGRITY_RUN_STATE_CURRENT.md")


def test_stage3_runner_partial_run_persists_run_state_without_overwriting_current(monkeypatch, tmp_path) -> None:
    runner_module = importlib.import_module("scripts.codex.run_dashboard_stage3_stance_integrity_gate")
    _patch_artifact_paths(monkeypatch, runner_module, tmp_path)

    environment = {
        "chat_provider": "openrouter",
        "chat_model": "qwen/qwen3.6-plus",
        "chat_fallback_enabled": False,
    }
    monkeypatch.setattr(runner_module, "bootstrap_stage3_environment", lambda: dict(environment))
    monkeypatch.setattr(runner_module, "_new_run_id", lambda: "stage3-run-partial")
    monkeypatch.setattr(
        runner_module,
        "parse_args",
        lambda: argparse.Namespace(
            session_prefix="stage3-test",
            case_limit=2,
            resume=False,
            reset_run=True,
        ),
    )

    def _fake_run(*, cases, case_complete_hook, **_kwargs):
        for case in cases:
            case_complete_hook(_fake_case_result(case))
        return {}

    monkeypatch.setattr(runner_module, "run_stage3_stance_integrity", _fake_run)

    assert runner_module.main() == 0

    run_state = json.loads(runner_module.RUN_STATE_JSON.read_text(encoding="utf-8"))
    assert run_state["run_id"] == "stage3-run-partial"
    assert run_state["status"] == "ready_for_resume"
    assert run_state["completed_case_ids"] == ["open_01", "open_02"]
    assert len(run_state["remaining_case_ids"]) == 10
    assert run_state["resume_recommended_command"].endswith("--resume --case-limit 2")
    assert not runner_module.REPORT_JSON.exists()


def test_stage3_runner_resume_completes_gate_and_writes_current_artifact(monkeypatch, tmp_path) -> None:
    runner_module = importlib.import_module("scripts.codex.run_dashboard_stage3_stance_integrity_gate")
    _patch_artifact_paths(monkeypatch, runner_module, tmp_path)

    environment = {
        "chat_provider": "openrouter",
        "chat_model": "qwen/qwen3.6-plus",
        "chat_fallback_enabled": False,
    }
    monkeypatch.setattr(runner_module, "bootstrap_stage3_environment", lambda: dict(environment))
    monkeypatch.setattr(
        runner_module,
        "parse_args",
        lambda: argparse.Namespace(
            session_prefix="stage3-test",
            case_limit=2,
            resume=True,
            reset_run=False,
        ),
    )

    run_state = build_stage3_run_state(
        run_id="stage3-run-complete",
        cases=DEFAULT_STAGE3_CASES,
        environment=environment,
        session_prefix="stage3-test",
        status="ready_for_resume",
    )
    for case in DEFAULT_STAGE3_CASES[:10]:
        record_stage3_completed_case(run_state, _fake_case_result(case))
    runner_module.RUN_STATE_JSON.write_text(json.dumps(run_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _fake_run(*, cases, case_complete_hook, **_kwargs):
        for case in cases:
            case_complete_hook(_fake_case_result(case))
        return {}

    monkeypatch.setattr(runner_module, "run_stage3_stance_integrity", _fake_run)

    assert runner_module.main() == 0

    updated_run_state = json.loads(runner_module.RUN_STATE_JSON.read_text(encoding="utf-8"))
    report = json.loads(runner_module.REPORT_JSON.read_text(encoding="utf-8"))

    assert updated_run_state["status"] == "completed"
    assert updated_run_state["remaining_case_ids"] == []
    assert report["summary"]["case_count"] == 12
    assert report["summary"]["unsupported_reversal_total"] == 0
    assert report["summary"]["revision_justified_total"] == 12
    assert report["summary"]["gate_verdict"] == "stage3_bounded_gate_pass"
    assert report["run_metadata"]["run_id"] == "stage3-run-complete"
