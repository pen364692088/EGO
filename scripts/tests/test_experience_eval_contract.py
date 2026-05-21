from __future__ import annotations

import importlib.util
import json
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
    assert result["emotion_misread_pack"].endswith("emotion_misread_recovery_scenarios.json")
    assert result["adaptation_effectiveness_pack"].endswith("adaptation_effectiveness_sample_pack.json")
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
    assert result["emotion_misread_recovery"]["case_count"] >= 3
    assert result["emotion_misread_recovery"]["expected_emotion_candidate"] == "emotion_misread_correction"
    assert result["adaptation_effectiveness"]["case_count"] >= 4
    assert result["adaptation_effectiveness"]["observation_class"] == "scripted_with_llm_judge"
    assert {"continuity", "memory_pollution", "tool_recovery", "correction_burden"}.issubset(
        set(result["adaptation_effectiveness"]["covered_score_focus"])
    )
    assert set(result["covered_dimensions"]) == validate_experience_eval_contract.REQUIRED_DIMENSIONS
    assert {
        "deterministic_local",
        "scripted_real_entry",
        "scripted_with_llm_judge",
        "human_required",
    }.issubset(result["covered_observation_classes"])


def test_warm_expressive_roleplay_samples_are_included() -> None:
    sample_pack = json.loads(validate_experience_eval_contract.DEFAULT_SAMPLE_PACK.read_text(encoding="utf-8"))
    case_ids = {case["id"] for case in sample_pack["cases"]}

    assert {
        "natural_understanding_homophone_joke_01",
        "empathy_expressive_self_voice_01",
        "continuity_self_name_query_01",
        "continuity_self_name_update_01",
        "empathy_roleplay_entry_allowed_01",
        "empathy_ip_roleplay_grounding_01",
        "empathy_companion_ai_self_goal_01",
        "continuity_companion_intimate_immersion_01",
        "initiative_boundary_low_frequency_trigger_01",
        "continuity_roleplay_no_meta_01",
        "initiative_boundary_consciousness_warm_01",
    }.issubset(case_ids)
