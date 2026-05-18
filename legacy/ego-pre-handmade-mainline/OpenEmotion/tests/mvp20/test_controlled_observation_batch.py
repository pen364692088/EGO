from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = ROOT / "OpenEmotion" / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from mvp20_scenario_bank import (  # noqa: E402
    SCENARIO_MANIFEST_SCHEMA_VERSION,
    load_scenario_bank,
    load_scenario_manifest,
    validate_scenario_manifest,
)


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_validate_scenario_manifest_rejects_missing_fields():
    errors = validate_scenario_manifest(
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "broken_case",
            "source_class": "repo_authored",
            "messages": ["hello"],
        }
    )

    assert "source_ref" in errors
    assert "license_note" in errors
    assert "dialogue_frame_target" in errors
    assert "idle_seconds" in errors


def test_load_scenario_manifest_rejects_unsupported_source_class(tmp_path):
    manifest_path = tmp_path / "bad_manifest.json"
    _write_manifest(
        manifest_path,
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "bad_source",
            "source_class": "public_web",
            "source_ref": "https://example.invalid",
            "license_note": "not allowed",
            "dialogue_frame_target": "initiative_followup_medium_reserve",
            "messages": ["What is this?", "Can you explain more?"],
            "idle_seconds": 900.0,
        },
    )

    with pytest.raises(ValueError, match="source_class"):
        load_scenario_manifest(manifest_path)


@pytest.mark.asyncio
async def test_batch_controlled_observation_runs_and_aggregates(tmp_path, monkeypatch):
    from run_mvp20_controlled_observation_batch import run_controlled_observation_batch

    bank_dir = tmp_path / "bank"
    base_payload = {
        "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
        "source_class": "repo_authored",
        "license_note": "repo authored",
        "messages": ["a", "b"],
        "idle_seconds": 900.0,
    }
    _write_manifest(
        bank_dir / "repo_a.json",
        {
            **base_payload,
            "scenario_id": "repo_case_a",
            "source_ref": "repo://repo_case_a",
            "dialogue_frame_target": "initiative_followup_medium_reserve",
        },
    )
    _write_manifest(
        bank_dir / "repo_b.json",
        {
            **base_payload,
            "scenario_id": "repo_case_b",
            "source_ref": "repo://repo_case_b",
            "dialogue_frame_target": "delivery_failure_hold_review",
        },
    )
    _write_manifest(
        bank_dir / "repo_c.json",
        {
            **base_payload,
            "scenario_id": "repo_case_c",
            "source_ref": "repo://repo_case_c",
            "dialogue_frame_target": "continuity_fragility_review",
        },
    )

    async def _fake_run_controlled_observation(**kwargs):
        scenario = dict(kwargs.get("scenario_manifest") or {})
        priorities = {
            "repo_case_a": "carry_forward",
            "repo_case_b": "hold",
            "repo_case_c": "review",
        }
        host_modes = {
            "repo_case_a": "candidate",
            "repo_case_b": "held",
            "repo_case_c": "held",
        }
        return {
            "status": "pass",
            "replay_valid": True,
            "initiative_proposal_present": True,
            "proposal_only_discipline_consistent": True,
            "behavioral_authority_none": True,
            "bounded_influence_present": True,
            "selected_priority": priorities[scenario["scenario_id"]],
            "commitment_mode": "carry_forward",
            "host_proactive_mode": host_modes[scenario["scenario_id"]],
            "initiative_self_delta": {
                "surface_reasons": ["initiative_pressure", "commitment_carryover", "idle_window"]
            },
            "initiative_writeback": {
                "decision": {"gate_verdict": "allow_writeback"},
                "record": {"revision_id": f"initiative_rev_{scenario['scenario_id']}"},
            },
        }

    monkeypatch.setattr(
        "run_mvp20_controlled_observation_batch.run_controlled_observation",
        _fake_run_controlled_observation,
    )

    payload = await run_controlled_observation_batch(
        bank_dir=bank_dir,
        output_json=tmp_path / "current_batch.json",
        artifacts_root=tmp_path / "artifacts",
    )

    assert payload["report_count"] == 3
    assert payload["accepted_count"] == 3
    assert payload["replay_consistent_count"] == 3
    assert payload["initiative_proposal_present_count"] == 3
    assert payload["proposal_only_discipline_count"] == 3
    assert payload["behavioral_authority_none_count"] == 3
    assert payload["bounded_influence_present_count"] == 3
    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V5"
    assert payload["evidence_level"] == "E5"
    assert payload["source_breakdown"] == {"repo_authored": 3}
    assert (tmp_path / "current_batch.json").exists()
    assert (tmp_path / "current_batch.md").exists()


def test_load_scenario_bank_ignores_unselected_ids(tmp_path):
    _write_manifest(
        tmp_path / "a.json",
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "keep_me",
            "source_class": "repo_authored",
            "source_ref": "repo://keep_me",
            "license_note": "repo",
            "dialogue_frame_target": "initiative_followup_medium_reserve",
            "messages": ["a", "b"],
            "idle_seconds": 600.0,
        },
    )
    _write_manifest(
        tmp_path / "b.json",
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "drop_me",
            "source_class": "repo_authored",
            "source_ref": "repo://drop_me",
            "license_note": "repo",
            "dialogue_frame_target": "delivery_failure_hold_review",
            "messages": ["a", "b"],
            "idle_seconds": 600.0,
        },
    )

    scenarios = load_scenario_bank(tmp_path, scenario_ids=["keep_me"])

    assert [item["scenario_id"] for item in scenarios] == ["keep_me"]
