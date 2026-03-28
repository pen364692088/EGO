import argparse
import json

from app.main import _validate_args
from app.restore_runtime import perform_startup_restore


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_artifacts(tmp_path):
    artifacts = tmp_path / "artifacts"
    _write_json(
        artifacts / "identity" / "ceo_invariants_snapshot.json",
        {
            "identity_handle": "ceo",
            "core_name": "CEO Agent",
            "core_role": "assistant",
            "non_negotiable_commitments": [{"description": "protect continuity"}],
        },
    )
    _write_json(
        artifacts / "self_model" / "ceo_self_model_snapshot.json",
        {
            "model_handle": "ceo",
            "capabilities": [{"name": "analysis"}],
            "limitations": [],
            "active_goals": [{"goal": "stay consistent"}],
            "standing_commitments": [{"description": "respect defaults"}],
            "tool_authority_boundary": {},
        },
    )
    _write_json(
        artifacts / "summary" / "summary_20260328_ceo.json",
        {
            "summary_id": "summary_20260328_ceo",
            "identity_handle_ref": "ceo",
            "identity_summary": {"core_role": "assistant"},
            "self_model_version_ref": {"model_handle": "ceo"},
            "recovery_hints": {"keep_style": True},
        },
    )
    return artifacts


def test_validate_args_rejects_restore_without_telegram():
    args = argparse.Namespace(
        telegram=False,
        status=False,
        runtime_v2_cli=False,
        dashboard=False,
        restore=True,
    )
    assert _validate_args(args) == "--restore 只能与 --telegram 一起使用。"


def test_validate_args_accepts_restore_telegram():
    args = argparse.Namespace(
        telegram=True,
        status=False,
        runtime_v2_cli=False,
        dashboard=False,
        restore=True,
    )
    assert _validate_args(args) is None


def test_perform_startup_restore_returns_pending_observation_and_audits(tmp_path):
    artifacts = _make_artifacts(tmp_path)
    audit_dir = artifacts / "restore" / "audit"

    result, observation = perform_startup_restore(
        artifacts_dir=artifacts,
        audit_dir=audit_dir,
        session_id="session_restore_test",
    )

    assert result.status == "success"
    assert observation.restore_status == "success"
    assert observation.restore_id == result.restore_id
    assert observation.authority_source == "restore_audit"
    assert observation.injection_summary["injected"] is True
    assert observation.recovery_hints_present is True
    assert observation.standing_commitments_preview == ["protect continuity", "respect defaults"]
    assert (audit_dir / f"{result.restore_id}.json").exists()
    assert (audit_dir / "injection_session_restore_test.json").exists()


def test_perform_startup_restore_returns_partial_when_self_model_missing(tmp_path):
    artifacts = tmp_path / "artifacts"
    _write_json(
        artifacts / "identity" / "ceo_invariants_snapshot.json",
        {
            "identity_handle": "ceo",
            "core_name": "CEO Agent",
            "core_role": "assistant",
            "non_negotiable_commitments": [{"description": "protect continuity"}],
        },
    )
    audit_dir = artifacts / "restore" / "audit"

    result, observation = perform_startup_restore(
        artifacts_dir=artifacts,
        audit_dir=audit_dir,
        session_id="session_restore_partial",
    )

    assert result.status == "partial"
    assert result.degraded_mode is True
    assert observation.restore_status == "partial"
    assert observation.degraded_mode is True
    assert observation.injection_summary["injected"] is True
    assert (audit_dir / f"{result.restore_id}.json").exists()
    assert (audit_dir / "injection_session_restore_partial.json").exists()


def test_perform_startup_restore_returns_failed_when_identity_missing(tmp_path):
    artifacts = tmp_path / "artifacts"
    audit_dir = artifacts / "restore" / "audit"

    result, observation = perform_startup_restore(
        artifacts_dir=artifacts,
        audit_dir=audit_dir,
        session_id="session_restore_failed",
    )

    assert result.status == "failed"
    assert result.errors
    assert observation.restore_status == "failed"
    assert observation.injection_summary["injected"] is False
    assert (audit_dir / f"{result.restore_id}.json").exists()
    assert not (audit_dir / "injection_session_restore_failed.json").exists()
