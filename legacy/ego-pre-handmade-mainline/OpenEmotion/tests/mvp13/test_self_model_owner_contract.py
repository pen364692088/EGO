import json
from pathlib import Path

from openemotion.self_model.model import (
    FORMAL_OWNER_SCHEMA_VERSION,
    PHASE1_ALLOWED_PROOF_LEVERS,
    PHASE1_AUTHORITATIVE_FIELDS,
    PHASE1_LEGACY_REFERENCE_ONLY_FIELDS,
    RUNTIME_LOCAL_PROJECTION_FIELD,
    RUNTIME_LOCAL_PROJECTION_SEMANTICS,
    SelfModel,
    create_default_self_model,
)


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "self_model.schema.json"


def test_owner_model_matches_required_schema_keys():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = create_default_self_model("openemotion").to_dict()

    assert tuple(schema["required"]) == PHASE1_AUTHORITATIVE_FIELDS
    assert tuple(payload.keys()) == PHASE1_AUTHORITATIVE_FIELDS


def test_owner_model_uses_identity_handle_not_model_handle():
    payload = create_default_self_model("openemotion").to_dict()

    assert payload["identity_handle"] == "openemotion"
    assert "model_handle" not in payload


def test_owner_model_from_dict_accepts_legacy_model_handle():
    payload = create_default_self_model("openemotion").to_dict()
    payload["model_handle"] = payload.pop("identity_handle")

    restored = SelfModel.from_dict(payload)

    assert restored.identity_handle == "openemotion"


def test_owner_model_emits_schema_and_audit_fields():
    payload = create_default_self_model("openemotion").to_dict()

    assert payload["schema_version"] == FORMAL_OWNER_SCHEMA_VERSION
    assert isinstance(payload["modification_audit_trail"], list)


def test_owner_contract_schema_metadata_matches_model_constants():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert tuple(schema["x_phase1_authoritative_fields"]) == PHASE1_AUTHORITATIVE_FIELDS
    assert tuple(schema["x_phase1_allowed_proof_levers"]) == PHASE1_ALLOWED_PROOF_LEVERS
    assert tuple(schema["x_phase1_legacy_reference_only_fields"]) == PHASE1_LEGACY_REFERENCE_ONLY_FIELDS
    assert schema["x_runtime_local_projection_field"] == RUNTIME_LOCAL_PROJECTION_FIELD
    assert schema["x_runtime_local_projection_semantics"] == RUNTIME_LOCAL_PROJECTION_SEMANTICS


def test_owner_contract_excludes_legacy_only_fields_from_proof_surface():
    payload = create_default_self_model("openemotion").to_dict()

    for field in PHASE1_LEGACY_REFERENCE_ONLY_FIELDS:
        assert field not in payload
        assert field not in PHASE1_ALLOWED_PROOF_LEVERS


def test_standing_commitment_binding_level_is_required_by_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    required = schema["properties"]["standing_commitments"]["items"]["required"]

    assert "binding_level" in required
