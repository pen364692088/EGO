from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


ROOT = Path(__file__).resolve().parents[2]
SCENARIO_BANK_DIR = ROOT / "OpenEmotion" / "scenarios" / "mvp17_observation_bank"
SCENARIO_MANIFEST_SCHEMA_VERSION = "mvp17.observation_scenario.v1"
ALLOWED_SCENARIO_SOURCE_CLASSES = ("open_license", "user_owned", "repo_authored")


def _trim(value: Any) -> str:
    return str(value or "").strip()


def _validate_string_list(items: Any) -> bool:
    if not isinstance(items, list) or not items:
        return False
    normalized = [_trim(item) for item in items if _trim(item)]
    return len(normalized) == len(items)


def validate_scenario_manifest(manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if _trim(manifest.get("schema_version")) != SCENARIO_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version")
    if not _trim(manifest.get("scenario_id")):
        errors.append("scenario_id")

    source_class = _trim(manifest.get("source_class"))
    if source_class not in ALLOWED_SCENARIO_SOURCE_CLASSES:
        errors.append("source_class")

    for field_name in ("source_ref", "license_note", "dialogue_frame_target"):
        if not _trim(manifest.get(field_name)):
            errors.append(field_name)

    if not _validate_string_list(manifest.get("messages")):
        errors.append("messages")

    try:
        idle_seconds = float(manifest.get("idle_seconds"))
    except (TypeError, ValueError):
        errors.append("idle_seconds")
    else:
        if idle_seconds <= 0:
            errors.append("idle_seconds")

    for field_name in ("resource_budget_hint", "maintenance_context", "social_context", "owner_bootstrap"):
        value = manifest.get(field_name)
        if value is not None and not isinstance(value, dict):
            errors.append(field_name)
    return sorted(set(errors))


def load_scenario_manifest(path: str | Path) -> Dict[str, Any]:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = validate_scenario_manifest(payload)
    if errors:
        raise ValueError(f"invalid MVP17 scenario manifest {manifest_path}: {', '.join(errors)}")
    return {
        "schema_version": SCENARIO_MANIFEST_SCHEMA_VERSION,
        "scenario_id": _trim(payload["scenario_id"]),
        "source_class": _trim(payload["source_class"]),
        "source_ref": _trim(payload["source_ref"]),
        "license_note": _trim(payload["license_note"]),
        "dialogue_frame_target": _trim(payload["dialogue_frame_target"]),
        "messages": [_trim(item) for item in payload["messages"]],
        "idle_seconds": float(payload["idle_seconds"]),
        "resource_budget_hint": dict(payload.get("resource_budget_hint") or {}),
        "maintenance_context": dict(payload.get("maintenance_context") or {}),
        "social_context": dict(payload.get("social_context") or {}),
        "owner_bootstrap": dict(payload.get("owner_bootstrap") or {}),
        "manifest_path": str(manifest_path),
    }


def load_scenario_bank(
    bank_dir: str | Path = SCENARIO_BANK_DIR,
    *,
    scenario_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    bank_path = Path(bank_dir)
    selected = {item.strip() for item in (scenario_ids or []) if str(item).strip()}
    manifests: List[Dict[str, Any]] = []
    for manifest_path in sorted(bank_path.glob("*.json")):
        manifest = load_scenario_manifest(manifest_path)
        if selected and manifest["scenario_id"] not in selected:
            continue
        manifests.append(manifest)
    return manifests
