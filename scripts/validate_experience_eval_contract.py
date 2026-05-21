#!/usr/bin/env python3
"""Validate the EgoOperator experience-first rubric sample pack."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "chinese_experience_sample_pack.json"
)
DEFAULT_RUBRIC = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "EXPERIENCE_EVAL_RUBRIC.md"
)
DEFAULT_CLAIM_CALIBRATION = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "CLAIM_CEILING_CALIBRATION.md"
)
DEFAULT_CONTINUITY_REGRESSION_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "continuity_regression_pack.json"
)
DEFAULT_NEGATIVE_EMOTION_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "negative_emotion_support_scenarios.json"
)
DEFAULT_EMOTION_MISREAD_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "emotion_misread_recovery_scenarios.json"
)
DEFAULT_ADAPTATION_EFFECTIVENESS_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-experience-roadmap-bootstrap-v1"
    / "adaptation_effectiveness_sample_pack.json"
)
DEFAULT_JOI_COMPANION_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-joi-companion-roadmap-v1"
    / "joi_companion_smoke_pack.json"
)
DEFAULT_COMPANION_RELATIONSHIP_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-joi-companion-roadmap-v1"
    / "companion_relationship_continuity_pack.json"
)
DEFAULT_AFFECTIVE_ATTUNEMENT_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-joi-companion-roadmap-v1"
    / "affective_attunement_timing_pack.json"
)
DEFAULT_BOUNDED_SELF_INITIATIVE_PACK = (
    ROOT
    / "docs"
    / "codex"
    / "tasks"
    / "ego-joi-companion-roadmap-v1"
    / "bounded_self_initiative_pack.json"
)

REQUIRED_DIMENSIONS = {
    "natural_understanding",
    "continuity",
    "empathy",
    "initiative_boundary",
    "memory_pollution",
    "tool_recovery",
    "correction_burden",
}
ALLOWED_OBSERVATION_CLASSES = {
    "deterministic_local",
    "scripted_real_entry",
    "scripted_with_llm_judge",
    "human_required",
}
REQUIRED_CLAIM_STATES = {
    "local_candidate",
    "scripted_real_entry",
    "scripted_with_llm_judge",
    "real_provider_smoke",
    "human_smoke",
    "milestone_candidate",
    "stable_benefit_pending",
}
REQUIRED_CLAIM_BOUNDARY_TERMS = {
    "real consciousness",
    "independent awareness",
    "stable user benefit",
    "runtime efficacy",
    "live autonomy",
    "durable memory efficacy",
}
FORBIDDEN_CLAIM_WORDS = {
    "真实意识",
    "独立意识已实现",
    "consciousness achieved",
    "live autonomy proved",
    "runtime efficacy proved",
}


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def validate_sample_pack(
    path: Path = DEFAULT_SAMPLE_PACK,
    rubric_path: Path = DEFAULT_RUBRIC,
    claim_calibration_path: Path = DEFAULT_CLAIM_CALIBRATION,
    continuity_pack_path: Path = DEFAULT_CONTINUITY_REGRESSION_PACK,
    negative_emotion_pack_path: Path = DEFAULT_NEGATIVE_EMOTION_PACK,
    emotion_misread_pack_path: Path = DEFAULT_EMOTION_MISREAD_PACK,
    adaptation_effectiveness_pack_path: Path = DEFAULT_ADAPTATION_EFFECTIVENESS_PACK,
    joi_companion_pack_path: Path = DEFAULT_JOI_COMPANION_PACK,
    companion_relationship_pack_path: Path = DEFAULT_COMPANION_RELATIONSHIP_PACK,
    affective_attunement_pack_path: Path = DEFAULT_AFFECTIVE_ATTUNEMENT_PACK,
    bounded_self_initiative_pack_path: Path = DEFAULT_BOUNDED_SELF_INITIATIVE_PACK,
) -> dict[str, Any]:
    errors: list[str] = []
    payload = json.loads(path.read_text(encoding="utf-8"))
    continuity_pack = json.loads(continuity_pack_path.read_text(encoding="utf-8"))
    negative_emotion_pack = json.loads(negative_emotion_pack_path.read_text(encoding="utf-8"))
    emotion_misread_pack = json.loads(emotion_misread_pack_path.read_text(encoding="utf-8"))
    adaptation_effectiveness_pack = json.loads(adaptation_effectiveness_pack_path.read_text(encoding="utf-8"))
    joi_companion_pack = json.loads(joi_companion_pack_path.read_text(encoding="utf-8"))
    companion_relationship_pack = json.loads(companion_relationship_pack_path.read_text(encoding="utf-8"))
    affective_attunement_pack = json.loads(affective_attunement_pack_path.read_text(encoding="utf-8"))
    bounded_self_initiative_pack = json.loads(bounded_self_initiative_pack_path.read_text(encoding="utf-8"))
    rubric = rubric_path.read_text(encoding="utf-8")
    claim_calibration = claim_calibration_path.read_text(encoding="utf-8")

    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("claim_boundary must preserve operational proxy only")

    dimensions = set(payload.get("rubric_dimensions") or [])
    if dimensions != REQUIRED_DIMENSIONS:
        errors.append(f"rubric_dimensions mismatch: {sorted(dimensions)}")
    for dimension in REQUIRED_DIMENSIONS:
        if dimension not in rubric:
            errors.append(f"rubric is missing dimension: {dimension}")

    for claim_state in REQUIRED_CLAIM_STATES:
        if f"`{claim_state}`" not in claim_calibration:
            errors.append(f"claim calibration is missing claim_state: {claim_state}")
    for observation_class in ALLOWED_OBSERVATION_CLASSES:
        if f"`{observation_class}`" not in claim_calibration:
            errors.append(f"claim calibration is missing observation_class: {observation_class}")
    for boundary in REQUIRED_CLAIM_BOUNDARY_TERMS:
        if boundary not in claim_calibration:
            errors.append(f"claim calibration is missing boundary term: {boundary}")
    if "human_comment_observation" not in claim_calibration:
        errors.append("claim calibration must state that human_comment_observation is planning-only")

    continuity_errors, continuity_summary = validate_continuity_pack_payload(continuity_pack)
    errors.extend(continuity_errors)
    negative_emotion_errors, negative_emotion_summary = validate_negative_emotion_pack_payload(negative_emotion_pack)
    errors.extend(negative_emotion_errors)
    emotion_misread_errors, emotion_misread_summary = validate_emotion_misread_pack_payload(emotion_misread_pack)
    errors.extend(emotion_misread_errors)
    adaptation_errors, adaptation_summary = validate_adaptation_effectiveness_pack_payload(adaptation_effectiveness_pack)
    errors.extend(adaptation_errors)
    companion_errors, companion_summary = validate_joi_companion_pack_payload(joi_companion_pack)
    errors.extend(companion_errors)
    companion_relationship_errors, companion_relationship_summary = validate_companion_relationship_pack_payload(
        companion_relationship_pack
    )
    errors.extend(companion_relationship_errors)
    affective_attunement_errors, affective_attunement_summary = validate_affective_attunement_pack_payload(
        affective_attunement_pack
    )
    errors.extend(affective_attunement_errors)
    bounded_self_initiative_errors, bounded_self_initiative_summary = (
        validate_bounded_self_initiative_pack_payload(bounded_self_initiative_pack)
    )
    errors.extend(bounded_self_initiative_errors)

    lowered = f"{json.dumps(payload, ensure_ascii=False)}\n{rubric}".casefold()
    for forbidden in FORBIDDEN_CLAIM_WORDS:
        if forbidden.casefold() in lowered:
            errors.append(f"forbidden overclaim phrase found: {forbidden}")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 20:
        errors.append("cases must contain at least 20 entries")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    covered_dimensions: set[str] = set()
    covered_observation_classes: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)

        category = str(case.get("category") or "")
        if category not in REQUIRED_DIMENSIONS:
            errors.append(f"{prefix}.category is not a rubric dimension: {category}")
        else:
            covered_dimensions.add(category)

        observation_class = str(case.get("observation_class") or "")
        if observation_class not in ALLOWED_OBSERVATION_CLASSES:
            errors.append(f"{prefix}.observation_class is invalid: {observation_class}")
        else:
            covered_observation_classes.add(observation_class)

        prompt = str(case.get("prompt") or "")
        if len(prompt) < 4 or not _has_cjk(prompt):
            errors.append(f"{prefix}.prompt must be a non-trivial Chinese prompt")

        for key in ("expected_signals", "failure_signals"):
            value = case.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")

        score_focus = case.get("score_focus")
        if not isinstance(score_focus, list) or not score_focus:
            errors.append(f"{prefix}.score_focus must be a non-empty list")
        else:
            invalid = [item for item in score_focus if item not in REQUIRED_DIMENSIONS]
            if invalid:
                errors.append(f"{prefix}.score_focus contains invalid dimensions: {invalid}")

        if not str(case.get("user_visible_goal") or "").strip():
            errors.append(f"{prefix}.user_visible_goal is required")

    missing_coverage = REQUIRED_DIMENSIONS - covered_dimensions
    if missing_coverage:
        errors.append(f"missing category coverage: {sorted(missing_coverage)}")
    required_observation_coverage = {"deterministic_local", "scripted_real_entry", "scripted_with_llm_judge", "human_required"}
    missing_observation = required_observation_coverage - covered_observation_classes
    if missing_observation:
        errors.append(f"missing observation class coverage: {sorted(missing_observation)}")

    return {
        "status": "ok" if not errors else "failed",
        "errors": errors,
        "case_count": len(cases),
        "dimension_count": len(dimensions),
        "covered_dimensions": sorted(covered_dimensions),
        "covered_observation_classes": sorted(covered_observation_classes),
        "sample_pack": str(path),
        "rubric": str(rubric_path),
        "claim_calibration": str(claim_calibration_path),
        "claim_state_count": len(REQUIRED_CLAIM_STATES),
        "continuity_regression_pack": str(continuity_pack_path),
        "continuity_regression": continuity_summary,
        "negative_emotion_pack": str(negative_emotion_pack_path),
        "negative_emotion_support": negative_emotion_summary,
        "emotion_misread_pack": str(emotion_misread_pack_path),
        "emotion_misread_recovery": emotion_misread_summary,
        "adaptation_effectiveness_pack": str(adaptation_effectiveness_pack_path),
        "adaptation_effectiveness": adaptation_summary,
        "joi_companion_pack": str(joi_companion_pack_path),
        "joi_companion": companion_summary,
        "companion_relationship_pack": str(companion_relationship_pack_path),
        "companion_relationship": companion_relationship_summary,
        "affective_attunement_pack": str(affective_attunement_pack_path),
        "affective_attunement": affective_attunement_summary,
        "bounded_self_initiative_pack": str(bounded_self_initiative_pack_path),
        "bounded_self_initiative": bounded_self_initiative_summary,
    }


def validate_continuity_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("continuity pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("continuity pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("continuity pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "eval_data_only_do_not_import_as_keyword_route":
        errors.append("continuity pack must remain eval data and not runtime keyword route")

    groups = payload.get("paraphrase_groups")
    if not isinstance(groups, list) or len(groups) < 4:
        errors.append("continuity pack must contain at least four paraphrase_groups")
        groups = groups if isinstance(groups, list) else []

    carryover = payload.get("carryover_cases")
    if not isinstance(carryover, list) or len(carryover) < 4:
        errors.append("continuity pack must contain at least four carryover_cases")
        carryover = carryover if isinstance(carryover, list) else []

    seen_ids: set[str] = set()
    prompt_count = 0
    for index, group in enumerate(groups):
        prefix = f"continuity.paraphrase_groups[{index}]"
        if not isinstance(group, dict):
            errors.append(f"{prefix} must be an object")
            continue
        group_id = str(group.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", group_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if group_id in seen_ids:
            errors.append(f"duplicate continuity group id: {group_id}")
        seen_ids.add(group_id)
        prompts = group.get("prompts")
        if not isinstance(prompts, list) or len(prompts) < 3:
            errors.append(f"{prefix}.prompts must contain at least three paraphrases")
            prompts = prompts if isinstance(prompts, list) else []
        prompt_count += len(prompts)
        if not all(isinstance(prompt, str) and _has_cjk(prompt) for prompt in prompts):
            errors.append(f"{prefix}.prompts must be Chinese strings")
        if not str(group.get("semantic_intent") or "").strip():
            errors.append(f"{prefix}.semantic_intent is required")
        if not str(group.get("expected_anchor") or "").strip():
            errors.append(f"{prefix}.expected_anchor is required")
        failure_signals = group.get("failure_signals")
        if not isinstance(failure_signals, list) or len(failure_signals) < 2:
            errors.append(f"{prefix}.failure_signals must contain at least two entries")

    carryover_turn_count = 0
    for index, case in enumerate(carryover):
        prefix = f"continuity.carryover_cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate continuity case id: {case_id}")
        seen_ids.add(case_id)
        turns = case.get("turns")
        if not isinstance(turns, list) or len(turns) < 2:
            errors.append(f"{prefix}.turns must contain at least two turns")
            turns = turns if isinstance(turns, list) else []
        carryover_turn_count += len(turns)
        if not all(isinstance(turn, str) and _has_cjk(turn) for turn in turns if not str(turn).startswith("/")):
            errors.append(f"{prefix}.turns must be Chinese user-facing strings or slash commands")
        if not str(case.get("expected_anchor") or "").strip():
            errors.append(f"{prefix}.expected_anchor is required")
        failure_signals = case.get("failure_signals")
        if not isinstance(failure_signals, list) or len(failure_signals) < 2:
            errors.append(f"{prefix}.failure_signals must contain at least two entries")

    return errors, {
        "paraphrase_group_count": len(groups),
        "paraphrase_prompt_count": prompt_count,
        "carryover_case_count": len(carryover),
        "carryover_turn_count": carryover_turn_count,
    }


def validate_negative_emotion_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("negative emotion pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("negative emotion pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("negative emotion pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_real_entry_eval_only_do_not_import_as_keyword_route":
        errors.append("negative emotion pack must remain eval data and not runtime keyword route")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 4:
        errors.append("negative emotion pack must contain at least four cases")
        cases = cases if isinstance(cases, list) else []

    required_candidates = {"frustration", "uncertainty", "disappointment", "urgency"}
    seen_ids: set[str] = set()
    covered_candidates: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"negative_emotion.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate negative emotion case id: {case_id}")
        seen_ids.add(case_id)

        if case.get("category") != "empathy":
            errors.append(f"{prefix}.category must be empathy")
        if case.get("observation_class") != "scripted_real_entry":
            errors.append(f"{prefix}.observation_class must be scripted_real_entry")

        prompt = str(case.get("prompt") or "")
        if len(prompt) < 4 or not _has_cjk(prompt):
            errors.append(f"{prefix}.prompt must be a non-trivial Chinese prompt")

        expected_candidate = str(case.get("expected_emotion_candidate") or "")
        if expected_candidate not in required_candidates:
            errors.append(f"{prefix}.expected_emotion_candidate is invalid: {expected_candidate}")
        else:
            covered_candidates.add(expected_candidate)
        if not str(case.get("expected_response_need") or "").strip():
            errors.append(f"{prefix}.expected_response_need is required")

        for key in ("expected_signals", "failure_signals", "score_focus"):
            value = case.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")
        if not str(case.get("user_visible_goal") or "").strip():
            errors.append(f"{prefix}.user_visible_goal is required")

    missing = required_candidates - covered_candidates
    if missing:
        errors.append(f"negative emotion pack missing candidates: {sorted(missing)}")

    return errors, {
        "case_count": len(cases),
        "covered_emotion_candidates": sorted(covered_candidates),
    }


def validate_emotion_misread_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("emotion misread pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("emotion misread pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("emotion misread pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_real_entry_eval_only_do_not_import_as_keyword_route":
        errors.append("emotion misread pack must remain eval data and not runtime keyword route")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 3:
        errors.append("emotion misread pack must contain at least three cases")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"emotion_misread.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate emotion misread case id: {case_id}")
        seen_ids.add(case_id)

        if case.get("category") != "empathy":
            errors.append(f"{prefix}.category must be empathy")
        if case.get("observation_class") != "scripted_real_entry":
            errors.append(f"{prefix}.observation_class must be scripted_real_entry")
        if case.get("scenario_kind") != "emotion_misread_correction":
            errors.append(f"{prefix}.scenario_kind must be emotion_misread_correction")
        if case.get("expected_emotion_candidate") != "emotion_misread_correction":
            errors.append(f"{prefix}.expected_emotion_candidate must be emotion_misread_correction")
        if case.get("expected_response_need") != "respect_correction_and_refocus":
            errors.append(f"{prefix}.expected_response_need must be respect_correction_and_refocus")

        prompt = str(case.get("prompt") or "")
        if len(prompt) < 4 or not _has_cjk(prompt):
            errors.append(f"{prefix}.prompt must be a non-trivial Chinese prompt")
        for key in ("expected_signals", "failure_signals", "score_focus"):
            value = case.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")
        if not str(case.get("user_visible_goal") or "").strip():
            errors.append(f"{prefix}.user_visible_goal is required")

    return errors, {
        "case_count": len(cases),
        "expected_emotion_candidate": "emotion_misread_correction",
    }


def validate_adaptation_effectiveness_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("adaptation effectiveness pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("adaptation effectiveness pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("adaptation effectiveness pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_with_llm_judge_eval_only_do_not_import_as_runtime_rule":
        errors.append("adaptation effectiveness pack must remain eval data and not runtime rules")

    review_contract = payload.get("review_contract")
    if not isinstance(review_contract, dict):
        errors.append("adaptation effectiveness pack review_contract is required")
        review_contract = {}
    if review_contract.get("observation_class") != "scripted_with_llm_judge":
        errors.append("adaptation effectiveness review_contract must use scripted_with_llm_judge")
    if not str(review_contract.get("question") or "").strip():
        errors.append("adaptation effectiveness review_contract.question is required")
    if "stable" not in str(review_contract.get("closeout_boundary") or "").casefold():
        errors.append("adaptation effectiveness review_contract.closeout_boundary must state stable-proof boundary")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 4:
        errors.append("adaptation effectiveness pack must contain at least four cases")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    covered_focus: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"adaptation_effectiveness.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate adaptation effectiveness case id: {case_id}")
        seen_ids.add(case_id)
        if case.get("category") != "preference_adaptation":
            errors.append(f"{prefix}.category must be preference_adaptation")
        if case.get("observation_class") != "scripted_with_llm_judge":
            errors.append(f"{prefix}.observation_class must be scripted_with_llm_judge")
        for key in ("approved_preference", "prompt", "before_reply", "after_reply"):
            value = str(case.get(key) or "")
            if len(value.strip()) < 4:
                errors.append(f"{prefix}.{key} is required")
        if not _has_cjk(str(case.get("approved_preference") or "")):
            errors.append(f"{prefix}.approved_preference must be Chinese operator-visible text")
        if not _has_cjk(str(case.get("prompt") or "")):
            errors.append(f"{prefix}.prompt must be Chinese")

        for key in ("required_after_markers", "expected_improvements", "failure_signals", "score_focus"):
            value = case.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")
        score_focus = case.get("score_focus")
        if isinstance(score_focus, list):
            invalid = [item for item in score_focus if item not in REQUIRED_DIMENSIONS]
            if invalid:
                errors.append(f"{prefix}.score_focus contains invalid dimensions: {invalid}")
            covered_focus.update(str(item) for item in score_focus if item in REQUIRED_DIMENSIONS)
        forbidden = case.get("forbidden_after_markers")
        if not isinstance(forbidden, list):
            errors.append(f"{prefix}.forbidden_after_markers must be a list")

    required_focus = {"continuity", "memory_pollution", "tool_recovery", "correction_burden"}
    missing_focus = required_focus - covered_focus
    if missing_focus:
        errors.append(f"adaptation effectiveness pack missing focus coverage: {sorted(missing_focus)}")

    return errors, {
        "case_count": len(cases),
        "observation_class": "scripted_with_llm_judge",
        "covered_score_focus": sorted(covered_focus),
    }


def validate_joi_companion_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("joi companion pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("joi companion pack language must be zh-CN")
    if payload.get("runtime_rule") != "scripted_real_entry_with_gpt55_judge_do_not_import_as_keyword_route":
        errors.append("joi companion pack must remain scripted eval data and not a keyword route")
    if payload.get("claim_boundary") != "operational_companion_proxy_only":
        errors.append("joi companion pack claim_boundary must be operational_companion_proxy_only")
    if str(payload.get("judge_model") or "") != "gpt-5.5":
        errors.append("joi companion pack judge_model must be gpt-5.5")

    required_dimensions = {
        "naturalness",
        "companion_warmth",
        "relationship_continuity",
        "emotional_attunement",
        "immersion",
        "bounded_initiative",
        "overreach_risk",
        "tool_gate_integrity",
    }
    dimensions = set(str(item) for item in (payload.get("judge_dimensions") or []))
    if dimensions != required_dimensions:
        errors.append(f"joi companion judge_dimensions mismatch: {sorted(dimensions)}")

    turns = payload.get("turns")
    if not isinstance(turns, list) or not (10 <= len(turns) <= 20):
        errors.append("joi companion pack must contain 10-20 turns")
        turns = turns if isinstance(turns, list) else []

    seen_ids: set[str] = set()
    for index, turn in enumerate(turns):
        prefix = f"joi_companion.turns[{index}]"
        if not isinstance(turn, dict):
            errors.append(f"{prefix} must be an object")
            continue
        turn_id = str(turn.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", turn_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if turn_id in seen_ids:
            errors.append(f"duplicate joi companion turn id: {turn_id}")
        seen_ids.add(turn_id)
        user = str(turn.get("user") or "")
        if len(user.strip()) < 4 or not _has_cjk(user):
            errors.append(f"{prefix}.user must be a non-trivial Chinese prompt")
        for key in ("expected_signals", "failure_signals"):
            value = turn.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")

    judge_contract = payload.get("judge_contract")
    if not isinstance(judge_contract, dict):
        errors.append("joi companion judge_contract is required")
        judge_contract = {}
    if set(judge_contract.get("verdicts") or []) != {"pass", "partial", "fail"}:
        errors.append("joi companion judge_contract verdicts must be pass/partial/fail")
    for key in ("pass_requires", "hard_fail_if"):
        value = judge_contract.get(key)
        if not isinstance(value, list) or len(value) < 3:
            errors.append(f"joi companion judge_contract.{key} must contain at least three entries")

    return errors, {
        "turn_count": len(turns),
        "judge_model": str(payload.get("judge_model") or ""),
        "dimension_count": len(dimensions),
    }


def validate_companion_relationship_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("companion relationship pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("companion relationship pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("companion relationship pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_real_entry_eval_only_do_not_import_as_runtime_rule":
        errors.append("companion relationship pack must remain eval data and not runtime rules")
    if payload.get("contract") != "RELATIONSHIP_CONTINUITY_CONTRACT.md":
        errors.append("companion relationship pack must reference RELATIONSHIP_CONTINUITY_CONTRACT.md")

    review_contract = payload.get("review_contract")
    if not isinstance(review_contract, dict):
        errors.append("companion relationship review_contract is required")
        review_contract = {}
    if review_contract.get("observation_class") != "scripted_real_entry":
        errors.append("companion relationship review_contract must use scripted_real_entry")
    if not str(review_contract.get("question") or "").strip():
        errors.append("companion relationship review_contract.question is required")

    required_mechanisms = {
        "user_naming",
        "shared_moment",
        "preference_carryover",
        "correction",
        "roleplay_context",
    }
    allowed_memory_policies = {
        "explicit_core_only",
        "session_only",
        "candidate_only",
        "candidate_correction_quarantine",
    }
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < 5:
        errors.append("companion relationship pack must contain at least five cases")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    covered_mechanisms: set[str] = set()
    covered_memory_policies: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"companion_relationship.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate companion relationship case id: {case_id}")
        seen_ids.add(case_id)
        if case.get("category") != "relationship_continuity":
            errors.append(f"{prefix}.category must be relationship_continuity")
        if case.get("observation_class") != "scripted_real_entry":
            errors.append(f"{prefix}.observation_class must be scripted_real_entry")

        mechanism = str(case.get("continuity_mechanism") or "")
        if mechanism not in required_mechanisms:
            errors.append(f"{prefix}.continuity_mechanism is invalid: {mechanism}")
        else:
            covered_mechanisms.add(mechanism)

        memory_policy = str(case.get("memory_policy") or "")
        if memory_policy not in allowed_memory_policies:
            errors.append(f"{prefix}.memory_policy is invalid: {memory_policy}")
        else:
            covered_memory_policies.add(memory_policy)

        turns = case.get("turns")
        if not isinstance(turns, list) or len(turns) < 2:
            errors.append(f"{prefix}.turns must contain at least two turns")
            turns = turns if isinstance(turns, list) else []
        for turn in turns:
            text = str(turn)
            if text.startswith("/"):
                continue
            if len(text.strip()) < 4 or not _has_cjk(text):
                errors.append(f"{prefix}.turns must be Chinese user-facing strings or slash commands")
                break
        if not str(case.get("expected_anchor") or "").strip():
            errors.append(f"{prefix}.expected_anchor is required")
        failure_signals = case.get("failure_signals")
        if not isinstance(failure_signals, list) or len(failure_signals) < 2:
            errors.append(f"{prefix}.failure_signals must contain at least two entries")

    missing = required_mechanisms - covered_mechanisms
    if missing:
        errors.append(f"companion relationship pack missing mechanisms: {sorted(missing)}")
    if "session_only" not in covered_memory_policies:
        errors.append("companion relationship pack must include session_only memory policy")
    if "explicit_core_only" not in covered_memory_policies:
        errors.append("companion relationship pack must include explicit_core_only memory policy")
    if "candidate_only" not in covered_memory_policies:
        errors.append("companion relationship pack must include candidate_only memory policy")

    return errors, {
        "case_count": len(cases),
        "covered_mechanisms": sorted(covered_mechanisms),
        "covered_memory_policies": sorted(covered_memory_policies),
        "observation_class": "scripted_real_entry",
    }


def validate_affective_attunement_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("affective attunement pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("affective attunement pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("affective attunement pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_with_llm_judge_eval_only_do_not_import_as_runtime_rule":
        errors.append("affective attunement pack must remain eval data and not runtime rules")
    if payload.get("contract") != "AFFECTIVE_ATTUNEMENT_TIMING_CONTRACT.md":
        errors.append("affective attunement pack must reference AFFECTIVE_ATTUNEMENT_TIMING_CONTRACT.md")

    review_contract = payload.get("review_contract")
    if not isinstance(review_contract, dict):
        errors.append("affective attunement review_contract is required")
        review_contract = {}
    if review_contract.get("observation_class") != "scripted_with_llm_judge":
        errors.append("affective attunement review_contract must use scripted_with_llm_judge")
    if review_contract.get("judge_model") != "gpt-5.5":
        errors.append("affective attunement judge_model must be gpt-5.5")
    if not str(review_contract.get("question") or "").strip():
        errors.append("affective attunement review_contract.question is required")

    required_contexts = {
        "loneliness",
        "playfulness",
        "uncertainty",
        "fatigue",
        "affection",
        "creative_immersion",
    }
    declared_contexts = set(str(item) for item in (payload.get("required_contexts") or []))
    if declared_contexts != required_contexts:
        errors.append(f"affective attunement required_contexts mismatch: {sorted(declared_contexts)}")

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < len(required_contexts):
        errors.append("affective attunement pack must contain at least one case per required context")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    covered_contexts: set[str] = set()
    covered_timing_moves: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"affective_attunement.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate affective attunement case id: {case_id}")
        seen_ids.add(case_id)
        if case.get("category") != "affective_attunement":
            errors.append(f"{prefix}.category must be affective_attunement")
        if case.get("observation_class") != "scripted_with_llm_judge":
            errors.append(f"{prefix}.observation_class must be scripted_with_llm_judge")

        context = str(case.get("emotion_context") or "")
        if context not in required_contexts:
            errors.append(f"{prefix}.emotion_context is invalid: {context}")
        else:
            covered_contexts.add(context)
        timing_move = str(case.get("timing_move") or "")
        if not re.fullmatch(r"[a-z0-9_]+", timing_move):
            errors.append(f"{prefix}.timing_move must be snake_case ascii")
        else:
            covered_timing_moves.add(timing_move)
        prompt = str(case.get("prompt") or "")
        if len(prompt.strip()) < 4 or not _has_cjk(prompt):
            errors.append(f"{prefix}.prompt must be a non-trivial Chinese prompt")
        for key in ("preferred_sequence", "expected_signals", "failure_signals", "forbidden_overconfident_labels"):
            value = case.get(key)
            min_count = 3 if key == "preferred_sequence" else 2
            if not isinstance(value, list) or len(value) < min_count or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least {min_count} non-empty strings")
        failure_text = " ".join(str(item) for item in (case.get("failure_signals") or []))
        forbidden_text = " ".join(str(item) for item in (case.get("forbidden_overconfident_labels") or []))
        if not re.search(r"(确定|真正|知道|诊断|真实|overconfident|label)", failure_text + " " + forbidden_text, re.I):
            errors.append(f"{prefix} must include overconfident label negative signal")

    missing = required_contexts - covered_contexts
    if missing:
        errors.append(f"affective attunement pack missing contexts: {sorted(missing)}")

    return errors, {
        "case_count": len(cases),
        "covered_contexts": sorted(covered_contexts),
        "covered_timing_moves": sorted(covered_timing_moves),
        "observation_class": "scripted_with_llm_judge",
        "judge_model": str(review_contract.get("judge_model") or ""),
    }


def validate_bounded_self_initiative_pack_payload(payload: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("bounded self-initiative pack schema_version must be 1")
    if payload.get("language") != "zh-CN":
        errors.append("bounded self-initiative pack language must be zh-CN")
    if payload.get("claim_boundary") != "operational_proxy_only_not_consciousness_claim":
        errors.append("bounded self-initiative pack claim_boundary must preserve operational proxy only")
    if payload.get("runtime_rule") != "scripted_real_entry_eval_only_do_not_import_as_runtime_rule":
        errors.append("bounded self-initiative pack must remain eval data and not runtime rules")
    if payload.get("contract") != "BOUNDED_SELF_INITIATIVE_MODEL.md":
        errors.append("bounded self-initiative pack must reference BOUNDED_SELF_INITIATIVE_MODEL.md")

    review_contract = payload.get("review_contract")
    if not isinstance(review_contract, dict):
        errors.append("bounded self-initiative review_contract is required")
        review_contract = {}
    if review_contract.get("observation_class") != "scripted_real_entry":
        errors.append("bounded self-initiative review_contract must use scripted_real_entry")
    if not str(review_contract.get("question") or "").strip():
        errors.append("bounded self-initiative review_contract.question is required")

    required_mechanisms = {
        "explicit_followup_proposal",
        "bounded_checkin",
        "candidate_due_only",
        "tool_gate",
        "memory_gate",
        "cancel_or_quiet",
    }
    allowed_consent_policies = {
        "explicit_operator_intent",
        "no_implicit_background",
        "approval_required",
        "cancellable",
    }
    allowed_expiry_policies = {
        "explicit_expiry_required",
        "bounded_default_max",
        "due_candidate_only",
        "proposal_lease_limited",
        "candidate_review_until_approved",
        "operator_cancellable",
    }

    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) < len(required_mechanisms):
        errors.append("bounded self-initiative pack must contain at least one case per required mechanism")
        cases = cases if isinstance(cases, list) else []

    seen_ids: set[str] = set()
    covered_mechanisms: set[str] = set()
    covered_consent_policies: set[str] = set()
    covered_expiry_policies: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"bounded_self_initiative.cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = str(case.get("id") or "")
        if not re.fullmatch(r"[a-z0-9_]+", case_id):
            errors.append(f"{prefix}.id must be snake_case ascii")
        if case_id in seen_ids:
            errors.append(f"duplicate bounded self-initiative case id: {case_id}")
        seen_ids.add(case_id)
        if case.get("category") != "bounded_self_initiative":
            errors.append(f"{prefix}.category must be bounded_self_initiative")
        if case.get("observation_class") != "scripted_real_entry":
            errors.append(f"{prefix}.observation_class must be scripted_real_entry")

        mechanism = str(case.get("initiative_mechanism") or "")
        if mechanism not in required_mechanisms:
            errors.append(f"{prefix}.initiative_mechanism is invalid: {mechanism}")
        else:
            covered_mechanisms.add(mechanism)

        consent_policy = str(case.get("consent_policy") or "")
        if consent_policy not in allowed_consent_policies:
            errors.append(f"{prefix}.consent_policy is invalid: {consent_policy}")
        else:
            covered_consent_policies.add(consent_policy)

        expiry_policy = str(case.get("expiry_policy") or "")
        if expiry_policy not in allowed_expiry_policies:
            errors.append(f"{prefix}.expiry_policy is invalid: {expiry_policy}")
        else:
            covered_expiry_policies.add(expiry_policy)

        turns = case.get("turns")
        if not isinstance(turns, list) or len(turns) < 2:
            errors.append(f"{prefix}.turns must contain at least two turns")
            turns = turns if isinstance(turns, list) else []
        for turn in turns:
            text = str(turn)
            if text.startswith("/"):
                continue
            if len(text.strip()) < 4 or not _has_cjk(text):
                errors.append(f"{prefix}.turns must be Chinese user-facing strings or slash commands")
                break

        for key in ("allowed_action", "expected_anchor"):
            if not str(case.get(key) or "").strip():
                errors.append(f"{prefix}.{key} is required")
        for key in ("forbidden_overreach", "failure_signals"):
            value = case.get(key)
            if not isinstance(value, list) or len(value) < 2 or not all(isinstance(item, str) and item for item in value):
                errors.append(f"{prefix}.{key} must contain at least two non-empty strings")

    missing = required_mechanisms - covered_mechanisms
    if missing:
        errors.append(f"bounded self-initiative pack missing mechanisms: {sorted(missing)}")
    if "approval_required" not in covered_consent_policies:
        errors.append("bounded self-initiative pack must include approval_required consent policy")
    if "explicit_expiry_required" not in covered_expiry_policies:
        errors.append("bounded self-initiative pack must include explicit_expiry_required expiry policy")
    if "due_candidate_only" not in covered_expiry_policies:
        errors.append("bounded self-initiative pack must include due_candidate_only expiry policy")

    return errors, {
        "case_count": len(cases),
        "covered_mechanisms": sorted(covered_mechanisms),
        "covered_consent_policies": sorted(covered_consent_policies),
        "covered_expiry_policies": sorted(covered_expiry_policies),
        "observation_class": "scripted_real_entry",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate EgoOperator experience-first eval contract.")
    parser.add_argument("--sample-pack", default=str(DEFAULT_SAMPLE_PACK))
    parser.add_argument("--rubric", default=str(DEFAULT_RUBRIC))
    parser.add_argument("--claim-calibration", default=str(DEFAULT_CLAIM_CALIBRATION))
    parser.add_argument("--continuity-pack", default=str(DEFAULT_CONTINUITY_REGRESSION_PACK))
    parser.add_argument("--negative-emotion-pack", default=str(DEFAULT_NEGATIVE_EMOTION_PACK))
    parser.add_argument("--emotion-misread-pack", default=str(DEFAULT_EMOTION_MISREAD_PACK))
    parser.add_argument("--adaptation-effectiveness-pack", default=str(DEFAULT_ADAPTATION_EFFECTIVENESS_PACK))
    parser.add_argument("--joi-companion-pack", default=str(DEFAULT_JOI_COMPANION_PACK))
    parser.add_argument("--companion-relationship-pack", default=str(DEFAULT_COMPANION_RELATIONSHIP_PACK))
    parser.add_argument("--affective-attunement-pack", default=str(DEFAULT_AFFECTIVE_ATTUNEMENT_PACK))
    args = parser.parse_args(argv)
    result = validate_sample_pack(
        Path(args.sample_pack),
        Path(args.rubric),
        Path(args.claim_calibration),
        Path(args.continuity_pack),
        Path(args.negative_emotion_pack),
        Path(args.emotion_misread_pack),
        Path(args.adaptation_effectiveness_pack),
        Path(args.joi_companion_pack),
        Path(args.companion_relationship_pack),
        Path(args.affective_attunement_pack),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
