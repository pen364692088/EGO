#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from program_state_common import (
    EVIDENCE_LEDGER_INDEX_PATH,
    EVIDENCE_LEVELS,
    EVIDENCE_LEDGER_SCHEMA_PATH,
    EGOCORE_PROGRAM_STATE_MIRROR,
    OPENEMOTION_PROGRAM_STATE_MIRROR,
    PROGRAM_STATE_PATH,
    ROOT,
    SHIM_REGISTER_PATH,
    STATUS_MD_PATH,
    SUMMARY_MD_PATH,
    evidence_rank,
    highest_evidence_entry,
    load_yaml,
    render_state_yaml_with_header,
    render_status_markdown,
    render_summary_markdown,
    validate_evidence_index,
    validate_program_state_schema,
)


ROOT_README = ROOT / "README.md"
LEGACY_PRE_HANDMADE_ROOT = ROOT / "legacy" / "ego-pre-handmade-mainline"
EGOCORE_README = LEGACY_PRE_HANDMADE_ROOT / "EgoCore" / "README.md"
OPENEMOTION_README = LEGACY_PRE_HANDMADE_ROOT / "OpenEmotion" / "README.md"
CURRENT_LOGIC_FLOW = ROOT / "docs" / "CURRENT_PROJECT_LOGIC_FLOW.md"
ACCEPTANCE_CHAINS = ROOT / "docs" / "ACCEPTANCE_CHAINS.md"
EXPERIENCE_SCRIPTS = ROOT / "docs" / "EXPERIENCE_SCRIPTS.md"
CLAIM_LANGUAGE_POLICY = ROOT / "docs" / "CLAIM_LANGUAGE_POLICY.md"
AGENTS_PATH = ROOT / "AGENTS.md"
TASK_TEMPLATE_PATH = ROOT / "docs" / "templates" / "CODEX_TASK_TEMPLATE.md"
PR_TEMPLATE_PATH = ROOT / ".github" / "pull_request_template.md"

CORE_DIR_PREFIXES = [
    ".github/",
    "docs/",
    "scripts/codex/",
    "Ego_handmade/",
    "legacy/ego-pre-handmade-mainline/EgoCore/app/runtime_v2/",
    "legacy/ego-pre-handmade-mainline/EgoCore/app/openemotion_adapter/",
    "legacy/ego-pre-handmade-mainline/EgoCore/app/openemotion_hooks/",
    "legacy/ego-pre-handmade-mainline/EgoCore/app/dashboard/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/proto_self/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/proto_self_v2/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/self_model/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/endogenous_drives/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/reflective_self/",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/openemotion/developmental_self/",
    "README.md",
    "legacy/ego-pre-handmade-mainline/EgoCore/README.md",
    "legacy/ego-pre-handmade-mainline/OpenEmotion/README.md",
]

CLAIM_PATTERNS = {
    r"已接主链": "E4",
    r"已启用": "E4",
    r"已生效": "E4",
    r"\bverified\b": "E4",
}

TASK_TEMPLATE_REQUIRED_SNIPPETS = [
    "当前 phase",
    "当前 layer",
    "当前 evidence level",
    "本任务预期改变哪个状态字段",
    "本任务不能证明什么",
    "是否涉及 boundary / authority source / shim",
    "是否需要更新 evidence ledger",
    "下一步最小闭环动作",
]

PR_TEMPLATE_REQUIRED_SNIPPETS = [
    "Current phase",
    "Current layer",
    "Current evidence level",
    "Expected state-field changes",
    "What this PR does not prove",
    "Boundary / authority / shim impact",
    "Evidence ledger update",
    "Next minimal closed-loop action",
]

AGENTS_REQUIRED_SNIPPETS = [
    "Read `docs/PROGRAM_STATE_UNIFIED.yaml`",
    "Summarize `current_phase / current_layer / highest_evidence_level / next_minimal_action`",
    "If implementation changes project state, update `PROGRAM_STATE_UNIFIED.yaml`",
    "If implementation changes evidence, update `artifacts/evidence_ledger`",
    "Regenerate derived views",
    "Never claim a conclusion stronger than the current evidence level",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check repo-level program state integrity")
    parser.add_argument("--base-ref", help="Optional git base ref for changed-file detection")
    parser.add_argument("--head-ref", help="Optional git head ref for changed-file detection")
    parser.add_argument("--skip-diff-check", action="store_true", help="Skip changed-file based drift rules")
    return parser.parse_args()


def _run_git(args: list[str]) -> list[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _changed_files(base_ref: str | None, head_ref: str | None) -> list[str]:
    if base_ref and head_ref:
        return _run_git(["diff", "--name-only", f"{base_ref}...{head_ref}"])

    files = set(_run_git(["diff", "--name-only", "HEAD"]))
    files.update(_run_git(["diff", "--name-only", "--cached", "HEAD"]))
    if not files:
        files.update(_run_git(["status", "--short"]))
        normalized: set[str] = set()
        for item in files:
            normalized.add(item[3:] if len(item) > 3 else item)
        return sorted(path for path in normalized if path)
    return sorted(files)


def _any_path_matches(paths: Iterable[str], prefixes: Iterable[str]) -> bool:
    return any(any(path == prefix or path.startswith(prefix) for prefix in prefixes) for path in paths)


def _contains_required_snippets(path: Path, snippets: list[str], label: str) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{label} missing: {path.relative_to(ROOT)}"]
    text = path.read_text(encoding="utf-8")
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{label} missing required snippet `{snippet}` in {path.relative_to(ROOT)}")
    return errors


def _expected_mirror_yaml(program_state: dict[str, object]) -> str:
    header = (
        "# AUTO-GENERATED COMPATIBILITY MIRROR\n"
        "# Source of truth: docs/PROGRAM_STATE_UNIFIED.yaml\n"
        "# Do not edit this file by hand. Edit docs/PROGRAM_STATE_UNIFIED.yaml and regenerate derived views.\n"
    )
    return render_state_yaml_with_header(program_state, header=header)


def main() -> int:
    args = parse_args()
    program_state = load_yaml(PROGRAM_STATE_PATH)
    evidence_schema = load_yaml(EVIDENCE_LEDGER_SCHEMA_PATH)
    evidence_index = load_yaml(EVIDENCE_LEDGER_INDEX_PATH)

    errors: list[str] = []
    errors.extend(validate_program_state_schema(program_state))
    errors.extend(validate_evidence_index(evidence_index))

    if not evidence_schema.get("required_fields"):
        errors.append("artifacts/evidence_ledger/schema.yaml must define required_fields")

    entries = evidence_index.get("entries") or []
    highest_entry = highest_evidence_entry(entries)
    highest_entry_level = str(highest_entry.get("evidence_level")) if highest_entry else "E0"
    program_level = str((program_state.get("program") or {}).get("highest_evidence_level", "E0"))
    if evidence_rank(program_level) > evidence_rank(highest_entry_level):
        errors.append(
            "program.highest_evidence_level exceeds the highest evidence level present in artifacts/evidence_ledger/index.yaml"
        )

    expected_status = render_status_markdown(program_state, evidence_index)
    expected_summary = render_summary_markdown(program_state, evidence_index)
    expected_mirror = _expected_mirror_yaml(program_state)

    file_expectations = {
        STATUS_MD_PATH: expected_status,
        SUMMARY_MD_PATH: expected_summary,
        EGOCORE_PROGRAM_STATE_MIRROR: expected_mirror,
        OPENEMOTION_PROGRAM_STATE_MIRROR: expected_mirror,
    }
    for path, expected in file_expectations.items():
        if not path.exists():
            errors.append(f"generated file missing: {path.relative_to(ROOT)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"generated file drift detected in {path.relative_to(ROOT)}; run python3 scripts/codex/generate_program_state_views.py"
            )

    integrity = program_state.get("integrity") or {}
    declared_generated = set(integrity.get("generated_views") or [])
    expected_generated = {
        "docs/STATUS.md",
        "artifacts/reports/program_state_summary.md",
        "legacy/ego-pre-handmade-mainline/EgoCore/docs/PROGRAM_STATE_UNIFIED.yaml",
        "legacy/ego-pre-handmade-mainline/OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml",
    }
    if declared_generated != expected_generated:
        errors.append("integrity.generated_views must exactly enumerate the generated status outputs and compatibility mirrors")
    if integrity.get("shim_register") != str(SHIM_REGISTER_PATH.relative_to(ROOT)):
        errors.append("integrity.shim_register must point at legacy/ego-pre-handmade-mainline/EgoCore/SHIM_REGISTER.md")

    for path in [ROOT_README, EGOCORE_README, OPENEMOTION_README, CURRENT_LOGIC_FLOW]:
        if not path.exists():
            errors.append(f"required authority document missing: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        if "docs/PROGRAM_STATE_UNIFIED.yaml" not in text:
            errors.append(f"{path.relative_to(ROOT)} must reference docs/PROGRAM_STATE_UNIFIED.yaml")

    claim_scan_paths = [
        ROOT_README,
        EGOCORE_README,
        OPENEMOTION_README,
        CURRENT_LOGIC_FLOW,
        ACCEPTANCE_CHAINS,
        EXPERIENCE_SCRIPTS,
        CLAIM_LANGUAGE_POLICY,
    ]
    for path in claim_scan_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, min_level in CLAIM_PATTERNS.items():
            if re.search(pattern, text, flags=re.IGNORECASE) and evidence_rank(highest_entry_level) < evidence_rank(min_level):
                errors.append(
                    f"{path.relative_to(ROOT)} contains `{pattern}` but the evidence ledger only reaches {highest_entry_level}"
                )

    if not any(entry.get("status") in {"fail", "partial"} for entry in entries):
        errors.append("evidence ledger must include at least one failure or partial entry")

    errors.extend(_contains_required_snippets(TASK_TEMPLATE_PATH, TASK_TEMPLATE_REQUIRED_SNIPPETS, "task template"))
    errors.extend(_contains_required_snippets(PR_TEMPLATE_PATH, PR_TEMPLATE_REQUIRED_SNIPPETS, "PR template"))
    errors.extend(_contains_required_snippets(AGENTS_PATH, AGENTS_REQUIRED_SNIPPETS, "AGENTS"))

    if not args.skip_diff_check:
        changed_files = _changed_files(args.base_ref, args.head_ref)
        state_path_str = str(PROGRAM_STATE_PATH.relative_to(ROOT))
        shim_path_str = str(SHIM_REGISTER_PATH.relative_to(ROOT))
        if _any_path_matches(changed_files, CORE_DIR_PREFIXES) and state_path_str not in changed_files:
            errors.append(
                "core governance/mainline paths changed without updating docs/PROGRAM_STATE_UNIFIED.yaml"
            )
        shim_like_changes = [
            path for path in changed_files if re.search(r"(shim|mirror|adapter)", path, flags=re.IGNORECASE)
        ]
        if shim_like_changes and shim_path_str not in changed_files:
            errors.append(
                "shim/mirror/adapter-related changes detected without updating legacy/ego-pre-handmade-mainline/EgoCore/SHIM_REGISTER.md"
            )

    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1

    print("program state integrity check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
