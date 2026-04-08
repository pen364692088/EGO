from __future__ import annotations

import ast
from pathlib import Path

from emotiond.self_model_adapter import (
    ACTIVE_RUNTIME_SUBSTRATE as ADAPTER_ACTIVE_RUNTIME_SUBSTRATE,
    AUTHORITY_STATUS as ADAPTER_AUTHORITY_STATUS,
    COMPATIBILITY_REASON as ADAPTER_COMPATIBILITY_REASON,
    FORMAL_MAINLINE_ENABLED as ADAPTER_FORMAL_MAINLINE_ENABLED,
    LIVE_RUNTIME_AUTHORITY as ADAPTER_LIVE_RUNTIME_AUTHORITY,
)
from emotiond.self_model_mirror import (
    ACTIVE_RUNTIME_SUBSTRATE as MIRROR_ACTIVE_RUNTIME_SUBSTRATE,
    AUTHORITY_STATUS as MIRROR_AUTHORITY_STATUS,
    FORMAL_MAINLINE_ENABLED as MIRROR_FORMAL_MAINLINE_ENABLED,
    LIVE_RUNTIME_AUTHORITY as MIRROR_LIVE_RUNTIME_AUTHORITY,
    REFERENCE_ONLY_REASON as MIRROR_REFERENCE_ONLY_REASON,
)
from openemotion.proto_self.state import SelfModel as RuntimeSelfModel
from openemotion.proto_self_v2.state import ProtoSelfStateV2
from openemotion.self_model import (
    ACTIVE_RUNTIME_SUBSTRATE,
    ACTIVE_RUNTIME_SUBSTRATE_ROLE,
    FORMAL_MAINLINE_ENABLED,
    LIVE_RUNTIME_AUTHORITY,
    PACKAGE_ACTIVE_RUNTIME_SUBSTRATE,
    PACKAGE_ACTIVE_RUNTIME_SUBSTRATE_ROLE,
    PACKAGE_AUTHORITY_STATUS,
    PACKAGE_FORMAL_MAINLINE_ENABLED,
    PACKAGE_LIVE_RUNTIME_AUTHORITY,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _imports_module(rel_path: str, module_prefix: str) -> bool:
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=rel_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_prefix or alias.name.startswith(f"{module_prefix}."):
                    return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == module_prefix or module.startswith(f"{module_prefix}."):
                return True
    return False


def test_self_model_owner_and_legacy_surfaces_are_explicit():
    assert PACKAGE_AUTHORITY_STATUS == "formal_owner"
    assert PACKAGE_FORMAL_MAINLINE_ENABLED is True
    assert PACKAGE_LIVE_RUNTIME_AUTHORITY == "openemotion.self_model"
    assert PACKAGE_ACTIVE_RUNTIME_SUBSTRATE == "openemotion.proto_self.self_model"
    assert PACKAGE_ACTIVE_RUNTIME_SUBSTRATE_ROLE == "compute_proposal_only"

    assert FORMAL_MAINLINE_ENABLED is True
    assert LIVE_RUNTIME_AUTHORITY == "openemotion.self_model"
    assert ACTIVE_RUNTIME_SUBSTRATE == "openemotion.proto_self.self_model"
    assert ACTIVE_RUNTIME_SUBSTRATE_ROLE == "compute_proposal_only"

    assert ADAPTER_AUTHORITY_STATUS == "compatibility_only"
    assert ADAPTER_FORMAL_MAINLINE_ENABLED is False
    assert ADAPTER_LIVE_RUNTIME_AUTHORITY == "openemotion.self_model"
    assert ADAPTER_ACTIVE_RUNTIME_SUBSTRATE == "openemotion.proto_self.self_model"
    assert "formal mainline" in ADAPTER_COMPATIBILITY_REASON

    assert MIRROR_AUTHORITY_STATUS == "reference_only"
    assert MIRROR_FORMAL_MAINLINE_ENABLED is False
    assert MIRROR_LIVE_RUNTIME_AUTHORITY == "openemotion.self_model"
    assert MIRROR_ACTIVE_RUNTIME_SUBSTRATE == "openemotion.proto_self.self_model"
    assert "formal mainline" in MIRROR_REFERENCE_ONLY_REASON


def test_proto_self_v2_self_model_state_shape_still_uses_runtime_substrate():
    self_model_field = ProtoSelfStateV2.__dataclass_fields__["self_model"]
    assert self_model_field.default_factory is RuntimeSelfModel


def test_formal_mainline_uses_formal_owner_not_legacy_self_model_surfaces():
    assert _imports_module(
        "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
        "openemotion.self_model",
    ) is True
    assert _imports_module(
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "openemotion.self_model",
    ) is True

    for rel_path in (
        "OpenEmotion/openemotion/proto_self_v2/kernel.py",
        "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        assert _imports_module(rel_path, "emotiond.self_model_adapter") is False
        assert _imports_module(rel_path, "emotiond.self_model_mirror") is False


def test_egocore_does_not_take_self_model_runtime_ownership():
    for rel_path in (
        "EgoCore/app/openemotion_hooks/native_hooks.py",
        "EgoCore/app/runtime_v2/proto_self_runtime.py",
        "EgoCore/app/openemotion_adapter/proto_self_adapter.py",
    ):
        assert _imports_module(rel_path, "openemotion.proto_self.self_model") is False


def test_legacy_wiring_tool_does_not_import_reference_only_mirror_module():
    assert _imports_module(
        "OpenEmotion/tools/main_chain_wiring_check.py",
        "emotiond.self_model_mirror",
    ) is False


def test_program_state_marks_adapter_evidence_as_historical_shadow_only():
    text = (REPO_ROOT / "OpenEmotion/docs/PROGRAM_STATE_UNIFIED.yaml").read_text(encoding="utf-8")
    assert "OpenEmotion/docs/archive/E2E_SELF_MODEL_ADAPTER_REPORT.md" in text
    assert "历史 SelfModelAdapter shadow wiring 证据" in text
    assert "adapter 非 formal mainline" in text
