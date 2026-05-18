from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from openemotion.proto_self_v2.seed_schemas import SEED_SUBJECT_PROFILE


def _contract_path() -> Path:
    return Path(__file__).resolve().parents[2] / "contracts" / "proto_self_v2.schema.json"


@lru_cache(maxsize=1)
def load_proto_self_v2_schema() -> Dict[str, Any]:
    return json.loads(_contract_path().read_text(encoding="utf-8"))


def _fallback_validate(value: Any, schema: Dict[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if value is None and "null" in expected_type:
            return
        if "object" in expected_type and isinstance(value, dict):
            pass
        elif "string" in expected_type and isinstance(value, str):
            pass
        else:
            raise ValueError(f"{path}: expected one of {expected_type}, got {type(value).__name__}")
    elif expected_type == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object, got {type(value).__name__}")
        for required_key in schema.get("required", []):
            if required_key not in value:
                raise ValueError(f"{path}: missing required field '{required_key}'")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, child in properties.items():
            if key in value:
                _fallback_validate(value[key], child, f"{path}.{key}" if path else key)
        if additional is False:
            unknown = sorted(set(value.keys()) - set(properties.keys()))
            if unknown:
                raise ValueError(f"{path}: unexpected fields {unknown}")
    elif expected_type == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected string, got {type(value).__name__}")

    const = schema.get("const")
    if const is not None and value != const:
        raise ValueError(f"{path}: expected const {const!r}, got {value!r}")


def validate_proto_self_v2_payload(payload: Dict[str, Any]) -> None:
    schema = load_proto_self_v2_schema()
    event_type = ((payload.get("event") or {}).get("event_type") or payload.get("event_type") or "").strip()
    seed_event_required = payload.get("subject_profile") == SEED_SUBJECT_PROFILE and event_type not in {
        "developmental_tick",
        "developmental_replay",
    }
    try:
        import jsonschema  # type: ignore
    except Exception:
        _fallback_validate(payload, schema, "payload")
        if seed_event_required and not isinstance(payload.get("seed_event"), dict):
            raise ValueError("payload.seed_event: required when subject_profile=seed_v0_2")
        return

    try:
        jsonschema.validate(payload, schema)
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        path = ".".join(str(part) for part in exc.absolute_path)
        where = f"payload.{path}" if path else "payload"
        raise ValueError(f"{where}: {exc.message}") from exc

    if seed_event_required and not isinstance(payload.get("seed_event"), dict):
        raise ValueError("payload.seed_event: required when subject_profile=seed_v0_2")
