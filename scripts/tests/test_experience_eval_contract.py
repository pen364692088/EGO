from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "validate_experience_eval_contract.py"
spec = importlib.util.spec_from_file_location("validate_experience_eval_contract", MODULE_PATH)
validate_experience_eval_contract = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = validate_experience_eval_contract
spec.loader.exec_module(validate_experience_eval_contract)


def test_experience_eval_contract_is_valid() -> None:
    result = validate_experience_eval_contract.validate_sample_pack()

    assert result["status"] == "ok"
    assert result["case_count"] >= 20
    assert result["dimension_count"] == 7
    assert result["claim_state_count"] == 7
    assert result["claim_calibration"].endswith("CLAIM_CEILING_CALIBRATION.md")
    assert result["continuity_regression_pack"].endswith("continuity_regression_pack.json")
    assert result["negative_emotion_pack"].endswith("negative_emotion_support_scenarios.json")
    assert result["continuity_regression"]["paraphrase_group_count"] >= 4
    assert result["continuity_regression"]["carryover_case_count"] >= 4
    assert result["continuity_regression"]["paraphrase_prompt_count"] >= 12
    assert result["negative_emotion_support"]["case_count"] >= 4
    assert set(result["negative_emotion_support"]["covered_emotion_candidates"]) == {
        "disappointment",
        "frustration",
        "uncertainty",
        "urgency",
    }
    assert set(result["covered_dimensions"]) == validate_experience_eval_contract.REQUIRED_DIMENSIONS
    assert {
        "deterministic_local",
        "scripted_real_entry",
        "scripted_with_llm_judge",
        "human_required",
    }.issubset(result["covered_observation_classes"])
