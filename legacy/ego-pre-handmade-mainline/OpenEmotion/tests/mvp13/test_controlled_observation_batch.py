from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
TOOLS_ROOT = ROOT / "OpenEmotion" / "tools"
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from mvp13_scenario_bank import (  # noqa: E402
    SCENARIO_MANIFEST_SCHEMA_VERSION,
    load_scenario_bank,
    load_scenario_manifest,
    validate_scenario_manifest,
)
from run_mvp13_controlled_observation_batch import run_controlled_observation_batch  # noqa: E402


def _write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_validate_scenario_manifest_rejects_missing_fields():
    errors = validate_scenario_manifest(
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "broken_case",
            "source_class": "open_license",
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
            "dialogue_frame_target": "definition_gap",
            "messages": ["What is this?", "Can you explain more?"],
            "idle_seconds": 900.0,
        },
    )

    with pytest.raises(ValueError, match="source_class"):
        load_scenario_manifest(manifest_path)


@pytest.mark.asyncio
async def test_batch_controlled_observation_runs_and_aggregates(tmp_path):
    bank_dir = tmp_path / "bank"
    _write_manifest(
        bank_dir / "repo.json",
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "repo_case",
            "source_class": "repo_authored",
            "source_ref": "repo://repo_case",
            "license_note": "repo authored",
            "dialogue_frame_target": "continuity_gap",
            "messages": [
                "如果记忆一直在，但每次处理它的主体都重新生成，那还是同一个自我吗？",
                "我怀疑我们把记忆误当成了持续存在的证明。",
                "你觉得呢",
            ],
            "idle_seconds": 900.0,
        },
    )
    _write_manifest(
        bank_dir / "license_a.json",
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "open_case_a",
            "source_class": "open_license",
            "source_ref": "https://huggingface.co/datasets/example_a",
            "license_note": "MIT",
            "dialogue_frame_target": "mechanism_gap",
            "messages": [
                "How could a tracking system be implemented in schools?",
                "What benefits would it provide to students who are not pursuing science careers?",
                "What would make that implementation actually work in practice?",
            ],
            "idle_seconds": 900.0,
        },
    )
    _write_manifest(
        bank_dir / "license_b.json",
        {
            "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
            "scenario_id": "open_case_b",
            "source_class": "open_license",
            "source_ref": "https://huggingface.co/datasets/example_b",
            "license_note": "Apache-2.0",
            "dialogue_frame_target": "definition_gap",
            "messages": [
                "What is a monopsony in economics?",
                "How can workers push back once a monopsony exists?",
                "What should regulators do to prevent abuse in that situation?",
            ],
            "idle_seconds": 900.0,
        },
    )

    payload = await run_controlled_observation_batch(
        bank_dir=bank_dir,
        output_json=tmp_path / "current_batch.json",
        artifacts_root=tmp_path / "artifacts",
    )

    assert payload["report_count"] == 3
    assert payload["accepted_count"] == 3
    assert payload["replay_consistent_count"] == 3
    assert payload["invariant_violation_count"] == 0
    assert payload["status"] == "pass"
    assert payload["verification_level"] == "V5"
    assert payload["evidence_level"] == "E5"
    assert set(payload["source_breakdown"]) == {"repo_authored", "open_license"}
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
            "dialogue_frame_target": "continuity_gap",
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
            "dialogue_frame_target": "definition_gap",
            "messages": ["a", "b"],
            "idle_seconds": 600.0,
        },
    )

    scenarios = load_scenario_bank(tmp_path, scenario_ids=["keep_me"])

    assert [item["scenario_id"] for item in scenarios] == ["keep_me"]
