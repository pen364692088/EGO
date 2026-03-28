import json
from pathlib import Path

from openemotion.self_model.model import SelfModel, create_default_self_model


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "self_model.schema.json"


def test_owner_model_matches_required_schema_keys():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = create_default_self_model("openemotion").to_dict()

    missing = [key for key in schema["required"] if key not in payload]
    assert missing == []


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

    assert payload["schema_version"] == "1.0.0"
    assert isinstance(payload["modification_audit_trail"], list)
