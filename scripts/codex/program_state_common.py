#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

PROGRAM_STATE_PATH = ROOT / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
STATUS_MD_PATH = ROOT / "docs" / "STATUS.md"
SUMMARY_MD_PATH = ROOT / "artifacts" / "reports" / "program_state_summary.md"
EGOCORE_PROGRAM_STATE_MIRROR = ROOT / "EgoCore" / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
OPENEMOTION_PROGRAM_STATE_MIRROR = ROOT / "OpenEmotion" / "docs" / "PROGRAM_STATE_UNIFIED.yaml"
EVIDENCE_LEDGER_DIR = ROOT / "artifacts" / "evidence_ledger"
EVIDENCE_LEDGER_SCHEMA_PATH = EVIDENCE_LEDGER_DIR / "schema.yaml"
EVIDENCE_LEDGER_INDEX_PATH = EVIDENCE_LEDGER_DIR / "index.yaml"
SHIM_REGISTER_PATH = ROOT / "EgoCore" / "SHIM_REGISTER.md"

EVIDENCE_LEVELS = [f"E{index}" for index in range(0, 7)]
VERIFICATION_LEVELS = [f"V{index}" for index in range(0, 6)]
SOURCE_TYPES = ["doc", "unit", "simulated", "integration", "real_channel", "observation"]
ENTRY_STATUSES = ["pass", "fail", "partial"]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def evidence_rank(level: str) -> int:
    try:
        return EVIDENCE_LEVELS.index(level)
    except ValueError:
        return -1


def verification_rank(level: str) -> int:
    try:
        return VERIFICATION_LEVELS.index(level)
    except ValueError:
        return -1


def highest_evidence_entry(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = sorted(entries, key=lambda item: evidence_rank(str(item.get("evidence_level", ""))), reverse=True)
    return ranked[0] if ranked else None


def render_state_yaml_with_header(data: dict[str, Any], *, header: str) -> str:
    return f"{header}\n{dump_yaml(data)}"


def validate_program_state_schema(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    program = data.get("program")
    if not isinstance(program, dict):
        return ["missing top-level `program` mapping"]

    required_program_fields = [
        "version",
        "north_star",
        "current_phase",
        "current_layer",
        "highest_evidence_level",
        "verification_level",
        "mainline_connected",
        "enabled",
        "real_trigger_evidence",
        "current_focus",
        "completed_since_last",
        "blocked_by",
        "key_unknowns",
        "next_minimal_action",
        "last_verified_commit",
        "last_verified_at",
        "status_owner",
    ]
    for field in required_program_fields:
        if field not in program:
            errors.append(f"program missing required field: {field}")

    if str(program.get("highest_evidence_level")) not in EVIDENCE_LEVELS:
        errors.append("program.highest_evidence_level must be one of E0..E6")
    if str(program.get("verification_level")) not in VERIFICATION_LEVELS:
        errors.append("program.verification_level must be one of V0..V5")

    for field in [
        "real_trigger_evidence",
        "current_focus",
        "completed_since_last",
        "blocked_by",
        "key_unknowns",
    ]:
        if not isinstance(program.get(field), list):
            errors.append(f"program.{field} must be a list")

    integrity = data.get("integrity")
    if not isinstance(integrity, dict):
        errors.append("missing top-level `integrity` mapping")
    else:
        if not isinstance(integrity.get("generated_views"), list):
            errors.append("integrity.generated_views must be a list")
        for field in ["evidence_ledger_dir", "shim_register"]:
            if not integrity.get(field):
                errors.append(f"integrity.{field} must be set")

    workstreams = data.get("workstreams")
    if not isinstance(workstreams, list):
        errors.append("top-level `workstreams` must be a list")
    else:
        required_workstream_fields = [
            "id",
            "owner",
            "status",
            "evidence_level",
            "verification_level",
            "mainline_connected",
            "enabled",
            "summary",
        ]
        for index, item in enumerate(workstreams):
            if not isinstance(item, dict):
                errors.append(f"workstreams[{index}] must be a mapping")
                continue
            for field in required_workstream_fields:
                if field not in item:
                    errors.append(f"workstreams[{index}] missing required field: {field}")
            if str(item.get("evidence_level")) not in EVIDENCE_LEVELS:
                errors.append(f"workstreams[{index}].evidence_level must be one of E0..E6")
            if str(item.get("verification_level")) not in VERIFICATION_LEVELS:
                errors.append(f"workstreams[{index}].verification_level must be one of V0..V5")

    return errors


def validate_evidence_index(index: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = index.get("entries")
    if not isinstance(entries, list):
        return ["evidence ledger index must contain an `entries` list"]

    required_fields = [
        "evidence_id",
        "status",
        "evidence_level",
        "source_type",
        "artifact_path",
        "what_it_proves",
        "what_it_does_not_prove",
        "related_workstream",
        "created_at",
        "created_from_commit",
    ]
    for index_value, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entries[{index_value}] must be a mapping")
            continue
        for field in required_fields:
            value = entry.get(field)
            if value in (None, "", []):
                errors.append(f"entries[{index_value}] missing required field: {field}")
        if str(entry.get("status")) not in ENTRY_STATUSES:
            errors.append(f"entries[{index_value}].status must be one of {', '.join(ENTRY_STATUSES)}")
        if str(entry.get("evidence_level")) not in EVIDENCE_LEVELS:
            errors.append(f"entries[{index_value}].evidence_level must be one of E0..E6")
        if str(entry.get("source_type")) not in SOURCE_TYPES:
            errors.append(f"entries[{index_value}].source_type must be one of {', '.join(SOURCE_TYPES)}")
    return errors


def render_status_markdown(program_state: dict[str, Any], evidence_index: dict[str, Any]) -> str:
    program = program_state["program"]
    workstreams = program_state.get("workstreams") or []
    entries = evidence_index.get("entries") or []
    highest_entry = highest_evidence_entry(entries)

    lines = [
        "# Project Status",
        "",
        "> AUTO-GENERATED FILE. Do not edit by hand.",
        f"> Source of truth: `{PROGRAM_STATE_PATH.relative_to(ROOT)}`",
        f"> Evidence ledger: `{EVIDENCE_LEDGER_INDEX_PATH.relative_to(ROOT)}`",
        "",
        "## Current Snapshot",
        "",
        "| field | value |",
        "|---|---|",
        f"| current_phase | `{program['current_phase']}` |",
        f"| current_layer | `{program['current_layer']}` |",
        f"| highest_evidence_level | `{program['highest_evidence_level']}` |",
        f"| verification_level | `{program['verification_level']}` |",
        f"| mainline_connected | `{program['mainline_connected']}` |",
        f"| enabled | `{program['enabled']}` |",
        f"| last_verified_commit | `{program['last_verified_commit']}` |",
        f"| last_verified_at | `{program['last_verified_at']}` |",
        "",
        "## North Star",
        "",
        program["north_star"],
        "",
        "## Current Focus",
        "",
    ]
    lines.extend(f"- {item}" for item in program["current_focus"])
    lines.extend(
        [
            "",
            "## Completed Since Last Update",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in program["completed_since_last"])
    lines.extend(
        [
            "",
            "## Blockers",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in program["blocked_by"])
    lines.extend(
        [
            "",
            "## Key Unknowns",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in program["key_unknowns"])
    lines.extend(
        [
            "",
            "## Next Minimal Action",
            "",
            program["next_minimal_action"],
            "",
            "## Real Trigger Evidence",
            "",
        ]
    )
    for item in program["real_trigger_evidence"]:
        if isinstance(item, dict):
            evidence_id = item.get("evidence_id", "unknown")
            note = item.get("note", "")
            lines.append(f"- `{evidence_id}`: {note}")
        else:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Workstreams",
            "",
            "| id | owner | status | evidence | verification | mainline_connected | enabled | summary |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in workstreams:
        lines.append(
            "| {id} | {owner} | `{status}` | `{evidence}` | `{verification}` | `{mainline}` | `{enabled}` | {summary} |".format(
                id=item["id"],
                owner=item["owner"],
                status=item["status"],
                evidence=item["evidence_level"],
                verification=item["verification_level"],
                mainline=item["mainline_connected"],
                enabled=item["enabled"],
                summary=item["summary"].replace("|", "\\|"),
            )
        )

    lines.extend(
        [
            "",
            "## Evidence Ledger Summary",
            "",
            f"- total entries: `{len(entries)}`",
            f"- highest entry: `{highest_entry['evidence_id']}` / `{highest_entry['evidence_level']}` / `{highest_entry['status']}`"
            if highest_entry
            else "- highest entry: `none`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def render_summary_markdown(program_state: dict[str, Any], evidence_index: dict[str, Any]) -> str:
    program = program_state["program"]
    highest_entry = highest_evidence_entry(evidence_index.get("entries") or [])
    lines = [
        "# Program State Summary",
        "",
        "> AUTO-GENERATED FILE. Do not edit by hand.",
        "",
        f"- phase: `{program['current_phase']}`",
        f"- layer: `{program['current_layer']}`",
        f"- highest evidence: `{program['highest_evidence_level']}`",
        f"- verification: `{program['verification_level']}`",
        f"- mainline_connected: `{program['mainline_connected']}`",
        f"- enabled: `{program['enabled']}`",
        f"- next_minimal_action: {program['next_minimal_action']}",
        f"- highest ledger entry: `{highest_entry['evidence_id']}` / `{highest_entry['evidence_level']}`"
        if highest_entry
        else "- highest ledger entry: `none`",
        "",
    ]
    return "\n".join(lines) + "\n"
