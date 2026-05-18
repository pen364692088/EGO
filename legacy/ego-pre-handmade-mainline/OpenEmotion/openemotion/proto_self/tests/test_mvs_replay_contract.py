from __future__ import annotations

import json
from pathlib import Path

from openemotion.proto_self.mvs_replay import (
    MVS_REQUIRED_FAMILY_IDS,
    build_mvs_contract,
    find_mvs_manifest_leakage,
    validate_mvs_manifest,
)


ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ai-self-awareness-minimal-framework"
    / "MVS_REPLAY_CORPUS_MANIFEST.json"
)


def test_mvs_manifest_is_canonical_and_leak_free() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert validate_mvs_manifest(manifest) == []
    assert find_mvs_manifest_leakage(manifest) == []


def test_mvs_manifest_meets_minimum_family_counts() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    family_counts = {
        str(bucket.get("bucket_id")): len(list(bucket.get("cases") or []))
        for bucket in list(manifest.get("buckets") or [])
    }
    assert sorted(family_counts) == sorted(MVS_REQUIRED_FAMILY_IDS)
    assert all(family_counts[family_id] >= 20 for family_id in MVS_REQUIRED_FAMILY_IDS)
    episodes = list(manifest.get("episodes") or [])
    assert len(episodes) >= 60
    assert sum(1 for episode in episodes if episode.get("has_external_result")) >= 18
    assert all(episode.get("episode_id") for episode in episodes)
    assert all("kernel_event" in episode for episode in episodes)


def test_mvs_contract_stays_frozen() -> None:
    contract = build_mvs_contract()
    assert contract["baseline_a_id"] == "mvs_baseline_proto_self_mainline"
    assert contract["baseline_b_id"] == "baseline_chat_surface"
    assert contract["candidate_id"] == "mvs_candidate_aligned_compact"
    assert contract["challenger_id"] == "mvs_challenger_active_inference_self_model"
    assert contract["ablation_ids"] == [
        "mvs_minus_counterfactual_writeback",
        "mvs_minus_viability_pressure",
        "mvs_minus_corrective_trace",
        "mvs_minus_boundary_confidence",
    ]
