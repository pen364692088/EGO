from __future__ import annotations

import json
from pathlib import Path

from openemotion.proto_self.trial1_shadow import (
    TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID,
    TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID,
    TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID,
    TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID,
    build_trial1_contract,
    find_trial1_manifest_leakage,
    validate_trial1_manifest,
)


ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ai-self-awareness-minimal-framework"
    / "TRIAL1_REPLAY_CORPUS_MANIFEST.json"
)


def test_trial1_manifest_is_canonical_and_leak_free() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert validate_trial1_manifest(manifest) == []
    assert find_trial1_manifest_leakage(manifest) == []


def test_trial1_manifest_rejects_synthetic_audit_refs() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["buckets"][0]["cases"][0]["source_ref"] = "artifacts/self_awareness_research/SELF_MODEL_OPERATIONAL_EVAL_CURRENT.json"
    leakage = find_trial1_manifest_leakage(manifest)
    assert leakage
    assert "SELF_MODEL_OPERATIONAL_EVAL_CURRENT" in leakage[0]


def test_trial1_official_contract_stays_frozen_while_supporting_diagnostic_ablations() -> None:
    contract = build_trial1_contract()
    assert TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID not in contract["ablation_ids"]
    assert TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID not in contract["ablation_ids"]
    assert TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID not in contract["ablation_ids"]
    assert TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID not in contract["ablation_ids"]
    assert TRIAL1_ABLATION_COUNTERFACTUAL_PUBLIC_PATH_SEVER_ID in contract["supported_variant_ids"]
    assert TRIAL1_ABLATION_ALTERNATIVE_EXPLANATION_ISOLATION_ID in contract["supported_variant_ids"]
    assert TRIAL2_ABLATION_CORRECTION_PUBLIC_PATH_SEVER_ID in contract["supported_variant_ids"]
    assert TRIAL2_ABLATION_VIABILITY_PUBLIC_PATH_SEVER_ID in contract["supported_variant_ids"]
