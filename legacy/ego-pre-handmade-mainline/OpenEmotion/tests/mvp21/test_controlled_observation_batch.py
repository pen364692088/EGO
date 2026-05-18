from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = ROOT / "OpenEmotion" / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from mvp21_scenario_bank import (  # noqa: E402
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
            "dialogue_frame_target": "realization_followup_review",
            "messages": ["What is this?", "Can you explain more?"],
            "idle_seconds": 900.0,
        },
    )

    with pytest.raises(ValueError, match="source_class"):
        load_scenario_manifest(manifest_path)


@pytest.mark.asyncio
async def test_batch_controlled_observation_runs_and_aggregates(tmp_path, monkeypatch):
    from run_mvp21_controlled_observation_batch import run_controlled_observation_batch

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
            "dialogue_frame_target": "realization_followup_review",
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
            "dialogue_frame_target": "commitment_fulfillment_prepare_review",
        },
    )

    async def _fake_run_controlled_observation(**kwargs):
        scenario = dict(kwargs.get("scenario_manifest") or {})
        selected_modes = {
            "repo_case_a": "review",
            "repo_case_b": "review",
            "repo_case_c": "review",
        }
        selected_lanes = {
            "repo_case_a": "review",
            "repo_case_b": "review",
            "repo_case_c": "review",
        }
        lane_hints = {
            "repo_case_a": ["host_reality_review", "host_continuity_queue"],
            "repo_case_b": ["host_reality_review", "host_failure_repair_queue"],
            "repo_case_c": ["host_continuity_queue", "host_reality_review"],
        }
        return {
            "status": "pass",
            "replay_valid": True,
            "initiative_realization_proposal_present": True,
            "proposal_only_discipline_consistent": True,
            "behavioral_authority_none": True,
            "bounded_influence_present": True,
            "initiative_realization_writeback_gate": "allow_writeback",
            "selected_mode": selected_modes[scenario["scenario_id"]],
            "selected_lane": selected_lanes[scenario["scenario_id"]],
            "host_lane_hints": lane_hints[scenario["scenario_id"]],
            "initiative_realization_delta": {
                "surface_reasons": [
                    "low_realization_readiness",
                    "low_fulfillment_readiness",
                ]
            },
        }

    monkeypatch.setattr(
        "run_mvp21_controlled_observation_batch.run_controlled_observation",
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
    assert payload["initiative_realization_proposal_present_count"] == 3
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
            "dialogue_frame_target": "realization_followup_review",
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
