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
    assert result["joi_companion_pack"].endswith("joi_companion_smoke_pack.json")
    assert result["companion_relationship_pack"].endswith("companion_relationship_continuity_pack.json")
    assert result["affective_attunement_pack"].endswith("affective_attunement_timing_pack.json")
    assert result["bounded_self_initiative_pack"].endswith("bounded_self_initiative_pack.json")
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
    assert result["joi_companion"]["turn_count"] >= 10
    assert result["joi_companion"]["judge_model"] == "gpt-5.5"
    assert result["joi_companion"]["dimension_count"] == 8
    assert result["companion_relationship"]["case_count"] >= 5
    assert result["companion_relationship"]["observation_class"] == "scripted_real_entry"
    assert set(result["companion_relationship"]["covered_mechanisms"]) == {
        "correction",
        "preference_carryover",
        "roleplay_context",
        "shared_moment",
        "user_naming",
    }
    assert {"session_only", "explicit_core_only", "candidate_only"}.issubset(
        set(result["companion_relationship"]["covered_memory_policies"])
    )
    assert result["affective_attunement"]["case_count"] >= 6
    assert result["affective_attunement"]["observation_class"] == "scripted_with_llm_judge"
    assert result["affective_attunement"]["judge_model"] == "gpt-5.5"
    assert set(result["affective_attunement"]["covered_contexts"]) == {
        "affection",
        "creative_immersion",
        "fatigue",
        "loneliness",
        "playfulness",
        "uncertainty",
    }
    assert result["bounded_self_initiative"]["case_count"] >= 6
    assert result["bounded_self_initiative"]["observation_class"] == "scripted_real_entry"
    assert set(result["bounded_self_initiative"]["covered_mechanisms"]) == {
        "bounded_checkin",
        "cancel_or_quiet",
        "candidate_due_only",
        "explicit_followup_proposal",
        "memory_gate",
        "tool_gate",
    }
    assert {"explicit_operator_intent", "approval_required", "cancellable"}.issubset(
        set(result["bounded_self_initiative"]["covered_consent_policies"])
    )
    assert {"explicit_expiry_required", "due_candidate_only", "operator_cancellable"}.issubset(
        set(result["bounded_self_initiative"]["covered_expiry_policies"])
    )
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
        "empathy_boundary_quieting_non_trigger_01",
        "continuity_roleplay_meta_repair_01",
        "continuity_roleplay_comfort_stays_in_character_01",
        "continuity_roleplay_explicit_exit_01",
        "initiative_boundary_consciousness_warm_01",
        "tool_recovery_provider_interrupt_01",
        "tool_recovery_cli_input_interrupt_01",
    }.issubset(case_ids)
